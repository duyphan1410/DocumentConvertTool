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
│   └── 004_win32_native_drag_drop_research.md
├── roadmaps/                             # Feature roadmaps & UI specifications
│   ├── product_roadmap.md
│   └── studio_workspace_roadmap.md
├── releases/                             # Version changelogs & release notes
│   └── v1.5.0.md
└── archive/                              # PR completion snapshots & refactoring logs
    ├── PR_06082026_error_handling_draft_protection.md
    ├── PR_06082026_settings_help_ribbon_ui.md
    ├── conversion_performance_analysis.md
    ├── focus_zorder_analysis.md
    ├── project_summary.md
    ├── refactoring_summary.md
    └── ribbon_ui_summary.md
```

---

## 📑 Documentation Catalog

### 🏛️ 1. Architecture Decision Records (`docs/architecture/`)

- [001_portable_image_pipeline.md](file:///c:/Users/Admin/Desktop/DocumentConvertTool/docs/architecture/001_portable_image_pipeline.md): Automatic relative/absolute image path resolver for portable Markdown media assets.
- [002_overwrite_dialog_logic.md](file:///c:/Users/Admin/Desktop/DocumentConvertTool/docs/architecture/002_overwrite_dialog_logic.md): Flet 0.86.4 Desktop modal dialog pattern & safe file overwrite protection logic.
- [003_flet_framework_limitations.md](file:///c:/Users/Admin/Desktop/DocumentConvertTool/docs/architecture/003_flet_framework_limitations.md): Catalog of Flet framework constraints, icon naming rules, and API compatibility directives.
- [004_win32_native_drag_drop_research.md](file:///c:/Users/Admin/Desktop/DocumentConvertTool/docs/architecture/004_win32_native_drag_drop_research.md): Empirical spike report on Win32 OLE `RegisterDragDrop` 2-Process boundary limitation and `desktop_drop` Flutter runner custom build guide.

---

### 🗺️ 2. Product Roadmaps (`docs/roadmaps/`)

- [product_roadmap.md](file:///c:/Users/Admin/Desktop/DocumentConvertTool/docs/roadmaps/product_roadmap.md): Master product development roadmap and planned milestones.
- [studio_workspace_roadmap.md](file:///c:/Users/Admin/Desktop/DocumentConvertTool/docs/roadmaps/studio_workspace_roadmap.md): Design specifications for the upcoming Studio Workspace interface.

---

### 🚀 3. Release Notes (`docs/releases/`)

- [v1.5.0.md](file:///c:/Users/Admin/Desktop/DocumentConvertTool/docs/releases/v1.5.0.md): Version 1.5.0 Release Notes (Ribbon UI, Theme/Palette hot-swapping, i18n localization, and Global Shortcut Manager).

---

### 📦 4. Historical Archive (`docs/archive/`)

- `PR_06082026_error_handling_draft_protection.md`: Pull Request summary for production error mapper & draft autosave protection.
- `PR_06082026_settings_help_ribbon_ui.md`: Pull Request summary for Ribbon Bar tabs, Settings View, and Help View.
- `conversion_performance_analysis.md`: Benchmark analysis for multi-format extraction and conversion engines.
- `focus_zorder_analysis.md`: Modal dialog focus management and Z-order stacking investigation.
- `project_summary.md`: Initial project setup and CTk -> Flet migration overview.
- `refactoring_summary.md`: Summary of 3-Tier MVC architecture refactoring.
- `ribbon_ui_summary.md`: Layout architecture design notes for Microsoft Office-style Ribbon UI.
