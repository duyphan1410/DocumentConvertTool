# Technical Backlog & Engineering Tasks

Thư mục này quản lý các hạng mục nợ kỹ thuật (Technical Debt), đề xuất cải tiến (RFCs) và tác vụ tối ưu hóa hiệu năng/kiến trúc cần triển khai trong các đợt phát triển tiếp theo.

---

## 📋 Danh sách Backlog Tasks

| Task ID | Tiêu đề | Phân loại | Độ ưu tiên | Trạng thái | Tài liệu chi tiết |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `PERF-001` | Bounded LRU Cache & Session Eviction cho `_BASE64_CACHE` | Performance / Memory | Medium | 🟢 Completed (v1.8.3) | [PERF_001_base64_cache_lru_eviction.md](PERF_001_base64_cache_lru_eviction.md) |
| `BUG-001` | Preview Scroll Jump khi Click/Resize Ảnh trong Live Preview | Bug / UX Stabilization | High | 🟢 Completed (v1.8.4) | [BUG_001_preview_scroll_jump_image_click.md](BUG_001_preview_scroll_jump_image_click.md) |
| `PERF-002` | Transient Orphaned Listener Closures during Active Model Downloads | Performance / Memory | Low | 🟡 Backlog / Known-Issue | [PERF_002_whisper_download_listener_weakref.md](PERF_002_whisper_download_listener_weakref.md) |
| `SEC-001` | Khắc phục Lỗ hổng Workspace Boundary, Đệ quy Stream & Thắt chặt Bảo mật MCP Server | Security / Robustness | Critical | 🟢 Completed (PR #85) | [SEC_001_mcp_security_boundary_and_stream_hardening.md](SEC_001_mcp_security_boundary_and_stream_hardening.md) |
| `PERF-003` | Lazy Import Entry Points & Tối ưu Cold-Start cho Headless Subprocesses | Performance / Refactoring | High | 🟢 Completed (PR #85) | [PERF_003_lazy_import_entrypoints_mcp_coldstart.md](PERF_003_lazy_import_entrypoints_mcp_coldstart.md) |
| `ARCH-001` | Hỗ trợ Stdio JSON-RPC cho MCP Server trên Bản Đóng gói PyInstaller | Packaging / Architecture | High | 🟢 Completed (PR #85) | [ARCH_001_pyinstaller_console_stdio_mcp_packaging.md](ARCH_001_pyinstaller_console_stdio_mcp_packaging.md) |
| `SEC-002` | Vá Lỗ hổng Argument Injection `workspace_dir` & Hợp nhất Entry Point MCP | Security / Architecture | **Critical** | 🟡 Ready for Review & Implementation | [SEC_002_mcp_client_argument_injection_and_startup_consolidation.md](SEC_002_mcp_client_argument_injection_and_startup_consolidation.md) |

---

## 📌 Quy chuẩn đặt tên file trong `docs/backlog/`

- Cú pháp: `<CATEGORY>_<INDEX>_<short_description>.md`
  - Ví dụ: `PERF_001_base64_cache_lru_eviction.md`, `REFACTOR_002_xxx.md`, `FEAT_003_xxx.md`
- Mỗi file task phải bao gồm:
  1. Hiện trạng & Phân tích nguyên nhân gốc (Problem Statement)
  2. Thiết kế giải pháp kỹ thuật (Proposed Architecture)
  3. Kế hoạch triển khai & File ảnh hưởng (Implementation Plan)
  4. Tiêu chí nghiệm thu (Acceptance Criteria)
