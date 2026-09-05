# Workspace Tab Context Menu, Micro Scrollbar, Link Resolution & Batch Polish (v1.8.1c)

**Phiên bản**: `v1.8.1c`  
**Ngày cập nhật**: 29/08/2026  
**Nhánh liên quan**: `feat/duy-29082026-tab-context-menu-micro-scrollbar`  


---

## 1. Bối cảnh & Mục tiêu

Sau khi hoàn thiện kiến trúc đa tab (Multi-Tab Workspace) và cơ chế bộ nhớ đệm 0ms RAM Preview, giai đoạn này tập trung giải quyết các trải nghiệm người dùng thực tế và hoàn thiện các tính năng tương tác chuyên sâu:

1. **Thanh cuộn TabBar che khuất tiêu đề**: Khi mở nhiều tab, Flutter hiển thị thanh cuộn mặc định 14-16px màu trắng nổi trên các tab làm mất thẩm mỹ và che khuất tên file.
2. **Thiếu Menu ngữ cảnh (Context Menu) cho Tab**: Người dùng chưa có thao tác chuột phải để quản lý nhanh các tab (đóng các tab khác, đóng tab bên phải, đóng tất cả, sao chép đường dẫn, mở thư mục trong Explorer).
3. **Liên kết tương đối trên ghi chú Untitled**: Khi kéo thả file từ Explorer vào một tab `Untitled` (chưa lưu), việc click vào liên kết Markdown ở khung Preview bị lỗi do chưa liên kết với thư mục Workspace đang mở.
4. **Tên file và bộ lọc mặc định khi Lưu**: Khi lưu tab `Untitled`, tên file mặc định bị gán cứng là `document.md` và hộp thoại Windows Save As bị hiển thị nhầm bộ lọc `Word (*.docx)` thay vì `Markdown (*.md)`.
5. **Bộ lọc file nén & Giao diện Chuyển đổi hàng loạt**: Modal Batch & Archive Converter cần hỗ trợ duyệt riêng các định dạng lưu trữ nén (`.zip`, `.rar`, `.7z`, `.tar.gz`) và đồng bộ kích thước dropdown.

---

## 2. Các giải pháp kỹ thuật đã triển khai

### 2.1. Thanh cuộn siêu mỏng 3px cho TabBar (Ultra-sleek Micro Scrollbar)
- **Vị trí**: `src/ui_flet/components/workspace_tab_bar.py`
- **Cơ chế**:
  - Áp dụng `ft.Theme(scrollbar_theme=ft.ScrollbarTheme(thickness=3, radius=2, track_visibility=False, thumb_visibility=False, interactive=True))` cho `WorkspaceTabBar`.
  - Đồng bộ chuẩn giao diện với thanh Ribbon Bar, loại bỏ hoàn toàn thanh cuộn trắng to bản.

### 2.2. Menu chuột phải cho Tab (Right-Click Tab Context Menu)
- **Vị trí**: `src/ui_flet/components/workspace_tab_bar.py`, `src/ui_flet/components/context_menu.py`, `src/ui_flet/controllers/layout_controller.py`, `src/ui_flet/app.py`
- **Các hành động hỗ trợ**:
  - ❌ **Đóng tab** (`Close Tab`): Đóng tab hiện tại (có cảnh báo nếu có thay đổi chưa lưu).
  - 🧹 **Đóng các tab khác** (`Close Other Tabs`): Đóng toàn bộ các tab còn lại, giữ lại tab đang chọn (`handle_close_other_tabs`).
  - ➡️ **Đóng các tab bên phải** (`Close Tabs to the Right`): Đóng các tab nằm phía sau (`handle_close_tabs_to_right`).
  - 🚪 **Đóng tất cả tab** (`Close All Tabs`): Đóng toàn bộ tab (`handle_close_all_tabs`).
  - 📋 **Sao chép đường dẫn tệp** (`Copy File Path`): Sao chép đường dẫn đầy đủ vào clipboard.
  - 📂 **Hiển thị trong Explorer** (`Reveal in File Explorer`): Mở thư mục chứa file trong Windows Explorer.
- **Đa ngôn ngữ**: Bổ sung đầy đủ nhãn dịch trong `src/i18n/locales/vi.json` và `en.json`.

### 2.3. Tự động phân giải liên kết tương đối từ Workspace cho Untitled Notes
- **Vị trí**: `src/ui_flet/views/preview_view.py`, `src/ui_flet/app.py`
- **Cơ chế**:
  - `MarkdownPreview` được tích hợp `get_workspace_path` callback.
  - Khi click vào liên kết tương đối (ví dụ: `[test_manual.md](test_manual.md)`) trên một tab chưa lưu, hệ thống tự động tra cứu trong thư mục Workspace đang mở (`workspace_folder`).
  - Tìm thấy file tài liệu (`.md`, `.docx`, `.xlsx`, `.pdf`, v.v.) sẽ kích hoạt `on_open_file` để **mở trực tiếp thành Tab mới trong ứng dụng**, không bật ra trình duyệt ngoài và không gây cảnh báo unawaited coroutine.

### 2.4. Đề xuất tên file lưu thông minh & Tự động khớp bộ lọc Save As
- **Vị trí**: `src/ui_flet/controllers/file_controller.py` (`async_save_markdown`), `src/ui_flet/native_dialogs.py` (`pick_output_file_sync`)
- **Cơ chế**:
  - **Smart Heading Extraction**: Tự động quét dòng tiêu đề `# Tiêu đề` đầu tiên trong nội dung để đề xuất tên file (ví dụ: `# Kế hoạch Q3` ➔ đề xuất `Ke_hoach_Q3.md`). Nếu không có tiêu đề, đề xuất `Untitled.md`.
  - **Filter Sorting**: Sắp xếp danh sách `OUTPUT_FILETYPES` trong hộp thoại Windows Save As sao cho định dạng đích (`.md` khi lưu Markdown) luôn được chọn đầu tiên.

### 2.5. Bổ sung File Picker cho Tệp nén & Tinh chỉnh Batch Converter
- **Vị trí**: `src/ui_flet/native_dialogs.py` (`pick_archive_file_sync`), `src/ui_flet/components/batch_dialog.py`
- **Cơ chế**:
  - Thêm `pick_archive_file_sync()` với bộ lọc `ARCHIVE_FILETYPES` (`.zip`, `.rar`, `.7z`, `.tar.gz`, `.tgz`, `.tbz2`, `.tar`, `.bz2`).
  - Giữ nguyên trạng thái `source_location` khi chuyển qua lại giữa tab Thư mục và tab Tệp nén.
  - Chuẩn hóa tên định dạng xuất trong Dropdown (`Markdown (.md)`, `Word (.docx)`, `PDF (.pdf)`, `HTML (.html)`, `Excel (.xlsx)`, v.v.).

---

## 3. Kết quả kiểm thử & Đo lường

| Hạng mục | Kết quả | Ghi chú |
|---|---|---|
| **Thanh cuộn TabBar** | Siêu mỏng 3px | Đồng bộ với Ribbon, không che khuất tab |
| **Menu chuột phải Tab** | Hoạt động 100% | Đóng 1 tab, đóng các tab khác, đóng tab bên phải, đóng tất cả, copy path, reveal |
| **Click Link trong Preview** | Hoàn hảo | Tab Untitled mở ngay file đích trong Workspace thành tab mới |
| **Gợi ý tên file khi Lưu** | Thông minh | Tự nhận diện Heading `# Title` ➔ `Title.md`, đúng bộ lọc `.md` |
| **Bộ lọc Archive Picker** | Hoạt động 100% | Lọc chuẩn các định dạng `.zip`, `.rar`, `.7z`, `.tar.gz` |
| **Automated Unit Tests** | **114/114 Tests Pass (100%)** | Toàn bộ test suite chạy thành công mượt mà |
