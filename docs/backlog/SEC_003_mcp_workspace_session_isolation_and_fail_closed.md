# 🛡️ SEC-003: MCP Multi-Client Workspace Session Isolation & Fail-Closed Boundary Enforcement

**Mã Task**: `SEC-003`  
**Phân loại**: Security / Architecture Refactoring  
**Độ ưu tiên**: High  
**Trạng thái**: 🟡 Backlog / Planned  
**Tài liệu liên quan**: [SEC-001](SEC_001_mcp_security_boundary_and_stream_hardening.md), [SEC-002](SEC_002_mcp_client_argument_injection_and_startup_consolidation.md), [FEAT-001](FEAT_001_mcp_document_version_history_and_safe_patch.md)

---

## 1. Hiện trạng & Phân tích Vấn đề Kiến trúc (Problem Statement)

Trong kiến trúc bảo mật hiện tại của DocConvert MCP Server (`src/mcp/security.py`), hàm `get_active_workspace_dir()` phụ thuộc vào một nguồn global duy nhất:
1. Biến môi trường hệ thống `DOCCONVERT_WORKSPACE`
2. Hoặc file cấu hình `%APPDATA%/DocConvert/settings.json`

Mô hình này hoạt động tốt cho kịch bản đơn lẻ (1 client desktop kết nối vào 1 workspace cố định), nhưng bộc lộ 2 lỗ hổng kiến trúc nghiêm trọng khi mở rộng:

---

### Vấn đề 1: Lỗ hổng Fail-Open khi Mất Đường dẫn Workspace (Critical Bug)

Hiện tại, nếu đường dẫn lưu trong `settings.json` bị mất/di dời hoặc `DOCCONVERT_WORKSPACE` không hợp lệ, `get_active_workspace_dir()` sẽ trả về `None`.

Trong `src/mcp/security.py`, hàm kiểm tra ranh giới:
```python
def is_path_in_workspace(target_path: str, workspace_dir: Optional[str] = None) -> bool:
    if not workspace_dir:
        return True  # <-- FAIL-OPEN: Mất hoàn toàn rào chắn bảo vệ!
```
**Hệ quả**: Khi `ws = None`, thay vì từ chối truy cập để bảo vệ hệ thống (`Fail-Closed`), hệ thống lại coi như "không giới hạn workspace" và cho phép các MCP tools đọc/ghi/patch file trên toàn bộ ổ đĩa máy tính người dùng.

---

### Vấn đề 2: Thiếu Cô lập Phiên (Session Isolation) giữa Nhiều Ứng dụng MCP Đồng thời

Khi nhiều ứng dụng AI (Claude Desktop, Cursor, Antigravity IDE, Cline...) cùng kết nối tới DocConvert MCP:
* Toàn bộ các client đều đọc chung `settings.json` global.
* Nếu Client A muốn thao tác trên Project A (`D:/Work/ProjectA`), còn Client B thao tác trên Project B (`D:/Personal/Notes`), hệ thống không có cơ chế phân biệt ngữ cảnh theo từng Session/Connection ID.
* Trạng thái global có thể dẫn tới việc Client B vô tình đọc/ghi nhầm vào workspace của Client A khi workspace bị đổi ngầm trong `settings.json`.

---

## 2. Thiết kế Giải pháp Kỹ thuật (Proposed Architecture)

### 2.1. Chuyển đổi Cơ chế Ranh giới sang Fail-Closed (Strict Boundary)
* `is_path_in_workspace(target_path, workspace_dir)`: Nếu `workspace_dir` là `None` hoặc rỗng $\rightarrow$ **Bắt buộc trả về `False`**.
* Mọi thao tác truy xuất dữ liệu khi chưa xác định được workspace hợp lệ đều bị từ chối với mã lỗi `WORKSPACE_NOT_FOUND` hoặc `ACCESS_DENIED`.

### 2.2. Cơ chế Gán Workspace theo Khởi tạo Phiên (Per-Process / Handshake Binding)
1. **Khởi tạo theo Process Argument (Khuyên dùng cho Stdio MCP)**:
   - Mỗi client khi spawn process `DocConvert-MCP.exe` có thể truyền trực tiếp đối số `--workspace <path>` hoặc env var cục bộ của subprocess đó.
   - MCP Server đọc và khóa cứng `workspace` vào instance của process đó, không đọc ghi đè vào `settings.json` dùng chung.
2. **Khởi tạo qua MCP `initialize` Handshake (Protocol-Level)**:
   - Đọc `rootUri` hoặc `workspaceFolders` trong payload `params.workspaceFolders` của lệnh `initialize` từ MCP Protocol chuẩn.
   - Lưu trữ `session_workspace` trong bộ nhớ của tiến trình MCP Server hiện hành.

---

## 3. Kế hoạch Triển khai (Implementation Roadmap)

| Giai đoạn | Nội dung công việc | File ảnh hưởng |
|---|---|---|
| **Phase 1: Fail-Closed Enforcement** | • Sửa `is_path_in_workspace()` trả về `False` khi `workspace_dir is None`.<br>• Cập nhật các helper `resolve_safe_doc_path()` và `resolve_doc_for_restore()` xử lý nghiêm ngặt case `ws is None`. | `src/mcp/security.py` |
| **Phase 2: Per-Process Workspace CLI Flag** | • Hỗ trợ cờ `--workspace <dir>` khi khởi động `DocConvert-MCP.exe`.<br>• Ưu tiên: `--workspace` CLI arg > `DOCCONVERT_WORKSPACE` process env > `settings.json`. | `src/mcp/server.py`<br>`src/mcp/security.py` |
| **Phase 3: MCP Initialize Root URI Binding** | • Trích xuất `rootUri` / `workspaceFolders` trong request `initialize` của MCP JSON-RPC protocol.<br>• Bind workspace tương ứng vào context của session server hiện hành. | `src/mcp/server.py` |
| **Phase 4: Automated Testing** | • Test case `ws=None` bắt buộc trả `False` (Fail-Closed).<br>• Test khởi động 2 tiến trình MCP với 2 `--workspace` khác nhau đồng thời, xác nhận hoàn toàn cô lập không ảnh hưởng lẫn nhau. | `tests/test_mcp_security.py`<br>`tests/test_mcp_session_isolation.py` |

---

## 4. Tiêu chí Nghiệm thu (Acceptance Criteria)

1. [ ] Khi không có workspace nào được thiết lập hoặc path không tồn tại, mọi request gọi MCP Tool đều fail an toàn (`WORKSPACE_NOT_FOUND`), không bao giờ bypass rào chắn security.
2. [ ] Nhiều client có thể spawn nhiều tiến trình `DocConvert-MCP.exe` trỏ vào các thư mục khác nhau trên cùng một máy mà không bị xung đột ranh giới.
3. [ ] 100% test suites trong hệ thống pass, không hồi quy.
