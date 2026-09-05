# Background Transcription, Tab Integration & Universal Media Support (Phase 3 — v1.9.0)

**Phiên bản**: `v1.9.0-dev`  
**Ngày cập nhật**: 03/09/2026  
**Nhánh liên quan**: `feat/duy-03092026-background-transcription-and-tabs`  

---

## 1. Tầm Nhìn & Bối Cảnh

Sau khi Pha 1 (Model Hub & Hardware Orchestrator) và Pha 2 (Core AI Engine & Audio Decoder) đã hoàn thành, nhánh này thực hiện **Pha 3: Tích hợp toàn diện End-to-End** — kết nối hệ thống nhận diện giọng nói Whisper vào Studio Workspace thông qua:

1. **Background Task Orchestration**: Transcription chạy ngầm không đóng băng GUI, người dùng tiếp tục làm việc trên các tab khác.
2. **Smart Tab Creation**: Kết quả Whisper tự động mở thành Tab mới trong Workspace với mode "Save as .md", autosave draft tức thì.
3. **Universal Media Container Support**: Hỗ trợ mọi container audio/video phổ biến (.mp3, .wav, .m4a, .flac, .aac, .ogg, .mp4, .mkv, .avi, .mov, .webm).
4. **Activity Bar Smart Context Routing**: Icon trạng thái spinning trên Activity Bar, click để mở lại dialog tiến trình đang chạy.

---

## 2. Giải Pháp Kỹ Thuật Đã Triển Khai

### 2.1. TranscribeDialog — Giao Diện Chuyển Đổi Âm Thanh Cục Bộ (`src/ui_flet/components/transcribe_dialog.py`)

- **Thiết kế lại hoàn toàn**: Chuyển từ dialog đơn giản sang giao diện chuyên dụng với Live Progress Bar, log hiển thị thời gian thực, nút Cancel Task an toàn.
- **Re-entrant Dialog**: Khi task đang chạy, click lại icon trên Activity Bar sẽ mở lại dialog với trạng thái tiến trình hiện tại thay vì tạo dialog mới.
- **Quy trình 3 bước**: (1) Chọn file media -> (2) Chọn model -> (3) Bấm Start, theo dõi tiến trình.

### 2.2. YouTubeDialog — Tái Cấu Trúc Dialog YouTube/Drive (`src/ui_flet/components/youtube_dialog.py`)

- **Tách biệt rõ trạng thái**: Dialog phân biệt giữa trạng thái Idle (nhập URL) và Running (hiển thị tiến trình).
- **Đồng bộ Activity Bar**: Icon spinning trên Activity Bar phản ánh chính xác task YouTube/Drive đang chạy.

### 2.3. Activity Bar Smart Context Routing (`src/ui_flet/app.py`, `src/ui_flet/layout/activity_bar.py`)

- **Icon Spinning động**: Khi có task transcription đang chạy, Activity Bar hiển thị icon media spinning (animation xoay liên tục).
- **Smart Re-open Logic**: Click icon spinning khi task `local_media` đang chạy -> mở lại `TranscribeDialog`; khi task YouTube/Drive đang chạy -> mở lại `YouTubeDialog`.
- **Trạng thái tự động reset**: Khi task hoàn tất hoặc bị hủy, icon trở về trạng thái tĩnh bình thường.

### 2.4. File Controller — Background Tab Creation & Draft Persistence (`src/ui_flet/controllers/file_controller.py`)

- **`_open_or_create_transcript_tab()`**: Logic thông minh tạo Tab mới cho kết quả transcription:
  - Nếu tab đang active là tab trống (chưa có nội dung) -> tái sử dụng tab đó.
  - Nếu tab đang active đã có nội dung -> tạo tab nền mới, không làm gián đoạn công việc hiện tại.
- **Auto Draft Persistence**: Gọi `perform_autosave(tab_id=...)` ngay sau khi tạo tab, đảm bảo 100% nội dung transcript được lưu vào `drafts/{tab_id}.md` ngay tức thì.
- **Mode Assignment**: Tab transcript luôn được gán `current_mode = "MD -> Markdown"` (hiển thị là "Save as .md" / "Lưu tệp Markdown (.md)").
- **Property Access Fix**: Sửa lỗi truy cập `active_tab.content` -> `active_tab.full_content` và `active_tab.mode` -> `active_tab.current_mode` theo đúng schema `DocumentTabState`.

### 2.5. Layout Controller — Tab Switch Mode Hydration (`src/ui_flet/controllers/layout_controller.py`)

- **Ưu tiên mode riêng từng tab**: Khi chuyển tab, ưu tiên `incoming_tab.current_mode` trước `default_mode` của AppState, đảm bảo mỗi tab giữ đúng mode riêng (ví dụ: Tab A = "MD -> PDF", Tab Transcript = "Save as .md").

### 2.6. Conversion Controller — Ribbon Bar Sync (`src/ui_flet/controllers/conversion_controller.py`)

- **Fix `AttributeError`**: Bổ sung `self.ribbon_bar = app_controls.get("ribbon_bar")` vào `__init__`.
- **Đồng bộ Toggle Icon**: Khi hộp thoại Overwrite tự động bật File Path Bar lên, đồng thời gọi `ribbon_bar.set_path_bar_visible(True)` để icon trên Ribbon phản ánh đúng trạng thái active/inactive.

### 2.7. Universal Media File Dialog (`src/ui_flet/native_dialogs.py`)

- **Mở rộng `INPUT_FILETYPES`**: Bổ sung toàn bộ container audio/video phổ biến vào bộ lọc hộp thoại mở file:
  - Audio: `*.mp3`, `*.wav`, `*.m4a`, `*.flac`, `*.aac`, `*.ogg`
  - Video: `*.mp4`, `*.mkv`, `*.avi`, `*.mov`, `*.webm`
- **Auto-route Media Files**: Khi mở file media từ File Dialog hoặc Explorer, tự động chuyển hướng sang `trigger_media_transcribe` thay vì cố gắng đọc như tài liệu văn bản.

### 2.8. i18n Localization cho Transcript Metadata (`src/services/whisper_service.py`, `src/i18n/locales/*.json`)

- **Quốc tế hóa bảng metadata**: Thêm translation keys cho bảng thông tin transcript:
  - `transcript.info_file`, `transcript.info_duration`, `transcript.info_model`, `transcript.info_language`, `transcript.info_segments`, `transcript.info_date`, `transcript.info_header`
- **`whisper_service.py` sử dụng `t(...)`**: Đảm bảo bảng metadata phản ánh đúng ngôn ngữ đang chọn trong app (Tiếng Việt / English).

### 2.9. Ribbon Bar Cleanup (`src/ui_flet/layout/ribbon_bar.py`)

- **Xóa nút YouTube thừa**: Loại bỏ `btn_youtube` khỏi toolbar row vì chức năng đã có icon chuyên dụng trên Activity Bar.

### 2.10. Model Hub Dialog Polish (`src/ui_flet/components/model_hub_dialog.py`)

- **Cải thiện UX**: Tinh chỉnh giao diện Model Hub cho phù hợp với luồng sử dụng mới (từ Activity Bar thay vì từ Ribbon).

---

## 3. Workspace Retention khi 0 Tabs

Sửa triệt để lỗi app quay về Welcome View khi không có tab nào mở mặc dù vẫn có workspace folder đang mở:

- **`has_draft_on_disk()`**: Kiểm tra chính xác sự tồn tại của draft files.
- **`async_load_draft_if_exists()`**: Khi khôi phục 0 tabs nhưng có `workspace_folder`, giữ nguyên Editor Workspace View với File Explorer hiển thị.

---

## 4. Danh Sách File Thay Đổi

| File | Loại thay đổi | Mô tả ngắn |
| :--- | :---: | :--- |
| `src/ui_flet/components/transcribe_dialog.py` | MODIFY | Thiết kế lại dialog transcription cục bộ với Live Progress |
| `src/ui_flet/components/youtube_dialog.py` | MODIFY | Tái cấu trúc dialog YouTube/Drive với trạng thái Idle/Running |
| `src/ui_flet/app.py` | MODIFY | Smart Activity Bar routing, window title update |
| `src/ui_flet/layout/activity_bar.py` | MODIFY | Icon spinning động, trạng thái task |
| `src/ui_flet/controllers/file_controller.py` | MODIFY | Background tab creation, draft persistence, mode assignment |
| `src/ui_flet/controllers/layout_controller.py` | MODIFY | Tab switch mode hydration ưu tiên current_mode |
| `src/ui_flet/controllers/conversion_controller.py` | MODIFY | Ribbon bar sync, fix AttributeError |
| `src/ui_flet/layout/ribbon_bar.py` | MODIFY | Xóa nút YouTube thừa |
| `src/ui_flet/native_dialogs.py` | MODIFY | Universal media container file dialog |
| `src/ui_flet/components/model_hub_dialog.py` | MODIFY | UX polish |
| `src/services/whisper_service.py` | MODIFY | i18n localization cho metadata |
| `src/i18n/locales/en.json` | MODIFY | Thêm transcript.info_* keys |
| `src/i18n/locales/vi.json` | MODIFY | Thêm transcript.info_* keys |
| `tests/test_whisper_service.py` | MODIFY | Cập nhật assertions theo i18n |
| `src/services/transcription_manager.py` | NEW | Quản lý transcription task lifecycle |
| `tests/test_transcription_manager.py` | NEW | Unit tests cho TranscriptionManager |

---

## 5. Kiểm Thử & Xác Minh

- **181/181 unit tests**: Passed cleanly (`OK`).
- **Runtime Verification**: Kiểm tra thực tế trên app với file audio, xác nhận:
  - Tab tạo ra có mode "Save as .md"
  - Draft được lưu ngay lập tức
  - Tab switch giữ đúng mode riêng
  - Activity Bar icon spinning/reset đúng trạng thái
  - Ribbon Bar toggle icon đồng bộ khi File Path Bar được auto-reveal
