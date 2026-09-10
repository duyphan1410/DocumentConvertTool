# 📑 Báo cáo Đánh giá Kiến trúc: PKB Phase 2 (Local MCP Server) & Entry Point Analysis

**Mã tài liệu**: `REPORT-PKB-PHASE2-ARCH-REVIEW`  
**Ngày thực hiện**: 2026-09-10  
**Phiên bản kiểm tra**: `v1.11.0`  
**Commit cơ sở**: `b4a1fa72bee34396ebae4a9ce9355601f254724e` (Merge pull request #84 from `feat/huy-10092026-pkb2-mcp-server` vào `dev`)  
**Tài liệu tham chiếu**: [phase2_mcp_server.md](../roadmaps/pkb/phase2_mcp_server.md), [Document Converter.spec](../../Document%20Converter.spec)

---

## Executive Summary (Tóm tắt Cấp cao)

Đợt rà soát kỹ thuật này tập trung kiểm chứng việc hiện thực hóa **PKB Phase 2: Local MCP Server** trong tương quan với toàn bộ kiến trúc codebase của Document Converter Tool.

### Kết luận Tổng quan:
1. **Nghiệp vụ MCP & Giao thức**: 6 tools MCP, cơ chế Dual Framing (line-delimited + Content-Length header), Stdout Isolation và Background Workspace Auto-sync đã được triển khai.
2. **Kiểm thử Xác thực (Test Verification Output)**:
   ```powershell
   PS C:\Users\Admin\Desktop\DocumentConvertTool> python -m unittest discover tests
   ----------------------------------------------------------------------
   Ran 279 tests in 15.029s
   OK
   ```
3. **Lỗ hổng Bảo mật & Sai lệch Spec**:
   - **Thiếu Workspace Boundary Check**: Code `resolve_safe_doc_path()` và 5 call sites trong `tools.py` chưa kiểm tra `os.path.commonpath` với thư mục Workspace như tài liệu đã cam kết.
   - **Tool `write_document_content` ngoài Spec**: Thêm ngoài kế hoạch mà không có cơ chế snapshot/bản sao lưu an toàn khi ghi đè.
   - **`is_valid_uuid` lỏng lẻo**: Chấp nhận mọi version UUID và cả Nil UUID thay vì ép chặt UUID v4 (`u.version == 4`).
4. **Độ ổn định Stream**: `_read_next_message()` dùng đệ quy khi gặp dòng trống/JSON lỗi dẫn đến nguy cơ `RecursionError`; việc redirect `sys.stdout` bị trễ sau các câu lệnh import ở top-level file.
5. **Điểm nghẽn Khởi động (Cold-start & RAM)**: `src/main.py` nạp `flet` và UI ở top-level làm chậm tiến trình con MCP từ 0.8s - 3.4s và tốn thêm ~60MB RAM OS không cần thiết (đo bằng Win32 API `GetProcessMemoryInfo`).
6. **Mâu thuẫn Đóng gói (PyInstaller `console=False`)**: `Document Converter.spec` cấu hình `console=False` triệt tiêu `sys.stdin`/`sys.stdout`, khiến bản build `.exe` đóng gói không thể hoạt động trực tiếp làm MCP Stdio Server.

---

## 1. Bằng chứng Đo đạc & Kiểm chứng Độc lập (Auditable Evidence)

### A. Xác thực Git Commit
```powershell
PS C:\Users\Admin\Desktop\DocumentConvertTool> git log -1 --format="Commit: %H | Author: %an | Date: %ad | Message: %s"
Commit: b4a1fa72bee34396ebae4a9ce9355601f254724e | Author: Duy Phan | Date: Thu Sep 10 13:30:19 2026 +0700 | Message: Merge pull request #84 from duyphan1410/feat/huy-10092026-pkb2-mcp-server
```

---

### B. Đo lường Hiệu năng & Bộ nhớ (Win32 API & Tracemalloc Telemetry)

Đo lường trực tiếp trên Windows 11 bằng Windows Win32 API (`psapi.dll:GetProcessMemoryInfo`):
```powershell
PS C:\Users\Admin\Desktop\DocumentConvertTool> python -c "..."
Import Elapsed (Cold Start / No Cache): 3,448.11 ms
Import Elapsed (Warm Cache .pyc):        823.96 ms
Working Set RAM (Vật lý):                 12.56 MB -> 72.50 MB (Delta: +59.93 MB)
Private Bytes (RAM Commit):               6.09 MB -> 69.18 MB (Delta: +63.08 MB)
Python Heap Allocation (tracemalloc):    Peak 42.32 MB
```

---

### C. Đối chiếu Spec vs Mã nguồn Thực tế

| Thành phần thiết kế | Đặc tả theo Roadmap | Triển khai thực tế | Đánh giá & Rủi ro |
| :--- | :--- | :--- | :---: |
| **Giao thức kết nối** | Stdio JSON-RPC 2.0 (Zero Network Exposure) | `src/mcp/server.py` qua `sys.stdin` / `sys.__stdout__` | ✅ Đạt |
| **Workspace Boundary Check** | Bắt buộc `os.path.commonpath([path, ws]) == ws` | **Chưa có trong `security.py` & call sites `tools.py`** | ❌ **Lệch Spec (Security Gap)** |
| **Định danh UUID v4** | Ép chuẩn UUID v4 định danh tài liệu | Dùng `uuid.UUID()` nhận mọi version/Nil UUID | ⚠️ **Cần siết `u.version == 4`** |
| **Danh mục Tools** | 5 core tools (`search`, `read`, `convert`, `tag`, `backlinks`) | 6 tools (thêm `write_document_content` ghi đè trực tiếp) | ⚠️ **Thiếu Safe Backup/Snapshot** |
| **Độ ổn định Stream** | Chống crash khi client gửi dữ liệu lỗi | Dùng đệ quy trong `_read_next_message()` | ⚠️ **Nguy cơ RecursionError** |
| **Vị trí Redirect Stdout** | Chống corrupt frame JSON-RPC | Đặt trong `main()` sau các top-level import | ⚠️ **Nguy cơ rò rỉ log lúc import** |

---

## 2. Danh mục Backlog Kỹ thuật Đã Khởi tạo

| Mã Task | Tiêu đề | Phân loại | Độ ưu tiên | File chi tiết |
| :--- | :--- | :---: | :---: | :--- |
| **`SEC-001`** | Khắc phục Lỗ hổng Workspace Boundary, Đệ quy Stream & Thắt chặt Bảo mật MCP Server | Security / Robustness | **Critical** | [SEC_001_mcp_security_boundary_and_stream_hardening.md](../backlog/SEC_001_mcp_security_boundary_and_stream_hardening.md) |
| **`PERF-003`** | Lazy Import Entry Points & Tối ưu Cold-Start cho Headless Subprocesses | Performance / Refactoring | **High** | [PERF_003_lazy_import_entrypoints_mcp_coldstart.md](../backlog/PERF_003_lazy_import_entrypoints_mcp_coldstart.md) |
| **`ARCH-001`** | Hỗ trợ Stdio JSON-RPC cho MCP Server trên Bản Đóng gói PyInstaller | Packaging / Architecture | **High** | [ARCH_001_pyinstaller_console_stdio_mcp_packaging.md](../backlog/ARCH_001_pyinstaller_console_stdio_mcp_packaging.md) |
