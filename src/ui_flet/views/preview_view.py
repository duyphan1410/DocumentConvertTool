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
import flet as ft
from src.i18n import t

import threading
from src.services.media_asset_manager import MediaAssetManager

_BASE64_CACHE: dict[str, str] = {}
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
            first_err_line = err_body.split("\n")[0] if err_body else f"HTTP {e.code}"
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
                md_img = f"![Mermaid Diagram](https://mermaid.ink/img/{encoded_payload}?bgColor={bg_hex})"
                return md_img
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




def image_to_base64_uri(file_path: str, max_width: int = 650, quality: int = 70) -> str:
    """
    Converts a local image file path into an ultra-lightweight base64 data URI.
    Uses PIL to downscale to 650px and compress to optimized JPEG/PNG (averaging ~35KB per image),
    reducing multi-megabyte payloads by 96% so Flutter renders immediately without freezing.
    """
    if file_path in _BASE64_CACHE:
        return _BASE64_CACHE[file_path]
    try:
        from PIL import Image
        import io

        for attempt in range(3):
            try:
                with Image.open(file_path) as img:
                    orig_w, orig_h = img.size
                    if orig_w > max_width:
                        new_h = max(1, int(orig_h * (max_width / orig_w)))
                        img = img.resize((max_width, new_h), Image.Resampling.LANCZOS)

                    buf = io.BytesIO()
                    has_alpha = False
                    if img.mode in ("RGBA", "LA"):
                        extrema = img.getextrema()
                        if len(extrema) >= 4 and extrema[3][0] < 255:
                            has_alpha = True
                    elif img.mode == "P" and "transparency" in img.info:
                        has_alpha = True

                    if has_alpha:
                        img.save(buf, format="PNG", optimize=True)
                        mime_type = "image/png"
                    else:
                        img = img.convert("RGB")
                        img.save(buf, format="JPEG", quality=quality, optimize=True)
                        mime_type = "image/jpeg"

                    raw_bytes = buf.getvalue()
                    encoded_data = base64.b64encode(raw_bytes).decode("ascii")
                    uri = f"data:{mime_type};base64,{encoded_data}"
                    _BASE64_CACHE[file_path] = uri
                    return uri
            except (PermissionError, OSError):
                time.sleep(0.05)

        # Fallback to direct raw read if PIL fails
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "image/png"
        with open(file_path, "rb") as f:
            encoded_data = base64.b64encode(f.read()).decode("ascii")
        uri = f"data:{mime_type};base64,{encoded_data}"
        _BASE64_CACHE[file_path] = uri
        return uri
    except Exception as e:
        print(f"[DEBUG] Failed to convert image '{file_path}' to base64: {e}")
        return file_path


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


def process_markdown_media(content: str, base_dir: str = None, is_dark: bool = False, palette_name: str = "Violet Cyberpunk", enable_cloud_mermaid: bool = True, session_id: str | None = None) -> str:
    """
    Parses Markdown content, intercepts Mermaid diagram blocks, resolves virtual URIs (such as @media/image.png)
    and local paths to fast base64 data URIs for Flet Markdown rendering.
    Also links interactive YouTube timestamps.
    """
    if not content:
        return ""

    content = clean_html_tags_for_preview(content)
    content = process_markdown_timestamps(content)
    content = process_markdown_mermaid(content, is_dark=is_dark, palette_name=palette_name, enable_cloud=enable_cloud_mermaid)
    t0 = time.time()
    asset_mgr = MediaAssetManager()
    img_count = 0

    def replace_image_match(match):
        nonlocal img_count
        img_count += 1
        alt_text = match.group(1)
        uri = match.group(2)

        if uri.startswith(("http://", "https://", "data:")):
            return f"![{alt_text}]({uri})"

        resolved_path = asset_mgr.resolve_uri(uri, base_dir=base_dir, session_id=session_id)
        if not os.path.exists(resolved_path) and base_dir:
            candidate = os.path.normpath(os.path.abspath(os.path.join(base_dir, uri)))
            if os.path.exists(candidate):
                resolved_path = candidate

        if os.path.exists(resolved_path):
            base64_uri = image_to_base64_uri(resolved_path)
            return f"![{alt_text}]({base64_uri})"
        return f"![{alt_text}]({uri})"

    image_pattern = r"!\[([^\]]*)\]\((.+?\.(?:png|jpg|jpeg|gif|svg|webp|bmp|ico)|https?://\S+|@media/\S+?|[^\n)]+)\)"
    result = re.sub(image_pattern, replace_image_match, content)
    t_elapsed = time.time() - t0
    print(f"[BENCHMARK] Processed {img_count} preview image links to Base64 in {t_elapsed:.3f}s")
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
    image_pattern = r"!\[([^\]]*)\]\((.+?\.(?:png|jpg|jpeg|gif|svg|webp|bmp|ico)|https?://\S+|@media/\S+?|[^\n)]+)\)"
    matches = list(re.finditer(image_pattern, content))
    if not matches:
        return content

    total_imgs = len(matches)
    replacements = {}

    for idx, match in enumerate(matches, 1):
        alt_text = match.group(1)
        uri = match.group(2)

        if uri.startswith(("http://", "https://", "data:")):
            continue

        resolved_path = asset_mgr.resolve_uri(uri, base_dir=base_dir, session_id=session_id)
        if not os.path.exists(resolved_path) and base_dir:
            candidate = os.path.normpath(os.path.abspath(os.path.join(base_dir, uri)))
            if os.path.exists(candidate):
                resolved_path = candidate

        if os.path.exists(resolved_path):
            base64_uri = await asyncio.to_thread(image_to_base64_uri, resolved_path)
            replacements[match.group(0)] = f"![{alt_text}]({base64_uri})"
            if progress_callback:
                try:
                    progress_callback(idx, total_imgs)
                except Exception:
                    pass
            await asyncio.sleep(0.005)

    result = content
    for old_token, new_token in replacements.items():
        result = result.replace(old_token, new_token)

    t_elapsed = time.time() - t0
    print(f"[BENCHMARK] Processed {total_imgs} preview image links to Base64 asynchronously in {t_elapsed:.3f}s")
    return result


class MarkdownPreview(ft.Container):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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

        # Non-YouTube link: launch in system browser
        try:
            if self.page:
                self.page.launch_url(url)
            else:
                import webbrowser
                webbrowser.open(url)
        except Exception as ex:
            print(f"[DEBUG] Failed to launch URL '{url}': {ex}")

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

    def set_content(self, markdown_text: str, base_dir: str = None, session_id: str | None = None):
        """Updates preview with processed markdown content, using cache if text hasn't changed."""
        self._base_dir = base_dir
        self._session_id = session_id
        if not markdown_text or not markdown_text.strip():
            self.markdown.value = "*No content to preview.*"
            self.markdown_text = ""
            self._last_raw_text = ""
            self._cached_processed_text = "*No content to preview.*"
            self.detect_youtube_video("")
        else:
            if markdown_text != self._last_raw_text:
                self._last_raw_text = markdown_text
                self._cached_processed_text = process_markdown_media(
                    markdown_text, base_dir=base_dir, is_dark=self._is_dark, palette_name=self._palette_name, session_id=session_id
                )
                self.detect_youtube_video(markdown_text)

            self.markdown.value = self._cached_processed_text

        try:
            self.update()
        except Exception:
            pass

    def set_processed_content(self, processed_md: str, raw_text: str, base_dir: str = None, session_id: str | None = None):
        """Sets pre-computed processed markdown directly in 0ms without re-parsing images or re-encoding Base64."""
        self._base_dir = base_dir
        self._session_id = session_id
        self._last_raw_text = raw_text
        self._cached_processed_text = processed_md
        self.markdown.value = processed_md
        if hasattr(self, "detect_youtube_video"):
            self.detect_youtube_video(raw_text)
        try:
            if self.page:
                self.update()
        except Exception:
            pass

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
                        self.markdown.value = processed
                        try:
                            if self.markdown.page:
                                self.markdown.update()
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

        try:
            self.update()
        except Exception:
            pass

        try:
            self.update()
        except Exception:
            pass

    def update_locale(self):
        """Refresh header title, doc info text, watch video button, and placeholder to current locale."""
        self.header_title.value = t("preview.title")
        self.btn_watch_video_text.value = t("preview.watch_video")
        self.btn_watch_video.tooltip = t("preview.watch_video_tooltip")

        if not self._last_raw_text:
            self.doc_info_text.value = t("preview.no_doc")
            self.markdown.value = t("preview.placeholder")
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

