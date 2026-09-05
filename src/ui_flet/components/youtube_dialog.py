"""
Video Transcript Import Dialog for Flet UI.
Supports both YouTube and Google Drive video URLs.
Extracts subtitles from YouTube or transcribes speech using local Whisper AI models.
Integrates with TranscriptionJobManager for non-blocking background execution, cancellation, and progress streaming.
"""
import asyncio
from typing import Callable, Optional
import flet as ft

from src.i18n import t
from src.services.youtube_service import extract_video_id, fetch_youtube_transcript
from src.services.drive_service import is_drive_url, extract_drive_file_id
from src.services.transcription_manager import TranscriptionJobManager, TranscriptionJob, JobStatus
from src.ui_flet.theme import PALETTES, resolve_color, get_style_color


def show_youtube_dialog(
    page: ft.Page,
    on_transcript_loaded: Optional[Callable[[str, str], None]] = None,
    on_success: Optional[Callable[[str, str], None]] = None,
    current_palette: str = "Violet Cyberpunk",
):
    """
    Displays modal dialog to import video subtitles/transcript as Markdown.
    Accepts YouTube URLs and Google Drive video URLs.
    Non-blocking: runs in background and allows resume / cancel.
    """
    callback_success = on_success or on_transcript_loaded
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

    url_input = ft.TextField(
        label=t("youtube.url_label"),
        hint_text=t("youtube.url_hint"),
        prefix_icon=ft.Icons.LINK_ROUNDED,
        autofocus=True,
        expand=True,
        text_size=13,
        dense=True,
    )

    chk_timestamps = ft.Checkbox(
        label=t("youtube.chk_timestamps"),
        value=True,
    )

    chk_auto_translate = ft.Checkbox(
        label=t("youtube.chk_auto_translate"),
        value=True,
    )

    chk_speech_fallback = ft.Checkbox(
        label=t("youtube.chk_speech_fallback"),
        value=True,
    )

    lang_dropdown = ft.Dropdown(
        label=t("youtube.lang_label"),
        value="auto",
        options=[
            ft.dropdown.Option("auto", t("youtube.lang_auto")),
            ft.dropdown.Option("vi", t("youtube.lang_vi")),
            ft.dropdown.Option("en", t("youtube.lang_en")),
        ],
        dense=True,
        width=220,
    )

    progress_ring = ft.ProgressRing(width=16, height=16, stroke_width=2.5, visible=False)
    progress_bar = ft.ProgressBar(
        value=None,
        visible=False,
        color=accent_primary,
        bgcolor=ft.Colors.with_opacity(0.15, accent_primary),
    )
    status_text = ft.Text("", size=12, color=accent_primary, visible=False, expand=True)

    # Info banner when queued behind another job
    queue_banner = ft.Container(
        visible=False,
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.HOURGLASS_TOP_ROUNDED, color=ft.Colors.BLUE_400, size=18),
                ft.Text("", size=12, color=ft.Colors.BLUE_300, expand=True),
            ],
            spacing=8,
        ),
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.BLUE_400),
        border_radius=6,
        padding=ft.Padding(left=10, top=7, right=10, bottom=7),
    )

    # Banner shown when no Whisper model is installed
    no_model_banner = ft.Container(
        visible=False,
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.AMBER_400, size=18),
                ft.Text(
                    t("speech.no_model_installed"),
                    size=12,
                    color=ft.Colors.AMBER_300,
                    expand=True,
                ),
            ],
            spacing=8,
        ),
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_400),
        border_radius=6,
        padding=ft.Padding(left=10, top=7, right=10, bottom=7),
    )

    btn_open_hub = ft.TextButton(
        t("speech.btn_open_model_hub"),
        icon=ft.Icons.DOWNLOAD_ROUNDED,
        style=ft.ButtonStyle(color=accent_primary),
        visible=False,
    )

    btn_fetch = ft.ElevatedButton(
        t("youtube.btn_fetch"),
        icon=ft.Icons.DOWNLOAD_ROUNDED,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=6),
            bgcolor=accent_primary,
            color=ft.Colors.WHITE,
        ),
    )

    btn_cancel = ft.TextButton(
        t("youtube.btn_cancel"),
    )

    btn_cancel_job = ft.TextButton(
        "Cancel Task",
        icon=ft.Icons.CANCEL_ROUNDED,
        style=ft.ButtonStyle(color=ft.Colors.RED_400),
        visible=False,
    )

    status_row = ft.Row(
        controls=[progress_ring, status_text],
        alignment=ft.MainAxisAlignment.START,
        spacing=8,
    )

    tracked_job: Optional[TranscriptionJob] = None

    def _ui_job_listener(job: TranscriptionJob):
        if not dialog.open:
            return
        if job.status == JobStatus.RUNNING:
            progress_bar.visible = True
            progress_ring.visible = True
            progress_bar.value = job.progress if job.progress > 0 else None
            status_text.value = job.stage_message or "Processing..."
            status_text.color = accent_primary
            status_text.visible = True
            btn_fetch.disabled = True
            btn_cancel_job.visible = True
        elif job.status == JobStatus.QUEUED:
            queue_banner.content.controls[1].value = f"Queued: Waiting for worker ({job.display_name})"
            queue_banner.visible = True
            btn_fetch.disabled = True
            btn_cancel_job.visible = True
        elif job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            progress_bar.visible = False
            progress_ring.visible = False
            btn_cancel_job.visible = False
            btn_fetch.disabled = False
            url_input.disabled = False
            if job.status == JobStatus.FAILED:
                status_text.value = job.error_message or "Failed"
                status_text.color = ft.Colors.RED_400
                status_text.visible = True
            elif job.status == JobStatus.CANCELLED:
                status_text.value = "Task cancelled"
                status_text.color = text_secondary
                status_text.visible = True
            elif job.status == JobStatus.COMPLETED:
                close_dialog()
                return

        try:
            page.update()
        except Exception:
            pass

    def close_dialog(e=None):
        if tracked_job:
            tracked_job.unsubscribe(_ui_job_listener)
        dialog.open = False
        try:
            page.update()
        except Exception:
            pass

    def on_cancel_job_click(e):
        if tracked_job:
            manager.cancel_job(tracked_job.job_id)
            btn_cancel_job.visible = False
            status_text.value = "Cancelled"
            status_text.color = text_secondary
            progress_bar.visible = False
            progress_ring.visible = False
            btn_fetch.disabled = False
            url_input.disabled = False
            page.update()

    btn_cancel_job.on_click = on_cancel_job_click

    def _open_model_hub(e=None):
        close_dialog()
        try:
            from src.ui_flet.components.first_time_model_dialog import show_first_time_model_dialog
            show_first_time_model_dialog(page=page, current_palette=current_palette)
        except Exception as ex:
            print(f"[DEBUG] Cannot open model hub: {ex}")

    btn_open_hub.on_click = _open_model_hub

    def _clean_and_set_url(text: str) -> bool:
        if not text:
            return False
        clean = text.strip()

        if is_drive_url(clean):
            url_input.value = clean
            url_input.error_text = None
            return True

        vid = extract_video_id(clean)
        if vid:
            if "youtube.com" in clean or "youtu.be" in clean:
                url_input.value = clean
            else:
                url_input.value = f"https://www.youtube.com/watch?v={vid}"
            url_input.error_text = None
            return True
        elif "youtube" in clean.lower() or "youtu.be" in clean.lower():
            url_input.value = clean
            url_input.error_text = None
            return True

        return False

    async def paste_from_clipboard(e=None):
        try:
            from src.utils.clipboard import get_clipboard_text
            clip_val = get_clipboard_text(page)
            if not clip_val:
                clip_val = await page.get_clipboard_async()
            if clip_val:
                if _clean_and_set_url(clip_val):
                    page.update()
                else:
                    url_input.value = clip_val.strip()
                    page.update()
        except Exception as ex:
            print(f"[DEBUG] Clipboard paste error: {ex}")

    try:
        from src.utils.clipboard import get_clipboard_text
        initial_clip = get_clipboard_text(page)
        if initial_clip:
            _clean_and_set_url(initial_clip)
    except Exception:
        pass

    btn_paste = ft.IconButton(
        icon=ft.Icons.CONTENT_PASTE_ROUNDED,
        tooltip="Paste from clipboard",
        icon_size=20,
        on_click=paste_from_clipboard,
    )

    # Attach to existing running/queued YouTube/Drive job if present
    active_yt_job = manager.get_active_job(job_types=["youtube", "drive"])
    if active_yt_job:
        tracked_job = active_yt_job
        tracked_job.subscribe(_ui_job_listener)
        url_input.value = active_yt_job.source
        url_input.disabled = True
        btn_fetch.disabled = True
        btn_cancel_job.visible = True
        progress_bar.visible = True
        progress_ring.visible = True
        progress_bar.value = active_yt_job.progress if active_yt_job.progress > 0 else None
        status_text.value = active_yt_job.stage_message or "Processing..."
        status_text.visible = True

    def _execute_transcription_task(job: TranscriptionJob, progress_cb: Callable[[str, float], None]):
        url = job.source
        lang_choice = lang_dropdown.value
        preferred_langs = ["vi", "en"] if lang_choice == "vi" else (["en", "vi"] if lang_choice == "en" else ["vi", "en"])
        speech_lang = "vi" if lang_choice == "vi" else ("en" if lang_choice == "en" else None)
        include_ts = chk_timestamps.value
        allow_trans = chk_auto_translate.value

        # Google Drive URL
        if is_drive_url(url):
            progress_cb(t("drive.downloading_audio"), 0.1)

            def _drive_status_cb(stage: str, *args):
                if job.cancel_event.is_set():
                    return
                if stage == "download_progress" and len(args) >= 2:
                    dl, tot = args[0], args[1]
                    pct = (dl / tot) if tot > 0 else 0.0
                    dl_mb, tot_mb = dl / (1024 * 1024), tot / (1024 * 1024)
                    msg = t("drive.download_progress", downloaded=f"{dl_mb:.1f}", total=f"{tot_mb:.1f}", percent=int(pct * 100))
                    progress_cb(msg, min(0.1 + pct * 0.4, 0.5))
                elif stage == "preprocessing":
                    progress_cb(t("speech.preprocessing"), 0.6)
                elif stage == "transcribing":
                    from src.services.whisper_service import get_best_installed_model
                    mid = get_best_installed_model()
                    from src.services.model_manager import AVAILABLE_MODELS
                    meta = AVAILABLE_MODELS.get(mid)
                    mname = meta.display_name if meta else (mid or "Whisper")
                    progress_cb(t("speech.transcribing_with_model", model_name=mname), 0.8)

            from src.services.drive_service import transcribe_drive_video
            return transcribe_drive_video(url, speech_lang, include_ts, _drive_status_cb)

        # YouTube URL
        else:
            progress_cb(t("youtube.fetching"), 0.15)
            success, md_content, err_code, _detected_lang = fetch_youtube_transcript(
                url_or_id=url,
                preferred_languages=preferred_langs,
                include_timestamps=include_ts,
                allow_auto_translate=allow_trans,
            )
            if success:
                return True, md_content, None

            # Fallback to Whisper speech transcription
            if err_code in ("ERR_NO_SUBTITLES", "ERR_EMPTY_SUBTITLES") and chk_speech_fallback.value:
                from src.services.whisper_service import get_best_installed_model
                model_id = get_best_installed_model()
                if model_id:
                    from src.services.model_manager import AVAILABLE_MODELS
                    model_meta = AVAILABLE_MODELS.get(model_id)
                    model_name = model_meta.display_name if model_meta else model_id
                    progress_cb(t("speech.transcribing_with_model", model_name=model_name), 0.4)

                    def _yt_status_cb(stage: str, *args):
                        if job.cancel_event.is_set():
                            return
                        if stage == "preprocessing":
                            progress_cb(t("speech.preprocessing"), 0.5)
                        elif stage == "transcribing":
                            progress_cb(t("speech.transcribing_with_model", model_name=model_name), 0.8)

                    from src.services.speech_service import transcribe_youtube_speech
                    return transcribe_youtube_speech(
                        url_or_id=url,
                        language=speech_lang,
                        include_timestamps=include_ts,
                        status_callback=_yt_status_cb,
                    )
                else:
                    return False, "", "ERR_NO_LOCAL_MODEL"

            return success, md_content, err_code

    def on_fetch_clicked(e):
        url = url_input.value.strip() if url_input.value else ""
        if not url:
            url_input.error_text = t("youtube.invalid_url")
            page.update()
            return

        url_input.error_text = None
        no_model_banner.visible = False
        btn_open_hub.visible = False
        btn_fetch.disabled = True
        btn_cancel_job.visible = True
        progress_bar.visible = True
        progress_ring.visible = True
        status_text.value = "Starting..."
        status_text.visible = True
        page.update()

        def _on_job_success(content: str, source_url: str, title: str):
            if callback_success:
                callback_success(content, source_url)

        def _on_job_error(err_msg: str):
            if err_msg == "ERR_NO_LOCAL_MODEL":
                no_model_banner.visible = True
                btn_open_hub.visible = True
                status_text.value = t("speech.no_model_installed")
                status_text.color = ft.Colors.RED_400
            else:
                status_text.value = err_msg
                status_text.color = ft.Colors.RED_400
            progress_bar.visible = False
            progress_ring.visible = False
            btn_fetch.disabled = False
            btn_cancel_job.visible = False
            try:
                page.update()
            except Exception:
                pass

        nonlocal tracked_job
        job = manager.submit_job(
            job_type="drive" if is_drive_url(url) else "youtube",
            source=url,
            display_name=url,
            execution_fn=_execute_transcription_task,
            on_success=_on_job_success,
            on_error=_on_job_error,
        )
        tracked_job = job
        job.subscribe(_ui_job_listener)

    btn_fetch.on_click = on_fetch_clicked
    btn_cancel.on_click = close_dialog

    dialog = ft.AlertDialog(
        modal=False,
        on_dismiss=close_dialog,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.PLAY_CIRCLE_FILLED_ROUNDED, color=ft.Colors.RED_500, size=28),
                ft.Text(
                    t("youtube.dialog_title"),
                    weight=ft.FontWeight.BOLD,
                    size=16,
                    color=text_primary,
                    expand=True,
                ),
            ],
            spacing=10,
        ),
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[url_input, btn_paste],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    ft.Container(height=4),
                    ft.Row(
                        controls=[lang_dropdown, chk_timestamps],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        spacing=10,
                    ),
                    chk_auto_translate,
                    chk_speech_fallback,
                    ft.Container(height=4),
                    progress_bar,
                    no_model_banner,
                    btn_open_hub,
                    queue_banner,
                    status_row,
                ],
                tight=True,
                spacing=6,
            ),
            width=560,
            padding=10,
        ),
        actions=[
            btn_cancel_job,
            btn_cancel,
            btn_fetch,
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(dialog)
    dialog.open = True
    page.update()
