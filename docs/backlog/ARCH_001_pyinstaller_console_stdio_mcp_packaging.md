# 📦 ARCH-001: Hỗ trợ Stdio JSON-RPC cho MCP Server trên Bản Đóng gói PyInstaller

**Mã Task**: `ARCH-001`  
**Phân loại**: Packaging / Architecture  
**Độ ưu tiên**: High  
**Trạng thái**: 🟢 Completed (2026-09-12)  
**Tài liệu liên quan**: [REPORT-PKB-PHASE2-ARCH-REVIEW](../reports/pkb_phase2_mcp_architecture_review.md), [Document Converter.spec](../../Document%20Converter.spec)

---

## 1. Hiện trạng & Vấn đề (Problem Statement)

### Vấn đề:
Khi đóng gói ứng dụng Windows bằng PyInstaller với tùy chọn `console=False` (Windowed GUI subsystem), hệ điều hành Windows không cấp Console Handles cho tiến trình:
- `sys.stdin` nhận giá trị `None`.
- `sys.stdout` nhận giá trị `None`.
- `sys.stderr` nhận giá trị `None`.

### Hậu quả:
Nếu người dùng cấu hình Claude Desktop trỏ vào file phân phối nhị phân `.exe`:
```json
{
  "mcpServers": {
    "docconvert": {
      "command": "C:/Program Files/DocConvert/Document Converter.exe",
      "args": ["--mcp-server"]
    }
  }
}
```
Tiến trình con sẽ bị crash ngay lập tức khi cố gắng đọc `sys.stdin.readline()` hoặc ghi `sys.stdout.write()`.

---

## 2. Phân tích Các Phương án Kỹ thuật & Sự Khác Biệt về Packaging Mode

### Phương án A.1: Multi-Executable chung Directory Bundle (`onedir` Mode)
- **Cơ chế đóng gói**: Sử dụng chế độ **`onedir`** (thư mục chứa executable kèm thư mục `_internal/` chứa shared DLLs).
- **Thiết kế**: Định nghĩa thêm một `EXE` target riêng với `console=True` trong cùng file `.spec`, chia sẻ chung `_internal/` với GUI:
```python
# Target 1: GUI App chính (Windowed)
exe_gui = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Document Converter',
    console=False,
    icon=['assets/icons/app_icon.ico'],
)

# Target 2: Headless MCP Stdio Server cho Claude (Console)
exe_mcp = EXE(
    pyz,
    [('src/mcp/server.py', 'src/mcp/server.py', 'PYSOURCE')],
    [],
    exclude_binaries=True,
    name='docconvert-mcp',
    console=True,  # Bật Console Subsystem để nhận Stdio stream
)

coll = COLLECT(
    exe_gui,
    exe_mcp,
    a.binaries,
    a.datas,
    name='Document Converter',
)
```
- **Ưu điểm**: Đơn giản, không tăng kích thước bộ cài chung (vì tái sử dụng 100% DLLs/assets trong `_internal`).
- **Đặc điểm**: Phù hợp cho bộ cài đặt Desktop tổng hợp (Installer / Zip) cài vào máy người dùng.

---

### Phương án A.2: Tách Analysis Độc lập Thành Single-File Binary (`onefile` Mode)
- **Cơ chế đóng gói**: Sử dụng chế độ **`onefile`** (tự giải nén vào temp, không tạo folder `_internal/`), tạo ra 1 file `.exe` duy nhất hoàn toàn độc lập với app GUI.
- **Thiết kế**: Tạo file spec riêng `DocConvert-MCP.spec` chỉ nạp core MCP và SQLite index:
```python
# DocConvert-MCP.spec (Isolated Standalone Binary ~15MB in 'onefile' mode)
# -*- mode: python ; coding: utf-8 -*-

a_mcp = Analysis(
    ['src/mcp/server.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'src.mcp.server',
        'src.mcp.tools',
        'src.mcp.security',
        'src.services.metadata_index',
        'src.services.fuzzy_matcher',
        'src.services.link_parser',
    ],
    excludes=[
        # Loại trừ toàn bộ GUI & Third-party AI
        'flet', 'flet_desktop', 'webview', 'pythonnet',
        'torch', 'torchaudio', 'faster_whisper', 'ctranslate2',
        'tensorflow', 'matplotlib', 'pandas', 'scipy', 'PyQt5', 'tkinter'
    ],
    noarchive=False,
    optimize=2,
)

pyz_mcp = PYZ(a_mcp.pure)

# Đóng gói 'onefile': đưa thẳng a_mcp.binaries và a_mcp.datas vào EXE() mà không qua COLLECT()
exe_standalone_mcp = EXE(
    pyz_mcp,
    a_mcp.scripts,
    a_mcp.binaries,
    a_mcp.datas,
    [],
    name='docconvert-mcp-standalone',
    debug=False,
    console=True,  # Bắt buộc cho Stdio JSON-RPC
    upx=True,
)
```
- **Ưu điểm**: Tạo ra đúng 1 file `docconvert-mcp-standalone.exe` (~15MB), chuẩn "Zero-Dependency", dễ phân phối độc lập qua GitHub Releases cho người dùng chỉ muốn dùng MCP Server với Claude/Cursor.
- **Nhược điểm**: Mỗi lần chạy tốn vài chục ms giải nén runtime ra thư mục tạm `%TEMP%`.

---

### Phương án B: Runtime Hook tái tạo Console Handles (`AttachConsole`)
Trong `src/mcp/server.py`, trước khi khởi tạo vòng lặp stdio, gọi Windows API để gắn tiến trình vào Console của tiến trình cha (Claude Desktop):
```python
import sys
import ctypes

def ensure_windows_stdio():
    if sys.platform == "win32" and (sys.stdin is None or sys.stdout is None):
        # Attach to parent process console
        ATTACH_PARENT_PROCESS = -1
        if ctypes.windll.kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
            sys.stdin = open("CONIN$", "r", encoding="utf-8")
            sys.stdout = open("CONOUT$", "w", encoding="utf-8")
            sys.stderr = open("CONOUT$", "w", encoding="utf-8")
```
- **Ưu điểm**: Giữ nguyên 1 executable duy nhất, không cần sửa đổi cấu trúc build spec.
- **Nhược điểm**: Tiềm ẩn rủi ro quyền I/O buffer trên một số môi trường sandbox hoặc non-standard shell wrappers.

---

## 3. Tiêu chí Nghiệm thu (Acceptance Criteria)

- [x] Bản build `.exe` hỗ trợ giao tiếp hai chiều JSON-RPC 2.0 với Claude Desktop qua stdio (cả qua `docconvert-mcp.exe` với `console=True` và qua fallback runtime `ensure_windows_stdio`).
- [x] Đã cấu hình multi-executable target trong `Document Converter.spec` (`exe_gui` và `exe_mcp`) và cung cấp `DocConvert-MCP.spec` cho standalone binary.
- [x] Tài liệu cài đặt Claude Desktop được cập nhật đường dẫn chính xác tới file executable hỗ trợ console.

---

## 4. Nhật ký Sửa đổi (Changelog)

- **v1.1 (2026-09-10)**:
  - Làm rõ sự khác biệt về Packaging Mode giữa **A.1 (`onedir` shared bundle)** và **A.2 (`onefile` isolated standalone binary)**.
  - Cung cấp mã nguồn `.spec` chi tiết cho cả hai phương thức.
