# New Approaches: Fixing Open File / Open Folder Foreground Issue

**Liên quan đến**: `FOCUS_ZORDER_ANALYSIS.md`
**Vị trí code**: `app.py::_open_converted_file` / `_open_converted_folder` → gọi `src.utils.env.open_file_or_folder_foreground(file_path, is_folder=...)`
**Ngày**: 01/08/2026
****Trạng thái hiện tại**: ✅ **ĐÃ GIẢI QUYẾT (01/08/2026)** — Đã thay thế toàn bộ ALT-key trick + `AttachThreadInput` bằng kiến trúc **3-Layer Fallback** trong `src/utils/env.py::open_file_or_folder_foreground`.

> ✅ **Đã đồng bộ tài liệu**: Bản `FOCUS_ZORDER_ANALYSIS.md` (mục 4.1/4.2) đã được cập nhật chính thức ghi nhận cơ chế Win32 3-Layer Fallback (SPI Lock Bypass + Topmost Z-Order Toggle + FlashWindowEx) làm tiêu chuẩn sản xuất cho DocumentConvertTool.

---

## 1. Vấn đề hiện tại (nhắc lại)

Sau khi convert xong, bấm **Open File**/**Open Folder** → `open_file_or_folder_foreground()` gọi `os.startfile()` rồi cố ép foreground bằng ALT-key trick. Kết quả:
- Cửa sổ Word/Excel/Explorer mới **không** lên trước — vẫn nằm sau DCT (Z-Index #2).
- Chỉ thấy nhấp nháy vàng ở taskbar.
- Nếu DCT không maximize (~80% size), thấy rõ cửa sổ mới nằm phía sau, không được kích hoạt.

**Root cause**: ALT-key + `AttachThreadInput` phụ thuộc timing của input queue → dễ bị Windows Foreground Lock chặn ngầm nếu không đồng bộ đúng lúc. Đây không phải cơ chế đáng tin cậy nhất.

---

## 2. Các phương án ĐÃ THỬ và bị loại (không thử lại)

Tổng hợp từ `FOCUS_ZORDER_ANALYSIS.md` mục 4 — áp dụng riêng cho luồng Open File/Open Folder:

| Đã thử | Vì sao fail | Có nên thử lại không? |
|---|---|---|
| `page.window.focused = False` | Đẩy DCT xuống Z-Index #3, phá `Alt+Tab` stack | ❌ Không |
| `subprocess.Popen("explorer /select,...")` | Spawn `explorer.exe` mới mỗi lần → duplicate window | ❌ Không, dùng `os.startfile` |
| `subprocess.Popen("cmd /c start ...")` | Flash cửa sổ đen `cmd.exe` 100–300ms trước khi mở app | ❌ Không |
| `win32gui.SetForegroundWindow(hwnd)` **trần** (không kèm SPI bypass/ALT-key) | Bị Foreground Lock chặn im lặng, taskbar chỉ chớp vàng | ⚠️ Chỉ dùng nếu **kèm** SPI bypass (mục 3, Layer 2) |
| ALT-key trick + `AttachThreadInput` | Phụ thuộc timing input queue, không ổn định | ❌ Không dùng (đã gỡ bỏ khỏi `src/utils/env.py`) |

---

## 3. Các phương án mới được đề xuất và ĐÃ TRIỂN KHAI

| # | Phương án | Cơ chế | Độ tin cậy | Trạng thái |
|---|---|---|---|---|
| 1 | `SystemParametersInfoW(SPI_SETFOREGROUNDLOCKTIMEOUT)` bypass tạm thời | Tắt Foreground Lock policy trong khoảnh khắc gọi `SetForegroundWindow`, sau đó khôi phục lại giá trị cũ | **Cao** — cách các tool (Total Commander, AltTabTerminator) hay dùng, không phụ thuộc timing input queue | ✅ Đã merge vào Layer 2 |
| 2 | `EnumWindows` + filter theo class name (`OpusApp`/`XLMAIN`/`PPTFrameClass`/`CabinetWClass`) | Tìm đúng HWND của app đích thuần túy theo class-name (bỏ qua window title để tránh lệch do ngôn ngữ/Read-Only) + retry loop 2s (20x100ms) | **Cao** | ✅ Đã merge vào Layer 1 |
| 3 | `HWND_TOPMOST` → `HWND_NOTOPMOST` toggle qua `SetWindowPos` | Đổi Z-order thuần túy, **không** cần xin quyền activate như `SetForegroundWindow` nên không bị Foreground Lock chặn | **Cao** cho việc "đưa lên nhìn thấy" | ✅ Đã merge vào Layer 3 (fallback) |
| 4 | `FlashWindowEx` (nháy icon taskbar) | Không ép z-order, chỉ báo hiệu — đúng UX chuẩn Windows dùng cho notification khi bị chặn foreground | N/A (fallback an toàn cuối) | ✅ Đã merge vào Layer 4 (fallback) |
| 5 | Detect target app đang fullscreen | So sánh rect window vs monitor | — | ❌ Chưa cần thiết |

---

## 4. Kiến trúc chính thức đã triển khai: 3-layer fallback

```
os.startfile(path)
      │
      ▼
Layer 1: EnumWindows (Strict Class Name Filter: OpusApp/XLMAIN/PPTFrameClass/CabinetWClass, 2.0s Retry Loop)
      │
      ▼
Layer 2: SPI_SETFOREGROUNDLOCKTIMEOUT Bypass + AllowSetForegroundWindow(-1) + SetForegroundWindow
      │  (nếu thất bại / OS lock chặn)
      ▼
Layer 3: SetWindowPos TOPMOST -> NOTOPMOST toggle (đưa lên top Z-order nhìn thấy)
      │  (nếu vẫn chưa giữ active focus)
      ▼
Layer 4: FlashWindowEx (nháy taskbar — fallback an toàn cuối)
```

---

## 5. Danh mục công việc (Checklist)

- [x] Xem nội dung hiện tại của `src/utils/env.py::open_file_or_folder_foreground` và audit tất cả callers.
- [x] Thay thế ALT-key trick và AttachThreadInput bằng Layer 2 (`SPI_SETFOREGROUNDLOCKTIMEOUT` bypass tạm thời + `SetForegroundWindow`).
- [x] Cập nhật Layer 1 dùng strict class-name filter (bỏ title matching filter, chỉ log debug title) kèm retry loop 2.0s (20x100ms).
- [x] Thêm Layer 3 (`SetWindowPos` TOPMOST/NOTOPMOST toggle) làm fallback Z-order.
- [x] Thêm Layer 4 (`FlashWindowEx`) làm notification fallback an toàn.
- [x] Tối ưu mở folder dùng `os.startfile(folder_dir)` để tái sử dụng cửa sổ Explorer hiện có, tránh duplicate.
- [x] Đồng bộ hoá lại tài liệu `FOCUS_ZORDER_ANALYSIS.md` mục 4.1/4.2.

