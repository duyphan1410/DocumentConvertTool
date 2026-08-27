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

### Câu hỏi cần thảo luận & thống nhất (Open Decisions)
- **Phương án hỗ trợ phần cứng**: Nên ưu tiên CPU-only (gọn nhẹ, ổn định, tương thích mọi máy) hay giữ cả tùy chọn GPU (CUDA) ngay từ đầu?
- **Mức độ tích hợp**: Có cần thêm cảnh báo phần cứng trong dialog hay chỉ cần dropdown chọn model đơn giản?

---

## 6. Checklist kỹ thuật & Tiêu chuẩn triển khai (Implementation Checklist)

- [ ] **Thư viện**: Sử dụng `faster-whisper` + `ctranslate2` (quantization `int8`).
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
- **Tính độc lập**: Kế hoạch phát triển bộ cài đặt Windows Installer (`Setup.exe`) và tính năng Whisper AI có thể tiến hành hoàn toàn độc lập mà không bị phụ thuộc chéo.

