"""
Video Transcript Import Dialog for Flet UI.
Supports both YouTube and Google Drive video URLs.
Extracts subtitles from YouTube or transcribes speech using local Whisper AI models.
No Google Speech API — only local offline AI or YouTube's built-in captions.
"""
import asyncio
from typing import Callable, Optional
import flet as ft

from src.i18n import t
from src.services.youtube_service import extract_video_id, fetch_youtube_transcript
from src.services.drive_service import is_drive_url, extract_drive_file_id
from src.ui_flet.theme import PALETTES, resolve_color, get_style_color


def show_youtube_dialog(
    page: ft.Page,
    on_transcript_loaded: Callable[[str, str], None],
    current_palette: str = "Violet Cyberpunk",
):
    """
    Displays modal dialog to import video subtitles/transcript as Markdown.
    Accepts YouTube URLs and Google Drive video URLs.
    """
    page.overlay[:] = [c for c in page.overlay if not isinstance(c, ft.AlertDialog)]

    is_dark = page.theme_mode != ft.ThemeMode.LIGHT
    palette = PALETTES.get(current_palette, {})

    text_primary = get_style_color("text_primary", is_dark)
    text_secondary = get_style_color("text_secondary", is_dark)
    accent_primary = resolve_color(palette, "text_accent_primary", is_dark)

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

    progress_ring = ft.ProgressRing(width=18, height=18, stroke_width=2.5, visible=False)
    status_text = ft.Text("", size=12, color=accent_primary, visible=False, expand=True)

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

    def _show_inline_error(msg: str):
        status_text.color = ft.Colors.RED_400
        status_text.value = msg
        status_text.visible = True
        page.update()

    def _show_status(msg: str):
        status_text.color = accent_primary
        status_text.value = msg
        status_text.visible = True
        progress_ring.visible = True
        page.update()

    def _show_no_model_banner():
        no_model_banner.visible = True
        btn_open_hub.visible = True
        page.update()

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

    status_row = ft.Row(
        controls=[progress_ring, status_text],
        alignment=ft.MainAxisAlignment.START,
        spacing=8,
    )

    def close_dialog(e=None):
        dialog.open = False
        try:
            page.update()
        except Exception:
            pass

    def _open_model_hub(e=None):
        close_dialog()
        try:
            from src.ui_flet.components.first_time_model_dialog import show_first_time_model_dialog
            show_first_time_model_dialog(page=page, current_palette=current_palette)
        except Exception as ex:
            print(f"[DEBUG] Cannot open model hub: {ex}")

    btn_open_hub.on_click = _open_model_hub

    def _clean_and_set_url(text: str) -> bool:
        """Normalizes YouTube or Drive URL in the text field. Returns True if recognized."""
        if not text:
            return False
        clean = text.strip()

        # Drive URL
        if is_drive_url(clean):
            url_input.value = clean
            url_input.error_text = None
            return True

        # YouTube URL/ID
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

    # Auto-populate if clipboard already contains a valid link
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

    async def on_fetch_clicked(e):
        url = url_input.value.strip() if url_input.value else ""
        if not url:
            url_input.error_text = t("youtube.invalid_url")
            page.update()
            return

        # Reset UI state
        url_input.error_text = None
        no_model_banner.visible = False
        btn_open_hub.visible = False
        btn_fetch.disabled = True
        btn_cancel.disabled = True

        # Language preference
        lang_choice = lang_dropdown.value
        if lang_choice == "vi":
            preferred_langs = ["vi", "en"]
            speech_lang = "vi"
        elif lang_choice == "en":
            preferred_langs = ["en", "vi"]
            speech_lang = "en"
        else:
            preferred_langs = ["vi", "en"]
            speech_lang = None  # Auto-detect language in Whisper

        include_ts = chk_timestamps.value
        allow_trans = chk_auto_translate.value

        success = False
        md_content = ""
        err_code = None

        loop = asyncio.get_running_loop()

        def _update_status_safe(text: str):
            def _apply():
                status_text.value = text
                status_text.visible = True
                progress_ring.visible = True
                page.update()
            loop.call_soon_threadsafe(_apply)

        # ── BRANCH: Google Drive URL ──────────────────────────────────────────
        if is_drive_url(url):
            file_id = extract_drive_file_id(url)
            if not file_id:
                url_input.error_text = t("drive.invalid_url")
                btn_fetch.disabled = False
                btn_cancel.disabled = False
                page.update()
                return

            _show_status(t("drive.downloading_audio"))

            def _drive_status_cb(stage: str, *args):
                if stage == "download_progress" and len(args) >= 2:
                    dl, tot = args[0], args[1]
                    dl_mb = dl / (1024 * 1024)
                    tot_mb = tot / (1024 * 1024)
                    pct = int((dl / tot) * 100) if tot > 0 else 0
                    msg = t("drive.download_progress", downloaded=f"{dl_mb:.1f}", total=f"{tot_mb:.1f}", percent=pct)
                    _update_status_safe(msg)
                elif stage == "preprocessing":
                    _update_status_safe(t("speech.preprocessing"))
                elif stage == "transcribing":
                    from src.services.speech_service import get_best_installed_model
                    mid = get_best_installed_model()
                    from src.services.model_manager import AVAILABLE_MODELS
                    meta = AVAILABLE_MODELS.get(mid)
                    mname = meta.display_name if meta else (mid or "Whisper")
                    _update_status_safe(t("speech.transcribing_with_model", model_name=mname))

            from src.services.drive_service import transcribe_drive_video
            success, md_content, err_code = await asyncio.to_thread(
                transcribe_drive_video,
                url,
                speech_lang,
                include_ts,
                _drive_status_cb,
            )

        # ── BRANCH: YouTube URL ───────────────────────────────────────────────
        else:
            video_id = extract_video_id(url)
            if not video_id:
                url_input.error_text = t("youtube.invalid_url")
                btn_fetch.disabled = False
                btn_cancel.disabled = False
                page.update()
                return

            # 1. Try standard YouTube subtitles first
            _show_status(t("youtube.fetching"))
            success, md_content, err_code, _detected_lang = await asyncio.to_thread(
                fetch_youtube_transcript,
                url_or_id=url,
                preferred_languages=preferred_langs,
                include_timestamps=include_ts,
                allow_auto_translate=allow_trans,
            )

            # 2. Fallback: local Whisper transcription (if subs not found and checkbox enabled)
            if not success and err_code in ("ERR_NO_SUBTITLES", "ERR_EMPTY_SUBTITLES") and chk_speech_fallback.value:
                from src.services.speech_service import get_best_installed_model
                model_id = get_best_installed_model()

                if model_id:
                    from src.services.model_manager import AVAILABLE_MODELS
                    model_meta = AVAILABLE_MODELS.get(model_id)
                    model_name = model_meta.display_name if model_meta else model_id
                    _show_status(t("speech.transcribing_with_model", model_name=model_name))

                    def _yt_status_cb(stage: str, *args):
                        if stage == "preprocessing":
                            _update_status_safe(t("speech.preprocessing"))
                        elif stage == "transcribing":
                            _update_status_safe(t("speech.transcribing_with_model", model_name=model_name))

                    from src.services.speech_service import transcribe_youtube_speech
                    sp_success, sp_md, sp_err = await asyncio.to_thread(
                        transcribe_youtube_speech,
                        url_or_id=url,
                        language=speech_lang,
                        include_timestamps=include_ts,
                        status_callback=_yt_status_cb,
                    )
                    if sp_success:
                        success = True
                        md_content = sp_md
                        err_code = None
                    else:
                        err_code = sp_err
                else:
                    # No local model installed — show banner, don't silently fall back
                    err_code = "ERR_NO_LOCAL_MODEL"

        # ── Restore buttons ───────────────────────────────────────────────────
        btn_fetch.disabled = False
        btn_cancel.disabled = False
        progress_ring.visible = False
        status_text.visible = False

        # ── Error handling ────────────────────────────────────────────────────
        if not success:
            if err_code == "ERR_NO_LOCAL_MODEL":
                _show_no_model_banner()
                _show_inline_error(t("speech.no_model_installed"))
            elif err_code in ("ERR_NO_SUBTITLES", "ERR_EMPTY_SUBTITLES"):
                _show_inline_error(t("youtube.no_subs_found"))
            elif err_code == "ERR_NO_SPEECH_DETECTED":
                _show_inline_error(t("youtube.no_speech_detected"))
            elif err_code in ("ERR_INVALID_URL", "ERR_INVALID_VIDEO_ID"):
                url_input.error_text = t("youtube.invalid_url")
                page.update()
            elif err_code == "ERR_INVALID_DRIVE_URL":
                url_input.error_text = t("drive.invalid_url")
                page.update()
            elif err_code == "ERR_DRIVE_ACCESS_DENIED":
                _show_inline_error(t("drive.access_denied"))
            elif err_code == "ERR_DRIVE_NOT_FOUND":
                _show_inline_error(t("drive.not_found"))
            elif err_code == "ERR_DRIVE_TOO_LARGE":
                _show_inline_error(t("drive.too_large"))
            elif err_code == "ERR_VIDEO_UNAVAILABLE":
                _show_inline_error(t("youtube.video_unavailable"))
            elif err_code == "ERR_AUDIO_DOWNLOAD_FAILED":
                _show_inline_error(t("youtube.audio_download_failed"))
            else:
                _show_inline_error(err_code or "Unknown Error")
            return

        # ── Success ───────────────────────────────────────────────────────────
        dialog.open = False
        page.update()

        if on_transcript_loaded:
            on_transcript_loaded(md_content, url)

    btn_fetch.on_click = lambda e: asyncio.create_task(on_fetch_clicked(e))
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
                    no_model_banner,
                    btn_open_hub,
                    status_row,
                ],
                tight=True,
                spacing=6,
            ),
            width=560,
            padding=10,
        ),
        actions=[
            btn_cancel,
            btn_fetch,
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(dialog)
    dialog.open = True
    page.update()
