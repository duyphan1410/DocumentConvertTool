# 2026-09-05 — PDF Extraction Robustness, Find & Replace Shortcut, and Help View Synchronization

## 📌 Bối cảnh & Mục tiêu
Phiên bản này tập trung giải quyết các lỗi biên phức tạp trong quá trình bóc tách tài liệu PDF, hoàn thiện hệ thống phím tắt tìm kiếm/thay thế, và đồng bộ hóa tài liệu trợ giúp:
1. **Khắc phục lỗi bóc tách PDF phức tạp (`pdf_module.py`)**:
   - Loại bỏ hoàn toàn 7,963 ký tự ma (ghost characters) tọa độ âm (`top < 0`) sinh ra chuỗi ký tự rác `(cid:0) P 4 D m...`.
   - Khắc phục hiện tượng icon/emoji (`Noto Sans Symbols 2`) bị lệch baseline `8.4px` so với font chữ (`Arial`) dẫn đến việc bị tách thành dòng riêng `### Ὦ`.
   - Ngăn chặn lỗi dồn cục nhiều hàng bảng vào chung 1 ô khi bảng không có đường kẻ ngang và bảo toàn 100% các tiêu đề/mục (`Phần 5:`, `1. Tệp tin...`) không bị nuốt vào bảng.
2. **Bổ sung Phím tắt `Ctrl+H` (Tìm kiếm & Thay thế)**:
   - Đấu nối phím tắt `Ctrl+H` vào `ShortcutManager`, `App`, và `SearchController` để mở trực tiếp thanh Tìm kiếm & Thay thế.
3. **Đồng bộ hóa Trợ giúp (`HelpView`) & Ngôn ngữ (`i18n`)**:
   - Cập nhật bảng phím tắt trong `HelpView` và bộ từ điển `vi.json`, `en.json`.
4. **Tối ưu hóa Tiến trình nạp tệp (`FileController`)**:
   - Giảm throttle streaming xuống 250ms cho hiệu ứng tải trang mượt mà kèm thanh tiến trình và bộ đếm từ/ký tự thời gian thực.
   - Bổ sung repaint an toàn khi mở lại các tab đã đóng.

---

## 🚀 Chi tiết triển khai

### 1. Nâng cấp Mô-đun PDF (`src/modules/pdf_module.py`)
- **Lọc ký tự âm từ gốc (`raw_page.filter`)**:
  - Khi mở trang với `pdfplumber`, áp dụng bộ lọc `raw_page.filter(...)` loại bỏ toàn bộ các ký tự có tọa độ âm (`top < 0` hoặc `x0 < 0`) trước khi thực hiện bất kỳ thao tác cắt xén (`crop`) nào.
- **Nhóm dòng theo Tỷ lệ phủ dọc & Khoảng cách tâm (`get_lines_from_chars`)**:
  - Thay thế ngưỡng khoảng cách cố định `3.8px` bằng thuật toán linh hoạt dựa trên tỷ lệ phủ dọc (`overlap >= 0.35 * min_size`) hoặc khoảng cách tâm dọc (`abs(c_mid - l_mid) <= 0.40 * max_size`).
  - Giúp gom các font biểu tượng/bullet và chữ viết thường vào cùng 1 dòng tự nhiên mà không cần hardcode từ điển ánh xạ font.
- **Ghép bảng an toàn qua ngắt trang (`_stitch_multipage_tables`)**:
  - Bổ sung điều kiện kiểm tra số lượng cột khớp nhau tuyệt đối (`len(t1_cols) == len(t2_cols)`) trước khi ghép, tránh tình trạng bảng trước nuốt trọn bảng sau.
- **Bộ lọc từ chối bảng giả mạo & Bảng nuốt đề mục (`load_to_markdown`)**:
  - *Mid-word cell slicing guard*: Nhận diện và loại bỏ các bảng bị cắt đứt giữa từ (như `Mi | crosoft`, `TC‐ | PREV‐002`, ngoặc đơn không đóng mở cân đối).
  - *Document text over-capture guard*: Nhận diện và fallback về `rich text` đối với các bảng nuốt trọn tiêu đề mục (`Phần 5:`, `Mục 4.x:`, `1. Tệp tin...`) hoặc khối danh sách gạch đầu dòng, bảo toàn nguyên vẹn cấu trúc Heading (`#`, `##`, `###`) và Paragraphs.

### 2. Phím tắt `Ctrl+H` & Thanh Tìm kiếm Thay thế (`src/ui_flet/`)
- **`shortcut_manager.py` & `app.py`**:
  - Bổ sung callback `on_replace_shortcut` lắng nghe tổ hợp phím `Ctrl+H` và `Ctrl+h`.
- **`search_controller.py` & `search_replace_bar.py`**:
  - Phương thức `toggle_search(show_replace=True)` mở trực tiếp giao diện thay thế và tự động focus vào ô tìm kiếm.

### 3. Đồng bộ Giao diện Trợ giúp & Bản địa hóa
- **`help_view.py`**: Thêm dòng mô tả phím tắt `Ctrl+H` (Tìm kiếm và Thay thế).
- **`src/i18n/locales/vi.json` & `en.json`**: Bổ sung các chuỗi dịch thuật tương ứng cho tính năng mới.

---

## 🧪 Kết quả kiểm thử & Xác minh
- [x] **Ghost Characters**: Triệt tiêu hoàn toàn chuỗi ký tự rác `(cid:0) P 4 D m...` trên trang 2 của `TestCase.pdf`.
- [x] **Heading & Symbol Alignment**: Các biểu tượng `Ὄ`, `Ὦ`, `ὐ`, `Ὃ` nằm liền mạch cùng hàng với dòng tiêu đề, không bị văng dòng thành `### Ὦ`.
- [x] **Table & Section Preservation**: Toàn bộ các tiêu đề `Phần 1`, `Phần 2`, `Phần 3`, `Phần 4`, `Phần 5`, bảng Test Case và danh mục được hiển thị đầy đủ, không bị nuốt mất heading.
- [x] **Phím tắt `Ctrl+H`**: Hoạt động chính xác trên Windows, mở trực tiếp thanh Replace.
- [x] **Unit Tests**: Chạy pass 100% test suite (`Ran 204 tests in 12.329s — OK`).
