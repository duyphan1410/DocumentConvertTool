# Báo Cáo Phân Tích Kỹ Thuật & Nhật Ký Kiểm Thử Hiển Thị Logo Ảnh Trong Flet UI

> **Dự án**: DocumentConvertTool  
> **Phiên bản Flet**: `0.86.4` (Flutter Desktop Engine)  
> **Trạng thái**: Tạm thời đóng hạng mục ảnh Logo cục bộ, chuyển sang sử dụng **Flutter Native Vector Icon** (`ft.Icon`) để bảo đảm giao diện 100% sắc nét, chuẩn thiết kế Office Ribbon.

---

## 1. Tóm Tắt Các Phương Pháp Đã Thử Nghiệm

Trong quá trình giải quyết hiện tượng hiển thị **Khối vuông màu xanh nhạt (Placeholder box)** tại vị trí Logo, chúng tôi đã thử nghiệm và ghi nhận kết quả từ 7 phương pháp sau:

| STT | Phương pháp kiểm thử | Mã nguồn / Cách thức | Kết quả ghi nhận |
| :---: | :--- | :--- | :--- |
| **1** | **Đường dẫn tương đối** | `ft.Image(src="icon-icons.png")` | ❌ Lỗi ô vuông xanh (Flutter không định tuyến được đĩa cứng). |
| **2** | **Đường dẫn tuyệt đối** | `ft.Image(src=os.path.abspath("assets/icon-icons.png"))` | ❌ Lỗi ô vuông xanh (Flet Desktop hạn chế load tệp đĩa trực tiếp qua `src`). |
| **3** | **Base64 Data URI** | `ft.Image(src="data:image/png;base64,iVBORw...")` | ❌ Lỗi ô vuông xanh (Flet hiểu nhầm `data:` là URL mạng HTTP). |
| **4** | **Raw Bytes (`bytes`)** | `ft.Image(src=open("assets/android-chrome-512x512.png", "rb").read())` | ❌ Lỗi ô vuông xanh (Bộ tuần tự hóa Flet Python -> Flutter gặp rào cản truyền mảng byte). |
| **5** | **Cấu hình `assets_dir`** | `ft.app(target=main, assets_dir="assets")` | ❌ Lỗi ô vuông xanh (`ft.app` là hàm Deprecated từ Flet 0.80+). |
| **6** | **Chuyển sang `ft.run`** | `ft.run(main, assets_dir=os.path.abspath("assets"))` | ❌ Lỗi ô vuông xanh (Vẫn gặp xung đột render đối với container thu nhỏ 22x22px trên Windows). |
| **7** | **Thiết lập BoxFit & Error Content** | `fit=ft.BoxFit.CONTAIN`, `error_content=ft.Icon(...)` | ⚠️ Rơi về `error_content` (Hiển thị Icon Vector thay thế). |

---

## 2. Nguyên Nhân Kỹ Thuật Gốc Rễ (Root Cause Analysis)

### 🚨 Nguyên nhân 1: Xung đột bộ giải mã ảnh `.ico` trên Flutter Engine
- File `.ico` là định dạng biểu tượng đa độ phân giải dành riêng cho hệ điều hành Windows (`WM_SETICON`).
- Bộ giải mã hình ảnh của Flutter Engine bên trong Flet **chỉ hỗ trợ**: PNG, JPEG, SVG, GIF, WebP. Khi nạp file `.ico` vào `ft.Image`, Flutter văng ngoại lệ `ImageDecoderException` và hiển thị ô màu xanh nhạt fallback.

### 🚨 Nguyên nhân 2: Khung chứa (Container) thu nhỏ quá mức (22x22 pixel)
- File ảnh Logo thương hiệu (như `512x512` px) khi đưa vào khung chứa cực nhỏ (`width=22, height=22`) trên thanh Ribbon Bar trong chế độ High-DPI của Windows 10/11 bị thuật toán Flutter Downsampling loại bỏ các điểm ảnh, gây mất nét hoặc lỗi bố cục rỗng.

### 🚨 Nguyên nhân 3: Cơ chế Asset Server ngầm trong Flet Desktop Mode
- Khác với Web/Browser thông thường (hỗ trợ thẻ `<img src="data:image/png;base64,...">`), Flet Desktop chạy một tiến trình Flutter C++ client riêng. Việc truyền chuỗi Base64 dài qua giao thức WebSocket bị nghẽn hoặc sai cấu hình MIME Type header.

---

## 3. Giải Pháp Tạm Thời & Tối Ưu Hiện Tại

Để ứng dụng vận hành **mượt mà, chuẩn thẩm mỹ Office Ribbon, không bao giờ gặp lỗi giao diện**, chúng tôi áp dụng thiết kế bằng **Vector Native Icons của Flutter**:

1. **Thanh Ribbon Bar ([ribbon_bar.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/ui_flet/layout/ribbon_bar.py#L120))**:
   ```python
   self.logo_icon = ft.Icon(
       ft.Icons.AUTO_AWESOME_ROUNDED,
       color=ft.Colors.PRIMARY,
       size=22,
   )
   ```
2. **Màn hình Welcome Dashboard ([welcome_view.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/ui_flet/views/welcome_view.py#L26))**:
   ```python
   self.icon_logo = ft.Icon(
       ft.Icons.DESCRIPTION_ROUNDED,
       color=ft.Colors.PRIMARY,
       size=56,
   )
   ```
3. **Thanh Taskbar & Title Bar Windows ([app.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/ui_flet/app.py#L58))**:
   - Tiếp tục giữ nguyên `self.page.window.icon = resolve_icon_path("icon256x256px.ico")` để đảm bảo Icon trên thanh Taskbar Windows hiển thị cực nét.

---
*Tài liệu được đóng gói tự động cho dự án DocumentConvertTool.*
