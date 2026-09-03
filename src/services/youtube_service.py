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


def translate_paragraphs_batch(paragraphs: List[str], target_lang: str = "vi", chunk_size: int = 25) -> List[str]:
    """
    Translates a list of paragraphs to target_lang using Google Translate web service.
    Batches requests using POST to avoid URL length limits and IP bans.
    """
    if not paragraphs or not target_lang or target_lang in ["auto", "raw"]:
        return paragraphs

    tl = "vi" if target_lang.lower().startswith("vi") else ("en" if target_lang.lower().startswith("en") else target_lang)
    translated_all = []

    try:
        import urllib.request
        import urllib.parse
        import json

        for i in range(0, len(paragraphs), chunk_size):
            batch = paragraphs[i : i + chunk_size]
            joined = "\n<<<SEG>>>\n".join(batch)
            encoded = urllib.parse.quote(joined)

            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={tl}&dt=t"
            req = urllib.request.Request(
                url,
                data=f"q={encoded}".encode("utf-8"),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    translated_full = "".join([part[0] for part in data[0] if part and part[0]])
                    parts = [p.strip() for p in translated_full.split("<<<SEG>>>")]
                    if len(parts) == len(batch):
                        translated_all.extend(parts)
                    else:
                        translated_all.extend(batch)
            except Exception:
                translated_all.extend(batch)
        return translated_all
    except Exception:
        return paragraphs


def _fetch_via_ytdlp(
    video_id: str,
    target_lang: str = "vi",
) -> Tuple[bool, dict]:
    """
    Extracts subtitles/captions using yt-dlp with mobile client simulation.
    Bypasses YouTube 429 IP rate-limits without requiring VPN / 1.1.1.1.
    """
    try:
        import yt_dlp
        import json
    except ImportError:
        return False, {}

    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {"youtube": {"player_client": ["android", "ios"]}},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            title = info.get("title", "")
            channel = info.get("uploader") or info.get("channel") or ""

            subs = info.get("subtitles") or {}
            auto_subs = info.get("automatic_captions") or {}

            # Candidate language list
            candidates = []
            # 1. Exact target match in manual subtitles
            if target_lang in subs:
                candidates.append((target_lang, subs[target_lang], False))
            # 2. Other manual subtitles
            for l, caps in subs.items():
                if l != target_lang:
                    candidates.append((l, caps, False))
            # 3. Original auto captions (e.g. en-orig, en, vi-orig, vi)
            for orig in ["en-orig", "en", "vi-orig", "vi", "ja", "ko", "zh"]:
                if orig in auto_subs:
                    candidates.append((orig, auto_subs[orig], True))
            # 4. Any other auto caption
            for l, caps in auto_subs.items():
                if l not in [c[0] for c in candidates]:
                    candidates.append((l, caps, True))

            snippets = []
            used_lang = ""
            is_gen = False

            for lang_code, caps, is_generated in candidates:
                json3 = next((f for f in caps if f.get("ext") == "json3"), caps[0] if caps else None)
                if not json3 or not json3.get("url"):
                    continue
                try:
                    resp = ydl.urlopen(json3["url"])
                    data = json.loads(resp.read().decode("utf-8"))
                    raw_events = data.get("events", [])
                    for ev in raw_events:
                        start_sec = ev.get("tStartMs", 0) / 1000.0
                        segs = ev.get("segs", [])
                        text = "".join([s.get("utf8", "") for s in segs]).strip()
                        if text and text != "\n":
                            snippets.append({"start": start_sec, "text": text})
                    if snippets:
                        used_lang = lang_code
                        is_gen = is_generated
                        break
                except Exception:
                    continue

            if snippets:
                return True, {
                    "title": title,
                    "channel": channel,
                    "lang": used_lang,
                    "is_generated": is_gen,
                    "snippets": snippets,
                }
    except Exception as e:
        print(f"[DEBUG] yt-dlp subtitle extraction failed: {e}")

    return False, {}


SENTENCE_END_RE = re.compile(r'[.!?。！？]["\'\)\]]*$')


def _group_snippets_into_sentences(
    snippets: List[dict],
    group_interval_seconds: float = 15.0,
    max_interval_seconds: float = 30.0,
    pause_threshold: Optional[float] = None,
) -> Tuple[List[float], List[str]]:
    """
    Groups subtitle snippets into coherent paragraphs of complete sentences.
    Splits when full sentences complete, when max interval is reached, or when
    a natural pause / silence gap (>= pause_threshold) occurs between snippets.
    """
    import html

    if not snippets:
        return [], []

    timestamps = []
    paragraph_list = []

    curr_snippets = []
    paragraph_start = None
    last_item_start = None

    def _flush_paragraph(p_start: Optional[float], texts: List[str]):
        if not texts:
            return
        joined = re.sub(r"\s+", " ", " ".join(texts)).strip()
        if not joined:
            return
        # Clean trailing commas/semicolons before ending sentence
        joined = re.sub(r"[,;: ]+$", "", joined)
        if not SENTENCE_END_RE.search(joined):
            joined += "."
        # Capitalize first character if lowercase
        joined = joined[0].upper() + joined[1:] if len(joined) > 1 else joined.upper()
        timestamps.append(p_start if p_start is not None else 0.0)
        paragraph_list.append(joined)

    for item in snippets:
        raw_text = html.unescape(item.get("text", "")).strip()
        if not raw_text:
            continue
        start = float(item.get("start", 0.0))

        # Check if there is a noticeable pause / silence since last snippet
        if (
            curr_snippets
            and last_item_start is not None
            and pause_threshold is not None
            and (start - last_item_start >= pause_threshold)
        ):
            _flush_paragraph(paragraph_start, curr_snippets)
            curr_snippets = []
            paragraph_start = None

        if paragraph_start is None:
            paragraph_start = start

        curr_snippets.append(raw_text)
        duration = start - paragraph_start
        last_item_start = start

        # Check if current snippet finishes a sentence
        is_sentence_end = bool(SENTENCE_END_RE.search(raw_text))

        # Split when sentence is complete AND duration >= group_interval_seconds,
        # OR when max duration is reached with at least 3 snippets
        should_split = (is_sentence_end and duration >= group_interval_seconds) or (
            duration >= max_interval_seconds and len(curr_snippets) >= 3
        )

        if should_split:
            _flush_paragraph(paragraph_start, curr_snippets)
            curr_snippets = []
            paragraph_start = None

    if curr_snippets:
        _flush_paragraph(paragraph_start, curr_snippets)

    return timestamps, paragraph_list


group_snippets_into_sentences = _group_snippets_into_sentences


def fetch_youtube_transcript(
    url_or_id: str,
    preferred_languages: Optional[List[str]] = None,
    include_timestamps: bool = True,
    group_interval_seconds: float = 15.0,
    allow_auto_translate: bool = True,
) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """
    Fetches transcript from YouTube and formats it into Markdown.
    Supports multi-tiered fallback: YouTubeTranscriptApi -> yt-dlp Android/iOS client -> Auto-translation.
    Eliminates IP-blocking (429/IpBoundException) directly in-software without requiring 1.1.1.1/VPN.

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

    target_lang = preferred_languages[0] if preferred_languages else "vi"
    lang_preferences = preferred_languages or ["vi", "en"]

    snippets = []
    video_title = ""
    author_name = ""
    lang_name = ""
    lang_code = ""
    type_str = ""
    needs_post_translation = False

    # Tier 1: Try youtube-transcript-api
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        meta = fetch_video_metadata(video_id)
        video_title = meta.get("title") or f"YouTube Video ({video_id})"
        author_name = meta.get("author") or ""

        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)

        target_transcript = None
        is_translated = False
        original_lang_name = ""

        try:
            target_transcript = transcript_list.find_transcript(lang_preferences)
        except Exception:
            target_transcript = None

        if not target_transcript and allow_auto_translate:
            for t in transcript_list:
                if getattr(t, "is_translatable", False):
                    try:
                        target_transcript = t.translate(target_lang)
                        is_translated = True
                        original_lang_name = getattr(t, "language", getattr(t, "language_code", "foreign"))
                        break
                    except Exception:
                        pass

        if not target_transcript:
            for t in transcript_list:
                if not getattr(t, "is_generated", True):
                    target_transcript = t
                    break

        if not target_transcript:
            for t in transcript_list:
                target_transcript = t
                break

        if target_transcript:
            fetched = target_transcript.fetch()
            for item in fetched:
                txt = getattr(item, "text", "")
                if not txt and isinstance(item, dict):
                    txt = item.get("text", "")
                st = getattr(item, "start", 0.0)
                if not st and isinstance(item, dict):
                    st = item.get("start", 0.0)
                if txt and str(txt).strip():
                    snippets.append({"start": float(st), "text": str(txt).strip()})

            lang_code = getattr(target_transcript, "language_code", target_lang if is_translated else "unknown")
            lang_name = getattr(target_transcript, "language", lang_code)
            is_gen = getattr(target_transcript, "is_generated", False)
            if is_translated:
                type_str = f"Auto-translated from {original_lang_name}"
            else:
                type_str = "Auto-generated" if is_gen else "Manual"
    except Exception as e:
        print(f"[DEBUG] youtube-transcript-api failed ({e}), falling back to yt-dlp engine...")

    # Tier 2: Fallback to yt-dlp with mobile client spoofing (bypasses 429 IP bans)
    if not snippets:
        success_ydl, ydl_data = _fetch_via_ytdlp(video_id, target_lang=target_lang)
        if success_ydl and ydl_data.get("snippets"):
            snippets = ydl_data["snippets"]
            if not video_title or video_title.startswith("YouTube Video"):
                video_title = ydl_data.get("title") or video_title
            if not author_name:
                author_name = ydl_data.get("channel") or ""
            lang_code = ydl_data.get("lang") or "unknown"
            lang_name = lang_code
            is_gen = ydl_data.get("is_generated", False)
            type_str = "Auto-generated" if is_gen else "Manual"

            # Check if post-translation is needed
            if allow_auto_translate and target_lang in ["vi", "en"] and not lang_code.startswith(target_lang):
                needs_post_translation = True

    if not snippets:
        return False, "", "ERR_NO_SUBTITLES", None

    # Grouping snippets into coherent paragraphs of complete sentences
    timestamps, paragraph_list = _group_snippets_into_sentences(
        snippets, group_interval_seconds=group_interval_seconds
    )

    # Apply batch auto-translation if required
    if needs_post_translation and paragraph_list:
        orig_lang_tag = lang_name or lang_code
        paragraph_list = translate_paragraphs_batch(paragraph_list, target_lang=target_lang)
        target_display = "Vietnamese (vi)" if target_lang.startswith("vi") else "English (en)"
        type_str = f"Auto-translated to {target_display} from {orig_lang_tag}"
        lang_name = target_display
        lang_code = target_lang

    # Format Markdown document
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

    for ts, p_text in zip(timestamps, paragraph_list):
        if include_timestamps:
            ts_str = format_timestamp(ts)
            sec = int(ts)
            md_lines.append(f"**[[{ts_str}]](yt://{video_id}?t={sec})** {p_text}\n")
        else:
            md_lines.append(f"{p_text}\n")

    markdown_output = "\n".join(md_lines)
    return True, markdown_output, None, lang_code
