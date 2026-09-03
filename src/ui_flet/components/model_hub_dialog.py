"""
AI Model Hub & Marketplace Component for Flet UI.
Provides a comprehensive manager allowing users to browse, download, delete, and inspect
offline AI speech models with dynamic hardware detection and drive space monitoring.
Can be rendered both embedded directly in SettingsView and as a standalone Modal Dialog.
"""
import asyncio
import os
import threading
from typing import Callable, Optional
import flet as ft

from src.i18n import t
from src.core.errors import DocumentError, ErrorCode
from src.ui_flet.components.message_dialog import show_message_dialog, DialogType
from src.services.hardware_detector import detect_hardware, recommend_model, HardwareInfo
from src.services.model_manager import (
    AVAILABLE_MODELS,
    ModelMetadata,
    download_model,
    delete_model,
    clean_all_models,
    is_model_installed,
    is_model_downloading,
    get_model_download_progress,
    add_download_listener,
    remove_download_listener,
    register_model_download,
    cancel_model_download,
    get_models_dir,
    get_storage_usage,
    verify_model_runtime,
)
from src.ui_flet.theme import PALETTES, resolve_color, get_style_color, make_border, is_theme_dark
from src.utils.env import open_file_or_folder_foreground


def build_model_hub_view(
    page: Optional[ft.Page] = None,
    current_palette: str = "Violet Cyberpunk",
    is_dark: Optional[bool] = None,
    on_models_changed: Optional[Callable[[], None]] = None,
    is_embedded: bool = False,
    on_close_dialog: Optional[Callable[[], None]] = None,
) -> ft.Container:
    """
    Builds the core Model Hub view containing hardware banner, model cards grid, and storage footer.
    """
    if is_dark is None:
        if page and hasattr(page, "theme_mode"):
            is_dark = page.theme_mode != ft.ThemeMode.LIGHT
        else:
            is_dark = True

    palette = PALETTES.get(current_palette, PALETTES["Violet Cyberpunk"])

    text_primary = get_style_color("text_primary", is_dark)
    text_secondary = get_style_color("text_muted", is_dark)
    accent_primary = resolve_color(palette, "text_accent_primary", is_dark)
    border_color = resolve_color(palette, "border_color", is_dark)
    card_bg = resolve_color(palette, "bg_pane", is_dark)
    header_bg = resolve_color(palette, "bg_header", is_dark)

    # 1. Detect hardware
    hw_info: HardwareInfo = detect_hardware()
    rec_model_id = recommend_model(hw_info)
    rec_model = AVAILABLE_MODELS.get(rec_model_id, AVAILABLE_MODELS["whisper-base"])

    # Active downloads tracking: model_id -> cancel_event
    active_downloads: dict[str, threading.Event] = {}

    # Capture the active UI event loop for cross-thread listener dispatching
    try:
        main_loop = asyncio.get_running_loop()
    except RuntimeError:
        main_loop = None

    # Storage info label
    storage_label = ft.Text("", size=12, color=text_secondary, weight=ft.FontWeight.W_500)

    def refresh_storage_display():
        used_mb, free_gb, drive = get_storage_usage()
        storage_label.value = t(
            "model_hub.storage_status",
            used_mb=used_mb,
            drive=drive,
            free_gb=free_gb,
        )

    refresh_storage_display()

    # Container for model cards grid
    cards_row = ft.Row(
        controls=[],
        spacing=12,
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.START,
        wrap=True if is_embedded else False,
    )

    # Dictionary to track active card controls for live updates
    card_refs: dict[str, dict] = {}

    def build_model_card(meta: ModelMetadata) -> ft.Container:
        installed = is_model_installed(meta.model_id)
        is_rec = meta.model_id == rec_model_id
        is_downloading = is_model_downloading(meta.model_id)

        # Badges list: If installed, display INSTALLED; if not installed but recommended, display RECOMMENDED
        badges = []
        if installed:
            badges.append(
                ft.Container(
                    content=ft.Text(t("model_hub.badge_installed"), size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.GREEN_600,
                    padding=ft.Padding(left=6, top=2, right=6, bottom=2),
                    border_radius=6,
                )
            )
        elif is_rec:
            badges.append(
                ft.Container(
                    content=ft.Text(t("model_hub.badge_recommended"), size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    bgcolor=accent_primary,
                    padding=ft.Padding(left=6, top=2, right=6, bottom=2),
                    border_radius=6,
                )
            )

        # Retrieve active progress state even if view was closed and reopened
        prog = get_model_download_progress(meta.model_id) if is_downloading else None
        init_pct = prog["pct"] if prog else 0.0
        init_msg = prog["msg"] if prog else (t("model_hub.badge_downloading") if is_downloading else "")

        card_pbar = ft.ProgressBar(value=init_pct, visible=is_downloading, color=accent_primary, height=4)
        card_status = ft.Text(
            init_msg,
            size=11,
            color=accent_primary,
            visible=is_downloading,
        )
        card_refs[meta.model_id] = {"pbar": card_pbar, "status": card_status}

        def live_listener(pct: float, msg: str):
            async def _u():
                card_pbar.value = pct
                card_pbar.visible = True
                card_status.value = msg
                card_status.visible = True
                if page:
                    try:
                        page.update()
                    except Exception:
                        pass

            if main_loop and not main_loop.is_closed():
                try:
                    asyncio.run_coroutine_threadsafe(_u(), main_loop)
                except Exception:
                    pass
            elif page:
                try:
                    card_pbar.value = pct
                    card_pbar.visible = True
                    card_status.value = msg
                    card_status.visible = True
                    page.update()
                except Exception:
                    pass

        if is_downloading:
            add_download_listener(meta.model_id, live_listener)

        async def download_clicked(e):
            if is_model_downloading(meta.model_id):
                return

            cancel_evt = register_model_download(meta.model_id)
            render_cards()
            last_msg = [""]

            def direct_cb(pct: float, msg: str):
                last_msg[0] = msg

            success = await asyncio.to_thread(
                download_model,
                meta.model_id,
                direct_cb,
                cancel_evt,
            )

            remove_download_listener(meta.model_id, live_listener)
            refresh_storage_display()
            render_cards()
            if on_models_changed:
                on_models_changed()

            if page:
                if success:
                    show_message_dialog(
                        page=page,
                        payload=t("model_hub.download_success", name=meta.display_name),
                        title=t("model_hub.dialog_success_title"),
                        dialog_type=DialogType.SUCCESS,
                    )
                elif not cancel_evt.is_set():
                    # Only show error dialog on actual network/disk failure, not user cancellation
                    err_detail = last_msg[0] or t("model_hub.error_generic", error="Network timeout")
                    doc_err = DocumentError(
                        code=ErrorCode.MODEL_DOWNLOAD_FAILED,
                        title=t("model_hub.dialog_err_title"),
                        message=err_detail,
                        suggestion=t("model_hub.error_suggestion"),
                    )
                    show_message_dialog(
                        page=page,
                        payload=doc_err,
                        dialog_type=DialogType.ERROR,
                    )

        def cancel_clicked(e):
            cancel_model_download(meta.model_id)
            refresh_storage_display()
            render_cards()

        def delete_clicked(e):
            if not page:
                delete_model(meta.model_id)
                refresh_storage_display()
                render_cards()
                if on_models_changed:
                    on_models_changed()
                return

            def close_confirm_dlg():
                if confirm_dlg.open:
                    confirm_dlg.open = False
                    try:
                        page.update()
                    except Exception:
                        pass

            def confirm_action(ev):
                close_confirm_dlg()
                delete_model(meta.model_id)
                refresh_storage_display()
                render_cards()
                if on_models_changed:
                    on_models_changed()

            def cancel_action(ev=None):
                close_confirm_dlg()

            confirm_dlg = ft.AlertDialog(
                modal=False,
                on_dismiss=cancel_action,
                title=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.WARNING_ROUNDED, color=ft.Colors.RED_400, size=24),
                        ft.Text(t("model_hub.confirm_delete_title"), weight=ft.FontWeight.BOLD, size=16),
                    ],
                    spacing=8,
                ),
                content=ft.Text(t("model_hub.confirm_delete_msg", name=meta.display_name, size=meta.size_mb), size=13),
                actions=[
                    ft.TextButton(t("first_time_dialog.btn_cancel"), on_click=cancel_action),
                    ft.Button(
                        t("model_hub.btn_delete"),
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE),
                        on_click=confirm_action,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.overlay.append(confirm_dlg)
            confirm_dlg.open = True
            page.update()

        # Action button logic
        if is_downloading:
            action_btn = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.ProgressRing(width=16, height=16, stroke_width=2, color=accent_primary),
                        ft.Text(t("model_hub.badge_downloading"), size=12, color=accent_primary, weight=ft.FontWeight.W_500, expand=True),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE_ROUNDED,
                            tooltip=t("first_time_dialog.btn_cancel_download"),
                            icon_color=ft.Colors.RED_400,
                            icon_size=18,
                            on_click=cancel_clicked,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(left=4, top=0, right=4, bottom=0),
            )
        elif installed:
            action_btn = ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.GREEN_400, size=16),
                                ft.Text(t("model_hub.badge_installed"), size=12, color=ft.Colors.GREEN_400, weight=ft.FontWeight.W_600),
                            ],
                            spacing=4,
                        ),
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        tooltip=t("model_hub.btn_delete"),
                        icon_color=ft.Colors.RED_400,
                        icon_size=18,
                        on_click=delete_clicked,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        else:
            action_btn = ft.Row(
                controls=[
                    ft.Button(
                        t("model_hub.btn_download", size=meta.size_mb),
                        icon=ft.Icons.DOWNLOAD_ROUNDED,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=6),
                            bgcolor=accent_primary if is_rec else header_bg,
                            color=ft.Colors.WHITE if is_rec else accent_primary,
                            padding=ft.Padding(left=14, top=8, right=14, bottom=8),
                        ),
                        on_click=download_clicked,
                        expand=True,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            )

        locale_str = getattr(page, "locale_str", "vi") if page else "vi"

        card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(meta.display_name, size=14, weight=ft.FontWeight.BOLD, color=text_primary),
                            ft.Row(controls=badges, spacing=4),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        height=24,
                    ),
                    ft.Divider(height=1, color=border_color),
                    ft.Text(
                        t(f"model_hub.desc_{meta.model_id.replace('-', '_')}"),
                        size=11,
                        color=text_secondary,
                        height=36,
                    ),
                    ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.FOLDER_ZIP_ROUNDED, size=14, color=text_secondary),
                                    ft.Text(f"{meta.size_mb} MB", size=11, color=text_primary, weight=ft.FontWeight.W_500),
                                ],
                                spacing=6,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.SPEED_ROUNDED, size=14, color=text_secondary),
                                    ft.Row(
                                        controls=[
                                            ft.Icon(
                                                ft.Icons.BOLT_ROUNDED,
                                                size=13,
                                                color=ft.Colors.AMBER_400 if i < meta.speed_rating else ft.Colors.with_opacity(0.25, text_secondary),
                                            )
                                            for i in range(5)
                                        ],
                                        spacing=1,
                                    ),
                                ],
                                spacing=6,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.VERIFIED_ROUNDED, size=14, color=text_secondary),
                                    ft.Row(
                                        controls=[
                                            ft.Icon(
                                                ft.Icons.STAR_ROUNDED,
                                                size=13,
                                                color=ft.Colors.AMBER_400 if i < meta.accuracy_rating else ft.Colors.with_opacity(0.25, text_secondary),
                                            )
                                            for i in range(5)
                                        ],
                                        spacing=1,
                                    ),
                                ],
                                spacing=6,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.MEMORY_ROUNDED, size=14, color=text_secondary),
                                    ft.Text(t("model_hub.label_ram", ram=meta.recommended_ram_gb), size=11, color=text_secondary),
                                ],
                                spacing=6,
                            ),
                        ],
                        spacing=4,
                    ),
                    card_pbar,
                    card_status,
                    ft.Container(expand=True),
                    action_btn,
                ],
                spacing=6,
            ),
            bgcolor=card_bg,
            border=make_border(1.5 if is_rec else 1, accent_primary if is_rec else border_color),
            border_radius=8,
            padding=12,
            height=275,
            expand=1 if not is_embedded else None,
            width=255 if is_embedded else None,
        )
        return card

    def render_cards():
        cards_row.controls = [build_model_card(m) for m in AVAILABLE_MODELS.values()]
        try:
            if page:
                page.update()
        except Exception:
            pass

    render_cards()

    # Hardware Banner
    hw_banner = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.COMPUTER_ROUNDED, color=accent_primary, size=18),
                        ft.Text(
                            t("model_hub.hw_header", summary=hw_info.get_summary_text()),
                            size=12,
                            weight=ft.FontWeight.W_600,
                            color=text_primary,
                            expand=True,
                        ),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.LIGHTBULB_ROUNDED, color=ft.Colors.AMBER_400, size=16),
                        ft.Text(
                            t("model_hub.recommendation", model_name=rec_model.display_name),
                            size=12,
                            color=text_secondary,
                            expand=True,
                        ),
                    ],
                    spacing=6,
                ),
            ],
            spacing=4,
        ),
        padding=10,
        bgcolor=header_bg,
        border_radius=8,
        border=make_border(1, border_color),
    )

    def on_clean_all_clicked(e):
        if not page:
            clean_all_models()
            refresh_storage_display()
            render_cards()
            if on_models_changed:
                on_models_changed()
            return

        def close_clean_dlg():
            if clean_dlg.open:
                clean_dlg.open = False
                try:
                    page.update()
                except Exception:
                    pass

        def confirm_clean(ev):
            close_clean_dlg()
            clean_all_models()
            refresh_storage_display()
            render_cards()
            if on_models_changed:
                on_models_changed()

        def cancel_clean(ev=None):
            close_clean_dlg()

        clean_dlg = ft.AlertDialog(
            modal=False,
            on_dismiss=cancel_clean,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.WARNING_ROUNDED, color=ft.Colors.RED_400, size=24),
                    ft.Text(t("model_hub.confirm_clean_title"), weight=ft.FontWeight.BOLD, size=16),
                ],
                spacing=8,
            ),
            content=ft.Text(t("model_hub.confirm_clean_msg"), size=13),
            actions=[
                ft.TextButton(t("first_time_dialog.btn_cancel"), on_click=cancel_clean),
                ft.Button(
                    t("model_hub.btn_clean_all"),
                    icon=ft.Icons.DELETE_SWEEP_ROUNDED,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE),
                    on_click=confirm_clean,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(clean_dlg)
        clean_dlg.open = True
        page.update()

    btn_clean_all = ft.TextButton(
        t("model_hub.btn_clean_all"),
        icon=ft.Icons.CLEANING_SERVICES_ROUNDED,
        style=ft.ButtonStyle(color=ft.Colors.RED_400),
        on_click=on_clean_all_clicked,
    )

    def open_folder_clicked(e):
        try:
            folder = get_models_dir()
            os.makedirs(folder, exist_ok=True)
            open_file_or_folder_foreground(folder, is_folder=True)
        except Exception as ex:
            print(f"[DEBUG] Open models folder failed: {ex}")

    btn_open_folder = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN_ROUNDED,
        tooltip=t("model_hub.tooltip_open_folder"),
        icon_color=text_secondary,
        icon_size=17,
        on_click=open_folder_clicked,
    )

    footer_row = ft.Row(
        controls=[
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.STORAGE_ROUNDED, size=15, color=text_secondary),
                    storage_label,
                    btn_open_folder,
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(expand=True),
            btn_clean_all,
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    if not is_embedded and on_close_dialog:
        btn_close = ft.Button(
            t("model_hub.btn_close"),
            on_click=lambda _: on_close_dialog(),
        )
        footer_row.controls.append(btn_close)

    root_container = ft.Container(
        content=ft.Column(
            controls=[
                hw_banner,
                ft.Container(height=2),
                cards_row,
                ft.Divider(height=1, color=border_color),
                footer_row,
            ],
            spacing=6,
            tight=True,
        ),
        width=830 if not is_embedded else None,
    )
    return root_container


def show_model_hub_dialog(
    page: ft.Page,
    current_palette: str = "Violet Cyberpunk",
    on_models_changed: Optional[Callable[[], None]] = None,
):
    """
    Displays the standalone AI Model Hub & Marketplace Modal Dialog.
    """
    # Clean up stale dialogs
    page.overlay[:] = [c for c in page.overlay if not isinstance(c, ft.AlertDialog)]

    is_dark = page.theme_mode != ft.ThemeMode.LIGHT
    palette = PALETTES.get(current_palette, PALETTES["Violet Cyberpunk"])
    text_primary = get_style_color("text_primary", is_dark)
    accent_primary = resolve_color(palette, "text_accent_primary", is_dark)

    def close_dialog(e=None):
        if dialog.open:
            dialog.open = False
            try:
                page.update()
            except Exception:
                pass

    dialog = ft.AlertDialog(
        modal=False,
        on_dismiss=close_dialog,
        content_padding=ft.Padding(18, 10, 18, 12),
        inset_padding=ft.Padding(16, 16, 16, 16),
    )

    content_view = build_model_hub_view(
        page=page,
        current_palette=current_palette,
        is_dark=is_dark,
        on_models_changed=on_models_changed,
        is_embedded=False,
        on_close_dialog=close_dialog,
    )

    dialog.title = ft.Row(
        controls=[
            ft.Icon(ft.Icons.AUTO_AWESOME_MOSAIC_ROUNDED, color=accent_primary, size=24),
            ft.Text(t("model_hub.title"), size=16, weight=ft.FontWeight.BOLD, color=text_primary),
        ],
        spacing=8,
    )
    dialog.content = content_view
    dialog.shape = ft.RoundedRectangleBorder(radius=10)

    page.overlay.append(dialog)
    dialog.open = True
    page.update()
