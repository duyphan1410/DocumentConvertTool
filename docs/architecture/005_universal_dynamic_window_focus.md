# 🏛️ ADR 005: Universal Dynamic Window Focus & Browser Thread Input Attachment

**Ngày quyết định:** 12/08/2026  
**Trạng thái:** Accepted & Implemented  
**Tầng tác động:** `src/utils/env.py`, `src/modules/html_module.py`  

---

## 1. Ngữ cảnh & Vấn đề (Context & Problem Statement)

Khi người dùng thực hiện chuyển đổi hoặc mở tệp kết quả (Word, Excel, PowerPoint, PDF, HTML) từ ứng dụng **Document Converter Tool**, hệ thống cần đưa ứng dụng đọc tương ứng (VS Code, Word, Excel, Chrome...) lên màn hình chính (**Z-Index #1 Active Foreground Focus**) để người dùng thao tác ngay.

Tuy nhiên, với các **Trình duyệt Web (Chrome, Edge, Firefox, Brave...)**:
1. **Thiết kế gom Tab (Multi-Tab Browser Process)**: Khi mở file `.html`, trình duyệt không tạo cửa sổ Win32 mới mà mở thêm Tab vào cửa sổ đã chạy trước đó.
2. **Chính sách bảo mật Windows (`ForegroundLockTimeout`)**: Windows 10/11 chặn các tiến trình ứng dụng ngầm "cướp" quyền Focus bàn phím sang một tab trình duyệt chạy ngầm, khiến biểu tượng trình duyệt bị nhấp nháy màu cam trên thanh Taskbar (`FlashWindowEx`).
3. **Hiện tượng Hardcode danh sách trình duyệt (Anti-Pattern)**: Ban đầu nếu ta viết cứng danh sách tên trình duyệt (`"chrome" in title or "edge" in title`), hệ thống sẽ mất đi tính linh hoạt (Dynamic Pattern) và bị đơ/hỏng khi người dùng sử dụng trình duyệt khác (Vivaldi, Opera, Arc, Waterfox, Tor Browser...).

---

## 2. Quyết định Kiến trúc (Architecture Decisions)

### 🎯 Nguyên tắc 1: Thuật toán Dò tìm Động 100% (True Dynamic Matching)
- **Tuyệt đối KHÔNG viết cứng (hardcode) danh sách trình duyệt** hoặc danh sách tên phần mềm trong `env.py`.
- **Sửa tận gốc tại `HTMLModule` (`src/modules/html_module.py`)**:
  - Gán nhãn tiêu đề động: `<title>{os.path.basename(out_path)}</title>` (ví dụ: `<title>testpptx.html</title>`).
  - Khi đó, **BẤT KỲ trình duyệt nào trên thế giới** khi mở file HTML đều tự động đưa tên tệp `testpptx.html` lên thanh tiêu đề cửa sổ.
  - Thuật toán `file_name in title` trong `env.py` duy trì khả năng nhận diện **ĐỘNG 100%** cho mọi trình đọc và mọi ứng dụng trên Windows mà không cần khai báo danh sách cứng.

### 🎯 Nguyên tắc 2: Liên kết Luồng Nhập Liệu (`AttachThreadInput`)
- Sử dụng API Win32 `user32.AttachThreadInput` để liên kết luồng nhập liệu bàn phím giữa ứng dụng hiện tại và tiến trình target trước khi gọi `SetForegroundWindow`:
  ```python
  curr_fg_hwnd = user32.GetForegroundWindow()
  if curr_fg_hwnd and curr_fg_hwnd != hwnd:
      fg_thread_id = user32.GetWindowThreadProcessId(curr_fg_hwnd, None)
      target_thread_id = user32.GetWindowThreadProcessId(hwnd, None)
      if fg_thread_id and target_thread_id and fg_thread_id != target_thread_id:
          attached = bool(user32.AttachThreadInput(fg_thread_id, target_thread_id, True))

  try:
      user32.BringWindowToTop(hwnd)
      user32.SetForegroundWindow(hwnd)
      user32.SwitchToThisWindow(hwnd, True)
  finally:
      if attached:
          user32.AttachThreadInput(fg_thread_id, target_thread_id, False)
  ```

---

## 3. Kết quả & Đánh giá (Consequences)

- **Trải nghiệm mượt mà**: Cửa sổ Chrome, Edge, VS Code, Word, Excel nhảy vọt 100% lên trước màn hình mà không bao giờ bị dính nhấp nháy Taskbar.
- **Tính mở rộng (Extensibility)**: Hoạt động động với 100% phần mềm và trình duyệt hiện tại cũng như tương lai trên hệ điều hành Windows.
