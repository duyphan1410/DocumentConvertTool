# 🏛️ Báo Cáo Chuẩn Hóa Hệ Thống Báo Lỗi, Bảo Vệ Bản Nháp & Hộp Thoại Modal (v1.6.0)

**Ngày cập nhật:** 06/08/2026  
**Dự án:** Document Converter Tool  
**Nhánh:** `dev`  

---

## 🎯 1. Tổng Quan Mục Tiêu Đã Đạt Được

Đợt nâng cấp này hoàn thành hai mục tiêu kiến trúc trọng yếu của ứng dụng desktop:
1. **Chuẩn hóa Hệ thống Xử lý Lỗi (Error Handling System)**: Đưa toàn bộ ngoại lệ kỹ thuật (`PermissionError`, `BadZipFile`, `FileNotFoundError`...) về dạng chuẩn `DocumentError` phân loại 10 mã `ErrorCode`, tự động tạo gợi ý khắc phục desktop-oriented, hiển thị lên Hộp thoại **Modal Popup (`MessageDialog`)** với nút Sao chép `Error ID` và lệnh `pip` tiện lợi.
2. **Bảo vệ Bản Nháp Tự Động (Autosave Protection & Single Responsibility)**: Tái cấu trúc triệt để cơ chế auto-save draft, phân định rõ hàm `perform_autosave()` (chỉ lưu, không xóa) và `clear_draft_file()` (chỉ xóa khi bấm nút), loại bỏ Race Condition và đảm bảo bản nháp `draft_autosave.md` giữ vĩnh viễn cho đến khi người dùng chủ động xóa.

---

## 📁 2. Danh Sách Tệp Đã Tạo & Cập Nhật

```text
DocumentConvertTool/
├── src/
│   ├── core/
│   │   ├── errors.py                # Enum ErrorCode (10 mã chuẩn) + DocumentError domain exception
│   │   ├── error_mapper.py          # ErrorMapper ánh xạ lỗi theo ngữ cảnh (read/write/convert) & sys.frozen
│   │   └── validator.py             # Validation Pipeline 6 bước (Existence ➔ Type ➔ Ext ➔ Perm ➔ Size ➔ Integrity)
│   ├── utils/
│   │   ├── logger.py                # Ghi log %APPDATA%/DocConvert/logs/YYYY-MM-DD.log & tự dọn log >30 ngày
│   │   └── win32_drag_drop.py       # Hook Win32 HWND & RevokeDragDrop cho kéo thả tệp OS
│   ├── services/
│   │   └── file_loader.py           # Nạp tệp qua Validation Pipeline & trả về DocumentError payload
│   ├── ui_flet/
│   │   ├── components/
│   │   │   ├── message_dialog.py    # Modal AlertDialog báo lỗi chuẩn Theme với expand=True & safe_set_clipboard
│   │   │   └── drag_drop_overlay.py # Form hiển thị vùng thả tệp chuẩn kèm badges định dạng
│   │   ├── controllers/
│   │   │   ├── file_controller.py   # Phân tách perform_autosave & clear_draft_file, nạp tệp qua open_file_by_path
│   │   │   ├── editor_controller.py # Hủy timer đếm ngược trước khi xóa văn bản & dọn draft_autosave.md
│   │   │   └── conversion_controller.py # Bọc lỗi lưu tệp stage="write" vào MessageDialog
│   │   └── layout/
│   │       └── footer_bar.py        # Cập nhật nút Copy Error bằng safe_set_clipboard + subprocess fallback
├── tests/
│   ├── test_error_handling.py       # Suite 10 unit test phủ 10 mã ErrorCode (Ran 10 tests in 0.02s - OK)
│   └── demo_ui_errors.py            # Kịch bản xem thử 10 Modal Báo lỗi trực quan
└── docs/
    └── PR_ERROR_HANDLING_DRAFT_PROTECTION_06082026.md # Báo cáo tổng hợp (Tệp này)
```

---

## ✨ 3. Chi Tiết Các Tính Năng & Tối Ưu Hệ Thống

### 📋 1. Chuẩn Hóa Lỗi Domain (`DocumentError` & `ErrorCode`)
- Định nghĩa 10 mã lỗi chuẩn hóa đại diện cho mọi tình huống sự cố tệp trên Desktop.
- Mỗi đối tượng `DocumentError` tự tạo `Error ID` chuẩn `ERR-YYYYMMDD-XXXX` phục vụ vết nhật ký hỗ trợ kỹ thuật.

#### Bảng Thống Kê Các Mã Lỗi & Hộp Thoại Modal Popup (`MessageDialog`)

| STT | Mã lỗi (`ErrorCode`) | Tình huống xảy ra (Trigger Condition) | Tiêu đề Modal | Lời khuyên & Gợi ý xử lý trên Modal Popup |
|---|---|---|---|---|
| **1** | `FILE_NOT_FOUND` | Nạp hoặc đọc tệp không tồn tại / đã bị di chuyển | **Tệp không tồn tại** | *"Vui lòng kiểm tra lại đường dẫn tệp hoặc di chuyển tệp về đúng vị trí."* |
| **2** | `IS_DIRECTORY` | Kéo-thả hoặc chọn đường dẫn thư mục thay vì tệp | **Thư mục không được hỗ trợ** | *"Vui lòng chọn hoặc kéo thả từng tệp tài liệu cụ thể (.docx, .pdf, .xlsx, .md...)."* |
| **3** | `UNSUPPORTED_EXTENSION` | Chọn tệp có định dạng không được hỗ trợ (.py, .exe...) | **Định dạng tệp không được hỗ trợ** | *"Vui lòng chọn tệp thuộc các định dạng sau: .docx, .pdf, .xlsx, .csv, .md, .html."* |
| **4** | `FILE_LOCKED` | Đọc tệp đang bị khóa do mở trong MS Word / Excel / Acrobat | **Tệp đang bị khóa hoặc bị ứng dụng khác mở** | *"Tài liệu hiện đang mở trong Microsoft Word/Excel. Vui lòng đóng ứng dụng đó và thử lại."* |
| **5** | `READ_ONLY_SAVE_ERROR` | Ghi đè hoặc lưu tệp vào đường dẫn bị từ chối quyền ghi | **Không thể lưu tệp đầu ra** | *"Vui lòng kiểm tra xem tệp đầu ra có đang mở trong MS Excel/Word không, hoặc kiểm tra quyền ghi thư mục."* |
| **6** | `FILE_EMPTY` | Nạp hoặc chọn tệp hoàn toàn rỗng (0 bytes) | **Tệp rỗng (0 bytes)** | *"Vui lòng chọn một tệp tài liệu có nội dung."* |
| **7** | `FILE_TOO_LARGE` | Chọn tệp có dung lượng vượt quá giới hạn 2GB | **Tệp quá lớn (>2GB)** | *"Vui lòng nén hoặc chia nhỏ tài liệu trước khi nạp vào ứng dụng."* |
| **8** | `CORRUPTED_STRUCTURE` | Tệp bị đổi đuôi giả mạo hoặc hỏng cấu trúc nén ZIP OOXML | **Cấu trúc tệp bị hỏng** | *"Hãy mở tệp bằng Microsoft Office và bấm Save As để tự động khôi phục cấu trúc tệp."* |
| **9** | `PASSWORD_PROTECTED` | Tệp bị đặt mật khẩu bảo vệ hoặc là tệp nhị phân legacy .doc/.xls | **Tệp bị mã hóa hoặc đặt mật khẩu** | *"Vui lòng bỏ mật khẩu tệp trong MS Office và chọn định dạng .docx/.xlsx hiện đại."* |
| **10** | `MISSING_DEPENDENCY` | Môi trường Python thiếu thư viện phụ thuộc (`pdfplumber`...) | **Thiếu thư viện phụ thuộc** | Hiển thị nút Sao chép lệnh `pip install <package>` (tự động ẩn nếu chạy từ bản `.exe`). |
| **11** | `UNKNOWN_ERROR` | Ngoại lệ kỹ thuật phát sinh không lường trước (Fallback) | **Đã xảy ra lỗi không xác định** | Hiển thị nút **"Sao chép Log & Error ID"** (`ERR-YYYYMMDD-XXXX`) để gửi báo cáo sự cố. |

### 🎭 2. Tầng Ánh Xạ Thông Minh `ErrorMapper`
- Phân biệt rõ ngữ cảnh thao tác `stage`:
  - Khi đọc tệp (`stage="read"`): Gợi ý *"Vui lòng đóng tệp trong Microsoft Word/Excel"*.
  - Khi lưu tệp (`stage="write"`): Gợi ý *"Ứng dụng bị từ chối quyền ghi, kiểm tra xem tệp xuất đích có đang mở không"*.
- **`sys.frozen` Check**: Tự động phát hiện nếu ứng dụng đóng gói thành file `.exe` độc lập sẽ ẩn hướng dẫn lệnh `pip install` để tránh gây bối rối cho end-user.

### 🛡️ 3. Tái Cấu Trúc Bảo Vệ Bản Nháp (Autosave Protection)
- **Đơn trách nhiệm (Single Responsibility)**:
  - `perform_autosave(self)`: **Chỉ làm đúng nhiệm vụ ghi nhận nội dung văn bản mới**. Tuyệt đối không xóa hay can thiệp vào tệp bản nháp khi ở màn Welcome hay lúc văn bản rỗng.
  - `clear_draft_file(self)`: **Chỉ xóa tệp `draft_autosave.md`** khi được gọi từ thao tác bấm nút "Xóa nội dung" (`clear_editor`).
- **Triệt tiêu Race Condition**: Trong `clear_editor()`, timer tự động đếm ngược `_autosave_timer` bị hủy (cancel) ngay trước khi xóa bộ đệm văn bản, ngăn ngừa triệt để tình trạng timer ghi đè dữ liệu cũ sau khi xóa.

### 🎨 4. Hộp Thoại Modal Popup Báo Lỗi (`MessageDialog`)
- Xây dựng trên `ft.AlertDialog` chuẩn Theme Palette, sử dụng thuộc tính `expand=True` hoàn toàn trên các Text control Flet.
- Hỗ trợ nút **"Sao chép Log & Error ID"** và **"Sao chép lệnh cài đặt"**: Tự động sao chép dữ liệu vào Clipboard an toàn qua `safe_set_clipboard` và **tự động đóng Modal Popup ngay lập tức** giúp người dùng thao tác nhanh chóng.

### 📁 5. Ghi Nhật Ký & Tự Động Xóa Log 30 Ngày
- Module `logger.py` tự động ghi các sự cố vào `%APPDATA%\DocConvert\logs\YYYY-MM-DD.log`.
- Định kỳ quét và xóa các tệp `.log` cũ hơn 30 ngày để tối ưu dung lượng đĩa cứng.

---

## 🧪 4. Kết Quả Kiểm Thử (Verification & Testing)

- **Unit Test Suite (`tests/test_error_handling.py`)**:
  Hoàn thành 10/10 bài test kiểm thử kịch bản lỗi với kết quả `Ran 10 tests in 0.022s - OK`.
- **Thử nghiệm Giao diện (`tests/demo_ui_errors.py`)**:
  Đã kiểm thử mở trực quan từng Modal Popup cho cả 10 mã lỗi trên ứng dụng Flet.
