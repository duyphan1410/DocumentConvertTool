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
├── roadmaps/                             # Feature roadmaps & UI specifications
│   ├── product_roadmap.md
│   └── studio_workspace_roadmap.md
├── releases/                             # Version changelogs & release notes
│   ├── v1.5.0.md
│   ├── v1.5.3.md
│   ├── v1.6.0.md
│   ├── v1.6.0_en.md
│   └── v1.7.0.md
└── archive/                              # PR completion snapshots & refactoring logs
    ├── 20260729_refactoring_summary.md
    ├── 20260730_conversion_performance_analysis.md
    ├── 20260730_project_summary.md
    ├── 20260730_ribbon_ui_summary.md
    ├── 20260731_focus_zorder_analysis.md
    ├── 20260806_error_handling_draft_protection.md
    ├── 20260806_settings_help_ribbon_ui.md
    ├── 20260810_auto_draft_loading_ux_summary.md
    ├── 20260812_pptx_conversion.md
    ├── 20260813_pptx_module_refactoring_and_table_deduplication.md
    ├── 20260814_json_yaml_conversion_modules.md
    └── 20260818_youtube_transcript_and_json_yaml_formatting_fixes.md
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

---

### 🗺️ 2. Product Roadmaps (`docs/roadmaps/`)

- [product_roadmap.md](roadmaps/product_roadmap.md): Master product development roadmap and planned milestones.
- [studio_workspace_roadmap.md](roadmaps/studio_workspace_roadmap.md): Design specifications for the upcoming Studio Workspace interface.

---

### 🚀 3. Release Notes (`docs/releases/`)

- [v1.8.0.md](releases/v1.8.0.md): Version 1.8.0 Release Notes (Studio Workspace, Activity Bar, File Explorer Tree with inline filter, Quick Open File Switcher `Ctrl+P`, 60fps Dual Draggable Splitters, and 2x2 Welcome Screen with `<kbd>` shortcut badges).
- [v1.7.0.md](releases/v1.7.0.md): Version 1.7.0 Release Notes (YouTube Subtitles/Transcript Extractor with Auto-Translate & Non-AI Speech Fallback, Direct Markdown Export, Win32 Clipboard URL Auto-Fill, Simplified Single-Row Ribbon, and JSON/YAML multiline fixes).
- [v1.6.0.md](releases/v1.6.0.md) ([English](releases/v1.6.0_en.md)): Version 1.6.0 Release Notes (PowerPoint Module `PPTX ↔ MD`, Architecture Refactoring, Table Parsing Deduplication, Word/PDF Formatting Fixes, and Universal Dynamic Window Focus).
- [v1.5.3.md](releases/v1.5.3.md): Version 1.5.3 Release Notes (Async draft restoration UX, 60fps LoadingView, 1-Click Smart Auto-Rename, and Exact Filename Highlight).
- [v1.5.0.md](releases/v1.5.0.md): Version 1.5.0 Release Notes (Ribbon UI, Theme/Palette hot-swapping, i18n localization, and Global Shortcut Manager).

---

### 📦 4. Historical Archive (`docs/archive/`)

- [20260827_activity_bar_and_studio_workspace.md](archive/20260827_activity_bar_and_studio_workspace.md): Studio Workspace & File Explorer Architecture (v1.8.0) — Activity Bar navigation, recursive File Explorer tree with inline filter, Quick Open fuzzy file search modal (`Ctrl+P`), 60fps Draggable Splitters with ratio persistence, and 2x2 Welcome View overhaul.
- [20260818_youtube_transcript_and_json_yaml_formatting_fixes.md](archive/20260818_youtube_transcript_and_json_yaml_formatting_fixes.md): YouTube Subtitles/Transcript Extractor (Multi-tier Strategy: Subtitles & Server-side Auto-Translate + Lightweight Non-AI Speech Fallback), Direct Markdown Export (`.md`), Win32 Clipboard (`Win + V`) & JSON/YAML multiline formatting fixes.
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
