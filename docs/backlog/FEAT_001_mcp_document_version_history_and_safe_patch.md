# 📦 FEAT-001: MCP Document Version History, Safe Patch, Audit Trail & Rollback Engine

**Mã Task**: `FEAT-001`  
**Phân loại**: Feature / Data Reliability / Security  
**Độ ưu tiên**: Critical  
**Trạng thái**: 🟢 Completed (Phase 1–4)  
**Nhánh triển khai**: `feat/duy-15092026-mcp-version-history`  
**Tài liệu liên quan**: [SEC-001](SEC_001_mcp_security_boundary_and_stream_hardening.md), [ARCH-001](ARCH_001_pyinstaller_console_stdio_mcp_packaging.md), [SEC-002](SEC_002_mcp_client_argument_injection_and_startup_consolidation.md), [SEC-003](SEC_003_mcp_workspace_session_isolation_and_fail_closed.md)

---

## 1. Hiện trạng & Phân tích 9 Vấn đề Cốt lõi + Ràng buộc Implementation

Công cụ `docconvert/write_document_content` MCP hiện tại cho phép AI ghi đè trực tiếp toàn bộ tài liệu Markdown. Mặc dù đã có cơ chế ghi tạm nguyên tử (atomic temporary file swap) và tạo 1 file `.bak`, qua đánh giá kiến trúc thực tế, hệ thống tồn tại các lỗ hổng và điểm nghẽn nghiêm trọng khi AI agent tương tác đa bước:

### 1.1. 9 Vấn đề Kiến trúc & Ràng buộc Hệ thống

| # | Vấn đề / Lỗ hổng | Rủi ro & Nguyên nhân kỹ thuật | Ràng buộc kiến trúc bắt buộc (Enforced Constraints) |
|---|---|---|---|
| **1** | **`cleanup_legacy_backups` thiếu Gate xác nhận 2 lớp & Nguy cơ Symlink Traversal** | Là công cụ mang tính phá hủy (destructive). Nếu expose qua JSON-RPC mà không có safety gate hoặc không chặn symlink, AI có thể vô tình xóa hàng loạt file hoặc xóa nhầm file ngoài workspace qua symlink. | • Mặc định `dry_run = True` (chỉ quét, thống kê danh sách file `.bak` và tổng dung lượng).<br>• Để thực thi xóa thật, AI/User **bắt buộc** truyền đồng thời `dry_run = False` **VÀ** `confirm = True`.<br>• `os.walk(ws, followlinks=False)` + loại bỏ `os.path.islink()` + kiểm tra `is_path_in_workspace(os.path.realpath(file), ws)` cho từng file.<br>• Dùng `safe_delete_to_recycle_bin` / `send2trash`. |
| **2** | **`patch_document_content` gây lỗi "Silent Wrong Replace" khi match không duy nhất** | Nếu đoạn `target_content` xuất hiện nhiều hơn 1 lần trong file, thao tác replace thông thường sẽ thay thế nhầm đoạn đầu tiên hoặc toàn bộ, làm hỏng nội dung tài liệu mà AI không hề hay biết. | • Đếm số lần xuất hiện: `count = content.count(target_content)`.<br>• Nếu `count == 0`: Trả lỗi `TARGET_NOT_FOUND`.<br>• Nếu `count > 1`: Trả lỗi `MULTIPLE_MATCHES_FOUND` kèm `match_count`, **từ chối sửa** và yêu cầu AI gửi block context dài hơn/độc nhất.<br>• Chỉ thay thế khi và chỉ khi `count == 1`. |
| **3** | **Snapshot full content không có cơ chế Pruning / Retention** | Mỗi lần sửa đều lưu full snapshot vào SQLite `document_history`. Sau hàng trăm lần edit của AI, database `index.db` sẽ phình to không kiểm soát. | • Bổ sung cấu hình `max_versions_per_doc` (mặc định: `30` non-baseline revisions).<br>• **Bảo vệ Baseline**: Luôn giữ nguyên `version = 0` (bản gốc của User).<br>• Tự động prune các version trung gian cũ nhất (`1..k`) khi số lượng vượt ngưỡng ngay trong write transaction. |
| **4** | **Race Condition khi sinh số thứ tự Version (`version = MAX + 1`)** | Đọc `MAX(version)` rồi mới tính `+ 1` ngoài tầng ứng dụng mà không có transaction lock có thể khiến 2 tiến trình/request ghi cùng lúc sinh ra trùng version number. | • Đóng gói toàn bộ logic capture baseline, calculate version và insert snapshot bên trong `self._write_lock` của `MetadataIndex`.<br>• Sử dụng atomic subquery: `COALESCE((SELECT MAX(version) FROM document_history WHERE document_id = ?), 0) + 1` trong SQLite transaction (bảo đảm AI version luôn $\ge 1$). |
| **5** | **`rollback_document` làm stale SQLite Metadata Index** | Sau khi ghi đè file trên đĩa về version cũ, nếu không re-index thì `content_hash`, `tags`, `wikilinks` trong các bảng `documents`, `tags`, `wikilinks` sẽ không khớp với nội dung thực tế trên đĩa. | • Spec quy định bắt buộc: Ngay sau khi khôi phục nội dung file đĩa thành công, `rollback_document` **bắt buộc** phải gọi `idx.index_document(safe_path)` tương tự `write_document_content`. |
| **6** | **Thiếu quy định bắt buộc dùng chung Path Resolution & UUID Security** | Các tool mới nếu tự viết hàm resolve path riêng sẽ có nguy cơ bỏ sót Workspace boundary check hoặc lọt lỗ hổng Path Traversal. | • Quy chuẩn tuyệt đối: Tất cả 4 tool mới và mọi tool MCP tương lai **bắt buộc** phải tái sử dụng `resolve_safe_doc_path()` và `is_valid_uuid()` từ `src.mcp.security`. Cấm tự parse/resolve path riêng. |
| **7** | **`rollback_document` bị vô hiệu hóa khi file đĩa đã bị xóa ngoài ý muốn** | `resolve_safe_doc_path()` hiện tại trả về `False` nếu file không còn tồn tại vật lý trên đĩa → Khi người dùng lỡ tay xóa mất file và muốn AI rollback khôi phục lại thì tool lại báo lỗi không tìm thấy file! | • Bổ sung hàm bảo mật chuyên biệt `resolve_doc_for_restore()`: Nếu file không tồn tại trên đĩa nhưng `document_id` hợp lệ trong SQLite index và `stored_path` thuộc `active_workspace`, cho phép tái tạo file tại đúng `stored_path` (tự động tạo thư mục cha `os.makedirs`) từ version snapshot. |
| **8** | **Nguy cơ AI giả mạo danh tính trong trường `author` & Invariant `version = 0`** | Nếu expose tham số `author` cho AI tự truyền qua JSON-RPC, AI có thể tự khai `author='USER'`, làm sai lệch nhật ký kiểm toán (audit trail). | • **Không expose** tham số `author` ra MCP Tool Schema của AI.<br>• **Quy ước bất biến**: `version = 0` luôn độc quyền dành cho `author = 'USER'` (Baseline). AI append luôn bắt đầu từ `version >= 1`.<br>• `author = 'SYSTEM'` cho các thao tác `rollback_document` / restore. |
| **9** | **Thiếu ràng buộc `UNIQUE(document_id, version)` ở tầng CSDL** | Index thường trên `(document_id, version)` chỉ tối ưu tốc độ tìm kiếm, không ngăn chặn được việc insert trùng version nếu xảy ra lỗi logic phần mềm. | • Thay thế bằng `UNIQUE INDEX` hoặc `UNIQUE(document_id, version)` constraint trực tiếp trong DDL schema của `document_history`. |

---

### 1.2. Các Ràng buộc Implementation Chi tiết

1. **Bảo toàn Invariant `version = 0` cho USER**: Trong `append_document_version()`, sử dụng subquery `COALESCE((SELECT MAX(version) FROM document_history WHERE document_id = ?), 0) + 1`. Nếu chưa có history hoặc baseline capture chưa có file đĩa, `MAX(version)` trả về `NULL` $\rightarrow$ `COALESCE(NULL, 0) + 1 = 1`. Do đó, các phiên bản do AI hoặc System ghi sẽ **luôn luôn có `version >= 1`**, không bao giờ bị ghi đè thành `version = 0` của User.
2. **Triệt tiêu "Audit Trail Ma" (Phantom Revisions)**: Tách rời 2 bước rõ ràng:
   - Bước 1: `ensure_baseline_version(document_id)` chạy **trước** khi ghi đĩa (đọc file gốc trên đĩa để snapshot `version = 0`).
   - Bước 2: Thực hiện Atomic Disk Write (`NamedTemporaryFile` + `os.replace`).
   - Bước 3: `append_document_version(document_id, new_content, ...)` chỉ chạy **sau khi** ghi đĩa thành công.
3. **Chống Symlink Traversal trong `cleanup_legacy_backups`**:
   - Duyệt thư mục với `os.walk(ws, followlinks=False)`.
   - Bỏ qua các file là symlink (`os.path.islink(f)`).
   - Kiểm tra đường dẫn thực tế `real_path = os.path.realpath(f)` với `is_path_in_workspace(real_path, ws)` trước khi đưa vào danh sách xử lý.
4. **Chuẩn tên Connection Context Manager**: Sử dụng `self.get_connection()` (không dùng `self._get_connection()` để tránh `AttributeError`).
5. **Đọc File an toàn với `errors="replace"`**: Mọi thao tác đọc file disk (kể cả baseline capture) đều phải sử dụng `open(path, "r", encoding="utf-8", errors="replace")` để chống crash `UnicodeDecodeError`.
6. **Không dùng `cursor.lastrowid` làm `version`**: `lastrowid` là Primary Key `id` (INTEGER AUTOINCREMENT), hoàn toàn khác với giá trị cột `version`. Sau khi `INSERT`, hàm query `SELECT version FROM document_history WHERE id = ?` với `inserted_id = cursor.lastrowid` để lấy đúng giá trị `version` trả về cho client.
7. **Baseline Capture an toàn tuyệt đối với `INSERT OR IGNORE`**: Tránh lỗi `IntegrityError` khi 2 tác vụ cùng lúc kiểm tra baseline bằng cách dùng `INSERT OR IGNORE INTO document_history (...) VALUES (?, 0, ...)`.
8. **Sửa lỗi Off-by-one trong Retention Pruning**: Khi `max_versions = 30`, điều kiện prune là `if len(non_baseline_rows) > max_versions:`, và số bản ghi cần xóa là `excess_count = len(non_baseline_rows) - max_versions`.
9. **`bytes_count` tính bằng SQL & Ẩn PK nội bộ `id`**: Trong `get_document_versions()`, sử dụng `LENGTH(CAST(content AS BLOB)) AS bytes_count` ngay tại câu lệnh SQL và không query cột `id` ra ngoài API.
10. **Đếm `total_versions` chính xác khi phân trang**: Tool handler `get_document_history` sử dụng `count_document_versions(document_id)` (thực hiện `SELECT COUNT(*)`) để trả về tổng số version hiện có.
11. **`cleanup_legacy_backups` Workspace Resolution**: Không nhận tham số `workspace` từ client/AI qua input schema. Workspace **luôn luôn** được resolve server-side thông qua `get_active_workspace_dir()`.

---

### 1.3. Hai Edge Cases Phụ & Chiến lược Xử lý Graceful Degradation (Phase 3)

| Edge Case | Mô tả & Nguyên nhân kỹ thuật | Hậu quả thực tế | Cơ chế phòng ngừa & Graceful Degradation |
|---|---|---|---|
| **EC-1: Disk Write OK nhưng `append_document_version()` thất bại** | File đĩa đã đổi sang nội dung mới thành công, nhưng lệnh ghi history vào SQLite ném exception (vd: ổ đĩa đầy đột ngột hoặc lock timeout kéo dài). | File vật lý chính xác 100%, nhưng thiếu 1 entry log trong audit trail. Khả năng rollback về `version 0` (baseline) vẫn bảo toàn nguyên vẹn. | Bọc `append_document_version()` trong `try...except`. Khai báo `warning_msg: Optional[str] = None` trước `try`. Trả về response thành công kèm `warning: "version_log_failed"` thay vì để toàn bộ tool handler bị crash. |
| **EC-2: `index_document()` thất bại sau khi đã ghi file và lưu history** | Cả file đĩa và `document_history` đều đồng bộ đúng, nhưng bước phân tích chỉ mục (`tags`, `wikilinks`, `content_hash`) bị lỗi do parser hoặc busy lock. | Dữ liệu gốc và lịch sử an toàn 100%. Các bảng tìm kiếm (`documents`, `tags`, `wikilinks`) tạm thời bị lệch (stale) nhẹ. | Log `logger.warning()` mà không làm gián đoạn tool. Tình trạng stale này sẽ tồn tại cho tới lần trigger `sync_workspace_incremental()` tiếp theo (khi khởi động lại MCP server, khi mở/đổi workspace trên GUI, hoặc chạy refactor) do hệ thống hiện chưa có cơ chế sync định kỳ (cron/ticker). |

---

## 2. Kiến trúc Tổng thể & Luồng Dữ liệu (System Architecture)

```
[AI Agent / MCP Client]
          │
          ├── [1] Patch Mode: `patch_document_content(doc_id, target, replace)`
          │        ├── 1. resolve_safe_doc_path(doc_id)
          │        ├── 2. Verify target_content.count() == 1 (Chống silent wrong replace)
          │        ├── 3. ensure_baseline_version(doc_id) -> Capture v0 trước khi mutate
          │        ├── 4. Atomic NamedTemporaryFile swap ra đĩa
          │        ├── 5. append_document_version(doc_id, patched_content, author='AI') (Graceful try/except, v >= 1)
          │        └── 6. idx.index_document(safe_path) (Non-blocking warning)
          │
          ├── [2] Full Write Mode: `write_document_content(doc_id, content)`
          │        ├── 1. resolve_safe_doc_path(doc_id)
          │        ├── 2. ensure_baseline_version(doc_id) -> Capture v0 trước khi mutate
          │        ├── 3. Atomic NamedTemporaryFile swap ra đĩa
          │        ├── 4. append_document_version(doc_id, content, author='AI') (Graceful try/except, v >= 1)
          │        └── 5. idx.index_document(safe_path) (Non-blocking warning)
          │
          ├── [3] History Inspection: `get_document_history(doc_id, limit)`
          │        ├── 1. resolve_safe_doc_path(doc_id)
          │        ├── 2. count_document_versions(doc_id) -> SELECT COUNT(*)
          │        └── 3. get_document_versions(doc_id, limit) -> Metadata + LENGTH(BLOB) (Zero content transfer, no internal PK)
          │
          ├── [4] Rollback Engine: `rollback_document(doc_id, target_version)`
          │        ├── 1. resolve_doc_for_restore(doc_id) -> Cho phép tái tạo file vật lý nếu bị mất
          │        ├── 2. get_version_content(doc_id, target_version) -> Lấy snapshot từ SQLite
          │        ├── 3. Atomic NamedTemporaryFile swap ra đĩa (hoặc tạo mới nếu mất file)
          │        ├── 4. append_document_version(doc_id, snapshot, author='SYSTEM', "Rollback to vX")
          │        └── 5. idx.index_document(safe_path)
          │
          └── [5] Legacy Cleanup: `cleanup_legacy_backups(dry_run=True, confirm=False)`
                   ├── Server-side workspace: get_active_workspace_dir()
                   ├── Anti-symlink: followlinks=False + islink check + is_path_in_workspace(realpath)
                   ├── 2-Layer Safety Gate: Bắt buộc dry_run=False & confirm=True mới xóa thật
                   └── Sử dụng safe_delete_to_recycle_bin (thùng rác hệ điều hành)
```

---

## 3. Thiết kế CSDL Chi tiết (`index.db`)

Bảng `document_history` được tích hợp vào `src/services/metadata_index.py` với DDL chuẩn hóa:

```sql
-- 1. Bảng lưu trữ lịch sử snapshot và audit trail
CREATE TABLE IF NOT EXISTS document_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,          -- 0: Original Human Baseline (USER), 1..N: Revisions (AI / SYSTEM)
    content TEXT NOT NULL,             -- Full text snapshot tại thời điểm sửa đổi
    change_summary TEXT,               -- Mô tả tóm tắt nội dung thay đổi
    author TEXT NOT NULL DEFAULT 'AI' CHECK(author IN ('USER', 'AI', 'SYSTEM')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- 2. UNIQUE Index chặn triệt để race condition & duplicate version ở tầng DB
CREATE UNIQUE INDEX IF NOT EXISTS idx_history_doc_ver_unique ON document_history(document_id, version);
CREATE INDEX IF NOT EXISTS idx_history_doc_created ON document_history(document_id, created_at DESC);
```

---

### 3.1. Các Phương thức Quản trị Version trong `MetadataIndex`

```python
MAX_VERSIONS_PER_DOC = 30


def ensure_baseline_version(self, document_id: str) -> bool:
    """
    Tự động chụp snapshot v0 baseline của USER từ file đĩa hiện tại (trước khi mutate).
    Sử dụng INSERT OR IGNORE để bảo đảm tính idempotent và an toàn tuyệt đối trước race condition.
    
    Returns:
        bool: True nếu đã có baseline (vừa tạo hoặc đã tồn tại từ trước), False nếu không đọc được file.
    """
    with self._write_lock:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Kiểm tra nhanh xem đã có baseline v0 trong DB chưa
            cursor.execute(
                "SELECT 1 FROM document_history WHERE document_id = ? AND version = 0",
                (document_id,)
            )
            if cursor.fetchone():
                return True
            
            # Đọc nội dung hiện tại trên đĩa làm baseline v0 của USER
            cursor.execute("SELECT path FROM documents WHERE id = ?", (document_id,))
            doc_row = cursor.fetchone()
            if doc_row and doc_row["path"] and os.path.isfile(doc_row["path"]):
                try:
                    with open(doc_row["path"], "r", encoding="utf-8", errors="replace") as f:
                        current_disk_content = f.read()
                    cursor.execute("""
                        INSERT OR IGNORE INTO document_history (document_id, version, content, change_summary, author)
                        VALUES (?, 0, ?, 'Initial human baseline before AI edits', 'USER')
                    """, (document_id, current_disk_content))
                    conn.commit()
                    return True
                except Exception:
                    return False
            return False


def append_document_version(
    self,
    document_id: str,
    content: str,
    change_summary: Optional[str] = None,
    author: str = "AI",
    max_versions: int = MAX_VERSIONS_PER_DOC
) -> int:
    """
    Ghi nhận version mới N vào SQLite (chỉ gọi sau khi ghi đĩa thành công để chống audit trail ma):
    1. Insert snapshot với version = COALESCE(MAX, 0) + 1 (bảo đảm AI revisions luôn có version >= 1).
    2. Query lại đúng cột `version` từ DB bằng `lastrowid`.
    3. Tự động prune các version trung gian cũ nhất nếu vượt quá `max_versions` (luôn bảo vệ v0 baseline).
    
    Returns:
        int: Số version thực tế vừa được tạo (vd: 1, 2, 3...)
    """
    with self._write_lock:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Insert Revision mới với atomic subquery tính version kế tiếp (luôn >= 1)
            cursor.execute("""
                INSERT INTO document_history (document_id, version, content, change_summary, author)
                VALUES (
                    ?,
                    COALESCE((SELECT MAX(version) FROM document_history WHERE document_id = ?), 0) + 1,
                    ?,
                    ?,
                    ?
                )
            """, (document_id, document_id, content, change_summary or "Updated document", author))
            
            inserted_id = cursor.lastrowid

            # 2. Lấy đúng giá trị cột `version` thực tế vừa insert (tránh bug nhầm PK id)
            cursor.execute("SELECT version FROM document_history WHERE id = ?", (inserted_id,))
            ver_row = cursor.fetchone()
            actual_version = ver_row["version"] if ver_row else 1

            # 3. Retention Pruning: Xóa version cũ nhất khi vượt ngưỡng (LUÔN GIỮ version 0)
            cursor.execute("""
                SELECT id FROM document_history 
                WHERE document_id = ? AND version > 0
                ORDER BY version ASC
            """, (document_id,))
            non_baseline_rows = cursor.fetchall()
            
            # Nếu số bản ghi non-baseline vượt quá max_versions
            if len(non_baseline_rows) > max_versions:
                excess_count = len(non_baseline_rows) - max_versions
                ids_to_delete = [r["id"] for r in non_baseline_rows[:excess_count]]
                cursor.executemany(
                    "DELETE FROM document_history WHERE id = ?",
                    [(i,) for i in ids_to_delete]
                )
            
            conn.commit()
            return actual_version


def count_document_versions(self, document_id: str) -> int:
    """
    Đếm tổng số phiên bản hiện có trong lịch sử của tài liệu (phục vụ pagination metadata).
    """
    with self.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM document_history WHERE document_id = ?", (document_id,))
        row = cursor.fetchone()
        return row["total"] if row else 0


def get_document_versions(
    self,
    document_id: str,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Truy vấn danh sách metadata lịch sử phiên bản của một tài liệu.
    Tính toán `bytes_count` trực tiếp trong SQLite bằng LENGTH(CAST(content AS BLOB)),
    không load chuỗi `content` lớn và không leak PK nội bộ `id`.
    
    Returns:
        List[Dict[str, Any]]: [{version, author, change_summary, created_at, char_count, bytes_count}]
    """
    with self.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                version,
                author,
                change_summary,
                created_at,
                LENGTH(content) AS char_count,
                LENGTH(CAST(content AS BLOB)) AS bytes_count
            FROM document_history
            WHERE document_id = ?
            ORDER BY version DESC
            LIMIT ?
        """, (document_id, limit))
        return [dict(row) for row in cursor.fetchall()]


def get_version_content(
    self,
    document_id: str,
    version: int
) -> Optional[str]:
    """
    Truy vấn nội dung snapshot Markdown đầy đủ của một version cụ thể (phục vụ rollback/restore).
    
    Returns:
        Optional[str]: Nội dung văn bản Markdown hoặc None nếu không tồn tại version này.
    """
    with self.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT content FROM document_history
            WHERE document_id = ? AND version = ?
        """, (document_id, version))
        row = cursor.fetchone()
        return row["content"] if row else None
```

---

## 4. Chi tiết Đặc tả 5 Công cụ MCP (MCP Tools Specification)

> [!IMPORTANT]
> **Quy chuẩn Bảo mật Bắt buộc**: Mọi tool dưới đây **phải** sử dụng `is_valid_uuid()` để kiểm tra `document_id` và `resolve_safe_doc_path()` / `resolve_doc_for_restore()` để bảo đảm boundary workspace. Nghiêm cấm mọi hành vi nhận direct path từ client mà không qua index validation.

### 4.1. Cập nhật `write_document_content`

- **Mục đích**: Ghi đè toàn bộ tài liệu Markdown, tự động lưu lịch sử version, tự động capture v0 baseline nếu là lần sửa đầu tiên.
- **Quy trình Thực thi An toàn (Chống Audit Trail Ma & Graceful Degradation)**:
  1. `is_valid, safe_path, doc = resolve_safe_doc_path(document_id, idx)`.
  2. `idx.ensure_baseline_version(document_id)` (Lưu v0 baseline từ đĩa nếu chưa có).
  3. Ghi file đĩa bằng atomic write: `NamedTemporaryFile` + `os.replace`.
  4. Ghi nhận revision mới (với graceful fallback):
     ```python
     warning_msg: Optional[str] = None
     try:
         version_created = idx.append_document_version(document_id, content, change_summary, author='AI')
     except Exception as e:
         version_created = None
         warning_msg = f"File written to disk successfully, but history snapshot failed: {str(e)}"
     ```
  5. `try: idx.index_document(safe_path)` (Bắt exception để log warning, không làm crash tool).
- **Response**:
  ```json
  {
    "document_id": "8f3b2e7a-...",
    "path": "C:\\Workspace\\Notes\\design.md",
    "bytes_written": 4820,
    "version": 2,
    "warning": null,
    "status": "success",
    "message": "File written atomically and revision indexed successfully."
  }
  ```

### 4.2. Tool mới: `patch_document_content`

- **Mục đích**: Tìm và thay thế một khối nội dung cụ thể trong tài liệu Markdown. Giảm thiểu 90% lượng token tiêu thụ và triệt tiêu nguy cơ AI bị drop nội dung khi file lớn.
- **Input Schema**:
  ```json
  {
    "name": "patch_document_content",
    "description": "Safely patches a specific unique text block in a Markdown document. Prevents accidental document truncation and enforces strict single-match verification.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "document_id": {
          "type": "string",
          "description": "Unique UUID v4 of the document to patch."
        },
        "target_content": {
          "type": "string",
          "description": "The exact existing text block to be replaced. Must match exactly one occurrence in the document."
        },
        "replacement_content": {
          "type": "string",
          "description": "The new replacement text content."
        },
        "change_summary": {
          "type": "string",
          "description": "Short explanation of what this patch changes (for history log)."
        }
      },
      "required": ["document_id", "target_content", "replacement_content"]
    }
  }
  ```
- **Quy trình Thực thi An toàn**:
  1. Kiểm tra UUID và resolve path an toàn qua `resolve_safe_doc_path(document_id, idx)`.
  2. Đọc nội dung hiện tại của file: `open(safe_path, "r", encoding="utf-8", errors="replace")`.
  3. Kiểm tra số lần xuất hiện: `matches = content.count(target_content)`.
     - Nếu `matches == 0`: Trả lỗi `TARGET_NOT_FOUND`. Hướng dẫn AI đọc lại file bằng `read_document` để lấy chuỗi chính xác.
     - Nếu `matches > 1`: Trả lỗi `MULTIPLE_MATCHES_FOUND` kèm `match_count: matches`. Hướng dẫn AI mở rộng thêm 2-3 dòng ngữ cảnh trước/sau vào `target_content` để tạo chuỗi độc nhất.
  4. Nếu `matches == 1`:
     - `patched_content = content.replace(target_content, replacement_content, 1)`.
     - `idx.ensure_baseline_version(document_id)` (Lưu baseline trước khi sửa).
     - Ghi đè file đĩa bằng atomic write (`NamedTemporaryFile` + `os.replace`).
     - Ghi nhận revision mới (với graceful fallback):
       ```python
       warning_msg: Optional[str] = None
       try:
           version_created = idx.append_document_version(document_id, patched_content, change_summary, author='AI')
       except Exception as e:
           version_created = None
           warning_msg = f"Patch applied to disk successfully, but history snapshot failed: {str(e)}"
       ```
     - `try: idx.index_document(safe_path)` (Bắt exception để log warning).
- **Response**:
  ```json
  {
    "document_id": "8f3b2e7a-...",
    "path": "C:\\Workspace\\Notes\\design.md",
    "bytes_written": 4820,
    "version": 3,
    "warning": null,
    "status": "success",
    "message": "File patched atomically and revision indexed successfully."
  }
  ```

### 4.3. Tool mới: `get_document_history`

- **Mục đích**: Cho phép AI hoặc người dùng tra cứu dòng thời gian các lần chỉnh sửa của tài liệu, người sửa (`USER`, `AI`, `SYSTEM`), tóm tắt thay đổi và dung lượng byte.
- **Input Schema**:
  ```json
  {
    "name": "get_document_history",
    "description": "Retrieves version timeline, authors, timestamps, and change summaries for a document. Does not return full body text to conserve token context.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "document_id": {
          "type": "string",
          "description": "Unique UUID v4 of the document."
        },
        "limit": {
          "type": "integer",
          "default": 20,
          "maximum": 50,
          "description": "Maximum number of history revisions to retrieve."
        }
      },
      "required": ["document_id"]
    }
  }
  ```
- **Xử lý Thực thi**:
  - `total = idx.count_document_versions(document_id)` (Query đếm riêng bằng `SELECT COUNT(*)`).
  - `versions = idx.get_document_versions(document_id, limit)`.
- **Output Sample**:
  ```json
  {
    "document_id": "8f3b2e7a-...",
    "total_versions": 4,
    "returned_versions": 2,
    "versions": [
      {
        "version": 3,
        "author": "AI",
        "change_summary": "Added comparison table for SQLite vs DuckDB",
        "created_at": "2026-09-15 12:40:10",
        "char_count": 4500,
        "bytes_count": 4820
      },
      {
        "version": 0,
        "author": "USER",
        "change_summary": "Initial human baseline before AI edits",
        "created_at": "2026-09-15 11:20:00",
        "char_count": 3000,
        "bytes_count": 3100
      }
    ]
  }
  ```

### 4.4. Tool mới: `rollback_document` (Kèm cơ chế Restore khi mất file vật lý)

- **Mục đích**: Khôi phục tài liệu về một version lịch sử cụ thể (mặc định: `version = 0` - Human Baseline).
- **Input Schema**:
  ```json
  {
    "name": "rollback_document",
    "description": "Restores a document to a previous historical version (default: version 0 baseline). Supports recreating deleted files if history exists.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "document_id": {
          "type": "string",
          "description": "Unique UUID v4 of the document."
        },
        "target_version": {
          "type": "integer",
          "default": 0,
          "description": "Target version number to restore (defaults to 0 for initial human baseline)."
        }
      },
      "required": ["document_id"]
    }
  }
  ```
- **Xử lý An toàn qua `resolve_doc_for_restore` & Thứ tự Thực thi**:
  1. Kiểm tra UUID v4 độc lập trước tiên:
     - Nếu `not is_valid_uuid(document_id)`: Trả ngay mã lỗi `INVALID_UUID`.
  2. Gọi `is_valid, safe_path, doc = resolve_doc_for_restore(document_id, idx)`:
     - Nếu `doc is None`: Trả mã lỗi `DOCUMENT_NOT_FOUND`.
     - Nếu `doc is not None` và `is_valid is False`: Trả mã lỗi `RESTORE_OUTSIDE_WORKSPACE`.
  3. Lấy snapshot `target_content` từ `document_history` qua `idx.get_version_content(document_id, target_version)`:
     - Nếu trả về `None`: Trả ngay mã lỗi `VERSION_NOT_FOUND` (tuyệt đối không để rơi xuống bước ghi file).
  4. Nếu file trên đĩa **đã bị xóa/mất**:
     - `resolve_doc_for_restore()` đã xác minh `safe_path` thuộc `active_workspace`.
     - Tự động tạo lại thư mục cha: `os.makedirs(os.path.dirname(safe_path), exist_ok=True)`.
  5. Ghi nội dung snapshot ra đĩa qua `NamedTemporaryFile` + `os.replace`.
  6. Ghi nhận 1 entry audit trail mới:
     ```python
     warning_msg: Optional[str] = None
     try:
         idx.append_document_version(document_id, target_content, change_summary=f"Rollback to version {target_version}", author='SYSTEM')
     except Exception as e:
         warning_msg = f"Rollback content written to disk, but audit logging failed: {str(e)}"
     ```
  7. **Bắt buộc re-index**: `try: idx.index_document(safe_path) except Exception as e: logger.warning("Re-index failed post-rollback: %s", e)`.

### 4.5. Tool mới: `cleanup_legacy_backups` (2-Layer Safety Confirmation & Anti-Symlink Traversal)

- **Mục đích**: Quét và dọn dẹp các file `.bak` dư thừa sinh ra từ các phiên bản cũ trong thư mục workspace.
- **Quy tắc Bảo mật Workspace**: Tuyệt đối **không nhận path thư mục từ client**. Workspace luôn được resolve tự động ở tầng server thông qua `get_active_workspace_dir()`.
- **Input Schema**:
  ```json
  {
    "name": "cleanup_legacy_backups",
    "description": "Scans and cleans up legacy *.bak backup files in the workspace. Requires dry_run=false AND confirm=true to execute deletion. Workspace is automatically resolved server-side.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "dry_run": {
          "type": "boolean",
          "default": true,
          "description": "If true (default), only lists found .bak files without deleting them."
        },
        "confirm": {
          "type": "boolean",
          "default": false,
          "description": "Explicit safety confirmation flag. Must be set to true when dry_run=false."
        }
      },
      "required": []
    }
  }
  ```
- **Xử lý An toàn (Anti-Symlink & 2-Layer Gate)**:
  1. Lấy `ws = get_active_workspace_dir()`. Nếu không tìm thấy workspace: báo lỗi `WORKSPACE_NOT_FOUND`.
  2. Quét đệ quy an toàn:
     - Dùng `os.walk(ws, followlinks=False)` để không theo symlink thư mục.
     - Với mỗi file kết thúc bằng `.bak`:
       - Nếu `os.path.islink(file_path)`: Bỏ qua (không xử lý symlink file).
       - `real_path = os.path.realpath(file_path)`.
       - Nếu `not is_path_in_workspace(real_path, ws)`: Bỏ qua.
       - Thêm vào danh sách candidate files hợp lệ.
  3. Nếu `dry_run == True`: Trả về danh sách file candidate, dung lượng từng file và tổng dung lượng giải phóng dự kiến.
  4. Nếu `dry_run == False` nhưng `confirm == False`: Trả về lỗi `CONFIRMATION_REQUIRED`, từ chối xóa và yêu cầu AI/User xác nhận rõ ràng bằng cách gửi `confirm: true`.
  5. Nếu `dry_run == False` và `confirm == True`: Di chuyển toàn bộ candidate files vào Thùng rác hệ điều hành (`send2trash` / `safe_delete_to_recycle_bin`). Trả về danh sách và số lượng file đã dọn dẹp an toàn.

---

## 5. Bổ sung Hàm Bảo mật `resolve_doc_for_restore` (`src/mcp/security.py`)

Để hỗ trợ khôi phục tài liệu khi file trên đĩa đã bị xóa ngoài ý muốn mà vẫn đảm bảo tính toàn vẹn và ngăn chặn path traversal:

```python
def resolve_doc_for_restore(
    doc_id: str,
    index: Any
) -> Tuple[bool, Optional[str], Optional[dict]]:
    """
    Resolves document path for restore/rollback operations where physical file may be missing on disk.
    
    Security Guarantees:
    1. Enforces strict UUID v4 validation.
    2. Validates document record existence in SQLite index.
    3. Validates that stored_path is strictly within the active workspace directory.
    
    Returns:
        (is_valid_and_permitted, absolute_file_path, document_record_dict)
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

    # Enforce workspace boundary check even if the physical file does not exist on disk
    ws = get_active_workspace_dir()
    if ws and not is_path_in_workspace(norm_path, ws):
        return False, None, doc

    return True, norm_path, doc
```

---

## 6. Bảng Mã Lỗi Chuẩn hóa (Error Code Manifest)

| Error Code | Mô tả | Hướng dẫn xử lý cho AI Agent |
|---|---|---|
| `INVALID_UUID` | `document_id` không phải UUID v4 hợp lệ | Kiểm tra lại danh sách ID lấy từ `search_documents`. |
| `DOCUMENT_NOT_FOUND` | ID không tồn tại trong DB hoặc nằm ngoài workspace | Tìm kiếm lại tài liệu qua `search_documents`. |
| `WORKSPACE_NOT_FOUND` | Không phát hiện active workspace | Cấu hình biến môi trường `DOCCONVERT_WORKSPACE` hoặc mở thư mục trong ứng dụng. |
| `TARGET_NOT_FOUND` | `target_content` không xuất hiện trong file | Gọi `read_document` để đọc lại nội dung mới nhất. |
| `MULTIPLE_MATCHES_FOUND` | `target_content` xuất hiện nhiều lần (match_count > 1) | Thêm 2-3 dòng ngữ cảnh liền kề vào `target_content` để tạo đoạn khớp duy nhất. |
| `VERSION_NOT_FOUND` | `target_version` không tồn tại trong lịch sử | Gọi `get_document_history` để xem các version khả dụng. |
| `CONFIRMATION_REQUIRED` | `dry_run=False` nhưng thiếu `confirm=True` | Yêu cầu người dùng xác nhận trước khi truyền `confirm=True`. |
| `RESTORE_OUTSIDE_WORKSPACE` | Đường dẫn khôi phục nằm ngoài Workspace | Kiểm tra cấu hình thư mục làm việc hiện tại. |

---

## 7. Kế hoạch Triển khai (Implementation Roadmap)

| Giai đoạn | Nội dung công việc | File ảnh hưởng |
|:---|:---|:---|
| **Phase 1: Database Engine** | • Thêm DDL `document_history` & `UNIQUE INDEX` vào `MetadataIndex._create_tables`<br>• Implement `ensure_baseline_version()`, `append_document_version()` (subquery `COALESCE(MAX, 0) + 1`), `count_document_versions()`, `get_document_versions()` (không leak PK), `get_version_content()`<br>• Bảo toàn invariant `version = 0` cho USER baseline | `src/services/metadata_index.py` |
| **Phase 2: Security & Restore Helper** | • Thêm helper `resolve_doc_for_restore()` hỗ trợ phục hồi file khi mất trên đĩa với strict boundary check<br>• Đảm bảo `resolve_safe_doc_path()` chặt chẽ | `src/mcp/security.py` |
| **Phase 3: MCP Tool Handlers** | • Cập nhật `handle_write_document_content` (quy trình 2 bước + graceful fallback EC-1/EC-2)<br>• Implement `handle_patch_document_content` (match count validation + response sample + graceful fallback)<br>• Implement `handle_get_document_history` (phân trang + count_document_versions + zero PK leak)<br>• Implement `handle_rollback_document`<br>• Implement `handle_cleanup_legacy_backups` (anti-symlink + server-side workspace)<br>• Đăng ký tools vào `MCP_TOOLS_MANIFEST` và `TOOL_HANDLERS` | `src/mcp/tools.py` |
| **Phase 4: Automated Testing** | • Test capture baseline v0 tự động (`ensure_baseline_version`) & invariant `v0 = USER`<br>• Test chống audit trail ma khi disk write fail & graceful warning khi append fail<br>• Test patch single match, 0 match, multi match<br>• Test rollback & re-index<br>• Test rollback với `document_id` sai format UUID (trả `INVALID_UUID`, không lẫn `DOCUMENT_NOT_FOUND`)<br>• Test restore missing disk file<br>• Test cleanup 2-layer safety gate, server-side workspace & symlink traversal prevention<br>• Test concurrent version numbering & unique constraint<br>• Test lastrowid vs version correctness & SQL bytes_count + count_document_versions | `tests/test_mcp_version_history.py`<br>`tests/test_mcp_patch_and_cleanup.py` |
| **Phase 5: UI Integration (Optional)** | • Thêm tab/drawer "Lịch sử phiên bản" trên giao diện Flet Desktop<br>• Nút "Dọn dẹp file .bak" trong Settings | `src/ui_flet/` |
