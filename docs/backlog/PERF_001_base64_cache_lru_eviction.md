# [Backlog & RFC] Bounded LRU Cache & Session Eviction for Preview Base64 Images

**Mã định danh**: `PERF-001`  
**Ngày khởi tạo**: 29/08/2026  
**Nhánh dự kiến thực hiện**: `feat/duy-DDMMYYYY-base64-cache-lru-eviction`  
**Phân loại**: Performance / Memory Management  
**Mức độ ưu tiên**: Medium (Technical Debt & Long-running Stability)  
**Trạng thái**: 🟡 Pending  

---

## 1. Hiện trạng & Phân tích nguyên nhân gốc (Problem Statement)

Tại file `src/ui_flet/views/preview_view.py` (dòng 23):
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

## 2. Thiết kế giải pháp kỹ thuật (Proposed Architecture)

### 2.1. Thành phần 1: Bounded LRU Cache (Giới hạn dung lượng tối đa)
Chuyển đổi `_BASE64_CACHE` sang `collections.OrderedDict` thread-safe:

```python
import collections
import threading

MAX_BASE64_CACHE_ENTRIES = 128
_BASE64_CACHE: collections.OrderedDict[str, str] = collections.OrderedDict()
_BASE64_CACHE_LOCK = threading.Lock()

def image_to_base64_uri(file_path: str, max_width: int = 650, quality: int = 70) -> str:
    with _BASE64_CACHE_LOCK:
        if file_path in _BASE64_CACHE:
            _BASE64_CACHE.move_to_end(file_path)
            return _BASE64_CACHE[file_path]

    # ... [Nén ảnh bằng Pillow] ...

    with _BASE64_CACHE_LOCK:
        _BASE64_CACHE[file_path] = uri
        _BASE64_CACHE.move_to_end(file_path)
        while len(_BASE64_CACHE) > MAX_BASE64_CACHE_ENTRIES:
            _BASE64_CACHE.popitem(last=False)  # Xóa phần tử ít dùng nhất (LRU)
    return uri
```

### 2.2. Thành phần 2: Scoped Session Purge Hook (Dọn dẹp theo Tab Session)
Cung cấp hàm xóa triệt để cache của một session khi tab bị đóng:

```python
def purge_session_base64_cache(session_id: str):
    """Xóa tất cả các entry Base64 thuộc session_id chỉ định khi đóng tab."""
    if not session_id:
        return
    with _BASE64_CACHE_LOCK:
        keys_to_delete = [k for k in _BASE64_CACHE if session_id in k]
        for k in keys_to_delete:
            _BASE64_CACHE.pop(k, None)
```

Liên kết hàm này với `MediaAssetManager.cleanup_session(session_id)` và `FileController.close_tab(tab_id)`.

---

## 3. Kế hoạch triển khai & Các file ảnh hưởng

1. **`src/ui_flet/views/preview_view.py`**:
   - Thay `_BASE64_CACHE` bằng `OrderedDict` + `_BASE64_CACHE_LOCK`.
   - Cập nhật `image_to_base64_uri()` và bổ sung `purge_session_base64_cache()`.
2. **`src/services/media_asset_manager.py`**:
   - Gọi `purge_session_base64_cache(session_id)` trong `cleanup_session()`.
3. **`tests/test_preview_view.py`** (hoặc bài test mới):
   - Viết unit test kiểm tra:
     - Cache không vượt quá 128 phần tử khi nạp 200 ảnh ảo.
     - Kiểm tra `purge_session_base64_cache()` xóa đúng các key liên quan khi đóng tab.

---

## 4. Tiêu chí nghiệm thu (Acceptance Criteria)

- [ ] `_BASE64_CACHE` không bao giờ vượt quá `MAX_BASE64_CACHE_ENTRIES` (128 mục).
- [ ] Khi đóng một tab chứa ảnh, toàn bộ entry trong RAM tương ứng với `session_id` đó được giải phóng 100%.
- [ ] Thread-safe: Không xảy ra `RuntimeError: dictionary changed size during iteration` khi nhiều tác vụ async đọc/ghi cache đồng thời.
- [ ] Toàn bộ 113+ unit test tiếp tục Pass và không ảnh hưởng đến thời gian nạp 0ms của các tab đang mở.
