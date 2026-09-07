# 2026-09-07 — PKB Phase 1: Tagging, Wikilinks, Backlinks Panel, and Ribbon Home Ergonomics

## 📌 Bối cảnh & Mục tiêu
Cột mốc này đánh dấu bước chuyển mình quan trọng của Document Converter Tool từ một trình chỉnh sửa và chuyển đổi tài liệu độc lập thành một **Personal Knowledge Base (PKB) Studio** hoàn chỉnh. Mục tiêu bao gồm:
1. **Triển khai PKB Giai đoạn 1 (Phase 1 — Data & Link Foundation)**:
   - Hỗ trợ cú pháp ghi chú liên kết hai chiều dạng Obsidian / Roam Research: `[[WikiLink]]`, `[[Target|Alias]]`, `[[Target#Heading]]` và hệ thống nhãn `#tag`, `#nested/tag`, YAML frontmatter `tags: [...]`.
   - Xây dựng chỉ mục đồ thị tri thức trong bộ nhớ (`MetadataIndex`) quản lý liên kết thuận (forward links), liên kết nghịch (backlinks), và các liên kết chưa khởi tạo (unresolved links).
   - Hỗ trợ click điều hướng siêu liên kết Wikilink và cuộn đến đề mục ngay trong khung xem trước `PreviewView`, cảnh báo link hỏng và tự động tạo file mới khi nhấp vào broken link.
   - Bổ sung thanh công cụ `BacklinkView` trên Activity Bar để duyệt mạng lưới liên kết (Linked References), Unlinked Mentions, Unresolved Links và dòng ngữ cảnh.
   - Bổ sung bộ lọc theo nhãn Tag trên thanh tìm kiếm `ExplorerView`.
2. **Tối ưu hóa công thái học Ribbon Bar & Home Button**:
   - Chuyển nút Home (`btn_home`) từ Activity Bar lên vị trí đầu thanh Ribbon Bar (nằm ngay bên trái nút "Mở tệp").
   - Loại bỏ nút Clear Editor thừa trên Ribbon Bar (đã có sẵn trong trình soạn thảo).
3. **Hoàn thiện bản địa hóa động đa ngôn ngữ (i18n Hot-Switching)**:
   - Đồng bộ hóa động toàn bộ văn bản, gợi ý tìm kiếm, nút lọc và mốc thời gian trên `WelcomeView` và `ExplorerView` ngay khi người dùng chuyển đổi ngôn ngữ trong Cài đặt mà không cần khởi động lại ứng dụng.

---

## 🚀 Chi tiết triển khai

### 1. Dịch vụ Chỉ mục Tri thức & Bóc tách Siêu liên kết (`src/services/`)
- **`link_parser.py`**:
  - Module phân tích cú pháp regex chuyên biệt: bóc tách chính xác `[[Target]]`, `[[Target|Alias]]`, `[[Target#Heading|Alias]]`, `#tag`, `#parent/child`.
  - Tự động bỏ qua các khối mã nguồn (code blocks) và khối mã nội dòng (inline code) để tránh nhận diện nhầm.
  - Phân tích YAML Frontmatter ở đầu tài liệu để trích xuất danh sách tags.
- **`metadata_index.py`**:
  - Quản lý cơ sở dữ liệu quan hệ đồ thị tri thức trong bộ nhớ với khóa luồng an toàn (`threading.RLock`).
  - Hỗ trợ đồng bộ hóa toàn diện (`sync_workspace`) và cập nhật vi sai thời gian thực khi chỉnh sửa tài liệu (`update_file_sync`, `remove_file`).
  - Cung cấp API truy vấn: `get_backlinks(path)`, `get_forward_links(path)`, `get_all_tags()`, `search_files_by_tag(tag)`, `get_unresolved_links()`.
- **`fuzzy_matcher.py`**:
  - Thuật toán so khớp mờ linh hoạt (bỏ dấu tiếng Việt NFD, so khớp token) phục vụ cho tìm kiếm và đối sánh liên kết.

### 2. Trình xem trước, Khám phá & Bảng liên kết ngược (`src/ui_flet/views/`)
- **`preview_view.py`**:
  - Chuyển đổi cú pháp `[[...]]` thành các liên kết điều hướng an toàn trong Live Preview.
  - Xử lý sự kiện click liên kết: tự động mở tệp đích, cuộn đến đúng Heading `#section`, hoặc tạo mới tệp nếu chưa tồn tại.
  - Hiển thị tooltip alias và cảnh báo trực quan cho các liên kết chưa tồn tại (unresolved links).
- **`backlink_view.py`**:
  - Giao diện thanh bên chuyên dụng hiển thị:
    - Danh sách các tệp trích dẫn đến tệp hiện tại (Linked References) kèm dòng ngữ cảnh xem trước.
    - Danh sách Unlinked Mentions với thao tác gắn liên kết nhanh.
    - Danh sách các liên kết đi (Outgoing Links) và liên kết gãy/chưa tạo (Unresolved Links).
    - Danh sách các nhãn tag của tệp.
- **`explorer_view.py`**:
  - Tích hợp bộ lọc Tag Filter Dropdown trên cùng một hàng ngang với thanh tìm kiếm tệp.
  - Đồng bộ hóa động danh sách nhãn khi workspace thay đổi.

### 3. Tinh chỉnh Giao diện Ribbon Bar & Activity Bar (`src/ui_flet/layout/`)
- **`ribbon_bar.py`**:
  - Đưa nút Home (`HOME_ROUNDED`) về vị trí ưu tiên cao nhất ở góc trái thanh công cụ, đứng trước "Mở tệp".
  - Loại bỏ nút thùng rác `btn_file_clear` khỏi Ribbon Bar.
- **`activity_bar.py`**:
  - Loại bỏ `item_home` khỏi Activity Bar để tạo không gian thoáng đãng, chuyên biệt cho các công cụ làm việc (Explorer, Backlinks, Settings, Help).

### 4. Nâng cấp Cơ chế Cập nhật Ngôn ngữ Trực tiếp (`i18n`)
- **`welcome_view.py` & `explorer_view.py`**:
  - Cập nhật phương thức `update_locale()` làm mới toàn diện `recent_title_text`, `search_field.hint_text`, `btn_clear_history`, bộ 3 nút lọc `btn_filter_all`, `btn_filter_files`, `btn_filter_folders`, tag filter dropdown, cũng như định dạng thời gian tương đối (`Vừa xong`, `x giờ trước`,...).
  - Đảm bảo tất cả các thành phần cập nhật ngay tức thì khi chuyển ngôn ngữ.

---

## 🧪 Kết quả kiểm thử & Xác minh
- [x] **Layer 1 (Link Parsing & Indexing)**: Kiểm thử regex và phân tích cú pháp tags/wikilinks vượt qua 100% các ca thử phức tạp.
- [x] **Layer 2 (Unit & Smoke Tests)**: 
  - `test_metadata_index.py`: Xác minh tính đúng đắn của đồ thị liên kết hai chiều và đồng bộ vi sai.
  - `test_pkb_ui_smoke.py`: Xác minh khởi tạo an toàn của BacklinkView.
  - Toàn bộ test suite chạy thành công: **215/215 tests passed (100% OK)**.
- [x] **Layer 3 (UI & Ergonomics)**:
  - Nút Home trên Ribbon Bar chuyển đổi mượt mà giữa màn hình chào mừng và trình soạn thảo.
  - Nhấp vào Wikilink trong Preview mở chính xác tệp đích trong tab mới.
  - Chuyển đổi ngôn ngữ Tiếng Việt ⟷ Tiếng Anh cập nhật đồng bộ 100% các thành phần trên giao diện.

---

## 🔍 Phân tích ảnh hưởng & Đánh giá rủi ro
- **Mức độ rủi ro (Blast Radius)**: THẤP (Low) — Các thay đổi được đóng gói thành các dịch vụ độc lập (`MetadataIndex`, `LinkParser`), giao diện kế thừa kiến trúc MVC phân tách rõ ràng và đã vượt qua toàn bộ 215 unit tests.
- **Các thành phần ảnh hưởng**: `src/services/`, `src/ui_flet/views/`, `src/ui_flet/layout/`, `src/i18n/locales/`.
