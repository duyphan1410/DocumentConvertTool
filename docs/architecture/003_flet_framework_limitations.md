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

### 🚨 3. Hạn chế lấy tiêu điểm cửa sổ Windows (Win32 Foreground Z-Order Focus)

#### 📌 Hiện tượng ban đầu:
1. Khi bấm mở tệp hoặc mở thư mục kết quả (Word, Excel, PowerPoint, Windows Explorer), cửa sổ ứng dụng target đôi khi nằm lại phía sau ứng dụng Flet hoặc bị thu nhỏ.
2. Với các tiến trình đã chạy sẵn trên Windows (như `explorer.exe` hoặc `excel.exe` khi mở lần 2), Windows OS chặn không cho ứng dụng Flet đẩy cửa sổ target lên Active Foreground (`SetForegroundWindow: False`).
3. Dùng cờ `HWND_NOTOPMOST` chớp nháy trước đây làm cửa sổ target hiện lên 1ms rồi tự động rụt về phía sau app Flet, gây hỏng thứ tự Alt+Tab.

#### 🔍 Nguyên nhân kỹ thuật gốc rễ:
Hệ điều hành Windows 10/11 áp dụng chính sách bảo mật `ForegroundLockTimeout` để ngăn cản các ứng dụng chạy ngầm "cướp" quyền Focus bàn phím. Nếu ứng dụng gọi `SetForegroundWindow` mà không có sự kiện tương tác bàn phím thực tế của người dùng hoặc không gán quyền `AllowSetForegroundWindow` cho `target_pid`, Windows DWM sẽ chặn chuyển đổi focus và đẩy cửa sổ target xuống Z-order phía sau.

#### 🛠️ Giải pháp chuẩn mực (Đã triển khai thành công tại `src/utils/env.py`):

Áp dụng cơ chế **Universal Dynamic Window Focus** kết hợp 4 lớp kỹ thuật Win32 API (Chi tiết hơn tại [005_universal_dynamic_window_focus.md](005_universal_dynamic_window_focus.md)):

```python
# 1. Mở khóa ForegroundLockTimeout bằng phím ALT ngầm (Simulated Keyboard Event)
user32.keybd_event(0x12, 0, 0x0001, 0)
user32.keybd_event(0x12, 0, 0x0001 | 0x0002, 0)

# 2. Cấp quyền kích hoạt màn hình cho đúng Process ID của ứng dụng target (Word/Excel/Explorer)
target_pid = ctypes.wintypes.DWORD()
user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
if target_pid.value:
    user32.AllowSetForegroundWindow(target_pid.value)

# 3. Phóng to cửa sổ Toàn màn hình (FULL SCREEN / Maximized)
user32.ShowWindow(hwnd, SW_MAXIMIZE)

# 4. Đưa cửa sổ lên đỉnh Z-order tự nhiên bằng HWND_TOP (Không dùng HWND_NOTOPMOST gây sụt Z-index)
user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)

# 5. Liên kết luồng nhập liệu bàn phím và chuyển Active Focus
curr_fg_hwnd = user32.GetForegroundWindow()
if curr_fg_hwnd and curr_fg_hwnd != hwnd:
    fg_thread_id = user32.GetWindowThreadProcessId(curr_fg_hwnd, None)
    target_thread_id = user32.GetWindowThreadProcessId(hwnd, None)
    if fg_thread_id and target_thread_id and fg_thread_id != target_thread_id:
        attached = bool(user32.AttachThreadInput(fg_thread_id, target_thread_id, True))

try:
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
finally:
    if attached:
        user32.AttachThreadInput(fg_thread_id, target_thread_id, False)

# 6. Retry chớp phím ALT nếu OS vẫn hạn chế
if user32.GetForegroundWindow() != hwnd:
    user32.keybd_event(0x12, 0, 0x0001, 0)
    user32.keybd_event(0x12, 0, 0x0001 | 0x0002, 0)
    user32.SetForegroundWindow(hwnd)
```

#### ✅ Kết quả đạt được:
1. **Focus 100% cửa sổ mới mở**: Cửa sổ Excel, Word, PowerPoint, PDF, HTML và Windows Explorer nổi lên đúng vị trí số 1 ngay khi nhấn nút.
2. **Alt+Tab mượt mà & Đưa app Flet xuống thứ tự tự nhiên**: Loại bỏ hoàn toàn việc dùng `HWND_TOPMOST` / `HWND_NOTOPMOST` chớp nháy, giúp thứ tự Alt+Tab của hệ điều hành Windows hoạt động hoàn hảo.
3. **Chống lặp lỗi tự chui ra sau app**: Xử lý triệt để bài toán `explorer.exe` và `excel.exe` mở nhiều lần (lần 1, 2, 3...) hoạt động ổn định 100%.

---

## 🎯 Kết Luận

Tài liệu này tổng hợp toàn bộ giải pháp kỹ thuật tối ưu để phát triển các thành phần UI, Custom Modal và dịch vụ nền trong dự án **DocumentConvertTool**.
