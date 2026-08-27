# Document Converter Workspace — Roadmap v2.0 & Flet UI Release

---

## Tổng quan hiện trạng (v1.4.0 - Flet 3-Tier MVC, Ribbon Bar & PDF Engine Release)

### ✅ Đã hoàn thành (Phase 0–4.3):

| Phase / Feature | Nội dung chính | Trạng thái |
| :--- | :--- | :---: |
| **P0 – Stabilization** | File extension validation, overwrite confirmation, fallback engines, unsaved warning | ✅ Completed |
| **P1 – UX & Format** | CSV ↔ MD, search & replace (Smart Hybrid focus), formatting toolbar, autosave draft (1.5s debounce) | ✅ Completed |
| **P2 – Format Expansion** | PDF ➔ MD (stitching tables, multiline cell continuation, slide image extraction), HTML ↔ MD | ✅ Completed |
| **P3 – Flet UI Migration** | Responsive split-pane layout, 4-Palette design tokens, instant 0ms container theme updates | ✅ Completed |
| **P4 – Native Dialogs & 3-Tier UI** | Async Win32 FileDialog via `asyncio.to_thread`, High-DPI Per-Monitor v2, 3-Tier modular layout (`layout/`, `components/`, `views/`). | ✅ Completed |
| **P4.2 – Pure Orchestrator MVC** | AppState, 6 Controllers (`file`, `editor`, `search`, `theme`, `conversion`, `layout`), Welcome Dashboard, Ribbon Bar 4 tabs | ✅ Completed |
| **P4.3 – PDF Polish & Packaging** | PDF list/bullet preservation, Vietnamese font handling, HTML code fence regex auto-repair, PyInstaller `hiddenimports`, Pinned requirements | ✅ Completed |
| **P4.4 – Settings, i18n & User Guide** | Option Settings View (i18n, font size, autosave interval), Help & User Guide View, Word Exporter Image Embed (`@media/`), Win32 Z-Order Focus Enhancement | ✅ Completed |


---

### ✅ v1.7.0 Release (Simplified Single-Row Ribbon, YouTube Extractor, Direct MD Export & UI Polish):

| Hạng mục | Vị trí / Tầng ảnh hưởng | Mô tả chi tiết & Hướng phát triển | Trạng thái |
| :--- | :--- | :--- | :---: |
| **YouTube Subtitle & Speech Transcriber** | `src/services/youtube_service.py`, `src/services/speech_service.py` | Kiến trúc đa tầng: Tầng 1 lấy phụ đề gốc/Server Auto-Translate (0% CPU/RAM); Tầng 2 Fallback nhận diện giọng nói Non-AI (`SpeechRecognition` + `yt-dlp`), phân đoạn 20s kèm timestamp `[mm:ss]`. | ✅ Completed (v1.7.0) |
| **Direct Markdown Export (`.md`)** | `src/ui_flet/views/editor_view.py`, `src/ui_flet/controllers/file_controller.py` | Nút Tải nhanh Markdown (`[⬇]`), mode `MD -> Markdown`, kích hoạt tức thì nút Mở tệp/Mở thư mục trên Footer Bar. | ✅ Completed (v1.7.0) |
| **Win32 Clipboard & URL Auto-Fill** | `src/utils/clipboard.py`, `src/ui_flet/components/youtube_dialog.py` | Đọc Clipboard Win32 qua `CF_UNICODETEXT` an toàn tiếng Việt có dấu, hỗ trợ `Win + V`, tự động điền link YouTube khi mở modal. | ✅ Completed (v1.7.0) |
| **JSON / YAML Multiline Formatting Fix** | `src/modules/json_module.py`, `src/modules/yaml_module.py` | Khắc phục hiển thị ký tự thoát (`\n`, `\t`), hỗ trợ chuỗi nhiều dòng thụt lề (multiline continuation) và tab preservation. | ✅ Completed (v1.7.0) |
| **Simplified Single-Row Ribbon** | `src/ui_flet/layout/ribbon_bar.py` | Tinh gọn thanh Ribbon thành 1 hàng duy nhất (38px–40px) đặt trên Editor, tối ưu diện tích dọc theo chuẩn UX 4/8dp rhythm, 100% Vector Icons. | ✅ Completed (v1.7.0) |
| **Folder Native Picker** | `src/ui_flet/native_dialogs.py` | Thêm `pick_directory_sync` / `pick_directory_async` qua `filedialog.askdirectory` chọn folder dự án với High-DPI Per-Monitor v2. | ✅ Completed (v1.7.0) |
| **File Path Bar Single-Row** | `src/ui_flet/components/file_path_bar.py` | Chuyển đổi từ xếp chồng 2 hàng (~90px) sang 1 hàng ngang chia đôi 50/50 (~38px), nút Browse trong suốt, đồng bộ Palette. | ✅ Completed (v1.7.0) |
| **Search & Replace Bar Ultra-Compact** | `src/ui_flet/components/search_replace_bar.py` | Thu gọn phông chữ `text_size=12`, `dense=True`, nút điều hướng `16px`, giảm >50% chiều cao panel. | ✅ Completed (v1.7.0) |
| **Help & User Guide Card Grid** | `src/ui_flet/views/help_view.py` | Tái thiết kế bố cục 2 cột dạng Thẻ Card, bảng phím tắt, tra cứu cú pháp Markdown, ma trận định dạng đầy đủ, và FAQ Accordion mượt mà. | ✅ Completed (v1.7.0) |
| **Option Settings & i18n View** | `src/ui_flet/views/settings_view.py` | Chuẩn hóa Typography Scale, menu Settings điều hướng 160px, đa ngôn ngữ Việt ↔ Anh, font size, autosave interval. | ✅ Completed (v1.7.0) |

---

### ✅ v1.7.2 Release (YouTube In-App Companion Player, Interactive Timestamps & WebView2 Optimization):

| Hạng mục | Vị trí / Tầng ảnh hưởng | Mô tả chi tiết & Hướng phát triển | Trạng thái |
| :--- | :--- | :--- | :---: |
| **In-App YouTube Companion Player** | `src/services/youtube_player.py` | Cửa sổ WebView2 (`540x335`, 16:9, Top-Left `x=24, y=65`), Local HTTP Bridge Server `127.0.0.1` chống Error 153, cờ `--autoplay-policy=no-user-gesture-required`. | ✅ Completed (v1.7.2) |
| **Interactive Timestamps (`yt://...`)** | `src/ui_flet/views/preview_view.py` | Tự động phân tích mốc `[mm:ss]` thành link tương tác `[mm:ss](yt://<id>?t=sec)`, click để tua video trực tiếp trong app hoặc fallback trình duyệt. | ✅ Completed (v1.7.2) |
| **Dynamic Win32 Window Focus (Non-Pinning)** | `src/services/youtube_player.py` | `on_top=False`, sử dụng `_force_window_foreground` với Win32 `AttachThreadInput` và `SetForegroundWindow` đưa cửa sổ lên đỉnh tức thì khi click timestamp. | ✅ Completed (v1.7.2) |
| **Auto YouTube Draft Restoration** | `src/ui_flet/controllers/file_controller.py` | Nhận diện phụ đề YouTube khi nạp lại bản nháp khởi động, tự động bật nút `▶ Watch Video` và phân giải timestamp. | ✅ Completed (v1.7.2) |
| **3-Layer Sync Auto-Close & PyInstaller Packaging** | `Document Converter.spec`, `run.py`, `layout_controller.py` | Đóng đồng bộ khi tắt app chính qua Window Event + `atexit` + `stdin` EOF; hỗ trợ chạy subprocess độc lập trong file `.exe`. | ✅ Completed (v1.7.2) |

---

### 🔄 v1.8.0 Roadmap (Studio Workspace & Multi-Doc Architecture):

| Hạng mục | Vị trí / Tầng ảnh hưởng | Mô tả chi tiết & Hướng phát triển | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Activity Bar & File Explorer** | `src/ui_flet/layout/activity_bar.py`, `src/ui_flet/views/explorer_view.py` | Dải dọc 48px Vector Icons (`ft.Icons.*`) + Sidebar cây thư mục dự án (`ft.ListView` + `ft.ExpansionTile` / Indent). | ⏳ Planned (v1.8) |
| **Draggable Split Panes (Splitter)** | `src/ui_flet/components/draggable_splitter.py` | Thanh kéo co giãn phân vùng linh hoạt giữa Editor ↔ Preview và Sidebar ↔ Workspace (`ft.GestureDetector`, `on_pan_update`, `MouseCursor.RESIZE_LEFT_RIGHT`, persistence `settings.json`). | ⏳ Planned (v1.8) |
| **Draggable Multi-Tab Workspace** | `src/ui_flet/views/workspace_view.py` | Quản lý đa Tab độc lập, hỗ trợ kéo thả sắp xếp lại thứ tự Tab (`ft.Draggable` & `ft.DragTarget`), chuyển đổi nhanh giữa các file đang mở. | ⏳ Planned (v1.8) |
| **Multi-Tab `AppState` & Draft Sessions** | `src/ui_flet/state.py`, `src/services/media_asset_manager.py` | Nâng cấp `AppState` sang `DocumentTabState` với Property Delegation để giảm thiểu thay đổi ở code cũ; Autosave draft theo `drafts/{tab_id}.md`. | ⏳ Planned (v1.8) |
| **Batch & ZIP Converter** | `src/services/batch_service.py` | Chuyển đổi hàng loạt tệp trong thư mục hoặc file nén `.zip`. | ⏳ Planned (v1.8) |

---

### 🔮 v2.0+ Roadmap (Personal Knowledge Base & Advanced Distribution):

| Hạng mục | Vị trí / Tầng ảnh hưởng | Mô tả chi tiết & Hướng phát triển | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Manual Wikilink `[[...]]`** | `src/services/link_parser.py` | Cú pháp `[[Tên File]]` tách biệt với link markdown cũ; Fuzzy Match (lowercase, bỏ dấu tiếng Việt `NFD`, trim space); In-memory graph index. | 🔮 Planned (v2.0) |
| **Broken Link Handling & Click-to-Create** | `src/ui_flet/views/preview_view.py` | Hiển thị link chưa tồn tại bằng màu cảnh báo / gạch chân; hỗ trợ Click để tự động tạo file `.md` mới trong workspace. | 🔮 Planned (v2.0) |
| **Backlink Panel** | `src/ui_flet/views/backlink_view.py` | Panel thanh bên hiển thị danh sách các tài liệu đang dẫn liên kết tới tài liệu hiện hành. | 🔮 Planned (v2.0) |
| **Folder Mode (`--onedir`) & Inno Setup 7 Installer** | `Document Converter.spec` / `installer/` | Chuyển đổi đóng gói sang Thư mục (`--onedir`) kết hợp bộ cài đặt Inno Setup 7 (`Setup.exe`), khởi động tức thì < 1s, phân quyền `%LocalAppData%\Programs`. | ✅ Completed (v1.7.2) |

---

### ⏳ Các Tính Năng & Module Mở Rộng Khác (Format & Feature Expansion):

| Hạng mục | Vị trí / Tầng ảnh hưởng | Mô tả chi tiết & Hướng phát triển | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Audio/Video Speech Transcriber** | `src/services/speech_service.py` | Plugin Whisper AI trích xuất giọng nói từ video `.mp4` và audio `.mp3` thành văn bản Markdown ghi chú cuộc họp. | ⏳ Planned |
| **EPub eBook Engine (`.epub`)** | `src/modules/epub_module.py` | Đọc và đóng gói sách điện tử `.epub` hai chiều với Markdown (`EPUB ↔ MD`). | ⏳ Planned |
| **Mermaid Diagram Live Preview** | `src/ui_flet/views/preview_view.py` | Hỗ trợ hiển thị sơ đồ Mermaid trong Live Preview bằng giải pháp Hybrid Interceptor (chuyển khối mã ````mermaid```` thành ảnh SVG/PNG Base64 nhúng trực tiếp vào `ft.Markdown`). | ✅ Available |
| **Image Settings Dialog & Format Tab** | `src/ui_flet/views/editor_view.py` | Hộp thoại tùy chỉnh kích thước/tỷ lệ hình ảnh (Nhỏ 25%, Vừa 50%, Gốc 100%, hoặc tùy chỉnh Width/Height HTML) và bổ sung Contextual Format Tab trên thanh Ribbon Bar khi thao tác với hình ảnh. | ⏳ Planned |
| **Recent Files History** | `src/ui_flet/views/welcome_view.py` | Lưu danh sách tệp vừa mở gần đây (Recent Documents) để mở lại nhanh từ Welcome Dashboard. | ⏳ Planned |
| **AI Auto-Link Engine** | `src/services/ai_link_service.py` | Gợi ý liên kết thông minh giữa các ghi chú dựa trên Semantic Embeddings / Local Vector Search. | ⏳ Planned |


---

## Hướng dẫn khởi chạy & Đóng gói sản phẩm

### 1. Khởi chạy ứng dụng (Development):
```powershell
python run.py
```

### 2. Đóng gói bộ cài đặt tự động 1-Click (PyInstaller `--onedir` + Inno Setup 7):
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1
```
Tự động xuất ra thư mục `--onedir` tại `dist/Document Converter/` và file cài đặt tại `dist/installer/Document_Converter_Setup_v1.7.2.exe`.

### 3. Đóng gói thủ công bằng PyInstaller:
```powershell
python -m PyInstaller "Document Converter.spec"
```

