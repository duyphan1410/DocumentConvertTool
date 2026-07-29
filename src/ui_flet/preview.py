"""
Markdown Preview Component for Flet UI (Milestone 2).
Uses Flet native ft.Markdown control, resolves @media/ image tokens
via MediaAssetManager, and embeds local images as base64 data URIs.
"""
import os
import re
import base64
import mimetypes
import flet as ft

from src.services.media_asset_manager import MediaAssetManager

import time

_BASE64_CACHE: dict[str, str] = {}

def image_to_base64_uri(file_path: str, max_width: int = 1000, quality: int = 85) -> str:
    """Converts a local image file path into a fast base64 data URI, cached in memory."""
    if file_path in _BASE64_CACHE:
        return _BASE64_CACHE[file_path]
    try:
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "image/png"

        # Retry loop to handle temporary file locks during PDF image extraction
        encoded_data = None
        for attempt in range(3):
            try:
                with open(file_path, "rb") as f:
                    encoded_data = base64.b64encode(f.read()).decode("utf-8")
                break
            except (PermissionError, OSError):
                time.sleep(0.05)

        if not encoded_data:
            return file_path

        uri = f"data:{mime_type};base64,{encoded_data}"
        _BASE64_CACHE[file_path] = uri
        return uri
    except Exception as e:
        print(f"[DEBUG] Failed to convert image '{file_path}' to base64: {e}")
        return file_path

import pathlib

def process_markdown_media(content: str, base_dir: str = None) -> str:
    """
    Parses Markdown content, resolves virtual URIs (such as @media/image.png)
    and local paths to fast base64 data URIs for Flet Markdown rendering.
    """
    if not content:
        return ""

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

        resolved_path = asset_mgr.resolve_uri(uri)
        if not os.path.exists(resolved_path) and base_dir:
            candidate = os.path.join(base_dir, uri)
            if os.path.exists(candidate):
                resolved_path = candidate

        if os.path.exists(resolved_path):
            base64_uri = image_to_base64_uri(resolved_path)
            return f"![{alt_text}]({base64_uri})"
        return f"![{alt_text}]({uri})"

    image_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
    result = re.sub(image_pattern, replace_image_match, content)
    t_elapsed = time.time() - t0
    print(f"[BENCHMARK] Processed {img_count} preview image links to Base64 in {t_elapsed:.3f}s")
    return result


class MarkdownPreview(ft.Container):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.expand = True
        self.border_radius = 8
        self.padding = 12
        self._last_raw_text = None
        self._cached_processed_text = None

        self.markdown = ft.Markdown(
            value="*Document Preview Placeholder*",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            expand=True,
            soft_line_break=True
        )

        self.scroll_column = ft.Column(
            controls=[self.markdown],
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )
        self.content = self.scroll_column

    def set_content(self, markdown_text: str, base_dir: str = None):
        """Updates preview with processed markdown content, using cache if text hasn't changed."""
        if not markdown_text or not markdown_text.strip():
            self.markdown.value = "*No content to preview.*"
            self._last_raw_text = ""
            self._cached_processed_text = "*No content to preview.*"
        else:
            if markdown_text != self._last_raw_text:
                self._last_raw_text = markdown_text
                self._cached_processed_text = process_markdown_media(markdown_text, base_dir=base_dir)
            self.markdown.value = self._cached_processed_text

        try:
            self.update()
        except Exception:
            pass

    def update_preview(self, markdown_text: str, base_dir: str = None):
        """Alias method for update_preview compatibility."""
        self.set_content(markdown_text, base_dir=base_dir)
