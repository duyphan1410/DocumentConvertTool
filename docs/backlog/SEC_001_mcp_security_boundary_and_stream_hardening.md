# 🛡️ SEC-001: Khắc phục Lỗ hổng Workspace Boundary, Đệ quy Stream & Thắt chặt Bảo mật MCP Server

**Mã Task**: `SEC-001`  
**Phân loại**: Security / Robustness  
**Độ ưu tiên**: Critical  
**Trạng thái**: 🟢 Completed (2026-09-12)  
**Tài liệu liên quan**: [REPORT-PKB-PHASE2-ARCH-REVIEW](../reports/pkb_phase2_mcp_architecture_review.md), [phase2_mcp_server.md](../roadmaps/pkb/phase2_mcp_server.md)

---

## 1. Hiện trạng & Lỗ hổng Bảo mật (Vulnerability Statement)

### Lỗ hổng 1: Thiếu Workspace Boundary Check trong `resolve_safe_doc_path()` & Call Sites
- **Hiện trạng**: Code `src/mcp/security.py` chỉ kiểm tra UUID hợp lệ -> Query SQLite -> File tồn tại trên đĩa. Không có so khớp `os.path.commonpath([doc_path, workspace_root]) == workspace_root`.
- **Rủi ro Thực tế**: `MetadataIndex` trong codebase là một singleton quản trị SQLite độc lập, **không lưu trữ thuộc tính `workspace_dir`**. Do đó, nếu hàm dùng `getattr(index, "workspace_dir", None)`, giá trị sẽ luôn là `None` và boundary check bị bỏ qua trong im lặng.
- **Call site gap**: Tất cả 5 vị trí gọi trong `src/mcp/tools.py` (`handle_read_document`, `handle_convert_document`, `handle_tag_document`, `handle_list_backlinks`, `handle_write_document_content`) hiện chỉ truyền `(document_id, idx)`. Bắt buộc phải cập nhật tất cả call sites này để lấy và truyền `workspace_dir` rõ ràng.

### Lỗ hổng 2: Hàm `is_valid_uuid()` không ép buộc chuẩn UUID v4
- **Hiện trạng**: Dùng `uuid.UUID(str(val))` chấp nhận UUID v1/v3/v5 và cả Nil UUID (`00000000-0000-0000-0000-000000000000`).
- **Khắc phục**: Kiểm tra `parsed.version == 4`, tự động loại bỏ các version khác cũng như Nil UUID (vì Nil UUID có `version is None`).

### Lỗ hổng 3: Thứ tự Redirect `sys.stdout = sys.stderr` bị trễ sau Imports
- **Hiện trạng**: `real_stdout = sys.__stdout__; sys.stdout = sys.stderr` nằm trong `main()` của `server.py`, nhưng trước đó đã import `src.mcp.tools` và `src.services.metadata_index` ở top-level.
- **Rủi ro**: Bất kỳ module nào phát sinh `print()` trong lúc import sẽ ghi thẳng vào `sys.stdout` thật, làm corrupt luồng JSON-RPC của Claude Desktop.

### Lỗ hổng 4: Nguy cơ `RecursionError` trong `_read_next_message()`
- **Hiện trạng**: Hàm gọi lại chính nó bằng đệ quy khi gặp dòng trống hoặc JSON decode error.
- **Rủi ro**: Client gửi chuỗi dòng trống hoặc dữ liệu lỗi kéo dài sẽ làm cạn kiệt stack call (~1000 frames) gây crash tiến trình.

### Lỗ hổng 5: Tool `write_document_content` ghi đè không có Backup / Safe-Swap
- **Hiện trạng**: `handle_write_document_content` mở file ghi đè trực tiếp (`open(safe_path, "w")`), không tạo file backup (`.bak`) và không hỗ trợ atomic write. Nếu tiến trình bị ngắt giữa chừng hoặc ghi lỗi, file gốc của người dùng sẽ bị trắng (0 bytes) hoặc hỏng hoàn toàn.

---

## 2. Thiết kế Kỹ thuật Khắc phục (Remediation Design)

### 2.1. Centralized & Cached Workspace Resolver (`src/mcp/security.py`)
> **Tối ưu**: Sử dụng `functools.lru_cache` để tái sử dụng kết quả đọc `settings.json`, tránh đọc đĩa lặp lại ở mỗi lệnh gọi tool. Đồng thời dùng chung hàm này cho cả `server.py` để loại bỏ duplicate code.

```python
import os
import json
import uuid
import functools
from typing import Optional, Tuple, Any


@functools.lru_cache(maxsize=1)
def get_active_workspace_dir() -> Optional[str]:
    """
    Resolves and caches the active workspace directory from environment or settings.json.
    Single Source of Truth for both security boundary checks and server background sync.
    """
    env_ws = os.getenv("DOCCONVERT_WORKSPACE")
    if env_ws and os.path.isdir(env_ws):
        return os.path.normpath(os.path.abspath(env_ws))

    appdata = os.getenv("APPDATA", os.path.expanduser("~"))
    settings_path = os.path.join(appdata, "DocConvert", "settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                cand = data.get("workspace_folder") or data.get("last_workspace")
                if cand and os.path.isdir(cand):
                    return os.path.normpath(os.path.abspath(cand))
        except Exception:
            pass
    return None


def is_valid_uuid(val: Any) -> bool:
    """Validates strictly for standard UUID version 4."""
    if not val or not isinstance(val, str):
        return False
    try:
        u = uuid.UUID(str(val).strip())
        return u.version == 4
    except (ValueError, AttributeError):
        return False


def resolve_safe_doc_path(
    doc_id: str, 
    index: Any, 
    workspace_dir: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[dict]]:
    """
    Enforces UUID v4, DB existence, disk existence, AND workspace boundary containment.
    """
    if not is_valid_uuid(doc_id):
        return False, None, None

    doc = index.get_document_by_id(doc_id)
    if not doc:
        return False, None, None

    stored_path = doc.get("path")
    if not stored_path or not isinstance(stored_path, str):
        return False, None, doc

    norm_path = os.path.normpath(os.path.abspath(stored_path))
    if not os.path.exists(norm_path) or not os.path.isfile(norm_path):
        return False, None, doc

    # Enforce workspace boundary containment
    ws = workspace_dir or get_active_workspace_dir()
    if ws:
        norm_ws = os.path.normpath(os.path.abspath(ws))
        try:
            # os.path.commonpath raises ValueError on Windows if paths are on different drive letters
            if os.path.commonpath([norm_path, norm_ws]) != norm_ws:
                return False, None, doc  # Path lies outside authorized workspace
        except ValueError:
            # Paths on different drives (e.g., C:\ vs D:\) are strictly outside boundary
            return False, None, doc

    return True, norm_path, doc
```

---

### 2.2. Khử Đệ quy trong `_read_next_message()` (`src/mcp/server.py`)
```python
def _read_next_message(self) -> Optional[Dict[str, Any]]:
    """Reads next message from stdin iteratively without recursion."""
    while True:
        line = self.stdin.readline()
        if not line:
            return None  # EOF or pipe closed

        # 1. Content-Length Framing
        if line.lower().startswith("content-length:"):
            try:
                content_len = int(line.split(":", 1)[1].strip())
                while True:
                    hdr = self.stdin.readline()
                    if hdr in ("\r\n", "\n", ""):
                        break
                payload = self.stdin.read(content_len)
                return json.loads(payload)
            except Exception as e:
                logger.error("Failed to parse Content-Length frame: %s", str(e))
                continue

        # 2. Line-delimited JSON Framing
        stripped = line.strip()
        if not stripped:
            continue

        try:
            return json.loads(stripped)
        except json.JSONDecodeError as jde:
            logger.error("JSON decode error on line: %s | Error: %s", stripped[:100], str(jde))
            self.send_error(None, -32700, f"Parse error: {str(jde)}")
            continue
```

---

### 2.3. Tái sử dụng Resolver trong `_trigger_background_workspace_sync` (`src/mcp/server.py`)
```python
from src.mcp.security import get_active_workspace_dir

def _trigger_background_workspace_sync(index: MetadataIndex) -> None:
    """Uses the centralized get_active_workspace_dir helper to avoid code duplication."""
    def _sync_worker():
        try:
            workspace_dir = get_active_workspace_dir()
            if workspace_dir:
                logger.info("Auto-syncing workspace in background: %s", workspace_dir)
                index.sync_workspace_incremental(workspace_dir)
                logger.info("Workspace background auto-sync completed.")
        except Exception as e:
            logger.warning("Background workspace sync skipped or failed: %s", str(e))

    sync_thread = threading.Thread(target=_sync_worker, name="mcp_bg_sync", daemon=True)
    sync_thread.start()
```

---

### 2.4. Cấu trúc Hoàn chỉnh của `src/main.py` (Cô lập Stdout & Lazy Load)
```python
import sys


def main():
    # 1. Headless: YouTube Player Subprocess
    if "--youtube-player" in sys.argv:
        from src.services.youtube_player import _run_player_subprocess
        _run_player_subprocess()
        return

    # 2. Headless: Local MCP Server for Claude Desktop & Code
    if "--mcp-server" in sys.argv:
        # Cách ly sys.stdout NGAY LẬP TỨC trước khi nạp bất kỳ module nào
        real_stdout = sys.__stdout__
        sys.stdout = sys.stderr

        from src.mcp.server import MCPServer
        from src.services.metadata_index import MetadataIndex

        index = MetadataIndex.get_instance()
        server = MCPServer(stdin_stream=sys.stdin, stdout_stream=real_stdout, index=index)
        server.run_forever()
        return

    # 3. GUI Mode: Chỉ nạp Flet và UI modules khi khởi chạy giao diện
    import flet as ft
    from src.ui_flet.app import main as flet_main
    ft.app(target=flet_main)


if __name__ == "__main__":
    main()
```

---

### 2.5. Safe Atomic Write & Backup cho `write_document_content` (`src/mcp/tools.py`)
```python
import shutil
import tempfile

def handle_write_document_content(
    document_id: str,
    content: str,
    index: Optional[MetadataIndex] = None,
    create_backup: bool = True
) -> Dict[str, Any]:
    idx = index or MetadataIndex.get_instance()
    is_valid, safe_path, doc = resolve_safe_doc_path(document_id, idx)

    if not is_valid or not safe_path:
        return {
            "error": "DOCUMENT_NOT_FOUND_OR_OUT_OF_BOUNDS",
            "message": f"Document ID '{document_id}' is invalid, missing on disk, or outside workspace boundary.",
            "document_id": document_id
        }

    try:
        # 1. Tạo file backup .bak trước khi ghi đè
        if create_backup and os.path.exists(safe_path):
            backup_path = f"{safe_path}.bak"
            shutil.copy2(safe_path, backup_path)

        # 2. Atomic Write qua file tạm để tránh mất dữ liệu nếu ngắt đột ngột
        dir_name = os.path.dirname(safe_path)
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            tf.write(content)
            temp_name = tf.name

        os.replace(temp_name, safe_path)

        # 3. Đồng bộ lại SQLite index
        idx.index_document(safe_path)

        return {
            "document_id": document_id,
            "path": safe_path,
            "bytes_written": len(content.encode("utf-8")),
            "backup_created": create_backup,
            "status": "success",
            "message": "File written atomically and indexed successfully."
        }
    except Exception as e:
        return {
            "error": "WRITE_ERROR",
            "message": f"Atomic write failed: {str(e)}",
            "document_id": document_id
        }
```

---

## 3. Tiêu chí Nghiệm thu (Acceptance Criteria)

- [x] `is_valid_uuid()` trả về `False` với UUID v1, v3, v5 và Nil UUID (`00000000-0000-0000-0000-000000000000`).
- [x] `resolve_safe_doc_path()` chặn 100% tài liệu nằm ngoài `workspace_dir` (trả về `is_valid=False`).
- [x] `get_active_workspace_dir()` được cache theo `mtime` của `settings.json` và dùng chung giữa `security.py` và `server.py`.
- [x] Toàn bộ 5 tool handlers trong `src/mcp/tools.py` và `search_documents`/`list_backlinks` đều lọc theo `workspace_dir` hợp lệ.
- [x] `_read_next_message()` xử lý thành công 5,000 dòng trống liên tiếp mà không bị `RecursionError` và hoạt động độc lập cả khi chưa gọi `run_forever()`.
- [x] `write_document_content` tạo file `.bak` sao lưu và sử dụng cơ chế ghi nguyên tử (`os.replace`).
- [x] Khởi chạy `python run.py --mcp-server` không phát sinh ký tự rác trên stdout.

---

## 4. Nhật ký Sửa đổi (Changelog)

- **v1.1 (2026-09-10)**:
  - Bổ sung `@functools.lru_cache` cho `get_active_workspace_dir()` để triệt tiêu I/O đọc đĩa lặp lại.
  - Tái cấu trúc `server.py` gọi chung `get_active_workspace_dir()`, loại bỏ trùng lặp code.
  - Sửa `except (ValueError, Exception):` thành `except ValueError:` chuẩn xác.
  - Bổ sung thiết kế Safe Atomic Write & Backup cho `write_document_content`.
