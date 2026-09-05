# 📦 PKB Phase 4: Export Module (Obsidian Sync & Claude Projects) & AI Auto-Link (v1.13.0)

**Mã định danh**: `PKB-PHASE-4`  
**Phiên bản mục tiêu**: `v1.13.0`  
**Tài liệu mẹ**: [pkb_feature_plan.md](../pkb_feature_plan.md)  
**Phụ thuộc**: Hoàn thành [Phase 1: Tagging & Wikilinks](phase1_tagging_wikilinks.md)  
**Phụ trách chính**: 👤 Duy (Export Writer, Frontmatter Engine & AI Auto-Link Service)  
**Trạng thái**: ⏳ Planned

---

## 1. Mục tiêu & Định hướng Kết nối Hệ sinh thái

Phase 4 hoàn thiện bức tranh Personal Knowledge Base (PKB) bằng cách cung cấp các công cụ **xuất bản và đồng bộ hóa (Interoperability)** đưa kho tri thức sang các nền tảng ghi chú chuyên nghiệp khác (Obsidian) hoặc AI Assistant trên nền tảng đám mây (Claude.ai Projects Web).

### Hai nhánh xuất bản chính:
1. **Obsidian Vault 1-Way Sync**: Ghi trực tiếp các file `.md` chuẩn hóa vào thư mục Vault của Obsidian.
2. **Claude Projects Static Export**: Đóng gói kho tài liệu thành file `.zip` tối ưu hóa riêng cho cơ chế RAG của Claude Projects trên nền tảng Web.
3. **AI Auto-Link Engine**: Bộ gợi ý liên kết thông minh bằng Semantic Embeddings / Local Vector Search.

---

## 2. Chuẩn hóa Định dạng: YAML Frontmatter Thống nhất

Cả 2 nhánh Export đều sử dụng chung một Writer chuẩn hóa để thêm YAML Frontmatter ở đầu mỗi file Markdown:

```markdown
---
title: "Kiến trúc Multi-Tab AppState"
tags: [architecture, flet, python]
created: 2026-09-03 14:30:00
updated: 2026-09-04 09:15:00
docconvert_id: "e4b105a3-7928-44d5-86f3-8b7a421b5d19"
---

# Kiến trúc Multi-Tab AppState
Nội dung tài liệu...
```

- **`docconvert_id`**: Giữ vai trò khóa định danh duy nhất để Obsidian hoặc các công cụ phân tích không bị nhầm lẫn hoặc trùng lặp khi re-export.

---

## 3. Đặc tả Kỹ thuật Hai Nhánh Export

### 3.1. Nhánh 1: Obsidian 1-Way Sync (`src/services/export_service.py`)
- **Use-case**: Người dùng đã có sẵn Obsidian Vault trên máy tính cá nhân và muốn DocConvert đóng vai trò là ingest/converter hub cập nhật dữ liệu sang Obsidian.
- **Cơ chế hoạt động**:
  - Người dùng cấu hình đường dẫn thư mục đích (Obsidian Vault Path) qua Settings hoặc Export Dialog.
  - Đồng bộ **1 chiều** (DocConvert ➔ Obsidian Vault).
  - So khớp `content_hash` trước khi ghi đè để tiết kiệm I/O đĩa cứng và tránh kích hoạt re-index không cần thiết của Obsidian.
  - Chuyển đổi các đường dẫn ảnh tương đối thành định dạng tương thích với cấu trúc attachment của Obsidian.

### 3.2. Nhánh 2: Claude Projects Export (`.zip`)
- **Use-case**: Người dùng sử dụng phiên bản web **claude.ai** (gói Claude Pro / Team / Enterprise) và muốn đưa toàn bộ kho tài liệu vào Project Knowledge.
- **Cơ chế tối ưu cho Claude RAG**:
  - **Giữ nguyên từng file riêng biệt**: Đóng gói thành `.zip` với các file `.md` độc lập, giữ nguyên cấu trúc phân cấp thư mục.
  - **Tuyệt đối KHÔNG gộp thành 1 file khổng lồ**: RAG Retrieval của Claude Projects hoạt động dựa trên việc đánh index và semantic search từng tài liệu nhỏ. Việc gộp chung một file lớn sẽ làm giảm nghiêm trọng độ chính xác truy xuất và dễ chạm trần context window của prompt.
  - **Dữ liệu tĩnh (Static Snapshot)**: Đây là bản snapshot tại thời điểm xuất file. Người dùng sẽ tải file `.zip` này lên claude.ai Projects và thực hiện re-export khi có những cập nhật lớn trong Workspace.

---

## 4. AI Auto-Link Engine (`src/services/ai_link_service.py`)

- **Ý tưởng**: Không chỉ dựa vào liên kết người dùng tự gõ `[[...]]`, AI Auto-Link phân tích ngữ nghĩa nội dung giữa các ghi chú để tự động đề xuất những kết nối tiềm năng.
- **Cơ chế kỹ thuật**:
  - **Tầng 1 (Lightweight / Offline)**: Trích xuất từ khóa bằng TF-IDF kết hợp BM25 cho tài nguyên máy tính hạn chế (0% GPU/RAM overload).
  - **Tầng 2 (Vector Embeddings)**: Sử dụng mô hình Embedding nhỏ chạy cục bộ (như `all-MiniLM-L6-v2` hoặc `bge-small-en-v1.5` qua ONNX Runtime / `fastembed`) để tạo vector cho từng đoạn văn bản.
- **Giao diện người dùng**:
  - Hiển thị danh sách "Gợi ý liên kết tiềm năng" trong Backlink Panel.
  - Người dùng bấm nút `[Chấp nhận liên kết]` để tự động chèn `[[Tên Tài Liệu]]` vào vị trí phù hợp.
