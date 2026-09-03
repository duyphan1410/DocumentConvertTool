# Kế hoạch Đóng Gói Ứng Dụng: Thư Mục Chuẩn Desktop (`--onedir`) & Bộ Cài Đặt Inno Setup (`Setup.exe`)

## 1. Tổng quan & Mục tiêu

Chuyển đổi phương thức đóng gói của Document Converter từ tệp đơn lẻ (`--onefile`) sang **Chế độ Thư mục Chuẩn (`--onedir`)**, kết hợp với kịch bản đóng gói **Inno Setup 6** chuyên nghiệp nhằm:
1. **Tối ưu tốc độ khởi động**: Khởi chạy tức thì (< 0.5s) thay vì phải giải nén hàng trăm MB ra `%TEMP%/_MEIxxxx`.
2. **Trải nghiệm cài đặt mượt mà**: Hỗ trợ cài đặt không cần quyền Admin (`%LocalAppData%\Programs`) hoặc toàn hệ thống (`Program Files`), tạo Desktop/Start Menu shortcuts, tích hợp trình gỡ cài đặt sạch sẽ.
3. **Tự động hóa hoàn toàn (CI/CD Ready)**: Tự động trích xuất phiên bản từ `src/__version__.py`, kiểm tra runtime phụ thuộc (WebView2, VC++ Redist) và xuất ra file `Document_Converter_Setup_vX.X.X.exe`.

---

## 2. Giải pháp cho 7 Vấn đề Trọng yếu (Production Checklist)

| STT | Vấn đề & Rủi ro | Giải pháp kỹ thuật triển khai |
| :--- | :--- | :--- |
| **1** | **AppId UUID Cố định** *(Tránh trùng lặp khi update)* | Tạo một UUID cố định duy nhất (VD: `{{8B598F53-2F47-4C7D-9A92-4A63C1B57801}}`) và hardcode cố định trong `installer.iss`. Mọi bản update sau này sẽ nhận diện đúng ứng dụng và ghi đè an toàn. |
| **2** | **Bảo vệ Dữ liệu User khi Uninstall** | Mặc định **GIỮ LẠI** thư mục cấu hình và cache draft/ảnh (`%APPDATA%\DocConvert\` hoặc `%USERPROFILE%\.docconvert`) để người dùng không bị mất các bản nháp đang soạn thảo khi nâng cấp/cài đặt lại. |
| **3** | **Phân quyền Cài đặt Linh hoạt (Admin vs User)** | Sử dụng cơ chế Inno Setup 6:<br>`PrivilegesRequired=lowest`<br>`PrivilegesRequiredOverridesAllowed=dialog`<br>Mặc định cài vào `%LocalAppData%\Programs` (không cần UAC/Admin, cực tiện cho tester), nhưng cho phép người dùng chọn cài cho *All Users* (`Program Files`) nếu có quyền Admin. |
| **4** | **Kiểm tra WebView2 Runtime Tự Động** | Thêm đoạn mã Pascal Script `[Code]` trong `installer.iss` kiểm tra Registry xem máy đã có Microsoft Edge WebView2 Runtime chưa (quét cả `HKLM` và `HKCU` tại key `SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017229-9D14-4726-A222-A5660D60E3B7}` và nhánh `WOW6432Node`). Nếu chưa có, tự động thông báo và hướng dẫn/tải WebView2 Bootstrapper. |
| **5** | **Tự Động Đồng Bộ Phiên Bản** | Script build `scripts/build_installer.ps1` sẽ tự động đọc chuỗi `__version__` từ `src/__version__.py` và truyền vào Inno Setup qua tham số dòng lệnh `iscc /DMyAppVersion="$AppVersion" installer/installer.iss`. Không cần sửa tay trong file `.iss`. |
| **6** | **Kiểm thử trên Môi Trường Sạch (Clean VM)** | Đảm bảo file `.spec` thu thập đầy đủ C-runtimes (`vcruntime140.dll`, `msvcp140.dll`, `ucrtbase.dll`). Hướng dẫn quy trình test trên máy ảo Windows Sandbox / Windows 10/11 sạch không cài sẵn Python hay Visual Studio. |
| **7** | **Xử lý Cảnh báo SmartScreen (Chưa Sign Cert)** | Trong tài liệu Release Notes / README, bổ sung phần hướng dẫn trực quan bằng hình ảnh cho Tester/User khi gặp màn hình Windows Defender SmartScreen (*Click "More info" ➔ Click "Run anyway"*). |

---

## 3. Cấu trúc Thư mục Ứng dụng Chuẩn (`--onedir`)

Khi ứng dụng được cài đặt vào máy người dùng:

```text
Document Converter/
├── Document Converter.exe       # EntryPoint chính
├── python3*.dll, *.pyd, *.dll   # Python Core (python312.dll), VC++ Runtimes, C-Extensions
├── assets/                       # Biểu tượng, logo, fonts
│   └── icons/app_icon.ico
├── src/                          # File từ điển ngôn ngữ i18n
│   └── i18n/locales/
├── flet/                         # Flet desktop framework binaries & assets
├── webview/                      # PyWebview bindings & bridge
├── unins000.exe                  # Trình gỡ cài đặt tự sinh của Inno Setup
└── unins000.dat
```

---

## 4. Chi tiết các tệp sẽ tạo và chỉnh sửa

### 1. [MODIFY] [`Document Converter.spec`](file:///c:/Users/Admin/Desktop/DocumentConvertTool/Document%20Converter.spec)
- Chuyển `EXE(...)` từ đóng gói tất cả sang `exclude_binaries=True`.
- Bổ sung `coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Document Converter')`.
- Đảm bảo các DLLs phụ thuộc (`openpyxl`, `fitz`, `pdfplumber`, `webview`, `pythonnet`) được thu thập trọn vẹn.

### 2. [NEW] `installer/installer.iss` (Kịch bản Inno Setup)
- Khai báo AppId UUID cố định.
- Hỗ trợ giao diện cài đặt Modern Wizard, icon `app_icon.ico`.
- Cấu hình tự động nhận biến phiên bản `{#MyAppVersion}` từ script build.
- Cấu hình `PrivilegesRequired=lowest` và `PrivilegesRequiredOverridesAllowed=dialog`.
- Tùy chọn Desktop Shortcut, Start Menu Shortcut và tự động khởi chạy sau cài đặt.
- Đoạn mã `[Code]` kiểm tra sự tồn tại của Edge WebView2 Runtime trên cả `HKLM` và `HKCU`.

### 3. [NEW] `scripts/build_installer.ps1` (Script Build 1-Click)
- Đọc `__version__` từ `src/__version__.py`.
- Dọn dẹp thư mục `build/` và `dist/` cũ.
- Thực thi PyInstaller tạo thư mục `dist/Document Converter/`.
- **Tự động tìm kiếm trình biên dịch `ISCC.exe`** qua các vị trí:
  - Lệnh trong biến môi trường `PATH` (`Get-Command iscc.exe`)
  - `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`
  - `C:\Program Files\Inno Setup 6\ISCC.exe`
  - `C:\Users\$env:USERNAME\AppData\Local\Programs\Inno Setup 6\ISCC.exe`
  - *Nếu không tìm thấy*: In cảnh báo màu rõ ràng hướng dẫn link tải Inno Setup 6 (`https://jrsoftware.org/isdl.php`) và dừng an toàn.
- Biên dịch file `.iss` thành `dist/installer/Document_Converter_Setup_vX.X.X.exe`.

### 4. [MODIFY] [`README.md`](file:///c:/Users/Admin/Desktop/DocumentConvertTool/README.md) & [`docs/roadmaps/product_roadmap.md`](file:///c:/Users/Admin/Desktop/DocumentConvertTool/docs/roadmaps/product_roadmap.md)
- Cập nhật hướng dẫn đóng gói sản phẩm bằng Inno Setup.
- Ghi chú hướng dẫn vượt qua Windows Defender SmartScreen cho tester.

---

## 5. Kế hoạch Kiểm tra & Xác minh (Verification Plan)

### Automated / Script Testing
- Chạy script `scripts/build_installer.ps1` để kiểm tra toàn bộ pipeline build:
  1. PyInstaller `--onedir` hoàn thành không lỗi thiếu module.
  2. Inno Setup `ISCC.exe` biên dịch thành công bộ cài `Setup.exe`.

### Manual Testing
1. **Kiểm tra Thư mục `--onedir`**: Chạy trực tiếp `dist/Document Converter/Document Converter.exe`, kiểm tra tốc độ khởi động (< 0.5s), thử chuyển đổi tài liệu (PDF, Word, Excel).
2. **Kiểm tra YouTube Player Subprocess**: Bấm mở video YouTube từ trong app, xác nhận cửa sổ Webview player con mở độc lập và hoạt động chuẩn xác.
3. **Kiểm tra Cài đặt Không cần Admin**: Chạy `Setup.exe` ở chế độ User thông thường, kiểm tra cài vào `%LocalAppData%\Programs\Document Converter` và tạo Shortcut ngoài Desktop.
4. **Kiểm tra Cài đặt Toàn hệ thống**: Chạy `Setup.exe` với quyền Run as Administrator, kiểm tra cài vào `C:\Program Files\Document Converter`.
5. **Kiểm tra Gỡ cài đặt (Uninstall)**: Gỡ cài đặt từ Windows Settings, xác nhận các file chương trình bị xóa sạch sẽ trong khi dữ liệu nháp người dùng không bị mất mát.
