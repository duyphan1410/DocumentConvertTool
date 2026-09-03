"""
Local AI Speech-to-Text Transcription Service.
Transcribes audio from videos using locally installed faster-whisper models.
Requires a model to be downloaded via the Model Hub — no internet needed at runtime.
Adheres to the project Lazy Import standard.
"""
import os
import shutil
import tempfile
from typing import List, Optional, Tuple

from src.services.youtube_service import extract_video_id, fetch_video_metadata, format_timestamp


def download_youtube_audio(video_id: str, target_dir: str) -> Optional[str]:
    """
    Downloads lightweight audio stream from YouTube video into target_dir.
    Returns the absolute path to the downloaded audio file (.m4a/.webm).
    """
    try:
        import yt_dlp
    except ImportError as e:
        print(f"[DEBUG] Missing yt_dlp: {e}")
        return None

    out_template = os.path.join(target_dir, f"{video_id}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/18/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },
    }

    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        for fname in os.listdir(target_dir):
            if fname.startswith(video_id):
                return os.path.join(target_dir, fname)
    except Exception as e:
        print(f"[DEBUG] yt-dlp audio download failed: {e}")

    return None


from src.services.whisper_service import (
    get_best_installed_model,
    preprocess_audio,
    transcribe_audio_whisper,
)


def transcribe_youtube_speech(
    url_or_id: str,
    language: Optional[str] = "vi",
    include_timestamps: bool = True,
    status_callback=None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Full pipeline to transcribe speech from a YouTube video using local Whisper AI.
    No internet connection required for transcription (only for audio download).

    Args:
        url_or_id: YouTube video URL or ID.
        language: Language code ('vi', 'en', 'auto', or None for auto-detect).
        include_timestamps: Whether to prepend timestamp markers.
        status_callback: Optional callable(stage_name) for UI progress updates.

    Returns:
        (success: bool, markdown_content: str, error_code: Optional[str])
    """
    video_id = extract_video_id(url_or_id)
    if not video_id:
        return False, "", "ERR_INVALID_URL"

    # Check local model availability
    model_id = get_best_installed_model()
    if not model_id:
        return False, "", "ERR_NO_LOCAL_MODEL"

    # Check yt_dlp available for audio download
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        return False, "", "ERR_MISSING_YTDLP"

    temp_dir = tempfile.mkdtemp(prefix="docconvert_speech_")
    try:
        # 1. Fetch Video Metadata
        meta = fetch_video_metadata(video_id)
        video_title = meta.get("title") or f"YouTube Video ({video_id})"
        author_name = meta.get("author") or ""

        # 2. Download audio stream
        if status_callback:
            status_callback("downloading")
        audio_file = download_youtube_audio(video_id, temp_dir)
        if not audio_file or not os.path.exists(audio_file):
            return False, "", "ERR_AUDIO_DOWNLOAD_FAILED"

        # 3. Preprocess & Transcribe with local Whisper
        print(f"[SPEECH] Starting Whisper transcription with model: {model_id}")
        chunks, detected_lang = transcribe_audio_whisper(
            audio_file,
            model_id=model_id,
            language=language,
            status_callback=status_callback,
            return_info=True,
        )
        if not chunks:
            return False, "", "ERR_NO_SPEECH_DETECTED"

        # 4. Format into Markdown
        from src.services.model_manager import AVAILABLE_MODELS
        model_display = AVAILABLE_MODELS.get(model_id, {})
        model_name = getattr(model_display, "display_name", model_id) if model_display else model_id

        if detected_lang == "vi":
            lang_display = "Vietnamese (vi)"
        elif detected_lang == "en":
            lang_display = "English (en)"
        else:
            lang_display = f"{detected_lang.upper()} ({detected_lang})"

        md_lines = [
            f"# {video_title}",
            "",
        ]
        if author_name:
            md_lines.append(f"- **Channel / Author**: {author_name}")
        md_lines.extend([
            f"- **Source URL**: https://www.youtube.com/watch?v={video_id}",
            f"- **Language**: {lang_display} [AI Transcription — {model_name}]",
            "",
            "---",
            "",
            "## Speech Transcript",
            "",
        ])

        # Group snippets into coherent paragraphs (similar to standard YouTube transcripts)
        from src.services.youtube_service import _group_snippets_into_sentences
        snippets = [{"start": s, "text": t} for s, t in chunks]
        timestamps, paragraph_list = _group_snippets_into_sentences(snippets)

        for ts, p_text in zip(timestamps, paragraph_list):
            if include_timestamps:
                ts_str = format_timestamp(ts)
                sec = int(ts)
                md_lines.append(f"**[[{ts_str}]](yt://{video_id}?t={sec})** {p_text}\n")
            else:
                md_lines.append(f"{p_text}\n")

        markdown_output = "\n".join(md_lines)
        return True, markdown_output, None

    except Exception as e:
        return False, "", f"ERR_SPEECH_TRANSCRIPTION: {str(e)}"
    finally:
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass


def transcribe_drive_speech(
    file_id: str,
    audio_path: str,
    file_name: str = "",
    language: Optional[str] = "vi",
    include_timestamps: bool = True,
    status_callback=None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Transcribes speech from a locally downloaded Google Drive audio/video file.

    Args:
        file_id: Google Drive file ID.
        audio_path: Local path to the downloaded audio/video file.
        file_name: Original filename for Markdown header.
        language: Language code ('vi', 'en', 'auto', or None for auto-detect).
        include_timestamps: Whether to include timestamp markers.
        status_callback: Optional callable(stage_name) for UI progress updates.

    Returns:
        (success: bool, markdown_content: str, error_code: Optional[str])
    """
    # Check local model availability
    model_id = get_best_installed_model()
    if not model_id:
        return False, "", "ERR_NO_LOCAL_MODEL"

    if not audio_path or not os.path.exists(audio_path):
        return False, "", "ERR_AUDIO_DOWNLOAD_FAILED"

    try:
        # Transcribe with local Whisper + Audio Preprocessing
        print(f"[SPEECH] Starting Whisper transcription (Drive) with model: {model_id}")
        chunks, detected_lang = transcribe_audio_whisper(
            audio_path,
            model_id=model_id,
            language=language,
            status_callback=status_callback,
            return_info=True,
        )
        if not chunks:
            return False, "", "ERR_NO_SPEECH_DETECTED"

        # Format into Markdown
        from src.services.model_manager import AVAILABLE_MODELS
        model_meta = AVAILABLE_MODELS.get(model_id)
        model_name = model_meta.display_name if model_meta else model_id

        if detected_lang == "vi":
            lang_display = "Vietnamese (vi)"
        elif detected_lang == "en":
            lang_display = "English (en)"
        else:
            lang_display = f"{detected_lang.upper()} ({detected_lang})"

        title = file_name or f"Google Drive Video ({file_id})"
        drive_url = f"https://drive.google.com/file/d/{file_id}/view"

        md_lines = [
            f"# {title}",
            "",
            f"- **Source URL**: {drive_url}",
            f"- **Language**: {lang_display} [AI Transcription — {model_name}]",
            "",
            "---",
            "",
            "## Speech Transcript",
            "",
        ]

        # Group snippets into coherent paragraphs (similar to standard YouTube transcripts)
        from src.services.youtube_service import _group_snippets_into_sentences
        snippets = [{"start": s, "text": t} for s, t in chunks]
        timestamps, paragraph_list = _group_snippets_into_sentences(snippets)

        for ts, p_text in zip(timestamps, paragraph_list):
            if include_timestamps:
                ts_str = format_timestamp(ts)
                md_lines.append(f"**[{ts_str}]** {p_text}\n")
            else:
                md_lines.append(f"{p_text}\n")

        return True, "\n".join(md_lines), None

    except Exception as e:
        return False, "", f"ERR_SPEECH_TRANSCRIPTION: {str(e)}"
