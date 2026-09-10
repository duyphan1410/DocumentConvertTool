# ⚡ PERF-003: Lazy Import Entry Points & Tối ưu Cold-Start cho Headless Subprocesses

**Mã Task**: `PERF-003`  
**Phân loại**: Performance / Architecture Refactoring  
**Độ ưu tiên**: High  
**Trạng thái**: 🟡 Ready for Implementation  
**Tài liệu liên quan**: [REPORT-PKB-PHASE2-ARCH-REVIEW](../reports/pkb_phase2_mcp_architecture_review.md)

---

## 1. Hiện trạng & Nguyên nhân Gốc (Problem Statement)

### Vấn đề:
Khi ứng dụng được khởi chạy với cờ headless như `--mcp-server` (dành cho Claude Desktop/Code) hoặc `--youtube-player` (trình phát video độc lập), tiến trình phải chịu thời gian khởi động chậm và tiêu tốn bộ nhớ lớn một cách không cần thiết.

### Đo lường Thực tế:
- **Thời gian nạp (Import Elapsed)**: **3,448.11 ms** (cold-start) / **823.96 ms** (warm cache).
- **Bộ nhớ chiếm dụng tăng thêm**: **+59.93 MB Working Set RAM** và **+63.08 MB Private Bytes** chỉ riêng cho tầng import Flet UI.

### Nguyên nhân:
1. `src/main.py` khai báo `import flet as ft` và `from src.ui_flet.app import main as flet_main` ở top-level, ép Python nạp toàn bộ cây module UI ngay tại thời điểm import.
2. `run.py` import `from src.main import main` trước khi rẽ nhánh, vô hiệu hóa mục đích né import của nó.
3. Logic bắt cờ `--youtube-player` bị duplicate ở cả `run.py` và `src/main.py`.

---

## 2. Thiết kế Kỹ thuật (Proposed Architecture)

### Nguyên tắc:
1. **Single Source of Truth**: Mọi routing dòng lệnh (`sys.argv`) tập trung duy nhất tại hàm `main()` của `src/main.py`.
2. **Lazy Loading**: Chỉ nạp `flet` và `src.ui_flet.app` bên trong nhánh khởi chạy GUI.
3. **Thin Launchers**: `run.py` và `main.py` (root) trở thành các shim wrappers thuần túy (4-5 dòng).

### Sơ đồ luồng:
```text
run.py / main.py (root)
          │
          ▼
   src.main.main()
     ├── sys.argv có '--youtube-player' ──► import youtube_player ──► _run_player_subprocess()
     ├── sys.argv có '--mcp-server'     ──► import mcp.server     ──► mcp_main()
     └── [Mặc định: GUI Mode]           ──► import flet & UI app  ──► ft.app(target=flet_main)
```

---

## 3. Kế hoạch Triển khai (Implementation Plan)

### File 1: `src/main.py`
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
        from src.mcp.server import main as mcp_main
        mcp_main()
        return

    # 3. GUI Mode: Lazy load Flet & App views only when UI is needed
    import flet as ft
    from src.ui_flet.app import main as flet_main
    ft.app(target=flet_main)


if __name__ == "__main__":
    main()
```

### File 2: `run.py`
```python
#!/usr/bin/env python
"""
Launcher script for the Document Converter Workspace.
Run this script to start the application.
"""
from src.main import main

if __name__ == "__main__":
    main()
```

---

## 4. Tiêu chí Nghiệm thu (Acceptance Criteria)

- [ ] Lệnh `python -c "import time; t0=time.perf_counter(); import src.main; t1=time.perf_counter(); print(f'{(t1-t0)*1000:.2f}ms')"` cho kết quả `< 50ms`.
- [ ] Chạy `python run.py --mcp-server` không load bất kỳ module `flet` nào trong `sys.modules`.
- [ ] Chạy `python run.py --youtube-player --help` mở subprocess không load Flet UI.
- [ ] Khởi chạy giao diện chính qua `python run.py` và `flet run .` hoạt động bình thường 100%.
- [ ] Toàn bộ test suite `python -m unittest discover tests` vượt qua 279/279 tests.
