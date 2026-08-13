# 📦 PR Archive Snapshot — 13/08/2026: `feat/duy-13082026-pptx-spec-optimization`

- **Branch Name:** `feat/duy-13082026-pptx-spec-optimization`
- **Commits:** `10c1921`, `e571848`
- **Date:** 13/08/2026
- **Status:** Merged / Cleaned
- **Target Component:** `src/modules/pptx_module.py`, `src/modules/word_module.py`, `src/modules/pdf_module.py`, `src/core/converters.py`, `src/ui_flet/controllers/search_controller.py`

---

## 🛠️ Summary of Changes

### 1. PPTX Module Un-nesting & Helper Refactoring (`src/modules/pptx_module.py`)
- Un-nested 10+ nested closure functions into clean private class and static methods:
  - `_is_smartart_shape(shape)`
  - `_is_numbered_paragraph(bl_str)`
  - `_flatten_shapes(shapes_col)`
  - `_split_markdown_into_slide_blocks(markdown_text)`
  - `_get_visual_line_count(text, level)`
  - `_parse_formatted_runs(paragraph, text, pt_cls, default_size, force_bold)`
  - `_calc_title_geometry(title, inches_cls)`
  - `_create_continuation_slide(prs, title_text, notes_text, blank_layout, inches_cls, pt_cls, pp_align_cls)`
  - `_ensure_space(needed_height, shape_type)`
  - `_calc_row_h(cell_text, col_w_inches)`
- Preserved pagination parameters: `0.24in` line height fitting estimation and `0.28in * lines + 0.15in` bounding box height.

### 2. Markdown Table Parsing Deduplication (`src/core/converters.py`)
- Created `parse_table_rows(table_lines: list[str]) -> list[list[str]]` block helper to standardize Markdown pipe table extraction, separator filtering (`|---|`), cell whitespace stripping, and column width padding.
- Refactored `parse_md_tables()` to reuse `parse_table_rows()`.
- Integrated `parse_table_rows()` in `WordModule` and `PPTXModule` table rendering loops.

### 3. Phase 3: PPTX Inline Markdown Unification (`src/modules/pptx_module.py`)
- Updated `PPTXModule._parse_formatted_runs` to call `parse_inline(text)` from `src.core.converters`.
- Added support for bold, italic, code (Consolas), underline, strikethrough, and clickable `run.hyperlink.address = seg.url` on PowerPoint `Run` objects.

### 4. Table Cell Formatting & Keyboard Shortcut Fixes
- **Word (`src/modules/word_module.py`)**: Replaced raw string dumps in Word table cells with multiline `<br>` line break splitting and `add_formatted_runs(p, c_line)` formatting.
- **PDF (`src/modules/pdf_module.py`)**: Overrode paragraph margin inside PDF table cells (`th p, td p { margin: 0; padding: 0; }`) and added `word-wrap: break-word`.
- **Search Shortcut (`src/ui_flet/controllers/search_controller.py`)**: Added `toggle_search()` alias method to prevent `AttributeError` when pressing `Ctrl+F` or `Ctrl+H`.

---

## 🧪 Test Verification

Ran 47 unit tests cleanly via `python -m unittest discover tests`:
```powershell
python -m unittest discover tests
----------------------------------------------------------------------
Ran 47 tests in 4.064s

OK
[SUCCESS] All unit tests passed cleanly!
```
