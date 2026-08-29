# Document Converter Workspace — Product Roadmap

---

## 📌 Tổng quan hiện trạng & Lịch sử phát hành

### ✅ Đã hoàn thành (v1.0 – v1.4.0):
| Phase / Feature | Nội dung chính | Trạng thái |
| :--- | :--- | :--- |
| **P0 – Stabilization** | File extension validation, overwrite confirmation, fallback engines, unsaved warning | ✅ Completed |
| **P1 – UX & Format** | CSV ↔ MD, search & replace (Smart Hybrid focus), formatting toolbar, autosave draft (1.5s debounce) | ✅ Completed |
| **P2 – Format Expansion** | PDF ➔ MD (stitching tables, multiline cell continuation, slide image extraction), HTML ↔ MD | ✅ Completed |
| **P3 – Flet UI Migration** | Responsive split-pane layout, 4-Palette design tokens, instant 0ms container theme updates | ✅ Completed |
| **P4 – Native Dialogs & 3-Tier UI** | Async Win32 FileDialog via `asyncio.to_thread`, High-DPI Per-Monitor v2, 3-Tier modular layout (`layout/`, `components/`, `views/`). | ✅ Completed |
| **P4.2 – Pure Orchestrator MVC** | AppState, 6 Controllers (`file`, `editor`, `search`, `theme`, `conversion`, `layout`), Welcome Dashboard, Ribbon Bar 4 tabs | ✅ Completed |
| **P4.3 – PDF Polish & Packaging** | PDF list/bullet preservation, Vietnamese font handling, HTML code fence regex auto-repair, PyInstaller `hiddenimports`, Pinned requirements | ✅ Completed |
| **P4.4 – Settings, i18n & User Guide** | Option Settings View (i18n, font size, autosave interval), Help & User Guide View, Word Exporter Image Embed (`@media/`), Win32 Z-Order Focus Enhancement | ✅ Completed |

---

### ✅ v1.7.0 (Simplified Single-Row Ribbon, YouTube Extractor, Direct MD Export & UI Polish):
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

### ✅ v1.7.2 (YouTube In-App Companion Player, Interactive Timestamps & Packaging):
| Hạng mục | Vị trí / Tầng ảnh hưởng | Mô tả chi tiết & Hướng phát triển | Trạng thái |
| :--- | :--- | :--- | :---: |
| **In-App YouTube Companion Player** | `src/services/youtube_player.py` | Cửa sổ WebView2 (`540x335`, 16:9, Top-Left `x=24, y=65`), Local HTTP Bridge Server `127.0.0.1` chống Error 153, cờ `--autoplay-policy=no-user-gesture-required`. | ✅ Completed (v1.7.2) |
| **Interactive Timestamps (`yt://...`)** | `src/ui_flet/views/preview_view.py` | Tự động phân tích mốc `[mm:ss]` thành link tương tác `[mm:ss](yt://<id>?t=sec)`, click để tua video trực tiếp trong app hoặc fallback trình duyệt. | ✅ Completed (v1.7.2) |
| **Dynamic Win32 Window Focus (Non-Pinning)** | `src/services/youtube_player.py` | `on_top=False`, sử dụng `_force_window_foreground` với Win32 `AttachThreadInput` và `SetForegroundWindow` đưa cửa sổ lên đỉnh tức thì khi click timestamp. | ✅ Completed (v1.7.2) |
| **Folder Mode (`--onedir`) & Inno Setup 7 Installer** | `Document Converter.spec` / `installer/` | Chuyển đổi đóng gói sang Thư mục (`--onedir`) kết hợp bộ cài đặt Inno Setup 7 (`Setup.exe`), khởi động tức thì < 1s, phân quyền `%LocalAppData%\Programs`. | ✅ Completed (v1.7.2) |
| **Auto YouTube Draft Restoration** | `src/ui_flet/controllers/file_controller.py` | Nhận diện phụ đề YouTube khi nạp lại bản nháp khởi động, tự động bật nút `▶ Watch Video` và phân giải timestamp. | ✅ Completed (v1.7.2) |
| **3-Layer Sync Auto-Close & Packaging** | `Document Converter.spec`, `run.py`, `layout_controller.py` | Đóng đồng bộ khi tắt app chính qua Window Event + `atexit` + `stdin` EOF; hỗ trợ chạy subprocess độc lập trong file `.exe`. | ✅ Completed (v1.7.2) |

---

### ✅ v1.8.0 / v1.8.1 (Studio Workspace & Multi-Doc Architecture):
| Hạng mục | Vị trí / Tầng ảnh hưởng | Mô tả chi tiết & Hướng phát triển | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Activity Bar & File Explorer** | `src/ui_flet/layout/activity_bar.py`, `src/ui_flet/views/explorer_view.py` | Dải dọc 48px Vector Icons (`ft.Icons.*`) + Sidebar cây thư mục dự án (Lazy-loading, Async I/O, Inline Real-time File Filter, phím tắt `Ctrl+B`). | ✅ Completed (v1.8.0) |
| **Quick Open File Switcher (`Ctrl+P`)** | `src/ui_flet/components/quick_open_dialog.py` | Modal Palette tìm kiếm mờ (fuzzy search) duyệt toàn bộ file trong Workspace, điều hướng bàn phím (`Enter`, `Esc`, Click outside dismiss). | ✅ Completed (v1.8.0) |
| **Draggable Split Panes (Splitter)** | `src/ui_flet/components/draggable_splitter.py` | Thanh kéo co giãn 60fps mượt mà giữa Sidebar ↔ Workspace và Editor ↔ Preview, Snap-to-Collapse (<100px), bounds (150-500px, 20%-80%), persistence `settings.json`. | ✅ Completed (v1.8.0) |
| **Overhauled 2x2 Welcome Screen** | `src/ui_flet/views/welcome_view.py` | Lưới 4 Thẻ tác vụ 2x2 trực quan, phím tắt vật lý `<kbd>`, độ tương phản màu chuẩn xác Dark/Light Mode. | ✅ Completed (v1.8.0) |
| **Explorer Context Menu & Safe File Ops** | `src/ui_flet/components/context_menu.py`, `src/ui_flet/components/file_modals.py`, `src/utils/file_ops.py`, `src/ui_flet/views/explorer_view.py` | Menu chuột phải nổi IDE, Win32 `SHFileOperationW` Recycle Bin (zero data loss), Smart 2-Tier Quick Convert (1-click to MD, 8 export formats flyout), Rename, Safe Delete (cảnh báo `is_dirty`), New File/Folder, nút *Collapse All Folders*, và Responsive Header (Actions Dropdown khi < 210px). | ✅ Completed (v1.8.1a) |
| **Draggable Multi-Tab Workspace** | `src/ui_flet/components/workspace_tab_bar.py`, `src/ui_flet/controllers/layout_controller.py` | Quản lý đa Tab độc lập, hỗ trợ kéo thả sắp xếp lại thứ tự Tab (`ft.Draggable` & `ft.DragTarget`), animated `ProgressRing` loading cho file nặng, phím tắt chuyển tab `Ctrl+Tab` / `Ctrl+Shift+Tab`, `Ctrl+T`, `Ctrl+W`. Menu chuột phải quản lý Tab (Đóng tab, đóng các tab khác, đóng tab bên phải, đóng tất cả, copy path, reveal explorer) và thanh cuộn 3px siêu mỏng. | ✅ Completed (v1.8.1b) |
| **Multi-Tab `AppState` & Draft Sessions** | `src/ui_flet/state.py`, `src/services/media_asset_manager.py`, `src/ui_flet/controllers/file_controller.py` | Nâng cấp `AppState` sang `DocumentTabState` với Property Delegation không gây breaking change; Autosave draft riêng biệt theo `drafts/{tab_id}.md` & `tab_session.json`; Cô lập bộ nhớ đệm ảnh theo `media_session_id`; Bộ nhớ đệm 0ms RAM Preview và Atomic Concurrency Guard. | ✅ Completed (v1.8.1b) |
| **Smart Drag & Drop (Editor Insert)** | `src/ui_flet/views/explorer_view.py`, `src/ui_flet/views/editor_view.py` | Kéo file từ Explorer thả vào Editor để tự động chèn cú pháp Link `[Tên](path)` hoặc nhúng ảnh `![Ảnh](path)` vào tab đang active; Hỗ trợ mở link tương đối từ Workspace trong tab Untitled. | ✅ Completed (v1.8.1c) |
| **Filesystem Drag & Drop (Move)** | `src/ui_flet/views/explorer_view.py`, `src/utils/file_ops.py` | Kéo thả tệp/thư mục nội bộ cây thư mục Explorer để di chuyển tệp vật lý (`ft.Draggable` & `ft.DragTarget` nội bộ Flet), tích hợp bộ kiểm tra an toàn `validate_move_operation` và đồng bộ hóa Workspace Tabs. | ✅ Completed (v1.8.1c) |
| **Batch & Archive Converter** | `src/services/batch_service.py`, `src/ui_flet/components/batch_dialog.py` | Chuyển đổi hàng loạt tài liệu theo Thư mục hoặc Tệp nén (`.zip`, `.rar`, `.7z`, `.tar.gz`) chạy ngầm (`ThreadPoolExecutor`), tự động cô lập lỗi (Error Isolation), giữ nguyên cây thư mục và đóng gói xuất ra `.zip` hoặc folder kết quả. Bổ sung hook *"Batch Convert this Folder"* vào Context Menu và Archive File Picker chuyên dụng. | ✅ Completed (v1.8.1c) |
| **Mermaid Diagram Live Preview** | `src/ui_flet/views/preview_view.py`, `src/utils/mermaid_renderer.py` | Hỗ trợ hiển thị sơ đồ Mermaid trong Live Preview bằng giải pháp Hybrid Interceptor (chuyển khối mã ````mermaid```` thành ảnh SVG/PNG Base64 nhúng trực tiếp vào `ft.Markdown`). | ✅ Completed (v1.8.0) |

---

### ✅ v1.8.2 (Floating Image Formatting, Multi-Tab Footer Sync & Explorer UX Polish):

| Hạng mục | Vị trí / Tầng ảnh hưởng | Mô tả chi tiết & Hướng phát triển | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Floating Image Format & Alignment Engine** | `src/modules/word_module.py`, `src/ui_flet/components/context_menu.py`, `src/ui_flet/views/preview_view.py` | Engine căn lề ảnh (Trái, Giữa, Phải) sử dụng cú pháp chuẩn `<p align="...">`, đồng bộ 100% khi xuất sang Word `.docx` bằng `WD_ALIGN_PARAGRAPH`. Menu chuột phải trên Live Preview nhấp vào ảnh để chỉnh kích thước hoặc căn lề. | ✅ Completed (v1.8.2) |
| **Redesigned `ImageSizeDialog`** | `src/ui_flet/components/image_size_dialog.py` | Giao diện điều chỉnh kích thước ảnh trực quan, cân đối chiều cao input/dropdown, loại bỏ khoảng trắng thừa, phím bấm hàng ngang (`Reset`, `Cancel`, `Apply Sizing`), hỗ trợ nhấp ra ngoài để đóng và xử lý vòng đời overlay an toàn. | ✅ Completed (v1.8.2) |
| **Multi-Tab Conversion State & Per-Tab FooterBar Sync** | `src/ui_flet/controllers/layout_controller.py`, `src/ui_flet/controllers/file_controller.py`, `src/ui_flet/layout/footer_bar.py` | Đồng bộ hóa trạng thái chuyển đổi và 2 nút `Open File` / `Open Location` theo từng Tab độc lập (`Per-Tab Hydration`); tự động ẩn khi nạp tệp mới từ Explorer hoặc khi Tab chưa được chuyển đổi. | ✅ Completed (v1.8.2) |
| **Explorer Tree Scrolling & Clipping Fix** | `src/ui_flet/views/explorer_view.py` | Sửa triệt để lỗi mất thanh cuộn cây thư mục và lỗi hiển thị tràn viền xuống thanh Footer bằng `ClipBehavior.HARD_EDGE` và cấu trúc Flex Container chuẩn mực tương tự `EditorView`. | ✅ Completed (v1.8.2) |
| **Smart Expanded Folder State Preservation** | `src/ui_flet/views/explorer_view.py` | Ghi nhớ đệ quy danh sách thư mục đang mở trước khi làm mới (`restore_expanded`), phân biệt hoàn hảo giữa `Refresh` (giữ nguyên các folder đang mở) và `Collapse All` (thu gọn toàn bộ). | ✅ Completed (v1.8.2) |
| **Full Folder Zone Drag & Drop** | `src/ui_flet/views/explorer_view.py` | Kéo thả tệp vào bất kỳ tệp con nào bên trong một thư mục đang mở rộng sẽ chuyển tệp vào đúng thư mục đó; loại bỏ vùng bắt rác toàn cục và gán điểm đón an toàn cho thư mục gốc. | ✅ Completed (v1.8.2) |
| **Fixed Keyboard Shortcut `Ctrl+B`** | `src/ui_flet/controllers/layout_controller.py` | Khắc phục lỗi phím tắt `Ctrl+B` không đóng mở được Sidebar do điều kiện event `e is not None`. | ✅ Completed (v1.8.2) |

---

## 🚀 Kế hoạch phát triển các phiên bản tiếp theo

### 🛠️ v1.8.3 (Patch, Backlog & Memory Optimization):

| Hạng mục | Vị trí / Tầng ảnh hưởng | Mô tả chi tiết & Hướng phát triển | Trạng thái |
| :--- | :--- | :--- | :---: |
| **`PERF-001` Bounded LRU Cache & Session Purge** | `src/ui_flet/views/preview_view.py`, `src/services/media_asset_manager.py` | Chuyển đổi `_BASE64_CACHE` sang `OrderedDict` (tối đa 128 mục) thread-safe; Tích hợp hook `purge_session_base64_cache()` giải phóng 100% RAM ảnh khi đóng Tab. *(Xem `docs/backlog/PERF_001_base64_cache_lru_eviction.md`)*. | 🟡 In Progress |
| **Batch Collision Disambiguation & Polish** | `src/services/batch_service.py`, `src/ui_flet/components/batch_dialog.py` | Tự động gắn hậu tố `(docx)`, `(pdf)` khi nhiều tệp trùng tên gốc trong cùng thư mục xuất sang `.md`; Nâng cấp `open_file_or_foreground` (Win32 Z-Index #1) cho nút Open Result. | ✅ Completed |

---

### 🎙️ v1.9.0 (AI Model Hub, Offline Speech Transcriber & Format Expansion):

| Hạng mục | Vị trí / Tầng ảnh hưởng | Mô tả chi tiết & Hướng phát triển | Trạng thái |
| :--- | :--- | :--- | :---: |
| **AI Model Hub & Marketplace** | `src/ui_flet/components/model_hub_dialog.py`, `src/ui_flet/views/settings_view.py` | Giao diện quản lý tải/xóa Model AI độc lập (`tiny`, `base`, `small`, `PhoWhisper`); Tự động quét phần cứng (RAM, CPU Cores, GPU) gắn nhãn gợi ý; Quản lý dung lượng ổ cứng tại `%APPDATA%\DocConvert\models\`. *(Xem `docs/roadmaps/whisper_feature_plan.md`)*. | ⏳ Planned (Hero Feature) |
| **Offline Audio/Video Speech Transcriber** | `src/services/whisper_service.py` | Engine `faster-whisper` + CTranslate2 (`int8`); Giải mã âm thanh đa định dạng `.mp4`, `.mp3`, `.wav`, `.m4a`; Phân đoạn Voice Activity Detection (VAD) mốc thời gian `[mm:ss]` và format Markdown có cấu trúc. | ⏳ Planned |
| **Recent Files History** | `src/ui_flet/views/welcome_view.py`, `src/ui_flet/controllers/file_controller.py` | Lưu danh sách 5–10 tệp mở gần đây (Recent Documents) có biểu tượng định dạng, đường dẫn rút gọn và hỗ trợ mở lại nhanh 1-click từ Welcome Dashboard. | ⏳ Planned |
| **Image Sizing Dialog & Format Tab** | `src/ui_flet/views/editor_view.py`, `src/ui_flet/layout/ribbon_bar.py` | Hộp thoại tùy chỉnh kích thước/tỷ lệ hình ảnh trực quan (Nhỏ 25%, Vừa 50%, Gốc 100%, hoặc tùy chỉnh W/H) và bổ sung Contextual Format Tab động trên Ribbon Bar khi click vào ảnh. | ⏳ Planned |
| **EPub eBook Engine (`.epub ↔ .md`)** | `src/modules/epub_module.py` | Đọc, phân giải cấu trúc chương sách và đóng gói sách điện tử `.epub` hai chiều với Markdown. | ⏳ Planned |

---

### 🔮 v2.0.0 (Personal Knowledge Base & Network Graph Ecosystem):

| Hạng mục | Vị trí / Tầng ảnh hưởng | Mô tả chi tiết & Hướng phát triển | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Manual Wikilinks `[[...]]`** | `src/services/link_parser.py` | Cú pháp liên kết hai chiều kiểu Obsidian `[[Tên File]]` hoặc `[[Tên File\|Tên hiển thị]]`; Bộ phân giải Fuzzy Match (bỏ dấu tiếng Việt `NFD`, case-insensitive, trim space); In-memory graph index. | 🔮 Planned (v2.0) |
| **Broken Link Handling & Click-to-Create** | `src/ui_flet/views/preview_view.py`, `src/ui_flet/controllers/file_controller.py` | Hiển thị link chưa tồn tại bằng màu cảnh báo / gạch chân đứt nét; Hỗ trợ Click để tự động tạo file `.md` mới trong Workspace và mở tab mới tức thì. | 🔮 Planned (v2.0) |
| **Backlink Panel** | `src/ui_flet/views/backlink_view.py`, `src/ui_flet/layout/activity_bar.py` | Panel thanh bên hiển thị danh sách các tài liệu đang dẫn nguồn về tài liệu hiện hành (*Linked References* & *Unlinked Mentions*). | 🔮 Planned (v2.0) |
| **Interactive Knowledge Graph View** | `src/ui_flet/views/graph_view.py` | Bản đồ đồ thị tri thức tương tác trực quan 2D kết nối tất cả các ghi chú trong toàn bộ thư mục Workspace. | 🔮 Planned (v2.0) |
| **AI Auto-Link Engine** | `src/services/ai_link_service.py` | Gợi ý liên kết thông minh giữa các tài liệu dựa trên Semantic Embeddings / Local Vector Search. | 🔮 Planned (v2.0) |

---

## 🛠️ Hướng dẫn khởi chạy & Đóng gói sản phẩm

### 1. Khởi chạy ứng dụng (Development):
```powershell
python run.py
```

### 2. Đóng gói bộ cài đặt tự động 1-Click (PyInstaller `--onedir` + Inno Setup 7):
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1
```
Tự động xuất ra thư mục `--onedir` tại `dist/Document Converter/` và file cài đặt tại `dist/installer/Document_Converter_Setup_v1.8.1.exe`.

### 3. Đóng gói thủ công bằng PyInstaller:
```powershell
python -m PyInstaller "Document Converter.spec"
```
