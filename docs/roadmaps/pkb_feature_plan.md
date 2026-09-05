# 🗂️ Personal Knowledge Base — Tagging, MCP, Graph & Export — Kế Hoạch Kiến Trúc & Phân Công Kỹ Thuật

**Mã định danh**: `PKB-001`
**Phiên bản phát hành mục tiêu**: `v1.10.0 → v1.13.0` (4 phase độc lập, release tuần tự)
**Ngày cập nhật**: 03/09/2026
**Trạng thái**: ⏳ Planned — chưa bắt đầu

---

## 1. Tầm nhìn Kiến trúc

DocConvert chuyển từ công cụ convert đơn thuần sang **hệ thống Personal Knowledge Base (PKB)**: mọi tài liệu được gắn nhãn, liên kết hai chiều, trực quan hoá dạng đồ thị, và mở "cửa" cho AI assistant (Claude) lẫn ecosystem ghi chú khác (Obsidian) truy cập.

Nguyên tắc xuyên suốt cả 4 phase:
- **Không breaking change** → tất cả release dạng minor (`1.x.0`), không nhảy `2.0.0`.
- **Tagging (Phase 1) là nền tảng bắt buộc** — MCP, Graph, Export đều đọc từ cùng 1 index, không parse lại content riêng lẻ.
- **MCP đặt trước Graph View**: AI (Claude) là consumer chính của PKB (ước lượng tỷ lệ dùng ~10:1 so với người xem trực quan). MCP chỉ cần data layer (Phase 1), không phụ thuộc Graph View — nên ưu tiên phần ROI cao/effort thấp hơn trước.
- **Bảo mật ưu tiên** ở Phase 2 (MCP): không expose raw file path cho model, chỉ dùng `document_id` nội bộ; transport dùng **stdio local**, không mở port/tunnel ra internet.

---

## 2. Ma trận Phân công & Tài liệu Chi tiết (2 người song song)

| Phase | Version | Nội dung chính | Tài liệu chi tiết | Người thực hiện |
| :---: | :---: | :--- | :--- | :---: |
| **1** | v1.10.0 | SQLite index (`documents`, `tags`, `wikilinks`), Wikilinks `[[...]]` fuzzy match VN, UI gắn nhãn | 📄 [phase1_tagging_wikilinks.md](pkb/phase1_tagging_wikilinks.md) | 👤 Duy (schema + UI) / 👤 Huy (fuzzy match algorithm — tái dùng kinh nghiệm `data_module.py`) |
| **2** | v1.11.0 | MCP Server stdio (Python, wrap module hiện có) cho Claude Desktop/Code | 📄 [phase2_mcp_server.md](pkb/phase2_mcp_server.md) | 👤 Huy (tool interface + security validation) — Duy review |
| **3** | v1.12.0 | Graph View (`networkx` layout → SVG render qua Flet, có filter) | 📄 [phase3_graph_view.md](pkb/phase3_graph_view.md) | 👤 Duy (UI/render) — không cần Huy, phụ thuộc thuần vào index Phase 1 |
| **4** | v1.13.0 | Export Module: Obsidian sync (frontmatter `.md`) + Export `.zip` cho claude.ai Projects | 📄 [phase4_export_sync.md](pkb/phase4_export_sync.md) | 👤 Duy (format writer) — song song với Phase 2/3 nếu rảnh sớm |

> Phase 2, 3, 4 đều **phụ thuộc Phase 1 hoàn tất** (giống nguyên tắc Sequential Handoff của Whisper). Cả 3 phase sau độc lập với nhau, có thể chạy song song. Chi tiết từng phase được đặc tả độc lập trong thư mục `docs/roadmaps/pkb/`.

---

## 3. Data Model & Interface

### 3.1. SQLite Index (Phase 1) — `%APPDATA%\DocConvert\index.db`

| Bảng | Cột chính |
| :--- | :--- |
| `documents` | `id`, `path`, `title`, `content_hash`, `updated_at` |
| `tags` | `id`, `name`, `normalized_name` |
| `document_tags` | `document_id`, `tag_id` |
| `wikilinks` | `source_id`, `target_id`, `raw_text` |

**Quyết định cần chốt trước khi code:** rebuild full scan mỗi lần mở app (v1.10.0 ban đầu) → tối ưu incremental theo `content_hash` sau nếu cần.

### 3.2. MCP Server — Transport & Tool Interface (Phase 2)

**Transport: stdio, không phải HTTP/SSE.**

| | stdio (chọn) | HTTP/SSE remote (không làm) |
| :--- | :--- | :--- |
| Cách chạy | Claude Desktop/Code tự spawn `python src/mcp/server.py` làm subprocess | Cần server public, TLS, OAuth token |
| Phạm vi dùng | Chỉ máy đang cài DocConvert | claude.ai web + mọi thiết bị |
| Rủi ro bảo mật | Không network ra ngoài | Phải mở tunnel (ngrok/cloudflare) → toàn bộ vault expose ra internet |
| **Quyết định** | ✅ Dùng — khớp use-case cá nhân/nội bộ, ưu tiên bảo mật | ❌ Không làm trong scope này |

Setup: user tự thêm vào `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "docconvert": {
      "command": "python",
      "args": ["C:/path/to/DocConvert/src/mcp/server.py"]
    }
  }
}
```
Giới hạn cần note cho user: chỉ hoạt động khi Claude Desktop/Code mở trên **cùng máy**; claude.ai bản web không dùng được route này (giải quyết ở Phase 4 — export).

| Tool | Input | Ghi chú bảo mật |
| :--- | :--- | :--- |
| `search_documents` | `query`, `tags?` | read-only |
| `read_document` | `document_id` | không nhận raw `file_path` từ model |
| `convert_document` | `document_id`, `target_format` (enum) | giới hạn format, không cho model chọn output path |
| `tag_document` | `document_id`, `tags[]` | ghi — cần confirm trước khi apply |
| `list_backlinks` | `document_id` | read-only |

### 3.3. Export Module (Phase 4) — dùng chung 1 writer cho 2 output

**Frontmatter chuẩn** (dùng cho cả 2 nhánh export bên dưới):
```yaml
---
title: "..."
tags: [tag1, tag2]
created: 2026-09-03
docconvert_id: "uuid"
---
```

| Nhánh | Output | Use-case | Ghi chú |
| :--- | :--- | :--- | :--- |
| **Obsidian sync** | Ghi thẳng `.md` vào vault folder user chỉ định | User đã có Obsidian vault | Sync **1 chiều** (DocConvert → vault); `docconvert_id` tránh duplicate khi re-export |
| **Claude Projects export** | Đóng gói `.zip` — giữ nguyên cấu trúc thư mục, mỗi note vẫn là 1 file `.md` riêng (không gộp thành 1 file lớn) | User dùng claude.ai bản web | Không gộp file vì Projects dùng RAG retrieval theo từng file nhỏ, gộp 1 file lớn làm giảm hiệu quả truy xuất và dễ chạm giới hạn context. Đây là dữ liệu **tĩnh** — user cần tự re-export/re-upload khi note thay đổi, không live như MCP |

---

## 4. Kế hoạch triển khai tuần tự
 
| Version | Nhiệm vụ chính | Phụ thuộc | Đặc tả kỹ thuật | Trạng thái |
| :---: | :--- | :---: | :--- | :---: |
| **v1.10.0** | SQLite index + Wikilinks `[[...]]` + Manual tagging UI + Broken link handling | — | [phase1_tagging_wikilinks.md](pkb/phase1_tagging_wikilinks.md) | ⏳ Planned |
| **v1.11.0** | MCP server stdio (`search/read/convert/tag/backlinks`) cho Claude Desktop/Code | v1.10.0 | [phase2_mcp_server.md](pkb/phase2_mcp_server.md) | ⏳ Planned |
| **v1.12.0** | Knowledge Graph View (`networkx` + SVG render, filter theo tag/tên/độ sâu, giới hạn 2-hop mặc định) | v1.10.0 | [phase3_graph_view.md](pkb/phase3_graph_view.md) | ⏳ Planned |
| **v1.13.0** | Export Module: Obsidian sync (1 chiều) + Export `.zip` cho claude.ai Projects | v1.10.0 | [phase4_export_sync.md](pkb/phase4_export_sync.md) | ⏳ Planned |

---

## 5. Rủi ro & Điểm cần quyết định

- **Phase 1**: tag nhập tay hay có auto-tag AI? → ảnh hưởng UI, cần chốt trước khi code.
- **Phase 2 (MCP)**: mọi tool nhận `document_id`, validate tồn tại trong index — tránh lỗi path-traversal (tham khảo case GHSA-62gx-5q78-wrvx của plugin Obsidian cộng đồng). Không mở HTTP/tunnel — giữ nguyên stdio.
- **Phase 3 (Graph)**: SVG tĩnh ổn định tới ~100–150 node hiển thị cùng lúc; vượt ngưỡng này cần filter (đã có ở scope) hoặc sau này cân nhắc `pywebview` + Sigma.js nếu cần trải nghiệm kéo-thả như Obsidian.
- **Phase 4 (Export)**: Obsidian sync 1 chiều là giới hạn có chủ đích; Claude Projects export là dữ liệu tĩnh (không live) — cả 2 cần note rõ trong docs user-facing.
