"""
Google Drive Video / Audio Download Service.
Extracts file IDs from Drive URLs, downloads media files for offline Whisper transcription,
and handles permission / access errors gracefully.
Adheres to the project Lazy Import standard.
"""
import os
import re
import shutil
import tempfile
from typing import Optional, Tuple


def extract_drive_file_id(url: str) -> Optional[str]:
    """
    Extracts the Google Drive file ID from various Drive URL formats.

    Supported formats:
      - https://drive.google.com/file/d/<ID>/view
      - https://drive.google.com/open?id=<ID>
      - https://drive.google.com/uc?id=<ID>
      - https://docs.google.com/... (shared docs with /d/<ID>/)

    Returns:
        The 33-character file ID string, or None if not matched.
    """
    if not url:
        return None

    raw = url.strip()

    patterns = [
        r"/file/d/([a-zA-Z0-9_-]{28,})",      # /file/d/<ID>/
        r"[?&]id=([a-zA-Z0-9_-]{28,})",        # ?id=<ID> or &id=<ID>
        r"/d/([a-zA-Z0-9_-]{28,})/",           # Google Docs /d/<ID>/
    ]

    for pat in patterns:
        match = re.search(pat, raw)
        if match:
            return match.group(1)

    return None


def is_drive_url(url: str) -> bool:
    """Returns True if the URL is a Google Drive / Docs URL."""
    if not url:
        return False
    return "drive.google.com" in url or "docs.google.com" in url


def fetch_drive_file_metadata(file_id: str) -> dict:
    """
    Attempts to fetch public file metadata (name, mimeType) via the Drive public API.
    Returns minimal dict with 'name' and 'mime_type'. Falls back gracefully on errors.

    Note: Only works for publicly accessible files. Private files will return defaults.
    """
    meta = {"name": "", "mime_type": ""}
    try:
        import urllib.request
        import json

        api_url = f"https://drive.google.com/uc?id={file_id}&export=download"
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            method="HEAD",
        )
        # We only need headers; a HEAD request is enough to detect redirect/name
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            content_disp = resp.headers.get("Content-Disposition", "")
            if "filename" in content_disp:
                name_match = re.search(r'filename[*]?=["\']?([^"\';\r\n]+)', content_disp)
                if name_match:
                    meta["name"] = name_match.group(1).strip().strip('"')
            meta["mime_type"] = resp.headers.get("Content-Type", "")
    except Exception as e:
        print(f"[DEBUG] Drive metadata fetch skipped: {e}")

    return meta


def _download_drive_audio_ytdlp(
    file_id: str,
    target_dir: str,
    progress_callback=None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempts to download ONLY the audio stream directly from Google Drive Video Playback
    CDN using yt-dlp. Highly efficient (downloads ~10MB audio instead of 500MB+ video).

    Returns:
        (dest_path, file_name) on success, or (None, error_code) on failure.
    """
    try:
        import yt_dlp
    except ImportError:
        return None, "ERR_DRIVE_DOWNLOAD_FAILED"

    url = f"https://drive.google.com/file/d/{file_id}/view"
    out_template = os.path.join(target_dir, f"drive_{file_id}.%(ext)s")

    ydl_opts = {
        # Prefer standalone audio stream (m4a, opus, webm) or lowest video if audio is embedded
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    if progress_callback:
        def _hook(d):
            if d.get("status") == "downloading":
                dl = d.get("downloaded_bytes", 0)
                tot = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                if tot > 0:
                    try:
                        progress_callback(dl, tot)
                    except Exception:
                        pass
        ydl_opts["progress_hooks"] = [_hook]

    try:
        print(f"[DRIVE] Attempting high-speed audio stream extraction via yt-dlp for file_id={file_id}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        for fname in os.listdir(target_dir):
            if fname.startswith(f"drive_{file_id}"):
                full_path = os.path.join(target_dir, fname)
                if os.path.isfile(full_path) and os.path.getsize(full_path) > 0:
                    print(f"[DRIVE] Fast audio stream downloaded via yt-dlp: {fname} ({os.path.getsize(full_path) / 1024 / 1024:.1f} MB)")
                    return full_path, fname

    except Exception as e:
        err_msg = str(e).lower()
        print(f"[DEBUG] yt-dlp drive audio extraction skipped: {e}")
        if "permission denied" in err_msg or "private" in err_msg or "sign in" in err_msg:
            return None, "ERR_DRIVE_ACCESS_DENIED"
        if "not found" in err_msg or "does not exist" in err_msg:
            return None, "ERR_DRIVE_NOT_FOUND"

    return None, "ERR_DRIVE_DOWNLOAD_FAILED"


def download_drive_audio(
    file_id: str,
    target_dir: str,
    progress_callback=None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Downloads a Google Drive file (audio/video) to target_dir.
    Uses a Dual-Path strategy:
      1. Fast Path: yt-dlp audio stream extraction (~10MB instead of 500MB+ full video).
      2. Direct Fallback: 1MB chunked streaming download with CookieJar session for large files.

    Args:
        file_id: Google Drive file ID.
        target_dir: Directory to save the downloaded file.
        progress_callback: Optional callable(downloaded_bytes, total_bytes) for progress.

    Returns:
        (local_file_path, file_name) on success.
        (None, error_code) on failure.
    """
    # ── PATH 1: Try ultra-fast audio-only stream extraction via yt-dlp ─────
    path, err = _download_drive_audio_ytdlp(file_id, target_dir, progress_callback)
    if path and os.path.exists(path):
        return path, err
    if err in ("ERR_DRIVE_ACCESS_DENIED", "ERR_DRIVE_NOT_FOUND"):
        return None, err

    # ── PATH 2: Fallback to 1MB chunked direct HTTP download ─────────────
    print(f"[DRIVE] Falling back to direct HTTP download for file_id={file_id}...")
    import urllib.request
    import urllib.error
    import http.cookiejar

    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
    }

    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    try:
        req = urllib.request.Request(download_url, headers=headers)
        with opener.open(req, timeout=20) as resp:
            content_type = resp.headers.get("Content-Type", "")
            content_disp = resp.headers.get("Content-Disposition", "")

            # Handle Google Drive virus scan warning / large file confirmation
            if "text/html" in content_type:
                html_bytes = resp.read(8192)
                html_text = html_bytes.decode("utf-8", errors="ignore").lower()

                if "sign in" in html_text or "accounts.google.com" in html_text:
                    return None, "ERR_DRIVE_ACCESS_DENIED"
                if "no such file" in html_text or "not found" in html_text:
                    return None, "ERR_DRIVE_NOT_FOUND"

                # Extract confirmation token and retry with session cookies retained
                confirm_match = re.search(r'confirm=([a-zA-Z0-9_-]+)', html_text)
                if confirm_match:
                    confirm_token = confirm_match.group(1)
                    confirmed_url = f"{download_url}&confirm={confirm_token}"
                    return _do_download_stream(opener, confirmed_url, file_id, target_dir, headers, progress_callback)

                return None, "ERR_DRIVE_TOO_LARGE"

            file_ext = _guess_extension(content_type, content_disp)
            file_name = _extract_filename(content_disp) or f"drive_{file_id}{file_ext}"
            dest_path = os.path.join(target_dir, file_name)

            # Stream download with 1MB buffer (1048576 bytes) for maximum throughput
            total_size = int(resp.headers.get("Content-Length", 0) or 0)
            downloaded = 0
            buf_size = 1048576  # 1 MB chunk

            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(buf_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        try:
                            progress_callback(downloaded, total_size)
                        except Exception:
                            pass

            if os.path.getsize(dest_path) == 0:
                return None, "ERR_DRIVE_DOWNLOAD_FAILED"

            print(f"[DRIVE] Direct download finished: {file_name} ({downloaded / 1024 / 1024:.1f} MB)")
            return dest_path, file_name

    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return None, "ERR_DRIVE_ACCESS_DENIED"
        if e.code == 404:
            return None, "ERR_DRIVE_NOT_FOUND"
        print(f"[DEBUG] Drive HTTP error: {e.code} {e.reason}")
        return None, "ERR_DRIVE_DOWNLOAD_FAILED"
    except Exception as e:
        print(f"[DEBUG] Drive download unexpected error: {e}")
        return None, "ERR_DRIVE_DOWNLOAD_FAILED"


def _do_download_stream(
    opener,
    url: str,
    file_id: str,
    target_dir: str,
    headers: dict,
    progress_callback=None,
) -> Tuple[Optional[str], Optional[str]]:
    """Performs confirmed file download with retained session cookies and 1MB buffer."""
    import urllib.request

    try:
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            content_disp = resp.headers.get("Content-Disposition", "")
            file_ext = _guess_extension(content_type, content_disp)
            file_name = _extract_filename(content_disp) or f"drive_{file_id}{file_ext}"
            dest_path = os.path.join(target_dir, file_name)

            total_size = int(resp.headers.get("Content-Length", 0) or 0)
            downloaded = 0
            buf_size = 1048576  # 1 MB buffer

            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(buf_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        try:
                            progress_callback(downloaded, total_size)
                        except Exception:
                            pass

            if os.path.getsize(dest_path) == 0:
                return None, "ERR_DRIVE_DOWNLOAD_FAILED"

            return dest_path, file_name
    except Exception as e:
        print(f"[DEBUG] Drive confirmed download failed: {e}")
        return None, "ERR_DRIVE_DOWNLOAD_FAILED"


def _guess_extension(content_type: str, content_disp: str) -> str:
    """Guess a sensible file extension from MIME type or Content-Disposition."""
    ct = content_type.lower().split(";")[0].strip()
    mime_map = {
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "video/x-matroska": ".mkv",
        "video/quicktime": ".mov",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
    }
    if ct in mime_map:
        return mime_map[ct]

    fname = _extract_filename(content_disp)
    if fname:
        ext = os.path.splitext(fname)[1]
        if ext:
            return ext

    return ".mp4"


def _extract_filename(content_disp: str) -> str:
    """Extract filename from Content-Disposition header."""
    if not content_disp:
        return ""
    match = re.search(r'filename[*]?=["\']?([^"\';\r\n]+)', content_disp)
    if match:
        return match.group(1).strip().strip('"\'')
    return ""


def transcribe_drive_video(
    url: str,
    language: Optional[str] = "vi",
    include_timestamps: bool = True,
    status_callback=None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Full pipeline: parse Drive URL → fast download audio → preprocess & transcribe with local Whisper.

    Args:
        url: Google Drive share URL.
        language: Language code ('vi', 'en', 'auto', or None for auto-detect).
        include_timestamps: Include [mm:ss] markers in output.
        status_callback: Optional callable(stage_name, *args) for UI progress updates.

    Returns:
        (success, markdown_content, error_code)
    """
    file_id = extract_drive_file_id(url)
    if not file_id:
        return False, "", "ERR_INVALID_DRIVE_URL"

    # Check local Whisper model
    from src.services.speech_service import get_best_installed_model, transcribe_drive_speech
    model_id = get_best_installed_model()
    if not model_id:
        return False, "", "ERR_NO_LOCAL_MODEL"

    temp_dir = tempfile.mkdtemp(prefix="docconvert_drive_")
    try:
        print(f"[DRIVE] Starting audio extraction for file_id={file_id}...")

        def _dl_progress(downloaded, total):
            if status_callback:
                try:
                    status_callback("download_progress", downloaded, total)
                except Exception:
                    pass

        local_path, file_name_or_err = download_drive_audio(
            file_id=file_id,
            target_dir=temp_dir,
            progress_callback=_dl_progress,
        )

        if local_path is None:
            return False, "", file_name_or_err

        # Transcribe with Audio Preprocessing + Whisper VAD
        file_title = os.path.splitext(file_name_or_err)[0] if file_name_or_err else ""
        success, md_content, err = transcribe_drive_speech(
            file_id=file_id,
            audio_path=local_path,
            file_name=file_title,
            language=language,
            include_timestamps=include_timestamps,
            status_callback=status_callback,
        )
        return success, md_content, err

    except Exception as e:
        return False, "", f"ERR_DRIVE_DOWNLOAD_FAILED: {str(e)}"
    finally:
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
