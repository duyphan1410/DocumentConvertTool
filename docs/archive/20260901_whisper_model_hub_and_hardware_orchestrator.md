# AI Model Hub Orchestrator, Multi-Vendor Hardware Detection & 2-Layer Verification Architecture (Phase 1 — v1.9.0)

**Phiên bản**: `v1.9.0-dev`  
**Ngày cập nhật**: 01/09/2026  
**Nhánh liên quan**: `feat/duy-01092026-whisper-model-hub`  

---

## 1. Tầm Nhìn Kiến Trúc & Bối Cảnh (Architecture Vision & Problem Statement)

Tính năng **Offline Audio/Video Transcriber** đưa **Document Converter Tool** tiến vào kỷ nguyên **Edge Computing / Local AI**. Để mang lại trải nghiệm tối ưu mà không làm phình dung lượng bộ cài đặt (`Setup.exe` < 80MB), hệ thống áp dụng mô hình **AI Model Hub / Model Marketplace On-Demand**:

1. **Quyền tự chủ của người dùng**: Người dùng tự do tải, trải nghiệm, chuyển đổi hoặc xóa các mô hình AI (`whisper-tiny`, `whisper-base`, `whisper-small` từ tổ chức chính thức `Systran`) tùy theo nhu cầu độ chính xác và dung lượng đĩa.
2. **Bộ điều phối phần cứng thông minh (0ms Hardware Detection)**: Tự động phát hiện cấu hình CPU (Cores & Clock speed), RAM, và nhận diện GPU đa hãng (NVIDIA CUDA, AMD Radeon RX, Intel Iris/Arc) để đưa ra khuyến nghị model tối ưu nhất cho phần cứng máy tính.
3. **Quản lý vòng đời Model chuyên nghiệp**: Cơ chế Stream Chunking 64KB cho phép hủy tải tức thì (< 5ms), Global Progress Stream giữ nguyên thanh tiến trình khi đóng/mở tab Cài đặt, và quy trình xác thực 2 lớp độc lập.

---

## 2. Giải Pháp Kỹ Thuật Đã Triển Khai

### 2.1. Quét Phần Cứng Đa Hãng Tốc Độ 0ms (`src/services/hardware_detector.py`)
- **CPU & RAM**: Trích xuất chi tiết xung nhịp thực tế qua Windows Registry (`~MHz`), số nhân vật lý/logic, và truy vấn bộ nhớ hệ thống trực tiếp qua Win32 API `GlobalMemoryStatusEx`.
- **Nhận diện GPU Đa Hãng**:
  1. *NVIDIA GPU*: Khởi tạo an toàn qua `nvidia-ml-py` (`==13.610.43`) kết hợp fallback `nvidia-smi CLI` để lấy Tên GPU, VRAM khả dụng, Phiên bản Driver và CUDA Toolkit Version. Đánh giá cờ `cuda_usable = True` khi VRAM $\ge$ 2048 MB và Driver $\ge$ 450.
  2. *AMD Radeon & Intel GPU*: Tự động quét Display Adapters từ Windows Registry (`SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}`) với độ trễ **0ms**, ưu tiên nhận diện Card đồ họa rời (ví dụ: `Radeon RX 5500M`).
- **Bộ nhớ đệm (RAM Cache)**: Kết quả thẩm định được lưu trong `_CACHED_HARDWARE` giúp các thao tác chuyển tab trong UI đạt độ trễ **0ms tuyệt đối**.

### 2.2. Quản Lý Tải Stream 64KB, Instant Cancel & 2-Layer Verification (`src/services/model_manager.py`)
- **Tải tệp theo khối Stream 64KB**: Tải tuần tự các file weights (`model.bin`, `config.json`, `vocabulary.txt`, `tokenizer.json`) từ Hugging Face qua `requests.get(stream=True)`.
- **Hủy tải tức thì (Instant Cancellation < 5ms)**: Kiểm tra cờ `cancel_event.is_set()` sau mỗi chunk 64KB. Khi bấm nút `[✖]`, socket được ngắt tức thì, tự động xóa sạch các file tạm dở dang.
- **Quy trình Xác thực 2 Lớp (2-Layer Verification Harness)**:
  - *Lớp 1 (File Integrity Check)*: Kiểm tra sự tồn tại và kích thước tối thiểu của tất cả các file cấu hình và nhị phân bắt buộc tại `%APPDATA%\DocConvert\models\<model_id>\`.
  - *Lớp 2 (CTranslate2 Runtime Load Check)*: Nạp thử mô hình vào `WhisperModel(compute_type="int8")` trên luồng độc lập để chứng minh file weights hoạt động hoàn hảo trước khi bàn giao cho pipeline xử lý âm thanh.

### 2.3. Kiến Trúc Global Progress Stream & Event Listener Registry
- **Vấn đề giải quyết**: Khi người dùng bấm tải model rồi đóng tab Cài đặt hoặc chuyển sang tab khác, view bị unmount nhưng quá trình tải vẫn chạy ngầm.
- **Giải pháp**:
  - `model_manager` duy trì từ điển trạng thái `_DOWNLOAD_PROGRESS` và danh sách listener `_PROGRESS_LISTENERS`.
  - Khi mở lại tab Cài đặt, thẻ model tự động đọc snapshot tiến độ hiện tại và kết nối vào luồng phát dữ liệu (`add_download_listener`).
  - Giao diện dispatch dữ liệu an toàn xuyên luồng qua `asyncio.run_coroutine_threadsafe(_u(), main_loop)`, giúp thanh tiến trình và thông số MB chạy mượt mà liên tục.

### 2.4. Giao Diện Người Dùng Hiện Đại (UI/UX) & Trải Nghiệm Mượt Mà
- **Model Hub Card Grid (`src/ui_flet/components/model_hub_dialog.py`)**:
  - Thẻ card chuẩn Material Design, xếp hàng ngang đồng đều các badge: Trạng thái, Dung lượng, Đánh giá Tốc độ (⚡), Độ chính xác (⭐), RAM yêu cầu.
  - Hộp thoại **Xác nhận xóa an toàn 1 bước** (Single-step safe confirmation), tự động đóng và giải phóng đĩa.
  - Nút **`📁 Mở thư mục lưu trữ Model`**: Tích hợp `open_file_or_folder_foreground` đưa cửa sổ File Explorer lên tiền cảnh (Z-Index #1).
- **First-time Quick Download Dialog (`src/ui_flet/components/first_time_model_dialog.py`)**: Hộp thoại tự động đề xuất model tối ưu nhất theo phần cứng khi người dùng lần đầu kích hoạt tính năng chuyển đổi giọng nói.
- **Căn chỉnh Sidebar Navigation (`src/ui_flet/views/settings_view.py`)**: Mở rộng độ rộng danh mục lên `210px` với padding `12px/14px` đối xứng, giúp tiêu đề *"AI Models (Whisper)"* hiển thị thoáng đãng và thanh lịch.

### 2.5. Quốc Tế Hóa 100% (i18n Multi-Language)
- Đưa toàn bộ chuỗi ký tự sang `vi.json` và `en.json`: Tiêu đề, mô tả 3 model AI, thông điệp tiến trình tải theo từng MB thực tế (`Đang tải {file} ({done}/{total} MB)...`), tooltip và các cảnh báo lỗi mạng/ổ đĩa.

---

## 3. Bộ Kiểm Thử & Nghiệm Thu (Automated Test Suite)

Hệ thống được kiểm thử toàn diện với **24/24 unit tests PASS 100%**:

```powershell
python -m unittest tests/test_hardware_detector.py tests/test_model_manager.py tests/test_model_hub_ui.py tests/test_settings_view.py
........................
----------------------------------------------------------------------
Ran 24 tests in 0.776s

OK
```

### Các nhóm test đã nghiệm thu:
1. `test_hardware_detector.py`: Xác minh quét CPU, RAM, GPU NVIDIA CUDA, GPU AMD Radeon, logic đánh giá phần cứng và cơ chế RAM Caching.
2. `test_model_manager.py`: Xác minh tải stream chunking, tính toán %/MB, hủy tải tức thì, xóa model, dọn dẹp toàn bộ ổ đĩa và kiểm tra xác thực 2 lớp.
3. `test_model_hub_ui.py`: Xác minh khởi tạo giao diện Model Hub, First-time dialog, kết nối listener và render card grid.
4. `test_settings_view.py`: Xác minh tích hợp tab AI Models vào SettingsView, mở rộng navigation width và đồng bộ theme.

---

## 4. Danh Sách Tệp Triển Khai & Thay Đổi

| Tệp tin | Vai trò & Thay đổi chính |
| :--- | :--- |
| `src/services/hardware_detector.py` | **[MỚI]** Module quét phần cứng CPU, RAM, GPU rời (NVIDIA, AMD, Intel) và thuật toán gợi ý model. |
| `src/services/model_manager.py` | **[MỚI]** Quản lý vòng đời tải, hủy tải, lưu trữ `%APPDATA%\DocConvert\models`, dọn dẹp đĩa và xác thực 2 lớp. |
| `src/ui_flet/components/model_hub_dialog.py` | **[MỚI]** Giao diện Model Hub Card Grid, giám sát dung lượng ổ cứng, nút mở folder focus Z-Index #1. |
| `src/ui_flet/components/first_time_model_dialog.py` | **[MỚI]** Hộp thoại đề xuất tải nhanh model tối ưu nhất theo phần cứng cho người dùng mới. |
| `src/ui_flet/views/settings_view.py` | Tích hợp tab **AI Models (Whisper)** vào Settings, mở rộng sidebar width lên `210px`. |
| `src/ui_flet/components/message_dialog.py` | Chuẩn hóa AlertDialog `modal=False`, đóng an toàn, ẩn nút Copy Error trên dialog thành công. |
| `src/ui_flet/layout/ribbon_bar.py` | Tự động bỏ lọc nút Ribbon Convert khi đóng toàn bộ tab trong Studio Workspace. |
| `src/core/errors.py` | Bổ sung mã lỗi `MODEL_DOWNLOAD_FAILED`, `MODEL_CORRUPTED`, `MODEL_RUNTIME_ERROR`. |
| `src/i18n/locales/vi.json` & `en.json` | Bổ sung 100% chuỗi đa ngôn ngữ cho Model Hub, mô tả 3 model và tiến trình tải. |
| `requirements.txt` | Khóa cứng phiên bản `faster-whisper==1.2.1`, `ctranslate2==4.8.1`, `nvidia-ml-py==13.610.43`, `huggingface-hub==1.28.0`, `av==18.1.0`. |
| `tests/test_hardware_detector.py` | **[MỚI]** Bộ kiểm thử cho Hardware Detector và thuật toán gợi ý. |
| `tests/test_model_manager.py` | **[MỚI]** Bộ kiểm thử cho Download Manager, Instant Cancel và 2-Layer Verification. |
| `tests/test_model_hub_ui.py` | **[MỚI]** Bộ kiểm thử cho UI Model Hub và First-time Dialog. |
| `docs/archive/20260903_whisper_feature_plan.md` | Bản đặc tả kiến trúc, phân công ma trận 2 người và lộ trình thực hiện. |
| `docs/archive/20260901_whisper_model_hub_and_hardware_orchestrator.md` | **[MỚI]** Tài liệu kỹ thuật lưu trữ chính thức của Pha 1. |

---

## 5. Ghi Chú Vận Hành & Bảo Trì (Model SHA256 Maintenance Policy)

> [!IMPORTANT]
> **Quy trình bảo trì mã băm SHA256 (`AVAILABLE_MODELS.expected_sha256`)**:
> - Mã băm SHA256 trong `model_manager.py` gắn chặt với commit/revision hiện tại của kho `Systran/faster-whisper-*` trên Hugging Face Hub.
> - **Khi nào cần cập nhật**:
>   1. Khi Systran re-upload hoặc phát hành bản weights mới (được re-convert bằng CTranslate2 mới hơn).
>   2. Khi dự án bổ sung model mới (ví dụ `whisper-medium` hoặc `whisper-large-v3`).
>   3. Khi có phản hồi từ người dùng về việc tải model bị báo lỗi `corrupted` liên tục dù mạng ổn định.
> - **Cách kiểm tra nhanh**: Chạy lệnh kiểm tra hash qua HuggingFace Hub API để cập nhật lại từ điển `expected_sha256` tương ứng trong `src/services/model_manager.py`.

