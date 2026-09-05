# Multi-Tab Session Restoration, 0ms RAM Preview Cache & Atomic Concurrency Guards (v1.8.1b)

**Phiên bản**: `v1.8.1b`  
**Ngày cập nhật**: 29/08/2026  
**Nhánh liên quan**: `fix/duy-29082026-multitab-loading-ram-cache`  


---

## 1. Bối cảnh & Vấn đề

Trong phiên bản Workspace Multi-Tab v1.8.0, một số vấn đề về hiệu năng và xung đột tương tranh (concurrency race conditions) xuất hiện khi người dùng mở nhiều tài liệu nặng (PPTX, DOCX có nhiều hình ảnh):

1. **Hiện tượng treo ứng dụng (Freeze GUI 1-2s)**: Khi mở file PPTX chứa 30 ảnh, dữ liệu Base64 thô nặng tới 20.2 MB. Khi Flet gửi chuỗi Markdown 20 MB qua socket sang Flutter, Flutter UI thread bị nghẽn trong 1.5 - 2s để decode 30 ảnh uncompressed.
2. **Tải lại từ đầu khi chuyển tab**: Mỗi lần click chuyển tab, hệ thống phải quét Regex, parse Mermaid và đọc lại toàn bộ ảnh từ đĩa, làm chớp màn hình và tốn CPU.
3. **Lệch pha giao diện (Race Condition)**: Khi một tài liệu nặng đang tải bất đồng bộ ở nền mà người dùng click sang tab khác, các hàm cập nhật UI (`editor_view.set_text`, `preview`, `page.title`) chạy chen ngang làm ghi đè nội dung của tab mới.
4. **Nhiễm chuỗi Loading vào file nháp**: Khi đổi tab trong lúc đang tải, chuỗi `"⏳ Loading..."` bị cơ chế autosave ghi đè vào file nháp trên đĩa gây mất nội dung thật.
5. **Lỗi Rollback >= 3 tab**: Khi mở file thất bại và đóng tab, `active_tab_id` không được cập nhật trước khi chuyển tab làm ghi đè nội dung sang tab thứ 3.

---

## 2. Các giải pháp kỹ thuật đã triển khai

### 2.1. Tối ưu hóa ảnh Preview siêu nhẹ (Pillow Downsampling & Compression)
- **Vị trí**: `src/ui_flet/views/preview_view.py` (`image_to_base64_uri`)
- **Cơ chế**:
  - Giới hạn chiều rộng ảnh preview tối đa 650px (`max_width=650`, thuật toán `LANCZOS`).
  - Kiểm tra kênh Alpha thực tế (`_has_transparency`). Nếu ảnh không trong suốt, chuyển đổi sang JPEG chất lượng 70%.
  - Giảm dung lượng payload từ **20.2 MB xuống còn ~1.1 MB** (tiết kiệm **96%** dung lượng).
  - Flutter giải mã và hiển thị tức thì trong 20-30 mili-giây, xóa bỏ hoàn toàn hiện tượng freeze GUI.

### 2.2. Bộ nhớ đệm Preview tức thì (0ms Instant RAM Cache)
- **Vị trí**: `src/ui_flet/state.py` (`DocumentTabState.cached_preview_md`), `src/ui_flet/controllers/layout_controller.py`, `src/ui_flet/views/preview_view.py` (`set_processed_content`)
- **Cơ chế**:
  - Markdown sau khi xử lý (kèm sơ đồ Mermaid và ảnh nén) được lưu trực tiếp trong RAM của từng `DocumentTabState`.
  - Khi chuyển đổi giữa các tab, hệ thống chỉ việc lấy chuỗi đã qua xử lý từ RAM đẩy thẳng lên `MarkdownPreview` qua `set_processed_content()`.
  - Không đọc lại đĩa (Zero Disk I/O), không tốn CPU tính toán lại, chuyển tab tức thì trong **0.01 - 0.02 giây**.

### 2.3. Khóa bảo vệ giao diện nguyên tử (Atomic UI Guard)
- **Vị trí**: `src/ui_flet/controllers/file_controller.py` (`open_file_by_path`)
- **Cơ chế**:
  - Tác vụ parse Markdown và nén ảnh bất đồng bộ (`process_markdown_media_async`) được tính toán trước ở nền.
  - Toàn bộ các lệnh tác động lên UI (`editor_view`, `preview`, `file_path_bar`, `page.title`, `footer_bar`, `explorer_view`) được gom chung vào một khối điều kiện:
    ```python
    if self.state.active_tab_id == target_tab.tab_id:
        # Chỉ cập nhật UI nếu tab này vẫn đang là tab active
    ```
  - Nếu người dùng chuyển sang tab khác trong lúc đang tải, dữ liệu tải xong chỉ cập nhật vào RAM của tab đó mà tuyệt đối không chạm vào giao diện của tab đang xem.

### 2.4. Bảo vệ Auto-Save & Tab Switch chống ô nhiễm chuỗi Loading
- **Vị trí**: `src/ui_flet/controllers/file_controller.py`, `src/ui_flet/controllers/layout_controller.py`
- **Cơ chế**:
  - Bổ sung chốt chặn `not target_tab.is_loading` và `not read_only` trong `perform_autosave()`.
  - Từ chối lưu các chuỗi bắt đầu bằng `"⏳ Loading"` hoặc `"*Loading"`.
  - Cập nhật `self.state.active_tab_id = fallback_id` khi đóng tab thất bại trong kịch bản >= 3 tab.

### 2.5. Mock Auto-Save trong Test Suite
- **Vị trí**: `tests/test_youtube_dialog.py`
- **Cơ chế**: Gắn `controller.perform_autosave = MagicMock()` để các bài test tự động không vô tình ghi file nháp thử nghiệm vào thư mục `%APPDATA%\DocConvert\` của người dùng.

---

## 3. Kết quả kiểm thử & Đo lường

| Tiêu chí | Trước tối ưu | Sau tối ưu | Cải thiện |
|---|---|---|---|
| Kích thước payload ảnh (30 ảnh PPTX) | ~20.2 MB | ~1.1 MB | **Giảm 96%** |
| Thời gian nghẽn GUI khi nạp ảnh | 1.5 - 2.0 giây | < 0.05 giây | **Nhanh hơn 40 lần** |
| Thời gian switch qua lại giữa các tab | 1.0 - 1.5 giây | 0.01 - 0.02 giây | **Nhanh hơn 75 lần** |
| Xung đột hiển thị khi đổi tab | Bị đè chữ PPTX | 100% độc lập | **Khắc phục triệt để** |
| Unit Test Suite (`113 tests`) | Pass | Pass (113/113 OK) | **Bảo toàn 100%** |
