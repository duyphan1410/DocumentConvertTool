# Document Converter Workspace — Roadmap v2.0 & Flet UI Release

---

## Tổng quan hiện trạng (v1.4.0 - Flet 3-Tier MVC, Ribbon Bar & PDF Engine Release)

### ✅ Đã hoàn thành (Phase 0–4.3):

| Phase / Feature | Nội dung chính | Trạng thái |
| :--- | :--- | :---: |
| **P0 – Stabilization** | File extension validation, overwrite confirmation, fallback engines, unsaved warning | ✅ Completed |
| **P1 – UX & Format** | CSV ↔ MD, search & replace (Smart Hybrid focus), formatting toolbar, autosave draft (1.5s debounce) | ✅ Completed |
| **P2 – Format Expansion** | PDF ➔ MD (stitching tables, multiline cell continuation, slide image extraction), HTML ↔ MD | ✅ Completed |
| **P3 – Flet UI Migration** | Responsive split-pane layout, 5-Palette design tokens, instant 0ms container theme updates | ✅ Completed |
| **P4 – Native Dialogs & 3-Tier UI** | Async Win32 FileDialog via `asyncio.to_thread`, High-DPI Per-Monitor v2, 3-Tier modular layout (`layout/`, `components/`, `views/`). | ✅ Completed |
| **P4.2 – Pure Orchestrator MVC** | AppState, 6 Controllers (`file`, `editor`, `search`, `theme`, `conversion`, `layout`), Welcome Dashboard, Ribbon Bar 4 tabs | ✅ Completed |
| **P4.3 – PDF Polish & Packaging** | PDF list/bullet preservation, Vietnamese font handling, HTML code fence regex auto-repair, PyInstaller `hiddenimports`, Pinned requirements | ✅ Completed |
| **P4.4 – Settings, i18n & User Guide** | Option Settings View (i18n, font size, autosave interval), Help & User Guide View, Word Exporter Image Embed (`@media/`), Win32 Z-Order Focus Enhancement | ✅ Completed |


---

### 🔄 Tính năng & Sửa lỗi cần thực hiện trong tương lai (v2.0 Roadmap):

| Hạng mục | Vị trí / Tầng ảnh hưởng | Mô tả chi tiết & Hướng phát triển | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Option Settings & i18n View** | `src/ui_flet/views/settings_view.py` | Xây dựng menu Settings trong Tab Options hỗ trợ **Chuyển đổi Ngôn ngữ (Tiếng Việt ↔ English)**, chỉnh phông chữ, khoảng thời gian Auto-save và thư mục xuất tệp mặc định. | ✅ Completed |
| **Help & User Guide View** | `src/ui_flet/views/help_view.py` | Xây dựng màn hình Hướng dẫn sử dụng & Markdown Cheatsheet trong Tab Help giúp người dùng mới nắm rõ quy trình chuyển đổi và phím tắt. | ✅ Completed |
| **Word Exporter Image Embed** | `src/modules/word_module.py` | Parse token `@media/` nhúng ảnh trực tiếp vào file Word `.docx` khi xuất từ Markdown. | ✅ Completed |
| **PowerPoint Module (`.pptx`)** | `src/modules/pptx_module.py` | Chuyển đổi slide PowerPoint `.pptx` hai chiều với Markdown (`PPTX ↔ MD`), hỗ trợ slide 16:9 widescreen, trích xuất danh sách đánh số (Numbering), bảng biểu, biểu đồ kèm chú thích (chart footprint), tự động phân trang khi nội dung tràn slide (text pagination + continuation slide). *Known limitation: table alignment mặc định trái (không hỗ trợ theo cột PowerPoint gốc).* | ✅ Completed (v1.6) |
| **YouTube URL Transcriber** | `src/services/youtube_service.py` | Trích xuất phụ đề/nội dung từ liên kết YouTube (`youtube.com/watch?v=...`) thành bài viết Markdown kèm mốc thời gian (Timestamps). | ⏳ Planned (v1.6) |
| **Data Formats Engine** | `src/modules/data_module.py` | Chuyển đổi dữ liệu cấu trúc `JSON` / `YAML` thành Bảng Markdown (Markdown Tables) phục vụ làm tài liệu kỹ thuật. | ⏳ Planned (v1.6) |
| **Audio/Video Speech Transcriber** | `src/services/speech_service.py` | Plugin Whisper AI trích xuất giọng nói từ video `.mp4` và audio `.mp3` thành văn bản Markdown ghi chú cuộc họp. | ⏳ Planned (v1.7) |
| **EPub eBook Engine (`.epub`)** | `src/modules/epub_module.py` | Đọc và đóng gói sách điện tử `.epub` hai chiều với Markdown (`EPUB ↔ MD`). | ⏳ Planned (v1.7) |
| **Mermaid Diagram Live Preview** | `src/ui_flet/views/preview_view.py` | Hỗ trợ hiển thị sơ đồ Mermaid trong Live Preview bằng giải pháp Interceptor (chuyển khối mã ````mermaid```` thành ảnh SVG/PNG Base64 nhúng trực tiếp vào `ft.Markdown`). | ⏳ Planned (v1.7) |
| **Recent Files History** | `src/ui_flet/views/welcome_view.py` | Lưu danh sách tệp vừa mở gần đây (Recent Documents) để mở lại nhanh từ Welcome Dashboard. | ⏳ Planned |
| **Multi-Tab Workspace** | `src/ui_flet/components/tab_bar.py` | Quản lý nhiều tài liệu mở song song trên các thẻ Tab theo phong cách Studio Workspace. | ⏳ Planned |
| **Batch & ZIP Converter** | `src/services/batch_service.py` | Chuyển đổi hàng loạt tệp trong thư mục hoặc file nén `.zip`. | ⏳ Planned |
| **Win32 Z-Order Focus Enhancement** | `src/utils/env.py` | Nâng cấp cơ chế Layer 4 FlashWindowEx để lấy tiêu điểm (Focus) mượt mà cho Microsoft Excel & Word khi mở file sau chuyển đổi (Tham khảo `FOCUS_ZORDER_ANALYSIS.md`). | ✅ Completed |
| **Portable Markdown Image Links** | `src/services/media_asset_manager.py` | Sửa lỗi tệp Markdown xuất từ tệp có hình chỉ app nội bộ đọc được; chuẩn hóa đường dẫn ảnh tương đối `<doc_name>_assets/` giúp VS Code & IDE khác preview bình thường. | ✅ Completed |
| **Edit Ribbon Add Image Instant Preview** | `src/ui_flet/controllers/file_controller.py` | Sửa lỗi tính năng Add Image trên thanh Edit Ribbon sau khi chọn & gắn link ảnh chưa tự động trigger render xem trước (Instant Preview) lên màn hình preview ngay. | ✅ Completed |
| **Image Settings Dialog & Format Tab** | `src/ui_flet/views/editor_view.py` | Hộp thoại tùy chỉnh kích thước/tỷ lệ hình ảnh (Nhỏ 25%, Vừa 50%, Gốc 100%, hoặc tùy chỉnh Width/Height HTML) và bổ sung Contextual Format Tab trên thanh Ribbon Bar khi thao tác với hình ảnh. | ⏳ Planned |
| **Folder Mode (`--onedir`) & Inno Setup Installer** | `Document Converter.spec` / Packaging | Chuyển đổi đóng gói từ Single-file (`--onefile`) sang Thư mục (`--onedir`) kết hợp bộ tạo cài đặt Inno Setup (`Setup.exe`) giúp mở ứng dụng tức thì (< 0.5s) và trải nghiệm cài đặt chuyên nghiệp. | ⏳ Planned (v2.0) |


---

## Hướng dẫn khởi chạy & Đóng gói sản phẩm

### 1. Khởi chạy ứng dụng (Development):
```powershell
python run.py
```

### 2. Đóng gói file `.exe` thương mại bằng PyInstaller:
```powershell
python -m PyInstaller "Document Converter.spec"
```
File thực thi duy nhất sẽ được tạo tại: **`dist/Document Converter.exe`**.

### 3. Đóng gói bằng Flet Pack CLI:
```powershell
flet pack run.py --name "Document Converter" --icon favicon.ico --windowed
```
