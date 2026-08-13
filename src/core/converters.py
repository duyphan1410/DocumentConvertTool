import os
import re

def parse_table_rows(table_lines: list[str]) -> list[list[str]]:
    """
    Parses a list of raw pipe-delimited Markdown table lines into clean row data.
    Filters out separator lines (|---|---|), strips cell whitespace, and normalizes row lengths.
    """
    data_lines = [l for l in table_lines if not re.match(r"^[\|\s\-:]+$", l.strip())]
    if not data_lines:
        return []
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in data_lines]
    # Filter empty elements if trailing/leading pipe split produced empty strings, while preserving inner cells
    clean_rows = []
    for r in rows:
        clean_rows.append([c for c in r])
    max_cols = max((len(r) for r in clean_rows), default=0)
    return [r + [""] * (max_cols - len(r)) for r in clean_rows]


def parse_md_tables(content: str) -> list:
    tables, lines, i = [], content.split("\n"), 0
    while i < len(lines):
        line = lines[i].strip()
        if "|" in line and not re.match(r"^[\|\s\-:]+$", line):
            table_name = f"Sheet{len(tables)+1}"
            for j in range(i-1, max(i-5, -1), -1):
                prev = lines[j].strip()
                if prev.startswith("#"):
                    table_name = re.sub(r"^#+\s*", "", prev)
                    table_name = re.sub(r'[\\/?*\[\]:]', "_", table_name)[:31]
                    break
            table_lines = []
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i].strip())
                i += 1
            rows = parse_table_rows(table_lines)
            if len(rows) >= 2:
                tables.append((table_name, rows))
        else:
            i += 1
    return tables


def save_markdown_from_text(content: str, out_path: str) -> str:
    from src.services.media_asset_manager import MediaAssetManager
    final_content = MediaAssetManager().export_assets(content, out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(final_content)
    return f"Markdown file saved successfully -> {os.path.basename(out_path)}"


def prepare_markdown_for_export(text: str) -> str:
    """
    Preprocesses Markdown text prior to document export across all modules (HTML, PDF, PPTX, Word):
    1. Standardizes bullet characters (•, ·, ⁃, ▪) into clean Markdown list items (- ).
    2. Prevents the Markdown 'Lazy List Continuation Trap':
       Inserts a blank line if a bold title line (e.g., **Social Network Website**) or header line
       immediately follows a list item without a blank line, breaking out of the <ul> list.
    """
    if not text:
        return text

    # 1. Convert bullet symbols (•, ·, ⁃, ▪) into -
    text = re.sub(r'^[•·⁃▪]\s*', '- ', text, flags=re.MULTILINE)
    text = re.sub(r'\s+[•·⁃▪]\s+', '\n- ', text)

    # 2. Prevent Markdown list continuation trap
    lines = text.split('\n')
    new_lines = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        is_list_item = stripped.startswith('- ') or stripped.startswith('* ') or bool(re.match(r'^\d+\.\s', stripped))
        if is_list_item:
            in_list = True
            new_lines.append(line)
        else:
            if in_list and (stripped.startswith('**') or stripped.startswith('###') or stripped.startswith('##') or stripped.startswith('#')):
                new_lines.append('')
                in_list = False
            new_lines.append(line)
    return '\n'.join(new_lines)


class TextSegment:
    def __init__(self, text: str, bold: bool = False, italic: bool = False, strike: bool = False, underline: bool = False, code: bool = False, url: str = None, is_image: bool = False):
        self.text = text
        self.bold = bold
        self.italic = italic
        self.strike = strike
        self.underline = underline
        self.code = code
        self.url = url
        self.is_image = is_image


def parse_inline(text: str, bold: bool = False, italic: bool = False, strike: bool = False, underline: bool = False, code: bool = False, url: str = None, is_image: bool = False) -> list[TextSegment]:
    if not text:
        return []

    # List of (pattern, style_modifier_dict)
    # Ordered to match more specific/longer patterns first
    patterns = [
        # Image: ![alt](url)
        (re.compile(r'!\[([^\]]*?)\]\((.+?\.(?:png|jpg|jpeg|gif|svg|webp|bmp|ico)|https?://\S+|@media/\S+?|[^\n)]+)\)', re.IGNORECASE), lambda m: {"url": m.group(2), "is_image": True}),
        # Link: [text](url)
        (re.compile(r'\[([^\]]*?)\]\(([^)]*?)\)'), lambda m: {"url": m.group(2)}),
        # Bold-Italic: ***text*** or ___text___
        (re.compile(r'\*\*\*(.*?)\*\*\*'), lambda m: {"bold": True, "italic": True}),
        (re.compile(r'___(.*?)___'), lambda m: {"bold": True, "italic": True}),
        # Bold: **text** or __text__
        (re.compile(r'\*\*(.*?)\*\*'), lambda m: {"bold": True}),
        (re.compile(r'__(.*?)__'), lambda m: {"bold": True}),
        # Italic: *text* or _text_
        (re.compile(r'\*(.*?)\*'), lambda m: {"italic": True}),
        (re.compile(r'_(.*?)_'), lambda m: {"italic": True}),
        # Strikethrough: ~~text~~
        (re.compile(r'~~(.*?)~~'), lambda m: {"strike": True}),
        # Underline: <u>text</u>
        (re.compile(r'(?i)<u>(.*?)</u>'), lambda m: {"underline": True}),
        # Inline Code: `text`
        (re.compile(r'`(.*?)`'), lambda m: {"code": True}),
    ]

    earliest_match = None
    earliest_start = len(text)
    matched_updater = None

    for pattern, updater in patterns:
        m = pattern.search(text)
        if m:
            start = m.start()
            if start < earliest_start:
                earliest_start = start
                earliest_match = m
                matched_updater = updater

    if earliest_match:
        start, end = earliest_match.span()
        prefix = text[:start]
        matched_text = earliest_match.group(1)
        suffix = text[end:]

        style_updates = matched_updater(earliest_match)
        
        new_bold = bold or style_updates.get("bold", False)
        new_italic = italic or style_updates.get("italic", False)
        new_strike = strike or style_updates.get("strike", False)
        new_underline = underline or style_updates.get("underline", False)
        new_code = code or style_updates.get("code", False)
        new_url = url or style_updates.get("url", None)
        new_is_image = is_image or style_updates.get("is_image", False)

        segments = []
        if prefix:
            segments.extend(parse_inline(prefix, bold, italic, strike, underline, code, url, is_image))
        
        segments.extend(parse_inline(matched_text, new_bold, new_italic, new_strike, new_underline, new_code, new_url, new_is_image))
        
        if suffix:
            segments.extend(parse_inline(suffix, bold, italic, strike, underline, code, url, is_image))
        
        return segments
    else:
        return [TextSegment(text, bold, italic, strike, underline, code, url, is_image)]


def wrap_text_style(text: str, bold: bool = False, italic: bool = False, strike: bool = False, underline: bool = False, code: bool = False) -> str:
    if not text:
        return ""
    # Find leading and trailing whitespaces
    left_spaces = text[:-len(text.lstrip())] if text.lstrip() else text
    right_spaces = text[len(text.rstrip()):] if text.rstrip() else ""
    middle = text.strip()
    if not middle:
        return text
    
    if bold:
        middle = f"**{middle}**"
    if italic:
        middle = f"*{middle}*"
    if strike:
        middle = f"~~{middle}~~"
    if underline:
        middle = f"<u>{middle}</u>"
    if code:
        middle = f"`{middle}`"
    
    return left_spaces + middle + right_spaces


def strip_markdown_styles(text: str) -> str:
    segments = parse_inline(text)
    return "".join(s.text for s in segments)

