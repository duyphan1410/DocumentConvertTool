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

_BASE64_CACHE: dict[str, str] = {}

def image_to_base64_uri(file_path: str, max_width: int = 1000, quality: int = 85) -> str:
    """Converts a local image file path into a balanced 65-70% optimized base64 data URI, cached in memory."""
    if file_path in _BASE64_CACHE:
        return _BASE64_CACHE[file_path]
    try:
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "image/png"

        # Scale down to 68% of full resolution for ideal balance between visual clarity and performance
        try:
            from PIL import Image
            import io
            with Image.open(file_path) as img:
                target_width = min(max_width, int(img.width * 0.68))
                if img.width > target_width:
                    ratio = target_width / float(img.width)
                    new_height = int(float(img.height) * ratio)
                    resized_img = img.resize((target_width, new_height), Image.Resampling.LANCZOS)
                else:
                    resized_img = img

                buffer = io.BytesIO()
                fmt = "PNG" if "png" in (mime_type or "").lower() else "JPEG"
                if fmt == "JPEG" and resized_img.mode in ("RGBA", "P"):
                    resized_img = resized_img.convert("RGB")

                resized_img.save(buffer, format=fmt, optimize=True)
                encoded_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as ex:
            print(f"[DEBUG] Failed PIL optimization for '{file_path}': {ex}")
            with open(file_path, "rb") as f:
                encoded_data = base64.b64encode(f.read()).decode("utf-8")

        uri = f"data:{mime_type};base64,{encoded_data}"
        _BASE64_CACHE[file_path] = uri
        return uri
    except Exception as e:
        print(f"[DEBUG] Failed to convert image '{file_path}' to base64: {e}")
        return file_path

def process_markdown_media(content: str) -> str:
    """
    Parses Markdown content, resolves virtual URIs (such as @media/image.png)
    using MediaAssetManager, and converts local image files to base64 data URIs.
    """
    if not content:
        return ""

    asset_mgr = MediaAssetManager()

    def replace_image_match(match):
        alt_text = match.group(1)
        uri = match.group(2)

        # 1. Resolve URI via MediaAssetManager
        resolved_path = asset_mgr.resolve_uri(uri)

        # 2. Check if resolved_path points to an existing local file
        if os.path.exists(resolved_path):
            final_uri = image_to_base64_uri(resolved_path)
        else:
            final_uri = uri

        return f"![{alt_text}]({final_uri})"

    # Match image syntax ![alt](url)
    image_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
    processed_content = re.sub(image_pattern, replace_image_match, content)
    return processed_content


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

    def set_content(self, markdown_text: str):
        """Updates preview with processed markdown content, using cache if text hasn't changed."""
        if not markdown_text or not markdown_text.strip():
            self.markdown.value = "*No content to preview.*"
            self._last_raw_text = ""
            self._cached_processed_text = "*No content to preview.*"
        else:
            if markdown_text != self._last_raw_text:
                self._last_raw_text = markdown_text
                self._cached_processed_text = process_markdown_media(markdown_text)
            self.markdown.value = self._cached_processed_text

        try:
            self.update()
        except Exception:
            pass
