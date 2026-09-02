# [Backlog & Bug] Preview Scroll Jump khi Tương Tác với Ảnh trong Live Preview

**Mã định danh**: `BUG-001`  
**Ngày khởi tạo**: 01/09/2026  
**Nhánh dự kiến thực hiện**: `fix/duy-01092026-preview-scroll-jump`  
**Phân loại**: Bug / UX Regression  
**Mức độ ưu tiên**: High (ảnh hưởng trực tiếp đến trải nghiệm chỉnh sửa ảnh)  
**Trạng thái**: 🟡 In Progress (đang xác nhận fix cuối)

---

## 1. Hiện trạng & Phân tích nguyên nhân gốc (Problem Statement)

Khi người dùng **click vào một ảnh gần cuối trang** trong panel Live Preview, hoặc **áp dụng thay đổi kích cỡ** (ví dụ: 25%, 50%) thông qua context menu, toàn bộ scroll position của preview bị reset về đầu trang ngay lập tức.

### Hai nguyên nhân gốc được xác định qua debug (traceback):

#### Nguyên nhân 1 — Click ảnh trong Preview (không rebuild set_content)
Chuỗi gọi hàm:
```
_handle_image_tap_down
  → _handle_preview_image_clicked (app.py)
      ├─ editor.selection = ft.TextSelection(...)   ← BUG: Flutter focus → auto-scroll
      ├─ editor.update()                            ← BUG: flush dirty controls
      └─ _render_menu → page.update()
```

#### Nguyên nhân 2 — Apply size change (resize 25%, 50%...)
Chuỗi gọi hàm (xác nhận qua traceback.print_stack):
```
replace_image_token (editor_view.py:416)
  → on_editor_changed → update_preview → set_content
  → _render_processed_content() ← tạo lại toàn bộ scroll_column.controls
  → scroll_column.update()      ← Flutter rebuild → scroll reset về 0
```

---

## 2. Thiết kế giải pháp kỹ thuật (Architecture & Proposed Fix)

### 2.1. Fix Nguyên nhân 1 — Xóa editor.selection và editor.update() (app.py)

Chỉ cập nhật biến tracking nội bộ Python, không động đến Flutter widget:
- Xóa `editor.selection = ft.TextSelection(...)`
- Xóa `editor.update()`
- Gọi `preview.restore_scroll()` sau `_show_image_context_menu_at()`

### 2.2. Fix Nguyên nhân 2 — Scroll Position Save/Restore (preview_view.py)

Cơ chế theo dõi liên tục qua `on_scroll` callback, khôi phục sau rebuild.

> **Lưu ý quan trọng**: `restore_scroll()` phải là lệnh CUỐI CÙNG sau `scroll_column.update()` và `self.update()`. Gọi trước sẽ bị ghi đè.

> **Lưu ý kỹ thuật**: `scroll_to` là async coroutine trong Flet, phải dùng `loop.create_task()` thay vì gọi trực tiếp (gây `RuntimeWarning: coroutine was never awaited`).

### 2.3. File ảnh hưởng

| File | Thay đổi |
|------|----------|
| `src/ui_flet/app.py` | Xóa editor.selection + editor.update() trong _handle_preview_image_clicked; thêm restore_scroll() |
| `src/ui_flet/views/preview_view.py` | Thêm _saved_scroll_offset, on_scroll handler, restore_scroll; gọi đúng thứ tự |

---

## 3. Kế hoạch triển khai & Trạng thái từng bước

| # | Bước | Status |
|---|------|--------|
| 1 | Xóa `editor.selection` + `editor.update()` khỏi `_handle_preview_image_clicked` | ✅ Done |
| 2 | Thêm `on_scroll` tracking vào `scroll_column` | ✅ Done |
| 3 | Implement `_on_scroll_changed`, `restore_scroll` | ✅ Done |
| 4 | Gọi `restore_scroll()` sau `set_content` và `set_processed_content` rebuild | ✅ Done |
| 5 | Fix thứ tự: `restore_scroll()` sau tất cả `update()` | ✅ Done |
| 6 | Fix `scroll_to` là async coroutine → dùng `loop.create_task()` | ✅ Done |
| 7 | Xác nhận từ user: scroll giữ nguyên khi click & resize ảnh | 🟡 Chờ xác nhận |

---

## 4. Tiêu chí nghiệm thu (Acceptance Criteria)

- [ ] Click vào ảnh ở bất kỳ vị trí nào trong Preview (kể cả gần cuối trang), scroll position KHÔNG bị thay đổi.
- [ ] Context menu xuất hiện gần vị trí click, không gây cuộn preview.
- [ ] Áp dụng size preset (25%, 50%, 75%, 100%) cho ảnh, scroll position KHÔNG bị reset về đầu trang.
- [ ] Thay đổi alignment (Left/Center/Right), scroll position giữ nguyên.
- [ ] Không có `RuntimeWarning: coroutine was never awaited` trong console.
- [ ] Chức năng thêm/chỉnh sửa ảnh (insert, replace, reset) vẫn hoạt động đúng sau fix.
