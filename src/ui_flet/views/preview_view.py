"""
Markdown Preview View Component for Flet UI.
Uses Flet native ft.Markdown control, resolves @media/ image tokens
via MediaAssetManager, and embeds local images as base64 data URIs.
"""
import os
import re
import base64
import mimetypes
import time
import pathlib
import flet as ft
from src.i18n import t

from src.services.media_asset_manager import MediaAssetManager

_BASE64_CACHE: dict[str, str] = {}


def image_to_base64_uri(file_path: str, max_width: int = 1000, quality: int = 85) -> str:
    """Converts a local image file path into a fast base64 data URI, cached in memory."""
    if file_path in _BASE64_CACHE:
        return _BASE64_CACHE[file_path]
    try:
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "image/png"

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


async def process_markdown_media_async(content: str, base_dir: str = None, progress_callback=None) -> str:
    """
    Asynchronously parses Markdown content and converts images to base64.
    Yields control back to the asyncio loop between images so Flet UI animations remain smooth.
    """
    if not content:
        return ""

    import asyncio
    t0 = time.time()
    asset_mgr = MediaAssetManager()
    image_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
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

        resolved_path = asset_mgr.resolve_uri(uri)
        if not os.path.exists(resolved_path) and base_dir:
            candidate = os.path.join(base_dir, uri)
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
        self.padding = 12
        self._last_raw_text = None
        self._cached_processed_text = None

        # Header elements — owned by MarkdownPreview for palette sync
        self.header_icon = ft.Icon(ft.Icons.PREVIEW, size=18)
        self.header_title = ft.Text(
            t("preview.title"),
            weight=ft.FontWeight.W_600,
        )
        self.doc_info_text = ft.Text(t("preview.no_doc"), size=12)

        self.header_row = ft.Row(
            controls=[
                self.header_icon,
                self.header_title,
                ft.Container(expand=True),
                self.doc_info_text,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.markdown = ft.Markdown(
            value=t("preview.placeholder"),
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            code_theme=ft.MarkdownCodeTheme.ATOM_ONE_DARK,
            expand=True,
            soft_line_break=True
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
                ft.Divider(),
                self.scroll_column,
            ],
            expand=True,
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


    def set_content(self, markdown_text: str, base_dir: str = None):
        """Updates preview with processed markdown content, using cache if text hasn't changed."""
        if not markdown_text or not markdown_text.strip():
            self.markdown.value = "*No content to preview.*"
            self.markdown_text = ""
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

    def apply_palette(self, palette: dict, is_dark: bool, palette_name: str = ""):
        """Apply palette accent colors to preview header and code themes."""
        from src.ui_flet.theme import resolve_color, get_style_color
        accent_primary = resolve_color(palette, "text_accent_primary", is_dark)
        border_color = resolve_color(palette, "border_color", is_dark)
        text_primary = get_style_color("text_primary", is_dark)
        bg_code = resolve_color(palette, "bg_component", is_dark)
        bg_quote = resolve_color(palette, "bg_header", is_dark)

        self.header_icon.color = accent_primary
        self.header_title.color = accent_primary


        code_text_color = "#ff79c6" if is_dark else "#c026d3"
        code_bg_color = "#282a36" if is_dark else "#f3f4f6"

        # Dynamic Code Theme (Dark / Light)
        self.markdown.code_theme = (
            ft.MarkdownCodeTheme.ATOM_ONE_DARK if is_dark else ft.MarkdownCodeTheme.ATOM_ONE_LIGHT
        )

        # Dynamic Markdown Style Sheet (Headings, Code, CodeBlock, Table & Blockquote)
        self.markdown.md_style_sheet = ft.MarkdownStyleSheet(
            # Heading hierarchy — size + weight differentiation (border-bottom not
            # supported by Flet Markdown; accepted framework limitation).
            h1_text_style=ft.TextStyle(size=28, weight=ft.FontWeight.BOLD,  color=text_primary),
            h2_text_style=ft.TextStyle(size=22, weight=ft.FontWeight.BOLD,  color=text_primary),
            h3_text_style=ft.TextStyle(size=18, weight=ft.FontWeight.W_600, color=text_primary),
            h4_text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_600, color=text_primary),
            h5_text_style=ft.TextStyle(size=14, weight=ft.FontWeight.W_500, color=text_primary),
            h6_text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_500, color=text_primary),

            p_text_style=ft.TextStyle(color=text_primary, size=14, height=1.4),
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
            # Table: only head text style is settable via MarkdownStyleSheet.
            # Cell borders and zebra rows are unsupported by Flet Markdown (framework limit).
            table_head_text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, color=text_primary),
        )


        try:
            self.update()
        except Exception:
            pass

    def update_locale(self):
        """Refresh header title, doc info text, and placeholder to current locale."""
        self.header_title.value = t("preview.title")
        if not self._last_raw_text:
            self.doc_info_text.value = t("preview.no_doc")
            self.markdown.value = t("preview.placeholder")
        else:
            words = len(self._last_raw_text.split())
            chars = len(self._last_raw_text)
            self.doc_info_text.value = t("editor.doc_info", words=f"{words:,}", chars=f"{chars:,}")

        for ctrl in [self.header_title, self.doc_info_text, self.markdown]:
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

