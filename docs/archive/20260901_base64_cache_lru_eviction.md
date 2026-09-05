# Bounded LRU Base64 Cache, Observer Session Eviction & Memory Architecture (v1.8.3)

**Phiên bản**: `v1.8.3`  
**Ngày hoàn thành**: 01/09/2026  
**Nhánh thực hiện**: `feat/duy-01092026-base64-cache-lru-eviction`  
**Mã nhiệm vụ**: `PERF-001`  

---

## 1. Bối cảnh & Vấn đề (Problem Statement)

Trong các phiên bản trước (`v1.8.0` – `v1.8.2`), Live Preview mã hóa Base64 ảnh Markdown sử dụng một từ điển toàn cục:
```python
_BASE64_CACHE: dict[str, str] = {}
```

### Rủi ro vận hành tích lũy:
1. **Rò rỉ bộ nhớ vô tận (Unbounded Memory Retention)**: Không có trần dung lượng cache. Khi làm việc với nhiều tài liệu chứa hàng trăm ảnh, mỗi ảnh nén giữ 35–50 KB Base64 trong RAM khiến app phình bộ nhớ liên tục.
2. **Dead Memory Reference sau khi đóng Tab**: Khi người dùng đóng tab, thư mục ảnh tạm trên đĩa (`cache/preview_media/session_tab_xxx/`) bị xóa nhưng dữ liệu Base64 trong RAM của session đó không bao giờ được thu hồi.
3. **Nguy cơ va chạm tham số & phụ thuộc kiến trúc**: Cần cơ chế khóa cache theo namespace session và thông số nén tách bạch, đồng thời giải phóng bộ nhớ sạch sẽ mà không tạo vòng lặp phụ thuộc (circular dependency) giữa tầng Service và UI.

---

## 2. Giải pháp Kiến trúc & Kỹ thuật đã triển khai

### 2.1. Cấu trúc Cache Key chuẩn hóa (Tuple Key)
Chuyển đổi khóa cache sang tuple 4 phần tử có kiểu dữ liệu mạnh:
```python
CacheKey = tuple[str, str, int, int]
# (session_id or "", file_path, effective_width, quality)
```
- **Tách biệt kích thước & chất lượng**: `effective_width = target_width if target_width is not None else max_width` và `quality` được lưu độc lập, đảm bảo ảnh thumbnail và ảnh phóng to không bị trả nhầm cache.
- **Xóa chính xác theo Session**: Khi đóng tab, chỉ cần so khớp `k[0] == session_id`, loại bỏ 100% rủi ro xóa nhầm giữa các tab có ID tương đồng (`tab_1` vs `tab_10`).

### 2.2. Nhận diện Session ID an toàn trên mọi hệ điều hành (OS-Agnostic)
- **Vị trí**: `src/ui_flet/views/preview_view.py` (`_resolve_session_id_from_path`)
- Sử dụng `pathlib.Path(file_path).parts` kết hợp hằng số `PREVIEW_MEDIA_DIR_NAME = "preview_media"` để trích xuất `session_id` độc lập với dấu phân cách thư mục trên Windows (`\`) và POSIX (`/`).

### 2.3. Triệt tiêu Circular Dependency bằng Observer Hook Pattern
- **Vị trí**: `src/services/media_asset_manager.py`, `src/ui_flet/views/preview_view.py`
- **Cơ chế**:
  - `MediaAssetManager` (Service Layer) khai báo danh sách `_cleanup_hooks` và phương thức `@classmethod register_cleanup_hook(hook)`.
  - Service Layer **hoàn toàn không import UI Layer**, bảo toàn nguyên tắc kiến trúc 3-Tier.
  - Khi `MediaAssetManager.clear_session(session_id)` được kích hoạt khi đóng tab, nó tự động lặp qua các hook đăng ký và gọi hàm trong khối `try/except` bảo vệ (kèm log `[WARNING]` và `log_error` nếu có ngoại lệ).
  - `preview_view.py` (UI Layer) đăng ký hook `purge_session_base64_cache` ở cấp độ module ngay khi nạp.

### 2.4. Bounded LRU Cache & Tối ưu hóa Đa luồng (Thread-Safe Concurrency)
- `collections.OrderedDict` với trần `MAX_BASE64_CACHE_ENTRIES = 128`.
- Khóa `_BASE64_CACHE_LOCK = threading.Lock()` bảo vệ mọi thao tác đọc, ghi, cập nhật LRU và dọn dẹp cache.
- **Tối ưu throughput**: Thao tác nén ảnh Pillow được thực hiện **bên ngoài lock**, chỉ các bước tra cứu cache và cập nhật dict mới giữ lock.
- Hàm `purge_session_base64_cache` gom thao tác lọc danh sách và xóa phần tử trong **duy nhất 1 lock block** nguyên tử.

---

## 3. Kiểm thử & Nghiệm thu (Verification & Test Suite)

Tạo mới bộ test chuyên biệt `tests/test_preview_base64_cache.py` với 6 bài test đạt 100% Pass:

1. `test_auto_detect_session_id_windows_and_posix`: Xác minh trích xuất `session_id` chính xác với đường dẫn Windows (`\`) và Linux (`/`).
2. `test_exact_session_purge`: Xác minh xóa `tab_1` không làm mất cache của `tab_10` hoặc `tab_11`.
3. `test_parameter_differentiation`: Xác minh `(width, quality)` khác nhau tạo key riêng biệt.
4. `test_lru_bounded_eviction`: Nạp 150 items, xác minh cache luôn `<= 128` mục và đẩy item cũ nhất ra ngoài.
5. `test_observer_cleanup_hook_integration`: Xác minh `clear_session` kích hoạt purge hook và hệ thống vẫn chạy ổn định dù có hook ném ngoại lệ.
6. `test_concurrency_thread_safety`: 8 luồng chạy đồng thời đọc/ghi/purge cache an toàn tuyệt đối.

---

## 4. Danh sách tệp thay đổi

| Tệp | Thay đổi chính |
| :--- | :--- |
| `src/__version__.py` | Cập nhật phiên bản lên `1.8.3`. |
| `src/services/media_asset_manager.py` | Thêm hằng số `PREVIEW_MEDIA_DIR_NAME`, `_cleanup_hooks`, `register_cleanup_hook()`, kích hoạt hook trong `clear_session()`. |
| `src/ui_flet/views/preview_view.py` | Triển khai `_BASE64_CACHE` dạng `OrderedDict` 128 mục, Tuple key, `_resolve_session_id_from_path()`, `purge_session_base64_cache()`, `clear_base64_cache()`, đăng ký hook. |
| `tests/test_preview_base64_cache.py` | Bộ unit test toàn diện cho LRU cache và session eviction. |
| `docs/backlog/PERF_001_base64_cache_lru_eviction.md` | Cập nhật thiết kế chi tiết RFC và đánh dấu trạng thái `Completed`. |
| `docs/backlog/README.md` | Cập nhật trạng thái `PERF-001` thành `🟢 Completed (v1.8.3)`. |
| `docs/roadmaps/product_roadmap.md` | Đánh dấu hoàn thành `PERF-001` trong mục release `v1.8.3`. |
| `docs/archive/20260901_base64_cache_lru_eviction.md` | Tài liệu lưu trữ chi tiết kỹ thuật v1.8.3. |
