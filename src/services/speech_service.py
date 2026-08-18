"""
Lightweight Non-AI Audio Speech-to-Text Recognition Service.
Transcribes audio from videos without subtitles using Google Web Speech / Windows SAPI.
Does not require downloading or running any heavy AI models.
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
    Returns the absolute path to the downloaded audio file (.wav or .m4a/.webm).
    """
    try:
        import yt_dlp
    except ImportError as e:
        print(f"[DEBUG] Missing yt_dlp: {e}")
        return None

    out_template = os.path.join(target_dir, f"{video_id}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
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


def transcribe_audio_file(
    audio_path: str,
    language: str = "vi",
    chunk_seconds: int = 20,
) -> List[Tuple[float, str]]:
    """
    Transcribes an audio file in chunks without loading any heavy AI models.
    Uses Google Web Speech API (speech_recognition) with language support (vi-VN, en-US).

    Returns:
        List of (start_timestamp_seconds, recognized_text)
    """
    try:
        import speech_recognition as sr
    except ImportError as e:
        print(f"[DEBUG] Missing speech_recognition: {e}")
        return []

    lang_code = "vi-VN" if language.lower().startswith("vi") else "en-US"
    r = sr.Recognizer()
    results = []

    try:
        with sr.AudioFile(audio_path) as source:
            total_duration = getattr(source, "DURATION", 0.0) or 0.0
            current_time = 0.0

            while current_time < total_duration:
                # Read next chunk
                audio_chunk = r.record(source, duration=chunk_seconds)
                try:
                    text = r.recognize_google(audio_chunk, language=lang_code)
                    if text and text.strip():
                        results.append((current_time, text.strip()))
                except sr.UnknownValueError:
                    # Silence or unrecognizable sound in this segment
                    pass
                except sr.RequestError as req_err:
                    print(f"[DEBUG] SpeechRecognition request error at {current_time}s: {req_err}")
                except Exception as chunk_ex:
                    print(f"[DEBUG] Error processing audio chunk at {current_time}s: {chunk_ex}")

                current_time += chunk_seconds
    except Exception as e:
        print(f"[DEBUG] transcribe_audio_file failed: {e}")

    return results


def transcribe_youtube_speech(
    url_or_id: str,
    language: str = "vi",
    include_timestamps: bool = True,
) -> Tuple[bool, str, Optional[str]]:
    """
    Full pipeline to transcribe speech from a YouTube video when no subtitles exist.

    Args:
        url_or_id: YouTube video URL or ID.
        language: Language code ('vi', 'en').
        include_timestamps: Whether to prepend timestamp markers.

    Returns:
        (success: bool, markdown_content: str, error_message: Optional[str])
    """
    video_id = extract_video_id(url_or_id)
    if not video_id:
        return False, "", "ERR_INVALID_URL"

    # Lazy check dependencies
    try:
        import yt_dlp  # noqa: F401
        import speech_recognition as sr  # noqa: F401
    except ImportError as e:
        return False, "", f"Missing dependencies for speech recognition: {e}"

    temp_dir = tempfile.mkdtemp(prefix="docconvert_speech_")
    try:
        # 1. Fetch Video Metadata
        meta = fetch_video_metadata(video_id)
        video_title = meta.get("title") or f"YouTube Video ({video_id})"
        author_name = meta.get("author") or ""

        # 2. Download audio stream
        audio_file = download_youtube_audio(video_id, temp_dir)
        if not audio_file or not os.path.exists(audio_file):
            return False, "", "ERR_AUDIO_DOWNLOAD_FAILED"

        # 3. Transcribe audio in chunks
        chunks = transcribe_audio_file(audio_file, language=language, chunk_seconds=20)
        if not chunks:
            return False, "", "ERR_NO_SPEECH_DETECTED"

        # 4. Format into Markdown
        lang_display = "Vietnamese (vi)" if language.startswith("vi") else "English (en)"
        md_lines = [
            f"# {video_title}",
            "",
        ]
        if author_name:
            md_lines.append(f"- **Channel / Author**: {author_name}")
        md_lines.extend([
            f"- **Source URL**: https://www.youtube.com/watch?v={video_id}",
            f"- **Language**: {lang_display} [Speech Recognition]",
            "",
            "---",
            "",
            "## Speech Transcript",
            "",
        ])

        for start_sec, text in chunks:
            if include_timestamps:
                ts_str = format_timestamp(start_sec)
                md_lines.append(f"**[{ts_str}]** {text}\n")
            else:
                md_lines.append(f"{text}\n")

        markdown_output = "\n".join(md_lines)
        return True, markdown_output, None

    except Exception as e:
        return False, "", f"ERR_SPEECH_TRANSCRIPTION: {str(e)}"
    finally:
        # Clean up temporary directory and downloaded audio
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
