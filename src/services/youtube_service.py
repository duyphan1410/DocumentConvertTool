"""
YouTube Subtitles / Transcript Extraction Service.
Extracts subtitles from YouTube videos and formats them into structured Markdown.
Adheres to the project Lazy Import standard.
"""
import re
from typing import List, Optional, Tuple


def extract_video_id(url_or_id: str) -> Optional[str]:
    """
    Extracts the 11-character YouTube video ID from various URL formats or raw ID.
    Supports:
      - Raw ID: dQw4w9WgXcQ
      - Standard: https://www.youtube.com/watch?v=dQw4w9WgXcQ
      - Short URL: https://youtu.be/dQw4w9WgXcQ
      - Shorts: https://www.youtube.com/shorts/dQw4w9WgXcQ
      - Embed: https://www.youtube.com/embed/dQw4w9WgXcQ
      - Live: https://www.youtube.com/live/dQw4w9WgXcQ
      - Mobile: https://m.youtube.com/watch?v=dQw4w9WgXcQ
    """
    if not url_or_id:
        return None

    raw = url_or_id.strip()

    # If it's already an 11-character ID
    if re.fullmatch(r"^[a-zA-Z0-9_-]{11}$", raw):
        return raw

    patterns = [
        r"(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/|\/live\/)([a-zA-Z0-9_-]{11})",
        r"[?&]v=([a-zA-Z0-9_-]{11})",
    ]

    for pat in patterns:
        match = re.search(pat, raw)
        if match:
            return match.group(1)

    return None


def format_timestamp(seconds: float) -> str:
    """Formats seconds into [mm:ss] or [hh:mm:ss]."""
    total_sec = int(seconds)
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def fetch_video_metadata(video_id: str) -> dict:
    """
    Fetches video metadata (title, author) via official YouTube oEmbed endpoint.
    Falls back gracefully if network is unavailable or request fails.
    """
    meta = {"title": f"YouTube Video ({video_id})", "author": ""}
    try:
        import urllib.request
        import json
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        req = urllib.request.Request(
            oembed_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("title"):
                    meta["title"] = data.get("title").strip()
                if data.get("author_name"):
                    meta["author"] = data.get("author_name").strip()
    except Exception as e:
        print(f"[DEBUG] Failed to fetch oEmbed metadata for {video_id}: {e}")
    return meta


def fetch_youtube_transcript(
    url_or_id: str,
    preferred_languages: Optional[List[str]] = None,
    include_timestamps: bool = True,
    group_interval_seconds: float = 15.0,
    allow_auto_translate: bool = True,
) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """
    Fetches transcript from YouTube and formats it into Markdown.
    Supports native multi-lingual transcripts and server-side Auto-Translate.

    Args:
        url_or_id: YouTube video URL or ID.
        preferred_languages: List of language codes in priority order (e.g. ['vi', 'en']).
        include_timestamps: Whether to prepend timestamp markers.
        group_interval_seconds: Group snippet texts within this duration into unified paragraphs.
        allow_auto_translate: Whether to auto-translate from other available languages if target is missing.

    Returns:
        (success: bool, markdown_content: str, error_message: Optional[str], detected_lang: Optional[str])
    """
    video_id = extract_video_id(url_or_id)
    if not video_id:
        return False, "", "ERR_INVALID_URL", None

    # Lazy import third-party dependency
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            TranscriptsDisabled,
            NoTranscriptFound,
            VideoUnavailable,
            InvalidVideoId,
            CouldNotRetrieveTranscript,
        )
    except ImportError as e:
        return False, "", f"Missing dependency 'youtube-transcript-api': {e}", None

    try:
        # Fetch Video Title & Author
        meta = fetch_video_metadata(video_id)
        video_title = meta.get("title") or f"YouTube Video ({video_id})"
        author_name = meta.get("author") or ""

        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)

        target_transcript = None
        target_lang = preferred_languages[0] if preferred_languages else "vi"
        lang_preferences = preferred_languages or ["vi", "en"]
        is_translated = False
        original_lang_name = ""

        # 1. Try finding direct match by preferred languages (manual or generated)
        try:
            target_transcript = transcript_list.find_transcript(lang_preferences)
        except Exception:
            target_transcript = None

        # 2. If preferred language not found directly and auto-translate is allowed
        if not target_transcript and allow_auto_translate:
            for t in transcript_list:
                if getattr(t, "is_translatable", False):
                    try:
                        target_transcript = t.translate(target_lang)
                        is_translated = True
                        original_lang_name = getattr(t, "language", getattr(t, "language_code", "foreign"))
                        break
                    except Exception as ex_tr:
                        print(f"[DEBUG] Translation to {target_lang} failed: {ex_tr}")

        # 3. Fallback to manually created transcripts in any language
        if not target_transcript:
            for t in transcript_list:
                if not getattr(t, "is_generated", True):
                    target_transcript = t
                    break

        # 4. Fallback to first available generated transcript
        if not target_transcript:
            for t in transcript_list:
                target_transcript = t
                break

        if not target_transcript:
            return False, "", "ERR_NO_SUBTITLES", None

        # Fetch snippets
        fetched = target_transcript.fetch()
        lang_code = getattr(target_transcript, "language_code", target_lang if is_translated else "unknown")
        lang_name = getattr(target_transcript, "language", lang_code)
        is_gen = getattr(target_transcript, "is_generated", False)
        
        if is_translated:
            type_str = f"Auto-translated from {original_lang_name}"
        else:
            type_str = "Auto-generated" if is_gen else "Manual"

        # Format into Markdown with clean Header and Title
        md_lines = [
            f"# {video_title}",
            "",
        ]
        if author_name:
            md_lines.append(f"- **Channel / Author**: {author_name}")
        md_lines.extend([
            f"- **Source URL**: https://www.youtube.com/watch?v={video_id}",
            f"- **Language**: {lang_name} (`{lang_code}`) [{type_str}]",
            "",
            "---",
            "",
            "## Transcript",
            "",
        ])

        if not fetched:
            return False, "", "ERR_EMPTY_SUBTITLES", lang_code

        # Grouping snippets into coherent paragraphs with timestamps
        if include_timestamps:
            current_paragraph = []
            curr_start = 0.0
            paragraph_start = None

            for item in fetched:
                text = getattr(item, "text", "")
                if not text and isinstance(item, dict):
                    text = item.get("text", "")
                text = str(text).strip()
                if not text:
                    continue

                start = getattr(item, "start", 0.0)
                if not start and isinstance(item, dict):
                    start = item.get("start", 0.0)

                if paragraph_start is None:
                    paragraph_start = start

                current_paragraph.append(text)

                # Group by interval or newline threshold
                if (start - paragraph_start >= group_interval_seconds) or len(current_paragraph) >= 5:
                    ts_str = format_timestamp(paragraph_start)
                    paragraph_text = " ".join(current_paragraph)
                    md_lines.append(f"**[{ts_str}]** {paragraph_text}\n")
                    current_paragraph = []
                    paragraph_start = None

            if current_paragraph:
                ts_str = format_timestamp(paragraph_start if paragraph_start is not None else 0.0)
                paragraph_text = " ".join(current_paragraph)
                md_lines.append(f"**[{ts_str}]** {paragraph_text}\n")
        else:
            # Plain paragraphs without timestamps
            current_paragraph = []
            for item in fetched:
                text = getattr(item, "text", "")
                if not text and isinstance(item, dict):
                    text = item.get("text", "")
                text = str(text).strip()
                if not text:
                    continue

                current_paragraph.append(text)
                if len(current_paragraph) >= 6:
                    md_lines.append(" ".join(current_paragraph) + "\n")
                    current_paragraph = []

            if current_paragraph:
                md_lines.append(" ".join(current_paragraph) + "\n")

        markdown_output = "\n".join(md_lines)
        return True, markdown_output, None, lang_code

    except (TranscriptsDisabled, NoTranscriptFound):
        return False, "", "ERR_NO_SUBTITLES", None
    except VideoUnavailable:
        return False, "", "ERR_VIDEO_UNAVAILABLE", None
    except InvalidVideoId:
        return False, "", "ERR_INVALID_VIDEO_ID", None
    except CouldNotRetrieveTranscript as e:
        return False, "", f"ERR_RETRIEVE_FAILED: {str(e)}", None
    except Exception as e:
        err_str = str(e).lower()
        if "no transcript" in err_str or "subtitles are disabled" in err_str or "transcriptsdisabled" in err_str:
            return False, "", "ERR_NO_SUBTITLES", None
        return False, "", f"ERR_UNKNOWN: {str(e)}", None
