"""
Transclusion Engine & Embed Service for Markdown PKB (v1.10.0).
Handles transclusion syntax `![[Target]]`, `![[Target#Heading]]`, and `![[image.png|width]]`.
Safely embeds full notes, sections, images, and attachments with circular-embed protection.
"""
from __future__ import annotations

import os
import re
from typing import Optional, Set, Tuple


IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".tiff"
}

ATTACHMENT_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".pptx", ".ppt", ".txt", ".mp3", ".wav", ".mp4"
}


def strip_frontmatter(text: str) -> str:
    """Removes YAML frontmatter block from markdown text if present."""
    if not text:
        return ""
    if text.startswith("---"):
        end_idx = text.find("\n---", 3)
        if end_idx != -1:
            return text[end_idx + 4:].lstrip("\r\n")
    return text


def get_document_excerpt(file_path: str, max_lines: int = 5, max_chars: int = 350) -> str:
    """
    Reads the first 3-5 clean lines of content from a markdown document
    to use as hover preview tooltip / card.
    """
    if not file_path or not os.path.exists(file_path):
        return ""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(4096)
        text = strip_frontmatter(text)
        lines = []
        for line in text.splitlines():
            clean = line.strip()
            if not clean or clean.startswith("```") or clean.startswith("|") or clean.startswith("![[") or clean.startswith("!["):
                continue
            clean = re.sub(r'\[\[([^\]\|]+)(?:\|([^\]]+))?\]\]', lambda m: m.group(2) if m.group(2) else m.group(1), clean)
            clean = re.sub(r'[*_`#>]', '', clean).strip()
            if clean:
                lines.append(clean)
            if len(lines) >= max_lines:
                break
        excerpt = "\n".join(lines)
        if len(excerpt) > max_chars:
            excerpt = excerpt[:max_chars].rstrip() + "..."
        return excerpt
    except Exception:
        return ""


def extract_heading_section(markdown_text: str, heading_name: str) -> str:
    """
    Extracts content under a specific markdown heading (`# Heading Name`) up to
    the next heading of same or higher level (equal or fewer `#`).
    Comparison is case-insensitive and ignores leading/trailing markdown styling.
    """
    if not markdown_text or not heading_name:
        return markdown_text

    clean_target = heading_name.strip().lower().lstrip("#").strip()
    lines = markdown_text.splitlines()
    
    target_idx = -1
    target_level = 0
    
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')

    for idx, line in enumerate(lines):
        m = heading_pattern.match(line.strip())
        if m:
            level = len(m.group(1))
            title = m.group(2).strip().lower()
            # Strip link / bold formatting if any
            clean_title = re.sub(r'[*_`\[\]]', '', title).strip()
            if clean_title == clean_target or title == clean_target:
                target_idx = idx
                target_level = level
                break

    if target_idx == -1:
        # Heading not found: return placeholder notice
        return f"> ⚠️ *Không tìm thấy đề mục: #{heading_name}*"

    # Collect lines until next heading with level <= target_level
    collected: list[str] = [lines[target_idx]]
    for line in lines[target_idx + 1:]:
        m = heading_pattern.match(line.strip())
        if m:
            level = len(m.group(1))
            if level <= target_level:
                break
        collected.append(line)

    return "\n".join(collected)


def format_transcluded_block(title: str, content: str, doc_id: Optional[str] = None) -> str:
    """
    Wraps embedded content into an elegant, styled callout/quote block.
    """
    clean_body = content.strip()
    if not clean_body:
        clean_body = "*(Trang trống)*"

    header_link = f"[{title}](doc://{doc_id})" if doc_id else title
    
    # Prefix each non-empty line with quote marker '>'
    body_lines = clean_body.splitlines()
    quoted_lines = []
    for l in body_lines:
        quoted_lines.append(f"> {l}" if l.strip() else ">")
        
    quoted_body = "\n".join(quoted_lines)
    return f"> 📄 **{header_link}**\n>\n{quoted_body}\n"


def process_markdown_transclusions(
    content: str,
    base_dir: Optional[str] = None,
    visited: Optional[Set[str]] = None,
    depth: int = 0,
    max_depth: int = 3,
) -> str:
    """
    Scans for `![[Target]]` or `![[Target|Option]]` transclusion embeds in Markdown.
    Supports:
    - Images: `![[image.png]]`, `![[image.png|300]]`, `![[image.png|alt]]` -> converts to `![alt](image.png)`
    - Note Transclusion: `![[Note]]` or `![[Note#Heading]]` -> embeds note content recursively.
    - Attachments: `![[file.pdf]]` -> converts to attachment badge.
    Guards against circular references and deep nesting with `visited` set and `max_depth`.
    """
    if not content or "![[" not in content:
        return content

    if visited is None:
        visited = set()

    # Identify excluded ranges (code blocks, inline code)
    excluded_ranges: list[tuple[int, int]] = []
    for m in re.finditer(r'(?m)^[ \t]*```[^\r\n]*\r?\n[\s\S]*?(?:^[ \t]*```|\Z)', content):
        excluded_ranges.append((m.start(), m.end()))
    for m in re.finditer(r'`+[^`\r\n]+`+', content):
        excluded_ranges.append((m.start(), m.end()))

    def _is_excluded(start: int, end: int) -> bool:
        for ex_s, ex_e in excluded_ranges:
            if not (end <= ex_s or start >= ex_e):
                return True
        return False

    pattern = re.compile(r'!\[\[([^\]\|]+)(?:\|([^\]]+))?\]\]')
    matches = list(pattern.finditer(content))
    if not matches:
        return content

    # Lazy import of MetadataIndex to avoid circular dependencies
    index = None
    try:
        from src.services.metadata_index import MetadataIndex
        index = MetadataIndex.get_instance()
    except Exception:
        pass

    result = list(content)

    for m in reversed(matches):
        if _is_excluded(m.start(), m.end()):
            continue

        raw_target = m.group(1).strip()
        option = m.group(2).strip() if m.group(2) else ""

        if not raw_target:
            continue

        # Check extension
        _, ext = os.path.splitext(raw_target)
        ext_lower = ext.lower()

        # 1. Image Embed: ![[image.png]] or ![[image.png|300]] or ![[image.png|alt]]
        if ext_lower in IMAGE_EXTENSIONS:
            if option:
                # Option can be width ('300', '300px', '50%') or dimensions ('300x200') or alt text
                if re.match(r'^\d+(?:px|%)?$', option) or re.match(r'^\d+x\d+$', option):
                    replacement = f"![{os.path.basename(raw_target)}|{option}]({raw_target})"
                else:
                    replacement = f"![{option}]({raw_target})"
            else:
                replacement = f"![{os.path.basename(raw_target)}]({raw_target})"
            result[m.start():m.end()] = list(replacement)
            continue

        # 2. Attachment Embed: ![[file.pdf]], ![[data.xlsx]]
        if ext_lower in ATTACHMENT_EXTENSIONS:
            doc_record = None
            if index:
                try:
                    doc_record = index.resolve_target_document(raw_target, source_path=base_dir)
                except Exception:
                    pass
            doc_id = doc_record["id"] if doc_record else ""
            title = option or doc_record["title"] if (doc_record and doc_record.get("title")) else os.path.basename(raw_target)
            link_uri = f"doc://{doc_id}" if doc_id else raw_target
            replacement = f"> 📎 **[{title}]({link_uri})** *({ext_lower.lstrip('.').upper()} File)*\n"
            result[m.start():m.end()] = list(replacement)
            continue

        # 3. Note Transclusion: ![[Note]] or ![[Note#Heading]]
        heading_target = None
        doc_target = raw_target
        if "#" in raw_target:
            parts = raw_target.split("#", 1)
            doc_target = parts[0].strip()
            heading_target = parts[1].strip()

        doc_record = None
        file_path = None

        if index:
            try:
                doc_record = index.resolve_target_document(doc_target, source_path=base_dir)
            except Exception:
                pass

        if doc_record and doc_record.get("path") and os.path.exists(doc_record["path"]):
            file_path = doc_record["path"]
        elif base_dir:
            # Fallback to relative path on disk
            candidates = [
                os.path.normpath(os.path.abspath(os.path.join(base_dir, doc_target))),
                os.path.normpath(os.path.abspath(os.path.join(base_dir, doc_target + ".md"))),
                os.path.normpath(os.path.abspath(os.path.join(base_dir, doc_target + ".markdown"))),
            ]
            for cand in candidates:
                if os.path.exists(cand) and os.path.isfile(cand):
                    file_path = cand
                    break

        if not file_path:
            # Unresolved transclusion target
            replacement = f"> ⚠️ *Không tìm thấy nội dung nhúng: [[{raw_target}]]*\n"
            result[m.start():m.end()] = list(replacement)
            continue

        canonical_path = os.path.normcase(os.path.normpath(os.path.abspath(file_path)))

        if canonical_path in visited or depth >= max_depth:
            # Circular embed or recursion depth exceeded
            replacement = f"> ⚠️ **[Vòng lặp nhúng (Circular Embed)]**: [[{doc_target}]]\n"
            result[m.start():m.end()] = list(replacement)
            continue

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()

            raw_text = strip_frontmatter(raw_text)

            if heading_target:
                embed_text = extract_heading_section(raw_text, heading_target)
            else:
                embed_text = raw_text

            # Recursively resolve any nested transclusions
            next_visited = visited | {canonical_path}
            nested_processed = process_markdown_transclusions(
                embed_text,
                base_dir=os.path.dirname(file_path),
                visited=next_visited,
                depth=depth + 1,
                max_depth=max_depth,
            )

            title = option or (doc_record.get("title") if doc_record else os.path.splitext(os.path.basename(file_path))[0])
            if heading_target:
                title = f"{title} > #{heading_target}"

            doc_id = doc_record.get("id") if doc_record else None
            replacement = format_transcluded_block(title=title, content=nested_processed, doc_id=doc_id)
        except Exception as ex:
            replacement = f"> ⚠️ *Lỗi khi nhúng [[{raw_target}]]: {ex}*\n"

        result[m.start():m.end()] = list(replacement)

    return "".join(result)
