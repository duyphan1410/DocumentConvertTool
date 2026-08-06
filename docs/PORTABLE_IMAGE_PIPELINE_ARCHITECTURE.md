# Portable Image Pipeline Architecture & Technical Report

## 1. Bối cảnh & Bài toán cần giải quyết (Core Challenge)

### ❌ Trạng thái cũ (Vấn đề tồn tại):
1. **Lỗi gãy link ảnh khi mở bằng ứng dụng khác:** Khi trích xuất ảnh từ PDF/Word hoặc chèn ảnh thủ công, link ảnh được nhúng dạng tuyệt đối dẫn vào thư mục hệ thống `C:\Users\Admin\AppData\Roaming\DocConvert\...` hoặc virtual URI `@media/`.
   - *Hậu quả:* Chỉ có app nội bộ đọc được. Khi mở file `.md` bằng **VS Code, Obsidian, Typora** hoặc **gửi sang máy khác**, toàn bộ hình ảnh bị gãy link (`Image not found`).
2. **Lỗi mờ/gãy Preview khi chèn ảnh:** Chèn ảnh qua thanh Ribbon dùng prefix `file:///C:/...` khiến bộ giải mã Windows trả về `False`, ảnh không hiển thị tức thì trên Preview.
3. **Lỗi đè văn bản & nuốt Tiêu đề:** 
   - Khi chèn ảnh từ Ribbon, Flet tự động bôi đen văn bản xung quanh ➔ Thao tác gõ phím tiếp theo làm mất chữ.
   - Khi xuất sang Word (`word_module.py`), nếu ảnh nằm chung dòng với Tiêu đề (như `# **TITLE**![img](path)`), bộ parser cũ hủy toàn bộ dòng và làm **mất hẳn văn bản Tiêu đề**.

---

## 2. Thiết kế Kiến trúc & Đánh đổi (Architecture & Trade-off Rationale)

Để giải quyết triệt để bài toán trên, ứng dụng áp dụng mô hình **Dual-Layer Asset Pipeline** (Tách biệt bộ đệm làm việc & gói xuất bản):

```
┌────────────────────────────────────────────────────────────────────────┐
│                        QUY TRÌNH XỬ LÝ HÌNH ẢNH                        │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  [1. Mở/Trích xuất PDF/Word] OR [Chèn ảnh từ đĩa]                     │
│               │                                                        │
│               ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │ Layer 1: AppData Session Cache (Lưu đệm tạm)             │          │
│  │ - Đảm bảo tốc độ Preview xem trước 0ms                    │          │
│  │ - Không làm rác các thư mục làm việc của người dùng      │          │
│  │ - Tự dọn dẹp (LRU Auto-Cleanup < 200MB / > 7 ngày)       │          │
│  └──────────────────────────────────────────────────────────┘          │
│               │                                                        │
│               ▼ (Khi người dùng bấm Lưu / Export file .md)             │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │ Layer 2: Relative Asset Export (<doc_name>_assets/)      │          │
│  │ - Copy ảnh từ Cache + Ảnh từ đĩa vào folder kế bên       │          │
│  │ - Chuẩn hóa link tương đối: ./<doc_name>_assets/img.png   │          │
│  │ - Kiểm tra Hash MD5 chống ghi đè trùng tên file          │          │
│  └──────────────────────────────────────────────────────────┘          │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### ⚖️ Đánh đổi (Trade-off Rationale):
* **Sự xuất hiện của thư mục `<doc_name>_assets/`:** Khi lưu file `.md`, một thư mục tài nguyên sẽ được tạo kế bên.
* **Vì sao đây là sự đánh đổi bắt buộc & tối ưu nhất?**
  1. Định dạng Markdown bản chất là file văn bản thuần (Plain Text), **không hỗ trợ đính kèm binary trực tiếp vào ruột file** (trừ khi dùng Base64 làm dung lượng file phình toàn bộ và giật lag trình đọc).
  2. Đây là **tiêu chuẩn công nghiệp (Standard Pattern)** được sử dụng bởi VS Code, Obsidian, Typora, Notion và GitHub Markdown khi làm việc với tài liệu đính kèm hình ảnh.
  3. Giữ được sự độc lập: Bạn chỉ cần nén folder tài liệu gửi đi, bất kỳ phần mềm hay hệ điều hành nào (Windows, macOS, Linux) cũng mở xem được 100%.

---

## 3. Chi tiết các thay đổi Kỹ thuật (Technical Changes)

| Tệp tin ảnh hưởng | Thay đổi chi tiết | Mục đích & Hiệu quả |
| :--- | :--- | :--- |
| **`src/services/media_asset_manager.py`** | Refactor hàm `export_assets()`: bóc tách tag ảnh `![]()`, giải mã cả 2 nguồn (AppData cache + ảnh đĩa ngoài), kiểm tra hash MD5 chống trùng file (`img_1.png`), lưu vào `<doc_name>_assets/` và rewrite link về `./<doc_name>_assets/filename`. | Đảm bảo tính di động 100% cho file Markdown xuất ra. |
| **`src/ui_flet/controllers/file_controller.py`** | Sửa token ảnh chèn từ Ribbon: bỏ prefix `file:///` thừa, chỉ giữ chuẩn đường dẫn Windows `![alt](C:/path/to/img.png)`. | Giúp `resolve_uri()` nhận diện file chuẩn, **ảnh hiển thị tức thì trên Preview**. |
| **`src/ui_flet/views/editor_view.py`** | Xây dựng hàm `insert_image_token(token)`: tự động căn chỉnh xuống dòng `\n` và thu con trỏ về vị trí kết thúc (collapsed selection). | **Loại bỏ triệt để lỗi mất chữ/đè chữ** xung quanh khi gõ phím tiếp theo. |
| **`src/modules/word_module.py`** | Nâng cấp `save_from_markdown()`: khi gặp dòng chứa cả văn bản/tiêu đề và ảnh, tự động bóc tách `text_before`, `image` và `text_after` thành các dòng queue riêng. | **Khắc phục dứt điểm lỗi nuốt chữ / mất Tiêu đề** khi xuất sang file Word (.docx). |
| **`tests/test_portable_image_export.py`** | Viết mới suite kiểm thử tự động cho việc tạo folder tương đối, rewrite link và deduplicate ảnh trùng tên. | Đảm bảo chất lượng mã nguồn. |
| **`tests/test_word_inline_image_fix.py`** | Viết mới suite kiểm thử tự động xác minh không bị mất Tiêu đề khi xuất file Word chứa ảnh nằm inline. | Kiểm thử tính toàn vẹn dữ liệu. |
| **`docs/ROADMAP.md`** | Cập nhật trạng thái 2 tính năng sang `✅ Completed` và bổ sung tính năng `Image Settings Dialog & Format Tab` vào danh sách `⏳ Planned`. | Quản lý lộ trình sản phẩm. |

---

## 4. Kết quả Nghiệm thu (Verification & Quality)

* **Unit Test Suite:** 
  ```powershell
  python -m unittest discover -s tests -p "*test*.py"
  ```
  👉 **32/32 unit tests trôi qua thành công 100% (`OK`)**.

* **Kiểm thử thực tế (End-to-End):**
  1. **Instant Preview:** Chèn ảnh qua nút Add Image ➔ Ảnh xuất hiện 0ms trên Preview.
  2. **Soạn thảo an toàn:** Chèn ảnh ở bất kỳ vị trí nào ➔ Không bị mất hay đè chữ xung quanh khi gõ tiếp.
  3. **Xuất Word chuẩn xác:** Chuyển đổi Markdown có ảnh dính Tiêu đề ➔ File Word hiển thị đầy đủ Tiêu đề, văn bản và hình ảnh.
  4. **Tính di động di chuyển:** Mở file `.md` vừa xuất bằng VS Code hay ứng dụng khác ➔ Hình ảnh preview hoàn hảo.
