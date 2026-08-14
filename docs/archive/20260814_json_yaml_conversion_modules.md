# 📦 PR Archive Snapshot — 14/08/2026: `feat/duy-14082026-json-yaml-conversion-modules`

- **Branch Name:** `feat/duy-14082026-json-yaml-conversion-modules`
- **Date:** 14/08/2026
- **Status:** Completed
- **Target Component:** `src/modules/json_module.py`, `src/modules/yaml_module.py`, `src/modules/__init__.py`, `src/core/base_module.py`, `src/core/validator.py`, `src/ui_flet/constants.py`, `src/i18n/locales/en.json`, `src/i18n/locales/vi.json`, `requirements.txt`, `Document Converter.spec`, `README.md`, `tests/test_json_yaml_modules.py`

---

## 📌 PR Summary: [feat/duy-14082026-json-yaml-conversion-modules -> dev]

### 🎯 Mục tiêu PR
Xây dựng và tích hợp hai module chuyển đổi hai chiều mới: **JSON (`JSON ↔ MD`)** và **YAML (`YAML ↔ MD`)** vào ứng dụng Document Converter Tool. Đảm bảo tuân thủ triệt để kiến trúc hệ thống (`ModuleRegistry`, `BaseDocumentModule`), quy tắc **Lazy Import Rule** (không import thư viện bên thứ 3 ở top-level để tránh crash khi khởi động), hỗ trợ chuyển đổi mảng dữ liệu thành Bảng Markdown Pipe Table, đối tượng lồng nhau thành cây tiêu đề/bullet, tích hợp kiểm soát cú pháp tệp trong `validator.py`, mở rộng giao diện UI Flet (`MODES`, `MODE_DISPLAY_KEYS`), hỗ trợ đa ngôn ngữ `en.json` / `vi.json`, đóng gói PyInstaller spec và bộ kiểm thử tự động 54 unit tests. Nâng phiên bản hệ thống lên **`v1.6.5`**.

---

### 🚀 Các thay đổi chính

#### 1. Core Engine & Modules (`src/modules/json_module.py`, `src/modules/yaml_module.py`)
- **JSONModule (`src/modules/json_module.py`)**:
  - Thừa hành `BaseDocumentModule` xử lý định dạng tệp `.json`.
  - `load_to_markdown`: Đọc và phân tích cú pháp JSON bằng thư viện chuẩn `json`. Nếu mảng dữ liệu chứa danh sách đối tượng dict đồng nhất ➔ tự động tạo Bảng Markdown Pipe Table (`| col1 | col2 |`). Nếu đối tượng dict lồng nhau ➔ chuyển đổi sang cấu trúc tiêu đề `#`, `##` và các thẻ bullet `- **key**: value`.
  - `save_from_markdown`: Trích xuất khối mã ```json (nếu có), phân tích Bảng Markdown (tái sử dụng `parse_md_tables` từ `converters.py`), hoặc đọc các cặp thẻ key-value để xuất lại tệp `.json` chuẩn formatted (`indent=2`, `ensure_ascii=False`).
- **YAMLModule (`src/modules/yaml_module.py`)**:
  - Thừa hành `BaseDocumentModule` xử lý định dạng tệp `.yaml`, `.yml`. Khai báo `required_dependencies = ["pyyaml"]`.
  - **Tuân thủ Lazy Import Rule**: Import `yaml` lazily bên trong phương thức `load_to_markdown` và `save_from_markdown`. Đảm bảo nếu môi trường thiếu `pyyaml`, ứng dụng vẫn khởi động bình thường và chỉ cảnh báo khi người dùng thực hiện chuyển đổi tệp YAML.
  - Phân tích cú pháp bằng `yaml.safe_load` và xuất tệp bằng `yaml.dump(allow_unicode=True, sort_keys=False)`.

#### 2. Tự Động Đăng Ký & Core Dependency Mapping (`src/modules/__init__.py`, `src/core/base_module.py`)
- **`src/modules/__init__.py`**: Import `JSONModule` và `YAMLModule` để tự động đăng ký với singleton `ModuleRegistry` ngay khi khởi động ứng dụng.
- **`src/core/base_module.py`**: Cập nhật hàm `check_dependencies()` bổ sung ánh xạ gói `pyyaml` sang tên module import trong Python là `yaml`.

#### 3. Validation Pipeline (`src/core/validator.py`)
- Thêm bước kiểm tra tính hợp lệ định dạng cho tệp `.json` (sử dụng `json.load`) và `.yaml` (sử dụng `yaml.safe_load`) trong `validate_file_pipeline()`.
- Phát hiện tệp hỏng/sai cú pháp và ném ngoại lệ `DocumentError` loại `CORRUPTED_STRUCTURE` kèm thông báo hướng dẫn sửa lỗi rõ ràng.

#### 4. Giao Diện UI & Đa Ngôn Ngữ (`src/ui_flet/constants.py`, `src/i18n/locales/en.json`, `src/i18n/locales/vi.json`)
- **`src/ui_flet/constants.py`**: Bổ sung 4 chế độ mới vào `MODES`, `MODE_DISPLAY_KEYS`, `IN_FILETYPES`, và `OUT_FILETYPES`:
  - `MD -> JSON`, `JSON -> MD`
  - `MD -> YAML`, `YAML -> MD`
- **`en.json` & `vi.json`**: Bổ sung nhãn hiển thị cho menu dropdown và các câu thông báo lỗi cú pháp JSON/YAML hỏng.

#### 5. Phụ Thuộc & Cấu Hình Build Executable (`requirements.txt`, `Document Converter.spec`, `src/__version__.py`)
- **`requirements.txt`**: Thêm `PyYAML>=6.0.1`.
- **`Document Converter.spec`**: Bổ sung `src.modules.json_module`, `src.modules.yaml_module`, và `yaml` vào danh sách `hiddenimports`.
- **`src/__version__.py`**: Nâng phiên bản hệ thống lên **`v1.6.5`**.

#### 6. Kiểm Thử Tự Động (`tests/test_json_yaml_modules.py`)
- Xây dựng 7 test cases chi tiết kiểm thử toàn diện:
  - Chuyển đổi JSON dạng mảng đối tượng sang Bảng Markdown và ngược lại.
  - Chuyển đổi JSON lồng nhau và khối mã ```json.
  - Chuyển đổi hai chiều YAML ↔ MD.
  - Kiểm tra tính năng tự động đăng ký trong `ModuleRegistry`.
  - Kiểm tra phát hiện lỗi cú pháp tệp hỏng trong `validate_file_pipeline`.

---

### 🧪 Kiểm thử & Xác minh

- [x] **Unit Tests**: Chạy thành công toàn bộ **54/54 unit tests** (`python -m unittest discover -s tests -p "test_*.py"`).
- [x] **Lazy Import Verification**: Thử nghiệm khi chưa cài `pyyaml`, ứng dụng khởi động mượt mà không crash.
- [x] **Regression Check**: Đảm bảo 100% các module cũ (Word, Excel, CSV, PDF, HTML, PPTX) hoạt động bình thường.

---

### 🔍 Phân tích ảnh hưởng & Đánh giá rủi ro
- **Mức độ rủi ro (Blast Radius)**: THẤP
- **Các hàm/module ảnh hưởng**: `JSONModule`, `YAMLModule`, `ModuleRegistry`, `base_module.py`, `validator.py`, `constants.py`, `en.json`, `vi.json`, `requirements.txt`, `Document Converter.spec`, `README.md`.
