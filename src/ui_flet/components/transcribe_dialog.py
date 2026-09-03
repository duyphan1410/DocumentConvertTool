"""
Transcribe Dialog for local Audio and Video files.
Provides UI for selecting local media files, choosing installed Whisper AI models,
setting language and timestamps, and tracking real-time transcription progress.
Integrates with TranscriptionJobManager for non-blocking background execution, cancellation, and progress streaming.
"""
import asyncio
import os
from typing import Callable, Optional

import flet as ft

from src.i18n import t
from src.services.model_manager import AVAILABLE_MODELS, is_model_installed
from src.services.whisper_service import get_best_installed_model, transcribe_file
from src.services.transcription_manager import TranscriptionJobManager, TranscriptionJob, JobStatus
from src.ui_flet.theme import PALETTES, resolve_color, get_style_color


def show_transcribe_dialog(
    page: ft.Page,
    current_palette: str,
    on_success: Callable[[str, str], None],
    default_file_path: Optional[str] = None,
):
    """
    Displays the Local Media Transcribe Dialog.
    Non-blocking: runs in background, can be dismissed, resumed, or cancelled.
    """
    page.overlay[:] = [c for c in page.overlay if not isinstance(c, ft.AlertDialog)]

    is_dark = page.theme_mode != ft.ThemeMode.LIGHT
    palette = PALETTES.get(current_palette, {})

    text_primary = get_style_color("text_primary", is_dark)
    text_secondary = get_style_color("text_secondary", is_dark)
    accent_primary = resolve_color(palette, "text_accent_primary", is_dark)

    manager = TranscriptionJobManager.get_instance()
    try:
        manager.set_event_loop(asyncio.get_running_loop())
    except Exception:
        pass

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

    btn_cancel_job = ft.TextButton(
        "Cancel Task",
        icon=ft.Icons.CANCEL_ROUNDED,
        style=ft.ButtonStyle(color=ft.Colors.RED_400),
        visible=False,
    )

    tracked_job: Optional[TranscriptionJob] = None

    def _ui_job_listener(job: TranscriptionJob):
        if not dialog.open:
            return
        if job.status == JobStatus.RUNNING:
            prg_bar.visible = True
            prg_bar.value = job.progress if job.progress > 0 else None
            lbl_status.value = job.stage_message or "Processing..."
            lbl_status.color = accent_primary
            lbl_status.visible = True
            btn_start.disabled = True
            btn_cancel_job.visible = True
        elif job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            prg_bar.visible = False
            btn_cancel_job.visible = False
            btn_start.disabled = not bool(installed_models)
            txt_file.disabled = False
            if job.status == JobStatus.FAILED:
                lbl_status.value = job.error_message or "Failed"
                lbl_status.color = ft.Colors.RED_400
                lbl_status.visible = True
            elif job.status == JobStatus.CANCELLED:
                lbl_status.value = "Task cancelled"
                lbl_status.color = text_secondary
                lbl_status.visible = True
            elif job.status == JobStatus.COMPLETED:
                _close_dialog()
                return

        try:
            page.update()
        except Exception:
            pass

    def _close_dialog(e=None):
        if tracked_job:
            tracked_job.unsubscribe(_ui_job_listener)
        dialog.open = False
        try:
            page.update()
        except Exception:
            pass

    btn_cancel.on_click = _close_dialog

    def on_cancel_job_click(e):
        if tracked_job:
            manager.cancel_job(tracked_job.job_id)
            btn_cancel_job.visible = False
            lbl_status.value = "Cancelled"
            lbl_status.color = text_secondary
            prg_bar.visible = False
            btn_start.disabled = not bool(installed_models)
            txt_file.disabled = False
            page.update()

    btn_cancel_job.on_click = on_cancel_job_click

    def _open_model_hub(e=None):
        _close_dialog()
        try:
            from src.ui_flet.components.model_hub_dialog import show_model_hub_dialog
            show_model_hub_dialog(page=page, current_palette=current_palette)
        except Exception as ex:
            print(f"[DEBUG] Cannot open model hub: {ex}")

    btn_open_hub.on_click = _open_model_hub

    # Attach to existing running local media job if present
    active_local_job = manager.get_active_job(job_types=["local_media", "local_audio", "local_video"])
    if active_local_job:
        tracked_job = active_local_job
        tracked_job.subscribe(_ui_job_listener)
        txt_file.value = active_local_job.source
        txt_file.disabled = True
        btn_start.disabled = True
        btn_cancel_job.visible = True
        prg_bar.visible = True
        prg_bar.value = active_local_job.progress if active_local_job.progress > 0 else None
        lbl_status.value = active_local_job.stage_message or "Processing..."
        lbl_status.visible = True

    def _execute_local_transcribe_task(job: TranscriptionJob, progress_cb: Callable[[str, float], None]):
        file_path = job.source
        selected_model = dd_model.value
        selected_lang = dd_language.value if dd_language.value != "auto" else None
        include_ts = chk_timestamps.value

        def _status_callback(stage: str, *args):
            if job.cancel_event.is_set():
                return
            if stage == "preprocessing":
                progress_cb(t("speech.preprocessing"), 0.25)
            elif stage == "transcribing":
                progress_cb(t("speech.transcribing_with_model", model_name=selected_model or "Whisper"), 0.6)
            elif stage == "segment_progress" and len(args) >= 2:
                cur, tot = args[0], args[1]
                pct = cur / tot if tot > 0 else 0.0
                progress_cb(f"Transcribing {int(pct*100)}%", min(0.3 + pct * 0.65, 0.95))

        return transcribe_file(
            file_path=file_path,
            model_id=selected_model,
            language=selected_lang,
            include_timestamps=include_ts,
            status_callback=_status_callback,
        )

    def _on_start_click(e):
        file_path = (txt_file.value or "").strip()
        if not file_path:
            txt_file.error_text = t("transcribe.error_no_file")
            page.update()
            return
        if not os.path.isfile(file_path):
            txt_file.error_text = t("transcribe.error_file_not_found")
            page.update()
            return

        txt_file.error_text = None
        prg_bar.visible = True
        lbl_status.visible = True
        lbl_status.value = t("transcribe.status_starting")
        lbl_status.color = accent_primary
        btn_start.disabled = True
        btn_cancel_job.visible = True
        page.update()

        def _on_job_success(content: str, source_path: str, title: str):
            if on_success:
                on_success(content, source_path)

        def _on_job_error(err_msg: str):
            lbl_status.value = err_msg or "Failed"
            lbl_status.color = ft.Colors.RED_400
            prg_bar.visible = False
            btn_start.disabled = False
            btn_cancel_job.visible = False
            try:
                page.update()
            except Exception:
                pass

        nonlocal tracked_job
        job = manager.submit_job(
            job_type="local_media",
            source=file_path,
            display_name=os.path.basename(file_path),
            execution_fn=_execute_local_transcribe_task,
            on_success=_on_job_success,
            on_error=_on_job_error,
        )
        tracked_job = job
        job.subscribe(_ui_job_listener)

    btn_start.on_click = _on_start_click

    dialog = ft.AlertDialog(
        modal=False,
        on_dismiss=_close_dialog,
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
        actions=[btn_cancel_job, btn_cancel, btn_start],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(dialog)
    dialog.open = True
    page.update()
