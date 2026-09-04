# 🏷️ PKB Phase 1: SQLite Index, Wikilinks & Backlinks (v1.10.0)

**Mã định danh**: `PKB-PHASE-1`  
**Phiên bản mục tiêu**: `v1.10.0`  
**Tài liệu mẹ**: [pkb_feature_plan.md](../pkb_feature_plan.md)  
**Phụ trách chính**: 👤 Duy (SQLite Schema, UI Tagging & Backlink View) / 👤 Huy (Link Parser & Tiếng Việt Fuzzy Match Engine)  
**Trạng thái**: ⏳ Planned

---

## 1. Mục tiêu & Phạm vi phát triển

Phase 1 đóng vai trò **nền tảng cốt lõi (Data & Link Foundation)** cho toàn bộ hệ sinh thái Personal Knowledge Base (PKB). Mọi tính năng kế tiếp (MCP Server, Graph View, Obsidian/Claude Export) đều phụ thuộc trực tiếp vào cơ sở dữ liệu và bộ phân giải liên kết được xây dựng trong phase này.

> 💡 **Điểm kế thừa từ hiện trạng (v1.8.1c)**:
> Ứng dụng hiện **đã có** tính năng Smart Drag & Drop từ File Explorer vào Editor (tự động tính relative path và chèn cú pháp Markdown tiêu chuẩn `[Tên](relative/path.md)` hoặc `![Ảnh](path)`), và `PreviewView` đã hỗ trợ click vào link tương đối này để mở tab (`on_open_file`).  
> **Mục tiêu của v1.10.0 là nâng cấp vượt bậc**: hỗ trợ cú pháp hai chiều `[[Tên Note]]` gõ phím tự nhiên kiểu Obsidian (không cần biết đường dẫn), bộ phân giải mờ (Fuzzy Match) tiếng Việt, cảnh báo link hỏng (broken link) và click-to-create tự tạo file mới.

### Các tính năng trong scope:
1. **SQLite Metadata Index**: Lưu trữ metadata của toàn bộ tài liệu, thẻ phân loại (tags), quan hệ tài liệu-thẻ, và liên kết hai chiều (wikilinks).
2. **Manual Wikilinks `[[...]]` Parser**:
   - Cú pháp chuẩn `[[Tên Tài Liệu]]` hoặc `[[Tên Tài Liệu|Tên hiển thị]]`.
   - Bộ đối sánh mờ (Fuzzy Match) tiếng Việt: Bỏ dấu NFD, case-insensitive, tự động chuẩn hóa khoảng trắng.
3. **Broken Link Handling & Click-to-Create**:
   - Cảnh báo trực quan trên Live Preview cho các liên kết chưa tồn tại (màu cảnh báo / nét đứt).
   - Nhấp vào link chưa tồn tại sẽ tự động tạo file `.md` mới trong thư mục đang hoạt động và mở tab mới.
4. **Backlink Panel**:
   - Tích hợp vào Activity Bar một panel chuyên dụng.
   - *Linked References*: Danh sách các văn bản có chứa liên kết `[[...]]` trỏ đến tài liệu hiện tại, kèm đoạn trích dẫn ngữ cảnh (snippet).
   - *Unlinked Mentions*: Phát hiện các văn bản chứa cụm từ khớp với tiêu đề tài liệu hiện tại nhưng chưa gắn cú pháp `[[...]]`, kèm nút "Link" 1-click.
5. **UI Gắn thẻ (Tagging)**:
   - Gắn nhãn thủ công thông qua UI và tự động trích xuất thẻ từ YAML Frontmatter (`tags: [...]`) hoặc `#tag`.

---

## 2. Kiến trúc & Tầng ảnh hưởng

```text
src/
├── services/
│   ├── metadata_index.py        # [NEW] Quản lý kết nối SQLite, CRUD documents/tags/wikilinks
│   ├── link_parser.py           # [NEW] Tokenize cú pháp [[...]], trích xuất links & mentions
│   └── fuzzy_matcher.py         # [NEW] Bỏ dấu tiếng Việt (NFD), Levenshtein / Token similarity
├── ui_flet/
│   ├── views/
│   │   ├── backlink_view.py     # [NEW] View hiển thị Linked References & Unlinked Mentions
│   │   ├── preview_view.py      # [MODIFY] Chặn click wikilink, tô màu link hỏng, điều hướng tab
│   │   └── explorer_view.py     # [MODIFY] Bổ sung bộ lọc theo Tags
│   ├── layout/
│   │   └── activity_bar.py      # [MODIFY] Thêm Icon điều hướng cho Backlink Panel
│   └── controllers/
│       └── file_controller.py   # [MODIFY] Tạo file tự động khi click broken link, sync index khi lưu
```

---

## 3. Chi tiết Kỹ thuật & Data Model

### 3.1. SQLite Index Schema (`%APPDATA%\DocConvert\index.db`)

```sql
-- Bảng tài liệu
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,               -- UUID v4
    path TEXT NOT NULL UNIQUE,          -- Đường dẫn tuyệt đối chuẩn hóa (lowercase trên Windows)
    title TEXT NOT NULL,                -- Tiêu đề (từ frontmatter hoặc tên file không có đuôi)
    content_hash TEXT NOT NULL,         -- SHA-256 nội dung để phát hiện thay đổi
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng danh mục thẻ
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,          -- Tên gốc (VD: "Trí Tuệ Nhân Tạo")
    normalized_name TEXT NOT NULL UNIQUE-- Tên chuẩn hóa (VD: "tri-tue-nhan-tao")
);

-- Quan hệ nhiều-nhiều Document - Tag
CREATE TABLE IF NOT EXISTS document_tags (
    document_id TEXT NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (document_id, tag_id),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- Liên kết hai chiều (Wikilinks)
CREATE TABLE IF NOT EXISTS wikilinks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,            -- Document chứa link
    target_id TEXT,                     -- Document được trỏ tới (NULL nếu là broken link)
    raw_text TEXT NOT NULL,             -- Cụm từ trong [[...]]
    display_text TEXT,                  -- Tên hiển thị (nếu có [[Target|Display]])
    FOREIGN KEY (source_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES documents(id) ON DELETE SET NULL
);

-- Chỉ mục tối ưu truy vấn
CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(path);
CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title);
CREATE INDEX IF NOT EXISTS idx_wikilinks_source ON wikilinks(source_id);
CREATE INDEX IF NOT EXISTS idx_wikilinks_target ON wikilinks(target_id);
CREATE INDEX IF NOT EXISTS idx_tags_normalized ON tags(normalized_name);
```

### 3.2. Thuật toán Fuzzy Match tiếng Việt (`fuzzy_matcher.py`)

1. **Chuẩn hóa chuỗi (NFD Normalization)**:
   ```python
   import unicodedata
   import re

   def normalize_vietnamese(text: str) -> str:
       # Tách tổ hợp ký tự dấu tiếng Việt
       nfkd = unicodedata.normalize('NFKD', text)
       ascii_text = ''.join(c for c in nfkd if not unicodedata.combining(c))
       # Xử lý ký tự đ/Đ đặc trưng
       ascii_text = ascii_text.replace('đ', 'd').replace('Đ', 'D')
       # Lowercase, bỏ ký tự đặc biệt, thu gọn khoảng trắng
       cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', ascii_text).lower().strip()
       return re.sub(r'\s+', ' ', cleaned)
   ```
2. **Chiến lược phân giải đích (Resolution Strategy)**:
   - **Tầng 1 (Exact Match)**: So khớp chính xác theo đường dẫn tương đối hoặc `title`.
   - **Tầng 2 (Normalized Match)**: So khớp theo `normalize_vietnamese(raw_text) == normalize_vietnamese(doc.title)`.
   - **Tầng 3 (Unresolved / Broken Link)**: Gán `target_id = NULL`, chuyển sang trạng thái chờ tạo file.

### 3.3. Click-to-Create & Broken Link Handling

- **Live Preview Rendering**:
  - Khi render Markdown trong `PreviewView`, phân tích các thẻ `[[...]]`.
  - Nếu `target_id` tồn tại: Render dạng link bình thường `[display_text](doc://<target_id>)`.
  - Nếu `target_id` là `NULL`: Render kèm class cảnh báo hoặc định dạng `[⚠️ display_text](doc-create://<raw_text>)`.
- **Hành vi nhấp chuột**:
  - `doc://<target_id>`: `FileController.open_document_by_id(target_id)` mở tab mới trong Workspace.
  - `doc-create://<raw_text>`: Hiển thị dialog xác nhận hoặc tự động tạo `<raw_text>.md` tại thư mục của tệp gốc, chèn tiêu đề mặc định `# <raw_text>`, mở tab và làm mới SQLite index.

---

## 4. UI/UX: Backlink Panel (`backlink_view.py`)

1. **Vị trí**: Panel bên trái (Sidebar), chuyển đổi qua Activity Bar (Icon `ft.Icons.SUBDIRECTORY_ARROW_RIGHT` hoặc `ft.Icons.SHARE`).
2. **Cấu trúc Panel**:
   - **Header**: Tiêu đề tài liệu hiện hành + Tổng số liên kết dẫn về.
   - **Section 1: Linked References (N)**:
     - Danh sách từng tài liệu đang trỏ đến trang hiện tại.
     - Kèm 1-2 dòng văn bản ngữ cảnh xung quanh wikilink, từ khóa được highlight đậm.
   - **Section 2: Unlinked Mentions (M)**:
     - Danh sách các tài liệu có chứa từ khóa là tiêu đề tệp hiện tại nhưng chưa bọc trong `[[...]]`.
     - Nút `[+ Link]` cho phép 1-click tự động thay thế cụm từ đó bằng `[[Tiêu Đề]]` trong tài liệu nguồn.

---

## 5. Rủi ro & Chiến lược Kiểm thử

| Rủi ro | Giải pháp kỹ thuật |
| :--- | :--- |
| **Xung đột tên file trùng lặp** | Khi có 2 file `notes.md` ở 2 folder khác nhau, ưu tiên file cùng thư mục trước; nếu không thì hiển thị đường dẫn thư mục cha để disambiguate. |
| **Tắc nghẽn I/O khi scan lần đầu** | Toàn bộ quá trình quét folder dự án chạy trong background thread (`asyncio.to_thread`), cập nhật tiến độ lên Footer Bar. |
| **Thay đổi file ngoài app** | Sử dụng `content_hash` để chỉ cập nhật các file có hash thay đổi, tránh re-index toàn bộ database. |
