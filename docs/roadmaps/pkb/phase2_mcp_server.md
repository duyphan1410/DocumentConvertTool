# 🔌 PKB Phase 2: Local MCP Server cho Claude Desktop & Code (v1.11.0)

**Mã định danh**: `PKB-PHASE-2`  
**Phiên bản mục tiêu**: `v1.11.0`  
**Tài liệu mẹ**: [pkb_feature_plan.md](../pkb_feature_plan.md)  
**Phụ thuộc**: Hoàn thành [Phase 1: Tagging & Wikilinks](phase1_tagging_wikilinks.md)  
**Phụ trách chính**: 👤 Huy (Tool Interface & Security Validation) — 👤 Duy (Review & Architecture Alignment)  
**Trạng thái**: ⏳ Planned

---

## 1. Mục tiêu & Triết lý Thiết kế

DocConvert v1.11.0 cung cấp một **Model Context Protocol (MCP) Server** chạy ngầm, biến toàn bộ kho tài liệu cá nhân thành kho tri thức có thể tương tác trực tiếp bởi các trợ lý AI như **Claude Desktop** và **Claude Code**.

### Nguyên tắc thiết kế cốt lõi:
1. **Ưu tiên ROI (MCP trước Graph View)**: AI là người tiêu thụ (consumer) chính của kho tài liệu số với tần suất truy vấn cao gấp nhiều lần so với việc người dùng ngắm đồ thị tri thức. Do đó, MCP được ưu tiên hoàn thành ngay sau khi data layer (Phase 1) sẵn sàng.
2. **Bảo mật tuyệt đối (Zero Network Exposure)**:
   - Sử dụng **stdio transport** (giao tiếp qua standard input/output nội bộ máy tính giữa Claude và tiến trình con Python).
   - Tuyệt đối **không mở HTTP port, không bind socket, không dùng cloudflare tunnel / ngrok** tránh phơi bày dữ liệu ra internet.
3. **Phòng chống Path Traversal (ID-only Surface)**:
   - Các tool tuyệt đối không nhận đường dẫn tệp trực tiếp (`file_path`) từ LLM.
   - Mọi thao tác đều định danh thông qua `document_id` (UUID v4) đã được lập chỉ mục và kiểm duyệt an toàn trong SQLite index của Phase 1.

---

## 2. Kiến trúc Hệ thống

```text
+-------------------------------------------------------------+
| Claude Desktop / Claude Code (Host Application)             |
+-------------------------------------------------------------+
                              │
                    stdin / stdout (JSON-RPC)
                              │
                              ▼
+-------------------------------------------------------------+
| src/mcp/server.py (DocConvert MCP Server Subprocess)        |
|                                                             |
|  ┌──────────────────┐  ┌──────────────────┐  ┌───────────┐  |
|  │ Protocol Handler │  │ Security Guard   │  │ Tool APIs │  |
|  └─────────┬────────┘  └────────┬─────────┘  └─────┬─────┘  |
|            │                    │                  │        |
+------------┼────────────────────┼──────────────────┼--------+
             │                    │                  │
             ▼                    ▼                  ▼
+─────────────────────────────────────────────────────────────+
| DocConvert Core Services & SQLite Index                     |
|  - %APPDATA%\DocConvert\index.db                            |
|  - src/services/metadata_index.py                           |
|  - src/modules/ (word_module, pdf_module, v.v.)             |
+-------------------------------------------------------------+
```

---

## 3. Danh mục & Đặc tả Chi tiết các MCP Tools

### 3.1. `search_documents`
- **Mô tả**: Tìm kiếm tài liệu trong kho dựa trên từ khóa ngữ nghĩa/tiêu đề và danh sách thẻ lọc.
- **Quyền hạn**: Read-only.
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "query": { "type": "string", "description": "Từ khóa tìm kiếm trong tiêu đề hoặc nội dung" },
      "tags": { 
        "type": "array", 
        "items": { "type": "string" }, 
        "description": "Danh sách các tag để lọc (AND condition)" 
      },
      "limit": { "type": "integer", "default": 10, "maximum": 50 }
    },
    "required": ["query"]
  }
  ```
- **Output**: Danh sách các tài liệu khớp kèm `document_id`, `title`, snippet tóm tắt, và danh sách tags.

### 3.2. `read_document`
- **Mô tả**: Đọc toàn bộ nội dung của một tài liệu dựa vào `document_id`.
- **Quyền hạn**: Read-only.
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "document_id": { "type": "string", "format": "uuid", "description": "ID định danh nội bộ của tài liệu" }
    },
    "required": ["document_id"]
  }
  ```
- **Security Check**: Tra cứu `document_id` trong SQLite. Nếu không tồn tại hoặc trỏ ra ngoài workspace được phép, trả lỗi `PERMISSION_DENIED`. Không bao giờ đọc trực tiếp đường dẫn từ bên ngoài.

### 3.3. `convert_document`
- **Mô tả**: Chuyển đổi định dạng của tài liệu hiện có trong kho sang định dạng đích (Markdown, Word, PDF, v.v.).
- **Quyền hạn**: Read / Write (tạo file kết quả an toàn).
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "document_id": { "type": "string", "format": "uuid" },
      "target_format": { 
        "type": "string", 
        "enum": ["md", "docx", "pdf", "html", "json", "yaml", "csv", "txt"] 
      }
    },
    "required": ["document_id", "target_format"]
  }
  ```
- **Xử lý**: Model không được tự chọn nơi ghi file tùy tiện; file kết quả tự động sinh cùng thư mục với tài liệu gốc hoặc thư mục output tiêu chuẩn của Workspace.

### 3.4. `tag_document`
- **Mô tả**: Gắn thêm hoặc xóa các nhãn (tags) của tài liệu trong hệ thống chỉ mục.
- **Quyền hạn**: Write.
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "document_id": { "type": "string", "format": "uuid" },
      "add_tags": { "type": "array", "items": { "type": "string" } },
      "remove_tags": { "type": "array", "items": { "type": "string" } }
    },
    "required": ["document_id"]
  }
  ```

### 3.5. `list_backlinks`
- **Mô tả**: Truy xuất mạng lưới các tài liệu liên kết đến tài liệu hiện tại (Linked References & Unlinked Mentions).
- **Quyền hạn**: Read-only.
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "document_id": { "type": "string", "format": "uuid" }
    },
    "required": ["document_id"]
  }
  ```

---

## 4. Hướng dẫn Cấu hình cho Người Dùng

Người dùng chỉ cần thêm cấu hình sau vào tệp cấu hình của Claude Desktop (`%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "docconvert": {
      "command": "python",
      "args": [
        "C:/Users/Admin/Desktop/DocumentConvertTool/src/mcp/server.py"
      ],
      "env": {
        "DOCCONVERT_INDEX_PATH": "%APPDATA%\\DocConvert\\index.db"
      }
    }
  }
}
```

---

## 5. Rủi ro An ninh & Phòng vệ

1. **Path-traversal Injection (Lỗ hổng kiểu GHSA-62gx-5q78-wrvx)**:
   - Các vụ tấn công trên các plugin Obsidian từng chứng minh việc LLM nhận đường dẫn tệp trực tiếp (`../../Windows/System32/...`) có thể dẫn tới đọc trộm file hệ thống.
   - **Giải pháp**: Tất cả các hàm kiểm tra `document_id` qua câu lệnh `SELECT path FROM documents WHERE id = ?`. Đường dẫn này phải được kiểm tra `os.path.commonpath([doc_path, workspace_root]) == workspace_root` trước khi tiến hành I/O.
2. **Crash cách ly (Fault Isolation)**:
   - Server MCP chạy trên tiến trình riêng biệt với GUI Flet chính, do đó bất kỳ exception nào từ Claude cũng không ảnh hưởng tới phiên làm việc của người dùng trên app desktop.
