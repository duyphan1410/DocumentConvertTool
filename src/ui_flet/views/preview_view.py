"""
Markdown Preview View Component for Flet UI.
Uses Flet native ft.Markdown control, resolves @media/ image tokens
via MediaAssetManager, and embeds local images as base64 data URIs.
"""
import os
import re
import base64
import json
import shutil
import subprocess
import tempfile
import collections
import mimetypes
import time
import pathlib
from typing import Optional, Callable
import flet as ft
from src.i18n import t


import threading
from src.services.media_asset_manager import MediaAssetManager

MAX_BASE64_CACHE_ENTRIES = 128
_BASE64_CACHE: collections.OrderedDict[tuple[str, str, int, int], str] = collections.OrderedDict()
_BASE64_CACHE_LOCK = threading.Lock()
MAX_MERMAID_CACHE_SIZE = 128
_MERMAID_CACHE: collections.OrderedDict[tuple[str, bool], str] = collections.OrderedDict()
_MERMAID_CACHE_LOCK = threading.Lock()
_CLOUD_FETCH_SEMAPHORE = threading.Semaphore(3)


def encode_mermaid_payload(code: str, is_dark: bool = False, palette_name: str = "Violet Cyberpunk") -> str:
    """Encodes mermaid diagram text and unified palette theme config to base64 json format for mermaid.ink."""
    from src.ui_flet.theme import get_diagram_theme_variables
    theme_vars = get_diagram_theme_variables(palette_name=palette_name, is_dark=is_dark)
    payload = {
        "code": code,
        "mermaid": {
            "theme": "base",
            "themeVariables": theme_vars
        }
    }
    json_str = json.dumps(payload)
    return base64.b64encode(json_str.encode("utf-8")).decode("ascii")


def render_mermaid_diagram(code: str, is_dark: bool = False, palette_name: str = "Violet Cyberpunk", enable_cloud: bool = True) -> str:
    """
    Renders mermaid code into a markdown image tag.
    Tier 1: Local `mmdc` CLI if available -> base64 PNG data URI with unified diagram theme.
    Tier 2: Cloud `mermaid.ink` fetched to fast base64 PNG data URI (zero network latency in Flutter UI).
    Tier 3 / Fallback: Gracefully returns code block with syntax error message if invalid.
    """
    clean_code = code.strip()
    if not clean_code:
        return f"```mermaid\n{code}\n```"

    cache_key = (clean_code, is_dark, palette_name)
    with _MERMAID_CACHE_LOCK:
        if cache_key in _MERMAID_CACHE:
            _MERMAID_CACHE.move_to_end(cache_key)
            return _MERMAID_CACHE[cache_key]

    # Tier 1: Check for local mmdc (Mermaid CLI)
    mmdc_path = shutil.which("mmdc")
    if mmdc_path:
        try:
            from src.ui_flet.theme import get_diagram_theme_variables
            theme_vars = get_diagram_theme_variables(palette_name=palette_name, is_dark=is_dark)
            cfg_dict = {"theme": "base", "themeVariables": theme_vars}
            bg_color = theme_vars.get("background", "#181a22" if is_dark else "#ffffff")

            with tempfile.NamedTemporaryFile(suffix=".mmd", mode="w", encoding="utf-8", delete=False) as in_f, \
                 tempfile.NamedTemporaryFile(suffix=".json", mode="w", encoding="utf-8", delete=False) as cfg_f, \
                 tempfile.NamedTemporaryFile(suffix=".png", mode="r", encoding="utf-8", delete=False) as out_f:
                in_f.write(clean_code)
                cfg_f.write(json.dumps(cfg_dict))
                in_path = in_f.name
                cfg_path = cfg_f.name
                out_path = out_f.name

            cmd = [mmdc_path, "-i", in_path, "-o", out_path, "-c", cfg_path, "-b", bg_color]
            result = subprocess.run(cmd, capture_output=True, timeout=10)

            if result.returncode == 0 and os.path.exists(out_path):
                with open(out_path, "rb") as f:
                    png_bytes = f.read()
                png_b64 = base64.b64encode(png_bytes).decode("ascii")
                data_uri = f"data:image/png;base64,{png_b64}"
                md_img = f"![Mermaid Diagram]({data_uri})"

                for p in (in_path, cfg_path, out_path):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

                with _MERMAID_CACHE_LOCK:
                    if len(_MERMAID_CACHE) >= MAX_MERMAID_CACHE_SIZE:
                        _MERMAID_CACHE.popitem(last=False)
                    _MERMAID_CACHE[cache_key] = md_img
                return md_img
        except Exception as e:
            print(f"[DEBUG] Local mmdc render failed: {e}, falling back to cloud/code block...")

    # Tier 2: Cloud mermaid.ink endpoint
    if enable_cloud:
        import urllib.request
        import urllib.error
        from src.ui_flet.theme import get_diagram_theme_variables
        theme_vars = get_diagram_theme_variables(palette_name=palette_name, is_dark=is_dark)
        bg_hex = theme_vars.get("background", "181a22" if is_dark else "ffffff").lstrip("#")
        try:
            encoded_payload = encode_mermaid_payload(clean_code, is_dark=is_dark, palette_name=palette_name)
            img_url = f"https://mermaid.ink/img/{encoded_payload}?bgColor={bg_hex}"
            req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            
            with _CLOUD_FETCH_SEMAPHORE:
                with urllib.request.urlopen(req, timeout=5) as res:
                    if res.status == 200:
                        png_bytes = res.read()
                        png_b64 = base64.b64encode(png_bytes).decode("ascii")
                        data_uri = f"data:image/png;base64,{png_b64}"
                        md_img = f"![Mermaid Diagram]({data_uri})"

                        with _MERMAID_CACHE_LOCK:
                            if len(_MERMAID_CACHE) >= MAX_MERMAID_CACHE_SIZE:
                                _MERMAID_CACHE.popitem(last=False)
                            _MERMAID_CACHE[cache_key] = md_img
                        return md_img
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore").strip()
            is_html_or_server_err = (
                e.code in (429, 500, 502, 503, 504)
                or err_body.lower().startswith(("<html", "<!doctype", "error 5", "error 429"))
            )
            if is_html_or_server_err:
                # Server busy / rate-limited: fallback to direct URL without caching as syntax error
                encoded_payload = encode_mermaid_payload(clean_code, is_dark=is_dark, palette_name=palette_name)
                return f"![Mermaid Diagram](https://mermaid.ink/img/{encoded_payload}?bgColor={bg_hex})"

            # Genuine Syntax error from mermaid parser
            clean_err = re.sub(r'<[^>]+>', '', err_body).strip()
            first_err_line = clean_err.split("\n")[0] if clean_err else f"HTTP {e.code}"
            fallback_res = f"> ⚠️ **Mermaid Syntax Error**: `{first_err_line[:90]}`\n\n```mermaid\n{code}\n```"
            with _MERMAID_CACHE_LOCK:
                if len(_MERMAID_CACHE) >= MAX_MERMAID_CACHE_SIZE:
                    _MERMAID_CACHE.popitem(last=False)
                _MERMAID_CACHE[cache_key] = fallback_res
            return fallback_res
        except Exception as e:
            print(f"[DEBUG] Mermaid payload fetch failed: {e}")
            try:
                # Fallback to direct URL if network timeout on fetch
                encoded_payload = encode_mermaid_payload(clean_code, is_dark=is_dark, palette_name=palette_name)
                return f"![Mermaid Diagram](https://mermaid.ink/img/{encoded_payload}?bgColor={bg_hex})"
            except Exception:
                return f"```mermaid\n{code}\n```"

    # Tier 3: Fallback keep code block
    return f"```mermaid\n{code}\n```"


def process_markdown_mermaid(content: str, is_dark: bool = False, palette_name: str = "Violet Cyberpunk", enable_cloud: bool = True) -> str:
    """
    Intercepts ```mermaid ... ``` code blocks in markdown and renders them in parallel.
    Uses adaptive worker pool: up to 8 workers for local mmdc CLI, or 3-4 workers for cloud endpoint.
    Cloud requests are strictly throttled to 3 concurrent connections via _CLOUD_FETCH_SEMAPHORE.
    """
    if not content or "```mermaid" not in content.lower():
        return content

    mermaid_pattern = r"(?<!`)(?:`{3,4})mermaid[^\n]*\n([\s\S]*?)\n\s*(?:`{3,4})"
    matches = list(re.finditer(mermaid_pattern, content))
    if not matches:
        return content

    import concurrent.futures
    has_mmdc = shutil.which("mmdc") is not None
    max_workers = min(8, os.cpu_count() or 4) if has_mmdc else 3

    codes = [m.group(1) for m in matches]
    results = [None] * len(codes)

    def _worker(item):
        idx, code = item
        try:
            return idx, render_mermaid_diagram(code, is_dark=is_dark, palette_name=palette_name, enable_cloud=enable_cloud)
        except Exception as e:
            print(f"[DEBUG] Mermaid worker failed for diagram {idx}: {e}")
            return idx, f"```mermaid\n{code}\n```"

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for idx, rendered in executor.map(_worker, enumerate(codes)):
            results[idx] = rendered
    print(f"[DEBUG] Mermaid: rendered {len(codes)} diagram(s) in {time.time()-t0:.2f}s (workers={max_workers}, mmdc={has_mmdc})")

    result = content
    for m, rendered in zip(reversed(matches), reversed(results)):
        result = result[:m.start()] + rendered + result[m.end():]
    return result




def _resolve_session_id_from_path(file_path: str, session_id: Optional[str] = None) -> str:
    """
    Extracts session_id from explicit argument or auto-detects from file path
    containing MediaAssetManager.PREVIEW_MEDIA_DIR_NAME using OS-agnostic pathlib parts.
    """
    if session_id:
        return session_id
    try:
        parts = pathlib.Path(file_path).parts
        from src.services.media_asset_manager import PREVIEW_MEDIA_DIR_NAME
        if PREVIEW_MEDIA_DIR_NAME in parts:
            idx = parts.index(PREVIEW_MEDIA_DIR_NAME)
            if idx + 1 < len(parts):
                return parts[idx + 1]
    except Exception:
        pass
    return ""


def image_to_base64_uri(file_path: str, target_width: Optional[int] = None, max_width: int = 650, quality: int = 70, session_id: Optional[str] = None) -> str:
    """
    Converts a local image file path into an ultra-lightweight base64 data URI.
    Uses PIL to downscale according to max_width (or target_width alias) and compress to optimized JPEG/PNG,
    reducing multi-megabyte payloads by 96% so Flutter renders immediately without freezing.

    Cache Entry Lifecycle:
    - Entries with session_id != "" are evicted immediately when tab/session closes via purge_session_base64_cache().
    - Entries with session_id == "" (external images outside session) are bounded by MAX_BASE64_CACHE_ENTRIES LRU eviction.
    """
    limit_w = target_width if target_width is not None else max_width
    limit_w = max(50, min(1200, limit_w))
    sid = _resolve_session_id_from_path(file_path, session_id)
    cache_key = (sid, file_path, limit_w, quality)

    with _BASE64_CACHE_LOCK:
        if cache_key in _BASE64_CACHE:
            _BASE64_CACHE.move_to_end(cache_key)
            return _BASE64_CACHE[cache_key]

    try:
        from PIL import Image
        import io

        for attempt in range(3):
            try:
                with Image.open(file_path) as img:
                    orig_w, orig_h = img.size
                    if orig_w > limit_w or (target_width is not None and orig_w != limit_w):
                        new_h = max(1, int(orig_h * (limit_w / orig_w)))
                        img = img.resize((limit_w, new_h), Image.Resampling.LANCZOS)

                    buf = io.BytesIO()
                    has_alpha = False
                    if img.mode in ("RGBA", "LA"):
                        extrema = img.getextrema()
                        if len(extrema) >= 4 and extrema[3][0] < 255:
                            has_alpha = True
                    elif img.mode == "P" and "transparency" in img.info:
                        has_alpha = True

                    if has_alpha:
                        img.save(buf, format="PNG")
                        mime_type = "image/png"
                    else:
                        img = img.convert("RGB")
                        img.save(buf, format="JPEG", quality=quality)
                        mime_type = "image/jpeg"

                    raw_bytes = buf.getvalue()
                    encoded_data = base64.b64encode(raw_bytes).decode("ascii")
                    uri = f"data:{mime_type};base64,{encoded_data}"

                    with _BASE64_CACHE_LOCK:
                        _BASE64_CACHE[cache_key] = uri
                        _BASE64_CACHE.move_to_end(cache_key)
                        while len(_BASE64_CACHE) > MAX_BASE64_CACHE_ENTRIES:
                            _BASE64_CACHE.popitem(last=False)
                    return uri
            except (PermissionError, OSError):
                time.sleep(0.05)

        # Fallback to direct raw read if PIL fails
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "image/png"
        with open(file_path, "rb") as f:
            encoded_data = base64.b64encode(f.read()).decode("ascii")
        uri = f"data:{mime_type};base64,{encoded_data}"
        with _BASE64_CACHE_LOCK:
            _BASE64_CACHE[cache_key] = uri
            _BASE64_CACHE.move_to_end(cache_key)
            while len(_BASE64_CACHE) > MAX_BASE64_CACHE_ENTRIES:
                _BASE64_CACHE.popitem(last=False)
        return uri
    except Exception as e:
        print(f"[DEBUG] Failed to convert image '{file_path}' to base64: {e}")
        return file_path


def purge_session_base64_cache(session_id: str):
    """
    Purges all base64 cache entries matching the specified session_id exactly.
    Executes in a single atomic lock block to guarantee thread safety.
    """
    if not session_id:
        return
    with _BASE64_CACHE_LOCK:
        keys_to_delete = [k for k in _BASE64_CACHE if k[0] == session_id]
        for k in keys_to_delete:
            _BASE64_CACHE.pop(k, None)


def clear_base64_cache():
    """Clears all entries in the base64 cache. Primarily for testing and system resets."""
    with _BASE64_CACHE_LOCK:
        _BASE64_CACHE.clear()


# Module-level observer hook registration to avoid repeated registrations
MediaAssetManager.register_cleanup_hook(purge_session_base64_cache)


def clean_html_tags_for_preview(content: str) -> str:
    """
    Sanitizes raw HTML tags like <br> so Flet Markdown renders cleanly.
    - Code blocks (```): left 100% untouched.
    - Inside tables: replaces <br> with Unicode Line Separator (\u2028) to force visual
      line break in Flutter RichText rendering without breaking the Markdown table parser.
    - Outside tables: replaces <br> with standard newline (\n).
    """
    if not content or "<br" not in content.lower():
        return content
    lines = content.split("\n")
    cleaned_lines = []
    in_code_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            cleaned_lines.append(line)
            continue

        if in_code_block:
            cleaned_lines.append(line)
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            cleaned_line = re.sub(r'<br\s*/?>', '\u2028', line, flags=re.IGNORECASE)
            cleaned_lines.append(cleaned_line)
        else:
            cleaned_lines.append(re.sub(r'<br\s*/?>', '\n', line, flags=re.IGNORECASE))
    return "\n".join(cleaned_lines)


def process_markdown_timestamps(content: str) -> str:
    """
    Detects if Markdown contains YouTube video references and converts timestamp tokens
    like `**[01:23]**` or `[01:23]` into clickable interactive links `**[[⏱️ 01:23]](yt://VIDEO_ID?t=83)**`.
    """
    if not content:
        return ""

    vid_match = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/|yt://)([a-zA-Z0-9_-]{11})", content)
    if not vid_match:
        return content

    vid = vid_match.group(1)

    def parse_time_seconds(ts: str) -> int:
        parts = [int(p) for p in ts.split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return 0

    def repl_bold_ts(match):
        ts = match.group(1)
        sec = parse_time_seconds(ts)
        return f"**[[⏱️ {ts}]](yt://{vid}?t={sec})**"

    # Replace **[mm:ss]** or **[hh:mm:ss]** that are not already Markdown links
    content = re.sub(r"\*\*\[(\d{1,2}:\d{2}(?::\d{2})?)\]\*\*(?!\()", repl_bold_ts, content)
    return content


def format_preview_image_token(alt_text: str, uri: str, align: str = "", tok_start: int = -1, original_src: str = "", idx: int = -1) -> str:
    """Formats markdown image with optional alignment wrapper and interactive click link for rich preview rendering."""
    import urllib.parse
    click_src = original_src or uri
    encoded_src = urllib.parse.quote(click_src)
    action_url = f"imgaction://select?src={encoded_src}&idx={idx}&start={tok_start}"
    md_img = f"[![{alt_text}]({uri})]({action_url})"
    align_norm = (align or "").lower().strip()
    if align_norm in ("center", "right", "left"):
        return f'<p align="{align_norm}">{md_img}</p>'
    return md_img


def process_markdown_media(content: str, base_dir: str = None, is_dark: bool = False, palette_name: str = "Violet Cyberpunk", enable_cloud_mermaid: bool = True, session_id: str | None = None) -> str:
    """
    Parses Markdown content, intercepts Mermaid diagram blocks, resolves virtual URIs (such as @media/image.png)
    and local paths to fast base64 data URIs for Flet Markdown rendering.
    Also links interactive YouTube timestamps and converts custom-sized <img> tags to scaled Markdown images.
    """
    if not content:
        return ""

    content = clean_html_tags_for_preview(content)
    content = process_markdown_timestamps(content)
    content = process_markdown_mermaid(content, is_dark=is_dark, palette_name=palette_name, enable_cloud=enable_cloud_mermaid)
    t0 = time.time()
    asset_mgr = MediaAssetManager()
    from src.ui_flet.helpers.image_token_helper import find_all_image_tokens

    tokens = find_all_image_tokens(content)
    total_imgs = len(tokens)
    if total_imgs == 0:
        return content

    rendered_tokens = []

    for idx, tok in enumerate(tokens):
        uri = tok.src
        alt_text = tok.alt or "image"

        target_w = 650
        if tok.width:
            if tok.width.endswith("%"):
                try:
                    pct = float(tok.width.rstrip("%"))
                    target_w = int(650 * (pct / 100.0))
                except Exception:
                    target_w = 650
            else:
                try:
                    target_w = int(float(tok.width.rstrip("px")))
                except Exception:
                    target_w = 650
        target_w = max(50, min(1200, target_w))

        if uri.startswith(("http://", "https://", "data:")):
            img_rendered = format_preview_image_token(alt_text, uri, tok.align, tok_start=tok.start, original_src=tok.src, idx=idx)
            rendered_tokens.append(img_rendered)
            continue

        resolved_path = asset_mgr.resolve_uri(uri, base_dir=base_dir, session_id=session_id)
        if not os.path.exists(resolved_path) and base_dir:
            candidate = os.path.normpath(os.path.abspath(os.path.join(base_dir, uri)))
            if os.path.exists(candidate):
                resolved_path = candidate

        if os.path.exists(resolved_path):
            base64_uri = image_to_base64_uri(resolved_path, target_width=target_w, session_id=session_id)
            img_rendered = format_preview_image_token(alt_text, base64_uri, tok.align, tok_start=tok.start, original_src=tok.src, idx=idx)
            rendered_tokens.append(img_rendered)
        else:
            img_rendered = format_preview_image_token(alt_text, uri, tok.align, tok_start=tok.start, original_src=tok.src, idx=idx)
            rendered_tokens.append(img_rendered)

    # Apply replacements from end to start by slice to guarantee 0 collisions across multiple identical images
    result = content
    for idx in reversed(range(len(tokens))):
        tok = tokens[idx]
        rendered = rendered_tokens[idx]
        result = result[:tok.start] + rendered + result[tok.end:]

    t_elapsed = time.time() - t0
    print(f"[BENCHMARK] Processed {total_imgs} preview image links to Base64 in {t_elapsed:.3f}s")
    return result


async def process_markdown_media_async(content: str, base_dir: str = None, is_dark: bool = False, palette_name: str = "Violet Cyberpunk", enable_cloud_mermaid: bool = True, progress_callback=None, session_id: str | None = None) -> str:
    """
    Asynchronously parses Markdown content, intercepts Mermaid diagrams, and converts images to base64.
    Yields control back to the asyncio loop between images so Flet UI animations remain smooth.
    """
    if not content:
        return ""

    content = clean_html_tags_for_preview(content)
    content = process_markdown_timestamps(content)
    content = process_markdown_mermaid(content, is_dark=is_dark, palette_name=palette_name, enable_cloud=enable_cloud_mermaid)
    import asyncio
    t0 = time.time()
    asset_mgr = MediaAssetManager()
    from src.ui_flet.helpers.image_token_helper import find_all_image_tokens

    tokens = find_all_image_tokens(content)
    total_imgs = len(tokens)
    if total_imgs == 0:
        return content

    rendered_tokens = []

    for idx, tok in enumerate(tokens):
        uri = tok.src
        alt_text = tok.alt or "image"

        target_w = 650
        if tok.width:
            if tok.width.endswith("%"):
                try:
                    pct = float(tok.width.rstrip("%"))
                    target_w = int(650 * (pct / 100.0))
                except Exception:
                    target_w = 650
            else:
                try:
                    target_w = int(float(tok.width.rstrip("px")))
                except Exception:
                    target_w = 650
        target_w = max(50, min(1200, target_w))

        if uri.startswith(("http://", "https://", "data:")):
            img_rendered = format_preview_image_token(alt_text, uri, tok.align, tok_start=tok.start, original_src=tok.src, idx=idx)
            rendered_tokens.append(img_rendered)
            continue

        resolved_path = asset_mgr.resolve_uri(uri, base_dir=base_dir, session_id=session_id)
        if not os.path.exists(resolved_path) and base_dir:
            candidate = os.path.normpath(os.path.abspath(os.path.join(base_dir, uri)))
            if os.path.exists(candidate):
                resolved_path = candidate

        if os.path.exists(resolved_path):
            base64_uri = await asyncio.to_thread(image_to_base64_uri, resolved_path, target_w, 650, 70, session_id)
            img_rendered = format_preview_image_token(alt_text, base64_uri, tok.align, tok_start=tok.start, original_src=tok.src, idx=idx)
            rendered_tokens.append(img_rendered)
            if progress_callback:
                try:
                    progress_callback(idx + 1, total_imgs)
                except Exception:
                    pass
            await asyncio.sleep(0.005)
        else:
            img_rendered = format_preview_image_token(alt_text, uri, tok.align, tok_start=tok.start, original_src=tok.src, idx=idx)
            rendered_tokens.append(img_rendered)

    # Apply replacements from end to start by slice to guarantee 0 collisions across multiple identical images
    result = content
    for idx in reversed(range(len(tokens))):
        tok = tokens[idx]
        rendered = rendered_tokens[idx]
        result = result[:tok.start] + rendered + result[tok.end:]

    t_elapsed = time.time() - t0
    print(f"[BENCHMARK] Processed {total_imgs} preview image links to Base64 asynchronously in {t_elapsed:.3f}s")
    return result


class MarkdownPreview(ft.Container):
    def __init__(
        self,
        on_open_file: Optional[Callable[[str], None]] = None,
        get_workspace_path: Optional[Callable[[], str]] = None,
        on_image_link_clicked: Optional[Callable[[str], None]] = None,
        on_insert_sample_table: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.on_open_file = on_open_file
        self._get_workspace_path = get_workspace_path
        self.on_image_link_clicked = on_image_link_clicked
        self.on_insert_sample_table = on_insert_sample_table
        self.expand = True
        self.border_radius = 8
        self.padding = ft.Padding(left=8, top=4, right=8, bottom=6)
        self._last_raw_text = None
        self._cached_processed_text = None
        self._detected_video_id = None
        self._detected_video_title = None
        self._is_dark = False
        self._palette_name = "Violet Cyberpunk"
        self._base_dir = None
        self._session_id = None
        self._saved_scroll_offset: float = 0.0
        self._preview_mode: str = "document"  # "document" or "spreadsheet"
        self._last_rendered_mode: str = "document"



        # Header elements — owned by MarkdownPreview for palette sync
        self.header_icon = ft.Icon(ft.Icons.PREVIEW_ROUNDED, size=16)
        self.header_title = ft.Text(
            t("preview.title"),
            size=12,
            weight=ft.FontWeight.W_600,
        )
        self.btn_watch_video_text = ft.Text(
            t("preview.watch_video"),
            size=11,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.WHITE,
        )
        self.btn_watch_video = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=15, color=ft.Colors.WHITE),
                    self.btn_watch_video_text,
                ],
                spacing=3,
                tight=True,
            ),
            visible=False,
            tooltip=t("preview.watch_video_tooltip"),
            height=26,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.RED_700,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(left=8, top=0, right=10, bottom=0),
            ),
            on_click=self._on_watch_video_clicked,
        )
        self.doc_info_text = ft.Text(t("preview.no_doc"), size=11)

        self.header_row = ft.Row(
            controls=[
                self.header_icon,
                self.header_title,
                self.btn_watch_video,
                ft.Container(expand=True),
                self.doc_info_text,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        )

        self.markdown = ft.Markdown(
            value=t("preview.placeholder"),
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            code_theme=ft.MarkdownCodeTheme.ATOM_ONE_DARK,
            expand=True,
            soft_line_break=True,
            on_tap_link=self._on_markdown_link_clicked,
        )

        self.markdown_row = ft.Row(
            controls=[self.markdown],
            expand=True,
            scroll=None,
        )

        self.scroll_column = ft.Column(
            controls=[self.markdown_row],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            on_scroll=self._on_scroll_changed,
            key="markdown_preview_scroll_column",
        )

        self.content = ft.Column(
            controls=[
                self.header_row,
                ft.Divider(height=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
                self.scroll_column,
            ],
            expand=True,
            spacing=4,
        )

    def _on_markdown_link_clicked(self, e):
        """Handles link clicks in MarkdownPreview. Interactive YouTube timestamps jump video position."""
        url = getattr(e, "data", "") or ""
        if not url:
            return

        if url.startswith("imgaction://"):
            if hasattr(self, "on_image_link_clicked") and self.on_image_link_clicked:
                try:
                    self.on_image_link_clicked(url)
                except Exception as ex:
                    print(f"[DEBUG] on_image_link_clicked error: {ex}")
            return

        from src.services.youtube_service import extract_video_id
        from src.services.youtube_player import YouTubePlayerManager

        vid = None
        start_sec = 0

        if url.startswith("yt://"):
            parsed = url[5:]
            if "?" in parsed:
                part_id, query = parsed.split("?", 1)
                vid = part_id.strip() if part_id and part_id != "seek" else None
                for param in query.split("&"):
                    if param.startswith("v=") and not vid:
                        vid = param[2:]
                    elif param.startswith("t="):
                        try:
                            start_sec = int(param[2:].rstrip("s"))
                        except ValueError:
                            start_sec = 0
            else:
                vid = parsed
        elif "youtube.com" in url or "youtu.be" in url:
            vid = extract_video_id(url)
            m = re.search(r"[?&]t=(\d+)", url)
            if m:
                try:
                    start_sec = int(m.group(1))
                except ValueError:
                    start_sec = 0

        if vid:
            title = self._detected_video_title or f"YouTube Video ({vid})"
            YouTubePlayerManager.get_instance().play(vid, start_seconds=start_sec, title=title)
            return

        # Check if url points to a local document file in current folder / workspace
        if not url.startswith(("http://", "https://", "mailto:", "ftp://")):
            clean_url = url.split("?")[0].split("#")[0].replace("%20", " ").strip()
            candidate = None
            if os.path.isabs(clean_url) and os.path.exists(clean_url):
                candidate = os.path.normpath(clean_url)
            else:
                # 1. Try relative to active file directory
                if self._base_dir:
                    cand = os.path.normpath(os.path.abspath(os.path.join(self._base_dir, clean_url)))
                    if os.path.exists(cand):
                        candidate = cand

                # 2. Try relative to open workspace directory (e.g. for Untitled notes)
                if not candidate and hasattr(self, "_get_workspace_path") and self._get_workspace_path:
                    ws_dir = self._get_workspace_path()
                    if ws_dir:
                        cand = os.path.normpath(os.path.abspath(os.path.join(ws_dir, clean_url)))
                        if os.path.exists(cand):
                            candidate = cand

            if candidate and os.path.isfile(candidate):
                doc_exts = {
                    ".md", ".docx", ".xlsx", ".xls", ".csv", ".pdf",
                    ".html", ".htm", ".pptx", ".json", ".yaml", ".yml"
                }
                ext = os.path.splitext(candidate)[1].lower()
                if ext in doc_exts and hasattr(self, "on_open_file") and self.on_open_file:
                    self.on_open_file(candidate)
                    return
                else:
                    try:
                        os.startfile(candidate)
                        return
                    except Exception:
                        pass

        # Non-YouTube and non-local document link: launch in system browser / default OS app
        try:
            import webbrowser
            if url.startswith(("http://", "https://", "mailto:", "ftp://")):
                webbrowser.open(url)
            elif candidate and os.path.exists(candidate):
                os.startfile(candidate)
        except Exception as ex:
            print(f"[DEBUG] Failed to launch URL '{url}': {ex}")

    def set_workspace_provider(self, get_workspace_path: Optional[Callable[[], str]] = None):
        """Sets callback to dynamically get active workspace directory for link resolution."""
        self._get_workspace_path = get_workspace_path

    def _on_scroll_changed(self, e):
        """Tracks the current scroll offset of the preview column, guarding against spurious layout resets."""
        try:
            px = float(getattr(e, "pixels", 0) or 0)
            ev_type = getattr(e, "event_type", None)
            is_restoring = getattr(self, "_is_restoring_scroll", False)
            if px == 0:
                print(f"[DEBUG][SCROLL_EVENT_ZERO] pixels={px}, type={ev_type}, restoring={is_restoring}, saved={getattr(self, '_saved_scroll_offset', 0.0)}")
            elif px > 0 and not is_restoring:
                self._saved_scroll_offset = px
        except Exception:
            pass

    def save_scroll(self):
        """Snapshot current scroll position for later restoration."""
        pass

    def restore_scroll(self, target_offset: Optional[float] = None, target_image_idx: Optional[int] = None):
        """Restores the preview scroll to the exact last known pixel offset after content changes."""
        try:
            offset = target_offset if target_offset is not None else getattr(self, "_saved_scroll_offset", 0.0)
            img_idx = target_image_idx if target_image_idx is not None else getattr(self, "_last_active_image_idx", None)
            if offset <= 0 and img_idx is None:
                return

            if not hasattr(self.scroll_column, "scroll_to"):
                return

            page = getattr(self.scroll_column, "page", None) or getattr(self.markdown, "page", None)
            if not page:
                return

            import asyncio
            import inspect

            self._is_restoring_scroll = True
            if offset > 0:
                self._saved_scroll_offset = offset

            async def _async_restore():
                try:
                    await asyncio.sleep(0.04)
                    if offset > 0:
                        res = self.scroll_column.scroll_to(offset=offset, duration=0)
                    elif img_idx is not None:
                        res = self.scroll_column.scroll_to(scroll_key=f"preview_img_{img_idx}", duration=0)
                    else:
                        res = None
                    if inspect.iscoroutine(res):
                        await res

                    # Second safety frame to guarantee position after Flutter layout settles
                    await asyncio.sleep(0.05)
                    if offset > 0:
                        res2 = self.scroll_column.scroll_to(offset=offset, duration=0)
                    elif img_idx is not None:
                        res2 = self.scroll_column.scroll_to(scroll_key=f"preview_img_{img_idx}", duration=0)
                    else:
                        res2 = None
                    if inspect.iscoroutine(res2):
                        await res2
                except asyncio.CancelledError:
                    pass
                except Exception as ex:
                    print(f"[DEBUG][PREVIEW_RESTORE] error: {ex}")
                finally:
                    await asyncio.sleep(0.05)
                    self._is_restoring_scroll = False

            if hasattr(page, "run_task"):
                self._active_restore_task = page.run_task(_async_restore)
            else:
                loop = getattr(page, "loop", None)
                if loop:
                    self._active_restore_task = asyncio.run_coroutine_threadsafe(_async_restore(), loop)
        except Exception as ex:
            print(f"[DEBUG][PREVIEW_RESTORE] error: {ex}")
            self._is_restoring_scroll = False

    def _on_watch_video_clicked(self, e):
        """Launches the in-app player for the detected YouTube video in the current document."""
        if self._detected_video_id:
            from src.services.youtube_player import YouTubePlayerManager
            title = self._detected_video_title or f"YouTube Video ({self._detected_video_id})"
            YouTubePlayerManager.get_instance().play(
                self._detected_video_id,
                start_seconds=0,
                title=title,
            )

    def show_loading(self, message: str = None):
        """Displays subtle header loading status in MarkdownPreview."""
        self.doc_info_text.value = f"⏳ {t('preview.loading_text')}"
        try:
            if self.doc_info_text.page:
                self.doc_info_text.update()
        except Exception:
            pass

    def hide_loading(self):
        """No-op helper for compatibility."""
        pass

    def set_word_wrap(self, enabled: bool):
        """Toggles soft line breaks in MarkdownPreview cleanly."""
        self.markdown.soft_line_break = enabled
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def set_font_size(self, size: int):
        """Dynamically update font size scale of MarkdownPreview stylesheet."""
        s = float(size)
        self.markdown.md_style_sheet = ft.MarkdownStyleSheet(
            p_text_style=ft.TextStyle(size=s),
            h1_text_style=ft.TextStyle(size=s * 1.8, weight=ft.FontWeight.BOLD),
            h2_text_style=ft.TextStyle(size=s * 1.5, weight=ft.FontWeight.BOLD),
            h3_text_style=ft.TextStyle(size=s * 1.3, weight=ft.FontWeight.BOLD),
            h4_text_style=ft.TextStyle(size=s * 1.1, weight=ft.FontWeight.BOLD),
            code_text_style=ft.TextStyle(size=s * 0.95, font_family="Consolas"),
            blockquote_text_style=ft.TextStyle(size=s, italic=True),
        )
        try:
            if self.markdown.page:
                self.markdown.update()
        except Exception:
            pass

    def detect_youtube_video(self, markdown_text: str):
        """Scans document text for YouTube video references and toggles Watch Video button visibility."""
        if not markdown_text or not markdown_text.strip():
            self._detected_video_id = None
            self._detected_video_title = None
            self.btn_watch_video.visible = False
            return

        vid_match = re.search(
            r"(?:youtube\.com/watch\?v=|youtu\.be/|yt://)([a-zA-Z0-9_-]{11})", markdown_text
        )
        if vid_match:
            self._detected_video_id = vid_match.group(1)
            t_match = re.search(r"^#\s+(.+)$", markdown_text, re.MULTILINE)
            self._detected_video_title = t_match.group(1).strip() if t_match else ""
            self.btn_watch_video.visible = True
        else:
            self._detected_video_id = None
            self._detected_video_title = None
            self.btn_watch_video.visible = False

    def _trigger_fake_link_click(self, url: str):
        """Dispatches link click event for interactive image click in live preview."""
        class FakeEvent:
            def __init__(self, data):
                self.data = data
        self._on_markdown_link_clicked(FakeEvent(url))

    def _save_tap_position(self, e, action_url: str):
        """Records tap coordinates on pointer down without premature gesture termination."""
        if "idx=" in action_url:
            try:
                import urllib.parse
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(action_url).query)
                idx_v = qs.get("idx", [-1])[0]
                if int(idx_v) >= 0:
                    self._last_active_image_idx = int(idx_v)
            except Exception:
                pass

        gx = None
        gy = None
        if hasattr(e, "global_position") and e.global_position:
            gx = getattr(e.global_position, "x", None) or getattr(e.global_position, "dx", None)
            gy = getattr(e.global_position, "y", None) or getattr(e.global_position, "dy", None)
        if gx is None and hasattr(e, "global_x"):
            gx = getattr(e, "global_x", None)
            gy = getattr(e, "global_y", None)
        self._last_tap_pos = (gx, gy)

    def _handle_image_tap(self, e, action_url: str):
        """Extracts tap coordinates on clean release and triggers context menu."""
        gx, gy = getattr(self, "_last_tap_pos", (None, None))
        if gx is None and hasattr(e, "global_position") and e.global_position:
            gx = getattr(e.global_position, "x", None) or getattr(e.global_position, "dx", None)
            gy = getattr(e.global_position, "y", None) or getattr(e.global_position, "dy", None)

        saved = getattr(self, "_saved_scroll_offset", 0.0)
        print(f"[DEBUG][IMAGE_CLICK] action_url={action_url}, click_pos=({gx}, {gy}), current_saved_offset={saved:.1f}")

        url_with_pos = action_url
        if gx is not None and gy is not None:
            url_with_pos += f"&click_x={int(gx)}&click_y={int(gy)}"
        self._trigger_fake_link_click(url_with_pos)

    def _render_processed_content(self, processed_md: str):
        """Renders processed markdown, decomposing aligned images into native Flet Rows for pixel-perfect centering without tables or borders."""
        if not processed_md or not processed_md.strip():
            self.markdown.value = "*No content to preview.*"
            self.scroll_column.controls = [self.markdown_row]
            return

        # Pattern matching preview image tokens formatted with optional alignment
        img_block_pattern = re.compile(
            r'(?:<p\s+align=["\'](center|right|left)["\']>\s*)?'
            r'(\[?!\[([^\]]*)\]\(((?:\\\(|\\\)|[^\(\)\s]|\((?:\\\(|\\\)|[^\(\)\s])*\))+)\)(?:\]\((imgaction://[^\)]+)\))?)'
            r'(?:\s*</p>)?',
            re.IGNORECASE
        )

        matches = list(img_block_pattern.finditer(processed_md))
        if not matches:
            self.markdown.value = processed_md
            self.scroll_column.controls = [self.markdown_row]
            return False

        # Build parsed item descriptors: ("text", content) or ("img", idx, align, src, alt, action_url)
        items = []
        last_end = 0

        for img_idx, m in enumerate(matches):
            align = (m.group(1) or "").lower().strip()
            alt = m.group(3) or "image"
            src = m.group(4) or ""
            action_url = m.group(5) or ""

            # Text chunk before this image
            if m.start() > last_end:
                text_chunk = processed_md[last_end:m.start()].strip()
                if text_chunk:
                    items.append(("text", text_chunk))

            # Determine row alignment
            if align == "center":
                main_align = ft.MainAxisAlignment.CENTER
            elif align == "right":
                main_align = ft.MainAxisAlignment.END
            else:
                main_align = ft.MainAxisAlignment.START

            items.append(("img", img_idx, main_align, src, alt, action_url))
            last_end = m.end()

        # Remaining trailing text chunk
        if last_end < len(processed_md):
            text_chunk = processed_md[last_end:].strip()
            if text_chunk:
                items.append(("text", text_chunk))

        # Check if smooth in-place update can be performed to avoid full widget tree recreation and visual flicker
        existing_controls = self.scroll_column.controls or []
        can_in_place = (len(existing_controls) == len(items) and len(items) > 0)
        reason = ""
        if can_in_place:
            for idx_c, (ctrl, item) in enumerate(zip(existing_controls, items)):
                if item[0] == "text" and not isinstance(ctrl, ft.Markdown):
                    can_in_place = False
                    reason = f"item[{idx_c}] is text but ctrl is {type(ctrl).__name__}"
                    break
                elif item[0] == "img" and not isinstance(ctrl, ft.Row):
                    can_in_place = False
                    reason = f"item[{idx_c}] is img but ctrl is {type(ctrl).__name__}"
                    break
        else:
            reason = f"len(existing)={len(existing_controls)} != len(items)={len(items)}"

        print(f"[DEBUG][CAN_IN_PLACE] can_in_place={can_in_place}, reason={reason}")

        if can_in_place:
            changed_controls = []
            for ctrl, item in zip(existing_controls, items):
                if item[0] == "text":
                    if ctrl.value != item[1]:
                        ctrl.value = item[1]
                        changed_controls.append(ctrl)
                elif item[0] == "img":
                    img_idx, main_align, src, alt, action_url = item[1], item[2], item[3], item[4], item[5]
                    if ctrl.alignment != main_align:
                        ctrl.alignment = main_align
                        changed_controls.append(ctrl)
                    if ctrl.controls and isinstance(ctrl.controls[0], ft.Container):
                        container = ctrl.controls[0]
                        container.tooltip = f"{alt} (Nhấn để chỉnh sửa)" if action_url else alt
                        img_ctrl = None
                        if isinstance(container.content, ft.GestureDetector):
                            img_ctrl = container.content.content
                            if action_url and getattr(container.content, "data", "") != action_url:
                                container.content.data = action_url
                        elif isinstance(container.content, ft.Image):
                            img_ctrl = container.content

                        if isinstance(img_ctrl, ft.Image):
                            if img_ctrl.src != src:
                                img_ctrl.src = src
                                if ctrl not in changed_controls:
                                    changed_controls.append(ctrl)
            for c in changed_controls:
                try:
                    if hasattr(c, "page") and c.page:
                        c.update()
                except Exception:
                    pass
            return True

        # Fallback: construct new controls tree
        new_controls = []
        for idx_item, item in enumerate(items):
            if item[0] == "text":
                new_controls.append(ft.Markdown(
                    value=item[1],
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    code_theme=self.markdown.code_theme,
                    md_style_sheet=self.markdown.md_style_sheet,
                    soft_line_break=True,
                    on_tap_link=self._on_markdown_link_clicked,
                    key=f"preview_text_{idx_item}",
                ))
            elif item[0] == "img":
                img_idx, main_align, src, alt, action_url = item[1], item[2], item[3], item[4], item[5]
                img_ctrl = ft.Image(
                    src=src,
                    fit=ft.BoxFit.CONTAIN,
                    border_radius=4,
                )
                if action_url:
                    target_url = action_url
                    gd = ft.GestureDetector(
                        content=img_ctrl,
                        data=target_url,
                        mouse_cursor=ft.MouseCursor.CLICK,
                        on_tap_down=lambda e, u=target_url: self._save_tap_position(e, getattr(e.control, "data", "") or u),
                        on_tap=lambda e, u=target_url: self._handle_image_tap(e, getattr(e.control, "data", "") or u),
                    )
                    img_container = ft.Container(
                        content=gd,
                        key=f"preview_img_{img_idx}",
                        border_radius=4,
                        tooltip=f"{alt} (Nhấn để chỉnh sửa)",
                        padding=ft.Padding(0, 4, 0, 4),
                    )
                else:
                    img_container = ft.Container(
                        content=img_ctrl,
                        key=f"preview_img_{img_idx}",
                        border_radius=4,
                        tooltip=alt,
                        padding=ft.Padding(0, 4, 0, 4),
                    )
                new_controls.append(ft.Row([img_container], key=f"preview_row_{img_idx}", alignment=main_align))

        self.scroll_column.controls = new_controls if new_controls else [self.markdown_row]
        return False

    def scroll_to_image(self, idx: int = 0):
        """Smoothly scrolls the preview pane to the specified image index."""
        try:
            if hasattr(self.scroll_column, "scroll_to"):
                res = self.scroll_column.scroll_to(
                    scroll_key=f"preview_img_{idx}",
                    duration=250,
                    curve=ft.AnimationCurve.EASE_OUT,
                )
                import asyncio
                import inspect
                if inspect.iscoroutine(res):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        pass
        except Exception as ex:
            print(f"[DEBUG] scroll_to_image error: {ex}")

    def set_preview_mode(self, mode: str):
        """Switches between 'document' (standard live markdown) and 'spreadsheet' (excel/csv grid view)."""
        if mode not in ("document", "spreadsheet"):
            mode = "document"
        if getattr(self, "_preview_mode", "document") != mode:
            self._preview_mode = mode
            if mode == "spreadsheet":
                self.header_icon.name = ft.Icons.TABLE_CHART_ROUNDED
                self.header_title.value = t("preview.spreadsheet_title") if t("preview.spreadsheet_title") != "preview.spreadsheet_title" else "BẢNG TÍNH EXCEL / CSV (PREVIEW)"
                self.btn_watch_video.visible = False
            else:
                self.header_icon.name = ft.Icons.PREVIEW_ROUNDED
                self.header_title.value = t("preview.title")

            raw = self._last_raw_text or ""
            self._last_raw_text = None
            self._cached_processed_text = None
            self.set_content(raw, base_dir=self._base_dir, session_id=self._session_id)

    def _handle_insert_sample_table_click(self, e):
        """Dispatches sample table insertion to the editor."""
        if self.on_insert_sample_table:
            self.on_insert_sample_table()

    def _render_spreadsheet_content(self, markdown_text: str):
        """Renders the exact simulated Excel workbook/sheet layout that ExcelModule produces."""
        import re
        from src.ui_flet.theme import get_style_color, resolve_color, PALETTES, make_border

        palette = PALETTES.get(self._palette_name, PALETTES["Violet Cyberpunk"])
        accent_primary = resolve_color(palette, "text_accent_primary", self._is_dark)
        bg_card = resolve_color(palette, "bg_component", self._is_dark)
        border_color = resolve_color(palette, "border_color", self._is_dark)
        text_primary = get_style_color("text_primary", self._is_dark)
        text_secondary = get_style_color("text_secondary", self._is_dark)
        header_bg = "#1e293b" if self._is_dark else "#f1f5f9"
        table_header_bg = "#2563eb" if self._is_dark else "#3b82f6"

        def _clean_inline(text: str) -> str:
            # Clean HTML image tags
            text = re.sub(r'<p[^>]*?>\s*<img[^>]*?alt=["\']([^"\']*)["\'][^>]*?>\s*</p>', r'📷 [\1]', text, flags=re.IGNORECASE)
            text = re.sub(r'<img[^>]*?alt=["\']([^"\']*)["\'][^>]*?>', r'📷 [\1]', text, flags=re.IGNORECASE)
            text = re.sub(r'<img[^>]*?>', r'📷 [Image]', text, flags=re.IGNORECASE)
            text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'📷 [\1]', text)
            # Clean links [text](url) -> text
            text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
            # Clean bold/italic/strike/code
            text = re.sub(r'[*_~`]', '', text)
            return text.strip()

        # Parse lines into Excel grid rows
        lines = markdown_text.splitlines() if markdown_text else []
        sheet_rows = []
        max_cols = 1
        in_table = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                in_table = False
                sheet_rows.append({"type": "empty", "cells": [""]})
                continue

            # Check for table separator line (|---|---|)
            if "|" in stripped and re.match(r"^[\|\s\-:]+$", stripped):
                in_table = True
                continue

            # Check if table row
            if "|" in stripped:
                inner_line = stripped
                if inner_line.startswith("|"):
                    inner_line = inner_line[1:]
                if inner_line.endswith("|"):
                    inner_line = inner_line[:-1]
                raw_cells = [c.strip() for c in inner_line.split("|")]
                cells = [_clean_inline(c) for c in raw_cells]
                is_header = not in_table
                in_table = True
                max_cols = max(max_cols, len(cells))
                sheet_rows.append({
                    "type": "table_header" if is_header else "table_data",
                    "cells": cells,
                })
            else:
                in_table = False
                match_heading = re.match(r"^(#{1,6})\s+(.*)", stripped)
                if match_heading:
                    level = len(match_heading.group(1))
                    h_text = _clean_inline(match_heading.group(2))
                    sheet_rows.append({
                        "type": "heading",
                        "level": level,
                        "cells": [h_text],
                    })
                else:
                    c_text = _clean_inline(stripped)
                    sheet_rows.append({
                        "type": "text",
                        "cells": [c_text],
                    })

        # Remove trailing empty rows
        while sheet_rows and sheet_rows[-1]["type"] == "empty":
            sheet_rows.pop()

        total_rows = len(sheet_rows)
        self.doc_info_text.value = f"Excel Sheet | {total_rows} Dòng × {max_cols} Cột"

        # Build Column Headers: [#] [A] [B] [C] ...
        cols = [
            ft.DataColumn(ft.Text("#", size=11, weight=ft.FontWeight.BOLD, color=text_secondary))
        ]
        for c_idx in range(max_cols):
            col_letter = chr(65 + c_idx) if c_idx < 26 else f"C{c_idx+1}"
            cols.append(
                ft.DataColumn(
                    ft.Container(
                        content=ft.Text(col_letter, size=11, weight=ft.FontWeight.BOLD, color=accent_primary),
                        alignment=ft.alignment.Alignment(0.0, 0.0),
                        padding=ft.Padding(0, 2, 0, 2),
                    )
                )
            )

        # Build Data Rows
        d_rows = []
        for r_idx, row_info in enumerate(sheet_rows, start=1):
            r_type = row_info["type"]
            cells_data = row_info["cells"]

            row_cells = [
                ft.DataCell(
                    ft.Container(
                        content=ft.Text(str(r_idx), size=11, color=text_secondary, weight=ft.FontWeight.W_500),
                        alignment=ft.alignment.Alignment(0.0, 0.0),
                    )
                )
            ]

            # Pad cells to max_cols
            padded_cells = cells_data + [""] * (max_cols - len(cells_data))

            for c_idx, val in enumerate(padded_cells):
                if r_type == "table_header":
                    cell_ctrl = ft.Container(
                        content=ft.Text(val, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        bgcolor=table_header_bg,
                        padding=ft.Padding(6, 4, 6, 4),
                        border_radius=3,
                        alignment=ft.alignment.Alignment(-1.0, 0.0),
                    )
                elif r_type == "heading":
                    h_size = 13 if row_info.get("level", 1) <= 2 else 12
                    cell_ctrl = ft.Text(val, size=h_size, weight=ft.FontWeight.BOLD, color=accent_primary, selectable=True)
                elif r_type == "empty":
                    cell_ctrl = ft.Text("", size=11)
                else:
                    is_img = val.startswith("📷")
                    cell_color = accent_primary if is_img else text_primary
                    cell_ctrl = ft.Text(val, size=12, color=cell_color, selectable=True)

                row_cells.append(ft.DataCell(cell_ctrl))

            d_rows.append(ft.DataRow(cells=row_cells))

        dt = ft.DataTable(
            columns=cols,
            rows=d_rows if d_rows else [
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text("1", size=11, color=text_secondary)),
                    ft.DataCell(ft.Text("(Trống / Empty)", size=11, color=text_secondary)),
                ])
            ],
            border=make_border(1, border_color),
            border_radius=6,
            heading_row_color=header_bg,
            heading_row_height=34,
            data_row_min_height=26,
            data_row_max_height=44,
            column_spacing=18,
            divider_thickness=1,
        )

        # Get sheet title from first heading or default
        doc_title = "Sheet1"
        if markdown_text:
            first_h = re.search(r"^#+\s+(.*)", markdown_text, re.MULTILINE)
            if first_h:
                doc_title = _clean_inline(first_h.group(1))[:25]

        sheet_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.TABLE_CHART_ROUNDED, size=16, color=accent_primary),
                            ft.Text(f"Sheet: {doc_title}", size=13, weight=ft.FontWeight.BOLD, color=text_primary),
                            ft.Container(
                                content=ft.Text(f"{max_cols} Cột × {total_rows} Dòng", size=10, color=accent_primary, weight=ft.FontWeight.W_600),
                                padding=ft.Padding(6, 2, 6, 2),
                                border_radius=4,
                                bgcolor=header_bg,
                                border=make_border(1, border_color),
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[dt],
                            scroll=ft.ScrollMode.ADAPTIVE,
                        ),
                        border_radius=6,
                    ),
                ],
                spacing=8,
            ),
            padding=10,
            border=make_border(1, border_color),
            border_radius=8,
            bgcolor=bg_card,
        )

        self.scroll_column.controls = [sheet_card]

    def set_content(self, markdown_text: str, base_dir: str = None, session_id: str | None = None):
        """Updates preview with processed markdown or spreadsheet grid, using cache if text hasn't changed."""
        self._base_dir = base_dir
        self._session_id = session_id
        if not markdown_text or not markdown_text.strip():
            if self._last_raw_text != "":
                self.markdown.value = "*No content to preview.*"
                self.scroll_column.controls = [self.markdown_row]
                self.markdown_text = ""
                self._last_raw_text = ""
                self._cached_processed_text = "*No content to preview.*"
                self.doc_info_text.value = t("preview.no_doc")
                self.detect_youtube_video("")
                try:
                    if hasattr(self.scroll_column, "page") and self.scroll_column.page:
                        self.scroll_column.update()
                except Exception:
                    pass
            return

        # Cache Guard: If text is unchanged and mode is unchanged, do not rebuild controls
        if markdown_text == self._last_raw_text and self._cached_processed_text and getattr(self, "_last_rendered_mode", "document") == self._preview_mode:
            return

        curr_offset = getattr(self, "_saved_scroll_offset", 0.0)
        self._last_raw_text = markdown_text
        self._last_rendered_mode = self._preview_mode

        is_in_place = False
        if getattr(self, "_preview_mode", "document") == "spreadsheet":
            self._render_spreadsheet_content(markdown_text)
        else:
            self._cached_processed_text = process_markdown_media(
                markdown_text, base_dir=base_dir, is_dark=self._is_dark, palette_name=self._palette_name, session_id=session_id
            )
            self.detect_youtube_video(markdown_text)
            is_in_place = self._render_processed_content(self._cached_processed_text)

        if not is_in_place:
            try:
                if hasattr(self.scroll_column, "page") and self.scroll_column.page:
                    self.scroll_column.update()
            except Exception:
                pass

        if curr_offset > 0 or getattr(self, "_last_active_image_idx", None) is not None:
            self.restore_scroll(target_offset=curr_offset)

    def set_processed_content(self, processed_md: str, raw_text: str, base_dir: str = None, session_id: str | None = None):
        """Sets pre-computed processed markdown directly in 0ms without re-parsing images or re-encoding Base64."""
        self._base_dir = base_dir
        self._session_id = session_id
        if getattr(self, "_preview_mode", "document") == "spreadsheet":
            self.set_content(raw_text, base_dir=base_dir, session_id=session_id)
            return

        if raw_text == self._last_raw_text and processed_md == self._cached_processed_text:
            return
        curr_offset = getattr(self, "_saved_scroll_offset", 0.0)
        self._last_raw_text = raw_text
        self._cached_processed_text = processed_md
        self._last_rendered_mode = "document"
        is_in_place = self._render_processed_content(processed_md)
        if hasattr(self, "detect_youtube_video"):
            self.detect_youtube_video(raw_text)

        if not is_in_place:
            try:
                if hasattr(self.scroll_column, "page") and self.scroll_column.page:
                    self.scroll_column.update()
            except Exception:
                pass

        if curr_offset > 0 or getattr(self, "_last_active_image_idx", None) is not None:
            self.restore_scroll(target_offset=curr_offset)

    def update_preview(self, markdown_text: str, base_dir: str = None, session_id: str | None = None):
        """Alias method for update_preview compatibility."""
        self.set_content(markdown_text, base_dir=base_dir, session_id=session_id)

    def apply_palette(self, palette: dict, is_dark: bool, palette_name: str = ""):
        """Apply palette accent colors to preview header, button, code themes, and diagram standard."""
        palette_name = palette_name or self._palette_name or "Violet Cyberpunk"
        theme_changed = (self._is_dark != is_dark) or (self._palette_name != palette_name)
        self._is_dark = is_dark
        self._palette_name = palette_name

        if theme_changed and self._last_raw_text and "```mermaid" in self._last_raw_text.lower():
            # Run Mermaid diagram re-rendering asynchronously in background thread so UI never freezes
            raw_text = self._last_raw_text
            base_dir = self._base_dir
            cur_session_id = self._session_id
            cur_dark = self._is_dark
            cur_palette = self._palette_name

            def _bg_rerender():
                try:
                    processed = process_markdown_media(
                        raw_text, base_dir=base_dir, is_dark=cur_dark, palette_name=cur_palette, session_id=cur_session_id
                    )
                    # Only apply if user hasn't switched theme again in the meantime
                    if self._is_dark == cur_dark and self._palette_name == cur_palette:
                        self._cached_processed_text = processed
                        self._render_processed_content(processed)
                        try:
                            if hasattr(self.scroll_column, "page") and self.scroll_column.page:
                                self.scroll_column.update()
                        except Exception:
                            pass
                except Exception as ex:
                    print(f"[DEBUG] Background mermaid re-render failed: {ex}")

            threading.Thread(target=_bg_rerender, daemon=True).start()

        from src.ui_flet.theme import resolve_color, get_style_color
        accent_primary = resolve_color(palette, "text_accent_primary", is_dark)
        border_color = resolve_color(palette, "border_color", is_dark)
        text_primary = get_style_color("text_primary", is_dark)
        bg_code = resolve_color(palette, "bg_component", is_dark)
        bg_quote = resolve_color(palette, "bg_header", is_dark)

        self.header_icon.color = accent_primary
        self.header_title.color = accent_primary
        self.btn_watch_video.style = ft.ButtonStyle(
            bgcolor=accent_primary,
            shape=ft.RoundedRectangleBorder(radius=6),
            padding=ft.Padding(left=8, top=0, right=10, bottom=0),
        )

        code_text_color = "#ff79c6" if is_dark else "#c026d3"

        # Dynamic Code Theme (Dark / Light)
        self.markdown.code_theme = (
            ft.MarkdownCodeTheme.ATOM_ONE_DARK if is_dark else ft.MarkdownCodeTheme.ATOM_ONE_LIGHT
        )

        # Dynamic Markdown Style Sheet (Headings, Code, CodeBlock, Checkbox, Table & Blockquote)
        self.markdown.md_style_sheet = ft.MarkdownStyleSheet(
            h1_text_style=ft.TextStyle(size=28, weight=ft.FontWeight.BOLD, color=text_primary),
            h2_text_style=ft.TextStyle(size=22, weight=ft.FontWeight.BOLD, color=text_primary),
            h3_text_style=ft.TextStyle(size=18, weight=ft.FontWeight.W_600, color=text_primary),
            h4_text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600, color=text_primary),
            h5_text_style=ft.TextStyle(size=14, weight=ft.FontWeight.W_500, color=text_primary),
            h6_text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_500, color=text_primary),
            p_text_style=ft.TextStyle(color=text_primary, size=14, height=1.4),
            checkbox_text_style=ft.TextStyle(color=text_primary, size=14),
            code_text_style=ft.TextStyle(
                font_family="Consolas",
                size=13,
                color=code_text_color,
            ),
            codeblock_padding=ft.Padding(left=14, top=12, right=14, bottom=12),
            codeblock_decoration=ft.BoxDecoration(
                bgcolor=bg_code,
                border_radius=ft.BorderRadius.all(8),
                border=ft.Border.all(1, border_color),
            ),
            blockquote_padding=ft.Padding(left=14, top=10, right=14, bottom=10),
            blockquote_decoration=ft.BoxDecoration(
                bgcolor=bg_quote,
                border_radius=ft.BorderRadius.only(top_right=6, bottom_right=6),
                border=ft.Border.only(left=ft.BorderSide(4, accent_primary)),
            ),
            blockquote_text_style=ft.TextStyle(
                italic=True,
                color=text_primary,
                size=14,
            ),
            table_head_text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, color=text_primary),
        )

        if self._cached_processed_text:
            self._render_processed_content(self._cached_processed_text)

        try:
            self.update()
        except Exception:
            pass

    def update_locale(self):
        """Refresh header title, doc info text, watch video button, and placeholder to current locale."""
        if getattr(self, "_preview_mode", "document") == "spreadsheet":
            self.header_title.value = t("preview.spreadsheet_title")
        else:
            self.header_title.value = t("preview.title")
        self.btn_watch_video_text.value = t("preview.watch_video")
        self.btn_watch_video.tooltip = t("preview.watch_video_tooltip")

        if not self._last_raw_text:
            self.doc_info_text.value = t("preview.no_doc")
            self.markdown.value = t("preview.placeholder")
        else:
            if getattr(self, "_preview_mode", "document") == "spreadsheet":
                self._render_spreadsheet_content(self._last_raw_text)
            else:
                words = len(self._last_raw_text.split())
                chars = len(self._last_raw_text)
                self.doc_info_text.value = t("editor.doc_info", words=f"{words:,}", chars=f"{chars:,}")

        for ctrl in [self.header_title, self.btn_watch_video, self.doc_info_text, self.markdown]:
            try:
                if hasattr(ctrl, "page") and ctrl.page:
                    ctrl.update()
            except Exception:
                pass

        try:
            if self.page:
                self.update()
        except Exception:
            pass

