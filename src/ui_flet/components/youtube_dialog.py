"""
YouTube Transcript Import Dialog for Flet UI.
Allows users to paste YouTube links, choose preferences, fetch subtitles,
and seamlessly inject structured Markdown into the workspace.
"""
import asyncio
from typing import Callable, Optional
import flet as ft

from src.i18n import t
from src.services.youtube_service import extract_video_id, fetch_youtube_transcript
from src.ui_flet.theme import PALETTES, resolve_color, get_style_color


def show_youtube_dialog(
    page: ft.Page,
    on_transcript_loaded: Callable[[str, str], None],
    current_palette: str = "Violet Cyberpunk",
):
    """
    Displays modal dialog to input a YouTube link and extract Markdown subtitles.
    """
    # Clean up any stale dialogs from overlay
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

    def _show_inline_error(msg: str):
        status_text.color = ft.Colors.RED_400
        status_text.value = msg
        status_text.visible = True
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

    def _clean_and_set_youtube_url(text: str) -> bool:
        if not text:
            return False
        clean = text.strip()
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
                if _clean_and_set_youtube_url(clip_val):
                    page.update()
                else:
                    url_input.value = clip_val.strip()
                    page.update()
        except Exception as ex:
            print(f"[DEBUG] Clipboard paste error: {ex}")

    # Auto-populate if clipboard already contains a valid YouTube link
    try:
        from src.utils.clipboard import get_clipboard_text
        initial_clip = get_clipboard_text(page)
        if initial_clip:
            _clean_and_set_youtube_url(initial_clip)
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

        video_id = extract_video_id(url)
        if not video_id:
            url_input.error_text = t("youtube.invalid_url")
            page.update()
            return

        url_input.error_text = None
        btn_fetch.disabled = True
        btn_cancel.disabled = True
        progress_ring.visible = True
        status_text.visible = True
        status_text.value = t("youtube.fetching")
        page.update()

        # Language preference
        lang_choice = lang_dropdown.value
        if lang_choice == "vi":
            preferred_langs = ["vi", "en"]
        elif lang_choice == "en":
            preferred_langs = ["en", "vi"]
        else:
            preferred_langs = ["vi", "en"]

        include_ts = chk_timestamps.value
        allow_trans = chk_auto_translate.value

        # 1. First Attempt: Standard / Auto-translated subtitles
        success, md_content, err_code, detected_lang = await asyncio.to_thread(
            fetch_youtube_transcript,
            url_or_id=url,
            preferred_languages=preferred_langs,
            include_timestamps=include_ts,
            allow_auto_translate=allow_trans,
        )

        # 2. Second Attempt: If no subtitles exist, fallback to Speech-to-Text Recognition
        if not success and (err_code == "ERR_NO_SUBTITLES" or err_code == "ERR_EMPTY_SUBTITLES") and chk_speech_fallback.value:
            status_text.value = t("youtube.recognizing_speech")
            page.update()
            try:
                from src.services.speech_service import transcribe_youtube_speech
                sp_success, sp_md, sp_err = await asyncio.to_thread(
                    transcribe_youtube_speech,
                    url_or_id=url,
                    language="vi" if preferred_langs[0] == "vi" else "en",
                    include_timestamps=include_ts,
                )
                if sp_success:
                    success = True
                    md_content = sp_md
                    err_code = None
            except Exception as ex_speech:
                print(f"[DEBUG] Speech Recognition fallback failed: {ex_speech}")

        btn_fetch.disabled = False
        btn_cancel.disabled = False
        progress_ring.visible = False
        status_text.visible = False

        if not success:
            if err_code == "ERR_NO_SUBTITLES" or err_code == "ERR_EMPTY_SUBTITLES":
                _show_inline_error(t("youtube.no_subs_found"))
            elif err_code == "ERR_NO_SPEECH_DETECTED":
                _show_inline_error(t("youtube.no_speech_detected"))
            elif err_code == "ERR_INVALID_URL" or err_code == "ERR_INVALID_VIDEO_ID":
                url_input.error_text = t("youtube.invalid_url")
                page.update()
            elif err_code == "ERR_VIDEO_UNAVAILABLE":
                _show_inline_error(t("youtube.video_unavailable"))
            elif err_code == "ERR_AUDIO_DOWNLOAD_FAILED":
                _show_inline_error(t("youtube.audio_download_failed"))
            else:
                _show_inline_error(err_code or "Unknown Error")
            return

        # Success: close dialog and inject into workspace
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
