# 🏛️ Tổng Hợp Tính Năng Tự Động Khôi Phục Bản Nháp & Tối Ưu UX Loading

**Ngày cập nhật:** 10/08/2026  
**Dự án:** Document Converter Tool  
**Phiên bản:** `v1.5.3`  
**Nhánh:** `feat/duy-10082026-auto-draft-loading-ux`  

---

## 🎯 1. Tổng Quan Mục Tiêu Đã Đạt Được

Đã nâng cấp và hoàn thiện toàn bộ trải nghiệm người dùng (UX) khi ứng dụng tự động khôi phục bản nháp (Auto Draft Restoration) lúc khởi động:
- **Tách biệt luồng bất đồng bộ**: Nạp văn bản và mở ngay Trình soạn thảo (`EditorView`) trong **~0.4 giây**, không còn hiện tượng giật đơ giao diện.
- **Tải ảnh Preview nhẹ nhàng ở Background**: Bảng xem trước (`MarkdownPreview`) hiển thị thông báo `⏳ Đang nạp bản xem trước...` trên thanh tiêu đề góc phải mà không làm nghẽn luồng gõ chữ của người dùng.
- **Nút 1-Click Smart Auto-Rename**: Modal xác nhận trùng tệp bổ sung thêm lựa chọn `[Lưu tệp mới (output_1.md)]` tự động đổi tên tệp chỉ với 1 cú nhấp chuột.
- **Bôi đen chính xác tên tệp (Exact Filename Highlight)**: Khi bấm "Hủy" trên Modal trùng tệp, con trỏ chuột tự động bôi đen chính xác duy nhất tên tệp (không bôi đen đường dẫn và phần mở rộng) giúp người dùng thay đổi tên tệp nhanh chóng.
- **Đa ngôn ngữ hóa 100% thanh đường dẫn**: Nhãn thanh đường dẫn tệp tự động chuyển đổi giữa `Tệp .ext` / `Lưu .ext` (Tiếng Việt) và `File .ext` / `Save .ext` (Tiếng Anh).

---

## ✨ 2. Các Tính Năng & Tối Ưu Nổi Bật

### ⏳ Màn Hình LoadingView Tách Luồng Độc Lập
- Màn hình `LoadingView` chỉ chịu trách nhiệm nạp nhanh văn bản nháp và cài đặt ứng dụng.
- Đảm bảo vòng xoay `ProgressRing` xoay tròn mượt mà 60fps và kết thúc mở ra Editor trong ~0.4s.

### 🖼️ Xử Lý Ảnh Live Preview Bất Đồng Bộ (`process_markdown_media_async`)
- Xử lý mã hóa Base64 cho hình ảnh slide PDF ở luồng ngầm bất đồng bộ.
- Nhường nhịp event loop (`await asyncio.sleep(0.005)`) giữa các bức ảnh, giúp luồng gõ văn bản của Editor hoàn toàn tự do và mượt mà 100%.

### 📋 Nút 1-Click "Lưu Tệp Mới" Trên Modal
- Tự động tính toán tên tệp khả dụng chưa tồn tại trên đĩa (`filename_1.md`, `filename_2.md`).
- Bấm 1-Click vào nút `[Lưu tệp mới...]` giúp ứng dụng tự cập nhật ô đường dẫn và thực hiện chuyển đổi ngay lập tức.

### 🎯 Tự Động Focus & Bôi Đen Chính Xác Tên Tệp
- Khi đường dẫn là `C:\Users\Admin\Desktop\Test\Resume.docx`, bấm "Hủy" sẽ giữ nguyên `C:\Users\Admin\Desktop\Test\` và `.docx`, chỉ bôi đen duy nhất chữ `Resume`.
- Cho phép người dùng gõ tên mới thay thế trực tiếp trên bàn phím mà không cần bấm chuột.

### 🌐 Đa Ngôn Ngữ Hóa Thanh Đường Dẫn Tệp
- Liên kết động các nhãn tệp với bộ từ điển `i18n`.
- Hỗ trợ đổi ngôn ngữ linh hoạt theo Cài đặt: `Tệp .md` / `Lưu .docx` (Tiếng Việt) và `File .md` / `Save .docx` (Tiếng Anh).

---

## 📁 3. Các Tệp Mã Nguồn Đã Thay Đổi

```text
DocumentConvertTool/
├── src/
│   ├── i18n/locales/
│   │   ├── vi.json                     # Bổ sung các phím dịch Tiếng Việt cho loading, dialog & pathbar
│   │   └── en.json                     # Bổ sung các phím dịch Tiếng Anh cho loading, dialog & pathbar
│   ├── ui_flet/
│   │   ├── constants.py                # Thêm get_default_output_dir() trả về thư mục ~/Documents/DocConvert_Output/
│   │   ├── app.py                      # Tích hợp LoadingView và kích hoạt async_load_draft_if_exists
│   │   ├── components/
│   │   │   └── file_path_bar.py        # Mở khóa ô gõ tệp nguồn & liên kết nhãn đa ngôn ngữ động
│   │   ├── controllers/
│   │   │   ├── file_controller.py      # Xử lý khôi phục nháp bất đồng bộ & benchmark thời gian
│   │   │   └── conversion_controller.py # Thêm 1-click Save As New & Exact Filename Highlight selection
│   │   ├── layout/
│   │   │   └── ribbon_bar.py           # Tùy chọn mode ưu tiên theo cài đặt default_mode
│   │   └── views/
│   │       ├── loading_view.py         # [NEW] View loading mượt 60fps
│   │       ├── workspace_view.py       # Điều phối chuyển đổi giữa LoadingView & EditorWorkspace
│   │       └── preview_view.py         # Quản lý nhãn loading header ⏳ Đang nạp bản xem trước...
└── docs/archive/
    └── 10082026_auto_draft_loading_ux_summary.md # Tệp tổng hợp tính năng (Tệp này)
```
