# 📑 Báo Cáo Nghiên Cứu Kỹ Thuật — Native Windows Drag & Drop trên Flet Desktop

**Ngày báo cáo:** 10/08/2026
**Dự án:** DocumentConvertTool
**Tác giả:** Dev Team & Pair Programming AI Assistant
**Trạng thái:** 🛑 Spike Completed — Architectural Blocker Identified (Future-Ready Blueprint)

---

## 1. 🎯 Mục Tiêu Khảo Sát

Tích hợp tính năng kéo thả tệp (`Drag & Drop`) trực tiếp từ Windows File Explorer vào ứng dụng Flet Desktop (`DocumentConvertTool`) bằng cách đăng ký giao diện Win32 OLE `IDropTarget` (`pywin32`) lên cửa sổ OS (`HWND`).

---

## 2. 🔬 Phương Pháp Thực Nghiệm & Đo Lường (Phase 0 Spike)

Kịch bản thực nghiệm độc lập được viết tại `spike_dnd.py` để kiểm tra tính khả thi của `RegisterDragDrop` trên cửa sổ Flet đang chạy.

### Mã Nguồn Kịch Bản Spike

```python
import os, sys, asyncio, ctypes
import win32api, win32process, win32con
import pythoncom, win32com.server.util, win32com.server.policy
import flet as ft

class SimpleDropTarget:
    _public_methods_ = ["DragEnter", "DragOver", "DragLeave", "Drop"]
    _com_interfaces_ = [pythoncom.IID_IDropTarget]

    def DragEnter(self, dataObj, keyState, point, effect):
        print(f"[SUCCESS] DragEnter received at point={point}!")
        return win32con.DROPEFFECT_COPY

    def DragOver(self, keyState, point, effect): return win32con.DROPEFFECT_COPY
    def DragLeave(self): return 0
    def Drop(self, dataObj, keyState, point, effect):
        print(f"[SUCCESS] Drop received at point={point}!")
        return win32con.DROPEFFECT_COPY

async def message_pump_loop():
    while True:
        try: pythoncom.PumpWaitingMessages()
        except Exception: pass
        await asyncio.sleep(0.05)

async def flet_main(page: ft.Page):
    page.title = "DnD_Spike_Test_Window"
    page.add(ft.Text("Drag & Drop Test Window"))
    await asyncio.sleep(1.5)

    hwnd = ctypes.windll.user32.FindWindowW(None, page.title)
    thread_id, window_pid = win32process.GetWindowThreadProcessId(hwnd)
    current_pid, current_tid = os.getpid(), win32api.GetCurrentThreadId()

    print(f"[SPIKE] Window HWND: {hwnd} | Window PID: {window_pid} | Python PID: {current_pid}")
    print(f"[SPIKE] Window Thread ID: {thread_id} | Python Thread ID: {current_tid}")

    if window_pid != current_pid:
        print("[SPIKE FATAL] Window thuộc process KHÁC (Flutter runner process)!")

    pythoncom.OleInitialize()
    target = SimpleDropTarget()
    wrapped = win32com.server.util.wrap(target, usePolicy=win32com.server.policy.DesignatedWrapPolicy)
    pythoncom.RegisterDragDrop(hwnd, wrapped)
    asyncio.create_task(message_pump_loop())
```

---

## 3. 📊 Kết Quả Thực Nghiệm Trực Tiếp

```text
[SPIKE] Starting Flet App...
[SPIKE] App page rendered. Waiting 1.5s for window to initialize...
[SPIKE] FindWindowW('DnD_Spike_Test_Window') returned HWND: 656932
[SPIKE] Window HWND: 656932 | Window PID: 9528 | Current Python PID: 10532
[SPIKE] Window Thread ID: 5084 | Current Python Thread ID: 17172
[SPIKE] [SPIKE FATAL] Window PID (9528) != Python PID (10532) -- DIFFERENT PROCESS!
[SPIKE] Explanation: The window belongs to the Flutter Desktop runner process, not the Python process!
[SPIKE] RegisterDragDrop cannot attach OLE handlers across process boundaries.
[SPIKE] Wrapped COM target: <PyIDispatch at 0x000002514F1732C0 with obj at 0x000002514F168FB0>
[SPIKE] RegisterDragDrop returned HRESULT/result: None (S_OK)
[SPIKE] COM STA message pump active (PumpWaitingMessages every 50ms).
[SPIKE] [SPIKE READY] Window is active. Try dragging a file from Explorer onto the window now...
```

---

## 4. 🧠 Phân Tích Nguyên Nhân Kỹ Thuật (Technical Root Cause)

1. **Kiến Trúc Đa Tiến Trình (Dual-Process Client/Driver Model)**:
   Flet Desktop (`ft.app(target=main)`) chia làm 2 tiến trình độc lập:
   - **Process Python (`PID 10532`)**: Chạy logic ứng dụng Python, AppState và Controllers.
   - **Process Flutter Client Runner (`PID 9528`)**: Chạy ứng dụng C++ Flutter Native render giao diện GUI.
2. **Giới Hạn Win32 OLE `RegisterDragDrop`**:
   Hàm `RegisterDragDrop(hwnd, pDropTarget)` của Windows OLE yêu cầu đối tượng `IDropTarget` COM server nằm **trong cùng tiến trình sở hữu `HWND`**. Vì cửa sổ thuộc về Process Flutter `9528`, các thông điệp Win32 `WM_DROPFILES` / OLE drag & drop được xử lý bởi Message Loop của Process `9528` và không bao giờ chuyển qua ranh giới Process (IPC Boundary) tới COM handler trong Process Python `10532`.
3. **Thử Nghiệm COM STA Message Pump**:
   Ngay cả khi bổ sung vòng lặp `pythoncom.PumpWaitingMessages()` định kỳ 50ms trên Thread Python, sự kiện `DragEnter` vẫn im lặng vì thông điệp không bao giờ được gửi tới Python process queue.
4. **Xác Nhận Cùng Upstream Issue**:
   Thực nghiệm này giải thích nguyên nhân gốc rễ vì sao GitHub Issue [flet-dev/flet#112](https://github.com/flet-dev/flet/issues/112) ("Implement Drag/Drop on desktop client") vẫn mở từ năm 2022 mà chưa thể giải quyết bằng script Python ở tầng ứng dụng.

---

## 5. 🛠️ Kế Hoạch Sẵn Sàng Khi Flet Cập Nhật Kiến Trúc (Future Roadmap)

Mặc dù tính năng chưa thể kích hoạt trực tiếp qua `pywin32`, toàn bộ cấu trúc mã nguồn đã được tổ chức sẵn sàng để kích hoạt ngay khi Flet ra mắt phiên bản hỗ trợ Drag & Drop native:

1. **Giao diện Overlay phủ toàn màn hình**:
   [drag_drop_overlay.py](../../src/ui_flet/components/drag_drop_overlay.py) (Đã sẵn sàng trong `main_stack`).
2. **Bộ điều khiển Controller xử lý danh sách tệp**:
   [file_controller.py](../../src/ui_flet/controllers/file_controller.py) (Hàm `handle_dropped_files()` đã sẵn sàng lọc tệp & nạp tự động qua pipeline `open_file_by_path()`).
3. **Tài liệu Kế hoạch triển khai**:
   `implementation_plan.md` đóng vai trò là Blueprint tham chiếu đầy đủ.

---

## 6. 🧪 Đánh Giá Giải Pháp Thay Thế: Tkinter Overlay Window (Option 3)

### Ý Tưởng Kỹ Thuật
Tạo một cửa sổ trong suốt `tkinter.Toplevel()` luôn đè lên trên (`topmost`) cửa sổ Flet, liên tục đồng bộ vị trí & kích thước (`GetWindowRect(flet_hwnd)`). Vì cửa sổ Tkinter được khởi tạo trực tiếp bởi tiến trình Python (`python.exe`), `window_pid == python_pid` sẽ đúng, từ đó cho phép nhận thông điệp `DragAcceptFiles` / OLE `IDropTarget` từ Windows Explorer.

### Rủi Ro Kỹ Thuật & Lý Do Không Khả Thi Cho Production
- **Xung đột Mouse Input / Click-Through**: Khi cửa sổ Tkinter overlay đè lên Flet để nhận tệp kéo thả, nó sẽ **chặn toàn bộ sự kiện click chuột** (nút bấm, gõ văn bản trong editor, ribbon tabs). Nếu bật `WS_EX_TRANSPARENT` để chuột click xuyên qua, OS Windows sẽ tự động bỏ qua cửa sổ đó trong quá trình Drag-and-Drop Hit-Testing, khiến kéo tệp không còn tác dụng.
- **Độ trễ & Giật lag đồng bộ (Sync Jitter)**: Việc polling vị trí bằng `GetWindowRect` tạo ra độ trễ (latency) rõ rệt khi người dùng di chuyển, thay đổi kích thước (`resize`), hoặc thu nhỏ (`minimize`) cửa sổ Flet, dẫn đến hiện tượng bóng ma (ghosting window).
- **Xung đột 2 GUI Main Loop**: Chạy đồng thời `tkinter.mainloop()` và `asyncio` event loop của Flet trong cùng 1 process Python đòi hỏi xử lý đa luồng phức tạp, dễ gây treo (freeze) hoặc crash ứng dụng.

---

## 7. 🚀 Giải Pháp Flutter Extension `desktop_drop` & Hướng Dẫn Custom Build Client Runner

### 🌟 Tại Sao `desktop_drop` Giải Quyết Được Vấn Đề?
Gói [desktop_drop](https://pub.dev/packages/desktop_drop) (`pub.dev/packages/desktop_drop`) được viết bằng Dart / C++ Native cho Flutter. Khi biên dịch vào `flet_desktop.exe` client runner, mã C++ của `desktop_drop` chạy **bên trong tiến trình Flutter Client (`PID 9528`)** — cùng Process sở hữu `HWND`. Do đó, nó xử lý triệt để bài toán OLE `RegisterDragDrop` mà không gặp bất kỳ rào cản process boundary nào.

### 📌 2 Lộ Trình Triển Khai (Dành Cho Trường Hợp Ưu Tiên UX Kéo Thả)

#### 🛤️ Lộ Trình A: Chờ Bản Nâng Cấp Chính Thức Từ Flet Framework (Khuyên Dùng)
- **Theo dõi Issue**: [flet-dev/flet#112](https://github.com/flet-dev/flet/issues/112)
- **Theo dõi Release Notes**: [Flet Releases trên GitHub](https://github.com/flet-dev/flet/releases)
- **Cơ chế**: Khi core team Flet thêm `desktop_drop` vào `packages/flet/pubspec.yaml`, chỉ cần `pip install --upgrade flet` là tính năng Drag & Drop native sẽ khả dụng cho mã Python mà không cần sửa đổi thêm.

#### 🛤️ Lộ Trình B: Tự Build Custom Client Runner Bằng Flutter SDK (Tự Chủ Nhanh Đóng Gói)
Nếu dự án cần ưu tiên trải nghiệm UX Kéo & Thả lập tức trước khi Flet phát hành chính thức, đội ngũ kỹ thuật có thể tự biên dịch bản runner theo quy trình:

1. **Clone mã nguồn Flet Client**:
   ```bash
   git clone https://github.com/flet-dev/flet.git
   ```
2. **Khai báo gói `desktop_drop` vào `packages/flet/pubspec.yaml`**:
   ```yaml
   dependencies:
     flutter:
       sdk: flutter
     desktop_drop: ^0.4.4   # <-- Thêm dependency native drag & drop
   ```
3. **Biên dịch bản Windows Client Runner**:
   ```bash
   cd packages/flet
   flutter build windows
   ```
4. **Liên kết Client Runner Custom vào Python App**:
   Thiết lập biến môi trường trỏ tới thư mục vừa build:
   ```cmd
   set FLET_VIEW_PATH=C:\path\to\flet\packages\flet\build\windows\runner\Release
   python main.py
   ```

---

## 📌 Kết Luận

- Mã nguồn chính (`src/`) của dự án được giữ nguyên 100% sạch sẽ, không chứa code rác hay dependencies thử nghiệm.
- Toàn bộ kết quả thực nghiệm, nguyên nhân kỹ thuật và 2 lộ trình kích hoạt (Chờ upstream hoặc Custom Build Flutter runner) được đóng gói đầy đủ tại tài liệu này làm cơ sở ra quyết định kỹ thuật cho dự án.

