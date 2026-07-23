import os
import sys
import re
from src.core.base_module import BaseDocumentModule
from src.core.registry import ModuleRegistry

class PDFModule(BaseDocumentModule):
    @property
    def name(self) -> str:
        return "PDF"

    @property
    def file_extensions(self) -> list[str]:
        return [".pdf"]

    @property
    def required_dependencies(self) -> list[str]:
        return ["markitdown", "pdfplumber", "markdown-pdf", "pymupdf", "Pillow"]

    def load_to_markdown(self, file_path: str) -> str:
        """
        Extracts PDF content to clean Markdown text with table structure recognition using pdfplumber.
        
        Supports table stitching across page breaks when tables are contiguous 
        (separated only by page breaks or empty space/headers) and merges continuation cells.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            # pyrefly: ignore [missing-import]
            import pdfplumber
            
            def merge_non_overlapping_columns(rows):
                if not rows or len(rows) < 2:
                    return rows
                num_cols = len(rows[0])
                cols = list(range(num_cols))
                changed = True
                while changed:
                    changed = False
                    for i in range(len(cols) - 1):
                        c1 = cols[i]
                        c2 = cols[i+1]
                        overlap = False
                        for row in rows:
                            if row[c1] and row[c2]:
                                overlap = True
                                break
                        if not overlap:
                            for row in rows:
                                if row[c2]:
                                    row[c1] = row[c2]
                            cols.pop(i+1)
                            changed = True
                            break
                rebuilt = []
                for row in rows:
                    rebuilt.append([row[c] for c in cols])
                return rebuilt

            def clean_table(table_data):
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
                merged = merge_non_overlapping_columns(cleaned)
                if not merged:
                    return []
                num_cols = len(merged[0])
                active_cols = []
                for col_idx in range(num_cols):
                    has_val = False
                    for row in merged:
                        if row[col_idx]:
                            has_val = True
                            break
                    if has_val:
                        active_cols.append(col_idx)
                if not active_cols:
                    return []
                rebuilt = []
                for row in merged:
                    rebuilt.append([row[idx] for idx in active_cols])
                return rebuilt

            def map_row_to_parent_columns(t2_row, t2_cols, t1_cols):
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

            def should_merge_first_row(last_row, first_row):
                if len(last_row) == len(first_row) and len(first_row) > 1:
                    if not first_row[0]:
                        # Case A: Last row of parent has empty cell where first row of child has content
                        for c in range(1, len(first_row)):
                            if not last_row[c] and first_row[c]:
                                return True
                        # Case B: Both have content in the last column but parent cell does not end with sentence punctuation
                        if last_row[-1] and first_row[-1]:
                            last_char = last_row[-1].strip()[-1] if last_row[-1].strip() else ""
                            if last_char not in (".", "!", "?", ":"):
                                return True
                return False

            def format_markdown_table(table_data):
                cleaned = clean_table(table_data)
                if not cleaned:
                    return ""
                headers = cleaned[0]
                rows = cleaned[1:]
                parts = []
                parts.append("| " + " | ".join(h.replace("\n", "<br>").replace("|", "\\|") for h in headers) + " |")
                parts.append("| " + " | ".join("---" for _ in headers) + " |")
                for r in rows:
                    parts.append("| " + " | ".join(cell.replace("\n", "<br>").replace("|", "\\|") for cell in r) + " |")
                return "\n".join(parts)

            def _extract_rich_text(cropped_page):
                chars = cropped_page.chars
                if not chars:
                    return ""
                
                # Sort characters by top coordinate first
                chars_sorted = sorted(chars, key=lambda c: (c["top"], c["x0"]))
                
                # Group characters into lines using a tolerance of 3 pixels
                lines = []
                current_line = []
                current_top = None
                
                for char in chars_sorted:
                    top = char["top"]
                    if current_top is None:
                        current_top = top
                        current_line.append(char)
                    elif abs(top - current_top) <= 3:
                        current_line.append(char)
                    else:
                        lines.append(current_line)
                        current_line = [char]
                        current_top = top
                if current_line:
                    lines.append(current_line)
                
                # Determine minimum left x0 coordinate across non-empty lines
                valid_lines_x0 = [l[0]["x0"] for l in lines if l and any(c.get("text", "").strip() for c in l)]
                min_x0 = min(valid_lines_x0) if valid_lines_x0 else 0

                import re
                UNICODE_BULLET_SET = r"[\u2022\u2043\u25e6\u25fe\u25aa\u25ab\u25cf\u25cb\u25c6\u25c7\u27a2\u25ba\u25b8\uf0b7\uf0a7\uf0a8\uf0d8\uf0be\uf0fc\uf076\uf0d1\uf0de\uf02d\u25a0\u25a1•⁃◦▪▫●○◆◇➢►▸ï‚·]"
                BULLET_PREFIX_RE = re.compile(rf"^(\*{{1,3}}|_{{1,3}})?\s*(?:{UNICODE_BULLET_SET}\s*|[–—]\s+|[-\*\+]\s+)(\1)?\s*")
                ORDERED_PREFIX_RE = re.compile(r"^(\*{{1,3}}|_{{1,3}})?\s*(?:\(?(\d+|[a-zA-Z]|[ivxlcdmIVXLCDM]+)[\.\)]|\d+(?:\.\d+)+\.?)\s*(\1)?\s*")

                def strip_bullet_prefix(text):
                    m = BULLET_PREFIX_RE.match(text)
                    if m:
                        return text[m.end():]
                    return text

                def strip_ordered_prefix(text):
                    m = ORDERED_PREFIX_RE.match(text)
                    if m:
                        p_val = m.group(2)
                        if is_valid_ordered_prefix(p_val):
                            return p_val, text[m.end():]
                    return None, text

                def is_valid_ordered_prefix(prefix_val):
                    if not prefix_val:
                        return False
                    if prefix_val.isdigit():
                        return int(prefix_val) < 100
                    p = prefix_val.lower()
                    if len(p) == 1 and p.isalpha():
                        return True
                    valid_roman = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
                                   "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx"}
                    return p in valid_roman

                line_items_temp = []
                bullet_x0_list = []

                for line in lines:
                    line.sort(key=lambda c: c["x0"])
                    line_x0 = line[0]["x0"] if line else min_x0
                    line_top = line[0]["top"] if line else 0
                    
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
                        
                    raw_line_text = "".join(formatted_runs).strip()
                    if not raw_line_text:
                        continue

                    is_heading = avg_size >= 12.5
                    is_bullet = False
                    is_ordered = False
                    cleaned_text = raw_line_text
                    prefix_val = None

                    if not is_heading:
                        if BULLET_PREFIX_RE.match(raw_line_text):
                            is_bullet = True
                            cleaned_text = strip_bullet_prefix(raw_line_text)
                            bullet_x0_list.append(line_x0)
                        else:
                            p_val, c_text = strip_ordered_prefix(raw_line_text)
                            if p_val and (not p_val.isdigit() or int(p_val) < 1000):
                                is_ordered = True
                                prefix_val = p_val
                                cleaned_text = c_text
                                bullet_x0_list.append(line_x0)

                    line_items_temp.append({
                        "raw": raw_line_text,
                        "cleaned": cleaned_text,
                        "prefix_val": prefix_val,
                        "top": line_top,
                        "x0": line_x0,
                        "size": avg_size,
                        "is_heading": is_heading,
                        "is_bullet": is_bullet,
                        "is_ordered": is_ordered,
                        "is_list_item": is_bullet or is_ordered
                    })

                min_bullet_x0 = min(bullet_x0_list) if bullet_x0_list else min_x0

                line_items = []
                for item in line_items_temp:
                    delta_x = item["x0"] - min_bullet_x0
                    if delta_x < 12:
                        indent = ""
                    elif 12 <= delta_x < 28:
                        indent = "  "
                    elif 28 <= delta_x < 44:
                        indent = "    "
                    else:
                        indent = "      "

                    normalized_text = item["raw"]
                    if item["is_bullet"]:
                        normalized_text = f"{indent}- {item['cleaned']}"
                    elif item["is_ordered"]:
                        normalized_text = f"{indent}{item['prefix_val']}. {item['cleaned']}"
                    elif item["is_heading"]:
                        if item["size"] >= 20:
                            normalized_text = f"# {item['raw']}"
                        elif 16 <= item["size"] < 20:
                            normalized_text = f"## {item['raw']}"
                        elif 12.5 <= item["size"] < 16:
                            normalized_text = f"### {item['raw']}"

                    item["text"] = normalized_text
                    line_items.append(item)

                # Combine wrapped continuation lines for list items and paragraphs
                line_texts = []
                for idx, item in enumerate(line_items):
                    if not line_texts:
                        line_texts.append(item["text"])
                        continue
                    
                    if line_text:
                        # Prepend heading tags if the line has larger text size
                        if avg_size >= 20:
                            line_text = f"# {re.sub(r'\*{2,3}', '', line_text)}"
                        elif 16 <= avg_size < 20:
                            line_text = f"## {re.sub(r'\*{2,3}', '', line_text)}"
                        elif 12.5 <= avg_size < 16:
                            line_text = f"### {re.sub(r'\*{2,3}', '', line_text)}"
                        else:
                            # Repair broken/fragmented bold tags across accent characters
                            for _ in range(3):
                                line_text = re.sub(r'\*\*(.*?)\*\*([^\s\*]{1,3})\*\*(.*?)\*\*', r'**\1\2\3**', line_text)
                                line_text = re.sub(r'\*\*(.*?)\*\*\s*\*\*(.*?)\*\*', r'**\1 \2**', line_text)
                            break
                rebuilt = []
                for row in rows:
                    rebuilt.append([row[c] for c in cols])
                return rebuilt

            def clean_table(table_data):
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
                merged = merge_non_overlapping_columns(cleaned)
                if not merged:
                    return []
                num_cols = len(merged[0])
                active_cols = []
                for col_idx in range(num_cols):
                    has_val = False
                    for row in merged:
                        if row[col_idx]:
                            has_val = True
                            break
                    if has_val:
                        active_cols.append(col_idx)
                if not active_cols:
                    return []
                rebuilt = []
                for row in merged:
                    rebuilt.append([row[idx] for idx in active_cols])
                return rebuilt

            def map_row_to_parent_columns(t2_row, t2_cols, t1_cols):
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

            def should_merge_first_row(last_row, first_row):
                if len(last_row) == len(first_row) and len(first_row) > 1:
                    if not first_row[0]:
                        # Case A: Last row of parent has empty cell where first row of child has content
                        for c in range(1, len(first_row)):
                            if not last_row[c] and first_row[c]:
                                return True
                        # Case B: Both have content in the last column but parent cell does not end with sentence punctuation
                        if last_row[-1] and first_row[-1]:
                            last_char = last_row[-1].strip()[-1] if last_row[-1].strip() else ""
                            if last_char not in (".", "!", "?", ":"):
                                return True
                return False

            def format_markdown_table(table_data):
                cleaned = clean_table(table_data)
                if not cleaned:
                    return ""
                headers = cleaned[0]
                rows = cleaned[1:]
                parts = []
                parts.append("| " + " | ".join(h.replace("\n", "<br>").replace("|", "\\|") for h in headers) + " |")
                parts.append("| " + " | ".join("---" for _ in headers) + " |")
                for r in rows:
                    parts.append("| " + " | ".join(cell.replace("\n", "<br>").replace("|", "\\|") for cell in r) + " |")
                return "\n".join(parts)

            def _extract_rich_text(cropped_page):
                chars = cropped_page.chars
                if not chars:
                    return ""
                
                # Sort characters by top coordinate first
                chars_sorted = sorted(chars, key=lambda c: (c["top"], c["x0"]))
                
                # Group characters into lines using a tolerance of 3 pixels
                lines = []
                current_line = []
                current_top = None
                
                for char in chars_sorted:
                    top = char["top"]
                    if current_top is None:
                        current_top = top
                        current_line.append(char)
                    elif abs(top - current_top) <= 3:
                        current_line.append(char)
                    else:
                        lines.append(current_line)
                        current_line = [char]
                        current_top = top
                if current_line:
                    lines.append(current_line)
                    
                line_texts = []
                for line in lines:
                    # Sort characters on the line from left to right
                    line.sort(key=lambda c: c["x0"])
                    
                    # Merge characters into runs that share the same font properties
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
                            # Check distance to previous character to insert spaces
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
                        
                    # Calculate average line size for heading detection
                    avg_size = total_size / char_count if char_count > 0 else 10
                    
                    # Format runs into markdown syntax
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
                    
                    if line_text:
                        # Prepend heading tags if the line has larger text size
                        if avg_size >= 20:
                            line_text = f"# {re.sub(r'\*{2,3}', '', line_text)}"
                        elif 16 <= avg_size < 20:
                            line_text = f"## {re.sub(r'\*{2,3}', '', line_text)}"
                        elif 12.5 <= avg_size < 16:
                            line_text = f"### {re.sub(r'\*{2,3}', '', line_text)}"
                        else:
                            # Repair broken/fragmented bold tags across accent characters
                            for _ in range(3):
                                line_text = re.sub(r'\*\*(.*?)\*\*([^\s\*]{1,3})\*\*(.*?)\*\*', r'**\1\2\3**', line_text)
                                line_text = re.sub(r'\*\*(.*?)\*\*\s*\*\*(.*?)\*\*', r'**\1 \2**', line_text)
                            
                    line_texts.append(line_text)
                    
                    # Check if current item is a genuine continuation line of the previous list item
                    is_continuation = (
                        prev_item["is_list_item"] and 
                        not item["is_list_item"] and 
                        not item["is_heading"] and 
                        gap_y <= normal_gap and 
                        item["x0"] > min_x0 + 10 and
                        item["x0"] >= prev_item["x0"]
                    )

                    if is_continuation:
                        if prev_item["is_list_item"] and not prev_item["cleaned"].strip():
                            # Standalone bullet symbol on its own line: merge cleanly with 1 space
                            line_texts[-1] = line_texts[-1].rstrip() + " " + item["raw"].lstrip()
                        else:
                            line_texts[-1] += " " + item["raw"].strip()
                    else:
                        # If transitioning from a list block to a non-list paragraph/sub-heading, insert a blank line separator
                        if prev_item["is_list_item"] and not item["is_list_item"] and not item["is_heading"]:
                            line_texts.append("")
                        line_texts.append(item["text"])

                return "\n".join(line_texts)

            from src.services.media_asset_manager import MediaAssetManager
            asset_mgr = MediaAssetManager()

            import fitz
            fitz_doc = None
            try:
                fitz_doc = fitz.open(file_path)
            except Exception as fitz_err:
                print(f"[DEBUG] PDFModule: PyMuPDF open failed: {fitz_err}", file=sys.stderr)

            doc_elements = []
            settings = {"snap_tolerance": 10, "join_tolerance": 10}
            
            with pdfplumber.open(file_path) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_images = []
                    if fitz_doc and page_idx < len(fitz_doc):
                        try:
                            page_fitz = fitz_doc[page_idx]
                            for img_idx, img_info in enumerate(page_fitz.get_images(full=True)):
                                xref = img_info[0]
                                extracted = fitz_doc.extract_image(xref)
                                if not extracted or not extracted.get("image"):
                                    continue
                                img_bytes = extracted["image"]
                                ext = extracted.get("ext", "png")

                                if len(img_bytes) < 300:
                                    continue

                                try:
                                    from PIL import Image as PILImage
                                    with PILImage.open(io.BytesIO(img_bytes)) as pil_img:
                                        if pil_img.width < 16 or pil_img.height < 16:
                                            continue
                                except Exception:
                                    pass

                                rects = page_fitz.get_image_rects(xref)
                                top_y = rects[0].y0 if rects else 0.0

                                filename = f"pdf_image_p{page_idx + 1}_{img_idx + 1}.{ext}"
                                uri = asset_mgr.register_image(img_bytes, filename)

                                page_images.append({
                                    "type": "image",
                                    "content": f"![Image {img_idx + 1}]({uri})",
                                    "top": top_y,
                                    "bottom": top_y + 15.0
                                })
                        except Exception as img_err:
                            print(f"[DEBUG] PDFModule: Error extracting images on page {page_idx + 1}: {img_err}", file=sys.stderr)

                    tables = sorted(page.find_tables(table_settings=settings), key=lambda t: t.bbox[1])
                    
                    block_regions = []
                    for t in tables:
                        bx0, btop, bx1, bbottom = t.bbox
                        block_regions.append({
                            "type": "table",
                            "data": t,
                            "top": btop,
                            "bottom": bbottom
                        })
                    for img_obj in page_images:
                        block_regions.append({
                            "type": "image",
                            "data": img_obj,
                            "top": img_obj["top"],
                            "bottom": img_obj["bottom"]
                        })

                    block_regions.sort(key=lambda b: b["top"])

                    current_y = 0.0
                    for region in block_regions:
                        rtop = region["top"]
                        rbottom = region["bottom"]

                        if rtop > current_y + 2.0:
                            cropped = page.crop((0, max(0.0, current_y), page.width, min(page.height, rtop)))
                            text_slice = _extract_rich_text(cropped)
                            if text_slice:
                                doc_elements.append({"type": "text", "content": text_slice})

                        if region["type"] == "table":
                            t = region["data"]
                            doc_elements.append({
                                "type": "table",
                                "content": t.extract(),
                                "bbox": t.bbox,
                                "columns": t.columns
                            })
                        elif region["type"] == "image":
                            doc_elements.append({
                                "type": "image",
                                "content": region["data"]["content"]
                            })

                        current_y = max(current_y, rbottom)

                    if current_y < page.height:
                        cropped = page.crop((0, max(0.0, current_y), page.width, page.height))
                        text_slice = _extract_rich_text(cropped)
                        if text_slice:
                            doc_elements.append({"type": "text", "content": text_slice})
                            
                    # Add page break marker (except for the last page)
                    if page_idx < len(pdf.pages) - 1:
                        doc_elements.append({"type": "page_break", "content": "\n\n---\n\n"})

            if fitz_doc:
                try:
                    fitz_doc.close()
                except Exception:
                    pass

            # STITCHING PROCESS
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
                            # Set an arbitrary high value to deliberately block stitching 
                            # if an unexpected or non-text element is found in the gap.
                            accumulated_gap_text_len += 9999
                            
                    if next_table_idx != -1 and has_page_break and accumulated_gap_text_len < 150:
                        el3 = doc_elements[next_table_idx]
                        t1_cols = el1["columns"]
                        t2_cols = el3["columns"]
                        t2_rows = el3["content"]
                        
                        mapped_rows = []
                        for row in t2_rows:
                            mapped = map_row_to_parent_columns(row, t2_cols, t1_cols)
                            mapped_rows.append(mapped)
                            
                        # Perform cell-continuation merge if needed
                        if el1["content"] and mapped_rows:
                            parent_last_row = el1["content"][-1]
                            child_first_row = mapped_rows[0]
                            if should_merge_first_row(parent_last_row, child_first_row):
                                for col_idx in range(len(parent_last_row)):
                                    val_T2 = child_first_row[col_idx]
                                    if val_T2:
                                        if parent_last_row[col_idx]:
                                            parent_last_row[col_idx] = parent_last_row[col_idx] + " " + val_T2
                                        else:
                                            parent_last_row[col_idx] = val_T2
                                mapped_rows.pop(0)
                        
                        el1["content"].extend(mapped_rows)
                        
                        # Remove elements between idx and next_table_idx
                        del doc_elements[idx + 1 : next_table_idx + 1]
                        changed = True
                        break

            # BUILD RENDERED OUTPUT
            output_parts = []
            for el in doc_elements:
                if el["type"] == "text":
                    output_parts.append(el["content"].strip())
                elif el["type"] == "table":
                    md_table = format_markdown_table(el["content"])
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
            # Print debug log before falling back
            print(f"[DEBUG] pdfplumber table extraction failed: {e}. Falling back to markitdown.", file=sys.stderr)
            try:
                # pyrefly: ignore [missing-import]
                from markitdown import MarkItDown
                md = MarkItDown()
                result = md.convert(file_path)
                if not result or not result.text_content:
                    return "*(Empty PDF)*"
                return result.text_content
            except Exception as inner_e:
                raise RuntimeError(f"PDF Ingestion Error: Failed to extract text layer from PDF file. Detail: {str(inner_e)}")

    def save_from_markdown(self, markdown_content: str, out_path: str) -> str:
        """Converts Markdown text to formatted PDF document using markdown-pdf."""
        import shutil
        import re
        try:
            from src.services.media_asset_manager import MediaAssetManager
            asset_mgr = MediaAssetManager()
            session_dir = asset_mgr.get_session_dir()
            os.makedirs(session_dir, exist_ok=True)

            def prepare_image(src_url: str) -> str:
                if not src_url or src_url.startswith("http://") or src_url.startswith("https://"):
                    return src_url

                resolved = asset_mgr.resolve_uri(src_url)
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
                return f'{prefix}src="{new_src}"{suffix}'

            processed_md = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', resolve_img_markdown, markdown_content)
            processed_md = re.sub(r'(<img\s+[^>]*?src=["\'])([^"\']+)(["\'][^>]*?>)', resolve_img_html, processed_md)

            # Pre-process Markdown: replace ~~text~~ with <del>text</del> for strikethrough support
            html_content = re.sub(r"~~(.*?)~~", r"<del>\1</del>", processed_md)

            from markdown_pdf import MarkdownPdf, Section

            font_dir = "C:/Windows/Fonts"
            font_face_css = ""
            font_family_name = "'Segoe UI', Arial, sans-serif"

            if os.path.exists(os.path.join(font_dir, "arial.ttf")):
                font_dir_slash = font_dir.replace("\\", "/")
                font_face_css = f"""
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

            css = (font_face_css + """
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
            }
            th, td {
                border: 1px solid #d0d7de;
                padding: 7px 12px;
                text-align: left;
                vertical-align: top;
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
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9.5pt;
                background-color: #f6f8fa;
                padding: 2px 6px;
                border-radius: 4px;
                color: #24292f;
            }
            pre {
                background-color: #f6f8fa;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 12px;
                overflow-x: auto;
                margin-top: 10px;
                margin-bottom: 14px;
            }
            pre code {
                background-color: transparent;
                padding: 0;
                border-radius: 0;
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
            hr {
                border: 0;
                border-top: 1px solid #d0d7de;
                margin: 20px 0;
            }
            """).replace("__FONT_FAMILY__", font_family_name)

            pdf = MarkdownPdf(toc_level=2)
            pdf.add_section(Section(html_content, root=session_dir), user_css=css)

            out_dir = os.path.dirname(out_path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)

            pdf.save(out_path)
            return f"Exported successfully to {os.path.basename(out_path)}"
        except Exception as e:
            raise RuntimeError(f"PDF Export Error: Failed to generate PDF document. Detail: {str(e)}")

ModuleRegistry.register(PDFModule())
