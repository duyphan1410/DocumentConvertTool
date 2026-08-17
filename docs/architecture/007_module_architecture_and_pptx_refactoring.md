# 🏛️ ADR 007: Document Module Architecture & PPTX Refactoring

**Ngày quyết định:** 13/08/2026  
**Trạng thái:** Accepted & Implemented  
**Tầng tác động:** `src/modules/`, `src/core/converters.py`  

---

## 1. 🎯 Bối Cảnh & Mục Tiêu (Context & Problem Statement)

Ứng dụng **DocumentConvertTool** áp dụng mô hình **3-Tier Architecture** kết hợp với **Dynamic Module Registry Pattern** (`ModuleRegistry`) để quản lý các định dạng chuyển đổi (`PPTX`, `Word`, `Excel`, `CSV`, `PDF`, `HTML`).

Qua quá trình phát triển tính năng chuyển đổi PowerPoint (`v1.6.0`), file `src/modules/pptx_module.py` phát triển lên ~900 dòng code. Mặc dù module hoạt động tốt, cấu trúc nội bộ chứa hơn 10 hàm lồng nhau (nested closure functions) bên trong 2 method chính `load_to_markdown` và `save_from_markdown`. Việc này dẫn tới các vấn đề:
1. **Khó đọc và bảo trì**: Các hàm closure lồng sâu 2-3 tầng trong scope làm luồng code bị phân mảnh và khó theo dõi.
2. **Lặp lại logic bóc tách Bảng Markdown**: Các module `word_module.py`, `pptx_module.py`, `excel_module.py`, `csv_module.py` đều tự viết lại đoạn băm regex pipe (`|`) và lọc dòng phân cách `--|--`.
3. **Lỗi định dạng ô bảng khi export sang Word/PDF**: Đoạn văn bản trong ô bảng chưa được xử lý ký tự ngắt dòng `<br>` và chưa được parse các thuộc tính chữ in đậm, nghiêng, hay link.

---

## 2. 🔍 Các Phương Án Cân Nhắc (Considered Options)

### Phương Án A (Được chọn): Giữ nguyên 1 file `pptx_module.py`, tách closure thành private helper methods
- Tách tất cả 10+ hàm closure lồng nhau thành các private static / class helper method của `PPTXModule` (`_is_smartart_shape`, `_flatten_shapes`, `_split_markdown_into_slide_blocks`, `_get_visual_line_count`, `_parse_formatted_runs`, `_calc_title_geometry`, `_create_continuation_slide`, `_ensure_space`, `_calc_row_h`).
- **Ưu điểm**: Effort thấp, an toàn tuyệt đối, bảo toàn 100% cơ chế tự động đăng ký `ModuleRegistry.register(PPTXModule())`, không thay đổi bất kỳ đường dẫn import ở nơi khác.
- **Nhược điểm**: File vẫn có độ dài ~1000 dòng nhưng cấu trúc đơn nhiệm rõ ràng.

### Phương Án B: Tách `pptx_module.py` thành một package con `src/modules/pptx/`
- Tách ra các file `__init__.py`, `reader.py`, `writer.py`, `utils.py`.
- **Ưu điểm**: Giảm chiều dài dòng của từng file lẻ.
- **Nhược điểm**: Rủi ro cao làm đứt gãy luồng `ModuleRegistry` tự động đăng ký tại khởi động ứng dụng nếu quên import package con; đòi hỏi sửa đổi import ở `file_loader.py`, `conversion_service.py` và `validator.py`.

---

## 3. 🏆 Quyết Định & Nguyên Nhân (Decision & Rationale)

Hệ thống thống nhất chọn **Phương Án A**, đi kèm với việc tái cấu trúc helper bảng dùng chung và chuẩn hóa quy tắc cho toàn bộ 6 module:

1. **Phương Án A cho `pptx_module.py`**:
   - Giữ 1 file `src/modules/pptx_module.py`.
   - Tách trọn vẹn 10 closure functions thành private methods của `PPTXModule`.
   - Luồng chính `load_to_markdown` và `save_from_markdown` trở thành luồng điều phối tuần tự (Sequential Orchestration Flow) cực kỳ rõ ràng qua các khối comment bước `# 1. ... # 2. ...`.

2. **Bổ bổ helper `parse_table_rows()` trong `src/core/converters.py`**:
   - Xây dựng helper `parse_table_rows(table_lines: list[str]) -> list[list[str]]` chuyên bóc tách danh sách dòng bảng Markdown, lọc bỏ dòng phân cách `|---|---|`, strip khoảng trắng cell và padding cột.
   - Các module xử lý bảng inline theo từng vị trí (`word_module.py`, `pptx_module.py`) gọi `parse_table_rows()` trên khối dòng của bảng đó $\rightarrow$ bảo toàn 100% vị trí chèn bảng inline trong văn bản.
   - `parse_md_tables()` (cho Excel/CSV) tái sử dụng `parse_table_rows()`.

3. **Hợp nhất `_parse_formatted_runs` với `parse_inline()` (Phase 3)**:
   - Chuyển `_parse_formatted_runs()` của PPTX sang gọi `parse_inline(text)` từ `converters.py`.
   - Bổ sung gán thuộc tính `run.hyperlink.address = seg.url` giúp các liên kết `[Link](url)` trong slide PPTX tự động chuyển thành Hyperlink nhấp chuột được thực sự.

4. **Sửa lỗi định dạng ô bảng Word & PDF**:
   - **Word**: Xử lý ký tự ngắt dòng `<br>` thành các dòng thực sự trong ô bảng Word và gọi `add_formatted_runs()` để parse chữ in đậm, nghiêng, mã inline.
   - **PDF**: Thêm CSS `th p, td p { margin: 0; padding: 0; }` và `word-break: break-word` triệt tiêu hiện tượng thụt lề 10px bất thường trong ô bảng PDF.

---

## 4. 📊 Phân Tích Uy / Nhược Điểm (Pros & Cons)

### Ưu Điểm:
- **0 Closure Function Lồng Nhau**: Loại bỏ hoàn toàn scope closure bug.
- **Tương Thích Ngược 100%**: Đảm bảo 6/6 module tuân thủ chuẩn `BaseDocumentModule` và `ModuleRegistry`.
- **Bảo Toàn Hyperlink & Định Dạng Inline**: Thống nhất bộ bóc tách `parse_inline()` trên cả Word và PPTX.
- **Tăng Độ Phủ Unit Test**: 47/47 unit test pass 100%.

### Hạn Chế / Trade-offs:
- File `pptx_module.py` có độ dài ~1000 dòng. Tuy nhiên, qua phân tích kiến trúc, độ dài này thuộc về luồng điều phối tuần tự và các helper method đã được cô lập hoàn hảo nên không ảnh hưởng tới khả năng bảo trì.

---

## 5. 🧪 Xác Minh & Thực Nghiệm (Validation Logs)

### 🔹 Kết quả Unit Test
```powershell
python -m unittest discover tests
----------------------------------------------------------------------
Ran 47 tests in 4.064s

OK
```

### 🔹 Bảng Tuân Thủ 6 Document Modules
- `PPTXModule` (`.pptx`) $\rightarrow$ Subclass `BaseDocumentModule`, Lazy Import, Registered
- `WordModule` (`.docx`) $\rightarrow$ Subclass `BaseDocumentModule`, Lazy Import, Registered
- `ExcelModule` (`.xlsx`, `.xls`) $\rightarrow$ Subclass `BaseDocumentModule`, Lazy Import, Registered
- `CSVModule` (`.csv`) $\rightarrow$ Subclass `BaseDocumentModule`, Lazy Import, Registered
- `PDFModule` (`.pdf`) $\rightarrow$ Subclass `BaseDocumentModule`, Lazy Import, Registered
- `HTMLModule` (`.html`, `.htm`) $\rightarrow$ Subclass `BaseDocumentModule`, Lazy Import, Registered
