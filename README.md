# Document Converter Workspace (v1.4.0)

![Python](<https://img.shields.io/badge/Python-3.12%20--%203.13-blue>)
![UI Framework](<https://img.shields.io/badge/UI-Flet%20Desktop%20%7C%203--Tier%20MVC-purple>)
![Platform](<https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-green>)
![Version](https://img.shields.io/badge/Version-1.4.0-brightgreen)
![License](https://img.shields.io/badge/License-AGPL--3.0-blue)

A modern desktop workspace for editing and converting documents between **Markdown**, **Excel**, **Word**, **PDF**, **CSV**, and **HTML** formats built with **Flet (Flutter for Python)**.

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
| **Word (`.docx`)** | ✅ | ✅ | Styled headings, clean structure, tables |
| **Excel (`.xlsx`)** | ✅ | ✅ | Multi-sheet parsing, frozen headers, auto-filters |
| **PDF (`.pdf`)** | ✅ | 🔄 v2.0 | Preserved list/bullet structure, Unicode Vietnamese fonts, `@media/` slide images |
| **CSV (`.csv`)** | ✅ | ✅ | Delimiter auto-detection, clean Markdown table generation |
| **HTML (`.html`)** | ✅ | ✅ | GitHub-flavored CSS styling, Pygments codehilite, safe regex code fence auto-repair |

### 🎨 Modern Flet UI & Architecture
* **3-Tier Pure MVC Architecture**: Clean decoupling between `Views`, `Controllers` (6 specialized controllers), `AppState`, and `Layout`.
* **Office Ribbon Navbar**: 4-tab navigation (`File`, `Edit`, `View`, `Options`) with zero-layout-shift collapsing.
* **Welcome Dashboard & Quick Open**: Instant onboarding card for new notes / quick document opening (`Ctrl+O`).
* **Live Document Preview**: Real-time Base64 RAM cache & dynamic image scaling with zero UI freezing (`asyncio.to_thread`).
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

## 🗺️ Version Roadmap

- **v1.0 — Core Engines**: Initial Word, Excel, CSV, PDF, HTML conversion modules.
- **v1.3 — Flet Desktop Migration**: Responsive split-pane layout, 5-palette theme engine, async loader.
- **v1.4 — Pure MVC & PDF Engine Polish (Current)**: 3-Tier MVC architecture (6 Controllers), Welcome Dashboard, Office Ribbon Bar, PDF list preservation & Vietnamese font fix, PyInstaller spec & dependency hardening.
- **v2.0 — Studio Workspace (Planned)**: Activity Bar (48px), File Tree Explorer, Multi-Tab workspace, Web SaaS & Installer packaging.

> [!NOTE]
> Detailed developer documentation, technical architecture summaries, and feature logs are organized in the [`docs/`](docs/) directory.

---

## ⚠️ Known Limitations

* **Large Documents:** Document preview is optimized for smooth editing performance; full file contents are converted completely during processing.
* **Complex Styles:** Advanced Office layout elements (floating text boxes, multi-column macros) are simplified into clean, standardized Markdown structures.

---

## 👥 Authors & Contributors

* **Duy Phan** ([@duyphan1410](https://github.com/duyphan1410)) — Core Architecture, UI Framework & Conversion Service Lead.
* **Satoou19 (Huy)** — Document Modules Overhaul, PDF & Image Handling Specialist.

---

## 📄 License

GNU AGPLv3 — Copyright (c) 2026 Duy Phan & Contributors
