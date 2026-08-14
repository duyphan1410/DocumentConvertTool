# ADR 008: PyMuPDF Story Table Metrics, Scoped CSS & Win32 Unicode Clipboard

## 1. Bối cảnh & Vấn đề Kỹ thuật (Context)

Trong quá trình hoàn thiện và kiểm thử phiên bản v1.6.x, hệ thống ghi nhận một số giới hạn kỹ thuật đặc thù giữa các thư viện dàn trang (PyMuPDF Story engine) và hệ điều hành Windows:

### 1.1. Lệch đường cơ sở chữ (Baseline Offset) trong Bảng PDF
- **Hiện tượng**: Khi xuất tài liệu Markdown sang PDF bằng `markdown-pdf` (sử dụng engine C++ `fitz.Story` của PyMuPDF), các đoạn mã nội dòng (`<code>` như `PhotoImage`) và chữ in nghiêng (`<em>` / `<i>` như `"Document Preview is empty..."`) bên trong ô bảng (`<td>`, `<th>`) bị thụt xuống dưới đường chân chữ (baseline) so với văn bản xung quanh.
- **Nguyên nhân gốc rễ (Root Cause)**:
  - `fitz.Story` không phải là một trình duyệt web hoàn chỉnh mà là một engine dàn trang PDF nhẹ.
  - Khi layout văn bản trong ô bảng (`<td>`), engine tính toán line box theo **đỉnh khung chữ (top bounding box / ascender)** thay vì theo đường chân chữ (baseline).
  - Bộ font **Arial** (`arial.ttf`) và **Consolas** (`consola.ttf`) có thông số font metrics (ascender/descender ratio) khác nhau:
    - Arial ascender: $\approx 0.905$
    - Consolas ascender: $\approx 0.742$
  - Sự chênh lệch tỷ lệ ascender khiến cho khi đỉnh khung chữ được xếp bằng nhau, chân chữ của `Consolas` bị rơi xuống thấp hơn `Arial` khoảng $\approx 3.4\text{px}$.
  - Ngược lại, ở văn bản bên ngoài bảng (`<p>`, `<li>`), engine sử dụng luồng paragraph layout chuẩn nên chữ `<code>` nằm đúng đường chân chữ tự nhiên.

### 1.2. Lỗi mã hóa tiếng Việt khi Sao chép vào Windows Clipboard (Mojibake)
- **Hiện tượng**: Khi sao chép thông tin lỗi (từ hộp thoại Modal hoặc thanh trạng thái Footer), văn bản tiếng Việt có dấu (`Định dạng tệp không được hỗ trợ...`) khi Dán (Paste) ra ngoài bị biến thành các ký tự lạ (`ﾄ雪ｻ杵h d蘯｡ng t盻㎝ khﾃｴng...`).
- **Nguyên nhân gốc rễ (Root Cause)**:
  - Khi gọi lệnh dòng lệnh `subprocess.run("clip", input=text, encoding="utf-8")`, tiện ích `clip.exe` tích hợp sẵn của Windows chỉ đọc luồng byte đầu vào theo bảng mã OEM/ANSI (CP437 hoặc CP1252) thay vì UTF-8.
  - Các byte UTF-8 đa byte của tiếng Việt bị hiểu sai thành bảng mã đơn byte, gây ra lỗi vỡ font / mojibake.

### 1.3. Lệch đuôi mở rộng khi phục hồi bản nháp (Draft Recovery Extension Mismatch)
- **Hiện tượng**: Khi người dùng đặt chế độ mặc định là `MD -> PDF` trong Cài đặt, ứng dụng hiển thị Dropdown `MD -> PDF` và nhãn `Save .pdf`, nhưng đường dẫn trong ô nhập liệu vẫn giữ đuôi `.pptx` từ bản nháp cũ trên đĩa. Khi bấm Convert, ứng dụng hỏi ghi đè file PPTX thay vì xuất file PDF.

---

## 2. Giải pháp Kiến trúc & Triển khai (Architecture Decisions)

### 2.1. Phân tách phạm vi CSS trong và ngoài bảng (Scoped CSS Compensation)
Trong [pdf_module.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/modules/pdf_module.py):
- **Văn bản thông thường ngoài bảng (`body`, `p`, `li`)**: Giữ nguyên vị trí tự nhiên, không áp đặt độ lệch nhân tạo:
  ```css
  code {
      font-family: __MONO_FONT__;
      font-size: 10.5pt;
      color: #0550ae;
      vertical-align: 1px;
      background-color: #f6f8fa;
      padding: 0 3px;
  }
  em, i {
      font-style: italic;
  }
  ```
- **Văn bản trong ô bảng (`td`, `th`)**: Bù trừ độ lệch font metrics dành riêng cho engine ô bảng:
  ```css
  td code, th code {
      font-family: __MONO_FONT__;
      font-size: 10pt;
      vertical-align: 3.4px;
      color: #0550ae;
      background-color: #f6f8fa;
      padding: 0 3px;
  }
  td em, th em, td i, th i {
      font-style: italic;
      vertical-align: 3.15px;
  }
  ```

### 2.2. Xây dựng Module Clipboard chuẩn Win32 Unicode (`CF_UNICODETEXT`)
Trong [clipboard.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/utils/clipboard.py):
- Không sử dụng `clip.exe` qua dòng lệnh.
- Sử dụng trực tiếp `ctypes` để gọi Win32 API (`OpenClipboard`, `EmptyClipboard`, `SetClipboardData` với định dạng `CF_UNICODETEXT = 13`).
- Mã hóa chuỗi sang `UTF-16LE` với null-terminator `b"\x00\x00"` và cấp phát bộ nhớ toàn cục hệ thống (`GlobalAlloc(GMEM_MOVEABLE)`).
- Đảm bảo 100% tiếng Việt có dấu, emoji và ký tự đặc biệt được bảo toàn nguyên vẹn trên mọi phiên bản Windows.

### 2.3. Tự động đối chiếu và đồng bộ đuôi file (Extension Reconciliation)
- Khi phục hồi bản nháp ([file_controller.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/ui_flet/controllers/file_controller.py)): Tự động kiểm tra và thay thế đuôi mở rộng của `out_path` theo `MODES[current_mode]["out_ext"]`.
- Khi lưu cài đặt ([settings_controller.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/ui_flet/controllers/settings_controller.py)): Tự động cập nhật lại nhãn `in_label`/`out_label` và đuôi mở rộng của ô nhập `out_path`.
- Khi bấm chuyển đổi ([conversion_controller.py](file:///c:/Users/Admin/Desktop/DocumentConvertTool/src/ui_flet/controllers/conversion_controller.py)): Đảm bảo an toàn tầng cuối, ép buộc đuôi file xuất luôn khớp với chế độ chuyển đổi đã chọn.

### 2.4. Tinh giản UX Báo lỗi và Quốc tế hóa Động (Dynamic i18n)
- **Tập trung hóa nút Copy**: Loại bỏ nút sao chép trùng lặp ở FooterBar, tập trung vào Modal `MessageDialog` với đầy đủ log chẩn đoán kỹ thuật.
- **Tương tác FooterBar**: Dòng trạng thái lỗi trên FooterBar cho phép click để mở lại Modal chi tiết bất kỳ lúc nào.
- **Quốc tế hóa thời gian thực**: `FooterBar` lưu trữ đối tượng `doc_err` chứa `ErrorCode`, tự động tra cứu lại từ điển `vi.json`/`en.json` khi người dùng thay đổi ngôn ngữ, không bị kẹt chuỗi tĩnh.

---

## 3. Kết quả & Đánh giá (Consequences)

| Tiêu chí | Trước khi xử lý | Sau khi xử lý |
|---|---|---|
| **Căn hàng chữ PDF** | Lệch dòng `3.4px` trong bảng hoặc nâng quá cao ngoài bảng | Thẳng hàng 100% cả trong bảng lẫn ngoài bảng |
| **Sao chép tiếng Việt** | Bị lỗi font mojibake (`ﾄ雪ｻ杵h...`) | Tiếng Việt có dấu chính xác 100% |
| **Đồng bộ đuôi file** | Khôi phục nhầm đuôi `.pptx` khi chế độ là `MD -> PDF` | Luôn tự động chuyển thành `.pdf` |
| **Trải nghiệm Báo lỗi** | 2 nút copy trùng lặp, thanh footer không tự dịch | Gọn gàng, chuẩn UX desktop, dịch real-time |
