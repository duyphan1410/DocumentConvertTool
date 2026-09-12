# 🛡️ SEC-002: Vá Lỗ hổng Argument Injection `workspace_dir` (6 Tools) & Hợp nhất Entry Point MCP

**Mã Task**: `SEC-002`  
**Phân loại**: Security / Architecture Refactoring  
**Độ ưu tiên**: Critical  
**Trạng thái**: 🟡 Ready for Implementation / Review  
**Tài liệu liên quan**: [REPORT-PKB-PHASE2-AUDIT-20260912](../reports/pkb_phase2_mcp_audit_and_security_report.md), [SEC-001](SEC_001_mcp_security_boundary_and_stream_hardening.md)

---

## 1. Hiện trạng & Lỗ hổng Bảo mật (Problem Statement)

### Lỗ hổng 1: Client JSON-RPC Override `workspace_dir` trên toàn bộ 6 MCP Tool Handlers
* **Hiện trạng**:
  * Trong `src/mcp/server.py`, hàm `handle_tools_call()` dispatch tool bằng: `handler(**arguments, index=self.index)`.
  * Trong `src/mcp/tools.py`, **tất cả 6 handlers** đều khai báo tham số phụ trợ `workspace_dir: Optional[str] = None`:
    1. `handle_search_documents(query, tags, limit, index, workspace_dir)`
    2. `handle_read_document(document_id, index, workspace_dir)`
    3. `handle_convert_document(document_id, target_format, index, workspace_dir)`
    4. `handle_tag_document(document_id, add_tags, remove_tags, index, workspace_dir)`
    5. `handle_list_backlinks(document_id, index, workspace_dir)`
    6. `handle_write_document_content(document_id, content, create_backup, index, workspace_dir)`
* **Cơ chế Khai thác**:
  * Khi client gửi payload `tools/call` kèm `"workspace_dir": "C:\\"`, Python giải nén `**arguments` và truyền `workspace_dir="C:\\"` vào handler.
  * **Hậu quả**:
    * Đối với `search_documents`: Client liệt kê và do thám được toàn bộ tài liệu đã index trên toàn bộ ổ đĩa.
    * Đối với 5 handlers còn lại: `resolve_safe_doc_path` sử dụng `workspace_dir="C:\\"` từ client, khiến điều kiện `os.path.commonpath([doc_path, "C:\\"]) == "C:\\"` luôn đúng, vô hiệu hóa hoàn toàn cơ chế kiểm soát ranh giới workspace của SEC-001.

### Lỗ hổng 2: Trùng lặp logic khởi động MCP & Import hàm private trong `src/main.py`
* **Hiện trạng**:
  * `src/main.py` import `_trigger_background_workspace_sync` (vi phạm encapsulation) và tự lặp lại toàn bộ chuỗi khởi tạo `MCPServer` thay vì ủy quyền cho `src.mcp.server.main()`.
  * Tiềm ẩn rủi ro sai lệch hành vi (Behavior Drift) giữa các cách khởi chạy khác nhau.

---

## 2. Thiết kế Giải pháp Kỹ thuật (Remediation Design)

### 2.1. Phòng thủ 2 Lớp Thực chất (True Defense-in-Depth & Clean Signature)

Nhằm loại bỏ hoàn toàn "Single Point of Failure" lẫn "Code Smell Test Hooks", kiến trúc được thiết kế lại chuẩn hóa như sau:

#### Lớp 1 (Gateway Schema Whitelist tại `src/mcp/server.py`):
`handle_tools_call()` trích xuất danh sách properties hợp lệ từ `MCP_TOOLS_MANIFEST` và lọc sạch toàn bộ arguments:
```python
manifest_tool = next((t for t in MCP_TOOLS_MANIFEST if t["name"] == tool_name), None)
allowed_props = set(manifest_tool.get("inputSchema", {}).get("properties", {}).keys()) if manifest_tool else set()

# Loại bỏ mọi key lạ/injection ngoài schema
sanitized_args = {k: v for k, v in arguments.items() if k in allowed_props}
tool_output = handler(**sanitized_args, index=self.index)
```

#### Lớp 2 (Loại bỏ Triệt để `workspace_dir` khỏi Signature của cả 6 Handlers tại `src/mcp/tools.py`):
- **Xóa hoàn toàn** tham số `workspace_dir` khỏi signature và thân hàm của cả 6 handlers. Signature của mỗi handler sẽ phản ánh 1:1 chuẩn mực theo đúng `MCP_TOOLS_MANIFEST` + `index`:
  1. `handle_search_documents(query: Optional[str] = None, tags: Optional[List[str]] = None, limit: int = 10, index: Optional[MetadataIndex] = None) -> Dict[str, Any]`
  2. `handle_read_document(document_id: str, index: Optional[MetadataIndex] = None) -> Dict[str, Any]`
  3. `handle_convert_document(document_id: str, target_format: str, index: Optional[MetadataIndex] = None) -> Dict[str, Any]`
  4. `handle_tag_document(document_id: str, add_tags: Optional[List[str]] = None, remove_tags: Optional[List[str]] = None, index: Optional[MetadataIndex] = None) -> Dict[str, Any]`
  5. `handle_list_backlinks(document_id: str, index: Optional[MetadataIndex] = None) -> Dict[str, Any]`
  6. `handle_write_document_content(document_id: str, content: str, create_backup: bool = True, index: Optional[MetadataIndex] = None) -> Dict[str, Any]`
- **Cơ chế xác định Workspace**: Cả 6 handlers và `resolve_safe_doc_path()` nội bộ tự động lấy workspace thông qua hàm trung tâm `get_active_workspace_dir()` từ `src.mcp.security`.
- **Cơ chế Unit Test**: Trong `tests/test_mcp_tools.py`, kiểm thử cách ly workspace bằng cách gán biến môi trường `os.environ["DOCCONVERT_WORKSPACE"] = other_dir` (hoặc `mock.patch('src.mcp.security.get_active_workspace_dir')`), **không tạo test hook làm ô nhiễm production signature**.

### 2.2. Hợp nhất Entry Point & Đảm bảo An toàn Redirect Stdout
* **Refactor trong `src/main.py`**:
  ```python
  # 2. Headless Subprocess: Local MCP Stdio Server for Claude Desktop & IDEs
  if "--mcp-server" in sys.argv:
      from src.mcp.server import main as run_mcp_server
      run_mcp_server()
      return
  ```
* **Đảm bảo An toàn Redirect**: Hàm `src.mcp.server.main()` thực hiện `ensure_windows_stdio()` và `sys.stdout = sys.stderr` ngay đầu hàm. Phân tích AST xác nhận `src/mcp/` có **0 lệnh `print()`** nên không có nguy cơ rò rỉ stdout.

### 2.3. Tính Toàn vẹn Đóng gói PyInstaller & Bảo tồn Registry Desktop GUI
- **Bảo tồn `src/services/conversion_service.py`**: Giữ nguyên câu lệnh `import src.modules` trong `conversion_service.py` để đảm bảo `ModuleRegistry.register(...)` của toàn bộ các converter plugins (bao gồm cả Audio và OCR trên GUI) hoạt động bình thường trên ứng dụng chính.
- **Bổ sung `hiddenimports` trong `DocConvert-MCP.spec`**:
  Thêm tường minh `'src.modules.audio_module'` và `'src.modules.pdf_scan_module'` vào `hiddenimports` của [DocConvert-MCP.spec](../../DocConvert-MCP.spec).
  - *Lý do an toàn*: Cả 2 module này chỉ lazy import runtime dependencies (`faster_whisper`, `torch`, `easyocr`) bên trong method `load_to_markdown()`. Khi chạy MCP Server, chỉ có phương thức `save_from_markdown()` của các target formats được gọi, nên PyInstaller có thể loại trừ các thư viện AI nặng mà không gây bất kỳ lỗi import hay phình to kích thước bundle nào.

---

## 3. Danh sách File Ảnh hưởng (Affected Files)

- [src/mcp/server.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/mcp/server.py): Thêm schema-based argument filtering trong `handle_tools_call`.
- [src/mcp/tools.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/mcp/tools.py): Xóa bỏ hoàn toàn tham số `workspace_dir` khỏi signature và thân hàm của toàn bộ 6 handlers, chuẩn hóa fallback `get_active_workspace_dir()`.
- [src/main.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/main.py): Gọn hóa nhánh `--mcp-server` thành ủy quyền gọi `src.mcp.server.main()`.
- [DocConvert-MCP.spec](file:///c:/Users/Admin/Desktop/DocumentConvertTool/DocConvert-MCP.spec): Bổ sung `audio_module` và `pdf_scan_module` vào `hiddenimports` đảm bảo đầy đủ module discovery.
- [tests/test_mcp_tools.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/tests/test_mcp_tools.py): Cập nhật các test workspace boundary sử dụng `DOCCONVERT_WORKSPACE` env var thay vì tham số hàm.
- [tests/test_mcp_server.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/tests/test_mcp_server.py): Bổ sung bộ test table-driven 2 bước (Positive Control vs Boundary Injection) cho toàn bộ 6 tools.

---

## 4. Tiêu chí Nghiệm thu (Acceptance Criteria)

### A. Phương pháp Kiểm thử Chống Test Giả (Robust Invariant Verification)
Mỗi test case injection trong `tests/test_mcp_server.py` bắt buộc phải triển khai theo phương pháp kiểm chứng 2 bước độc lập:
1. **Positive Control (Kiểm chứng Hợp lệ)**: Tạo file vật lý tại `Path_outside`, index vào database. Khi đặt `DOCCONVERT_WORKSPACE = Path_outside`, tool tương ứng PHẢI THỰC THI THÀNH CÔNG (đọc đúng nội dung, chuyển đổi đúng file, gắn đúng tag).
2. **Experiment Test (Kiểm chứng Injection bị Chặn)**: Chuyển active workspace sang `Path_active` ($Path_{active} \ne Path_{outside}$). Gửi JSON-RPC `tools/call` kèm injection key `"workspace_dir": Path_outside`. Tool PHẢI BỊ CHẶN vì file nằm ngoài `Path_active`, chứng minh tham số inject bị vô hiệu hóa.

> ⚠️ **Lưu ý triển khai cho Test Case `convert_document`**: Bắt buộc phải thực hiện assertion `self.assertFalse(os.path.exists(expected_out_file))` **TRƯỚC KHI** context manager `tempfile.TemporaryDirectory()` thoát và xóa thư mục tạm, để đảm bảo phát hiện chính xác mọi hành vi rò rỉ ghi file ra đĩa.

### B. Checklist Nghiệm thu Chi tiết:
- [ ] **Table-Driven Injection Tests (Cả 6 Tools)**:
  1. `search_documents`: Đặt workspace A, inject workspace B $\rightarrow$ Chỉ trả về kết quả thuộc workspace A (loại trừ file workspace B).
  2. `read_document`: File hợp lệ tại workspace B, active tại workspace A, inject workspace B $\rightarrow$ Trả về `DOCUMENT_NOT_FOUND` / boundary check failure.
  3. `convert_document`: File hợp lệ tại workspace B, active tại workspace A, inject workspace B $\rightarrow$ Trả về `DOCUMENT_NOT_FOUND` và KHÔNG sinh file output trên đĩa (kiểm tra trước khi cleanup dir).
  4. `tag_document`: File hợp lệ tại workspace B, active tại workspace A, inject workspace B $\rightarrow$ Trả về `DOCUMENT_NOT_FOUND` và KHÔNG sửa đổi tag trong database.
  5. `list_backlinks`: File hợp lệ tại workspace B, active tại workspace A, inject workspace B $\rightarrow$ Trả về `DOCUMENT_NOT_FOUND` và KHÔNG tiết lộ liên kết tài liệu.
  6. `write_document_content`: File hợp lệ tại workspace B, active tại workspace A, inject workspace B $\rightarrow$ Trả về `DOCUMENT_NOT_FOUND` và KHÔNG sửa đổi/tạo file `.bak` trên đĩa.
- [ ] **Clean Signature & Type Safety (Lớp 2)**: Toàn bộ 6 hàm handler trong `src/mcp/tools.py` không còn tham số `workspace_dir`. Gọi hàm trực tiếp với `workspace_dir` sẽ bị chặn ngay bởi `TypeError` ở cấp độ Python.
- [ ] **Unit Tests Passing**: Toàn bộ test suite `python -m unittest tests.test_metadata_index tests.test_mcp_security tests.test_mcp_server tests.test_mcp_tools` vượt qua 100%.
- [ ] **Clean Encapsulation**: `src/main.py` không còn import bất kỳ hàm nội bộ private nào (tiền tố `_`).
- [ ] **Single Entry Point**: Toàn bộ logic khởi động MCP được gom về 1 điểm duy nhất tại `src/mcp/server.py:main()`.
- [ ] **Measurable Packaging Integrity**: `DocConvert-MCP.spec` phân tích thành công không phát sinh `ModuleNotFoundError`, và `excludes` loại trừ triệt để `torch`, `faster_whisper` giữ kích thước nhị phân mục tiêu.
