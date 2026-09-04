# 📚 DocumentConvertTool — Technical Documentation Index

Welcome to the central documentation hub for **DocumentConvertTool**. This repository follows strict software engineering documentation standards (Architecture Decision Records, Semantic Releases, Product Roadmaps, and Historical PR Archives).

---

## 📂 Documentation Directory Architecture

```text
docs/
├── README.md                             # Central index catalog
├── architecture/                         # Architecture Decision Records (ADRs)
│   ├── 001_portable_image_pipeline.md
│   ├── 002_overwrite_dialog_logic.md
│   ├── 003_flet_framework_limitations.md
│   ├── 004_win32_native_drag_drop_research.md
│   ├── 005_universal_dynamic_window_focus.md
│   ├── 006_parentheses_image_path_resolution_fix.md
│   └── 007_module_architecture_and_pptx_refactoring.md
├── roadmaps/                             # Active feature roadmaps & UI specifications
│   ├── pkb/                              # PKB-001 Detailed Phase Specifications
│   │   ├── phase1_tagging_wikilinks.md   # Phase 1: SQLite Index, Wikilinks & Backlinks (v1.10.0)
│   │   ├── phase2_mcp_server.md          # Phase 2: Local stdio MCP Server for Claude (v1.11.0)
│   │   ├── phase3_graph_view.md          # Phase 3: Interactive Knowledge Graph View (v1.12.0)
│   │   └── phase4_export_sync.md         # Phase 4: Obsidian Sync & Claude Projects Export (v1.13.0)
│   ├── pkb_feature_plan.md               # PKB-001 Master Architecture & Phased Blueprint
│   └── product_roadmap.md                # Master product roadmap
├── releases/                             # Version changelogs & release notes
│   ├── v1.5.0.md
│   ├── v1.5.3.md
│   ├── v1.6.0.md
│   ├── v1.6.0_en.md
│   └── v1.7.0.md
└── archive/                              # Completed snapshots, feature plans & PR logs
    ├── 20260904_whisper_model_optimization_and_vision_alignment.md
    ├── 20260903_whisper_feature_plan.md
    ├── 20260903_background_transcription_and_tabs.md
    ├── 20260902_image_regex_parentheses_and_preview_scroll_stabilization.md
    ├── 20260901_whisper_model_hub_and_hardware_orchestrator.md
    ├── 20260901_base64_cache_lru_eviction.md
    ├── 20260830_floating_image_formatting_multitab_footer_sync_and_explorer_polish.md
    ├── 20260829_tab_context_menu_micro_scrollbar_and_batch_polish.md
    ├── 20260829_multitab_session_performance_and_atomic_guards.md
    ├── 20260828_multi_tab_workspace.md
    ├── 20260828_explorer_context_menu_and_safe_file_operations.md
    ├── 20260827_studio_workspace_roadmap.md
    ├── 20260827_activity_bar_and_studio_workspace.md
    ├── 20260818_youtube_transcript_and_json_yaml_formatting_fixes.md
    ├── 20260818_simplified_ribbon_and_ui_polish.md
    ├── 20260818_plan_setup_exe.md
    ├── 20260817_pdf_card_tables_and_image_pipeline.md
    ├── 20260814_json_yaml_conversion_modules.md
    ├── 20260813_pptx_module_refactoring_and_table_deduplication.md
    ├── 20260812_pptx_conversion.md
    ├── 20260810_auto_draft_loading_ux_summary.md
    ├── 20260806_error_handling_draft_protection.md
    ├── 20260806_settings_help_ribbon_ui.md
    ├── 20260731_focus_zorder_analysis.md
    ├── 20260730_conversion_performance_analysis.md
    ├── 20260730_project_summary.md
    ├── 20260730_ribbon_ui_summary.md
    └── 20260729_refactoring_summary.md
```

---

## 📑 Documentation Catalog

### 🏛️ 1. Architecture Decision Records (`docs/architecture/`)

- [001_portable_image_pipeline.md](architecture/001_portable_image_pipeline.md): Automatic relative/absolute image path resolver for portable Markdown media assets.
- [002_overwrite_dialog_logic.md](architecture/002_overwrite_dialog_logic.md): Flet 0.86.4 Desktop modal dialog pattern & safe file overwrite protection logic.
- [003_flet_framework_limitations.md](architecture/003_flet_framework_limitations.md): Catalog of Flet framework constraints, icon naming rules, and API compatibility directives.
- [004_win32_native_drag_drop_research.md](architecture/004_win32_native_drag_drop_research.md): Empirical spike report on Win32 OLE `RegisterDragDrop` 2-Process boundary limitation and `desktop_drop` Flutter runner custom build guide.
- [005_universal_dynamic_window_focus.md](architecture/005_universal_dynamic_window_focus.md): Universal 100% dynamic window title matching & Win32 `AttachThreadInput` browser elevation solution.
- [006_parentheses_image_path_resolution_fix.md](architecture/006_parentheses_image_path_resolution_fix.md): Parentheses image path resolution fix for MediaAssetManager.
- [007_module_architecture_and_pptx_refactoring.md](architecture/007_module_architecture_and_pptx_refactoring.md): Document Module architecture, structural un-nesting of PPTXModule, and Markdown table parsing deduplication.
- [008_pdf_table_metric_and_win32_clipboard_architecture.md](architecture/008_pdf_table_metric_and_win32_clipboard_architecture.md): High-accuracy PDF table reconstruction and Win32 clipboard monitoring.
- [009_pdf_card_layout_and_artifact_filter_pipeline.md](architecture/009_pdf_card_layout_and_artifact_filter_pipeline.md): Adaptive PDF 2-column card layout and artifact filtering.
- [010_onedir_inno_setup_packaging_architecture.md](architecture/010_onedir_inno_setup_packaging_architecture.md): PyInstaller `--onedir` distribution combined with Inno Setup 7.
- [011_drag_drop_and_batch_archive_converter.md](architecture/011_drag_drop_and_batch_archive_converter.md): Smart Drag & Drop Markdown token insertion, filesystem move validator, and multi-threaded Batch & Archive conversion service.


---

### 🗺️ 2. Product Roadmaps (`docs/roadmaps/`)

- [product_roadmap.md](roadmaps/product_roadmap.md): Master product development roadmap and planned milestones.
- [pkb_feature_plan.md](roadmaps/pkb_feature_plan.md): Kế hoạch kiến trúc & phân công 4-phase cho Tagging, MCP Server, Graph View, Export Module (v1.10.0 → v1.13.0).
  - [phase1_tagging_wikilinks.md](roadmaps/pkb/phase1_tagging_wikilinks.md): Chi tiết kỹ thuật Phase 1 — SQLite Index, Wikilinks `[[...]]`, Fuzzy Matching & Backlink Panel (v1.10.0).
  - [phase2_mcp_server.md](roadmaps/pkb/phase2_mcp_server.md): Chi tiết kỹ thuật Phase 2 — Local stdio MCP Server cho Claude Desktop / Code (v1.11.0).
  - [phase3_graph_view.md](roadmaps/pkb/phase3_graph_view.md): Chi tiết kỹ thuật Phase 3 — Interactive Knowledge Graph View với NetworkX & SVG (v1.12.0).
  - [phase4_export_sync.md](roadmaps/pkb/phase4_export_sync.md): Chi tiết kỹ thuật Phase 4 — Obsidian Sync, Claude Projects Exporter & AI Auto-Link (v1.13.0).

---

### 🚀 3. Release Notes (`docs/releases/`)

- [v1.8.0.md](releases/v1.8.0.md): Version 1.8.0 Release Notes (Studio Workspace, Activity Bar Dock, Recursive File Explorer Tree with Inline Filter, Draggable Splitter, Quick Open `Ctrl+P`, and Overhauled 2x2 Welcome Screen).
- [v1.7.2.md](releases/v1.7.2.md): Version 1.7.2 Release Notes (Embedded Microsoft Edge WebView2 YouTube Companion Player with Clickable Transcript Seeking, Local HTTP Bridge Server, Win32 Dynamic Focus Elevation, and Inno Setup 7 Desktop Installer).
- [v1.7.0.md](releases/v1.7.0.md): Version 1.7.0 Release Notes (YouTube Subtitles/Transcript Extractor with Auto-Translate & Non-AI Speech Fallback, Direct Markdown Export, Win32 Clipboard URL Auto-Fill, Simplified Single-Row Ribbon, and JSON/YAML multiline fixes).
- [v1.6.0.md](releases/v1.6.0.md) ([English](releases/v1.6.0_en.md)): Version 1.6.0 Release Notes (PowerPoint Module `PPTX ↔ MD`, Architecture Refactoring, Table Parsing Deduplication, Word/PDF Formatting Fixes, and Universal Dynamic Window Focus).
- [v1.5.3.md](releases/v1.5.3.md): Version 1.5.3 Release Notes (Async draft restoration UX, 60fps LoadingView, 1-Click Smart Auto-Rename, and Exact Filename Highlight).
- [v1.5.0.md](releases/v1.5.0.md): Version 1.5.0 Release Notes (Ribbon UI, Theme/Palette hot-swapping, i18n localization, and Global Shortcut Manager).

---

### 📦 4. Historical Archive (`docs/archive/`)

#### Completed Feature Plans (moved from `roadmaps/`)
- [20260903_whisper_feature_plan.md](archive/20260903_whisper_feature_plan.md): Audio/Video Transcriber (Whisper AI) & Model Hub Marketplace — Architecture specification, 2-person responsibility matrix, hardware standards, and 3-phase sequential execution roadmap. ✅ All Phases Completed.
- [20260827_studio_workspace_roadmap.md](archive/20260827_studio_workspace_roadmap.md): Architecture evaluation & Studio Workspace design specification (Activity Bar, File Explorer, Draggable Splitter, Tab Manager). ✅ Completed (v1.8.0).
- [20260818_plan_setup_exe.md](archive/20260818_plan_setup_exe.md): `--onedir` packaging & Inno Setup 7 installer plan (AppId, user data protection, WebView2 runtime check, CI/CD automation). ✅ Completed (v1.7.2).

#### PR Completion Snapshots & Technical Logs
- [20260904_whisper_model_optimization_and_vision_alignment.md](archive/20260904_whisper_model_optimization_and_vision_alignment.md): Whisper Models Optimization, Hardware Recommendation Tuning & Vision Alignment (v1.9.1) — PhoWhisper retracted to Optional Add-on, real-world Vietnamese benchmark analysis (79.6s audio, sweet spot `whisper-small` ~7.4x realtime), CTranslate2 CPU 8-threads, Model Hub non-blocking toast SnackBar, progress throttle, 4-card equal-ratio grid, TranscribeDialog live % progress, and lightning emoji removal.
- [20260903_background_transcription_and_tabs.md](archive/20260903_background_transcription_and_tabs.md): Background Transcription, Tab Integration & Universal Media Support (Phase 3 — v1.9.0) — TranscribeDialog redesign, Activity Bar smart routing, background tab creation, draft persistence, Ribbon Bar toggle sync, and universal media container file dialog.
- [20260902_image_regex_parentheses_and_preview_scroll_stabilization.md](archive/20260902_image_regex_parentheses_and_preview_scroll_stabilization.md): Image regex parentheses fix and preview scroll position stabilization across tab switches.
- [20260901_whisper_model_hub_and_hardware_orchestrator.md](archive/20260901_whisper_model_hub_and_hardware_orchestrator.md): AI Model Hub Orchestrator, Multi-Vendor Hardware Detection & 2-Layer Verification Architecture (Phase 1 — v1.9.0).
- [20260901_base64_cache_lru_eviction.md](archive/20260901_base64_cache_lru_eviction.md): Bounded LRU Base64 cache with session-scoped eviction and thread-safe OrderedDict.
- [20260830_floating_image_formatting_multitab_footer_sync_and_explorer_polish.md](archive/20260830_floating_image_formatting_multitab_footer_sync_and_explorer_polish.md): Floating Image Formatting, Multi-Tab Footer Synchronization & Explorer UX Polish (v1.8.2) — Menu ngữ cảnh ảnh trên Preview, căn lề `<p align="...">` đồng bộ Word `.docx`, thiết kế lại `ImageSizeDialog` gọn gàng, đồng bộ Footer Bar theo từng Tab (`Per-Tab Hydration`), sửa cuộn/tràn viền Explorer, khôi phục thư mục mở rộng khi Refresh và kéo thả toàn vùng thư mục con.
- [20260829_tab_context_menu_micro_scrollbar_and_batch_polish.md](archive/20260829_tab_context_menu_micro_scrollbar_and_batch_polish.md): Workspace Tab Context Menu, Micro Scrollbar, Link Resolution & Batch Polish (v1.8.1c) — Menu chuột phải quản lý Tab, thanh cuộn mỏng 3px, bộ lọc file nén cho Batch Converter, tự động phân giải relative link cho tab Untitled và đề xuất tên lưu thông minh theo Heading.
- [20260829_multitab_session_performance_and_atomic_guards.md](archive/20260829_multitab_session_performance_and_atomic_guards.md): Multi-Tab Session Restoration, 0ms RAM Preview Cache & Atomic Concurrency Guards (v1.8.1b) — Bộ nhớ đệm Preview tức thì trong RAM, Pillow thumbnail downsampling giảm 96% dung lượng, và khóa tương tranh nguyên tử (Atomic UI Guard) chống ghi đè khi switch tab.
- [20260828_multi_tab_workspace.md](archive/20260828_multi_tab_workspace.md): Multi-Tab Workspace Architecture & AppState Delegation (v1.8.1b) — Kiến trúc đa Tab tài liệu độc lập, kéo thả sắp xếp tab (`ft.Draggable`), cô lập bản nháp `tab_session.json` và Media Session cache.
- [20260828_explorer_context_menu_and_safe_file_operations.md](archive/20260828_explorer_context_menu_and_safe_file_operations.md): Explorer Context Menu & Safe File Operations (v1.8.1a) — Menu chuột phải thông minh, Win32 `SHFileOperationW` Recycle Bin qua ctypes double-null, Smart 2-Tier Quick Convert (1-click to MD, 8-format hover flyout), nút Collapse All Folders, hover highlight và đồng bộ Footer Status.

- [20260827_activity_bar_and_studio_workspace.md](archive/20260827_activity_bar_and_studio_workspace.md): Studio Workspace & File Explorer Architecture (v1.8.0) — Activity Bar navigation, recursive File Explorer tree with inline filter, Quick Open fuzzy file search modal (`Ctrl+P`), 60fps Draggable Splitters with ratio persistence, and 2x2 Welcome View overhaul.
- [20260818_youtube_transcript_and_json_yaml_formatting_fixes.md](archive/20260818_youtube_transcript_and_json_yaml_formatting_fixes.md): YouTube Subtitles/Transcript Extractor (Multi-tier Strategy: Subtitles & Server-side Auto-Translate + Lightweight Non-AI Speech Fallback), Direct Markdown Export (`.md`), Win32 Clipboard (`Win + V`) & JSON/YAML multiline formatting fixes.
- [20260818_simplified_ribbon_and_ui_polish.md](archive/20260818_simplified_ribbon_and_ui_polish.md): Simplified Single-Row Ribbon and UI Polish.
- [20260814_json_yaml_conversion_modules.md](archive/20260814_json_yaml_conversion_modules.md): Bi-directional JSON ↔ MD & YAML ↔ MD conversion modules, Lazy Import Rule compliance, and unit tests integration.
- [20260813_pptx_module_refactoring_and_table_deduplication.md](archive/20260813_pptx_module_refactoring_and_table_deduplication.md): Refactoring log for PPTX un-nesting, table parsing deduplication, and cell formatting fixes.
- [20260812_pptx_conversion.md](archive/20260812_pptx_conversion.md): PowerPoint bi-directional conversion engine & dynamic window focus integration log.
- [20260810_auto_draft_loading_ux_summary.md](archive/20260810_auto_draft_loading_ux_summary.md): Auto-draft restoration UX, background image pre-loading, and smart overwrite modal.
- [20260806_error_handling_draft_protection.md](archive/20260806_error_handling_draft_protection.md): Production error mapper & draft autosave protection.
- [20260806_settings_help_ribbon_ui.md](archive/20260806_settings_help_ribbon_ui.md): Ribbon Bar tabs, Settings View, and Help View.
- [20260731_focus_zorder_analysis.md](archive/20260731_focus_zorder_analysis.md): Modal dialog focus management and Z-order stacking investigation.
- [20260730_conversion_performance_analysis.md](archive/20260730_conversion_performance_analysis.md): Benchmark analysis for multi-format extraction and conversion engines.
- [20260730_project_summary.md](archive/20260730_project_summary.md): Initial project setup and CTk -> Flet migration overview.
- [20260730_ribbon_ui_summary.md](archive/20260730_ribbon_ui_summary.md): Layout architecture design notes for Microsoft Office-style Ribbon UI.
- [20260729_refactoring_summary.md](archive/20260729_refactoring_summary.md): Summary of 3-Tier MVC architecture refactoring.
