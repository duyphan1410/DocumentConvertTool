# Phase 1.8.1b: Multi-Tab Workspace Architecture & AppState Delegation Summary

**Branch**: `feat/duy-28082026-multi-tab-workspace`  
**Date**: 2026-08-28  
**Scope**: Multi-Tab Document Architecture, Property Delegation, Isolated Draft Sessions, Draggable TabBar UI, and Smart File Operations.

---

## 1. Mục tiêu kiến trúc

1. **Multi-Tab Document Architecture**: Cho phép mở, chuyển đổi, đóng và sắp xếp nhiều tài liệu độc lập cùng lúc mà không làm chậm ứng dụng.
2. **Transparent Property Delegation (`state.py`)**: Tách biệt `DocumentTabState` (quản lý trạng thái theo tab: `in_path`, `out_path`, `full_content`, `is_dirty`, `undo_stack`, `is_orphaned`, `media_session_id`) và `AppState` với cơ chế Getter/Setter ủy quyền trong suốt, đảm bảo 0 breaking changes cho các controller cũ.
3. **Isolated Autosave & Media Sessions**: Mỗi tab tự động lưu draft độc lập tại `%APPDATA%/DocConvert/drafts/{tab_id}.md` và manifest `tab_session.json`. Bộ nhớ đệm ảnh preview `@media/` được cô lập 100% theo từng session của tab, ngăn chặn triệt để hiện tượng asset bleed.
4. **Draggable TabBar UI & Fast Visual Feedback**: Hỗ trợ kéo thả tab (`ft.Draggable` & `ft.DragTarget`), chấm tròn dirty (`●`), cảnh báo file orphaned khi bị xóa từ bên ngoài, và vòng xoay loading `ft.ProgressRing` xoay mượt mà khi nạp tài liệu nặng (Mermaid/ảnh lớn) mà không gây giật lag UI.
5. **Smart Keyboard & File Operations**:
   - `Ctrl+T`: Mở tab Untitled mới.
   - `Ctrl+W`: Đóng tab active (hỏi xác nhận nếu có thay đổi chưa lưu).
   - `Ctrl+Tab` / `Ctrl+Shift+Tab`: Chuyển đổi qua lại giữa các tab theo vòng tròn.
   - `Ctrl+S`: Lưu nhanh (Fast Save) nếu file đã tồn tại trên đĩa, hoặc mở Save Dialog trỏ đúng thư mục workspace nếu là tab Untitled.

---

## 2. Các tầng thay đổi chi tiết

### Tầng 1: Data Model & State Delegation (`src/ui_flet/state.py`)
- Khai báo `DocumentTabState` với các trường: `tab_id`, `in_path`, `out_path`, `title`, `current_mode`, `full_content`, `is_dirty`, `is_orphaned`, `is_loading`, `undo_stack`, `redo_stack`, `media_session_id`.
- Triển khai phương thức vòng đời tab trong `AppState`: `create_tab()`, `close_tab()`, `activate_tab()`, `find_tab_by_id()`, `find_tab_by_path()`, `reorder_tabs()`, `get_tab_index()`.
- Áp dụng Property Delegation: Các thuộc tính như `state.in_path`, `state.full_content`, `state.is_dirty` tự động trỏ đến tab đang active (`_ensure_active_tab()`), fallback an toàn khi số tab = 0.

### Tầng 2: Multi-Session Cache Isolation (`src/services/media_asset_manager.py`)
- Quản lý thư mục cache riêng biệt theo session: `%APPDATA%/DocConvert/cache/preview_media/{session_id}/`.
- Khắc phục lỗ hổng asset bleed trong `resolve_uri`: Không duyệt chéo sang thư mục của session khác khi phân giải link `@media/`.

### Tầng 3: Workspace Tab Bar Component (`src/ui_flet/components/workspace_tab_bar.py`)
- `DocumentTabItem`: Hiển thị icon theo loại file, tiêu đề tab, chấm dirty `●`, nút đóng `×`, và animated `ft.ProgressRing` khi `is_loading = True`.
- Kéo thả sắp xếp thứ tự tab an toàn thông qua `e.page.get_control(e.src_id).data`.
- Tách biệt vùng click tiêu đề `title_click_area` và nút đóng `close_btn` để chống event bubbling.

### Tầng 4: Controller Orchestration & Smart Save
- `FileController` ([file_controller.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/ui_flet/controllers/file_controller.py)):
  - Hỗ trợ lưu draft theo tab (`drafts/{tab_id}.md` & `tab_session.json`).
  - `handle_file_renamed()`: Duyệt và cập nhật đường dẫn cho tất cả các tab đang mở matching với file/folder được đổi tên.
  - `handle_file_deleted()`: Đánh dấu `is_orphaned = True` nếu tab đang có dữ liệu chưa lưu để giữ an toàn trong RAM, hoặc đóng tab an toàn nếu không dirty.
  - `handle_save_shortcut()`: Triển khai luồng Smart `Ctrl+S`.
- `LayoutController` ([layout_controller.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/ui_flet/controllers/layout_controller.py)):
  - Quản lý chuyển đổi tab (`handle_doc_tab_selected`) với preview hydration bất đồng bộ không gây nghẽn UI.
  - Xử lý đóng tab cuối cùng phân nhánh theo `workspace_folder`: nếu chưa mở folder thì về `WelcomeView`, nếu đang mở folder thì giữ nguyên workspace rỗng.
  - Phím tắt điều hướng `Ctrl+Tab`, `Ctrl+Shift+Tab`, `Ctrl+T`, `Ctrl+W`.
- `FileModals` ([file_modals.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/ui_flet/components/file_modals.py)):
  - `show_unsaved_tab_dialog()`: Hộp thoại xác nhận đóng tab chưa lưu với 3 lựa chọn **Save**, **Discard**, **Cancel**, hỗ trợ đóng bằng click ra ngoài hoặc phím Escape (`modal=False`).

### Tầng 5: Đa ngôn ngữ (i18n) & Đóng gói (PyInstaller)
- Bổ sung chuỗi bản địa hóa đa ngôn ngữ `vi.json` và `en.json`: `tab.*`, `dialog.unsaved_tab_*`, `status.file_deleted_warning`.
- Cập nhật `Document Converter.spec` với `src.ui_flet.components.workspace_tab_bar`.

---

## 3. Kết quả kiểm thử tự động

- **Unit Test Suite (`tests/test_multi_tab_state.py`)**: 11 bài test kiểm thử toàn diện:
  - Property Delegation & Zero-Tab Fallback.
  - Vòng đời tab (Tạo, chuyển, đóng, sắp xếp thứ tự).
  - An toàn `find_tab_by_path("")` cho các tab Untitled.
  - Cô lập session ảnh và chống asset bleed giữa các tab.
- **Toàn bộ Test Suite Dự Án**: **113/113 tests** chạy thành công (**100% OK**, exit code 0).
