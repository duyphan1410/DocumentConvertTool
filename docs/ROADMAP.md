# Document Converter Workspace — Roadmap v2.0 & Flet UI Release

---

## Tổng quan hiện trạng (v1.3.0 - Flet 3-Tier Architecture Release)

### ✅ Đã hoàn thành (Phase 0–5):

| Phase / Feature | Nội dung chính | Trạng thái |
| :--- | :--- | :---: |
| **P0 – Stabilization** | File extension validation, overwrite confirmation, fallback engines, unsaved warning | ✅ Completed |
| **P1 – UX & Format** | CSV ↔ MD, search & replace (Smart Hybrid focus), formatting toolbar, autosave draft (1.5s debounce) | ✅ Completed |
| **P2 – Format Expansion** | PDF ➔ MD (stitching tables, multiline cell continuation, slide image extraction), HTML ↔ MD | ✅ Completed |
| **P3 – Flet UI Migration** | Responsive split-pane layout, 5-Palette design tokens, instant 0ms container theme updates | ✅ Completed |
| **P4 – Native Dialogs & 3-Tier UI** | Async Win32 FileDialog via `asyncio.to_thread`, High-DPI Per-Monitor v2, 3-Tier modular layout (`layout/`, `components/`, `views/`). **Đã tích hợp đầy đủ 3 tính năng bảo vệ:**<br>1. Tự động lọc Dropdown Mode theo đuôi file nạp (`update_mode_options`).<br>2. Hộp thoại xác nhận đè file Win32 Native (`confirmoverwrite`).<br>3. Kiểm tra Editor rỗng ngăn chuyển đổi (`_on_convert_clicked`). | ✅ Completed |
| **P5 – Performance & Async Load** | Tách luồng `asyncio.to_thread` nạp file không bị đơ UI, log `[BENCHMARK]`, RAM Base64 image cache (`_BASE64_CACHE` trong `preview.py`) | ✅ Completed |

---

### 🔄 Tính năng đang phát triển nối tiếp (Phase 4 - Image Pipeline):

| Phase / Feature | Nội dung chính | Trạng thái | Ghi chú |
| :--- | :--- | :---: | :--- |
| **Two-Way Image Pipeline** | Service `MediaAssetManager`, giải mã URI `@media/` ➔ Base64 RAM Cache (`_BASE64_CACHE`) cho live preview & nhúng ảnh Word export | 🔄 In Progress | - Xem trước ảnh Markdown/PDF: ✅ Done (`preview.py`)<br>- Word Exporter Image Embed: ⏳ Pending (`word_module.py`) |

---

## Kế hoạch phát triển tiếp theo (v2.0 Roadmap)

### 🎯 Brief Kế Hoạch Đã Được Thống Nhất:

| Phase | Tên tính năng | Tầng ảnh hưởng | Mô tả chi tiết |
| :--- | :--- | :--- | :--- |
| **Phase 4.1** | **Word Exporter Image Embed** | `src/modules/word_module.py` | Parse token `@media/` nhúng ảnh trực tiếp vào file Word `.docx` khi xuất từ Markdown. |
| **Phase 4.2** | **Office Ribbon Navbar UI Brief & Design** | `src/ui_flet/layout/ribbon_bar.py` | Thiết kế brief wireframe thanh công cụ Ribbon 4 tabs (File, Edit, Convert, View), hỗ trợ thu gọn về HeaderBar. |
| **Phase 4.3** | **Formatting Toolbar & Headings** | `src/ui_flet/components/formatting_toolbar.py` | Dropdown chọn cấp độ tiêu đề **Heading H1 - H6** & phím tắt định dạng nhanh cho Editor. |
| **Phase 5.1** | **Multi-Tab Workspace** | `src/ui_flet/components/tab_bar.py` | Mở & quản lý nhiều tài liệu song song trên các tab. |
| **Phase 6.1** | **GitHub Styled MD ➔ HTML ➔ PDF Engine** | `src/services/pdf_exporter.py` | Tích hợp `sindresorhus/github-markdown-css` (`assets/css/github-markdown.css`) xuất HTML & PDF sắc nét chuẩn GitHub. |
| **Phase 6.2** | **Print Preview & Print View** | `src/ui_flet/views/print_view.py` | Giao diện xem trước trang in A4 chuẩn phân trang & hộp thoại in hệ thống. |
| **Phase 6.3** | **Batch & ZIP Converter** | `src/services/batch_service.py` | Chuyển đổi hàng loạt nhiều tệp trong folder hoặc gói tệp `.zip`. |
| **Phase 7.0** | **CLI Mode & Packaging** | `src/cli.py`, `Document Converter.spec` | Chế độ dòng lệnh headless & đóng gói bộ cài `DocumentConverter_Setup_v2.0.0.exe`. |

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
