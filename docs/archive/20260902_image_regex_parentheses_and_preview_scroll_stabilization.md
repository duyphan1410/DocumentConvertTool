# [Archive] Xử Lý Đường Dẫn Ảnh Chứa Dấu Ngoặc Đơn & Khôi Phục Vị Trí Cuộn Preview Đa Tầng

**Ngày hoàn thành**: 02/09/2026  
**Nhánh thực hiện**: `fix/duy-02092026-image-regex-and-smooth-preview`  
**Tác giả**: Duy Phan  
**Trạng thái**: 🟢 Hoàn thành & Sẵn sàng đóng gói (163/163 Tests Passed)

---

## 1. Mục tiêu & Bối cảnh kỹ thuật

Nhánh này tập trung giải quyết 3 vấn đề lớn trong hệ thống hiển thị và tương tác Live Document Preview:

1. **Xử lý đường dẫn ảnh chứa dấu ngoặc đơn `()`**: Các ảnh xuất ra từ slide PowerPoint hoặc file PDF thường có tên chứa dấu ngoặc đơn (ví dụ: `Vanguard_Engineering_Impact_(2)_assets/pptx_slide1_img.png`). Regex chuẩn trước đây dừng quét ngay khi gặp dấu `)` đầu tiên, làm cắt cụt link ảnh, khiến Preview không render được và toolbar chỉnh ảnh bị lệch token.
2. **Khôi phục vị trí cuộn Preview khi tương tác ảnh (Scroll Jumping & Reset)**: Khi click vào ảnh ở cuối tài liệu để mở Context Menu hoặc áp dụng thay đổi kích thước (25%, 50%, 75%, 100%), Flutter Desktop hủy gesture controller hoặc render lại widget tree, khiến Preview bị giật và nhảy về đầu trang (`112.2px` hoặc `0.0px`).
3. **Mở rộng hỗ trợ cú pháp Mermaid**: Bổ sung toàn diện bộ test checklist cho các loại biểu đồ Mermaid (Flowchart, Sequence, Class, State, ER, Gantt, Git Graph, Pie, Mindmap, User Journey, Timeline, Quadrant, C4 Context) cùng cơ chế xử lý lỗi syntax an toàn.

---

## 2. Chi tiết các thay đổi kỹ thuật

### 2.1. Cải tiến Regex Bóc Tách Đường Dẫn Ảnh Hỗ Trợ Dấu Ngoặc Đơn
- **Vị trí**: `src/ui_flet/helpers/image_token_helper.py` & `src/ui_flet/views/preview_view.py`.
- **Giải pháp**:
  - Nâng cấp regex `IMAGE_TOKEN_REGEX` và `img_block_pattern` với pattern đệ quy nhóm cân bằng:
    ```python
    r'!\[(?P<alt>[^\]]*)\]\((?P<src>(?:\\\(|\\\)|[^\(\)\s]|\((?:\\\(|\\\)|[^\(\)\s])*\))+)\)'
    ```
  - Bóc tách chính xác toàn bộ đường dẫn URL/File path chứa các ký tự `(1)`, `(2)`, `_assets(final)`, không còn bị cắt ngắn hoặc làm hỏng cú pháp markdown.

### 2.2. Cơ chế Khôi Phục Vị Trí Cuộn Đa Tầng (`Multi-Stage Progressive Restore`)
- **Vị trí**: `src/ui_flet/views/preview_view.py` & `src/ui_flet/app.py`.
- **Giải pháp**:
  1. **Tách biệt sự kiện chuột (`Clean Tap Release`)**:
     - Ghi nhận tọa độ `(gx, gy)` trong `_save_tap_position` (`on_tap_down`).
     - Chỉ kích hoạt mở Menu trong `_handle_image_tap` (`on_tap`) khi người dùng đã nhả chuột $\rightarrow$ Triệt tiêu xung đột cử chỉ (gesture cancel) trong Flutter ScrollController.
  2. **Multi-Stage Progressive Restore Loop**:
     - Do Flutter Desktop cần thời gian bất đồng bộ để đo chiều cao (layout measurement) của 30+ ảnh Base64 lớn và khối Mermaid, hệ thống thực hiện khôi phục tiến trình qua các mốc `(0.0s, 0.02s, 0.06s, 0.15s, 0.35s)`.
     - Sử dụng cờ khóa `_is_restoring_scroll = True` để bảo vệ biến `_saved_scroll_offset` không bị các sự kiện layout tạm thời của Flutter ghi đè về `112.2px`.
  3. **Khôi phục toàn diện tại mọi trạng thái Menu**:
     - Tự động gọi `restore_scroll()` khi Context Menu mở ra, khi bấm chọn option và khi click ra ngoài để đóng menu (`_on_image_menu_dismissed`).

### 2.3. Tối ưu hóa Cập nhật In-Place và Loại Bỏ Tooltip Chớp Tắt
- **Vị trí**: `src/ui_flet/views/preview_view.py`.
- **Giải pháp**:
  - Gỡ bỏ tooltip `image (Nhấn để chỉnh sửa)` trên các ảnh ở Preview để loại bỏ hoàn toàn hiện tượng chớp tắt thanh xám 10ms khi click chuột.
  - Tối ưu hóa `_render_processed_content` để tái sử dụng cây controls có sẵn (`can_in_place`), giảm thiểu số lần tạo lại widget.

---

## 3. Danh sách các File Thay Đổi & Tạo Mới

| File | Hành động | Mục đích |
|---|---|---|
| `src/ui_flet/helpers/image_token_helper.py` | Modify | Nâng cấp regex bóc tách markdown image token hỗ trợ dấu ngoặc đơn `()` |
| `src/ui_flet/views/preview_view.py` | Modify | Multi-stage progressive restore, clean tap release, regex đồng bộ và loại bỏ tooltip |
| `src/ui_flet/app.py` | Modify | Gắn `restore_scroll()` vào luồng mở menu, đóng menu và ngắt kết nối editor toolbar thừa |
| `src/ui_flet/components/context_menu.py` | Modify | Tối ưu hóa overlay container và mount 1 lần duy nhất lúc khởi động |
| `tests/test_image_path_parentheses.py` | New | Bộ unit test kiểm thử toàn diện regex đường dẫn ảnh chứa ngoặc đơn |
| `tests/test_document_preview.py` | Modify | Bổ sung test cases cho preview view với đường dẫn ảnh phức tạp |
| `tests/test_mermaid_preview.py` | Modify | Kiểm thử render và interceptor mermaid đa sơ đồ |
| `docs/backlog/BUG_001_preview_scroll_jump_image_click.md` | Modify | Cập nhật hoàn thành BUG-001 và ghi nhận trade-off layout Flutter |
| `docs/backlog/README.md` | Modify | Cập nhật bảng tổng hợp backlog tasks |

---

## 4. Kết quả Kiểm Thử & Nghiệm Thu

- **Layer 1 (Imports & Syntax)**: 100% clean, không phát sinh cảnh báo Coroutine unawaited.
- **Layer 2 (Automated Test Suite)**: **163/163 tests PASS** trong **8.95 giây** (`python -m unittest discover tests`).
- **Layer 3 (Live UI Verification)**:
  - File `Vanguard_Engineering_Impact_(2).md` (30 ảnh Base64 + 16 biểu đồ Mermaid) hiển thị pixel-perfect.
  - Click vào bất kỳ ảnh nào ở độ sâu nào của tài liệu: Vị trí cuộn được giữ vững 100%, menu mở tại chỗ, đóng menu giữ nguyên vị trí, đổi kích cỡ co giãn tại chỗ.
