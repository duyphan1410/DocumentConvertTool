"""
Helper utilities for parsing, generating, and inspecting image tokens (Markdown and HTML <img>)
in the document editor and preview panes.
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass
class ImageTokenInfo:
    """Represents a detected image token inside the document text."""
    raw_token: str
    start: int
    end: int
    src: str
    alt: str = ""
    width: str = ""
    height: str = ""
    align: str = ""  # "left", "center", "right", or ""
    is_html: bool = False

    @property
    def is_percentage_width(self) -> bool:
        return bool(self.width and self.width.strip().endswith("%"))

    @property
    def clean_width_value(self) -> str:
        """Returns width value stripped of px or % units."""
        return self.width.strip().rstrip("%").rstrip("px").strip()

    @property
    def clean_height_value(self) -> str:
        """Returns height value stripped of px units."""
        return self.height.strip().rstrip("px").strip()


def _parse_html_attributes(tag_content: str) -> dict[str, str]:
    """
    Extracts HTML attributes from a tag string into a dictionary.
    Handles single quotes, double quotes, unquoted values, and varied attribute order.
    """
    attr_pattern = r'([a-zA-Z0-9_-]+)(?:\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+)))?'
    attrs = {}
    for match in re.finditer(attr_pattern, tag_content):
        name = match.group(1).lower()
        val = match.group(2) if match.group(2) is not None else (
            match.group(3) if match.group(3) is not None else (
                match.group(4) if match.group(4) is not None else ""
            )
        )
        attrs[name] = val
    return attrs


def _extract_align_value(attrs: dict[str, str], default_tag: str = "") -> str:
    """Extracts alignment ('left', 'center', 'right') from tag attributes or style declaration."""
    if default_tag.lower() == "center":
        return "center"
    align = (attrs.get("align", "") or "").strip().lower()
    if align in ("left", "center", "right"):
        return align
    style = attrs.get("style", "").lower()
    if style:
        m = re.search(r'text-align\s*:\s*(left|center|right)', style)
        if m:
            return m.group(1).lower()
    return ""


def find_all_image_tokens(text: str) -> List[ImageTokenInfo]:
    """
    Scans the document text and extracts all image tokens (both Markdown and HTML).
    Ensures non-greedy, clean detection even with multiple images on the same line.
    """
    if not text:
        return []

    tokens: List[ImageTokenInfo] = []

    # 1. HTML Image tag pattern wrapped in <p>, <div>, or <center>
    # Handles: <p align="...">...<img ...>...</p>, <div align="...">...<img ...>...</div>, <center><img ...></center>
    html_wrapper_img_pattern = re.compile(
        r'<(p|div|center)(?:\s+([^>]*?))?>\s*(<img\s+[^>]*?>)\s*</\1>',
        re.IGNORECASE | re.DOTALL
    )
    for m in html_wrapper_img_pattern.finditer(text):
        tag_name = m.group(1).lower()
        tag_attrs_str = m.group(2) or ""
        parent_attrs = _parse_html_attributes(tag_attrs_str)
        img_str = m.group(3)
        img_attrs = _parse_html_attributes(img_str)
        src = img_attrs.get("src", "")
        if src:
            align = _extract_align_value(parent_attrs, default_tag=tag_name) or _extract_align_value(img_attrs)
            tokens.append(ImageTokenInfo(
                raw_token=m.group(0),
                start=m.start(),
                end=m.end(),
                src=src,
                alt=img_attrs.get("alt", ""),
                width=img_attrs.get("width", ""),
                height=img_attrs.get("height", ""),
                align=align,
                is_html=True,
            ))

    # 2. Markdown Image pattern wrapped in <p>, <div>, or <center>
    # Handles: <p align="...">![alt](src)</p>, <div align="...">![alt](src)</div>, <center>![alt](src)</center>
    html_wrapper_md_pattern = re.compile(
        r'<(p|div|center)(?:\s+([^>]*?))?>\s*(!\[([^\]]*)\]\(\s*(?:<([^>]+)>|([^\)\"\']+?))(?:\s+[\"\']([^\"\']*)[\"\'])?\s*\))\s*</\1>',
        re.IGNORECASE | re.DOTALL
    )
    for m in html_wrapper_md_pattern.finditer(text):
        if any(tok.start <= m.start() and m.end() <= tok.end for tok in tokens):
            continue
        tag_name = m.group(1).lower()
        tag_attrs_str = m.group(2) or ""
        parent_attrs = _parse_html_attributes(tag_attrs_str)
        alt = m.group(4) or ""
        src = (m.group(5) or m.group(6) or "").strip()
        align = _extract_align_value(parent_attrs, default_tag=tag_name)
        if src:
            tokens.append(ImageTokenInfo(
                raw_token=m.group(0),
                start=m.start(),
                end=m.end(),
                src=src,
                alt=alt,
                width="",
                height="",
                align=align,
                is_html=True,
            ))

    # 3. Standalone <img> tags (not already captured inside a wrapper)
    html_img_pattern = re.compile(r'<img\s+[^>]*?>', re.IGNORECASE)
    for m in html_img_pattern.finditer(text):
        if any(tok.start <= m.start() and m.end() <= tok.end for tok in tokens):
            continue
        img_attrs = _parse_html_attributes(m.group(0))
        src = img_attrs.get("src", "")
        if src:
            align = _extract_align_value(img_attrs)
            tokens.append(ImageTokenInfo(
                raw_token=m.group(0),
                start=m.start(),
                end=m.end(),
                src=src,
                alt=img_attrs.get("alt", ""),
                width=img_attrs.get("width", ""),
                height=img_attrs.get("height", ""),
                align=align,
                is_html=True,
            ))

    # 4. Standalone Markdown Image pattern: ![alt](url) or ![alt](url "title")
    md_img_pattern = re.compile(
        r'!\[([^\]]*)\]\(\s*(?:<([^>]+)>|([^\)\"\']+?))(?:\s+[\"\']([^\"\']*)[\"\'])?\s*\)'
    )
    for m in md_img_pattern.finditer(text):
        if any(tok.start <= m.start() and m.end() <= tok.end for tok in tokens):
            continue
        alt = m.group(1)
        src = (m.group(2) or m.group(3) or "").strip()
        tokens.append(ImageTokenInfo(
            raw_token=m.group(0),
            start=m.start(),
            end=m.end(),
            src=src,
            alt=alt,
            width="",
            height="",
            align="",
            is_html=False,
        ))

    # Sort all tokens in order of appearance
    tokens.sort(key=lambda t: t.start)
    return tokens


def find_image_token_at_offset(text: str, cursor_start: int, cursor_end: int = -1) -> Optional[ImageTokenInfo]:
    """
    Finds and returns the image token located at or overlapping the given cursor selection range.
    Touch tolerance: If cursor is right before (start) or right after (end) the token, it is considered active.
    """
    if not text:
        return None

    if cursor_end < 0:
        cursor_end = cursor_start

    c_min = min(cursor_start, cursor_end)
    c_max = max(cursor_start, cursor_end)

    tokens = find_all_image_tokens(text)
    for token in tokens:
        # Check for overlap or touching boundary
        if token.start <= c_max and c_min <= token.end:
            return token

    return None


def generate_image_token(
    src: str,
    alt: str = "",
    width: str = "",
    height: str = "",
    align: str = "",
) -> str:
    """
    Generates appropriate Markdown or HTML image token string based on sizing and alignment.
    - If standard 100% / unconstrained with no alignment: generates clean `![alt](src)`
    - If width/height or alignment specified: generates clean HTML `<img ... />` or `<p align="..."><img ... /></p>`
    """
    clean_src = (src or "").strip().replace("\\", "/")
    clean_alt = (alt or "").strip()
    clean_width = (width or "").strip()
    clean_height = (height or "").strip()
    clean_align = (align or "").strip().lower()

    # Standard Markdown if no custom dimensions and no alignment
    if not clean_width and not clean_height and not clean_align:
        return f"![{clean_alt}]({clean_src})"

    # If width is 100% and no height and no align, revert to clean markdown
    if clean_width in ("100%", "100") and not clean_height and not clean_align:
        return f"![{clean_alt}]({clean_src})"

    # Construct HTML <img> tag
    parts = [f'src="{clean_src}"']
    if clean_alt:
        parts.append(f'alt="{clean_alt}"')
    if clean_width:
        parts.append(f'width="{clean_width}"')
    if clean_height and clean_height.lower() != "auto":
        parts.append(f'height="{clean_height}"')

    img_tag = f'<img {" ".join(parts)} />'

    if clean_align in ("center", "left", "right"):
        return f'<p align="{clean_align}">{img_tag}</p>'

    return img_tag


def inspect_image_dimensions(image_path: str, base_dir: Optional[str] = None) -> Tuple[int, int]:
    """
    Safely inspects the natural dimensions (width, height) of an image file.
    Includes graceful fallbacks when PIL cannot open the file or path is invalid.
    """
    if not image_path:
        return 800, 600

    # Resolve local path if base_dir provided
    target_path = image_path
    if not os.path.isabs(target_path) and base_dir:
        candidate = os.path.normpath(os.path.abspath(os.path.join(base_dir, target_path)))
        if os.path.exists(candidate):
            target_path = candidate

    if os.path.exists(target_path) and os.path.isfile(target_path):
        try:
            from PIL import Image
            with Image.open(target_path) as img:
                return img.size  # (width, height)
        except Exception:
            pass

    # Fallback standard dimensions
    return 800, 600


def calculate_scaled_dimensions(
    orig_w: int,
    orig_h: int,
    target_scale_percent: Optional[int] = None,
    custom_w: Optional[int] = None,
    custom_h: Optional[int] = None,
    lock_ratio: bool = True,
) -> Tuple[int, int]:
    """
    Calculates pixel width and height based on scaling ratio or custom dimensions.
    """
    if orig_w <= 0:
        orig_w = 800
    if orig_h <= 0:
        orig_h = 600

    aspect = orig_w / max(1, orig_h)

    if target_scale_percent is not None:
        factor = max(1, target_scale_percent) / 100.0
        new_w = max(1, int(round(orig_w * factor)))
        new_h = max(1, int(round(orig_h * factor)))
        return new_w, new_h

    if custom_w is not None and lock_ratio:
        new_w = max(1, custom_w)
        new_h = max(1, int(round(new_w / aspect)))
        return new_w, new_h

    if custom_h is not None and lock_ratio:
        new_h = max(1, custom_h)
        new_w = max(1, int(round(new_h * aspect)))
        return new_w, new_h

    new_w = max(1, custom_w if custom_w is not None else orig_w)
    new_h = max(1, custom_h if custom_h is not None else orig_h)
    return new_w, new_h
