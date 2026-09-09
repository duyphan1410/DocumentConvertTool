"""
Link & Tag Parser Service Interface & Stubs.
Author: Huy (Regex, Tokenization & Link Extraction)
Interface Contract for PKB Phase 1 (v1.10.0).
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class WikilinkToken:
    """Represents a [[Target]] or [[Target|Display]] wikilink token found in markdown content."""
    raw_target: str               # "Kế Hoạch 2026"
    display_text: Optional[str]   # "Xem kế hoạch" (or None if no alias)
    snippet: str                  # 1-2 lines of surrounding text context
    start_pos: int                # Start character index in document
    end_pos: int                  # End character index in document


@dataclass
class UnlinkedMentionToken:
    """Represents an unlinked mention of a target document title in markdown content."""
    matched_text: str             # The exact string matched (e.g. "Kế Hoạch 2026")
    snippet: str                  # 1-2 lines of surrounding text context
    start_pos: int
    end_pos: int


def extract_wikilinks(markdown_text: str) -> list[WikilinkToken]:
    """
    Extracts all [[...]] wikilinks from Markdown content with aliases and context snippets.
    Ignores occurrences within code blocks (```...```), inline code (`...`), and YAML frontmatter.
    Filters out invalid placeholder targets (e.g. '...', empty strings).
    
    TODO (Huy): Optimize regex for edge cases, escaped brackets, and multiline snippets.
    """
    if not markdown_text:
        return []
    
    # Identify ranges to exclude (frontmatter, code blocks, inline code)
    excluded_ranges: list[tuple[int, int]] = []
    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', markdown_text, re.DOTALL)
    if fm_match:
        excluded_ranges.append((fm_match.start(), fm_match.end()))
    for m in re.finditer(r'(?m)^[ \t]*```[^\r\n]*\r?\n[\s\S]*?(?:^[ \t]*```|\Z)', markdown_text):
        excluded_ranges.append((m.start(), m.end()))
    for m in re.finditer(r'`+[^`\r\n]+`+', markdown_text):
        excluded_ranges.append((m.start(), m.end()))

    def _is_excluded(start: int, end: int) -> bool:
        for ex_s, ex_e in excluded_ranges:
            if not (end <= ex_s or start >= ex_e):
                return True
        return False

    tokens: list[WikilinkToken] = []
    lines = markdown_text.splitlines(keepends=True)
    line_offsets: list[int] = []
    curr = 0
    for l in lines:
        line_offsets.append(curr)
        curr += len(l)

    def _get_snippet(start: int, end: int) -> str:
        line_idx = 0
        for i, off in enumerate(line_offsets):
            if off <= start:
                line_idx = i
            else:
                break
        start_line = max(0, line_idx - 1)
        end_line = min(len(lines), line_idx + 2)
        snip = "".join(lines[start_line:end_line]).strip()
        return snip

    # 1. Wikilinks [[Target]] or [[Target|Alias]]
    pattern = re.compile(r'\[\[([^\]\|]+)(?:\|([^\]]+))?\]\]')
    for m in pattern.finditer(markdown_text):
        if _is_excluded(m.start(), m.end()):
            continue
        target = m.group(1).strip()
        # Filter out empty or placeholder targets (e.g. '...', '…', '---')
        if not target or re.match(r'^[.\-—_\s]+$', target):
            continue
        alias = m.group(2).strip() if m.group(2) else None
        snip = _get_snippet(m.start(), m.end())
        tokens.append(WikilinkToken(
            raw_target=target,
            display_text=alias,
            snippet=snip,
            start_pos=m.start(),
            end_pos=m.end(),
        ))

    # 2. Standard Markdown Relative Links [Display](relative/path.md)
    md_link_pattern = re.compile(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)')
    for m in md_link_pattern.finditer(markdown_text):
        if _is_excluded(m.start(), m.end()):
            continue
        url = m.group(2).strip()
        if not url.startswith(("http://", "https://", "mailto:", "#", "ftp://", "data:", "doc://", "doc-create://", "yt://", "imgaction://")):
            clean_url = url.split("?")[0].split("#")[0].replace("%20", " ").strip()
            if clean_url.lower().endswith((".md", ".markdown")):
                display = m.group(1).strip()
                snip = _get_snippet(m.start(), m.end())
                tokens.append(WikilinkToken(
                    raw_target=clean_url,
                    display_text=display,
                    snippet=snip,
                    start_pos=m.start(),
                    end_pos=m.end(),
                ))
    return tokens


def extract_tags(markdown_text: str) -> list[str]:
    """
    Extracts tags from YAML Frontmatter (`tags: [...]`) and inline `#tag` tokens.
    
    TODO (Huy): Support nested tags (#project/subproject) and YAML list format.
    """
    if not markdown_text:
        return []
    tags: set[str] = set()

    # 1. YAML Frontmatter Tags: tags: [a, b] or tags:\n - a\n - b
    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', markdown_text, re.DOTALL)
    if fm_match:
        fm_content = fm_match.group(1)
        # Inline list: tags: [tag1, tag2]
        inline_list_m = re.search(r'tags:\s*\[(.*?)\]', fm_content, re.IGNORECASE)
        if inline_list_m:
            for item in inline_list_m.group(1).split(','):
                cleaned = item.strip().strip('"\'')
                if cleaned:
                    tags.add(cleaned)
        else:
            # Block list: tags:\n - tag1\n - tag2
            block_list_m = re.search(r'tags:\s*\n((?:\s*-\s*[^\n]+\n?)+)', fm_content, re.IGNORECASE)
            if block_list_m:
                for line in block_list_m.group(1).splitlines():
                    val = re.sub(r'^\s*-\s*', '', line).strip().strip('"\'')
                    if val:
                        tags.add(val)

    # 2. Inline #tag (avoiding Markdown headers `# Heading` and hex colors `#fff`)
    # Match #tag where tag starts with alphanumeric and is preceded by whitespace/start of line
    inline_tag_pattern = re.compile(r'(?:^|\s)#([a-zA-Z0-9_\-/\u00C0-\u1EF9]+)(?=\s|$|[.,;:!?])')
    # Exclude frontmatter when scanning inline tags
    body_text = markdown_text[fm_match.end():] if fm_match else markdown_text
    # Exclude code blocks
    body_without_code = re.sub(r'(?m)^[ \t]*```[^\r\n]*\r?\n[\s\S]*?(?:^[ \t]*```|\Z)', '', body_text)
    body_without_code = re.sub(r'`+[^`\r\n]+`+', '', body_without_code)

    for m in inline_tag_pattern.finditer(body_without_code):
        tag_val = m.group(1).strip()
        # Filter out purely numeric tags or single chars if desired
        if tag_val and not tag_val.isdigit():
            tags.add(tag_val)

    return sorted(list(tags))


def find_unlinked_mentions(markdown_text: str, target_title: str) -> list[UnlinkedMentionToken]:
    """
    Finds occurrences of `target_title` in markdown text that are NOT already enclosed in [[...]] wikilinks.
    Supports Vietnamese diacritic invariant and fuzzy matching.
    """
    if not markdown_text or not target_title or len(target_title) < 2:
        return []

    from src.services.fuzzy_matcher import normalize_vietnamese, find_fuzzy_substring_occurrences

    # Fast pre-filter: if normalized target title does not exist in normalized text, skip immediately
    norm_target = normalize_vietnamese(target_title)
    if norm_target not in normalize_vietnamese(markdown_text):
        return []

    # Identify ranges to exclude (code blocks, existing wikilinks, existing markdown links, HTML tags)
    excluded_ranges: list[tuple[int, int]] = []
    for m in re.finditer(r'\[\[[\s\S]*?\]\]', markdown_text):
        excluded_ranges.append((m.start(), m.end()))
    for m in re.finditer(r'\[[\s\S]*?\]\([^\)]*\)', markdown_text):
        excluded_ranges.append((m.start(), m.end()))
    for m in re.finditer(r'<[^>\n]+>', markdown_text):
        excluded_ranges.append((m.start(), m.end()))
    for m in re.finditer(r'(?m)^[ \t]*```[^\r\n]*\r?\n[\s\S]*?(?:^[ \t]*```|\Z)', markdown_text):
        excluded_ranges.append((m.start(), m.end()))

    def _is_excluded(start: int, end: int) -> bool:
        for ex_s, ex_e in excluded_ranges:
            if not (end <= ex_s or start >= ex_e):
                return True
        return False

    lines = markdown_text.splitlines(keepends=True)
    line_offsets: list[int] = []
    curr = 0
    for l in lines:
        line_offsets.append(curr)
        curr += len(l)

    def _get_snippet(start: int) -> str:
        line_idx = 0
        for i, off in enumerate(line_offsets):
            if off <= start:
                line_idx = i
            else:
                break
        return lines[line_idx].strip() if line_idx < len(lines) else ""

    occurrences = find_fuzzy_substring_occurrences(markdown_text, target_title, min_similarity=0.88)
    mentions: list[UnlinkedMentionToken] = []

    for start_p, end_p, matched_str, _ in occurrences:
        if not _is_excluded(start_p, end_p):
            snip = _get_snippet(start_p)
            mentions.append(UnlinkedMentionToken(
                matched_text=matched_str,
                snippet=snip,
                start_pos=start_p,
                end_pos=end_p,
            ))
    return mentions
