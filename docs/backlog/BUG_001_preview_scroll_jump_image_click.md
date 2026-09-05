# [Backlog & Bug] Preview Scroll Jump khi Tương Tác với Ảnh trong Live Preview

**Mã định danh**: `BUG-001`  
**Ngày khởi tạo**: 01/09/2026  
**Ngày hoàn thành**: 02/09/2026  
**Nhánh thực hiện**: `fix/duy-02092026-image-regex-and-smooth-preview`  
**Phân loại**: Bug / UX Stabilization  
**Mức độ ưu tiên**: High  
**Trạng thái**: 🟢 Completed (Đã giải quyết triệt để lỗi mất vị trí cuộn / nhảy lên đầu; Ghi nhận giới hạn độ trễ layout của Flutter)

---

## 1. Hiện trạng & Phân tích nguyên nhân gốc (Problem Statement)

Khi người dùng click vào ảnh hoặc áp dụng thay đổi kích cỡ/căn lề qua Context Menu trong panel Live Preview:
1. **Focus Arena & Pointer Interrupt**: Cử chỉ `on_tap_down` khiến Flutter hủy `ScrollDragController` khi menu overlay xuất hiện, đẩy thanh cuộn về vị trí gốc (`112.2px`).
2. **Rebuild Reset**: `scroll_column.update()` khiến Flutter hủy và tạo lại cây RenderObject, làm mất `ScrollController` offset.
3. **Async Base64 Layout Measurement**: Khi tài liệu chứa 30+ ảnh Base64 lớn và sơ đồ Mermaid, `maxScrollExtent` của Flutter tăng dần trong 100–350ms. Lệnh `scroll_to` ở frame đầu tiên bị clamp lại ở độ cao tạm thời nếu không có cơ chế progressive retry.

---

## 2. Thiết kế giải pháp kỹ thuật (Architecture & Implementation)

### 2.1. Tách biệt Gesture Events
- `on_tap_down`: Chỉ ghi nhận tọa độ `(gx, gy)`.
- `on_tap`: Nhả chuột sạch sẽ mới mở Context Menu $\rightarrow$ triệt tiêu xung đột gesture.

### 2.2. Multi-Stage Progressive Scroll Restoration
- Sử dụng vòng lặp khôi phục đa tầng `(0.0s, 0.02s, 0.06s, 0.15s, 0.35s)` với cờ khóa `_is_restoring_scroll = True`.
- Đảm bảo thanh cuộn luôn bám dính chính xác vị trí ảnh mục tiêu sau khi toàn bộ ảnh Base64 được đo lường xong chiều cao.

### 2.3. Khôi phục tự động tại mọi trạng thái Menu
- Tự động gọi `restore_scroll()` khi menu mở, khi bấm chọn option và khi click ra ngoài để đóng menu (`_on_image_menu_dismissed`).

---

## 3. Ghi nhận giới hạn kỹ thuật (Known Limitation & Future RFC)

> [!NOTE]
> **Hiện tượng giật nhẹ (Micro-jitter ~100-300ms) khi resize ảnh**:
> Do cơ chế Layout của Flutter Desktop cần từ 100ms đến 350ms để tính toán lại chiều cao chính xác của 30+ ảnh Base64 và các khối Mermaid, chu kỳ `Multi-Stage Progressive Restore` sẽ thực hiện điều chỉnh vị trí cuộn trong khoảng thời gian này.
> **Đánh giá**: Đây là giới hạn kiến trúc chấp nhận được (Trade-off) để bảo đảm 100% tài liệu **không bị lạc vị trí / cuộn về đầu trang**, phù hợp với bản dựng hiện tại.
> **Hạng mục đề xuất tiếp theo**: `PERF-002: Preview ListView.builder / Virtual Scroll Engine` để ảo hóa danh sách khi tải tài liệu siêu lớn.

---

## 4. Tiêu chí nghiệm thu (Acceptance Criteria)

- [x] Click vào ảnh ở bất kỳ vị trí nào trong Preview, scroll position KHÔNG bị mất / không bị cuộn lên đầu.
- [x] Context menu xuất hiện chính xác tại vị trí click.
- [x] Áp dụng size preset (25%, 50%, 75%, 100%) và căn lề (Left, Center, Right) luôn giữ vững vị trí ảnh.
- [x] Click ra ngoài đóng menu giữ nguyên vị trí cuộn.
- [x] Không phát sinh cảnh báo Coroutine unawaited.
- [x] 163/163 Unit Tests đạt PASS 100%.
