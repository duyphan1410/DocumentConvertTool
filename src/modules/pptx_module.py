"""
PowerPoint (.pptx) Document Module for DocumentConvertTool.
Converts PPTX slides to Markdown and Markdown to PPTX slides.
"""
import os
import re
import zipfile
from src.core.base_module import BaseDocumentModule
from src.core.registry import ModuleRegistry


class PPTXModule(BaseDocumentModule):
    @property
    def name(self) -> str:
        return "PowerPoint"

    @property
    def file_extensions(self) -> list[str]:
        return [".pptx"]

    @property
    def required_dependencies(self) -> list[str]:
        return ["python-pptx", "Pillow"]

    def load_to_markdown(self, file_path: str) -> str:
        """
        Extracts PowerPoint (.pptx) slides to clean Markdown text.
        Preserves titles (as ## headings), bullet levels, tables, pictures via MediaAssetManager,
        charts (as MD tables), and slide notes.
        Slides are separated strictly by '\\n\\n---\\n\\n'.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if not zipfile.is_zipfile(file_path):
            return "⚠️ File Validation Error: Invalid file. Please select a valid PPTX document."

        try:
            import pptx
            from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
            from src.core.converters import wrap_text_style
            from src.services.media_asset_manager import MediaAssetManager

            asset_mgr = MediaAssetManager()
            prs = pptx.Presentation(file_path)
            slide_markdowns = []

            def is_smartart_shape(shape) -> bool:
                """Checks if shape is SmartArt or GraphicFrame containing diagram XML."""
                try:
                    diag_enum = getattr(MSO_SHAPE_TYPE, "DIAGRAM", None)
                    if diag_enum is not None and getattr(shape, "shape_type", None) == diag_enum:
                        return True
                except Exception:
                    pass

                try:
                    xml_str = getattr(shape.element, "xml", "")
                    if "drawingml/2006/diagram" in xml_str or "dgm:" in xml_str:
                        return True
                except Exception:
                    pass
                return False

            def is_numbered_paragraph(paragraph) -> bool:
                """Checks if a python-pptx paragraph uses PowerPoint auto-numbering (buAutoNum)."""
                try:
                    pPr = getattr(getattr(paragraph, "_p", None), "pPr", None)
                    if pPr is not None:
                        xml_str = getattr(pPr, "xml", "")
                        if "buAutoNum" in xml_str:
                            return True
                        if hasattr(paragraph._p, "xpath") and paragraph._p.xpath("./a:pPr/a:buAutoNum"):
                            return True
                except Exception:
                    pass
                return False

            def flatten_shapes(shapes_iterable):
                """Recursively flattens group shapes and sorts them by top position."""
                flat = []
                sorted_items = sorted(shapes_iterable, key=lambda s: getattr(s, "top", 0) or 0)
                for s in sorted_items:
                    if hasattr(s, "shape_type") and s.shape_type == MSO_SHAPE_TYPE.GROUP:
                        if hasattr(s, "shapes"):
                            flat.extend(flatten_shapes(s.shapes))
                        else:
                            flat.append(s)
                    else:
                        flat.append(s)
                return flat

            for slide_idx, slide in enumerate(prs.slides, 1):
                slide_blocks = []
                all_shapes = flatten_shapes(slide.shapes)

                for shape in all_shapes:
                    # 1. Slide Title Detection
                    if getattr(shape, "is_placeholder", False):
                        try:
                            p_type = shape.placeholder_format.type
                            if p_type in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE):
                                if shape.has_text_frame and shape.text_frame.text and shape.text_frame.text.strip():
                                    title_text = shape.text_frame.text.strip().replace("\n", " ")
                                    slide_blocks.append(f"## {title_text}")
                                    continue
                        except Exception:
                            pass

                    # 2. Table extraction
                    if shape.has_table:
                        try:
                            table = shape.table
                            table_rows = []
                            for row in table.rows:
                                cell_texts = [cell.text.replace("\n", "<br>").strip() for cell in row.cells]
                                table_rows.append(f"| {' | '.join(cell_texts)} |")

                            if table_rows:
                                col_count = len(table.columns)
                                sep = f"| {' | '.join(['---'] * col_count)} |"
                                table_md = "\n".join([table_rows[0], sep] + table_rows[1:])
                                slide_blocks.append(table_md)
                                continue
                        except Exception as e:
                            print(f"[DEBUG] Table extraction error in PPTX: {e}")

                    # 3. Chart extraction -> Markdown Table
                    if shape.has_chart:
                        try:
                            chart = shape.chart
                            plots = chart.plots
                            if plots:
                                categories = [str(c) for c in plots[0].categories]
                                series_list = list(chart.series)

                                if categories and series_list:
                                    headers = ["Category"] + [s.name or f"Series {i+1}" for i, s in enumerate(series_list)]
                                    header_line = f"| {' | '.join(headers)} |"
                                    sep_line = f"| {' | '.join(['---'] * len(headers))} |"

                                    data_lines = []
                                    for c_idx, cat in enumerate(categories):
                                        row_vals = [cat]
                                        for s in series_list:
                                            vals = list(s.values)
                                            val_str = str(vals[c_idx]) if c_idx < len(vals) else ""
                                            row_vals.append(val_str)
                                        data_lines.append(f"| {' | '.join(row_vals)} |")

                                    chart_title = ""
                                    try:
                                        if getattr(chart, "has_title", False) and hasattr(chart, "chart_title"):
                                            tf = getattr(chart.chart_title, "text_frame", None)
                                            if tf and hasattr(tf, "paragraphs"):
                                                extracted_t = "\n".join(p.text for p in tf.paragraphs if p.text and p.text.strip()).strip()
                                                chart_title = extracted_t if extracted_t else "Tiêu đề Biểu đồ"
                                            else:
                                                chart_title = "Tiêu đề Biểu đồ"
                                    except Exception:
                                        pass

                                    chart_type_name = "column"
                                    try:
                                        c_type = getattr(chart, "chart_type", None)
                                        if c_type is not None:
                                            c_type_str = str(c_type).lower()
                                            if "bar" in c_type_str:
                                                chart_type_name = "bar"
                                            elif "pie" in c_type_str:
                                                chart_type_name = "pie"
                                            elif "line" in c_type_str:
                                                chart_type_name = "line"
                                    except Exception:
                                        pass

                                    legend_pos = ""
                                    try:
                                        if getattr(chart, "has_legend", False) and hasattr(chart, "legend"):
                                            pos_enum = getattr(chart.legend, "position", None)
                                            if pos_enum is not None:
                                                pos_str = str(pos_enum).lower()
                                                if "right" in pos_str:
                                                    legend_pos = "right"
                                                elif "top" in pos_str:
                                                    legend_pos = "top"
                                                elif "left" in pos_str:
                                                    legend_pos = "left"
                                                elif "bottom" in pos_str:
                                                    legend_pos = "bottom"
                                    except Exception:
                                        pass

                                    title_attr = f' title="{chart_title}"' if chart_title else ""
                                    legend_attr = f' legend="{legend_pos}"' if legend_pos else ""
                                    chart_md = f"<!-- chart: {chart_type_name}{title_attr}{legend_attr} -->\n" + "\n".join([header_line, sep_line] + data_lines)
                                    slide_blocks.append(chart_md)
                                    continue
                        except Exception as e:
                            print(f"[DEBUG] Chart extraction error in PPTX: {e}")
                            slide_blocks.append("*[Unsupported: Chart]*")
                            continue

                    # 4. Picture extraction
                    if (hasattr(shape, "shape_type") and shape.shape_type == MSO_SHAPE_TYPE.PICTURE) or hasattr(shape, "image"):
                        try:
                            image_blob = shape.image.blob
                            ext = getattr(shape.image, "ext", "png") or "png"
                            img_filename = f"pptx_slide{slide_idx}_img_{id(shape)}.{ext}"
                            virtual_uri = asset_mgr.register_image(image_blob, img_filename)
                            slide_blocks.append(f"![image]({virtual_uri})")
                            continue
                        except Exception as e:
                            print(f"[DEBUG] Picture extraction error in PPTX: {e}")

                    # 5. SmartArt detection & fallback
                    if is_smartart_shape(shape):
                        slide_blocks.append("*[Unsupported: SmartArt/Diagram]*")
                        continue

                    # 6. Text Frame / Paragraphs (Body text)
                    if shape.has_text_frame:
                        tf = shape.text_frame
                        para_lines = []
                        num_counters = {}
                        for paragraph in tf.paragraphs:
                            if not paragraph.text or not paragraph.text.strip():
                                continue

                            run_parts = []
                            for run in paragraph.runs:
                                if not run.text:
                                    continue
                                font = getattr(run, "font", None)
                                bold = getattr(font, "bold", None) if font else None
                                italic = getattr(font, "italic", None) if font else None
                                strike = getattr(font, "strike", None) if font else None
                                underline = getattr(font, "underline", None) if font else None

                                formatted = wrap_text_style(
                                    run.text,
                                    bold=bold,
                                    italic=italic,
                                    strike=strike,
                                    underline=underline
                                )
                                run_parts.append(formatted)

                            p_text = "".join(run_parts).strip()
                            if p_text:
                                lvl = getattr(paragraph, "level", 0) or 0
                                indent = "  " * lvl
                                is_num = is_numbered_paragraph(paragraph) or bool(re.match(r"^\d+\.\s+", p_text))
                                if is_num:
                                    num_counters[lvl] = num_counters.get(lvl, 0) + 1
                                    curr_num = num_counters[lvl]
                                    clean_p = re.sub(r"^\d+\.\s+", "", p_text)
                                    para_lines.append(f"{indent}{curr_num}. {clean_p}")
                                else:
                                    num_counters[lvl] = 0
                                    clean_p = re.sub(r"^•\s*", "", p_text)
                                    para_lines.append(f"{indent}- {clean_p}")

                        if para_lines:
                            slide_blocks.append("\n".join(para_lines))
                        continue

                    # Fallback for unknown shape types with text/content
                    if hasattr(shape, "text") and shape.text and shape.text.strip():
                        slide_blocks.append(shape.text.strip())

                # 7. Slide Notes Extraction (preserving bullets & numbering)
                if slide.has_notes_slide:
                    try:
                        notes_tf = slide.notes_slide.notes_text_frame
                        if notes_tf and notes_tf.text and notes_tf.text.strip():
                            notes_lines = []
                            num_counters_notes = {}
                            for p in notes_tf.paragraphs:
                                p_str = p.text.strip()
                                if not p_str:
                                    continue
                                lvl = getattr(p, "level", 0) or 0
                                indent = "  " * lvl
                                is_num = is_numbered_paragraph(p) or bool(re.match(r"^\d+\.\s+", p_str))
                                if is_num:
                                    num_counters_notes[lvl] = num_counters_notes.get(lvl, 0) + 1
                                    clean_p = re.sub(r"^\d+\.\s+", "", p_str)
                                    notes_lines.append(f"{indent}{num_counters_notes[lvl]}. {clean_p}")
                                else:
                                    num_counters_notes[lvl] = 0
                                    clean_p = re.sub(r"^•\s*", "", p_str)
                                    if clean_p.startswith("- "):
                                        notes_lines.append(f"{indent}{clean_p}")
                                    else:
                                        notes_lines.append(f"{indent}- {clean_p}")

                            if notes_lines:
                                slide_blocks.append("### Notes:\n" + "\n".join(notes_lines))
                    except Exception as ex:
                        print(f"[DEBUG] Slide notes extraction error: {ex}")

                slide_content = "\n\n".join(slide_blocks).strip()
                if not slide_content:
                    slide_content = f"*(Empty Slide {slide_idx})*"
                slide_markdowns.append(slide_content)

            # Join slides strictly with '\n\n---\n\n'
            return "\n\n---\n\n".join(slide_markdowns)

        except Exception as e:
            return f"⚠️ PPTX Conversion Error: {str(e)}"

    def save_from_markdown(self, markdown_content: str, out_path: str) -> str:
        """
        Converts Markdown text into a PowerPoint presentation (.pptx).
        Parses headings, bullet levels, bold/italic styles, tables, charts, images, and slide notes.
        Splits slides strictly by '\\n\\n---\\n\\n' markers.
        """
        try:
            import pptx
            from pptx.util import Inches, Pt
            from pptx.chart.data import CategoryChartData
            from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
            from src.services.media_asset_manager import MediaAssetManager

            asset_mgr = MediaAssetManager()
            prs = pptx.Presentation()
            # Set default 16:9 Widescreen aspect ratio (13.333 in x 7.5 in)
            prs.slide_width = Inches(13.333)
            prs.slide_height = Inches(7.5)
            blank_layout = prs.slide_layouts[6]  # Blank slide layout

            slide_blocks = [s.strip() for s in markdown_content.split("\n\n---\n\n") if s.strip()]

            if not slide_blocks:
                slide_blocks = [markdown_content.strip()]

            def parse_formatted_runs(paragraph, text: str, default_size=18):
                """Parses inline bold/italic/code markdown text and appends runs to PPTX paragraph."""
                tokens = re.split(r"(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*|`.*?`)", text)
                for token in tokens:
                    if not token:
                        continue
                    run = paragraph.add_run()
                    run.font.size = Pt(default_size)

                    if token.startswith("***") and token.endswith("***") and len(token) > 6:
                        run.text = token[3:-3]
                        run.font.bold = True
                        run.font.italic = True
                    elif token.startswith("**") and token.endswith("**") and len(token) > 4:
                        run.text = token[2:-2]
                        run.font.bold = True
                    elif token.startswith("*") and token.endswith("*") and len(token) > 2:
                        run.text = token[1:-1]
                        run.font.italic = True
                    elif token.startswith("`") and token.endswith("`") and len(token) > 2:
                        run.text = token[1:-1]
                        run.font.name = "Consolas"
                    else:
                        run.text = token

            for block in slide_blocks:
                # 1. Extract Slide Notes if present
                notes_text = None
                notes_match = re.search(r"(?:^|\n)### Notes:\s*\n(.*)$|(?:^|\n)Notes:\s*\n(.*)$", block, re.DOTALL)
                if notes_match:
                    notes_text = (notes_match.group(1) if notes_match.group(1) is not None else notes_match.group(2) or "").strip()
                    block = block[:notes_match.start()].strip()

                lines = block.split("\n")

                title_text = None
                content_lines = []

                for l in lines:
                    stripped = l.strip()
                    if not title_text and (stripped.startswith("# ") or stripped.startswith("## ")):
                        title_text = re.sub(r"^#+\s*", "", stripped)
                    elif re.match(r"^\*\s*\(?Empty Slide.*\)?\s*\*$", stripped, re.IGNORECASE):
                        continue
                    else:
                        content_lines.append(l)

                if title_text:
                    title_layout = prs.slide_layouts[5]  # Title Only layout
                    slide = prs.slides.add_slide(title_layout)
                    if hasattr(slide.shapes, "title") and slide.shapes.title:
                        slide.shapes.title.text = title_text
                    top_offset = Inches(1.6)
                    start_top_offset = Inches(1.6)
                else:
                    slide = prs.slides.add_slide(blank_layout)
                    top_offset = Inches(0.8)
                    start_top_offset = Inches(0.8)

                # Attach Slide Notes if present
                if notes_text:
                    try:
                        slide.notes_slide.notes_text_frame.text = notes_text
                    except Exception as ex:
                        print(f"[DEBUG] Failed to set slide notes: {ex}")

                # Overflow protection threshold
                max_slide_top = prs.slide_height - Inches(0.8)

                def ensure_space(required_height=Inches(1.0)):
                    nonlocal slide, top_offset, start_top_offset
                    if top_offset + required_height > max_slide_top and top_offset > start_top_offset:
                        print(f"[DEBUG] Slide content overflow warning: top_offset={top_offset} + {required_height} exceeds slide height, auto-creating continuation slide")
                        slide = prs.slides.add_slide(blank_layout)
                        top_offset = Inches(0.8)
                        start_top_offset = Inches(0.8)
                        if notes_text:
                            try:
                                slide.notes_slide.notes_text_frame.text = notes_text
                            except Exception:
                                pass

                # Process content lines (detecting tables, charts, images, bullet lists, paragraphs)
                i = 0
                pending_chart_type = None
                pending_chart_title = None
                pending_chart_legend = None

                while i < len(content_lines):
                    line = content_lines[i]
                    stripped = line.strip()

                    if not stripped:
                        i += 1
                        continue

                    # 1.5 Chart footprint comment detection <!-- chart: type title="..." legend="..." -->
                    chart_comment_match = re.match(
                        r"^<!--\s*chart:\s*(\w+)(?:.*?title=[\"'](.*?)[\"'])?(?:.*?legend=[\"'](.*?)[\"'])?\s*-->$",
                        stripped,
                        re.IGNORECASE
                    )
                    if chart_comment_match:
                        pending_chart_type = chart_comment_match.group(1).lower()
                        pending_chart_title = chart_comment_match.group(2) or ""
                        pending_chart_legend = chart_comment_match.group(3) or ""
                        i += 1
                        continue

                    # 2. Markdown Table or Chart Detection (| col1 | col2 |)
                    if stripped.startswith("|") and stripped.endswith("|"):
                        table_block = []
                        while i < len(content_lines) and content_lines[i].strip().startswith("|") and content_lines[i].strip().endswith("|"):
                            table_block.append(content_lines[i].strip())
                            i += 1

                        # Filter out separator row (| --- | --- |)
                        table_data_lines = [row for row in table_block if not re.match(r"^\|[\s\-:]+(\|[\s\-:]+)+\|$", row)]
                        if table_data_lines:
                            rows_data = [[cell.strip() for cell in row.strip("|").split("|")] for row in table_data_lines]

                            # If chart footprint comment was present, construct native PowerPoint Chart!
                            if pending_chart_type and len(rows_data) > 1:
                                try:
                                    ensure_space(Inches(4.8))
                                    chart_data = CategoryChartData()
                                    headers = rows_data[0]
                                    categories = [r[0] for r in rows_data[1:]]
                                    chart_data.categories = categories

                                    for col_idx in range(1, len(headers)):
                                        series_name = headers[col_idx]
                                        series_vals = []
                                        for r in rows_data[1:]:
                                            try:
                                                v = float(r[col_idx]) if col_idx < len(r) else 0.0
                                            except (ValueError, TypeError):
                                                v = 0.0
                                            series_vals.append(v)
                                        chart_data.add_series(series_name, series_vals)

                                    chart_enum = XL_CHART_TYPE.COLUMN_CLUSTERED
                                    if pending_chart_type == "bar":
                                        chart_enum = XL_CHART_TYPE.BAR_CLUSTERED
                                    elif pending_chart_type == "pie":
                                        chart_enum = XL_CHART_TYPE.PIE
                                    elif pending_chart_type == "line":
                                        chart_enum = XL_CHART_TYPE.LINE

                                    chart_shape = slide.shapes.add_chart(chart_enum, Inches(0.8), top_offset, Inches(11.7), Inches(4.5), chart_data)
                                    chart_obj = chart_shape.chart

                                    if pending_chart_title:
                                        chart_obj.has_title = True
                                        if hasattr(chart_obj.chart_title, "text_frame") and chart_obj.chart_title.text_frame.paragraphs:
                                            chart_obj.chart_title.text_frame.paragraphs[0].text = pending_chart_title
                                    else:
                                        chart_obj.has_title = False

                                    chart_obj.has_legend = True
                                    try:
                                        chart_obj.legend.include_in_layout = False
                                    except Exception:
                                        pass
                                    if pending_chart_legend:
                                        l_str = pending_chart_legend.lower()
                                        if "right" in l_str:
                                            chart_obj.legend.position = XL_LEGEND_POSITION.RIGHT
                                        elif "top" in l_str:
                                            chart_obj.legend.position = XL_LEGEND_POSITION.TOP
                                        elif "left" in l_str:
                                            chart_obj.legend.position = XL_LEGEND_POSITION.LEFT
                                        elif "bottom" in l_str:
                                            chart_obj.legend.position = XL_LEGEND_POSITION.BOTTOM

                                    top_offset += Inches(4.8)
                                    pending_chart_type = None
                                    pending_chart_title = None
                                    pending_chart_legend = None
                                    continue
                                except Exception as chart_ex:
                                    print(f"[DEBUG] Failed to create chart from footprint: {chart_ex}")

                            # Fallback: Create native PowerPoint Table
                            row_count = len(rows_data)
                            col_count = max(len(r) for r in rows_data) if rows_data else 1
                            ensure_space(Inches(0.5 * row_count + 0.3))

                            table_shape = slide.shapes.add_table(row_count, col_count, Inches(0.8), top_offset, Inches(11.7), Inches(0.4 * row_count))
                            table = table_shape.table
                            for r_idx, row in enumerate(rows_data):
                                for c_idx, val in enumerate(row):
                                    if c_idx < col_count:
                                        table.cell(r_idx, c_idx).text = val.replace("<br>", "\n")
                            top_offset += Inches(0.5 * row_count + 0.3)
                            pending_chart_type = None
                        continue

                    # 3. Markdown Image Detection (![alt](path))
                    img_match = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
                    if img_match:
                        img_uri = img_match.group(2)
                        resolved = asset_mgr.resolve_uri(img_uri)
                        if not os.path.exists(resolved) and os.path.exists(img_uri):
                            resolved = img_uri

                        if os.path.exists(resolved):
                            try:
                                ensure_space(Inches(3.8))
                                slide.shapes.add_picture(resolved, Inches(0.8), top_offset, width=Inches(7.0))
                                top_offset += Inches(3.8)
                            except Exception as ex:
                                print(f"[DEBUG] Failed to insert picture in PPTX export: {ex}")
                        i += 1
                        continue

                    # 4. Text Frame (Bullet lists & formatted paragraphs with pagination)
                    tx_lines = []
                    while i < len(content_lines):
                        l_str = content_lines[i].strip()
                        if not l_str or (l_str.startswith("|") and l_str.endswith("|")) or re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", l_str):
                            break
                        tx_lines.append(content_lines[i])
                        i += 1

                    while tx_lines:
                        # If current slide has very little space left and already contains content, create continuation slide
                        if top_offset > max_slide_top - Inches(1.2) and top_offset > start_top_offset:
                            slide = prs.slides.add_slide(blank_layout)
                            top_offset = Inches(0.8)
                            start_top_offset = Inches(0.8)
                            if notes_text:
                                try:
                                    slide.notes_slide.notes_text_frame.text = notes_text
                                except Exception:
                                    pass

                        avail_height = max_slide_top - top_offset
                        line_height = Inches(0.38)
                        max_lines_fit = max(1, int((avail_height - Inches(0.2)) / line_height))

                        chunk = tx_lines[:max_lines_fit]
                        tx_lines = tx_lines[max_lines_fit:]

                        box_height = Inches(0.38 * len(chunk) + 0.2)
                        txBox = slide.shapes.add_textbox(Inches(0.8), top_offset, Inches(11.7), box_height)
                        tf = txBox.text_frame
                        tf.word_wrap = True

                        first_para = True
                        for bl in chunk:
                            bl_str = bl.strip()
                            if not bl_str:
                                continue

                            if first_para:
                                p = tf.paragraphs[0]
                                first_para = False
                            else:
                                p = tf.add_paragraph()

                            leading_spaces = len(bl) - len(bl.lstrip(" "))
                            level = min(8, leading_spaces // 2)
                            p.level = level

                            # Preserve list formatting (Numbered lists vs Bullet dots)
                            is_numbered = bool(re.match(r"^\d+\.\s+", bl_str))
                            is_bullet = bool(re.match(r"^[*\-+]\s+", bl_str))

                            if is_numbered:
                                clean_text = bl_str
                            elif is_bullet:
                                stripped_text = re.sub(r"^[*\-+]\s+", "", bl_str)
                                clean_text = f"•  {stripped_text}"
                            elif level > 0:
                                clean_text = f"•  {bl_str}"
                            else:
                                clean_text = bl_str

                            font_sz = max(12, 18 - level * 2)
                            parse_formatted_runs(p, clean_text, default_size=font_sz)

                        top_offset += box_height

            out_dir = os.path.dirname(out_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

            prs.save(out_path)
            return f"Saved to PowerPoint -> {os.path.basename(out_path)}"

        except Exception as e:
            return f"⚠️ Export Error: Failed to save PPTX document — {str(e)}"


# Automatically register module when imported
ModuleRegistry.register(PPTXModule())
