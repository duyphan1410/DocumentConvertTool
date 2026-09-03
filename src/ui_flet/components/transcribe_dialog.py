"""
Transcribe Dialog for local Audio and Video files.
Provides UI for selecting local media files, choosing installed Whisper AI models,
setting language and timestamps, and tracking real-time transcription progress.
"""
import asyncio
import os
from typing import Callable, Optional

import flet as ft

from src.i18n import t
from src.services.model_manager import AVAILABLE_MODELS, is_model_installed
from src.services.whisper_service import get_best_installed_model, transcribe_file
from src.ui_flet.theme import PALETTES, resolve_color, get_style_color


def show_transcribe_dialog(
    page: ft.Page,
    current_palette: str,
    on_success: Callable[[str, str], None],
    default_file_path: Optional[str] = None,
):
    """
    Displays the Local Media Transcribe Dialog.

    Args:
        page: Flet page instance.
        current_palette: Theme palette name.
        on_success: Callback(markdown_content, file_path) when transcription completes.
        default_file_path: Optional pre-filled media file path.
    """
    page.overlay[:] = [c for c in page.overlay if not isinstance(c, ft.AlertDialog)]

    is_dark = page.theme_mode != ft.ThemeMode.LIGHT
    palette = PALETTES.get(current_palette, {})

    text_primary = get_style_color("text_primary", is_dark)
    text_secondary = get_style_color("text_secondary", is_dark)
    accent_primary = resolve_color(palette, "text_accent_primary", is_dark)

    # 1. File Input Field & File Picker
    txt_file = ft.TextField(
        value=default_file_path or "",
        label=t("transcribe.label_file"),
        hint_text=t("transcribe.hint_file"),
        border_radius=6,
        expand=True,
        text_size=13,
    )

    async def _on_browse_click(e):
        from src.ui_flet.native_dialogs import pick_media_file_async

        picked_path = await pick_media_file_async()
        if picked_path:
            txt_file.value = picked_path
            txt_file.error_text = None
            page.update()

    btn_browse = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN_ROUNDED,
        tooltip=t("transcribe.tooltip_browse"),
        on_click=_on_browse_click,
    )

    # 2. Installed Models Detection
    installed_models = [mid for mid in ["whisper-small", "whisper-base", "whisper-tiny"] if is_model_installed(mid)]
    best_model = get_best_installed_model()

    model_options = []
    for mid in installed_models:
        meta = AVAILABLE_MODELS.get(mid)
        label = f"{meta.display_name} (~{meta.size_mb} MB)" if meta else mid
        model_options.append(ft.dropdown.Option(key=mid, text=label))

    dd_model = ft.Dropdown(
        label=t("transcribe.label_model"),
        options=model_options,
        value=best_model if best_model in installed_models else (installed_models[0] if installed_models else None),
        border_radius=6,
        text_size=13,
        expand=True,
        visible=bool(installed_models),
    )

    no_model_banner = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.AMBER_400, size=18),
                ft.Text(
                    t("transcribe.no_model_installed"),
                    size=12,
                    color=ft.Colors.AMBER_300,
                    expand=True,
                ),
            ],
            spacing=8,
        ),
        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.AMBER_900),
        border_radius=6,
        padding=ft.Padding(left=10, top=6, right=10, bottom=6),
        visible=not bool(installed_models),
    )

    btn_open_hub = ft.TextButton(
        t("speech.btn_open_model_hub"),
        icon=ft.Icons.AUTO_AWESOME_MOSAIC_ROUNDED,
        visible=not bool(installed_models),
    )

    # 3. Language & Timestamp Options
    dd_language = ft.Dropdown(
        label=t("transcribe.label_language"),
        options=[
            ft.dropdown.Option(key="auto", text=t("transcribe.lang_auto")),
            ft.dropdown.Option(key="vi", text=t("transcribe.lang_vi")),
            ft.dropdown.Option(key="en", text=t("transcribe.lang_en")),
        ],
        value="auto",
        border_radius=6,
        text_size=13,
        expand=True,
    )

    chk_timestamps = ft.Checkbox(
        label=t("transcribe.chk_timestamps"),
        value=True,
    )

    # 4. Progress & Status Display
    prg_bar = ft.ProgressBar(
        value=None,
        visible=False,
        color=accent_primary,
        bgcolor=ft.Colors.with_opacity(0.2, accent_primary),
    )
    lbl_status = ft.Text(
        value="",
        size=12,
        color=accent_primary,
        visible=False,
    )

    # 5. Dialog Actions
    btn_start = ft.ElevatedButton(
        t("transcribe.btn_start"),
        icon=ft.Icons.AUTO_AWESOME_ROUNDED,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=6),
            bgcolor=accent_primary,
            color=ft.Colors.WHITE,
        ),
        disabled=not bool(installed_models),
    )

    btn_cancel = ft.TextButton(
        t("transcribe.btn_cancel"),
    )

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.MIC_ROUNDED, color=accent_primary, size=22),
                ft.Text(t("transcribe.dialog_title"), weight=ft.FontWeight.BOLD, size=16),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=520,
            content=ft.Column(
                controls=[
                    ft.Row(controls=[txt_file, btn_browse], spacing=6),
                    no_model_banner,
                    btn_open_hub,
                    ft.Row(controls=[dd_model, dd_language], spacing=10),
                    chk_timestamps,
                    prg_bar,
                    lbl_status,
                ],
                tight=True,
                spacing=12,
            ),
        ),
        actions=[btn_cancel, btn_start],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def _close_dialog(e=None):
        dialog.open = False
        try:
            page.update()
        except Exception:
            pass

    btn_cancel.on_click = _close_dialog

    def _open_model_hub(e=None):
        _close_dialog()
        try:
            from src.ui_flet.components.first_time_model_dialog import show_first_time_model_dialog
            show_first_time_model_dialog(page=page, current_palette=current_palette)
        except Exception as ex:
            print(f"[DEBUG] Cannot open model hub: {ex}")

    btn_open_hub.on_click = _open_model_hub

    # 6. Execution Flow
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    def _update_status(stage: str):
        def _apply():
            if stage == "preprocessing":
                lbl_status.value = t("speech.preprocessing")
                prg_bar.value = None
            elif stage == "transcribing":
                lbl_status.value = t("transcribe.status_transcribing")
            lbl_status.visible = True
            prg_bar.visible = True
            try:
                page.update()
            except Exception:
                pass

        if loop and loop.is_running():
            loop.call_soon_threadsafe(_apply)
        else:
            _apply()

    def _update_progress(curr: float, total: float):
        def _apply():
            if total > 0:
                pct = min(1.0, max(0.0, curr / total))
                prg_bar.value = pct
                lbl_status.value = f"{t('transcribe.status_transcribing')} ({int(pct * 100)}%)"
                try:
                    page.update()
                except Exception:
                    pass

        if loop and loop.is_running():
            loop.call_soon_threadsafe(_apply)
        else:
            _apply()

    async def _on_start_click(e=None):
        file_path = (txt_file.value or "").strip()
        if not file_path or not os.path.exists(file_path):
            txt_file.error_text = t("transcribe.err_file_not_found")
            page.update()
            return

        model_id = dd_model.value or get_best_installed_model()
        if not model_id:
            no_model_banner.visible = True
            btn_open_hub.visible = True
            page.update()
            return

        btn_start.disabled = True
        btn_cancel.disabled = True
        txt_file.disabled = True
        btn_browse.disabled = True
        dd_model.disabled = True
        dd_language.disabled = True
        chk_timestamps.disabled = True
        prg_bar.visible = True
        lbl_status.visible = True
        lbl_status.value = t("transcribe.status_starting")
        lbl_status.color = accent_primary
        page.update()

        lang_val = dd_language.value
        lang_param = None if lang_val == "auto" else lang_val

        try:
            success, content, err = await asyncio.to_thread(
                transcribe_file,
                file_path=file_path,
                model_id=model_id,
                language=lang_param,
                include_timestamps=chk_timestamps.value,
                on_progress=_update_progress,
                status_callback=_update_status,
            )

            if not success or not content:
                lbl_status.value = f"Lỗi: {err or t('transcribe.err_transcription_failed')}"
                lbl_status.color = ft.Colors.RED_400
                prg_bar.visible = False
                btn_start.disabled = False
                btn_cancel.disabled = False
                txt_file.disabled = False
                btn_browse.disabled = False
                dd_model.disabled = False
                dd_language.disabled = False
                chk_timestamps.disabled = False
                page.update()
                return

            # Success: close dialog and trigger workspace load
            dialog.open = False
            page.update()

            if on_success:
                on_success(content, file_path)

        except Exception as exc:
            lbl_status.value = f"Lỗi: {str(exc)}"
            lbl_status.color = ft.Colors.RED_400
            prg_bar.visible = False
            btn_start.disabled = False
            btn_cancel.disabled = False
            page.update()

    btn_start.on_click = lambda _: asyncio.create_task(_on_start_click())

    page.overlay.append(dialog)
    dialog.open = True
    page.update()
