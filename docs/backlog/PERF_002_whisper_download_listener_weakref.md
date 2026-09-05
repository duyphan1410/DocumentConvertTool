# PERF-002: Transient Orphaned Listener Closures during Active Model Downloads

**Task ID**: `PERF-002`  
**Phân loại**: Memory Optimization / Technical Debt  
**Độ ưu tiên**: Low  
**Trạng thái**: 🟡 Backlog / Known-Issue  

---

## 1. Hiện trạng & Phân tích cơ chế (Problem Statement)

Trong `src/ui_flet/components/model_hub_dialog.py` và `src/services/model_manager.py`:
- Khi một model đang được tải xuống từ Hugging Face (`is_model_downloading(model_id) == True`), hàm `build_model_card()` đăng ký một callback `live_listener` vào danh sách toàn cục `_PROGRESS_LISTENERS[model_id]`.
- Callback `live_listener` đóng gói (closure) các biến `card_pbar`, `card_status` và `page`.
- Nếu người dùng chuyển qua lại các tab hoặc kích hoạt `render_cards()` nhiều lần trong khi 1 model đang tải dở, hàm `build_model_card()` sẽ tạo ra các control mới và tiếp tục gọi `add_download_listener()`.

### Minh họa trực quan kịch bản (Scenario Walkthrough):
1. **Lần mở 1**: Người dùng mở Model Hub $\rightarrow$ Tạo ra thanh tiến trình **ProgressBar A**. Hàm tải ghi nhớ: *"Mỗi khi tải được 1%, hãy cập nhật cho ProgressBar A"*.
2. **Đóng rồi mở lại lần 2** (trong lúc model vẫn đang tải dở): Tạo ra thanh tiến trình mới **ProgressBar B**. Hàm tải ghi nhớ: *"Mỗi khi tải được 1%, hãy cập nhật cho cả ProgressBar A và ProgressBar B"*.
3. **Mở lại N lần**: Danh sách `_PROGRESS_LISTENERS[model_id]` giữ $N$ listeners. Các thanh tiến trình cũ (A -> N-1) tuy đã biến mất khỏi giao diện nhưng closure vẫn nằm trong RAM tạm thời.

---

## 2. Đánh giá tác động thực tế & Cơ chế an toàn hiện có

> [!NOTE]
> **Trải nghiệm thực tế hoàn toàn ổn định**: Người dùng cuối không bao giờ nhìn thấy lỗi, giật lag hay crash ứng dụng vì các lý do sau:
> 1. **Cơ chế thu hồi tự động**: Trong khối `finally` của `download_model()` và `cancel_model_download()`, dòng `_PROGRESS_LISTENERS.pop(model_id, None)` giải phóng sạch sẽ 100% các listener mồ côi này ngay khi lượt tải kết thúc (thành công, thất bại hoặc hủy).
> 2. **Cơ chế bảo vệ Exception**: Trong hàm phát tín hiệu `_notify_progress()`, các lời gọi listener cũ bị unmount đều được bọc trong `try...except Exception: pass`, không gây ảnh hưởng đến tiến trình UI chính.
> 3. **Mức tiêu hao tài nguyên**: Tác động chỉ dừng ở mức tiêu tốn thêm **vài Kilobyte RAM** trong đúng khoảng thời gian tải model (10 - 30 giây), sau đó bộ nhớ được giải phóng hoàn toàn.

---

## 3. Thiết kế giải pháp dài hạn (Proposed Architecture)

Khi mở rộng hệ thống tải đa model song song hoặc hỗ trợ tác vụ tải ngầm nền (background multi-worker queue), có thể áp dụng 1 trong 2 giải pháp:

### Giải pháp A: Sử dụng WeakRef Registry (Khuyên dùng)
Chuyển `_PROGRESS_LISTENERS` sang lưu trữ dạng `weakref.ref` hoặc `weakref.WeakMethod`.

> [!WARNING]
> **Lưu ý bắt buộc về Strong Reference**: `live_listener` là một closure được định nghĩa cục bộ bên trong `build_model_card()`. Nếu chỉ lưu `weakref.ref(live_listener)` vào `_PROGRESS_LISTENERS` mà không có nơi nào khác giữ **Strong Reference** tới nó, closure sẽ bị Python Garbage Collector thu hồi ngay khi hàm `build_model_card()` kết thúc $\rightarrow$ Weakref chết sớm và thanh tiến trình sẽ **hoàn toàn không cập nhật**.
> 
> **Cách xử lý đúng**: Lưu thêm 1 strong reference vào `card_refs[model_id]["listener"] = live_listener` (dict này đã có sẵn trong view). Khi `render_cards()` chạy lại, card mới tự động ghi đè key này, giúp strong ref cũ tự động mất đi và weakref tự động dọn dẹp theo đúng ý đồ.

```python
import weakref

# Lưu trữ weakref thay vì strong reference
_PROGRESS_LISTENERS: dict[str, list[weakref.ref]] = {}

def _notify_progress(model_id: str, pct: float, msg: str):
    active_refs = []
    for wr in _PROGRESS_LISTENERS.get(model_id, []):
        cb = wr()
        if cb is not None:
            active_refs.append(wr)
            try:
                cb(pct, msg)
            except Exception:
                pass
    _PROGRESS_LISTENERS[model_id] = active_refs
```
- Khi Flet/Flutter hủy control hoặc `card_refs` ghi đè listener mới, tham chiếu yếu tự động trở thành `None`, hàm dispatch tự động loại bỏ khỏi danh sách mà không cần gọi `remove_download_listener` thủ công.

### Giải pháp B: Local State Unbind Tracking
Lưu reference của `live_listener` vào `card_refs[meta.model_id]["listener"]`. Trong mỗi lần `build_model_card()`, kiểm tra và gọi `remove_download_listener()` trước khi gán listener mới.

---

## 4. Tiêu chí nghiệm thu (Acceptance Criteria)
- [ ] Số lượng phần tử trong `_PROGRESS_LISTENERS[model_id]` luôn $\le 1$ cho mỗi view active bất kể số lần gọi `render_cards()`.
- [ ] Khi đóng Modal/SettingsView trong lúc tải, các UI controls cũ được Garbage Collector thu hồi ngay lập tức mà không cần đợi lượt tải hoàn tất.
