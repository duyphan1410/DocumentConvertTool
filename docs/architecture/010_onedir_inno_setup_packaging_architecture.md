# 010. Kiến Trúc Đóng Gói Thư Mục Chuẩn Desktop (`--onedir`) & Bộ Cài Đặt Inno Setup 7 (`Setup.exe`)

**Trạng thái:** Hoàn thành & Đã áp dụng (v1.7.2)  
**Tác giả:** Duy Phan (@duyphan1410)  
**Ngày:** 27/08/2026  

---

## 1. Bối Cảnh & Vấn Đề Kỹ Thuật

Trước phiên bản v1.7.2, Document Converter được đóng gói ở dạng tệp thực thi đơn lẻ (`--onefile`).
- **Hạn chế lớn**: Mỗi lần người dùng khởi chạy ứng dụng, bootloader của PyInstaller phải giải nén hàng trăm MB dữ liệu, DLLs và Python runtime vào thư mục tạm `%TEMP%/_MEIxxxx`. Quá trình này gây độ trễ khởi động từ 3–5 giây và dễ bị phần mềm diệt virus quét nhầm (False Positive).
- **Thiếu trình cài đặt chuẩn**: Không có shortcut Desktop/Start Menu tự động, không có trình gỡ cài đặt sạch sẽ trong Windows Settings.

---

## 2. Quyết Định Kiến Trúc (Architecture Decisions)

### 2.1. Chuyển sang Thư mục chuẩn Desktop (`--onedir`)
- PyInstaller đóng gói theo mô hình thư mục: File thực thi chính `Document Converter.exe` nằm tại thư mục gốc, toàn bộ phụ thuộc DLLs, C-Extensions, .NET runtime assemblies và tài nguyên được thu thập gọn gàng bên trong thư mục con `_internal/`.
- **Kết quả**: Thời gian khởi động ứng dụng giảm từ ~4s xuống **< 1s** (khởi chạy tức thì).

### 2.2. AppId UUID Định Danh Cố Định (Bắt buộc duy trì)
- Khai báo AppId GUID cố định trong `installer/installer.iss`:
  ```ini
  AppId={{8B598F53-2F47-4C7D-9A92-4A63C1B57801}}
  ```
- **Quy tắc bất biến**: Chuỗi GUID này là **mã định danh duy nhất của phần mềm trên Windows** (tương tự Bundle ID trên macOS/iOS). **Tuyệt đối không được thay đổi chuỗi GUID này trong các bản nâng cấp tiếp theo (v1.8.0, v2.0...)** để đảm bảo trình cài đặt nhận diện đúng phiên bản cũ và ghi đè nâng cấp an toàn mà không sinh trùng lặp trong Control Panel / Installed Apps.

### 2.3. Phân Quyền Cài Đặt Linh Hoạt (`PrivilegesRequired=lowest`)
- Cấu hình:
  ```ini
  PrivilegesRequired=lowest
  PrivilegesRequiredOverridesAllowed=dialog
  ```
- **Mặc định**: Cài đặt vào `%LocalAppData%\Programs\Document Converter` mà **không cần quyền Administrator** (không bị màn hình UAC làm phiền, thân thiện cho tester/máy công ty).
- **Nâng cao**: Vẫn cho phép người dùng chọn *Install for all users* (`Program Files`) nếu có quyền Admin.

### 2.4. Kiểm Tra Tự Động Edge WebView2 Runtime (Pascal Script)
- Kiểm tra mã GUID Registry chính thức của Microsoft Edge WebView2 Evergreen:
  - `SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}`
  - Quét cả nhánh `HKLM`, `HKCU` (32-bit và 64-bit / `WOW6432Node`).
- Nếu máy tính thiếu WebView2, trình cài đặt hiển thị thông báo hướng dẫn tải mà không chặn tiến trình cài đặt chính.

### 2.5. Bảo Vệ Dữ Liệu Người Dùng Khi Gỡ Cài Đặt
- Thư mục lưu bản nháp autosave và cache (`%APPDATA%` / `%USERPROFILE%`) được giữ nguyên vẹn khi người dùng thực hiện gỡ cài đặt (Uninstall), đảm bảo không mất mát dữ liệu đang soạn thảo.

### 2.6. Pipeline Tự Động Hóa 1-Click (`scripts/build_installer.ps1`)
- Script PowerShell đọc tự động `__version__` từ `src/__version__.py`, dọn dẹp cache `build/` & `dist/`, thực thi PyInstaller bằng Python hệ thống, và tự động tìm `ISCC.exe` (hỗ trợ cả Inno Setup 6 & 7) để xuất file `dist/installer/Document_Converter_Setup_v1.7.2.exe`.

---

## 3. Cấu Trúc File & Thư Mục Triển Khai

```text
DocumentConvertTool/
├── Document Converter.spec          # Cấu hình PyInstaller onedir + COLLECT
├── installer/
│   └── installer.iss                # Kịch bản Inno Setup 7 (AppId GUID, Pascal script)
├── scripts/
│   └── build_installer.ps1          # Script 1-Click Build tự động hóa
└── dist/
    ├── Document Converter/          # Thư mục ứng dụng Portable (Standalone)
    │   ├── Document Converter.exe
    │   └── _internal/
    └── installer/                   # Thư mục chứa bộ cài đặt Setup.exe
        └── Document_Converter_Setup_v1.7.2.exe (~89.6 MB)
```
