# 🕸️ PKB Phase 3: Interactive Knowledge Graph View (v1.12.0)

**Mã định danh**: `PKB-PHASE-3`  
**Phiên bản mục tiêu**: `v1.12.0`  
**Tài liệu mẹ**: [pkb_feature_plan.md](../pkb_feature_plan.md)  
**Phụ thuộc**: Hoàn thành [Phase 1: Tagging & Wikilinks](phase1_tagging_wikilinks.md) (Đọc trực tiếp từ SQLite index)  
**Phụ trách chính**: 👤 Duy (UI/UX Flet, Graph Layout & SVG Render Engine)  
**Trạng thái**: ⏳ Planned

---

## 1. Mục tiêu & Trải nghiệm Người dùng

DocConvert v1.12.0 cung cấp giao diện **Knowledge Graph View** 2D tương tác trực quan, giúp người dùng nắm bắt cấu trúc mạng lưới tri thức, khám phá mối liên hệ tiềm ẩn giữa các ghi chú/tài liệu trong Workspace.

### Điểm nhấn trải nghiệm:
- **Tập trung vào ngữ cảnh (Ego Network)**: Mặc định hiển thị mạng lưới đồ thị **2-hop** xung quanh tài liệu đang mở (Active Document) thay vì tải toàn bộ hàng nghìn nốt gây lag và rối mắt.
- **Tương tác trực tiếp (Click-to-Navigate)**: Nhấp vào bất kỳ nốt (node) nào trên đồ thị sẽ tự động mở tài liệu tương ứng trong một tab mới trên Workspace.
- **Bộ lọc đa chiều (Dynamic Filtering)**: Lọc tức thì theo thẻ (tags), từ khóa tìm kiếm, hoặc điều chỉnh bán kính độ sâu (1-hop, 2-hop, 3-hop, hoặc toàn bộ Workspace).

---

## 2. Kiến trúc Kỹ thuật & Pipeline Render

```text
[SQLite Index (index.db)]
        │
        ▼
[src/services/graph_service.py]
  - Query nodes (documents) & edges (wikilinks, shared tags)
  - Build NetworkX DiGraph
  - Compute 2D Positions via Force-Directed Layout (Spring Layout)
        │
        ▼
[src/utils/svg_graph_builder.py]
  - Generate clean vector SVG with nodes, edges, labels, hover zones
        │
        ▼
[src/ui_flet/views/graph_view.py]
  - Render SVG inside Flet interactive canvas / container
  - Handle Pan, Zoom & Node Click events via coordinates mapping
```

---

## 3. Đặc tả Chi tiết các Thành phần

### 3.1. Thuật toán Bố cục Đồ thị (`graph_service.py`)
- Sử dụng thư viện `networkx`:
  ```python
  import networkx as nx

  def build_ego_graph(center_doc_id: str, radius: int = 2) -> nx.DiGraph:
      full_graph = load_graph_from_sqlite()
      # Trích xuất đồ thị con 2-hop quanh node đang mở
      ego = nx.ego_graph(full_graph, center_doc_id, radius=radius)
      # Tính toán tọa độ 2D bằng thuật toán Fruchterman-Reingold
      pos = nx.spring_layout(ego, k=0.3, iterations=50, seed=42)
      return ego, pos
  ```
- **Trọng số liên kết (Edge Weight)**:
  - Liên kết Wikilink rõ ràng (`[[...]]`): Weight = 2.0 (hút gần nhau hơn).
  - Chung thẻ Tag: Weight = 0.5 (hút nhẹ để nhóm các cụm chủ đề).

### 3.2. Vector SVG Generator (`svg_graph_builder.py`)
- Render vector SVG chuẩn XML:
  - **Edges (Cạnh)**: Đường kẻ cong bezier hoặc thẳng với độ mờ (opacity: 0.4), màu phụ thuộc vào theme (Dark/Light).
  - **Nodes (Điểm nút)**:
    - Node trung tâm: Bán kính lớn (R=12px), viền sáng màu Primary Palette.
    - Node 1-hop: Bán kính vừa (R=8px).
    - Node 2-hop: Bán kính nhỏ (R=6px).
  - **Labels (Nhãn văn bản)**: Tên file rút gọn, hiển thị rõ ràng khi zoom hoặc hover.

### 3.3. Giao diện Flet & Điều khiển (`graph_view.py`)
- **Activity Bar Entry**: Bổ sung icon `ft.Icons.HUB` hoặc `ft.Icons.SCHEMA` trên Activity Bar để mở toàn màn hình Graph View hoặc mở dạng Split Pane cạnh Editor.
- **Thanh công cụ điều khiển (Control Overlay)**:
  - Thanh trượt Zoom (`+`, `-`, `Fit to Screen`).
  - Dropdown chọn số hop: `1-hop`, `2-hop (Khuyên dùng)`, `Toàn bộ kho`.
  - Dropdown lọc theo Tag: Chọn một hoặc nhiều tag để highlight các cụm chủ đề.

---

## 4. Tối ưu Hiệu năng & Ngưỡng an toàn (Guards)

1. **Giới hạn nốt an toàn (Node Threshold Guard)**:
   - Render SVG tĩnh trong Flet mượt mà và tối ưu nhất trong khoảng **100 – 150 nốt**.
   - Nếu đồ thị toàn bộ workspace vượt quá **150 nốt**:
     - Hệ thống sẽ tự động chuyển sang chế độ **Ego 2-hop** mặc định.
     - Hiển thị thông báo nhẹ (Banner): *"Kho tri thức lớn (>150 nốt). Đang hiển thị mạng lưới 2-hop quanh ghi chú hiện tại để đảm bảo độ mượt 60fps"*.
2. **Kéo thả mượt mà**:
   - Nếu trong tương lai cần thao tác physics kéo thả nốt thời gian thực kiểu Canvas WebGL, kiến trúc sẵn sàng mở rộng tích hợp qua `pywebview` nhúng Sigma.js / Cytoscape.js mà không phá vỡ tầng data layer.
