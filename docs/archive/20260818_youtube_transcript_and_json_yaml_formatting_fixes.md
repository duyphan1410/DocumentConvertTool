# 📦 PR Archive Snapshot — 18/08/2026: YouTube Subtitles/Transcript Extractor, Non-AI Speech Fallback, Markdown Direct Export & JSON/YAML Formatting Fixes

- **Branch Name:** `feat/huy-180820026-youtube-transcript`, `fix/huy-18082026-json/yaml-formatting`
- **Date:** 18/08/2026
- **Status:** Merged into `dev`
- **Target Components:** `src/services/youtube_service.py`, `src/services/speech_service.py`, `src/ui_flet/components/youtube_dialog.py`, `src/utils/clipboard.py`, `src/ui_flet/native_dialogs.py`, `src/ui_flet/views/editor_view.py`, `src/ui_flet/controllers/file_controller.py`, `src/ui_flet/controllers/conversion_controller.py`, `src/ui_flet/constants.py`, `src/ui_flet/layout/ribbon_bar.py`, `src/ui_flet/views/welcome_view.py`, `src/modules/json_module.py`, `src/modules/yaml_module.py`, `src/i18n/locales/vi.json`, `src/i18n/locales/en.json`, `requirements.txt`, `Document Converter.spec`, `tests/test_youtube_service.py`, `tests/test_speech_service.py`, `tests/test_json_yaml_modules.py`

---

## 📌 PR Summary & Objectives

Bản cập nhật hoàn thiện hai nhóm tính năng cốt lõi cho phiên bản **v1.7.0**:
1. **Trích xuất nội dung từ Video YouTube sang Markdown (`YouTube ➔ MD`)**:
   - Triển khai kiến trúc Đa tầng (Multi-tier Strategy):
     - **Tầng 1 (Subtitles & Auto-Translate)**: Lấy phụ đề gốc trực tiếp từ YouTube API theo ngôn ngữ mong muốn (Việt / Anh). Tự động gọi tính năng **Dịch tự động (Auto-Translate)** từ máy chủ YouTube nếu video chỉ có phụ đề ngôn ngữ khác (xử lý tức thì, 0% tải CPU/RAM cục bộ).
     - **Tầng 2 (Lightweight Speech Recognition Fallback - Zero AI Model)**: Khi video hoàn toàn không có phụ đề, hệ thống kích hoạt luồng bóc tách audio stream bằng `yt-dlp` và nhận diện giọng nói qua `SpeechRecognition` (Google Web Speech API / SAPI) chia nhỏ theo block 20s, lọc khoảng lặng, gán mốc thời gian `**[mm:ss]**`.
   - Hỗ trợ mọi định dạng liên kết YouTube (`watch?v=`, `youtu.be/`, `shorts/`, `embed/`, `live/`, `m.youtube.com/`).
   - Tự động lấy metadata chuẩn (Tiêu đề Video, Tên Kênh) qua YouTube oEmbed API để đặt tên file và sinh Header Markdown.
2. **Trải nghiệm Lưu / Xuất Tệp Markdown Trực Tiếp (`.md`)**:
   - Bổ sung chế độ **`MD -> Markdown` (`Lưu tệp Markdown (.md)`)** trong Conversion Mode, tự động kích hoạt sau khi import từ YouTube.
   - Thống nhất thao tác lưu tệp Markdown qua phím tắt **`Ctrl + S`**, nút **Lưu tệp (`💾`)** trên Ribbon Bar và nút **CHUYỂN ĐỔI** ở Footer Bar.
   - Tự động liên kết và bật nút `Mở tệp` & `Mở thư mục` trên Footer Bar ngay sau khi lưu tệp Markdown thành công.
3. **Nâng cấp Clipboard Win32 & Tự động điền URL**:
   - Tích hợp đọc bộ nhớ Clipboard Windows trực tiếp qua Win32 API (`CF_UNICODETEXT` / `user32.dll` kèm Retry Loop), tự động nhận diện và điền link YouTube khi vừa mở hộp thoại.
   - Tích hợp cơ chế **Inline Error Feedback** trên hộp thoại YouTube giúp loại bỏ 100% nguy cơ treo app do xung đột modal barrier.
4. **Sửa lỗi định dạng Chuỗi nhiều dòng & Ký tự thoát (Escape Sequences) trong JSON / YAML**:
   - Khắc phục triệt để lỗi chuỗi nhiều dòng bị hiển thị thành chuỗi escape (`\n`, `\t`, `\r\n`) trong Markdown Editor và ngược lại.
   - Hỗ trợ giữ nguyên tab indent, line break tự nhiên khi chuyển đổi hai chiều `JSON ↔ MD` và `YAML ↔ MD`.

---

## 🛠️ Chi Tiết Triển Khai & File Thay Đổi

### 1. Dịch Vụ Trích Xuất YouTube & Nhận Diện Giọng Nói
- **`src/services/youtube_service.py`**:
  - `extract_video_id(url)`: Regex trích xuất Video ID hỗ trợ đầy đủ các biến thể URL (Standard, Shortened, Shorts, Embed, Live, Mobile).
  - `get_video_metadata(video_id)`: Gọi YouTube oEmbed API (`https://www.youtube.com/oembed?url=...&format=json`) để trích xuất `title` và `author_name`.
  - `fetch_youtube_transcript(video_id, preferred_lang, allow_auto_translate)`: Trích xuất danh sách phụ đề qua `youtube_transcript_api`, tự động ưu tiên phụ đề thủ công / auto-generated / auto-translated sang ngôn ngữ đích.
  - `format_transcript_to_markdown(transcript_data, title, author, video_id, language)`: Sinh văn bản Markdown hoàn chỉnh kèm Header metadata và các block thời gian `**[mm:ss]** text`.
- **`src/services/speech_service.py`**:
  - Tích hợp `yt-dlp` để stream và tải luồng âm thanh nhẹ (`bestaudio[ext=m4a]/bestaudio`) sang thư mục tạm.
  - Sử dụng `SpeechRecognition` với bộ nhận diện `recognize_google` (hoặc SAPI trên Windows) chia nhỏ audio thành các đoạn 20s.
  - Tự động lọc các đoạn im lặng và gộp kết quả kèm timestamp tương ứng.
- **`src/ui_flet/components/youtube_dialog.py`**:
  - Hộp thoại giao diện hiện đại với input URL, nút Dán từ Clipboard (`Win + V`), lựa chọn ngôn ngữ đích (Tiếng Việt `vi` / Tiếng Anh `en`), tùy chọn Auto-Translate và Speech Recognition Fallback.
  - Hiển thị thanh tiến trình xử lý `ft.ProgressBar` và thông báo trạng thái trực quan.

### 2. Clipboard Win32 & Native Dialogs
- **`src/utils/clipboard.py`**:
  - Xây dựng hàm `get_clipboard_text()` an toàn trên Windows sử dụng `ctypes.windll.user32` với định dạng `CF_UNICODETEXT` (hỗ trợ đầy đủ tiếng Việt có dấu, không bị lỗi font hay crash clipboard lock).
  - Fallback an toàn sang `tkinter` trên macOS / Linux.
- **`src/ui_flet/native_dialogs.py`**:
  - Tự động cấu hình `Tcl/Tk` tránh lỗi khởi tạo hộp thoại.

### 3. Direct Markdown Export & UI Controller Polish
- **`src/ui_flet/views/editor_view.py`**:
  - Thêm nút Tải nhanh Markdown (`btn_save_md`, icon `ft.Icons.DOWNLOAD_ROUNDED`) trên thanh Header của Editor Buffer.
- **`src/ui_flet/controllers/file_controller.py`**:
  - Bổ sung phương thức `trigger_save_markdown()` xử lý lưu tệp `.md` trực tiếp từ buffer soạn thảo.
  - Sau khi lưu, cập nhật trạng thái `AppState.last_converted_path` và kích hoạt ngay các nút `Mở tệp` / `Mở thư mục` trên Footer Bar.
- **`src/ui_flet/controllers/conversion_controller.py`**:
  - Cập nhật logic mở tệp/thư mục hỗ trợ linh hoạt cả tệp chuyển đổi thông thường lẫn tệp Markdown vừa xuất trực tiếp.
- **`src/ui_flet/constants.py`**:
  - Bổ sung mode `MD -> Markdown` (`Lưu Markdown (.md)`) vào danh mục `MODES` và ánh xạ phần mở rộng `.md`.
- **`src/ui_flet/layout/ribbon_bar.py` & `src/ui_flet/views/welcome_view.py`**:
  - Thêm nút tác vụ nhanh `Nhập từ YouTube` (`ft.Icons.ONDEMAND_VIDEO_ROUNDED` / `ft.Icons.SMART_DISPLAY_ROUNDED`) trên Ribbon Bar và Welcome Dashboard.

### 4. JSON / YAML Multiline & Escape Sequence Formatting Fixes
- **`src/modules/json_module.py` & `src/modules/yaml_module.py`**:
  - Khắc phục lỗi hiển thị chuỗi escape `\n`, `\r\n`, `\t` khi chuyển đổi từ JSON/YAML sang Markdown.
  - Khi lưu từ Markdown trở lại JSON/YAML, cơ chế stateful parser nhận diện các dòng văn bản thụt lề liên tiếp (multiline continuation) và gộp lại vào key hoặc list item trước đó với ký tự xuống dòng thực tế thay vì escape string thô.
  - Chuyển đổi an toàn các ký tự `\r\n`, `\n`, `\t` trong hàm `_coerce_value()`.

---

## 🧪 Kết Quả Kiểm Thử (Verification)

1. **Unit Tests JSON / YAML**:
   - Bổ sung các test cases kiểm thử chuỗi nhiều dòng (`test_json_multiline_string_roundtrip`, `test_json_tab_and_indent_preservation`, `test_yaml_multiline_string_roundtrip`, `test_yaml_tab_and_indent_preservation`).
2. **Unit Tests YouTube Service & Speech Service**:
   - `tests/test_youtube_service.py`: Kiểm thử regex trích xuất video ID, metadata oEmbed, auto-translate fallback, và định dạng Markdown.
   - `tests/test_speech_service.py`: Kiểm thử luồng download audio, mock speech recognition và xử lý lỗi dependency.
