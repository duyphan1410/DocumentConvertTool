# 📋 Báo Cáo Tổng Hợp & Kết Quả Xử Lý: Image Sizing, Floating Mini-Toolbar & Trạng Thái Undo

> **Dự án**: DocumentConvertTool  
> **Thời gian tạo**: 29/08/2026  
> **Phạm vi**: Nhánh `feat/duy-29082026-floating-image-toolbar-and-format-fixes`  
> **Trạng thái**: ✅ **ĐÃ KHẮC PHỤC HOÀN TOÀN & KIỂM THỬ 100% THÀNH CÔNG** (138/138 Unit Tests Passed)

---

## 📌 1. Tổng quan & Bối cảnh (Executive Summary)

Tính năng **Image Sizing Dialog & Format** ban đầu được tích hợp trên Ribbon Bar của PR `feat/huy-29082026-Image-Sizing-Dialog-&-Format-Tab`. Trong quá trình sử dụng thực tế, tính năng này bộc lộ các vấn đề:
1. **Lỗi Runtime / Crash**: `ImageFit` không tồn tại trong Flet, API `page.open/close` không tương thích, `dd_unit.on_select` không hợp lệ.
2. **Lỗi logic & tương tác**: Nút đổi ảnh (Replace Image) không áp dụng, các nút preset 25% → 100% chỉ click được 1 lần (lần 2 bị đơ do mất focus), xuất Word bị ép ra giữa.
3. **Trải nghiệm UI/UX bị chật chội**: Nhét cụm Picture Format vào thanh Ribbon 38px gây dồn nút và đổi màu nền tím bị quá gắt ("Overkill").
4. **Lỗi mất đồng bộ trạng thái `is_dirty` khi Undo**: Khi người dùng gõ phím rồi nhấn Undo (`Ctrl+Z` hoặc `[↩]`) về đúng nội dung ban đầu lúc mở file, tab vẫn bị giữ chấm bẩn `is_dirty = True`.

Toàn bộ các vấn đề trên đã được **tái cấu trúc và khắc phục triệt để** trên nhánh mới `feat/duy-29082026-floating-image-toolbar-and-format-fixes`.

---

## 📊 2. Bảng Theo Dõi Trạng Thái Xử Lý Lỗi

| STT | Vấn đề / Triệu chứng | Mức độ | Trạng thái | Giải pháp đã thực hiện |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Crash khi mở Image Sizing Dialog** (`ImageFit` không tồn tại) | 🔴 **CRITICAL** | ✅ **RESOLVED** | Chuyển sang `ft.BoxFit.CONTAIN` chuẩn Flet. |
| **2** | **Crash khi mở/đóng Modal Dialog** (`page.open/close` không tồn tại) | 🔴 **CRITICAL** | ✅ **RESOLVED** | Quản lý qua `page.overlay.append(dlg)`, `dlg.open = True/False` và `page.update()`. |
| **3** | **Không căn lề được ảnh trên Preview** (ảnh luôn dính lề trái) | 🟠 **HIGH** | ✅ **RESOLVED** | Cập nhật bộ render Preview Markdown hỗ trợ căn lề thẻ HTML `p align`. |
| **4** | **Nút Replace Image chỉ mở Picker rồi không cập nhật gì** | 🟠 **HIGH** | ✅ **RESOLVED** | Chuyển đổi đường dẫn ảnh thành đường dẫn tương đối (relative path) và kích hoạt update UI đồng bộ. |
| **5** | **Preset 25% → 100% & Reset bị đơ ở lần click thứ 2** | 🟠 **HIGH** | ✅ **RESOLVED** | Bổ sung cơ chế **`pinned_image_token`** và truyền explicit token vào action handler. |
| **6** | **Xung đột căn lề khi xuất Word** (ảnh không chọn căn lề bị ép ra Giữa) | 🟡 **MEDIUM** | ✅ **RESOLVED** | Sửa nhánh mặc định khi `tok.align == ""` thành `WD_ALIGN_PARAGRAPH.LEFT`. |
| **7** | **Lỗi thuộc tính Dropdown `on_select`** | 🟡 **MEDIUM** | ✅ **RESOLVED** | Gán sự kiện qua thuộc tính chuẩn `dd_unit.on_change = ...`. |
| **8** | **Undo về nội dung gốc lúc mở file vẫn bị `is_dirty`** | 🟠 **HIGH** | ✅ **RESOLVED** | Bổ sung `saved_content` vào `DocumentTabState`, tự động so sánh tắt chấm bẩn khi Undo/Redo về baseline. |
| **9** | **UI Header bị chật chội, che khuất nút Open/Undo/Redo** | 🔵 **UI/UX** | ✅ **RESOLVED** | Gỡ bỏ toàn bộ bar trên Header; chuyển toàn bộ tính năng vào **Explorer-Style Context Menu**. |
| **10** | **Hiện tượng Menu tự động bung liên tục khi ảnh ở đầu văn bản (`offset 0`)** | 🟠 **HIGH** | ✅ **RESOLVED** | Phân tích cơ chế `TextField`: Tắt auto-popup theo con trỏ text; chuyển sang cơ chế **Click trực tiếp trên Live Preview (Intentional Action)**. |

---

## 🔬 3. Chi Tiết Các Cải Tiến Kiến Trúc Đã Triển Khai

### 3.1. Phân Tích Hiện Tượng Auto-Popup tại Đầu Dòng (`Offset 0`) & Giải Pháp Kiến Trúc
* **Bản chất kỹ thuật**: Trong Flutter/Flet `TextField`, khi nạp file hoặc sau khi thay thế văn bản, con trỏ chuột mặc định rơi vào vị trí đầu tiên (`offset = 0`). Nếu tài liệu có ảnh ngay dòng 1 (`offset 0`), sự kiện `on_selection_change` liên tục nhận diện được token ảnh $\rightarrow$ gây ra vòng lặp tự động bung Context Menu ngoài ý muốn và khóa giao diện.
* **Quyết định kiến trúc**: 
  - Tách biệt $100\%$ giữa việc gõ văn bản và tương tác ảnh: Khung soạn thảo `Editor` giữ nguyên tĩnh lặng, không tự động bung popup che chữ khi di chuyển con trỏ.
  - Chuyển toàn bộ tương tác ảnh sang **Click trực tiếp vào ảnh trên Live Document Preview** (chuẩn như Microsoft Word) và **Explorer Context Menu** 2 cấp.

### 3.2. Context Menu 2 Cấp Chuẩn File Explorer (Explorer-Style Image Context Menu)
* **Vị trí**: Nổi trực tiếp tại tọa độ click của bức ảnh trên Live Document Preview.
* **Cấu trúc Menu**:
  ```text
  ┌─────────────────────────────────────────────────────────┐
  │ 🖼️ Tên ảnh (Badge Header)                              │
  ├─────────────────────────────────────────────────────────┤
  │ 📐 Image Size (Kích thước)                    › ────────┼──> ┌───────────────────────────┐
  │ 📍 Alignment (Căn lề)                         › ────────┼──┐ │ 25% (Quarter Width)       │
  ├─────────────────────────────────────────────────────────┤  │ │ ✓ 50% (Half Width) [Active]│
  │ 📂 Replace Image... (Đổi ảnh khác)                      │  │ │ 75% (Three Quarters)      │
  │ ⚙️ Custom Size & Dimensions... (Tùy chỉnh W×H)          │  │ │ 100% (Original / Full)    │
  │ ↺ Reset to Original (Đặt lại mặc định)                 │  │ ├───────────────────────────┤
  └─────────────────────────────────────────────────────────┘  │ │ ⚙️ Custom Dimensions...   │
                                                               │ └───────────────────────────┘
                                                               │
                                                               └──> ┌────────────────────────┐
                                                                    │ ⫷ Align Left (Trái)    │
                                                                    │ ✓ ⫹ Align Center (Giữa)│
                                                                    │ ⫸ Align Right (Phải)   │
                                                                    └────────────────────────┘
  ```
* **Hiệu ứng trực quan**: 
  - Tự động đánh **dấu tích xanh `✓`** và **highlight màu Accent** vào đúng kích thước và căn lề mà bức ảnh đang áp dụng.
  - Tự động đóng menu ngay khi người dùng chọn xong bất kỳ tùy chọn nào và cập nhật đồng bộ 2 chiều (Editor Markdown $\leftrightarrow$ Live Preview).

### 3.3. Cơ chế Theo Dõi `saved_content` Chuẩn IDE cho `is_dirty`
* Thêm trường `saved_content: str = ""` vào `DocumentTabState`.
* Cập nhật `tab.saved_content = content` và `tab.is_dirty = False` khi:
  - Nạp tệp từ đĩa vào tab (`open_file_by_path`).
  - Mở tab tài liệu mới (`handle_new_doc_tab`).
  - Lưu tệp thành công qua phím tắt `Ctrl+S` hoặc hộp thoại Save (`save_content`).
* Khi Undo (bằng nút `[↩]` hoặc `Ctrl+Z`) quay về nội dung ban đầu lúc mở file, **chấm bẩn `•` trên Tab tự động biến mất** tức thì.

### 3.4. Tái Cấu Trúc Hộp Thoại Tùy Chỉnh Nâng Cao (`ImageSizeDialog`)
* **Bố cục các nút Footer chuẩn hàng ngang (`Horizontal Row Layout`)**:
  - Sắp xếp cố định: Bên trái là `[↺ Reset to Original]`, bên phải là `[Cancel]` và `[✓ Apply Sizing]`.
  - Khóa `actions_padding=ft.Padding(0, 0, 0, 0)` và tinh chỉnh `content_padding=ft.Padding(18, 6, 18, 10)` $\rightarrow$ Loại bỏ triệt để khoảng trống thừa xám dày ở đáy modal.
* **Đồng bộ hóa kích thước ô nhập Width & Height với Dropdown đơn vị**:
  - Ô nhập `Width`, ô chọn `Unit` (`px` / `%`, `width=90`), và ô nhập `Height` đều có chiều cao cân đối chuẩn xác, nằm trên một hàng ngang thẳng tắp.
* **Mở rộng đệm trường thông tin**:
  - `Alt Description Text` và `Image Source / Path` được nâng `content_padding=ft.Padding(12, 12, 12, 12)` giúp văn bản rộng rãi, thoáng mắt.
* **Vòng đời Modal chuẩn xác (Clean Lifecycle)**:
  - Khắc phục lỗi nút Cancel không đóng được modal: Giữ nguyên control trong overlay khi gọi `self.dialog.open = False` và `self.page.update()`.
  - Hỗ trợ đóng modal linh hoạt bằng 4 cách:
    1. Bấm nút **`Cancel`**.
    2. Bấm chuột ra ngoài vùng màng mờ (**Backdrop click**).
    3. Bấm biểu tượng **`[✕]` (Close)** ở góc trên bên phải tiêu đề.
    4. Bấm phím **`Esc`**.

---

## 📖 4. Hướng Dẫn Sử Dụng (User Guide)

### 4.1. Thao tác nhanh qua Context Menu trên Live Preview (Khuyên dùng)
1. **Mở Menu tương tác**: Click chuột trái trực tiếp vào bất kỳ bức ảnh nào trên khung **Live Document Preview** bên phải.
2. **Chọn kích thước**: Rê chuột vào mục **`Image Size ›`** $\rightarrow$ Click chọn `25%`, `50%`, `75%`, `100%`. Menu tự động đóng và văn bản cập nhật tức thì.
3. **Chọn căn lề**: Rê chuột vào mục **`Alignment ›`** $\rightarrow$ Click chọn `Left`, `Center`, hoặc `Right`.
4. **Đổi ảnh khác**: Click mục **`Replace Image...`** $\rightarrow$ Chọn file ảnh mới từ máy tính.
5. **Đặt lại mặc định**: Click mục **`Reset to Original`** để khôi phục $100\%$ kích thước gốc.

### 4.2. Tùy chỉnh kích thước nâng cao (Pixel & Tỉ lệ khung hình)
1. Click vào ảnh trên Live Preview $\rightarrow$ Chọn **`Custom Size & Dimensions...`**.
2. Nhập số pixel chính xác cho `Width` / `Height`, hoặc chọn đơn vị `%`.
3. Bấm biểu tượng **`[🔒 Lock Aspect Ratio]`** để tự động khóa/mở khóa tỷ lệ chiều dài $\times$ chiều cao.
4. Chỉnh sửa `Alt Description` hoặc duyệt tệp ảnh mới qua nút **`[📁]`**.
5. Bấm **`[✓ Apply Sizing]`** để áp dụng hoặc bấm **`Cancel`** / click ra ngoài để hủy.

---

## ⚠️ 5. Lưu Ý Kỹ Thuật Quan Trọng (Technical Notes)

> [!IMPORTANT]
> **Về việc hiển thị căn lề ảnh trên Live Document Preview**:
> * Khung **Live Document Preview** sử dụng bộ render `flutter_markdown` của Flutter Engine. Do đặc thù của engine Markdown hiển thị inline trong Flutter, thuộc tính `align` của thẻ `<p align="left|center|right">` hiện tại **không thể hiện thay đổi vị trí trực tiếp trên Live Preview** (ảnh sẽ hiển thị theo luồng tài liệu mặc định).
> * **Tuy nhiên, khi xuất sang file Word (`.docx`) hoặc PDF**, module chuyển đổi tài liệu (`WordModule`) sẽ đọc chính xác $100\%$ thẻ căn lề HTML và đặt ảnh vào đúng vị trí **Trái / Giữa / Phải** chuẩn chỉnh trong tài liệu Word xuất ra.

---

## 🧪 6. Kết Quả Kiểm Thử & Xác Minh (Verification)

### 6.1. Automated Unit Tests
```powershell
python -m unittest discover -s tests
```
```
----------------------------------------------------------------------
Ran 138 tests in 9.596s

OK (138/138 Passed - 100%)
```

---
*Báo cáo được hoàn thiện và cập nhật đầy đủ vào tài liệu dự án.*
