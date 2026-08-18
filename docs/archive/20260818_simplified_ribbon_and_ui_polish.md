# 📦 PR Summary & Technical Report: Simplified Single-Row Ribbon & UI Polish (v1.7.0)

**Ngày thực hiện:** 18/08/2026  
**Nhánh:** `feat/duy-18082026-simplified-ribbon` ➔ `dev`  
**Phiên bản:** `v1.7.0`  

---

## 🎯 Mục Tiêu

Nâng cấp giao diện lên phiên bản **v1.7.0** với thanh **Simplified Single-Row Ribbon Bar (38–40px)** tinh gọn, tối ưu diện tích dọc theo chuẩn UX 4/8dp rhythm và 100% Vector Icons `ft.Icons.*`, bổ sung bộ hàm chọn thư mục dự án **Folder Native Picker**, chuẩn hóa toàn diện hệ thống **Typography Scale** (11–16px), và tái thiết kế màn hình **Help View** sang bố cục Card Grid 2 Cột chuyên nghiệp.

---

## 🚀 Các Thay Đổi Chính

### 1. Simplified Single-Row Ribbon Bar & Dynamic States (`src/ui_flet/layout/ribbon_bar.py`, `layout_controller.py`)
- Chuyển đổi Ribbon từ mô hình 2 tầng (~100px) sang **1 hàng duy nhất cao 38–40px** đặt ngay phía trên Editor, tiết kiệm hơn 60% không gian dọc.
- Bố cục 5 nhóm công cụ chuẩn UX: Nhóm File, Nhóm Typography (H1-H6, Bold, Italic, Strike, Code), Nhóm Paragraph & Media (Quote, Lists, Table, Image), Nhóm Tìm kiếm (Search button), và Nhóm Right Controls (Conversion Mode, Toggles, Settings, Help).
- Cơ chế phản hồi thị giác động (Dynamic Visual State Toggles): Active = Filled/Rounded + Sáng màu Accent; Inactive = Outlined + Muted Grey.

### 2. Tinh Gọn File Path Bar & Search Bar (`src/ui_flet/components/file_path_bar.py`, `search_replace_bar.py`)
- Chuyển `FilePathBar` từ 2 hàng dọc (~90px) sang **1 hàng ngang chia đôi 50/50 (~38px)** với nút Browse trong suốt viền bo 6px và đồng bộ màu Accent theo Palette.
- Thu gọn `SearchReplaceBar` xuống font 12px, `dense=True`, nút điều hướng 16px, giảm hơn 50% chiều cao panel.

### 3. Tái Thiết Kế Help View & FAQ Accordion (`src/ui_flet/views/help_view.py`, `vi.json`, `en.json`)
- Tái cấu trúc thành **Card Grid 2 Cột**: Bảng phím tắt Consolas nổi bật, Bảng tra cứu cú pháp Markdown, Ma trận định dạng đầy đủ 9 loại tệp, và Hộp mẹo Pro-Tips.
- Xây dựng component `FaqItem` Custom Accordion thay thế `ft.ExpansionPanel` cũ: Căn lề trái 100%, câu trả lời thụt lề 31px thẳng hàng dưới câu hỏi, mũi tên xoay sáng màu Accent.
- Dọn sạch toàn bộ emoji text trùng lặp trong từ điển Tiếng Việt và Tiếng Anh.

### 4. Chuẩn Hóa Typography Scale & Layout (`settings_view.py`, `footer_bar.py`, `editor_view.py`, `preview_view.py`)
- Căn chỉnh đồng bộ hệ thống cỡ chữ: Header View (16px), Component Header (12px), Input / Table / Action Buttons (12px), Secondary Badges / Subtitles (11px).
- Footer Bar hạ chiều cao còn ~38px, nút Chuyển đổi mỏng nhẹ thanh thoát.

### 5. Core Native Folder Picker & Tests (`src/ui_flet/native_dialogs.py`, `tests/test_simplified_ribbon.py`)
- Triển khai `pick_directory_sync()` và `pick_directory_async()` qua `filedialog.askdirectory()` với High-DPI Per-Monitor v2.
- Bổ sung bộ kiểm thử 6 test cases mới bao quát Ribbon, Palette Sync, Locale Update và Folder Dialogs.

---

## 🧪 Kiểm Thử & Xác Minh
- [x] **Layer 1 (Imports & Deprecations)**: Toàn bộ module Flet Desktop và các thư viện tài liệu import trơn tru.
- [x] **Layer 2 (Unit & Service Tests)**: **60/60 test cases** chạy qua `python -m unittest` đều pass 100% trong 4.11s.
- [x] **Layer 3 (Integration / Headless Launch)**: File `tests/test_headless_launch.py` khởi động Flet GUI vòng đời hoàn chỉnh trong 3.12s không phát sinh lỗi.
- [x] **Layer 4 (Live Manual UX)**: Kiểm thử trực tiếp trên Windows OS với cả 4 Bảng màu (*Violet, Emerald, Ocean, Gold*) và chuyển đổi Tiếng Việt ↔ Tiếng Anh tức thì.

---

## 🔍 Phân Tích Ảnh Hưởng & Đánh Giá Rủi Ro
- **Mức độ rủi ro (Blast Radius)**: **THẤP (Low)** — GitNexus shape check xác nhận toàn bộ thay đổi đều nằm trong phạm vi Controller & View UI mới.
- **Tương thích ngược (Backward Compatibility)**: Đã bọc đầy đủ các phương thức `select_tab()`, `_select_tab()` và `deselect_all_tabs()` giúp các controller cũ (`FileController`, `WorkspaceView`) vận hành trơn tru không bị gián đoạn.
