# Document Converter Workspace (v1.6.6)

![Python](https://img.shields.io/badge/Python-3.12%20--%203.13-blue)
![UI Framework](https://img.shields.io/badge/UI-Flet%20Desktop%20%7C%203--Tier%20MVC-purple)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D4)
![Version](https://img.shields.io/badge/Version-1.6.6-brightgreen)
![License](https://img.shields.io/badge/License-AGPL--3.0-blue)

A modern desktop workspace for editing and converting documents between **Markdown**, **PowerPoint**, **Excel**, **Word**, **PDF**, **CSV**, **HTML**, **JSON**, and **YAML** formats built with **Flet (Flutter for Python)**.

---

## 📥 Download

Download the latest standalone executable (no Python installation required):

➡️ [**Download Document Converter (v1.6.6) for Windows**](https://github.com/duyphan1410/DocumentConvertTool/releases/latest)

<small>⚠️ *Windows SmartScreen may warn because the application is unsigned. Click **More info → Run anyway** if prompted.*</small>

---

## 📸 Screenshots & Themes

| Dark Mode (Violet Cyberpunk) | Light Mode (Light Theme) |
| :--------------------------: | :---------------------------------: |
| ![Dark Mode](assets/demo/screenshot_dark.png) | ![Light Mode](assets/demo/screenshot_light.png) |

---

## ✨ Key Features

### 📄 Document Conversion Matrix

| Format | Import to Markdown (`➔ .md`) | Export from Markdown (`.md ➔`) | Highlights |
| :--- | :---: | :---: | :--- |
| **PowerPoint (`.pptx`)** | ✅ | ✅ | 16:9 Widescreen slides, auto-numbering, chart data extraction, legend padding, slide overflow protection, slide notes bullets |
| **Word (`.docx`)** | ✅ | ✅ | Styled headings, clean structure, tables |
| **Excel (`.xlsx`)** | ✅ | ✅ | Multi-sheet parsing, frozen headers, auto-filters |
| **PDF (`.pdf`)** | ✅ | ✅ | Geometric multi-column card tables, hierarchy tree alignment, SMask alpha compositing, shadow/halo artifact elimination, 20x fast thumbnail analysis |
| **CSV (`.csv`)** | ✅ | ✅ | Delimiter auto-detection, clean Markdown table generation |
| **HTML (`.html`)** | ✅ | ✅ | GitHub-flavored CSS styling, Pygments codehilite, safe regex code fence auto-repair |
| **JSON (`.json`)** | ✅ | ✅ | Tabular array-to-table conversion, nested key-value formatting, fenced code blocks |
| **YAML (`.yaml`, `.yml`)** | ✅ | ✅ | Structured tree formatting, pipe table conversion, safe PyYAML parsing |

### 🎨 Modern Flet UI & Architecture
* **3-Tier Pure MVC Architecture**: Clean decoupling between `Views`, `Controllers` (6 specialized controllers), `AppState`, and `Layout`.
* **Production Error Handling & Modal System**: Standardized `DocumentError` domain exceptions (10 `ErrorCode`s), `ErrorMapper` stage context, and theme-aware `MessageDialog` modals with Error ID tracking and one-click copy.
* **Single Responsibility Autosave Draft Protection**: Preserves `draft_autosave.md` safely across welcome screens, startup, and file loads; cancels pending timers before text clear.
* **Office Ribbon Navbar**: 4-tab navigation (`File`, `Edit`, `View`, `Options`) with zero-layout-shift collapsing.
* **Welcome Dashboard & Quick Open**: Instant onboarding card for new notes / quick document opening (`Ctrl+O`).
* **Live Document Preview**: Real-time Base64 RAM cache & dynamic image scaling with zero UI freezing (`asyncio.to_thread`).
* **Universal Dynamic Win32 Focus & Browser Elevation**: 100% dynamic title-based window matching and `AttachThreadInput` Win32 API thread input attachment for seamless active focus across all Windows editors and web browsers.
* **Instant 5-Palette Theme Engine**: Deep Ocean, Violet Cyberpunk, Emerald Obsidian, Slate Minimal, Amber Gold.

---

## 🚀 Quick Start

### Installation & Running

```powershell
# Clone the repository
git clone https://github.com/duyphan1410/DocumentConvertTool.git
cd DocumentConvertTool

# Install dependencies
pip install -r requirements.txt

# Run application
python run.py
```

### Packaging Executable (PyInstaller)

```powershell
python -m PyInstaller "Document Converter.spec"
```
The output executable will be created at `dist/Document Converter.exe`.

---

## 🗺️ Version History

- **v1.0 — Core Engines**: Initial Word, Excel, CSV, PDF, HTML conversion modules.
- **v1.3 — Flet Desktop Migration**: Responsive split-pane layout, 5-palette theme engine, async loader.
- **v1.4 — Pure MVC & PDF Engine Polish**: 3-Tier MVC architecture (6 Controllers), Welcome Dashboard, Office Ribbon Bar, PDF list preservation & Vietnamese font fix.
- **v1.5 — Error Handling, Draft Protection & Auto-Loading UX**: 10 `ErrorCode`s, autosave draft protection, 60fps async loading view, 1-click smart auto-rename & localized path bar.
- **v1.6 — PowerPoint Engine, Universal Dynamic Focus & Browser Elevation**: Bi-directional PPTX ↔ MD engine (16:9 widescreen, auto-numbering, chart extraction, legend padding, slide overflow protection), 100% dynamic Win32 window focus & `AttachThreadInput` browser elevation.
- **v1.6.5 — JSON & YAML Modules**: Bi-directional JSON ↔ MD & YAML ↔ MD conversion plugins (pipe table conversion, nested object tree formatting, code block fallback, safe PyYAML lazy loading).
- **v1.6.6 — PDF Card Table Layout, Image Artifact Filter & High-Speed Pipeline (Current)**: N-column spatial card table router ($N=2..5$), hierarchy tree alignment, illustration pseudo-table linguistic guard, Polaroid blank core frame filter, button glow/halo filter, and thumbnail downsampling (20x faster).

> [!NOTE]
> Detailed developer documentation, technical architecture summaries, and feature logs are organized in the [`docs/`](docs/) directory.

---

## ⚠️ Known Limitations

* **Drag & Drop:** Dragging files directly from Windows File Explorer onto the application window is currently not supported in Flet Desktop; please use the **Open Document** button (`Ctrl+O`) to load files.
* **Large Documents:** Document preview is optimized for smooth editing performance; full file contents are converted completely during processing.
* **Complex Styles:** Advanced Office layout elements (floating text boxes, multi-column macros) are simplified into clean, standardized Markdown structures.

---

## 👥 Authors & Contributors

* **Duy Phan** ([@duyphan1410](https://github.com/duyphan1410)) — Core Architecture, UI Framework & Conversion Service Lead.
* **Satoou19 (Huy)** — Document Modules Overhaul, PDF & Image Handling Specialist.

---

## 📄 License

GNU AGPLv3 — Copyright (c) 2026 Duy Phan & Contributors
