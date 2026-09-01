"""
First-Time Model Consent & Quick Download Dialog for Flet UI.
Prompts users when no Whisper model is installed, explains offline benefits,
highlights the hardware-recommended model, and offers 1-click download or Hub navigation.
"""
import asyncio
import threading
from typing import Callable, Optional
import flet as ft

from src.i18n import t
from src.services.hardware_detector import detect_hardware, recommend_model, HardwareInfo
from src.services.model_manager import (
    AVAILABLE_MODELS,
    download_model,
    is_model_installed,
)
from src.ui_flet.theme import PALETTES, resolve_color, get_style_color, make_border


def show_first_time_model_dialog(
    page: ft.Page,
    on_model_ready: Optional[Callable[[str], None]] = None,
    on_open_model_hub: Optional[Callable[[], None]] = None,
    current_palette: str = "Violet Cyberpunk",
):
    """
    Displays the First-Time Setup Dialog proposing the recommended model for 1-click download.
    """
    # Clean up stale dialogs from overlay
    page.overlay[:] = [c for c in page.overlay if not isinstance(c, ft.AlertDialog)]

    is_dark = page.theme_mode != ft.ThemeMode.LIGHT
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

    # State tracking
    is_downloading = False
    cancel_event: Optional[threading.Event] = None

    # UI Controls
    progress_bar = ft.ProgressBar(width=440, value=0, visible=False, color=accent_primary)
    status_text = ft.Text("", size=12, color=accent_primary, visible=False, expand=True)

    stars = "⭐" * rec_model.accuracy_rating
    speed_icons = "🚀" * rec_model.speed_rating

    # Recommended Model Card Container
    card_content = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=accent_primary, size=20),
                        ft.Text(rec_model.display_name, size=15, weight=ft.FontWeight.BOLD, color=text_primary),
                        ft.Container(
                            content=ft.Text(t("model_hub.badge_recommended"), size=10, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                            bgcolor=accent_primary,
                            padding=ft.Padding(left=8, top=2, right=8, bottom=2),
                            border_radius=10,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=8,
                ),
                ft.Text(
                    t(f"model_hub.desc_{rec_model.model_id.replace('-', '_')}"),
                    size=12,
                    color=text_secondary,
                ),
                ft.Row(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.FOLDER_ZIP_ROUNDED, size=14, color=text_secondary),
                                ft.Text(f"{rec_model.size_mb} MB", size=11, color=text_primary, weight=ft.FontWeight.W_500),
                            ],
                            spacing=4,
                        ),
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.SPEED_ROUNDED, size=14, color=text_secondary),
                                ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.BOLT_ROUNDED,
                                            size=13,
                                            color=ft.Colors.AMBER_400 if i < rec_model.speed_rating else ft.Colors.with_opacity(0.25, text_secondary),
                                        )
                                        for i in range(5)
                                    ],
                                    spacing=1,
                                ),
                            ],
                            spacing=4,
                        ),
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.VERIFIED_ROUNDED, size=14, color=text_secondary),
                                ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.STAR_ROUNDED,
                                            size=13,
                                            color=ft.Colors.AMBER_400 if i < rec_model.accuracy_rating else ft.Colors.with_opacity(0.25, text_secondary),
                                        )
                                        for i in range(5)
                                    ],
                                    spacing=1,
                                ),
                            ],
                            spacing=4,
                        ),
                    ],
                    spacing=14,
                ),
            ],
            spacing=6,
        ),
        padding=12,
        bgcolor=card_bg,
        border=make_border(1, accent_primary),
        border_radius=8,
    )

    btn_download = ft.Button(
        t("first_time_dialog.btn_quick_download", size=rec_model.size_mb),
        icon=ft.Icons.DOWNLOAD_ROUNDED,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=6),
            bgcolor=accent_primary,
            color=ft.Colors.WHITE,
        ),
    )

    btn_cancel = ft.TextButton(
        t("first_time_dialog.btn_cancel"),
    )

    link_hub = ft.TextButton(
        t("first_time_dialog.link_view_all"),
        style=ft.ButtonStyle(color=accent_primary),
    )

    def close_dialog(e=None):
        nonlocal is_downloading
        if is_downloading and cancel_event:
            cancel_event.set()
        if dialog.open:
            dialog.open = False
            try:
                page.update()
            except Exception:
                pass

    def on_link_hub_clicked(e):
        close_dialog()
        if on_open_model_hub:
            on_open_model_hub()

    async def on_download_clicked(e):
        nonlocal is_downloading, cancel_event
        if is_downloading:
            return

        is_downloading = True
        cancel_event = threading.Event()
        progress_bar.visible = True
        status_text.visible = True
        btn_download.disabled = True
        btn_cancel.content = t("first_time_dialog.btn_cancel_download")
        page.update()

        def update_progress(pct: float, msg: str):
            async def _ui():
                progress_bar.value = pct
                status_text.value = msg
                page.update()
            asyncio.run_coroutine_threadsafe(_ui(), loop)

        loop = asyncio.get_running_loop()

        success = await asyncio.to_thread(
            download_model,
            rec_model_id,
            update_progress,
            cancel_event,
        )

        is_downloading = False
        if success:
            status_text.value = t("model_hub.download_success", name=rec_model.display_name)
            status_text.color = ft.Colors.GREEN_400
            page.update()
            await asyncio.sleep(0.8)
            close_dialog()
            if on_model_ready:
                on_model_ready(rec_model_id)
        else:
            status_text.value = t("model_hub.download_failed", name=rec_model.display_name, error=t("first_time_dialog.error_cancelled"))
            status_text.color = ft.Colors.RED_400
            btn_download.disabled = False
            btn_cancel.content = t("first_time_dialog.btn_cancel")
            page.update()

    btn_download.on_click = on_download_clicked
    btn_cancel.on_click = close_dialog
    link_hub.on_click = on_link_hub_clicked

    dialog = ft.AlertDialog(
        modal=False,
        on_dismiss=close_dialog,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.MIC_ROUNDED, color=accent_primary, size=24),
                ft.Text(t("first_time_dialog.title"), size=16, weight=ft.FontWeight.BOLD, color=text_primary),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=520,
            content=ft.Column(
                controls=[
                    ft.Text(
                        t("first_time_dialog.subtitle"),
                        size=12,
                        color=text_secondary,
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.MEMORY_ROUNDED, size=16, color=accent_primary),
                                ft.Text(t("first_time_dialog.hw_detected", summary=hw_info.get_summary_text()), size=11, color=text_secondary, expand=True),
                            ],
                            spacing=6,
                        ),
                        bgcolor=card_bg,
                        padding=ft.Padding(left=10, top=6, right=10, bottom=6),
                        border_radius=6,
                    ),
                    ft.Text(
                        t("first_time_dialog.recommend_reason"),
                        size=12,
                        weight=ft.FontWeight.W_500,
                        color=text_primary,
                    ),
                    card_content,
                    progress_bar,
                    ft.Row(
                        controls=[status_text],
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    ft.Row(
                        controls=[link_hub],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ],
                spacing=10,
                tight=True,
            ),
        ),
        actions=[
            btn_cancel,
            btn_download,
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=10),
    )

    page.overlay.append(dialog)
    dialog.open = True
    page.update()
