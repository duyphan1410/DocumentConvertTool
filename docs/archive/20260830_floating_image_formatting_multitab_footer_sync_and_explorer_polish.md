# Floating Image Formatting, Multi-Tab Footer Synchronization & Explorer UX Polish (v1.8.2)

**Phiên bản**: `v1.8.2`  
**Ngày cập nhật**: 30/08/2026  
**Nhánh liên quan**: `feat/duy-29082026-floating-image-toolbar-and-format-fixes`  

---

## 1. Bối cảnh & Vấn đề Cần giải quyết

Sau khi hoàn thiện hệ thống Multi-Tab và Batch Converter ở phiên bản v1.8.1, quá trình vận hành và kiểm thử thực tế đã phát hiện các vấn đề cốt lõi về trải nghiệm người dùng (UX) và tính toàn vẹn dữ liệu:

1. **Vòng lặp vô hạn Context Menu khi con trỏ ở Offset 0**:
   - Khi tài liệu bắt đầu bằng một hình ảnh (offset 0), mỗi khi con trỏ chuột quay về đầu trang (hoặc sau khi cập nhật nội dung), hệ thống tự động phát hiện token ảnh và mở menu nổi liên tục (infinite popup loop), cản trở việc gõ văn bản của người dùng.
2. **Hộp thoại kích thước ảnh (`ImageSizeDialog`) chưa chuẩn UX**:
   - Các nút tác vụ (`Reset`, `Cancel`, `Apply`) bị xếp dọc hoặc bố trí rời rạc; chiều cao giữa các ô input `Width`, `Height` và dropdown `Unit` không đồng đều; khoảng đệm xám thừa ở đáy modal lớn (do Flutter Material 3 AlertDialog padding).
   - Nút `Cancel` và thao tác nhấp ra ngoài (click-outside dismiss) bị lỗi kẹt overlay do gọi `page.overlay.remove` quá sớm trước khi Flutter client xử lý xong sự kiện `open: false`.
3. **Trạng thái Footer Bar bị kẹt tĩnh giữa các Tab (`Multi-Tab Footer Desynchronization`)**:
   - Khi chuyển đổi ở **Tab A**, FooterBar hiển thị `[Convert] [Open File] [Open Location] ✓ output.docx`. Khi người dùng chuyển sang **Tab B** (chưa convert hoặc tài liệu khác), FooterBar vẫn giữ nguyên nút bấm của Tab A. Bấm `Open File` từ Tab B sẽ mở nhầm file của Tab A!
   - Khi người dùng nhấp mở tệp mới từ Explorer, 2 nút kết quả không được ẩn đi.
4. **Mất thanh cuộn và tràn viền ở File Explorer**:
   - `tree_list` bị nhét vào `DragTarget` con ở giữa `Column` khiến Flutter không xác định được chiều cao giới hạn (unbounded height constraints), làm mất hoàn toàn thanh cuộn chuột của Explorer.
   - Thiếu `clip_behavior=ft.ClipBehavior.HARD_EDGE` khiến các tệp cuối danh sách bị tràn đè lên thanh Footer.
5. **Nút Refresh trên Explorer hoạt động như Collapse All**:
   - Mỗi lần bấm **Refresh** (hoặc sau khi tạo/xóa/đổi tên file), toàn bộ cây thư mục bị xóa và tạo lại ở trạng thái đóng (`is_expanded = False`), làm đóng hết các thư mục người dùng đang mở dở.
6. **Kéo thả tệp trong Explorer tự động văng ra thư mục Root**:
   - `DragTarget` bắt sự kiện thả bị bọc toàn cục trên cả Explorer; người dùng kéo thả trong thư mục con nếu thả trượt vào khoảng trống giữa các file sẽ bị `shutil.move` chuyển ngay tệp ra thư mục Root (`workspace_path`).
7. **Phím tắt `Ctrl+B` bị vô hiệu hóa**:
   - Do điều kiện kiểm tra `and e is not None` trong `toggle_sidebar`, khiến các sự kiện bàn phím gửi từ `ShortcutManager` (nơi `e=None`) không kích hoạt được việc ẩn/hiện Sidebar.

---

## 2. Các giải pháp kỹ thuật đã triển khai (Technical Architecture)

### 2.1. Căn lề Hình ảnh & Xuất Word chuẩn xác (`WordModule`)
- **Vị trí**: `src/modules/word_module.py`, `src/ui_flet/components/context_menu.py`, `src/ui_flet/views/preview_view.py`
- **Cơ chế**:
  - Tách bạch rõ ràng: Soạn thảo văn bản trong Editor là thao tác thuần gõ phím (không auto-popup phiền toái); menu ngữ cảnh hình ảnh được kích hoạt có chủ đích khi nhấp chuột trái vào ảnh trong **Live Document Preview**.
  - Khi căn lề, bọc ảnh bằng thẻ chuẩn:
    ```markdown
    <p align="center">
    ![Alt text](path/to/image.png)
    </p>
    ```
  - Trong `WordModule`: Tích hợp bộ giải tích regex bắt thẻ `<p align="(left|center|right)">` và gán thuộc tính đoạn `WD_ALIGN_PARAGRAPH.LEFT`, `WD_ALIGN_PARAGRAPH.CENTER`, hoặc `WD_ALIGN_PARAGRAPH.RIGHT` cho khối chứa ảnh trong file `.docx`.

### 2.2. Tái thiết kế toàn diện `ImageSizeDialog`
- **Vị trí**: `src/ui_flet/components/image_size_dialog.py`
- **Cải tiến UX & Lifecycle**:
  - **Bố cục hàng ngang hiện đại**: `[↺ Reset to Original]` [Spacer] `[Hủy]` `[✓ Áp dụng]`.
  - **Đồng bộ chiều cao input**: Thiết lập `content_padding=ft.Padding(10, 11, 10, 11)` giúp `txt_width`, `dd_unit` (90px) và `txt_height` thẳng hàng tuyệt đối.
  - **Mở rộng ô thông tin**: Đệm `ft.Padding(12, 12, 12, 12)` cho `Alt Description Text` và `Image Source / Path`.
  - **Loại bỏ khoảng xám thừa**: Cấu hình `actions_padding=ft.Padding(0, 0, 0, 0)` và `content_padding=ft.Padding(18, 6, 18, 10)`.
  - **Khắc phục lỗi đóng Modal**: Bỏ lệnh `page.overlay.remove()` sớm; dùng cơ chế chuẩn `dialog.open = False` + `dialog.update()` + `page.update()`, dọn dẹp các instance cũ trong `show()` qua danh sách overlay lọc.

### 2.3. Đồng bộ hóa Trạng thái FooterBar theo từng Tab (`Per-Tab Hydration`)
- **Vị trí**: `src/ui_flet/controllers/layout_controller.py`, `src/ui_flet/controllers/file_controller.py`, `src/ui_flet/layout/footer_bar.py`
- **Cơ chế**:
  - Trong `handle_doc_tab_selected`, bổ sung **Bước 11: Hydrate FooterBar**:
    ```python
    has_valid_converted = bool(
        incoming_tab.last_converted_path
        and os.path.exists(incoming_tab.last_converted_path)
    )
    footer_bar.set_result_buttons_visible(has_valid_converted)
    if has_valid_converted:
        fname = os.path.basename(incoming_tab.last_converted_path)
        footer_bar.set_status(f"✓ {fname}", color=ft.Colors.GREEN_400)
    else:
        footer_bar.set_status_key("footer.status_ready")
    ```
  - Trong `FileController.open_file_by_path`: Gọi `self.footer_bar.set_result_buttons_visible(False)` ngay khi bắt đầu nạp tệp mới và đồng bộ lại trạng thái khi hoàn tất nạp.
  - Tận dụng cơ chế **Property Delegation** của `AppState`: Các nút `Open File` và `Open Location` luôn truy xuất đúng `last_converted_path` của Tab đang Active.

### 2.4. Khắc phục lỗi Cuộn và Cắt viền File Explorer
- **Vị trí**: `src/ui_flet/views/explorer_view.py`
- **Cơ chế**:
  - Tái cấu trúc phân tầng Layout giống chuẩn `EditorView`: `tree_list` (`ft.ListView(expand=True)`) là con trực tiếp của `content_column` (`ft.Column(expand=True)`).
  - Gỡ bỏ `expand=True` ở container gốc của `ExplorerView` để giữ nguyên chiều rộng có thể co giãn (`width=width`), tránh bị ép chiếm 50% màn hình trong `Row`.
  - Bổ sung `clip_behavior=ft.ClipBehavior.HARD_EDGE` cho `ExplorerView`, ngăn chặn mọi trường hợp tràn viền đè lên Footer.

### 2.5. Ghi nhớ trạng thái thư mục mở rộng (`restore_expanded`)
- **Vị trí**: `src/ui_flet/views/explorer_view.py`
- **Cơ chế**:
  - Hàm `_collect_expanded_paths()` thu thập tập hợp tất cả các đường dẫn thư mục đang mở (`is_expanded = True`).
  - Hàm `restore_expanded(expanded_paths)` tự động mở lại thư mục và quét đệ quy các thư mục con tương ứng khi `refresh_tree()` chạy.
  - Giúp người dùng thoải mái bấm **Refresh** hoặc tạo/xóa tệp mà không bị mất dấu vị trí thư mục đang làm việc.

### 2.6. Kéo thả thông minh toàn vùng Folder (`Full Folder Zone Drag-and-Drop`)
- **Vị trí**: `src/ui_flet/views/explorer_view.py`
- **Cơ chế**:
  - Mọi `FileTreeItem` bên trong thư mục con đều được bọc `ft.DragTarget` với đích đến là thư mục cha chứa nó (`dest_dir = os.path.dirname(file_path)`).
  - Khi kéo tệp thả vào **bất kỳ vị trí nào** trong thư mục con đang mở rộng (dù trúng tên file hay khoảng cách), tệp sẽ được chuyển vào đúng thư mục cha đó.
  - Loại bỏ `DragTarget` bắt thả toàn cục. Gán điểm đón riêng cho thư mục gốc vào `self.folder_title_row` (`📁 Test`) với hiệu ứng highlight khi rê chuột qua.

### 2.7. Sửa lỗi Phím tắt `Ctrl+B`
- **Vị trí**: `src/ui_flet/controllers/layout_controller.py`
- **Cơ chế**: Bỏ điều kiện `and e is not None` trong `toggle_sidebar` để các lệnh gọi từ `ShortcutManager` (truyền `e=None`) đóng/mở Sidebar bình thường.

---

## 3. Tổng kết Thay đổi Files (File Modification Matrix)

| Tập tin | Loại thay đổi | Mô tả chi tiết |
| :--- | :---: | :--- |
| `src/__version__.py` | **[MOD]** | Nâng phiên bản ứng dụng lên `1.8.2`. |
| `src/modules/word_module.py` | **[MOD]** | Hỗ trợ căn lề ảnh `<p align="...">` sang `WD_ALIGN_PARAGRAPH.LEFT/CENTER/RIGHT` trong Word. |
| `src/ui_flet/components/image_size_dialog.py` | **[MOD]** | Thiết kế lại modal kích thước ảnh: nút bấm ngang, đồng bộ height input, padding gọn, fix cancel overlay. |
| `src/ui_flet/components/context_menu.py` | **[MOD]** | Tích hợp menu ngữ cảnh chỉnh sửa ảnh phong cách IDE Explorer khi click ảnh trên Preview. |
| `src/ui_flet/views/editor_view.py` | **[MOD]** | Gỡ bỏ auto-popup menu ảnh khi di chuyển con trỏ qua offset 0; kích hoạt menu thủ công an toàn. |
| `src/ui_flet/views/preview_view.py` | **[MOD]** | Kết nối sự kiện click chuột vào ảnh trong Preview với Context Menu định dạng ảnh. |
| `src/ui_flet/controllers/layout_controller.py` | **[MOD]** | Bổ sung Bước 11 Hydrate FooterBar trong `handle_doc_tab_selected`; sửa lỗi phím tắt `Ctrl+B`. |
| `src/ui_flet/controllers/file_controller.py` | **[MOD]** | Đồng bộ ẩn/hiện nút FooterBar khi nạp tệp từ Explorer (`open_file_by_path`). |
| `src/ui_flet/views/explorer_view.py` | **[MOD]** | Sửa cuộn ListView, chặn tràn viền Footer, khôi phục folder mở rộng khi refresh, full-zone drag-and-drop. |
| `README.md` | **[MOD]** | Cập nhật phiên bản v1.8.2, link tải và nhật ký phiên bản. |
| `docs/roadmaps/product_roadmap.md` | **[MOD]** | Đánh dấu hoàn thành toàn bộ các hạng mục của cột mốc v1.8.2. |
| `docs/releases/v1.8.2.md` | **[NEW]** | Tài liệu phát hành chính thức bản v1.8.2. |
| `docs/reports/image_sizing_and_format_bug_report.md` | **[MOD]** | Báo cáo kỹ thuật chi tiết về lỗi kích thước ảnh, định dạng lề và hướng dẫn sử dụng. |

---

## 4. Kết quả Kiểm thử & Đo lường (Test Suite Verification)

```
Ran 138 tests in 9.5s
OK (100% Pass)
```

- **Unit Tests**: 138/138 bài kiểm thử đạt kết quả xuất sắc ($100\%$).
- **Multi-Tab Concurrency**: Trạng thái chuyển đổi và nút bấm Footer đồng bộ mượt mà $100\%$ khi chuyển qua lại giữa các Tab.
- **Explorer Drag & Drop**: Kéo thả file nội bộ chính xác $100\%$, không có hiện tượng văng nhầm ra thư mục Root.
- **Image Formatting**: Căn lề ảnh Trái, Giữa, Phải xuất sang file Word `.docx` chuẩn xác từng pixel.
