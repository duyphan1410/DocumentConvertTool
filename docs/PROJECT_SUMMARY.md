# DocumentConvertTool - Tóm tắt dự án

## Khởi chạy & Đóng gói ứng dụng

Chạy ứng dụng trực tiếp:

```powershell
python run.py
```

Đóng gói ứng dụng thành file `.exe` thương mại bằng PyInstaller:

```powershell
python -m PyInstaller "Document Converter.spec"
```

Đóng gói bằng Flet Pack CLI (Tùy chọn):

```powershell
flet pack run.py --name "Document Converter" --icon favicon.ico --windowed
```

## Tổng quan

DocumentConvertTool là một ứng dụng desktop viết bằng Python & Flet UI để chỉnh sửa và chuyển đổi tài liệu giữa các định dạng Markdown, Excel (.xlsx), Word (.docx), PDF (.pdf), CSV (.csv) và HTML (.html). Ứng dụng cung cấp một workspace trung tâm dùng Markdown làm ngôn ngữ trao đổi để:

- Tải tài liệu, tự động nhận diện định dạng tệp đầu vào.
- Trích xuất nội dung và hình ảnh liên quan (`@media/`).
- Chỉnh sửa dưới dạng Markdown với bộ công cụ Tìm & Thay thế (Search & Replace), Undo/Redo.
- Xem trước thời gian thực (Live Document Preview) với cơ chế mã hóa Base64 RAM Cache (`_BASE64_CACHE`) và tự động thu nhỏ độ phân giải ảnh (68% scale via `Pillow LANCZOS`).
- Xuất dữ liệu sang định dạng mục tiêu (Excel, Word, PDF, CSV, HTML).

## Mục đích chính

- Chuyển bảng Markdown sang Excel với định dạng và style.
- Chuyển nội dung Markdown sang Word định dạng sẵn.
- Trích xuất worksheet Excel thành bảng Markdown.
- Trích xuất tài liệu Word thành Markdown sạch.
- Trích xuất PDF sang Markdown hỗ trợ gộp bảng liên trang và hình ảnh slide.
- Chuyển đổi hai chiều giữa Markdown và HTML/CSV.
- Cung cấp giao diện desktop Flet UI hiện đại, hỗ trợ chọn file lọc 8 loại tệp đơn lẻ qua Hộp thoại Windows Native FileDialog bất đồng bộ (`asyncio.to_thread`), đổi Palette/Theme 0ms tức thì, và tự động lưu bản nháp (Autosave draft 1.5s).

## Kiến trúc

### Điểm khởi chạy & Giao diện Flet UI (`src/ui_flet/`)

- `run.py`: Script khởi chạy chính, gọi `src.main.main()`.
- `src/main.py`: Cài đặt môi trường hệ thống và khởi tạo ứng dụng giao diện từ `src.ui_flet.app.DocumentConvertApp`.
- `src/ui_flet/app.py`: Triển khai giao diện chính bằng `Flet UI` (Flutter engine for Python).
  - Tự động lọc danh sách Chế độ chuyển đổi (Conversion Mode Dropdown) theo đuôi tệp tin vừa nạp.
  - Tự động lưu nháp ngầm (Autosave Draft) sau 1.5 giây vào `%APPDATA%\DocConvert\draft_autosave.md`.
  - Bộ công cụ Tìm & Thay thế với Smart Hybrid Focus (cycling Enter và chọn ô highlight).
  - Đổi bảng màu Palette (Emerald Obsidian, Violet Cyber, Deep Ocean, Slate Minimal...) và chế độ Light/Dark Mode tức thì (0ms) với cập nhật container độc lập (`header_container`, `left_pane`, `right_pane`, `footer_container`, `btn_convert`, `editor`).
  - Giao diện responsive 2 cột linh hoạt (Editor Buffer & Live Document Preview).
- `src/ui_flet/native_dialogs.py`: Hộp thoại chọn tệp Native Windows File Dialog (`askopenfilename`/`asksaveasfilename`) chạy bất đồng bộ qua `asyncio.to_thread` trên luồng phụ, hiển thị đầy đủ 8 danh mục lọc tệp đơn lẻ (`Word`, `Excel`, `PDF`, `Markdown`, `CSV`, `HTML`, `All Files`) chuẩn xác và sắc nét High-DPI.
- `src/ui_flet/preview.py`: Trình xem trước Live Preview Markdown thời gian thực với cơ chế mã hóa Base64 RAM Cache (`_BASE64_CACHE`) và tự động thu nhỏ độ phân giải ảnh 68% (`Pillow LANCZOS`) cho trải nghiệm cuộn cực mượt.

### Hệ thống Module chuyển đổi (Plugin-based)

Dự án áp dụng thiết kế hướng đăng ký (Registry pattern), tất cả các định dạng tài liệu được đóng gói thành các module kế thừa từ `BaseDocumentModule` và đăng ký với `ModuleRegistry` lúc khởi chạy:

- `src/core/base_module.py`: Định nghĩa lớp cơ sở `BaseDocumentModule` với các phương thức trừu tượng `load_to_markdown` và `save_from_markdown`.
- `src/core/registry.py`: Đăng ký và phân phối các module dựa trên phần mở rộng tệp tin.
- `src/modules/word_module.py`: Trích xuất tài liệu Word `.docx` sang Markdown (dùng `mammoth`) và xuất nội dung Markdown sang `.docx` (dùng `python-docx`).
- `src/modules/excel_module.py`: Trích xuất bảng tính Excel `.xlsx` sang Markdown và xuất Markdown sang Excel `.xlsx` (dùng `openpyxl`).
- `src/modules/csv_module.py`: Trích xuất tệp dữ liệu phẳng `.csv` sang Markdown dạng bảng và xuất ngược lại từ Markdown dạng bảng sang `.csv`.
- `src/modules/pdf_module.py`: Trích xuất file `.pdf` sang Markdown sử dụng `pdfplumber` / `pymupdf` (với thuật toán gộp bảng liên trang, merge ô multiline thông minh và trích xuất ảnh slide).
- `src/modules/html_module.py`: Xuất Markdown sang HTML (dùng `markdown2` kèm CSS phong cách GitHub hỗ trợ Light/Dark mode) và trích xuất HTML sang Markdown (dùng `bs4` / standard parser).

### Kiểm tra và môi trường

- `src/core/validator.py`:
  - `validate_md_tables(content)`: kiểm tra cấu trúc bảng Markdown và trả về cảnh báo nếu bảng không hợp lệ.
  - `validate_file_integrity(file_path)`: kiểm tra chữ ký định dạng tệp đầu vào (như `%PDF` cho PDF).
- `src/utils/env.py`:
  - `setup_environment()`: cấu hình xuất UTF-8 và thiết lập đường dẫn Tcl/Tk cho Python trên Windows.
  - `SetProcessDpiAwareness(2)`: thiết lập DPI Awareness (Per-Monitor v2) cho Windows, đảm bảo hiển thị sắc nét trên mọi màn hình High-DPI.

### Đóng gói ứng dụng

- `Document Converter.spec`: Tệp cấu hình PyInstaller đã tối ưu, loại bỏ các thư viện thừa (`onnxruntime`, `cryptography`, `matplotlib`, `scipy`, `setuptools`, `distutils`, `unittest`, `tkinter.test`) để giảm thời gian build và dung lượng tệp thực thi.

## Các luồng chuyển đổi hỗ trợ

- Markdown (.md) → Excel (.xlsx)
- Markdown (.md) → Word (.docx)
- Markdown (.md) → CSV (.csv)
- Markdown (.md) ↔ HTML (.html)
- Excel (.xlsx) → Markdown (.md)
- Word (.docx) → Markdown (.md)
- CSV (.csv) → Markdown (.md)
- PDF (.pdf) → Markdown (.md)
