# Báo Cáo Phân Tích & Giải Pháp Kỹ Thuật Flet Framework (Windows Desktop)

> **Dự án**: DocumentConvertTool  
> **Môi trường**: Windows 10/11 | Python 3.11+ | Flet UI (Flutter Desktop C++ Engine)  
> **Mục đích**: Lưu trữ nhật ký kỹ thuật chuẩn hóa giao diện, xử lý bất đồng bộ và kỹ thuật dựng In-App Custom Dialogs theo Palette Theme của ứng dụng.

---

## 📋 Hướng Dẫn Kỹ Thuật & Giải Pháp Chuẩn Tối Ưu

---

### 🎨 1. Kỹ thuật dựng In-App Custom Modal AlertDialog chuẩn Palette Theme

#### 📌 Vấn đề thường gặp:
Khi xây dựng `ft.AlertDialog` trong Flet UI:
1. Đôi khi Popup không xuất hiện hoặc bị giấu ngầm khi gọi trong luồng `asyncio`.
2. Dùng `await future` dễ gây treo luồng nếu coroutine chặn việc nhường luồng (Yield) của Flet.

#### 💡 Bí quyết kỹ thuật giải quyết 100% (Từ nhánh `fix/duy-31072026-html-ribbon-draft-fixes`):

1. **Đăng ký vào Overlay (`page.overlay.append`)**:
   Bắt buộc phải đẩy `dialog` vào mảng Overlay của trang trước khi mở:
   ```python
   if dialog not in self.page.overlay:
       self.page.overlay.append(dialog)
   self.page.dialog = dialog
   dialog.open = True
   self.page.update()
   ```

2. **Sử dụng Callback đồng bộ thay cho `await Future`**:
   Thay vì dùng `await fut` gây block coroutine, sử dụng hàm đóng `close_dialog` gọi callback kích hoạt trực tiếp:
   ```python
   def close_dialog(e, confirmed: bool):
       dialog.open = False
       self.page.update()

       if confirmed:
           on_confirm_callback()  # Tiến hành ghi đè file
       else:
           self.footer_bar.set_status("Conversion cancelled", ft.Colors.AMBER_400)
   ```

3. **Áp dụng Design Tokens từ `theme.py`**:
   Lấy màu sắc trực tiếp từ Palette đang chọn để Modal mang 100% phong cách thiết kế của app:
   ```python
   palette = PALETTES.get(self.state.current_palette, {})
   is_dark = self.page.theme_mode != ft.ThemeMode.LIGHT

   bg_card = resolve_color(palette, "bg_component", is_dark)
   bg_pill = resolve_color(palette, "bg_header", is_dark)
   accent_color = resolve_color(palette, "text_accent_secondary", is_dark)
   text_primary = get_style_color("text_primary", is_dark)
   border_color = resolve_color(palette, "border_color", is_dark)
   ```

---

### 🚨 2. Hạn chế về hiển thị ảnh Logo tùy chỉnh (`ft.Image`)

#### 📌 Hiện tượng:
Hiển thị **khối vuông màu xanh nhạt (Placeholder box)** tại vị trí Logo thay vì hình ảnh thực tế.

#### 🔍 Nguyên nhân kỹ thuật gốc rễ:
1. **Không hỗ trợ định dạng `.ico`**: Bộ giải mã hình ảnh của Flutter Engine bên trong Flet **chỉ hỗ trợ**: PNG, JPEG, SVG, GIF, WebP. Việc nạp file `.ico` vào `ft.Image` gây ra ngoại lệ `ImageDecoderException`.
2. **Hạn chế của máy chủ `assets_dir` khi chạy `ft.app()`**: Trong Flet 0.86.4, khi khởi chạy qua hàm `ft.app(target=main)`, bộ định tuyến tài nguyên tĩnh ngầm không gắn được đường dẫn đĩa tuyệt đối cho tiến trình C++ Flutter Desktop.
3. **Mã hóa Base64 Data URI bị coi là URL không hợp lệ**: Chuỗi `data:image/png;base64,...` quá dài bị Flutter Desktop runtime bỏ qua thay vì render như trên trình duyệt Web.
4. **Co nén điểm ảnh High-DPI (Downscaling)**: Nạp file PNG gốc độ phân giải cao (`512x512px`) vào khung chứa cực nhỏ (`22x22px`) làm thuật toán Flutter Downsampling loại bỏ các điểm ảnh, gây mất nét hoặc khung hình rỗng.

#### 🛠️ Giải pháp chuẩn mực:
- **Dùng Flutter Native Vector Icon (`ft.Icon`)**:
  ```python
  self.logo_icon = ft.Icon(
      ft.Icons.AUTO_AWESOME_ROUNDED,
      color=ft.Colors.PRIMARY,
      size=22,
  )
  ```
- **Biểu tượng Taskbar Windows**: Tiếp tục dùng file `icon256x256px.ico` gán cho `page.window.icon` để hiển thị sắc nét trên thanh tác vụ Windows.

---

### 🚨 3. Hạn chế lấy tiêu điểm cửa sổ Windows (Win32 Foreground Z-Order)

#### 📌 Hiện tượng:
Sau khi chuyển đổi tài liệu xong và tự động mở file bằng Microsoft Word hoặc Excel, cửa sổ Word/Excel đôi khi không tự đẩy lên trên cùng (Foreground).

#### 🔍 Nguyên nhân kỹ thuật gốc rễ:
Hệ điều hành Windows 10/11 có cơ chế bảo mật chống chiếm quyền màn hình (Foreground Lock Timeout), tự động ngăn cấm các tiến trình chạy ngầm gọi hàm Win32 API `SetForegroundWindow` (`SetForegroundWindow: False`).

#### 🛠️ Giải pháp chuẩn mực:
Áp dụng chiến lược 4 lớp trong [env.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/utils/env.py#L35):
1. **Layer 1**: Gọi `SetForegroundWindow`.
2. **Layer 2**: Gán tạm `SetWindowPos(HWND_TOPMOST)`.
3. **Layer 3**: Giả lập phím `ALT` via `keybd_event`.
4. **Layer 4**: Nhấp nháy thanh Taskbar qua API `FlashWindowEx`.

---

## 🎯 Kết Luận

Tài liệu này tổng hợp toàn bộ giải pháp kỹ thuật tối ưu để phát triển các thành phần UI, Custom Modal và dịch vụ nền trong dự án **DocumentConvertTool**.
