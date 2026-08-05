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


---

### 🔄 Tính năng & Sửa lỗi cần thực hiện trong tương lai (v2.0 Roadmap):

| Hạng mục | Vị trí / Tầng ảnh hưởng | Mô tả chi tiết & Hướng phát triển | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Option Settings View** | `src/ui_flet/views/settings_view.py` | Xây dựng menu Setting / View Setting trong Tab Options để điều chỉnh thông số mặc định (Font, Auto-save interval, Export paths). | ⏳ Planned |
| **Word Exporter Image Embed** | `src/modules/word_module.py` | Parse token `@media/` nhúng ảnh trực tiếp vào file Word `.docx` khi xuất từ Markdown. | 🔄 In Progress |
| **Flet Local Image Engine Optimization** | `src/utils/assets.py` | Tối ưu hóa bộ định tuyến Asset Server ngầm của Flet Desktop để hiển thị ảnh Logo tùy chỉnh sắc nét (Tham khảo `flet_logo_image_investigation.md`). | ⏳ Pending |
| **Win32 Z-Order Focus Enhancement** | `src/utils/env.py` | Nâng cấp cơ chế Layer 4 FlashWindowEx để lấy tiêu điểm (Focus) mượt mà cho Microsoft Excel & Word khi mở file sau chuyển đổi (Tham khảo `FOCUS_ZORDER_ANALYSIS.md`). | ⏳ Pending |
| **Multi-Tab Workspace** | `src/ui_flet/components/tab_bar.py` | Quản lý nhiều tài liệu mở song song trên các thẻ Tab. | ⏳ Planned |
| **GitHub Styled PDF Engine** | `src/services/pdf_exporter.py` | Tích hợp `sindresorhus/github-markdown-css` xuất PDF chuẩn GitHub A4. | ⏳ Planned |
| **Batch & ZIP Converter** | `src/services/batch_service.py` | Chuyển đổi hàng loạt tệp trong thư mục hoặc file nén `.zip`. | ⏳ Planned |

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
