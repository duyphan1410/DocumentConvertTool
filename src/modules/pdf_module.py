import os
import sys
import re
import io
import hashlib
from src.core.base_module import BaseDocumentModule
from src.core.registry import ModuleRegistry

# PyInstaller static analyzer hints
try:
    import pdfplumber
    import fitz
    import markdown_pdf
except ImportError:
    pass


class PDFModule(BaseDocumentModule):
    """
    Production-grade PDF converter module.
    
    Supports:
    - High-fidelity rich text extraction with font styles (Bold, Italic) and baseline alignment.
    - Multi-column slide text separation (preventing character interleaving on 2-column slides).
    - Intelligent Card Table & multi-row Data Table extraction with cross-page stitching.
    - Alpha-mask (SMask) PNG compositing with MD5-based image deduplication.
    - Export from Markdown to PDF with customized font faces, tables, code blocks, and TOC.
    """

    @property
    def name(self) -> str:
        return "PDF"

    @property
    def file_extensions(self) -> list[str]:
        return [".pdf"]

    @property
    def required_dependencies(self) -> list[str]:
        return ["pdfplumber", "pymupdf", "markdown-pdf", "Pillow"]

    # =========================================================================
    # TABLE PROCESSING HELPERS
    # =========================================================================

    def _merge_non_overlapping_columns(self, rows: list[list[str]]) -> list[list[str]]:
        """Merges adjacent table columns if they never contain overlapping text."""
        if not rows or len(rows) < 2:
            return rows
        num_cols = len(rows[0])
        cols = list(range(num_cols))
        changed = True
        while changed:
            changed = False
            for i in range(len(cols) - 1):
                c1 = cols[i]
                c2 = cols[i + 1]
                overlap = False
                for row in rows:
                    if row[c1] and row[c2]:
                        overlap = True
                        break
                if not overlap:
                    for row in rows:
                        if row[c2]:
                            row[c1] = row[c2]
                    cols.pop(i + 1)
                    changed = True
                    break
        rebuilt = []
        for row in rows:
            rebuilt.append([row[c] for c in cols])
        return rebuilt

    def _clean_table(self, table_data: list[list[any]]) -> list[list[str]]:
        """Cleans empty rows/columns and formats whitespace in extracted tables."""
        if not table_data:
            return []
        valid_rows = [r for r in table_data if r is not None]
        if not valid_rows:
            return []
        max_cols = max(len(r) for r in valid_rows)
        cleaned = []
        for row in valid_rows:
            cleaned_row = []
            for cell in row:
                val = str(cell).strip() if cell is not None else ""
                cleaned_row.append(val)
            if len(cleaned_row) < max_cols:
                cleaned_row.extend([""] * (max_cols - len(cleaned_row)))
            cleaned.append(cleaned_row[:max_cols])
        merged = self._merge_non_overlapping_columns(cleaned)
        if not merged:
            return []
        num_cols = len(merged[0])
        active_cols = []
        for col_idx in range(num_cols):
            has_val = any(row[col_idx] for row in merged)
            if has_val:
                active_cols.append(col_idx)
        if not active_cols:
            return []
        rebuilt = []
        for row in merged:
            rebuilt.append([row[idx] for idx in active_cols])
        return rebuilt

    def _map_row_to_parent_columns(self, t2_row: list[any], t2_cols: list[any], t1_cols: list[any]) -> list[str]:
        """Maps child table row cells to parent column coordinates for cross-page table stitching."""
        parent_row = [""] * len(t1_cols)
        for j, cell in enumerate(t2_row):
            val = str(cell).strip() if cell is not None else ""
            tx0 = t2_cols[j].bbox[0]
            tx1 = t2_cols[j].bbox[2]
            
            best_idx = -1
            max_overlap = -1
            for idx, col in enumerate(t1_cols):
                cx0 = col.bbox[0]
                cx1 = col.bbox[2]
                overlap = min(tx1, cx1) - max(tx0, cx0)
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_idx = idx
            if best_idx != -1 and max_overlap > 0:
                parent_row[best_idx] = val
        return parent_row

    def _should_merge_first_row(self, last_row: list[str], first_row: list[str]) -> bool:
        """Determines if the first row of a continued table should be merged into the last row of the parent."""
        if len(last_row) == len(first_row) and len(first_row) > 1:
            if not first_row[0]:
                for c in range(1, len(first_row)):
                    if not last_row[c] and first_row[c]:
                        return True
                if last_row[-1] and first_row[-1]:
                    last_char = last_row[-1].strip()[-1] if last_row[-1].strip() else ""
                    if last_char not in (".", "!", "?", ":"):
                        return True
        return False

    def _format_markdown_table(self, table_data: list[list[any]]) -> str:
        """Renders raw 2D table data into a clean Markdown table string."""
        cleaned = self._clean_table(table_data)
        if not cleaned or len(cleaned) < 2 or len(cleaned[0]) < 2:
            return ""
        headers = cleaned[0]
        rows = cleaned[1:]
        parts = []
        parts.append("| " + " | ".join(h.replace("\n", "<br>").replace("|", "\\|") for h in headers) + " |")
        parts.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in rows:
            parts.append("| " + " | ".join(c.replace("\n", "<br>").replace("|", "\\|") for c in row) + " |")
        return "\n".join(parts)

    def _restructure_card_table_if_needed(self, t_data: list[list[any]]) -> tuple[str | None, list[list[str]] | None]:
        """
        Detects presentation card grids (e.g. 4 or 5 vertical cards like Slide 3, Slide 6)
        and converts them into structured Markdown card tables with titles.
        
        Returns (extracted_title, restructured_table_data), or (None, None) to reject pseudo-tables.
        """
        if not t_data:
            return None, None
            
        valid_rows = [r for r in t_data if r and any(c and str(c).strip() for c in r)]
        if len(valid_rows) != 1:
            return None, t_data  # Multi-row table is left as-is
        
        row = valid_rows[0]
        if len(row) < 2:
            return None, t_data
            
        lines_per_col = []
        for c in row:
            if c:
                clist = [l.strip() for l in str(c).split("\n") if l.strip()]
                lines_per_col.append(clist)
            else:
                lines_per_col.append([])
                
        has_multiline = any(len(c) >= 2 for c in lines_per_col)
        if not has_multiline:
            return None, t_data

        # 1. Clean out standalone page numbers or step/circle numbers (e.g. "3", "6", "P.3", "①", "1", "2", "3", "4")
        for c_lines in lines_per_col:
            if c_lines and re.match(r'^\s*(\d{1,3}|p\.\s*\d+|[①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾❿])\s*$', c_lines[0], re.IGNORECASE):
                c_lines.pop(0)

        # 2. Clean out fragmented all-caps top title remnants (e.g. 'Á HỌC' from 'KHOÁ HỌC')
        for c_lines in lines_per_col:
            if len(c_lines) >= 3 and c_lines[0].isupper() and (len(c_lines[0].split()) <= 2 or len(c_lines[0]) <= 5):
                c_lines.pop(0)

        # 3. Handle Tree/Flowchart root parent titles (e.g. 'Projective Techniques' above 'Construction')
        extracted_title = None
        if len(lines_per_col) >= 3:
            for idx, c in enumerate(lines_per_col):
                if len(c) >= 3 and 0 < idx < len(lines_per_col) - 1:
                    # If this column has an extra top line that acts as diagram root node
                    extracted_title = c.pop(0)
                    break

        # 4. Determine header and data body per column: Line 0 is Header, Line 1+ is Data
        headers = []
        data_cells = []
        for col_lines in lines_per_col:
            if col_lines:
                headers.append(col_lines[0])
                data_cells.append("<br>".join(col_lines[1:]) if len(col_lines) > 1 else "")
            else:
                headers.append("")
                data_cells.append("")

        # 5. Guard against broken pseudo-tables using linguistic and geometric properties
        stop_words = {'những', 'các', 'về', 'của', 'và', 'khi', 'cho', 'để', 'trong', 'với', 'là', 'tại', 'có', 'ở', 'được', 'ng', 'cô', 'thời', 'nhỏ', 'năng', 'đấu', 'trợ', 'à'}
        for h in headers:
            text = h.strip()
            if not text:
                continue
            words = text.split()
            first_word = words[0].lower()
            last_word = words[-1].lower()
            if first_word in stop_words or text[0].islower():
                return None, None
            if last_word in stop_words or len(last_word) <= 1:
                return None, None
            if len(words) > 5:
                return None, None

        restructured = [headers, data_cells]
        return extracted_title, restructured

    # =========================================================================
    # TEXT & MULTI-COLUMN EXTRACTION HELPERS
    # =========================================================================

    def _extract_rich_text(self, cropped_page) -> str:
        """
        Extracts formatted text from a cropped page region, handling:
        - Character-level font styles (Bold, Italic) without inserting extra spaces in Vietnamese words.
        - Multi-column segmentation (preventing letter interleaving on 2-column slides).
        - Accurate Heading vs Paragraph classification.
        """
        chars = cropped_page.chars
        if not chars:
            return ""

        def get_lines_from_chars(block_chars: list[dict]) -> list[list[dict]]:
            if not block_chars:
                return []
            chars_sorted = sorted(block_chars, key=lambda c: (c['top'], c['x0']))
            lines = []
            curr = []
            curr_top = None
            for c in chars_sorted:
                top = c['top']
                if curr_top is None:
                    curr_top = top
                    curr.append(c)
                elif abs(top - curr_top) <= 3.8:
                    curr.append(c)
                else:
                    lines.append(curr)
                    curr = [c]
                    curr_top = top
            if curr:
                lines.append(curr)
            return lines

        raw_lines = get_lines_from_chars(chars)
        min_top = min(min(c['top'] for c in l) for l in raw_lines) if raw_lines else 0.0

        def format_lines(lines_to_format: list[list[dict]]) -> list[tuple[str, int]]:
            items = []
            for line in lines_to_format:
                line.sort(key=lambda c: c["x0"])
                runs = []
                current_run_text = ""
                current_font = None
                total_size = 0
                char_count = 0
                
                for char in line:
                    font = char.get("fontname", "").lower()
                    bold = "bold" in font
                    italic = "italic" in font or "oblique" in font
                    
                    size = char.get("size", 10)
                    total_size += size
                    char_count += 1
                    
                    style_key = (bold, italic)
                    if current_font is None:
                        current_font = style_key
                        current_run_text = char["text"]
                    elif style_key == current_font:
                        last_char = line[line.index(char) - 1]
                        gap = char["x0"] - last_char["x1"]
                        char_width = char["x1"] - char["x0"]
                        if gap > char_width * 0.25 and not current_run_text.endswith(" ") and char["text"] != " ":
                            current_run_text += " "
                        current_run_text += char["text"]
                    else:
                        runs.append((current_run_text, current_font))
                        current_font = style_key
                        current_run_text = char["text"]
                if current_run_text:
                    runs.append((current_run_text, current_font))
                    
                avg_size = total_size / char_count if char_count > 0 else 10
                
                formatted_runs = []
                for text, (bold, italic) in runs:
                    stripped = text.strip()
                    if not stripped:
                        formatted_runs.append(text)
                        continue
                        
                    leading_spaces = text[:len(text) - len(text.lstrip())]
                    trailing_spaces = text[len(text.rstrip()):]
                    
                    val = stripped
                    if bold and italic:
                        val = f"***{val}***"
                    elif bold:
                        val = f"**{val}**"
                    elif italic:
                        val = f"*{val}*"
                        
                    formatted_runs.append(f"{leading_spaces}{val}{trailing_spaces}")
                    
                line_text = "".join(formatted_runs).strip()
                if not line_text or line_text.strip() in ("-", "•", "·", "⁃", "▪"):
                    continue

                for _ in range(3):
                    line_text = re.sub(r'\*\*(.*?)\*\*([^\s\*]{1,3})\*\*(.*?)\*\*', r'**\1\2\3**', line_text)
                    line_text = re.sub(r'\*\*(.*?)\*\*\s*\*\*(.*?)\*\*', r'**\1 \2**', line_text)

                is_bullet = False
                if re.search(r'^[•·⁃▪]\s*', line_text) or re.search(r'^[-\*]\s+', line_text):
                    line_text = re.sub(r'^[•·⁃▪]\s*', '- ', line_text)
                    line_text = re.sub(r'^\*\s+', '- ', line_text)
                    line_text = re.sub(r'\s+[•·⁃▪]\s+', '\n- ', line_text)
                    is_bullet = True

                heading_lvl = 0
                words = line_text.split()
                ends_sentence = bool(re.search(r'([.!?…;~”"’»\)\]\}]|\.\.\.)$', line_text.strip()))
                is_page_num = bool(re.match(r'^\s*(\*{0,2}\d{1,3}\*{0,2}|p\.\s*\d+)\s*$', line_text, re.IGNORECASE))
                first_char = line_text[0] if line_text else ""

                if not is_bullet and not line_text.startswith("- ") and not is_page_num:
                    if first_char.isupper() or line_text.isupper():
                        if avg_size >= 22 and len(words) <= 7:
                            heading_lvl = 1
                            line_text = re.sub(r'\*{2,3}', '', line_text)
                        elif 13.5 <= avg_size < 17 and line_text.isupper() and len(words) <= 5:
                            heading_lvl = 3
                            line_text = re.sub(r'\*{2,3}', '', line_text)

                items.append((line_text, heading_lvl))
            return items

        def merge_heading_items(items: list[tuple[str, int]]) -> list[tuple[str, int]]:
            merged = []
            for text, heading_lvl in items:
                if not text:
                    continue
                if not merged:
                    merged.append((text, heading_lvl))
                    continue

                prev_text, prev_lvl = merged[-1]
                prev_ends_punc = bool(re.search(r'([.!?…;~”"’»\)\]\}]|\.\.\.)$', prev_text.strip()))
                starts_lower = text[0].islower() if text else False
                prev_ends_continuation = bool(re.search(r'[,–—/\&、，-]\s*$', prev_text.strip()))
                prev_words = prev_text.split()

                # 1. If current line starts with lowercase, it is a wrapped continuation of the previous line
                # (e.g. bullet continuation: "- Độc thân... Có con" + "nhỏ từ 0 - 6 tuổi")
                if starts_lower:
                    merged[-1] = (f"{prev_text} {text}", prev_lvl)
                # 2. Merge consecutive headings of the same level (e.g. big multi-line slide title)
                elif prev_lvl > 0 and heading_lvl > 0 and prev_lvl == heading_lvl and not prev_ends_punc:
                    merged[-1] = (f"{prev_text} {text}", prev_lvl)
                # 3. Normal paragraph body sentence wrapping:
                elif prev_lvl == 0 and heading_lvl == 0 and not prev_text.startswith("- ") and not text.startswith("- ") and not prev_text.startswith("**"):
                    if prev_ends_continuation or (len(prev_words) >= 5 and not prev_ends_punc):
                        merged[-1] = (f"{prev_text} {text}", 0)
                    else:
                        merged.append((text, heading_lvl))
                else:
                    merged.append((text, heading_lvl))
            return merged

        # Check if body lines form a 3, 4, or 5 column card grid
        body_segmented_lines = []
        max_segs = 1
        for line in raw_lines:
            line.sort(key=lambda c: c['x0'])
            line_top = min(c['top'] for c in line)
            min_x = min(c['x0'] for c in line)
            max_x = max(c['x1'] for c in line)

            # Check if line contains distinct column segments (horizontal gap >= 20px)
            segs = []
            curr_seg = [line[0]]
            for i in range(1, len(line)):
                gap = line[i]['x0'] - line[i-1]['x1']
                if gap >= 20:
                    segs.append(curr_seg)
                    curr_seg = [line[i]]
                else:
                    curr_seg.append(line[i])
            if curr_seg:
                segs.append(curr_seg)

            if len(segs) > max_segs:
                max_segs = len(segs)

            body_segmented_lines.append((line_top, min_x, max_x, segs, line))

        top_lines = []
        left_lines = []
        right_lines = []
        has_columns = False

        if max_segs >= 3:
            # Multi-column grid (e.g. 5 columns on Slide 6)
            col_streams = [[] for _ in range(max_segs)]
            for line_top, min_x, max_x, segs, line in body_segmented_lines:
                if len(segs) == 1 and (line_top < min_top + 60 or (max_x - min_x > 300 and min_x < 250 and max_x > 550)):
                    top_lines.append(line)
                elif len(segs) == max_segs:
                    for s_idx, s in enumerate(segs):
                        col_streams[s_idx].append(s)
                else:
                    for s in segs:
                        s_mid = (min(c['x0'] for c in s) + max(c['x1'] for c in s)) / 2.0
                        col_idx = min(max_segs - 1, max(0, int((s_mid / cropped_page.width) * max_segs)))
                        col_streams[col_idx].append(s)

            # Check if right columns are vector graphic diagram text noise (e.g. rotated labels on Sinking Ship)
            right_stream_texts = []
            for s in col_streams[1:]:
                right_stream_texts.extend([t for t, _ in format_lines(s)])
            all_right_words = " ".join(right_stream_texts).split()

            is_graphic_noise = False
            if all_right_words:
                single_or_short = sum(1 for w in all_right_words if len(w) <= 2)
                avg_len = sum(len(w) for w in all_right_words) / len(all_right_words)
                if (single_or_short / len(all_right_words) > 0.35 and avg_len < 3.8) or (len(all_right_words) <= 3 and avg_len <= 3.0):
                    is_graphic_noise = True

            if is_graphic_noise:
                # Discard diagram text noise and keep only clean left-side content
                left_items = merge_heading_items(format_lines(col_streams[0]))
                top_items = merge_heading_items(format_lines(top_lines))
                all_merged = top_items + left_items
                line_texts = []
                for text, heading_lvl in all_merged:
                    if heading_lvl == 1:
                        line_texts.append(f"# {text}")
                    elif heading_lvl == 2:
                        line_texts.append(f"## {text}")
                    elif heading_lvl == 3:
                        line_texts.append(f"### {text}")
                    else:
                        line_texts.append(text)
                reordered_lines = self._standardize_slide_header(line_texts)
                return "\n\n".join(reordered_lines)

            col_headers = []
            col_data = []
            for stream in col_streams:
                items = merge_heading_items(format_lines(stream))
                if items:
                    col_headers.append(items[0][0])
                    col_data.append("<br>".join(t for t, _ in items[1:]) if len(items) > 1 else "")
                else:
                    col_headers.append("")
                    col_data.append("")

            top_items = merge_heading_items(format_lines(top_lines))
            top_texts = []
            for text, heading_lvl in top_items:
                if heading_lvl == 1:
                    top_texts.append(f"# {text}")
                elif heading_lvl == 2:
                    top_texts.append(f"## {text}")
                elif heading_lvl == 3:
                    top_texts.append(f"### {text}")
                else:
                    top_texts.append(text)

            top_reordered = self._standardize_slide_header(top_texts)
            table_md = "| " + " | ".join(col_headers) + " |\n"
            table_md += "| " + " | ".join(["---"] * max_segs) + " |\n"
            table_md += "| " + " | ".join(col_data) + " |"
            return "\n\n".join(top_reordered + [table_md])

        for line_top, min_x, max_x, segs, line in body_segmented_lines:
            mid_x = (min_x + max_x) / 2.0
            if len(segs) > 1:
                has_columns = True
                left_lines.append(segs[0])
                for s in segs[1:]:
                    right_lines.append(s)
            else:
                if line_top < min_top + 60 or (max_x - min_x > 300 and min_x < 250 and max_x > 550):
                    top_lines.append(line)
                elif mid_x < 420:
                    left_lines.append(line)
                else:
                    right_lines.append(line)

        if left_lines and right_lines:
            has_columns = True

        if has_columns:
            top_items = format_lines(top_lines)
            left_items = format_lines(left_lines)
            right_items = format_lines(right_lines)

            # Check if left and right columns form a 2-column comparison table
            table_result = self._try_build_comparison_table(top_items, left_items, right_items)
            if table_result is not None:
                return table_result

            # Check if right_items is vector graphic/diagram text noise (e.g. rotated labels on Sinking Ship)
            # which is already rendered inside the illustration image
            right_texts = [t for t, _ in right_items]
            all_words = " ".join(right_texts).split()
            is_graphic_noise = False
            if all_words:
                single_or_short = sum(1 for w in all_words if len(w) <= 2)
                avg_len = sum(len(w) for w in all_words) / len(all_words)
                if (single_or_short / len(all_words) > 0.40 and avg_len < 3.8) or (len(all_words) <= 3 and avg_len <= 3.0):
                    is_graphic_noise = True

            merged_right = [] if is_graphic_noise else merge_heading_items(right_items)
            all_merged = merge_heading_items(top_items) + merge_heading_items(left_items) + merged_right
        else:
            all_items = format_lines(raw_lines)
            all_merged = merge_heading_items(all_items)

        line_texts = []
        for text, heading_lvl in all_merged:
            if heading_lvl == 1:
                line_texts.append(f"# {text}")
            elif heading_lvl == 2:
                line_texts.append(f"## {text}")
            elif heading_lvl == 3:
                line_texts.append(f"### {text}")
            else:
                line_texts.append(text)

        reordered_lines = self._standardize_slide_header(line_texts)
        return "\n\n".join(reordered_lines)

    def _standardize_slide_header(self, texts: list[str]) -> list[str]:
        """
        Extracts standalone page numbers and category banners regardless of where they appear
        in the raw text stream (top, middle, or bottom of slide) and places them uniformly at the top.
        """
        page_num = None
        banner = None
        title = None
        cleaned_texts = [l.strip() for l in texts if l.strip()]

        for item in cleaned_texts:
            m_num = re.match(r'^\s*\*{0,2}(\d{1,3})\*{0,2}\s*$', item)
            if m_num and not page_num:
                page_num = f"**{m_num.group(1)}**"
                break

        other_items = []
        for item in cleaned_texts:
            m_num = re.match(r'^\s*\*{0,2}(\d{1,3})\*{0,2}\s*$', item)
            if m_num and page_num and f"**{m_num.group(1)}**" == page_num:
                continue

            if item.startswith("### ") and not banner and not title and len(other_items) == 0:
                banner_text = item[4:].strip()
                if banner_text.isupper() and len(banner_text.split()) <= 4:
                    banner = item
                    continue

            if item.startswith("# ") and not title and len(other_items) <= 2:
                title = item
                continue

            other_items.append(item)

        result = []
        if banner:
            result.append(banner)
        if page_num:
            result.append(page_num)
        if title:
            result.append(title)
        result.extend(other_items)
        return result

    def _try_build_comparison_table(self, top_items: list[tuple[str, int]], left_items: list[tuple[str, int]], right_items: list[tuple[str, int]]) -> str | None:
        """
        Synthesizes a clean Markdown comparison table when two parallel columns
        share a symmetric structure (e.g. Slide 32 'Cách hỏi thông thường' vs 'Cách story-telling').
        """
        if not left_items or not right_items:
            return None
            
        h0_l, lvl0_l = left_items[0]
        h0_r, lvl0_r = right_items[0]
        
        if (h0_l.startswith("- ") or h0_r.startswith("- ") or
            len(h0_l.split()) > 5 or len(h0_r.split()) > 5):
            return None

        def split_sections(items):
            secs = []
            cur_h = None
            cur_b = []
            for t, lvl in items:
                if lvl > 0 or (t.isupper() and len(t.split()) <= 4):
                    if cur_h or cur_b:
                        secs.append((cur_h or "", "<br><br>".join(cur_b)))
                    cur_h = t
                    cur_b = []
                else:
                    cur_b.append(t)
            if cur_h or cur_b:
                secs.append((cur_h or "", "<br><br>".join(cur_b)))
            return secs

        left_secs = split_sections(left_items)
        right_secs = split_sections(right_items)
        
        if len(left_secs) >= 1 and len(left_secs) == len(right_secs):
            h0_left, b0_left = left_secs[0]
            h0_right, b0_right = right_secs[0]
            if h0_left and h0_right and b0_left and b0_right:
                rows = []
                rows.append(f"| {h0_left} | {h0_right} |")
                rows.append("| --- | --- |")
                rows.append(f"| {b0_left} | {b0_right} |")
                for i in range(1, len(left_secs)):
                    hl, bl = left_secs[i]
                    hr, br = right_secs[i]
                    if hl or hr:
                        rows.append(f"| **{hl}** | **{hr}** |")
                    if bl or br:
                        rows.append(f"| {bl} | {br} |")
                tbl_str = "\n".join(rows)
                
                top_strs = []
                for t, lvl in top_items:
                    if lvl == 1:
                        top_strs.append(f"# {t}")
                    elif lvl == 2:
                        top_strs.append(f"## {t}")
                    elif lvl == 3:
                        top_strs.append(f"### {t}")
                    else:
                        top_strs.append(t)

                reordered_top = self._standardize_slide_header(top_strs)
                if reordered_top:
                    return "\n\n".join(reordered_top) + "\n\n" + tbl_str
                return tbl_str
        return None

    # =========================================================================
    # IMAGE EXTRACTION HELPERS
    # =========================================================================

    def _extract_page_images(self, page, page_idx: int, page_fitz, smasks_on_page: set, global_img_counter: int) -> tuple[list[dict], int]:
        """
        Extracts valid images from a PDF page using PyMuPDF (fitz) with:
        - SMask alpha transparency compositing.
        - Black stencil and shadow mask filtering.
        - Background coverage guard.
        - Centralized MD5-based deduplication.
        """
        page_images = []
        try:
            from PIL import Image as PILImage
            import numpy as np

            image_list = page_fitz.get_images(full=True)
            candidates = []

            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                smask_xref = img_info[1]

                if xref in smasks_on_page:
                    continue

                pix = fitz.Pixmap(page_fitz.parent, xref)
                ext = "png"
                img_bytes = None

                # Handle alpha SMask transparency compositing
                if smask_xref > 0:
                    try:
                        mask = fitz.Pixmap(page_fitz.parent, smask_xref)
                        if mask.w == pix.w and mask.h == pix.h:
                            if pix.colorspace and pix.colorspace.name != "DeviceRGB":
                                pix = fitz.Pixmap(fitz.csRGB, pix)
                            pix = fitz.Pixmap(pix, mask)
                            img_bytes = pix.tobytes("png")
                            ext = "png"
                    except Exception as smask_err:
                        print(f"[DEBUG] PDFModule: SMask compositing failed for xref {xref}: {smask_err}", file=sys.stderr)

                if img_bytes is None:
                    if pix.n >= 5:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    img_bytes = pix.tobytes(ext)

                if not img_bytes or len(img_bytes) < 300:
                    continue

                try:
                    with PILImage.open(io.BytesIO(img_bytes)) as pil_img:
                        if pil_img.width < 16 or pil_img.height < 16:
                            continue
                        if pil_img.mode == "L" and pil_img.getextrema() == (0, 0):
                            continue
                        if pil_img.mode == "RGB" and pil_img.getextrema() == ((0, 0), (0, 0), (0, 0)):
                            continue
                        if pil_img.mode == "RGBA":
                            alpha_extrema = pil_img.split()[3].getextrema()
                            if alpha_extrema == (0, 0):
                                continue

                        # High-speed optimization: Analyze on a lightweight thumbnail (max 128x128)
                        thumb = pil_img.copy()
                        if thumb.width > 128 or thumb.height > 128:
                            thumb.thumbnail((128, 128), PILImage.Resampling.NEAREST)

                        arr = np.array(thumb)
                        h, w = arr.shape[:2]
                        if thumb.mode == 'RGBA':
                            rgb = arr[:, :, :3]
                            alpha = arr[:, :, 3]
                        else:
                            rgb = arr if arr.ndim >= 3 else np.stack([arr]*3, axis=-1)
                            alpha = np.full((h, w), 255, dtype=np.uint8)

                        non_trans = alpha > 20
                        if not np.any(non_trans):
                            continue

                        valid_rgb = rgb[non_trans]
                        std_dev = float(np.std(valid_rgb))
                        r, g, b = valid_rgb[:, 0], valid_rgb[:, 1], valid_rgb[:, 2]
                        color_diff = float(np.mean(np.abs(r.astype(int) - g.astype(int)) + np.abs(g.astype(int) - b.astype(int))))

                        # Filter out button drop shadow glows, blurry gray halos, and solid color placeholders
                        if std_dev < 8.0 or (color_diff < 12.0 and std_dev < 14.0):
                            print(f"[DEBUG] PDFModule: Filtered shadow/halo artifact on page {page_idx + 1} (std_dev={std_dev:.1f}, color_diff={color_diff:.1f})")
                            continue

                        if h >= 10 and w >= 10:
                            # Analyze center core (middle 50% of image): if center is empty white/transparent, it's a decorative frame
                            center = arr[int(h * 0.25) : int(h * 0.75), int(w * 0.25) : int(w * 0.75)]
                            if thumb.mode == 'RGBA':
                                c_rgb = center[:, :, :3]
                                c_a = center[:, :, 3]
                                c_is_white = np.all(c_rgb >= 235, axis=2)
                                c_is_trans = c_a < 20
                                center_blank = float(np.mean(c_is_white | c_is_trans))
                            else:
                                c_rgb = center[:, :, :3] if center.ndim >= 3 else center
                                center_blank = float(np.mean(np.all(c_rgb >= 235, axis=2))) if center.ndim >= 3 else float(np.mean(center >= 235))

                            if center_blank > 0.85:
                                print(f"[DEBUG] PDFModule: Filtered empty card frame/shadow mask on page {page_idx + 1} (center_blank={center_blank:.0%})")
                                continue

                        total_px = h * w
                        white_px = np.sum(np.all(rgb >= 235, axis=2))
                        white_ratio = white_px / total_px if total_px > 0 else 0.0

                        if white_ratio > 0.88:
                            print(f"[DEBUG] PDFModule: Filtered white frame on page {page_idx + 1} (white_ratio={white_ratio:.2f})")
                            continue

                        rects = page_fitz.get_image_rects(xref)
                        top_y = rects[0].y0 if rects else 0.0
                        rect = rects[0] if rects else fitz.Rect(0, 0, 0, 0)

                        page_area = page.width * page.height
                        img_area = (rect.x1 - rect.x0) * (rect.y1 - rect.y0)
                        if page_area > 0 and img_area > page_area * 0.85:
                            print(f"[DEBUG] PDFModule: Skipped likely-background image (page {page_idx+1})")
                            continue

                        candidates.append({
                            "xref": xref,
                            "img_idx": img_idx,
                            "img_bytes": img_bytes,
                            "ext": ext,
                            "top_y": top_y
                        })
                except Exception:
                    pass

            for cand in candidates:
                filename = f"pdf_image_p{page_idx + 1}_{cand['img_idx'] + 1}.{cand['ext']}"
                uri = self.register_image_asset(cand["img_bytes"], filename)
                page_images.append({
                    "type": "image",
                    "content": f"![Image {global_img_counter}]({uri})",
                    "top": cand["top_y"],
                    "bottom": cand["top_y"] + 15.0
                })
                global_img_counter += 1
        except Exception as img_err:
            print(f"[DEBUG] PDFModule: Error extracting images on page {page_idx + 1}: {img_err}", file=sys.stderr)

        return page_images, global_img_counter

    # =========================================================================
    # MULTI-PAGE TABLE STITCHING
    # =========================================================================

    def _stitch_multipage_tables(self, doc_elements: list[dict]) -> None:
        """Stitches adjacent tables split across page breaks into a unified table."""
        changed = True
        while changed:
            changed = False
            for idx in range(len(doc_elements) - 1):
                el1 = doc_elements[idx]
                if el1["type"] != "table":
                    continue
                    
                next_table_idx = -1
                has_page_break = False
                accumulated_gap_text_len = 0
                for j in range(idx + 1, len(doc_elements)):
                    el_next = doc_elements[j]
                    if el_next["type"] == "table":
                        next_table_idx = j
                        break
                    elif el_next["type"] == "page_break":
                        has_page_break = True
                        continue
                    elif el_next["type"] == "text":
                        text_content = el_next["content"].strip()
                        if text_content:
                            accumulated_gap_text_len += len(text_content)
                    else:
                        accumulated_gap_text_len += 9999
                        
                if next_table_idx != -1 and has_page_break and accumulated_gap_text_len < 150:
                    el3 = doc_elements[next_table_idx]
                    t1_cols = el1["columns"]
                    t2_cols = el3["columns"]
                    t2_rows = el3["content"]
                    
                    mapped_rows = []
                    for row in t2_rows:
                        mapped = self._map_row_to_parent_columns(row, t2_cols, t1_cols)
                        mapped_rows.append(mapped)
                        
                    if el1["content"] and mapped_rows:
                        parent_last_row = el1["content"][-1]
                        child_first_row = mapped_rows[0]
                        if self._should_merge_first_row(parent_last_row, child_first_row):
                            for col_idx in range(len(parent_last_row)):
                                val_T2 = child_first_row[col_idx]
                                if val_T2:
                                    if parent_last_row[col_idx]:
                                        parent_last_row[col_idx] = parent_last_row[col_idx] + " " + val_T2
                                    else:
                                        parent_last_row[col_idx] = val_T2
                            mapped_rows.pop(0)
                    
                    el1["content"].extend(mapped_rows)
                    del doc_elements[idx + 1 : next_table_idx + 1]
                    changed = True
                    break

    # =========================================================================
    # MAIN DOCUMENT INGESTION (PDF -> Markdown)
    # =========================================================================

    def load_to_markdown(self, file_path: str) -> str:
        """
        Extracts PDF content to clean Markdown text with table structure recognition using pdfplumber.
        Supports table stitching across page breaks and image deduplication.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            # pyrefly: ignore [missing-import]
            import pdfplumber
            
            settings = {
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "explicit_vertical_lines": [],
                "explicit_horizontal_lines": [],
                "snap_tolerance": 3,
                "join_tolerance": 3,
                "edge_min_length": 3,
                "min_words_vertical": 3,
                "min_words_horizontal": 1,
                "intersection_tolerance": 3,
            }

            fitz_doc = None
            try:
                fitz_doc = fitz.open(file_path)
            except Exception as e:
                print(f"[DEBUG] PyMuPDF (fitz) open failed: {e}", file=sys.stderr)

            doc_elements = []
            global_img_counter = 1

            with pdfplumber.open(file_path) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_fitz = fitz_doc[page_idx] if fitz_doc and page_idx < len(fitz_doc) else None
                    page_images = []

                    if page_fitz:
                        try:
                            smasks_on_page = {
                                info[1] for info in page_fitz.get_images(full=True) if info[1] > 0
                            }
                        except Exception:
                            smasks_on_page = set()

                        page_images, global_img_counter = self._extract_page_images(
                            page, page_idx, page_fitz, smasks_on_page, global_img_counter
                        )

                    tables = sorted(page.find_tables(table_settings=settings), key=lambda t: t.bbox[1])
                    block_regions = []
                    for t in tables:
                        t_data = t.extract()
                        if not t_data or not any(r and any(c and str(c).strip() for c in r) for r in t_data):
                            continue

                        # Guard: Reject 1-column pseudo-tables (e.g. Slide 27 page frame with standalone page number)
                        num_cols = max(len(r) for r in t_data if r)
                        if num_cols < 2:
                            print(f"[DEBUG] PDFModule: Skipped 1-column frame box on page {page_idx + 1} — fallback to rich text")
                            continue

                        # Check if table has broken/missing cells (e.g. Slide 32 with unextracted shaded cell)
                        has_broken_cell = False
                        for row in t_data:
                            if row and any(c and len(str(c).strip()) > 20 for c in row):
                                if any(not c or not str(c).strip() for c in row):
                                    has_broken_cell = True
                                    break
                        if has_broken_cell:
                            print(f"[DEBUG] PDFModule: Skipped table with missing/unextracted cell on page {page_idx + 1} — fallback to rich text")
                            continue

                        extracted_title, final_t_data = self._restructure_card_table_if_needed(t_data)
                        if final_t_data is None:
                            print(f"[DEBUG] PDFModule: Skipped broken/diagram pseudo-table on page {page_idx + 1} — fallback to rich text")
                            continue

                        # Guard: Reject 1-column pseudo-tables (e.g. Slide 27 page number box)
                        cleaned_table = self._clean_table(final_t_data)
                        if not cleaned_table or len(cleaned_table) < 2 or len(cleaned_table[0]) < 2:
                            print(f"[DEBUG] PDFModule: Skipped 1-column frame box on page {page_idx + 1} — fallback to rich text")
                            continue

                        # Linguistic & Structural Quality Guard: Reject illustration diagram pseudo-tables
                        # (e.g. Sinking Ship where text is single-letter rotated noise or header is a full paragraph)
                        row0 = [str(c).strip() for c in cleaned_table[0] if c]
                        has_paragraph_header = any(len(h.split()) > 15 for h in row0)

                        all_table_text = " ".join(str(c) for r in cleaned_table for c in r if c)
                        table_words = all_table_text.split()
                        is_scrambled_noise = False
                        if table_words:
                            single_short = sum(1 for w in table_words if len(w) <= 2)
                            avg_len = sum(len(w) for w in table_words) / len(table_words)
                            if single_short / len(table_words) > 0.35 and avg_len < 3.5:
                                is_scrambled_noise = True

                        if has_paragraph_header or is_scrambled_noise:
                            print(f"[DEBUG] PDFModule: Skipped illustration diagram pseudo-table on page {page_idx + 1} — fallback to rich text")
                            continue

                        bx0, btop, bx1, bbottom = t.bbox
                        block_regions.append({
                            "type": "table",
                            "data": t,
                            "extracted": final_t_data,
                            "extracted_title": extracted_title,
                            "top": btop,
                            "bottom": bbottom
                        })

                    block_regions.sort(key=lambda b: b["top"])

                    current_y = 0.0
                    for region in block_regions:
                        rtop = region["top"]
                        rbottom = region["bottom"]

                        if rtop > current_y + 2.0:
                            cropped = page.crop((0, max(0.0, current_y), page.width, min(page.height, rtop)))
                            text_slice = self._extract_rich_text(cropped)
                            if text_slice:
                                doc_elements.append({"type": "text", "content": text_slice})

                        t = region["data"]
                        if region.get("extracted_title"):
                            doc_elements.append({
                                "type": "text",
                                "content": f"# {region['extracted_title']}"
                            })
                        doc_elements.append({
                            "type": "table",
                            "content": region.get("extracted", t.extract()),
                            "bbox": t.bbox,
                            "columns": t.columns
                        })
                        current_y = max(current_y, rbottom)

                    if current_y < page.height - 2.0:
                        cropped = page.crop((0, max(0.0, current_y), page.width, page.height))
                        text_slice = self._extract_rich_text(cropped)
                        if text_slice:
                            doc_elements.append({"type": "text", "content": text_slice})

                    for img_obj in page_images:
                        doc_elements.append({
                            "type": "image",
                            "content": img_obj["content"]
                        })
                            
                    if page_idx < len(pdf.pages) - 1:
                        doc_elements.append({"type": "page_break", "content": "\n\n---\n\n"})

            if fitz_doc:
                try:
                    fitz_doc.close()
                except Exception:
                    pass

            self._stitch_multipage_tables(doc_elements)

            output_parts = []
            for el in doc_elements:
                if el["type"] == "text":
                    output_parts.append(el["content"].strip())
                elif el["type"] == "table":
                    md_table = self._format_markdown_table(el["content"])
                    if md_table:
                        output_parts.append(md_table)
                elif el["type"] == "image":
                    output_parts.append(el["content"].strip())
                elif el["type"] == "page_break":
                    output_parts.append(el["content"])
                    
            if not output_parts:
                return "*(Empty PDF)*"
            return "\n\n".join(output_parts)
            
        except Exception as e:
            print(f"[DEBUG] pdfplumber table extraction failed: {e}. Falling back to markitdown.", file=sys.stderr)
            try:
                # pyrefly: ignore [missing-import]
                from markitdown import MarkItDown
                md = MarkItDown()
                result = md.convert(file_path)
                if not result or not result.text_content:
                    return "*(Empty PDF)*"
                return result.text_content
            except Exception:
                raise RuntimeError(f"PDF Ingestion Error: Failed to extract text layer from PDF file. Detail: {str(e)}")

    # =========================================================================
    # EXPORT (Markdown -> PDF)
    # =========================================================================

    def _prepare_pdf_css(self, font_dir: str = "C:/Windows/Fonts") -> tuple[str, str, str]:
        """Builds CSS with system Unicode fonts and typography styling."""
        font_face_css = ""
        font_family_name = "'Segoe UI', Arial, sans-serif"

        if os.path.exists(os.path.join(font_dir, "arial.ttf")):
            font_dir_slash = font_dir.replace("\\", "/")
            font_face_css += f"""
            @font-face {{
                font-family: 'AppUnicodeFont';
                src: url('{font_dir_slash}/arial.ttf');
            }}
            @font-face {{
                font-family: 'AppUnicodeFont';
                font-weight: bold;
                src: url('{font_dir_slash}/arialbd.ttf');
            }}
            @font-face {{
                font-family: 'AppUnicodeFont';
                font-style: italic;
                src: url('{font_dir_slash}/ariali.ttf');
            }}
            @font-face {{
                font-family: 'AppUnicodeFont';
                font-weight: bold;
                font-style: italic;
                src: url('{font_dir_slash}/arialbi.ttf');
            }}
            """
            font_family_name = "'AppUnicodeFont', sans-serif"

        mono_font_family = "'Consolas', 'Courier New', monospace"
        if os.path.exists(os.path.join(font_dir, "consola.ttf")):
            font_dir_slash = font_dir.replace("\\", "/")
            font_face_css += f"""
            @font-face {{
                font-family: 'AppMonoFont';
                src: url('{font_dir_slash}/consola.ttf');
            }}
            @font-face {{
                font-family: 'AppMonoFont';
                font-weight: bold;
                src: url('{font_dir_slash}/consolab.ttf');
            }}
            """
            mono_font_family = "'AppMonoFont', 'Consolas', monospace"

        css = (font_face_css + """
        @page {
            size: A4;
            margin: 2cm 2.5cm 2.5cm 2.5cm;
        }
        body {
            font-family: __FONT_FAMILY__;
            font-size: 11pt;
            line-height: 1.6;
            color: #24292f;
            margin: 0;
            padding: 0;
        }
        h1, h2, h3, h4, h5, h6 {
            font-family: __FONT_FAMILY__;
            color: #0f172a;
            font-weight: bold;
            margin-top: 1.4em;
            margin-bottom: 0.6em;
            line-height: 1.25;
        }
        h1 {
            font-size: 20pt;
            border-bottom: 1px solid #d0d7de;
            padding-bottom: 0.3em;
        }
        h2 {
            font-size: 16pt;
            border-bottom: 1px solid #d0d7de;
            padding-bottom: 0.2em;
        }
        h3 { font-size: 13pt; }
        h4 { font-size: 11pt; }
        p {
            margin-top: 0;
            margin-bottom: 10px;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin-top: 12px;
            margin-bottom: 16px;
            font-size: 10.5pt;
            page-break-inside: avoid;
        }
        th, td {
            border: 1px solid #d0d7de;
            padding: 6px 10px;
            text-align: left;
            vertical-align: top;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        th p, td p {
            margin: 0;
            padding: 0;
        }
        th ul, td ul, th ol, td ol {
            margin: 4px 0;
            padding-left: 18px;
        }
        th {
            background-color: #f6f8fa;
            font-weight: 600;
            color: #1f2328;
        }
        tr:nth-child(even) {
            background-color: #fcfcfc;
        }
        code {
            font-family: __MONO_FONT__;
            font-size: 10.5pt;
            color: #0550ae;
            vertical-align: 1px;
            background-color: #f6f8fa;
            padding: 0 3px;
        }
        em, i {
            font-style: italic;
        }
        td code, th code {
            font-family: __MONO_FONT__;
            font-size: 10pt;
            vertical-align: 3.4px;
            color: #0550ae;
            background-color: #f6f8fa;
            padding: 0 3px;
        }
        td em, th em, td i, th i {
            font-style: italic;
            vertical-align: 3.15px;
        }
        pre {
            background-color: #f6f8fa;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            padding: 12px;
            overflow-x: auto;
            margin-top: 10px;
            margin-bottom: 14px;
            page-break-inside: avoid;
        }
        pre code {
            background-color: transparent;
            padding: 0;
            border-radius: 0;
            color: #24292f;
            line-height: 1.4;
        }
        blockquote {
            margin: 12px 0;
            padding: 0 14px;
            color: #57606a;
            border-left: 4px solid #d0d7de;
        }
        ul, ol {
            padding-left: 24px;
            margin-top: 0;
            margin-bottom: 12px;
        }
        li {
            margin-bottom: 4px;
        }
        del {
            text-decoration: line-through;
            color: #6e7781;
        }
        a {
            color: #0969da;
            text-decoration: none;
        }
        img {
            max-width: 100%;
            height: auto;
            border-radius: 4px;
        }
        p[align="center"], div[align="center"], center {
            text-align: center;
        }
        p[align="right"], div[align="right"] {
            text-align: right;
        }
        p[align="left"], div[align="left"] {
            text-align: left;
        }
        p[align="center"] img, div[align="center"] img, center img, img[align="center"] {
            display: inline-block;
            margin-left: auto;
            margin-right: auto;
        }
        p[align="right"] img, div[align="right"] img, img[align="right"] {
            display: inline-block;
            margin-left: auto;
            margin-right: 0;
        }
        p[align="left"] img, div[align="left"] img, img[align="left"] {
            display: inline-block;
            margin-left: 0;
            margin-right: auto;
        }
        hr {
            border: 0;
            border-top: 1px solid #d0d7de;
            margin: 20px 0;
        }
        """).replace("__FONT_FAMILY__", font_family_name).replace("__MONO_FONT__", mono_font_family)

        return css, font_family_name, mono_font_family

    def save_from_markdown(self, markdown_content: str, out_path: str) -> str:
        """Converts Markdown text to formatted PDF document using markdown-pdf."""
        import shutil
        try:
            from src.core.converters import prepare_markdown_for_export
            markdown_content = prepare_markdown_for_export(markdown_content)

            from src.services.media_asset_manager import MediaAssetManager
            asset_mgr = MediaAssetManager()
            session_dir = asset_mgr.get_session_dir()
            os.makedirs(session_dir, exist_ok=True)

            out_dir = os.path.dirname(out_path) if out_path else None

            def prepare_image(src_url: str) -> str:
                if not src_url or src_url.startswith("http://") or src_url.startswith("https://"):
                    return src_url

                resolved = asset_mgr.resolve_uri(src_url, base_dir=out_dir)
                if not os.path.isabs(resolved) and out_dir:
                    possible_path = os.path.join(out_dir, resolved)
                    if os.path.exists(possible_path):
                        resolved = possible_path

                if not os.path.isabs(resolved):
                    possible_path = os.path.join(session_dir, resolved)
                    if os.path.exists(possible_path):
                        resolved = possible_path

                resolved = os.path.normpath(os.path.abspath(resolved))

                if os.path.exists(resolved) and os.path.isfile(resolved):
                    filename = os.path.basename(resolved)
                    dest = os.path.join(session_dir, filename)
                    if os.path.normpath(resolved) != os.path.normpath(dest):
                        try:
                            shutil.copy2(resolved, dest)
                        except Exception as e:
                            print(f"[DEBUG] PDFModule: Failed to copy image {resolved} to {dest}: {e}")
                    return filename
                return src_url

            def resolve_img_markdown(match):
                alt = match.group(1)
                src = match.group(2)
                new_src = prepare_image(src)
                return f"![{alt}]({new_src})"

            def resolve_img_html(match):
                prefix = match.group(1)
                src = match.group(2)
                suffix = match.group(3)
                new_src = prepare_image(src)
                return f'{prefix}{new_src}{suffix}'

            if "!" in markdown_content or "<img" in markdown_content:
                processed_md = re.sub(r'!\[([^\]]*)\]\((.+?\.(?:png|jpg|jpeg|gif|svg|webp|bmp|ico)|https?://\S+|@media/\S+?|[^\n)]+)\)', resolve_img_markdown, markdown_content, flags=re.IGNORECASE)
                processed_md = re.sub(r'(<img\s+[^>]*?src=["\'])([^"\']+)(["\'][^>]*?>)', resolve_img_html, processed_md, flags=re.IGNORECASE)
            else:
                processed_md = markdown_content

            if "~~" in processed_md:
                html_content = re.sub(r"~~(.*?)~~", r"<del>\1</del>", processed_md)
            else:
                html_content = processed_md

            from markdown_pdf import MarkdownPdf, Section

            css, _, _ = self._prepare_pdf_css()

            pdf = MarkdownPdf(toc_level=2)
            pdf.add_section(Section(html_content, root=session_dir), user_css=css)

            out_dir = os.path.dirname(out_path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)

            if hasattr(pdf, "toc") and pdf.toc:
                try:
                    min_lvl = pdf.toc[0][0]
                    if min_lvl > 1:
                        offset = min_lvl - 1
                        pdf.toc = [(max(1, item[0] - offset), item[1], item[2]) for item in pdf.toc]
                except Exception:
                    pass

            try:
                pdf.save(out_path)
            except Exception as save_err:
                if "hierarchy level" in str(save_err) or "toc" in str(save_err).lower():
                    pdf.toc = []
                    pdf.save(out_path)
                else:
                    raise save_err

            return f"Exported successfully to {os.path.basename(out_path)}"
        except Exception as e:
            raise RuntimeError(f"PDF Export Error: Failed to generate PDF document. Detail: {str(e)}")


ModuleRegistry.register(PDFModule())
