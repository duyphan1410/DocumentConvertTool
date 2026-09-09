# 2026-09-09 — PKB Phase 1 Finalization, PDF Extraction Stabilization, and Whisper AI Runtime Packaging (v1.10.1)

## 📌 Bối cảnh & Mục tiêu
Cột mốc này hoàn thiện toàn diện **Personal Knowledge Base Phase 1 (v1.10.0 / v1.10.1)** cùng với các gói sửa lỗi tồn đọng (Backlog Stabilization) then chốt về hiệu năng xử lý tài liệu lớn và tính tương thích đóng gói ứng dụng:
1. **Hoàn thiện & Tối ưu hóa PKB Phase 1**:
   - Tối ưu hiệu năng quét liên kết và hiển thị Backlink Panel với cơ chế đa luồng nền bất đồng bộ (`asyncio.to_thread`), thanh tiến trình tải (`ProgressRing`) và bộ nhớ đệm 0ms RAM LRU cache.
   - Khắc phục triệt để lỗi nhảy con trỏ chuột khi bấm `Undo`/`Redo` trong Trình soạn thảo (`EditorView`).
   - Tinh gọn bộ nảy popup gợi ý tự động (Autocomplete) cho cú pháp `[[...]]` và `#tag`.
2. **Khắc phục lỗi trích xuất PDF nặng & Đồ họa phức tạp**:
   - Sửa lỗi crash khi crop hình ảnh/bảng biểu có tọa độ bounding box lệch gốc (`non-zero x0/y0`) trong sách giáo trình và tài liệu scan nhiều trang.
   - Chuyển đổi chuẩn xác hệ màu `DeviceCMYK` sang `sRGB`, ngăn ngừa sai lệch hoặc vỡ màu ảnh trích xuất.
   - Bổ sung cơ chế hủy tác vụ hợp tác (`cooperative worker thread cancellation`) khi người dùng dừng nạp file lớn.
3. **Đóng gói & Chịu lỗi Runtime Whisper AI Speech-to-Text**:
   - Đóng gói đầy đủ các thư viện phụ thuộc `onnxruntime`, `ctranslate2`, `faster_whisper`, `silero_vad.onnx`, `av`, `tokenizers` trong `Document Converter.spec`.
   - Bổ sung cơ chế chuyển đổi Windows 8.3 Short Path (`GetShortPathNameW`) trong `model_manager.py` để tương thích 100% với tài khoản người dùng Windows có dấu tiếng Việt hoặc ký tự đặc biệt.
   - Tự động kiểm tra runtime ONNX và fallback sang `vad_filter=False` nếu phát hiện môi trường thiếu Silero VAD.
   - Minh bạch hóa toàn bộ thông báo lỗi kỹ thuật qua hệ thống đa ngôn ngữ `src/i18n` (`vi.json` & `en.json`) với 100% key parity thay vì báo sai `"NO SPEECH DETECTED"`.
4. **Nâng phiên bản & Biên dịch bộ cài đặt**:
   - Nâng phiên bản hệ thống lên **`v1.10.1`**.
   - Biên dịch thành công bộ cài đặt hoàn chỉnh `dist/installer/Document_Converter_Setup_v1.10.1.exe` (128.55 MB).

---

## 🚀 Chi tiết triển khai

### 1. Tối ưu Hiệu năng Backlink & Trình soạn thảo (`src/ui_flet/`)
- **`backlink_view.py`**:
  - Tách luồng quét và lọc danh sách liên kết ra khỏi main UI loop bằng `asyncio.to_thread`, giảm độ trễ khi chuyển đổi giữa các tab tài liệu lớn.
  - Bổ sung `ProgressRing` hoạt họa biểu thị trạng thái đang quét liên kết.
  - Tích hợp bộ nhớ đệm 0ms LRU cache lưu trữ kết quả phân giải liên kết theo `content_hash`.
- **`editor_view.py`**:
  - Lưu và khôi phục vị trí con trỏ thông minh khi thực hiện các thao tác lịch sử `Undo` / `Redo`.
  - Tối ưu bộ lắng nghe phím bấm kích hoạt popup autocomplete.
- **`preview_view.py`**:
  - Hỗ trợ đầy đủ cú pháp nhúng nội dung (transclusion embed): `![[image.png]]`, `![[Note#Section]]` với cơ chế phát hiện vòng lặp nhúng (circular embed guard).

### 2. Xử lý Trích xuất PDF Nâng cao (`src/modules/pdf_module.py`)
- **`crop_page_image_safe` & BBox Calculations**:
  - Xử lý bù tọa độ `page.rect.x0` và `page.rect.y0` khi trích xuất hình ảnh hoặc vùng bảng biểu từ các trang PDF có MediaBox/CropBox không bắt đầu từ `(0, 0)`.
- **Color Space Sanitization**:
  - Kiểm tra `pixmap.colorspace` và tự động chuyển đổi từ `DeviceCMYK` sang `DeviceRGB` trước khi lưu hoặc chuyển đổi sang PNG Base64.
- **Cancellation Hook**:
  - Kiểm tra cờ `cancel_event.is_set()` sau mỗi trang xử lý để giải phóng tài nguyên ngay lập tức khi tác vụ bị hủy.

### 3. Đóng gói & Chịu lỗi Whisper AI Engine (`src/services/`, `Document Converter.spec`)
- **`Document Converter.spec`**:
  - Loại bỏ `'onnxruntime'` khỏi danh sách `excludes`.
  - Thêm `collect_all` cho các module: `faster_whisper`, `ctranslate2`, `onnxruntime`, `av`, `tokenizers`.
- **`model_manager.py`**:
  - Cập nhật `get_model_path()` sử dụng `ctypes.windll.kernel32.GetShortPathNameW` trên Windows để lấy đường dẫn 8.3 dạng ANSI an toàn cho C++ runtime.
- **`whisper_service.py`**:
  - Bổ sung kiểm tra an toàn `import onnxruntime` trước khi kích hoạt `vad_filter`.
  - Bổ sung khối `try/except` tự động retry chuyển sang chế độ không dùng VAD filter nếu quá trình phiên âm gặp lỗi khởi tạo runtime.
  - Sử dụng hàm `t(...)` của `src.i18n` cho toàn bộ các exception và chuỗi lỗi trả về (`audio.technical_error`, `audio.missing_runtime`, `audio.model_dir_not_found`, `audio.decode_failed`, `audio.empty_audio`).
- **`transcribe_dialog.py` & `youtube_dialog.py`**:
  - Chuyển đổi 100% các chuỗi trạng thái và nút bấm qua i18n (`transcribe.btn_cancel_task`, `transcribe.status_processing`, `transcribe.status_cancelled`, `speech.transcribing_progress`).

---

## 🧪 Kết quả kiểm thử & Xác minh
- [x] **Unit Tests**: Toàn bộ **259/259 unit tests** vượt qua thành công (**100% OK**).
- [x] **BBox Crop Test**: `tests/test_pdf_module_bbox.py` xác minh chính xác việc trích xuất trên PDF có BBox lệch gốc.
- [x] **Whisper Error Handling Test**: `tests/test_whisper_error_handling.py` xác minh retry fallback VAD và bản địa hóa i18n cho cả tiếng Việt và tiếng Anh.
- [x] **i18n Key Parity Test**: `tests/test_i18n.py` xác nhận độ khớp 100% giữa `vi.json` và `en.json`.
- [x] **Installer Build Verification**: Script `scripts/build_installer.ps1` tạo thành công file cài đặt `Document_Converter_Setup_v1.10.1.exe` (128.55 MB).

---

## 🔍 Đánh giá rủi ro & Thành phần ảnh hưởng
- **Mức độ rủi ro (Risk Level)**: THẤP (Low) — Các thay đổi nâng cấp tính ổn định, bổ sung cơ chế fallback tự động, không gây phá vỡ giao diện lập trình hay định dạng dữ liệu đã có.
- **Các thành phần ảnh hưởng**: `src/modules/pdf_module.py`, `src/services/whisper_service.py`, `src/services/model_manager.py`, `src/ui_flet/views/`, `src/ui_flet/components/`, `src/i18n/locales/`, `Document Converter.spec`.
