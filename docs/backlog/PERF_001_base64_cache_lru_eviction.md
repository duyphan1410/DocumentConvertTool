# [Backlog & RFC] Bounded LRU Cache & Session Eviction for Preview Base64 Images

**Mã định danh**: `PERF-001`  
**Ngày khởi tạo**: 29/08/2026  
**Nhánh dự kiến thực hiện**: `feat/duy-01092026-base64-cache-lru-eviction`  
**Phân loại**: Performance / Memory Management  
**Mức độ ưu tiên**: Medium (Technical Debt & Long-running Stability)  
**Trạng thái**: 🟢 Completed (v1.8.3)  

---

## 1. Hiện trạng & Phân tích nguyên nhân gốc (Problem Statement)

Tại file `src/ui_flet/views/preview_view.py` (dòng 25):
```python
_BASE64_CACHE: dict[str, str] = {}
```

### So sánh với các cơ chế Cache khác trong hệ thống:
1. **`_MERMAID_CACHE`**: Sử dụng `collections.OrderedDict` kết hợp `MAX_MERMAID_CACHE_SIZE = 128` và `threading.Lock` để tự động đẩy phần tử cũ ra ngoài theo chính sách LRU (Least Recently Used).
2. **`_BASE64_CACHE`**: Là một `dict` Python thông thường, **không có chặn trần số lượng phần tử (Unbounded)**, không có cơ chế dọn dẹp và không được giải phóng theo vòng đời của tài liệu.

### Rủi ro rò rỉ bộ nhớ (Memory Leak Profile):
- **Tích lũy vô tận**: Khi người dùng làm việc lâu dài (mở nhiều tài liệu Word, PPTX, PDF có hàng trăm hình ảnh), mỗi ảnh sau khi nén vẫn chiếm khoảng 35 KB - 50 KB bộ nhớ RAM dưới dạng Base64 string. 1,000 ảnh duyệt qua = ~50 MB RAM bị giữ vĩnh viễn.
- **Dead Memory Reference sau khi đóng Tab**: Khi người dùng đóng một tab (`close_tab()`), thư mục ảnh tạm trên ổ cứng (`cache/preview_media/session_tab_xxx/`) đã bị `MediaAssetManager.cleanup_session()` xóa bỏ hoàn toàn, nhưng đường dẫn file và dữ liệu Base64 tương ứng vẫn **tồn tại vĩnh viễn trong RAM của `_BASE64_CACHE`**.

---

## 2. Thiết kế giải pháp kỹ thuật (Architecture & RFC-001 Refinement)

### 2.1. Cấu trúc Cache Key chuẩn hóa (Tuple Key)
Tránh hoàn toàn lỗi substring matching và hiển thị sai kích thước:
```python
# Tuple[str, str, int, int]
# (session_id or "", file_path, effective_width, quality)
```
- **Xóa chính xác theo Session**: `keys_to_delete = [k for k in _BASE64_CACHE if k[0] == session_id]`. Khi purge `tab_1`, chỉ xóa đúng `tab_1`, không ảnh hưởng `tab_10` hay `tab_11`.
- **Phân biệt kích thước & chất lượng**: `effective_width = target_width if target_width is not None else max_width`. Đảm bảo thumbnail (400px) và modal xem lớn (1200px) có key cache riêng biệt.
- **Auto-detect Session ID**: Dùng `pathlib.Path(file_path).parts` kết hợp hằng số `PREVIEW_MEDIA_DIR_NAME = "preview_media"` để trích xuất `session_id` an toàn độc lập OS (`\\` vs `/`).

### 2.2. Khắc phục Circular Dependency (Observer / Cleanup Hook Pattern)
Để bảo toàn kiến trúc 3-Tier (Service layer không import ngược UI layer):
1. `MediaAssetManager` (Service Layer) cung cấp phương thức `register_cleanup_hook(cls, hook)` và lưu danh sách `_cleanup_hooks`.
2. Khi `MediaAssetManager.clear_session(session_id)` chạy, nó kích hoạt toàn bộ các registered cleanup hooks đã đăng ký.
3. `preview_view.py` (UI Layer) chỉ đăng ký hàm `purge_session_base64_cache`:
   ```python
   MediaAssetManager.register_cleanup_hook(purge_session_base64_cache)
   ```

### 2.3. Bounded LRU Cache & Thread Safety
```python
MAX_BASE64_CACHE_ENTRIES = 128
_BASE64_CACHE: collections.OrderedDict[tuple[str, str, int, int], str] = collections.OrderedDict()
_BASE64_CACHE_LOCK = threading.Lock()
```
- Tra cứu & Cập nhật LRU (`move_to_end`, `popitem(last=False)`) an toàn trong single lock block.
- Nén ảnh Pillow thực hiện ngoài lock để tối ưu đa luồng.

---

## 3. Tiêu chí nghiệm thu (Acceptance Criteria)

- [ ] `_BASE64_CACHE` không bao giờ vượt quá `MAX_BASE64_CACHE_ENTRIES` (128 mục).
- [ ] Khi đóng một tab chứa ảnh, toàn bộ entry trong RAM tương ứng với `session_id` đó được giải phóng 100% qua observer hook.
- [ ] Purge `tab_1` không xóa nhầm `tab_10` hoặc `tab_11`.
- [ ] Thumbnail và ảnh phóng to của cùng 1 file không bị ghi đè hay trả về nhầm độ phân giải.
- [ ] Không có circular dependency giữa Service và UI layers.
- [ ] Thread-safe: 100% pass với concurrency tests.

