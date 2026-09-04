# Whisper Models Optimization, Hardware Recommendation Tuning & Vision Alignment (v1.9.1)

**Phiên bản**: `v1.9.1`  
**Ngày cập nhật**: 04/09/2026  
**Nhánh liên quan**: `fix/duy-04092026-whisper-model-optimization`  

---

## 1. Tầm Nhìn & Bối Cảnh (Executive Summary & Vision Shift)

Sau khi hoàn thành bản phát hành `v1.9.0` (Phase 3: Background Transcription & Tab Integration), quá trình thử nghiệm thực tế với các tập tin âm thanh thực tế (hội thoại tiếng Việt, thuật ngữ game, bài giảng) đã đặt ra yêu cầu tái cấu trúc tầm nhìn và tối ưu hóa hệ thống nhận diện giọng nói:

1. **Định vị Bộ 4 Mô Hình Chuẩn**:
   - Hệ sinh thái 4 model chuẩn (`whisper-base`, `whisper-small`, `whisper-medium`, `whisper-large-v3`) được hoàn thiện với SHA256 checksums chuẩn từ Hugging Face.
   - Kế hoạch `PhoWhisper` được chuyển từ tính năng trọng tâm của v1.9.1 sang **Optional Add-on dự phòng**, do bộ model Whisper chuẩn đa ngữ xử lý các từ mượn, thuật ngữ công nghệ và tiếng Anh xen lẫn tiếng Việt tự nhiên và chính xác hơn đáng kể.
2. **Khuyến Nghị Phần Cứng Thực Tế (CPU Sweet Spot)**:
   - Trước đây, thuật toán tự động khuyến nghị `whisper-medium` cho các CPU nhiều nhân (>= 6 cores). Tuy nhiên, trên CPU không có card đồ họa CUDA, `whisper-medium` tốn gần 30s cho 80s âm thanh (~2.8x realtime).
   - `whisper-small` đạt tốc độ ấn tượng (~7.4x realtime, chỉ mất ~10.8s cho 80s âm thanh) trong khi chất lượng nhận diện từ ngữ tiếng Việt/tiếng lóng vượt trội hoàn toàn so với `base`. Vì vậy, `whisper-small` chính thức trở thành **Sweet Spot** được đề xuất mặc định cho người dùng CPU.
3. **Trải Nghiệm Người Dùng (UX/UI Polish)**:
   - Thay thế hộp thoại thông báo modal bằng Toast SnackBar không chặn luồng khi tải xong model, giữ nguyên trạng thái mở của Model Hub Dialog.
   - Thắt chặt tần suất cập nhật tiến trình (~6 lần/giây) tránh hiện tượng giật lag GUI khi tải song song.
   - Căn chỉnh 4 card model co giãn tự động theo tỷ lệ đều 25% trên thanh trượt.
   - Loại bỏ biểu tượng tia sét khỏi toàn bộ nhãn văn bản và giao diện theo yêu cầu nhận diện thương hiệu.

---

## 2. Dữ Liệu Benchmark Thực Nghiệm (Real-World Benchmark)

Kiểm thử trực tiếp trên phần cứng AMD Ryzen 5 5600H (12 Threads, 3.3GHz, 16GB RAM) với tập tin âm thanh tiếng Việt thực tế (`Set up wave = win .mp3`, thời lượng: **79.6s**):

| Model | Thời gian xử lý | Tốc độ tương đối | Số Segments | Khả năng nhận diện ngữ cảnh tiếng Việt & Gaming Jargon |
| :--- | :---: | :---: | :---: | :--- |
| **whisper-base** | **4.99s** | ~15.93x realtime | 13 | Bỏ sót và sai lệch nhiều từ ngữ: *"Cà Lý"* (Kali), *"sét ức"* (setup), *"không F lớn được"* (không ép lính được). |
| **whisper-small** | **10.81s** | **~7.36x realtime** | 14 | **Cân bằng hoàn hảo**: Nhận diện đúng *"Kali"*, *"set up rồi đó"*, *"không F lính được"*. Xử lý 80s chỉ tốn ~11s trên CPU. |
| **whisper-medium**| **28.86s** | ~2.76x realtime | 13 | **Chính xác tuyệt đối**: Nhận diện chuẩn xác tiếng lóng game (*"núp để hít F"*, *"setup rồi đó"*, *"không F lính được"*). Tốn gần 29s. |

> **Kết luận Thực nghiệm**:  
> Đối với người dùng không có GPU rời (chạy thuần CPU), `whisper-small` mang lại chất lượng bản dịch tốt nhất mà không gây cảm giác chờ đợi nặng nề.

---

## 3. Các Giải Pháp Kỹ Thuật Đã Triển Khai

### 3.1. Tối Ưu Hóa Bộ Đề Xuất Phần Cứng (`src/services/hardware_detector.py`)
- Cập nhật hàm `recommend_model()`: Với môi trường CPU (không có CUDA), máy từ 8GB RAM trở lên và $\ge 4$ nhân vật lý sẽ được khuyến nghị `whisper-small`.
- Giữ `whisper-medium` và `whisper-large-v3` dành riêng cho hệ thống có GPU NVIDIA hỗ trợ CUDA ($\ge 4\text{GB}$ VRAM).

### 3.2. Điều Chỉnh Đa Luồng CTranslate2 (`src/services/whisper_service.py`)
- Nâng cấu hình số luồng tính toán CPU từ 4 luồng cố định lên tối đa 8 luồng vật lý (`min(8, os.cpu_count() or 1)`), khai thác tối đa sức mạnh của CPU hiện đại.

### 3.3. Tinh Chỉnh Model Hub Dialog (`src/ui_flet/components/model_hub_dialog.py`)
- Chuyển đổi thông báo tải thành công sang `ft.SnackBar` hiển thị góc dưới, loại bỏ hộp thoại modal chặn luồng gây ngắt kết nối với cửa sổ cha.
- Thêm cơ chế throttle thanh tiến trình: chỉ gọi `page.update()` tối đa ~6 lần/giây nhằm chống nghẽn luồng UI khi download file tốc độ cao.
- Điều chỉnh tỷ lệ grid card: Đặt `expand=1` cho cả 4 card model giúp giao diện dãn đều mép sang mép trên mọi kích thước cửa sổ.

### 3.4. Bổ Sung Callback Tiến Trình Cho Transcribe Dialog (`src/ui_flet/components/transcribe_dialog.py`)
- Kết nối trực tiếp `on_progress` từ `transcribe_file()` lên thanh progress bar, hiển thị định dạng trực quan: `Transcribing X% (current_s / total_s)...`.
- Bổ sung huy hiệu và mô tả ngữ cảnh sử dụng cho từng model trong dropdown chọn lựa.

### 3.5. Công Cụ Benchmark Thực Nghiệm (`scripts/benchmark_models.py`)
- Xây dựng script kiểm thử benchmark độc lập cho phép chỉ định số giây cần cắt âm thanh (`python scripts/benchmark_models.py [slice_seconds]`).
- Tự động đo thời gian tiền xử lý audio 16kHz, thời gian chạy từng model và in bảng so sánh chất lượng văn bản transcription đối chiếu.

---

## 4. Danh Sách Commits Trên Nhánh `fix/duy-04092026-whisper-model-optimization`

1. `feeb2f7` **fix(service)**: `optimize whisper hardware recommendations, download validation, and cpu threads`
2. `d9a5546` **feat(i18n)**: `update model guidance, descriptions, and remove lightning icon`
3. `490b65b` **fix(ui)**: `improve model hub layout, toast notifications, and transcription progress`
4. `921743c` **test(speech)**: `add slice benchmark tool, update model manager and detector tests`
5. `87ecbec` **chore(release)**: `bump version to v1.9.1`
6. `880a7df` **docs(roadmap)**: `refine whisper model roadmap and add pkb phased feature plan`

---

## 5. Đánh Giá Rủi Ro & Khả Năng Mở Rộng
- **Mức độ rủi ro**: THẤP (Low).
- **Phạm vi tác động**: Giới hạn trong phân hệ nhận diện giọng nói (Audio Transcriber, Model Hub, Hardware Detector). Toàn bộ các pipeline chuyển đổi tài liệu khác (DOCX, PDF, XLSX, PPTX, MD) hoàn toàn không bị ảnh hưởng.
