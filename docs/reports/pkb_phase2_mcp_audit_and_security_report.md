# 📑 Báo cáo Kiểm thử & Đánh giá An ninh: PKB Phase 2 Post-Merge Audit

**Mã tài liệu**: `REPORT-PKB-PHASE2-AUDIT-20260912`  
**Ngày thực hiện**: 2026-09-12  
**Phiên bản kiểm tra**: `v1.11.0`  
**Commit cơ sở**: `aad3baf17f3eb6335cb9a9fee2cea3515e449390` (Merge pull request #85 from `feat/huy-10092026-pkb2-mcp-server` vào `dev`)  
**Tài liệu tham chiếu**: [REPORT-PKB-PHASE2-ARCH-REVIEW](pkb_phase2_mcp_architecture_review.md), [SEC-001](../backlog/SEC_001_mcp_security_boundary_and_stream_hardening.md), [PERF-003](../backlog/PERF_003_lazy_import_entrypoints_mcp_coldstart.md), [ARCH-001](../backlog/ARCH_001_pyinstaller_console_stdio_mcp_packaging.md)

---

## Executive Summary (Tóm tắt Cấp cao)

Báo cáo này tổng hợp kết quả kiểm thử, rà soát an ninh và đánh giá kiến trúc độc lập sau khi tích hợp nhánh `feat/huy-10092026-pkb2-mcp-server` (PR #85) vào nhánh `dev`.

### Kết luận Cốt lõi:
1. **Các hạng mục đã hoàn thành tốt**:
   - Vượt qua **38/38 unit tests** dành riêng cho MCP và MetadataIndex.
   - Stream protocol xử lý bằng vòng lặp phẳng (`while`), giới hạn `MAX_CONTENT_LENGTH = 50MB`, chống tràn stack (`RecursionError`).
   - Ghi đè file qua `write_document_content` đã có cơ chế sao lưu `.bak` và ghi file nguyên tử (`.tmp` + `os.replace`).
   - Đã cấu hình phân tách target đóng gói trong [Document Converter.spec](../../Document%20Converter.spec) và tạo [DocConvert-MCP.spec](../../DocConvert-MCP.spec) cho console MCP.
2. **Lỗ hổng Bảo mật Mới (Critical)**:
   - **Toàn bộ 6/6 MCP Tool Handlers đều bị dính `workspace_dir` Injection**:
     - 5 handlers thao tác dữ liệu: `read_document`, `convert_document`, `tag_document`, `list_backlinks`, `write_document_content`.
     - 1 handler tìm kiếm: `search_documents` (cho phép liệt kê/do thám toàn bộ tài liệu ngoài workspace).
     - Client bên ngoài có thể truyền tham số `workspace_dir` trong JSON-RPC tool arguments để ghi đè ranh giới workspace đã cấu hình (Đã xác minh bằng thực nghiệm PoC cho cả `read_document` và `search_documents`).
3. **Nợ kỹ thuật & Kiến trúc (Medium)**:
   - Trùng lặp chuỗi logic khởi động MCP giữa `src/main.py` và `src/mcp/server.py:main()`.
   - `src/main.py` import trực tiếp hàm private `_trigger_background_workspace_sync` từ `src.mcp.server`.
4. **Phân tích Rà soát `print()` (AST Breakdown & Runtime Verified)**:
   - Phân tích AST toàn bộ thư mục `src/`: Có tổng cộng **228 lệnh `print()`**. Riêng thư mục trọng yếu `src/mcp/` có **0 lệnh `print()`** (toàn bộ logging MCP sử dụng `logger` đẩy ra `stderr`).
   - **100% lệnh `print()` đều nằm trong thân hàm runtime, 0 lệnh ở module-level import**.
   - PoC thực tế chứng minh dòng `print()` runtime được chuyển hướng an toàn vào `stderr`, stream JSON-RPC `real_stdout` hoàn toàn sạch.
5. **Rà soát Đóng gói PyInstaller & Cơ chế Bảo vệ Đa tầng của `convert_document`**:
   - `src/services/conversion_service.py` thực hiện `import src.modules` để tự động đăng ký các plugin converter vào `ModuleRegistry`. **Giữ nguyên 100% file này để bảo vệ tính năng Desktop GUI**.
   - **Mối liên hệ nhân quả về tính an toàn khi chạy MCP**:
     - *Lớp bảo vệ 1 (Format Whitelist)*: `sanitize_target_format()` trong [src/mcp/security.py](../../src/mcp/security.py) chỉ chấp nhận `SUPPORTED_CONVERT_FORMATS = {"docx", "pdf", "html", "json", "yaml", "csv", "txt"}`. Bất kỳ yêu cầu chuyển đổi audio/OCR nào đều bị chặn ngay từ đầu, nên `AudioModule` và `PDFScanModule` **không bao giờ được `ModuleRegistry` lựa chọn thực thi**.
     - *Lớp bảo vệ 2 (Packaging Safety)*: Bản thân `audio_module.py` và `pdf_scan_module.py` có top-level import sạch (không kéo theo AI) và phương thức `save_from_markdown()` rỗng (`raise NotImplementedError`). Do đó, việc thêm 2 module này vào `hiddenimports` của [DocConvert-MCP.spec](../../DocConvert-MCP.spec) là an toàn 100%, không gây xung đột với `excludes=['torch', 'faster_whisper']`, đảm bảo bản build standalone giữ đúng kích thước siêu nhẹ (~15MB Zero-Dependency).

---

## 1. Bằng chứng Thực nghiệm & Kiểm chứng Độc lập

### A. Xác thực Lỗ hổng `workspace_dir` Injection trên `read_document` và `search_documents`

#### 1. PoC trên `read_document` (Đọc trộm file ngoài Workspace)
**Mã kịch bản kiểm thử đầy đủ**:
```python
import tempfile, os, json, io
from src.services.metadata_index import MetadataIndex
from src.mcp.server import MCPServer

with tempfile.TemporaryDirectory() as fake_ws, tempfile.TemporaryDirectory() as outside_dir:
    os.environ['DOCCONVERT_WORKSPACE'] = fake_ws

    secret_file = os.path.join(outside_dir, 'secret.md')
    with open(secret_file, 'w', encoding='utf-8') as f:
        f.write('# TOP SECRET DATA\nPassword=123456')

    idx = MetadataIndex(db_path=os.path.join(fake_ws, 'test.db'))
    doc_id = idx.upsert_document(secret_file, title='Secret', content_hash='abc')

    server = MCPServer(index=idx)
    
    # TEST A: Request bình thường không truyền workspace_dir (Bị chặn bởi resolve_safe_doc_path)
    fake_stdout_a = io.StringIO()
    server.stdout = fake_stdout_a
    server.handle_tools_call(1, {'name': 'read_document', 'arguments': {'document_id': doc_id}})
    out_a = json.loads(fake_stdout_a.getvalue())

    # TEST B: Request độc hại truyền workspace_dir = outside_dir (Vượt rào thành công)
    fake_stdout_b = io.StringIO()
    server.stdout = fake_stdout_b
    server.handle_tools_call(2, {'name': 'read_document', 'arguments': {'document_id': doc_id, 'workspace_dir': outside_dir}})
    out_b = json.loads(fake_stdout_b.getvalue())
```

**Output thực tế**:
```text
[DocConvert-MCP INFO] Executing tool 'read_document' with args: ['document_id']
[DocConvert-MCP INFO] Executing tool 'read_document' with args: ['document_id', 'workspace_dir']

=== TEST A: Request hợp chuẩn (Không truyền workspace_dir) ===
{
  "error": "DOCUMENT_NOT_FOUND",
  "message": "Document ID '7f851e99-021a-4af0-84cc-38f4073fb56a' not found in index, file does not exist, or outside workspace boundary.",
  "document_id": "7f851e99-021a-4af0-84cc-38f4073fb56a"
}

=== TEST B: Request độc hại (Inject arguments.workspace_dir = outside_dir) ===
{
  "document_id": "7f851e99-021a-4af0-84cc-38f4073fb56a",
  "title": "Secret",
  "path": "C:\\Users\\Admin\\AppData\\Local\\Temp\\tmp9qea5zss\\secret.md",
  "tags": [],
  "updated_at": "2026-09-12 05:57:46",
  "content": "# TOP SECRET DATA\nPassword=123456"
}
```

#### 2. PoC trên `search_documents` (Do thám danh mục tài liệu ngoài Workspace)
**Mã kịch bản kiểm thử đầy đủ**:
```python
import tempfile, os, json, io
from src.services.metadata_index import MetadataIndex
from src.mcp.server import MCPServer

with tempfile.TemporaryDirectory() as ws_a, tempfile.TemporaryDirectory() as ws_b:
    os.environ['DOCCONVERT_WORKSPACE'] = ws_a

    doc_a = os.path.join(ws_a, 'doc_a.md')
    with open(doc_a, 'w', encoding='utf-8') as f:
        f.write('# Doc A in Workspace A')
        
    doc_b = os.path.join(ws_b, 'doc_b.md')
    with open(doc_b, 'w', encoding='utf-8') as f:
        f.write('# Doc B in Workspace B (Confidential)')

    idx = MetadataIndex(db_path=os.path.join(ws_a, 'test.db'))
    idx.upsert_document(doc_a, title='Doc A', content_hash='111')
    idx.upsert_document(doc_b, title='Doc B', content_hash='222')

    server = MCPServer(index=idx)

    # TEST 1: Request bình thường (Scoped đúng vào Workspace A)
    fake_stdout_1 = io.StringIO()
    server.stdout = fake_stdout_1
    server.handle_tools_call(1, {'name': 'search_documents', 'arguments': {'query': 'Doc'}})
    res_1 = json.loads(fake_stdout_1.getvalue())

    # TEST 2: Request độc hại (Inject workspace_dir = Workspace B -> LỘ TÀI LIỆU B)
    fake_stdout_2 = io.StringIO()
    server.stdout = fake_stdout_2
    server.handle_tools_call(2, {'name': 'search_documents', 'arguments': {'query': 'Doc', 'workspace_dir': ws_b}})
    res_2 = json.loads(fake_stdout_2.getvalue())
```

**Output thực tế**:
```text
[DocConvert-MCP INFO] Executing tool 'search_documents' with args: ['query']
[DocConvert-MCP INFO] Executing tool 'search_documents' with args: ['query', 'workspace_dir']

=== TEST 1: search_documents KHÔNG inject (Scoped đúng vào Workspace A) ===
{
  "query": "Doc",
  "tags_filter": [],
  "total_matches": 1,
  "results": [
    {
      "document_id": "86fd999f-3a94-4814-a163-d25444bf9099",
      "title": "Doc A",
      "path": "C:\\Users\\Admin\\AppData\\Local\\Temp\\tmpkdi0vitd\\doc_a.md",
      "relevance_score": 0.928
    }
  ]
}

=== TEST 2: search_documents CÓ inject (workspace_dir = Workspace B -> LỘ TÀI LIỆU B) ===
{
  "query": "Doc",
  "tags_filter": [],
  "total_matches": 1,
  "results": [
    {
      "document_id": "84c07f2e-4e06-43b2-8ab9-caeb5fe79f00",
      "title": "Doc B",
      "path": "C:\\Users\\Admin\\AppData\\Local\\Temp\\tmpn66gstku\\doc_b.md",
      "relevance_score": 0.928
    }
  ]
}
```

---

### B. Chi tiết Phân bổ Lệnh `print()` qua Phân tích Cú pháp AST Toàn Codebase

Thống kê chi tiết số lượng lời gọi hàm `print()` theo từng thư mục con trong `src/`:

```powershell
PS C:\Users\Admin\Desktop\DocumentConvertTool> python -c "import ast, os; ..."
- src/mcp (server.py, tools.py, security.py): 0 print() calls (Thuần túy dùng logging -> stderr)
- src/services:                               63 print() calls
- src/ui_flet/controllers:                    41 print() calls
- src/modules:                                37 print() calls
- src/ui_flet/views:                          35 print() calls
- src/ui_flet (root):                         22 print() calls
- src/utils:                                  16 print() calls
- src/ui_flet/components:                      8 print() calls
- src/core:                                    3 print() calls
- src/i18n:                                    2 print() calls
- src/ui_flet/layout:                          1 print() calls
--------------------------------------------------------------------------------
Tổng cộng toàn bộ src/:                     228 print() calls
Số lệnh ở top-level import time:               0
```

* **Kết luận**:
  * Thư mục `src/mcp/` đạt chuẩn an toàn tuyệt đối với 0 lệnh `print()`.
  * Toàn bộ 228 lệnh `print()` ở các module khác đều là log debug/runtime bên trong các hàm xử lý. Khi MCP Server chạy với `sys.stdout = sys.stderr`, tất cả output này đều bị chuyển hướng sang `stderr`, đảm bảo luồng `real_stdout` JSON-RPC không bị ảnh hưởng.

---

### C. Đối soát Mã nguồn Khởi động: `src/main.py` vs `src/mcp/server.py`

| Thành phần khởi động | [src/main.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/main.py#L12-L26) | [src/mcp/server.py:main()](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/mcp/server.py#L256-L271) | Đánh giá |
| :--- | :--- | :--- | :---: |
| `ensure_windows_stdio()` | Có gọi | Có gọi | Trùng lặp |
| `real_stdout = sys.__stdout__; sys.stdout = sys.stderr` | Có gọi | Có gọi | Trùng lặp |
| `index = MetadataIndex.get_instance()` | Có gọi | Có gọi | Trùng lặp |
| `_trigger_background_workspace_sync(index)` | Import & gọi hàm private | Định nghĩa & gọi nội bộ | Vi phạm Encapsulation |
| `MCPServer(..., stdout_stream=real_stdout).run_forever()` | Có gọi | Có gọi | Trùng lặp |

---

## 2. Ghi nhận Tài liệu & Giao diện Dòng lệnh (Documentation & DX Notes)

1. **Độ lệch về cờ `--help` trong PR Description**:
   - PR Description ghi nhận: *"chuyển toàn bộ cờ `--mcp` và `--help` về `src/main.py`"*.
   - Hiện trạng mã nguồn: Cả `run.py` và `src/main.py` chưa từng có code xử lý `--help` / `-h`. Khi gõ `python run.py --help`, tiến trình khởi chạy Desktop GUI Flet mặc định.
   - Ghi nhận: Cần bổ sung xử lý `--help` trong các đợt hoàn thiện CLI/DX tiếp theo.
2. **Lỗi chính tả trong Commit `691a58c`**:
   - Commit message chứa từ trùng: `"DOCCONVERT_INDEX_PATH env supportsupport"`.

---

## 3. Kế hoạch Hành động & Backlog Tasks

| Mã Task | Tiêu đề | Phân loại | Độ ưu tiên | File chi tiết |
| :--- | :--- | :---: | :---: | :--- |
| **`SEC-002`** | Vá Lỗ hổng Argument Injection `workspace_dir` (6 Tools) & Hợp nhất Entry Point MCP | Security / Architecture | **Critical** | [SEC_002_mcp_client_argument_injection_and_startup_consolidation.md](../backlog/SEC_002_mcp_client_argument_injection_and_startup_consolidation.md) |
