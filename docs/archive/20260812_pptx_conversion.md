# 📌 Nhật Ký Phát Triển & Tổng Kết PR: PowerPoint Module & Universal Dynamic Window Focus

**Ngày thực hiện:** 12/08/2026  
**Tác giả:** duyphan1410  
**Nhánh làm việc:** `feat/duy-12082026-pptx-conversion-enhancements`  
**Phiên bản phát hành:** `v1.6.0`  

---

## 🎯 Mục Tiêu Đợt Phát Triển

Phát triển hoàn chỉnh Plugin chuyển đổi **PowerPoint hai chiều (`PPTX ↔ MD`)**, nâng cấp trải nghiệm người dùng với slide 16:9 Widescreen, xử lý triệt để các edge case (chống tràn slide, căn lề chú thích biểu đồ, trích xuất danh sách đánh số Numbering), gia cố thuật toán Win32 Focus cửa sổ động 100%, và khắc phục toàn bộ các lỗi phát sinh trong hệ thống.

---

## 🚀 Chi Tiết Các Hạng Mục Đã Thực Hiện

### 1. PowerPoint Module (`src/modules/pptx_module.py`)
- **Trích xuất `PPTX ➔ MD`**:
  - Nhận diện tiêu đề (`## Title`), đoạn văn bản và danh sách đánh số **Numbering (`1. `, `2. `)** từ OpenXML `a:buAutoNum`.
  - Bóc tách Biểu đồ (Column, Bar, Pie, Line) ra Bảng Markdown kèm ghi chú chân `<!-- chart: type title="..." legend="..." -->`.
  - Trích xuất ảnh ra thư mục `@media/` và lưu trữ nội dung Slide Notes ở góc dưới slide với định dạng bullet `• `.
- **Tạo PowerPoint `MD ➔ PPTX`**:
  - Mặc định khởi tạo trình chiếu tỷ lệ **16:9 Widescreen (13.333" x 7.5")**.
  - Dựng lại Biểu đồ Native PowerPoint từ Markdown table và chú thích footprint `<!-- chart: ... -->`.
  - Bổ sung khoảng cách/padding cho Hộp chú thích (`include_in_layout = False`), loại bỏ 100% hiện tượng đè chữ lên nhãn cột.
  - Tự động ngắt slide chống tràn nội dung (`ensure_space`) khi tổng chiều cao `top_offset` lấp đầy slide.

### 2. Thuật Toán Win32 Window Focus Động 100% (`src/utils/env.py`)
- Loại bỏ danh sách lớp cửa sổ cứng (`target_classes`).
- Duyệt động tất cả cửa sổ ứng dụng đang chạy dựa trên Tiêu đề (`title`) chứa tên file vừa mở (`testpptx.md`, `testpptx.pdf`...).
- Tương thích linh hoạt 100% với mọi phần mềm trên Windows (VS Code, Obsidian, Typora, Sublime Text, Notepad++, Word, Excel, Chrome...).
- Tự động loại trừ cửa sổ làm việc Antigravity IDE (`if "antigravity" in title: return True`).

### 3. Sửa Lỗi Hệ Thống & Tối Ưu Hóa
- **PyMuPDF TOC Hierarchy Level**: Tự động dịch chuyển cấp độ Mục lục (TOC) về cấp 1 khi văn bản bắt đầu bằng `## Heading 2` để ngăn lỗi PyMuPDF `ValueError: hierarchy level of item 0 must be 1`.
- **Word Exporter `UnboundLocalError`**: Khắc phục dứt điểm lỗi truy cập biến `src_url` ngoài khối điều kiện regex khi xuất file `.docx`.
- **Flet 0.80+ UI Compatibility**: Cập nhật `MessageDialog` sử dụng `content=ft.Text(...)` cho `TextButton`.
- **Auto-Draft Mode Filtering**: Khi ứng dụng khôi phục bản nháp lúc khởi động, menu dropdown "Chế độ chuyển đổi" tự động lọc chính xác các chế độ tương thích với đuôi tệp nháp.

---

## 🧪 Kết Quả Kiểm Thử

- **Unit Tests**: Pass 100% (40/40 tests).
- **Manual QA**: Đã kiểm thử chuyển đổi thành công 2 chiều với các định dạng Word, Excel, PowerPoint, PDF, CSV, HTML.
- **GitNexus Impact Analysis**: Khôi phục trạng thái làm việc sạch sẽ, không có cảnh báo rủi ro cao.
