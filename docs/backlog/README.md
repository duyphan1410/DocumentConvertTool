# Technical Backlog & Engineering Tasks

Thư mục này quản lý các hạng mục nợ kỹ thuật (Technical Debt), đề xuất cải tiến (RFCs) và tác vụ tối ưu hóa hiệu năng/kiến trúc cần triển khai trong các đợt phát triển tiếp theo.

---

## 📋 Danh sách Backlog Tasks

| Task ID | Tiêu đề | Phân loại | Độ ưu tiên | Trạng thái | Tài liệu chi tiết |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `PERF-001` | Bounded LRU Cache & Session Eviction cho `_BASE64_CACHE` | Performance / Memory | Medium | 🟢 Completed (v1.8.3) | [PERF_001_base64_cache_lru_eviction.md](PERF_001_base64_cache_lru_eviction.md) |

---

## 📌 Quy chuẩn đặt tên file trong `docs/backlog/`

- Cú pháp: `<CATEGORY>_<INDEX>_<short_description>.md`
  - Ví dụ: `PERF_001_base64_cache_lru_eviction.md`, `REFACTOR_002_xxx.md`, `FEAT_003_xxx.md`
- Mỗi file task phải bao gồm:
  1. Hiện trạng & Phân tích nguyên nhân gốc (Problem Statement)
  2. Thiết kế giải pháp kỹ thuật (Proposed Architecture)
  3. Kế hoạch triển khai & File ảnh hưởng (Implementation Plan)
  4. Tiêu chí nghiệm thu (Acceptance Criteria)
