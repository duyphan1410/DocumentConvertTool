# 📦 PR Archive Snapshot — 13/08/2026: `feat/duy-13082026-pptx-spec-optimization`

- **Branch Name:** `feat/duy-13082026-pptx-spec-optimization`
- **Commits:** `10c1921`, `e571848`, `bb8be62` + ribbon/editor UX fixes
- **Date:** 13/08/2026
- **Status:** In Progress
- **Target Component:** `src/modules/pptx_module.py`, `src/modules/word_module.py`, `src/modules/pdf_module.py`, `src/core/converters.py`, `src/ui_flet/controllers/search_controller.py`, `src/ui_flet/layout/ribbon_bar.py`, `src/ui_flet/views/editor_view.py`, `src/ui_flet/views/workspace_view.py`, `src/ui_flet/app.py`

---

## 📌 PR Summary: [feat/duy-13082026-pptx-spec-optimization -> dev]

### 🎯 Mục tiêu PR
Nâng cấp toàn diện bộ engine chuyển đổi hai chiều PowerPoint (`PPTX ↔ MD`), tái cấu trúc kiến trúc `PPTXModule` (loại bỏ 10+ closure functions lồng nhau), khử trùng lặp logic bóc tách Bảng Markdown dùng chung (`parse_table_rows`), hoàn thiện hỗ trợ Hyperlink nhấp chuột cho Slide, sửa lỗi phân giải đường dẫn hình ảnh có chứa dấu ngoặc đơn `()` / ký tự đặc biệt, tối ưu hóa tốc độ build PyInstaller (`137s ➔ 60.7s`), nâng phiên bản hệ thống lên **`v1.6.3`** và cập nhật hệ thống tài liệu kỹ thuật (`docs/`). Đồng thời khắc phục một loạt lỗi UX Ribbon Bar và Undo/Redo cursor trong Editor.

---

### 🚀 Các thay đổi chính

#### 1. Core Engine & PowerPoint Module (`src/modules/pptx_module.py`)
- **Nâng cấp engine PowerPoint 2 chiều (`PPTX ↔ MD`)**: Hỗ trợ slide 16:9 widescreen, trích xuất numbering `a:buAutoNum`, bảng biểu, chart footprint `<!-- chart: ... -->`, slide notes pane và thuật toán tự động ngắt trang chống tràn slide (`Continuation Slide`).
- **Tái cấu trúc (Un-nesting 10+ Closures)**: Tách các hàm lồng nhau thành các private helper methods (`_is_smartart_shape`, `_flatten_shapes`, `_split_markdown_into_slide_blocks`, `_get_visual_line_count`, `_parse_formatted_runs`, `_calc_title_geometry`, `_create_continuation_slide`, `_ensure_space`, `_calc_row_h`).
- **Hyperlink nhấp chuột trong PPTX**: Hợp nhất `_parse_formatted_runs` sử dụng `parse_inline(text)` từ `converters.py` và tự động gán `run.hyperlink.address = seg.url` cho liên kết dạng `[Tên Link](https://...)`.

#### 2. Khử Trùng Lặp Bóc Tách Bảng Markdown (`src/core/converters.py`)
- Định nghĩa helper `parse_table_rows(table_lines)` chuẩn hóa lọc đường phân cách `|---|`, strip cell whitespace và padding độ rộng cột.
- Tái sử dụng thống nhất giữa các module `WordModule`, `PPTXModule`, `ExcelModule`, `CSVModule`.

#### 3. Media Asset Manager & Preview (`src/services/media_asset_manager.py`, `src/ui_flet/views/preview_view.py`)
- Khắc phục triệt để lỗi đứt đường dẫn hình ảnh và Instant Preview khi tên tệp hoặc thư mục có chứa dấu ngoặc đơn `()`, dấu cách hoặc ký tự tiếng Việt.

#### 4. Ribbon UX & Editor Fixes (`src/ui_flet/layout/ribbon_bar.py`, `src/ui_flet/views/editor_view.py`, `src/ui_flet/views/workspace_view.py`, `src/ui_flet/controllers/search_controller.py`, `src/ui_flet/app.py`)
- **Undo/Redo cursor sync (`editor_view.py`)**: Sửa lỗi con trỏ văng về cuối văn bản sau Undo/Redo. Áp dụng pattern deferred selection — gọi `page.run_task(_apply_selection)` sau `asyncio.sleep(delay)` để đợi Flutter hoàn thành render frame 1 (text value) trước khi áp selection. Dùng thuật toán `lf_to_utf16` đọc `self.editor.value` thực tế từ Flet để tính offset chính xác, tránh lệch khi Flet chuẩn hóa `\r\n`. Delay tự động tăng theo kích thước file.
- **Ribbon startup auto-collapse fix (`workspace_view.py`)**: Sửa lỗi tab Edit mở rồi tự thu gọn khi khởi động. Nguyên nhân: `show_editor` gọi `_select_tab("edit")` khi `active_tab` đã là `"edit"` và panel visible → kích hoạt toggle-collapse. Fix: dùng `select_tab("edit", force=True)` để bỏ qua kiểm tra toggle.
- **Ctrl+F — Mở Ribbon khi đang collapse (`ribbon_bar.py`)**: Sửa điều kiện `if self.active_tab != "edit"` thành `if self.active_tab != "edit" or not self.panel_container.visible` — đảm bảo Ctrl+F mở ribbon ngay cả khi ribbon đang thu gọn mà `active_tab` vẫn là `"edit"`.
- **Ctrl+F — Toggle logic thông minh (`ribbon_bar.py`, `app.py`, `search_controller.py`)**: 
  - Ctrl+F lần 2 khi đang ở Edit tab + Find visible → đóng Find bar.
  - Ctrl+F khi đã chuyển sang tab khác (View, File…) → luôn mở lại Edit tab + Find bar, không toggle-off dựa trên `_search_visible` cũ.
  - `app.py`: đổi từ `toggle_search(True)` → `toggle_search()` cho Ctrl+F.
  - `search_controller.py`: signature `toggle_search(visible=None)` hỗ trợ None/True/False.
- **Spam guard cho Ctrl+F (`ribbon_bar.py`)**: Thêm flag `_search_toggling` với pattern `try/finally` để block re-entrant calls khi user spam Ctrl+F liên tục — tránh state race và ngăn khả năng duplicate Find bar.
- **Word (`src/modules/word_module.py`)**: Xử lý ngắt dòng `<br>` trong ô bảng Word và áp dụng định dạng inline (`add_formatted_runs`).
- **PDF (`src/modules/pdf_module.py`)**: Đè CSS `th p, td p { margin: 0; padding: 0; }` và `word-break: break-word` triệt tiêu lề dưới 10px thụt lề trong ô bảng PDF.

#### 5. Tối Ưu Hóa Build PyInstaller (`Document Converter.spec`, `src/__version__.py`)
- Tối ưu hóa file spec: thay `collect_all` tràn lan bằng `collect_data_files` / `collect_submodules` tinh gọn; loại trừ các DLL nhị phân nặng (`pdfium.dll`, `mupdf.dll`, `flet.dll`, `_fitz`) khỏi UPX; bảo toàn module `tkinter` cho cửa sổ chọn tệp Native FilePicker trên Windows (thời gian đóng gói giảm từ 137s xuống 60.7s).

#### 6. Hệ Thống Tài Liệu Kỹ Thuật (`docs/`)
- **ADR-007 (`docs/architecture/007_module_architecture_and_pptx_refactoring.md`)**: Lưu trữ quyết định kiến trúc refactor module.
- **PR Snapshot Archive (`docs/archive/20260813_pptx_module_refactoring_and_table_deduplication.md`)**: Lưu trữ PR log cho nhánh.
- **Release Notes (`docs/releases/v1.6.0.md`)**: Gộp nội dung bản vá `v1.6.3` & `v1.6.1 patch` trực tiếp vào tài liệu release `v1.6.0.md`.
- **Master Index (`docs/README.md`)**: Cập nhật danh mục tài liệu tổng thể.

---

### 🧪 Kiểm thử & Xác minh
- [x] **Layer 1 (Imports)**: Tất cả module Python (`docx`, `pptx`, `openpyxl`, `fitz`, `pdfplumber`, `flet`, `tkinter`) import thành công 100%.
- [x] **Layer 2 (Unit / Service)**: Chạy thành công toàn bộ **47/47 unit tests** (`python -m unittest discover tests`).
- [x] **Layer 3 (Integration / Headless)**: Đã build kiểm thử tệp thực thi PyInstaller `dist/Document Converter.exe` (thời gian build 60.7s, cửa sổ Win32 FilePicker hoạt động mượt mà, chuyển đổi thực tế `.md` sang `.pptx`, `.docx`, `.pdf` hiển thị hoàn hảo).

---

### ⚠️ Giới hạn hiện tại & Phạm vi bổ sung

- **Flet/Flutter 2-frame rendering**: Undo/Redo cursor dùng `asyncio.sleep(50ms)` để deferred selection — hoạt động tốt với file nhỏ-vừa; file cực lớn (>500K chars) delay tự động tăng tối đa 150ms.
- **Settings Path**: Hiện chỉ hỗ trợ Windows (`%APPDATA%\DocConvert\settings.json`) — cross-platform path chưa triển khai.

---

### 🔍 Phân tích ảnh hưởng & Đánh giá rủi ro
- **Mức độ rủi ro (Blast Radius)**: THẤP
- **Các hàm/module ảnh hưởng**: `PPTXModule`, `WordModule`, `PDFModule`, `MediaAssetManager`, `SearchController`, `RibbonBar`, `EditorView`, `WorkspaceView`, `converters.py`, `Document Converter.spec`, `docs/`.
