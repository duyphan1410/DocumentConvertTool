# 2026-09-04 — OCR Scanned PDF Engine & Preview Scroll Synchronization

## 📌 Bối cảnh & Mục tiêu
Phiên bản này tập trung giải quyết 2 bài toán lớn trong Document Converter Workspace:
1. **Engine OCR & Phân giải PDF dạng Quét ảnh (Scanned PDF)**: Bổ sung khả năng nhận diện văn bản tự động từ các tài liệu PDF dạng quét/chụp ảnh (`pdf_scan_module`), trích xuất ảnh minh họa, giữ nguyên bảng biểu và cấu trúc phân đoạn, chuyển đổi sang Markdown chuẩn.
2. **Đồng bộ hóa vị trí cuộn Preview & Menu ngữ cảnh Ảnh**: Xử lý triệt để hiện tượng giật/nhảy scroll về đầu trang khi mở Context Menu ảnh và khi áp dụng các preset kích thước (25%, 50%, 75%, 100%) hoặc căn lề (Trái, Giữa, Phải).

---

## 🚀 Chi tiết triển khai

### 1. Engine OCR & Scanned PDF Module (`src/services/ocr_service.py`, `src/modules/pdf_scan_module.py`)
- **Kiến trúc OCR đa tầng**: Tích hợp engine OCR hỗ trợ tiếng Việt và tiếng Anh có khả năng tự động fallback (`pytesseract` / Tesseract OCR engine, `RapidOCR` / ONNX engine).
- **Phân tách trang & Khôi phục bảng biểu**:
  - `PDFScanModule` duyệt từng trang, nhận diện văn bản OCR kết hợp trích xuất các khối ảnh và phân đoạn heading/paragraph.
  - Tích hợp kiểm tra phụ thuộc thiếu (`get_missing_dependencies_for_path`) và hướng dẫn cài đặt trực quan trên UI.
- **Tích hợp toàn diện UI / MVC**:
  - Đăng ký mode `PDF_SCAN -> PDF (Quét ảnh / OCR) -> Markdown` trong `src/ui_flet/constants.py`.
  - Kết nối với `ConversionController`, `FileController`, `RibbonBar`, `FooterBar`, và bộ từ điển đa ngôn ngữ (`vi.json`, `en.json`).
  - Bộ kiểm thử tự động tại `tests/test_ocr_service.py` và `tests/test_pdf_scan_module.py`.

### 2. Đồng bộ hóa Scroll Preview & Context Menu (`src/ui_flet/views/preview_view.py`, `src/ui_flet/app.py`)
- **Khóa vị trí tức thì khi mở Context Menu**:
  - Khi click vào ảnh trong Live Preview, `_show_image_context_menu_at` ghi nhớ `saved_offset` và kích hoạt `restore_scroll(target_offset=saved_offset, duration=0)`.
  - Khung Preview đứng yên 100% tại ảnh đang xem, menu ngữ cảnh nổi lên chính xác tại tọa độ con trỏ chuột.
- **Cơ chế cập nhật In-Place tối ưu**:
  - Trong `_render_processed_content()`, khi số lượng thành phần không đổi (`can_in_place = True`), chỉ gọi `.update()` trên đúng Control/Row bị thay đổi (`ctrl.update()`), không gọi `scroll_column.update()`, tránh việc Flutter xóa sạch cây widget và reset viewport.
- **2-Pass Frame Layout Synchronization**:
  - Trong `restore_scroll()`, sử dụng `page.run_task(_async_restore)` để đưa tác vụ vào đúng Event Loop chính của Flet từ Worker Thread.
  - Thực hiện 2 lượt đồng bộ: Pass 1 (sau 40ms) và Pass 2 (sau 90ms) để đảm bảo sau khi Flutter layout engine hoàn tất tính toán `maxScrollExtent`, màn hình được neo cố định tại đúng vị trí ảnh.

---

## 🧪 Kết quả kiểm thử & Xác minh
- [x] **OCR Engine**: Nhận diện chính xác văn bản tiếng Việt có dấu từ tài liệu scan mẫu.
- [x] **PDF Scan Module**: Chuyển đổi thành công sang Markdown có cấu trúc kèm metadata.
- [x] **Preview Scroll**: Đứng yên hoàn toàn khi click mở/đóng menu ảnh và khi áp dụng các preset kích thước/căn lề.
- [x] **Unit Tests**: Chạy pass toàn bộ test suite `test_ocr_service.py` và `test_pdf_scan_module.py`.
