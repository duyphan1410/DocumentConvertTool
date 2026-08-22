# Audio/Video Transcriber (Whisper AI) — Tổng kết thảo luận & Đề xuất thiết kế

> Ghi chú: Đây là feature **mới**, tách biệt với `speech_service.py` hiện có (Non-AI, dùng Google Web Speech API). Cần đặt tên module riêng (VD: `whisper_service.py`), không sửa đè lên code cũ.

---

## 1. Lựa chọn thư viện & Model

| Thành phần | Quyết định | Lý do |
| :--- | :--- | :--- |
| Thư viện | `faster-whisper` (không dùng `openai-whisper` gốc) | Không phụ thuộc PyTorch (~2-3GB), dùng CTranslate2 nhẹ hơn, nhanh hơn ~4x trên CPU, dễ đóng gói PyInstaller hơn |
| Model mặc định | `base` | Cân bằng tốc độ/chất lượng; `tiny` nhanh hơn nhưng độ chính xác thấp (đặc biệt tiếng Việt) |
| Quantization | `int8` | Tăng tốc thêm ~2x trên CPU so với float32, không cần GPU |

### Bảng tham khảo tốc độ (CPU tầm trung, không GPU)

| Model | Audio 1 tiếng ước tính | Ghi chú |
| :--- | :--- | :--- |
| `tiny` (faster-whisper) | ~4–8 phút | Nhanh nhất, độ chính xác thấp |
| `base` (faster-whisper) | ~8–15 phút | **Đề xuất mặc định** |
| `small`+ | Vài chục phút | Chỉ nên cho phép nếu máy có GPU |

**Công thức ước lượng nhanh** (dùng cho progress bar): `Thời gian xử lý ≈ độ dài audio (phút) × 0.15–0.2`
→ Audio 10 phút ≈ 1.5–2 phút xử lý (baseline UX hợp lý).

### Kết luận về giới hạn tốc độ
Không có cách nào transcribe 1 tiếng audio trong ~1 phút nếu chạy **local/offline/CPU** (đúng tinh thần "Non-AI/lightweight" ban đầu của app). Muốn đạt mốc đó bắt buộc phải đánh đổi:
- Dùng **GPU (CUDA)** — không đảm bảo máy user có, hoặc
- Dùng **Cloud API** (OpenAI Whisper API, Google STT) — mất tính offline, phát sinh phí, gửi data ra ngoài

→ **Quyết định**: chấp nhận vài phút chờ cho audio dài, tập trung làm tốt UX chờ đợi (progress bar, chạy background, không block UI).

---

## 2. Kích thước file input (tham khảo)

| Định dạng | 1 tiếng audio |
| :--- | :--- |
| MP3 128kbps | ~55–60MB |
| MP3 320kbps | ~140MB |
| MP4 (kèm video) | 500MB – 2GB+ (Whisper chỉ decode audio track, không quan tâm phần video) |

Không đặt giới hạn cứng theo dung lượng, chỉ cần cảnh báo mềm theo **thời lượng** (xem mục 4).

---

## 3. Chiến lược tải Model — "Tải lần đầu, cache lại"

### Vì sao không bundle model vào installer
- Model `base` ~145MB — bundle vào `Setup.exe` sẽ phình dung lượng cài đặt không cần thiết cho user không dùng tính năng này
- Tách biệt hoàn toàn khỏi pipeline packaging hiện tại (`.spec`, `installer.iss`) — chỉ cần thêm `hiddenimports` cho `faster-whisper`/`ctranslate2` (vài chục MB thư viện), không đụng gì khác

### Luồng hoạt động
| Bước | Hành vi |
| :--- | :--- |
| Cài đặt app | Chỉ có thư viện, chưa có model |
| User bấm tính năng lần đầu | Hiện dialog: tên model, dung lượng (~145MB), thời gian tải ước tính → nút **Tải & Dùng** / **Hủy** |
| Đồng ý tải | Progress bar tải, chạy `asyncio.to_thread` (không block UI, tái dùng pattern đã có trong `speech_service.py`) |
| Tải xong | Cache lại — các lần sau dùng ngay, không hỏi lại, chạy offline hoàn toàn |
| Không có mạng lần đầu | Cần fallback thông báo lỗi rõ ràng |

### Vị trí cache
Đổi `download_root` của `faster-whisper` từ mặc định (`~/.cache/huggingface`) sang:
```
%APPDATA%\DocConvert\models\
```
→ Nhất quán với pattern cache đang dùng ở `MediaAssetManager`.

---

## 4. Quản lý bộ nhớ Model (Storage Management)

Thêm vào `SettingsView` (tận dụng cấu trúc category có sẵn — thêm category mới hoặc gộp vào "Editor"):

| Chức năng | Mô tả |
| :--- | :--- |
| Xem model đã tải + dung lượng | Liệt kê model, size |
| Nút "Xóa model" | Giải phóng dung lượng, không cần gỡ cài lại app |
| Check dung lượng đĩa trống trước khi tải | `shutil.disk_usage()`, cảnh báo nếu không đủ chỗ |

### Cảnh báo mềm theo thời lượng audio
| Điều kiện | Hành vi |
| :--- | :--- |
| Audio > 30 phút | Dialog: "Quá trình này có thể mất ~X phút, tiếp tục?" (tính theo công thức mục 1) |
| Audio > 2–3 tiếng hoặc file > 500MB (tuỳ chọn) | Có thể chặn cứng hoặc cảnh báo mạnh hơn |
| Luôn có progress indicator | Không để user nhìn màn hình đứng im — tái dùng ý tưởng `chunk_seconds=20` đang có ở `speech_service.py` |

---

## 5. Chọn Model theo phần cứng — 3 hướng & Đề xuất

| Hướng | Ưu điểm | Nhược điểm |
| :--- | :--- | :--- |
| A. Tự động detect (CPU/GPU/RAM) | UX mượt, user không cần hiểu kỹ thuật | Phức tạp hơn, có thể detect sai trên máy lạ |
| B. Cho user chọn tay hoàn toàn | Đơn giản code, minh bạch | User không rành dễ chọn sai (VD chọn `small` trên máy yếu → treo máy) |
| **C. Kết hợp (đề xuất)** | Auto-detect gợi ý mặc định, vẫn cho đổi tay | Cần thêm chút code detect, nhưng cân bằng tốt nhất |

### Logic gợi ý đề xuất (Hướng C)
```
- Detect RAM (dùng thư viện psutil — cần thêm dependency mới, khai báo vào .spec)
- RAM < 8GB hoặc không có GPU  → mặc định gợi ý "tiny"
- RAM >= 8GB                   → mặc định gợi ý "base"
- Có GPU CUDA khả dụng         → cho phép chọn thêm "small"/"medium", chạy trên GPU
- Vẫn hiện dropdown cho user tự đổi, kèm mô tả ngắn tốc độ/chất lượng từng option
```

### Quyết định kỹ thuật cần thống nhất trước khi triển khai
- **Phiên bản đầu tiên (MVP)**: Ưu tiên triển khai chế độ **CPU-only** với `int8` quantization để đảm bảo tính gọn nhẹ, ổn định và tương thích tối đa trên mọi cấu hình máy người dùng.
- **Hỗ trợ GPU (CUDA)**: Đặt làm giai đoạn mở rộng tiếp theo để tránh phụ thuộc vào CUDA runtime phức tạp khi đóng gói bản đầu.

---

## 6. Checklist kỹ thuật & Tiêu chuẩn triển khai (Implementation Checklist)

- [ ] **Thư viện**: Sử dụng `faster-whisper` + `ctranslate2` (quantization `int8`).
- [ ] **Phạm vi phần cứng**: Triển khai trước CPU-only; cấu hình cơ chế gợi ý model dựa trên tài nguyên hệ thống.
- [ ] **Cấu trúc module**: Tạo module độc lập `src/services/whisper_service.py`, không làm ảnh hưởng đến `speech_service.py` hiện tại.
- [ ] **Đường dẫn lưu trữ**: Cấu hình `download_root` chuẩn về `%APPDATA%\DocConvert\models\`.
- [ ] **Bất đồng bộ & UX**: Bọc toàn bộ quá trình transcribe trong `asyncio.to_thread` / worker thread để không block giao diện Flet Desktop.
- [ ] **Quản lý tài nguyên**: Tích hợp kiểm tra dung lượng đĩa trống (`shutil.disk_usage()`) trước khi tải model.
- [ ] **Giao diện người dùng**: Xây dựng hộp thoại xác nhận tải model lần đầu (Consent Dialog), thanh tiến trình tải và tiến trình chuyển đổi (Progress Bar).

---

## 7. Tác động tới quy trình Đóng gói & Installer (Packaging & Delivery Impact)

Chiến lược tải model theo nhu cầu (**On-demand Download**) giúp cô lập hoàn toàn tính năng với quy trình đóng gói:
- **Kích thước bộ cài**: `Setup.exe` không bị phình to (không bundle file weights ~145MB vào installer).
- **Cấu hình PyInstaller**: Chỉ cần khai báo `hiddenimports` cho `faster_whisper` và `ctranslate2` khi tích hợp module vào dự án.
- **Tính độc lập**: Kế hoạch phát triển bộ cài Inno Setup (`plan_setup_exe.md`) và tính năng Whisper AI có thể tiến hành hoàn toàn độc lập mà không bị phụ thuộc chéo.

---

## 8. Chiến lược & Kế hoạch Kiểm thử Toàn diện (Comprehensive Testing Matrix)

Để đảm bảo tính năng hoạt động ổn định trên mọi môi trường và xử lý mượt mà mọi ngoại lệ, quy trình kiểm thử được tổ chức thành **4 tầng kiểm soát**:

### 🔹 Tầng 1: Unit Tests (Tự động & Mock — CI/CD Ready)
- **Kiểm thử định dạng Markdown (`tests/test_whisper_service.py`)**: Mock generator kết quả của `faster-whisper` để kiểm tra logic render Markdown (tiêu đề H1, bảng metadata, timestamps `[hh:mm:ss]`, format text).
- **Kiểm thử bắt lỗi**:
  - File không tồn tại ➔ Bắt đúng lỗi `ERR_FILE_NOT_FOUND`.
  - File sai định dạng / file hỏng ➔ Bắt đúng lỗi `ERR_INVALID_AUDIO_FORMAT`.
- **Kiểm thử tích hợp ngắn**: Dùng 1 file âm thanh mẫu siêu ngắn (3–5s) trong `tests/assets/sample_audio.wav` để test thực tế pipeline decode âm thanh không lỗi.

### 🔹 Tầng 2: Integration & UI Tests (Giao diện Flet & Controller)
- **Consent Dialog**: Kiểm tra hiển thị dialog tải model lần đầu (tên model, dung lượng ~145MB, nút "Tải & Dùng" / "Hủy").
- **Trải nghiệm bất đồng bộ (Non-blocking)**: Xác nhận giao diện Flet không bị đơ/treo khi tải model hoặc khi đang nhận diện giọng nói (nhờ `asyncio.to_thread`).
- **Buffer & Live Preview**: Xác nhận sau khi hoàn tất, nội dung Markdown được nạp vào editor buffer, kích hoạt live preview và autosave draft.
- **Settings View & Dọn dẹp**: Kiểm tra hiển thị dung lượng model trong `%APPDATA%\DocConvert\models\` và chức năng "Xóa model" giải phóng bộ nhớ.

### 🔹 Tầng 3: Kiểm thử Môi trường Đóng gói (Dev Mode ➔ `--onedir` ➔ `Setup.exe`)
- **Dev Mode (`python run.py`)**: Kiểm tra tải model qua mạng và nhận diện file `.mp3`, `.wav`, `.m4a`, `.mp4`.
- **Thư mục Portable (`dist/Document Converter/`)**: Kiểm tra `ctranslate2` và `faster-whisper` C-runtimes load thành công, không gặp lỗi thiếu DLL hay `ModuleNotFoundError`.
- **Máy ảo sạch (Clean VM / Windows Sandbox)**: Cài đặt từ `Setup.exe` trên môi trường Windows sạch (không có Python) để xác nhận trọn vẹn quy trình người dùng cuối.

### 🔹 Tầng 4: Edge Cases & Kiểm soát Rủi ro (Stress Test)
- **Mất kết nối mạng giữa chừng**: Ngắt mạng khi đang tải model ➔ App báo lỗi rõ ràng, dọn dẹp file tải dở, không bị crash.
- **Dung lượng đĩa không đủ**: Kiểm tra `shutil.disk_usage()` chặn tải nếu ổ cứng trống < 200MB.
- **File âm thanh im lặng (Silent Audio)**: Xử lý êm dịu, trả về metadata và ghi chú `[Không phát hiện giọng nói]`.
- **File Video nặng (> 500MB MP4)**: Bóc tách luồng audio stream an toàn mà không làm tràn bộ nhớ RAM (OOM).
