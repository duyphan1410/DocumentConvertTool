# Document Converter Workspace (v1.9.2)

![Python](https://img.shields.io/badge/Python-3.12%20--%203.13-blue)
![UI Framework](https://img.shields.io/badge/UI-Flet%20Desktop%20%7C%20Studio%20MVC-purple)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D4)
![Version](https://img.shields.io/badge/Version-1.9.2-brightgreen)
![License](https://img.shields.io/badge/License-AGPL--3.0-blue)

A modern, studio-grade desktop workspace for editing, transcribing, and converting documents between **Markdown**, **PowerPoint**, **Excel**, **Word**, **PDF**, **Scanned PDF (OCR)**, **CSV**, **HTML**, **JSON**, **YAML**, and **Audio/Video Media** formats built with **Flet (Flutter for Python)**.

---

## 📥 Download

Download the latest standalone installer (no Python installation required):

➡️ [**Download Document Converter (v1.9.2) for Windows**](https://github.com/duyphan1410/DocumentConvertTool/releases/latest)

<small>⚠️ *Windows SmartScreen may warn because the application is unsigned. Click **More info → Run anyway** if prompted.*</small>

---

## 📸 Screenshots & Themes

| Dark Mode (Violet Cyberpunk) | Light Mode (Light Theme) |
| :--------------------------: | :---------------------------------: |
| ![Dark Mode](assets/demo/screenshot_dark.png) | ![Light Mode](assets/demo/screenshot_light.png) |

---

## ✨ Key Features

### 🧠 AI Model Hub & Offline Speech Transcriber (Whisper AI)
* **100% Offline Speech-to-Text**: High-accuracy local speech transcription for `.mp3`, `.wav`, `.m4a`, `.flac`, `.aac`, `.ogg`, `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm` with zero data sent over the Internet.
* **AI Model Hub & Marketplace**: Built-in model manager for downloading, verifying (SHA256 checksums), and managing Whisper models (`base`, `small`, `medium`, `large-v3`) at `%APPDATA%\DocConvert\models\`.
* **Hardware-Aware Recommendation Engine**: Scans CPU cores, available system RAM, and NVIDIA CUDA GPUs (VRAM & Driver) to recommend the optimal AI model for your PC.
* **Voice Activity Detection & Timestamps**: Silero VAD segmentation and audio normalization (-0.9 dBFS) producing structured Markdown with interactive `[mm:ss]` timestamps.
* **Background Transcription & Smart Tab Routing**: Transcribes large media in the background without UI freeze, automatically spawning and hydrating dedicated Workspace Tabs upon completion.

### 👁️ OCR Scanned PDF Engine & Media Services
* **Scanned PDF to Markdown (`pdf_scan_to_md`)**: Multi-tier optical character recognition engine automatically extracting and formatting text from image-only and scanned PDF documents.
* **YouTube & Drive Transcriber**: Multi-tier subtitle extraction: Tier 1 Subtitles & Auto-Translate (0% CPU/RAM), Tier 2 Whisper AI Fallback (`faster-whisper`), oEmbed metadata, clickable timestamps & Companion Player.
* **In-App YouTube Companion Player**: Dedicated Edge WebView2 mini player (`540x335`, 16:9) with clickable timestamp seeking (`yt://...`), local HTTP bridge server (Error 153 immune), and Win32 focus elevation.

### 🗂️ Studio Workspace & File Management
* **Recent Files & Folders History**: Persistent LRU activity store at `%APPDATA%\DocConvert\recent_history.json` with Pinning (`📌 Pin`), Search filtering, Tab categories (`All` / `Files` / `Folders`), and missing file detection.
* **2-Column Welcome Studio Dashboard**: Clean 2-column layout (Quick Actions & Branding on the left, Recent History & Workspace shortcuts on the right) with Home button (`ft.Icons.HOME_ROUNDED`) navigation.
* **Multi-Window Support (`Ctrl+Shift+N`)**: Launch independent workspace windows with native Win32 foreground elevation.
* **Activity Bar Navigation**: Professional vertical dock (48px) with customizable left/right sidebar positioning, active highlight indicators, and workspace switcher.
* **File Explorer Sidebar**: Recursive workspace directory tree with extension-specific icon mapping, breadcrumb headers, single/double-click instant file opening, inline real-time search filter, and recursive *Collapse All Folders*.
* **Explorer Context Menu & Safe File Operations**: Floating right-click context menu with Win32 `SHFileOperationW` Recycle Bin deletion (zero data loss), Windows naming constraint validation, case-only rename support, unsaved changes (`is_dirty`) protection warnings, and new Markdown/Folder creation.
* **Multi-Tab Workspace**: Independent document tabs with `ft.Draggable` tab reordering, `tab_session.json` draft persistence, per-tab footer sync, and 0ms RAM preview caching.
* **Smart Drag & Drop**: Drag files from Explorer into the Editor to automatically insert Markdown links `[Name](path)` or images `![Alt](path)`, and drag-and-drop file organization inside Explorer.
* **Multi-Threaded Batch & Archive Converter**: Process entire directories or archive files (`.zip`, `.rar`, `.7z`, `.tar.gz`) in background worker pools with direct `.zip` output packaging.
* **Quick Open File Switcher (`Ctrl+P`)**: Blazing fast fuzzy file search modal palette across the entire project workspace.
* **Smooth 60fps Draggable Splitters**: Dual responsive splitters for adjusting Sidebar width (150px–500px) and Editor/Preview ratio (20%–80%) with permanent configuration persistence.

### 🖼️ Floating Image Formatting & Visuals
* **Floating Image Context Menu & Formatter**: Right-click images in Live Preview to align Left, Center, or Right using `<p align="...">`, synchronized 100% with Word export (`WD_ALIGN_PARAGRAPH`).
* **Interactive Image Sizing Dialog**: Quick presets (25%, 50%, 75%, 100%, Custom W/H), aspect ratio lock, and click-outside dismissal.
* **Mermaid Diagram Live Preview**: Native rendering of Flowchart, Sequence, Class, and Gantt diagrams directly in Live Preview.

---

## 📄 Document Conversion Matrix

| Format | Import to Markdown (`➔ .md`) | Export from Markdown (`.md ➔`) | Highlights |
| :--- | :---: | :---: | :--- |
| **PowerPoint (`.pptx`)** | ✅ | ✅ | 16:9 Widescreen slides, auto-numbering, chart data extraction, legend padding, slide overflow protection |
| **Word (`.docx`)** | ✅ | ✅ | Styled headings, clean structure, tables, image alignment (`WD_ALIGN_PARAGRAPH`) |
| **Excel (`.xlsx`)** | ✅ | ✅ | Multi-sheet parsing, frozen headers, auto-filters, spreadsheet table preview |
| **PDF (`.pdf`)** | ✅ | ✅ | Geometric multi-column card tables, hierarchy tree alignment, SMask alpha compositing |
| **Scanned PDF (OCR)** | ✅ | — | Optical Character Recognition text extraction from image-based PDF pages |
| **CSV (`.csv`)** | ✅ | ✅ | Delimiter auto-detection, clean Markdown table generation |
| **HTML (`.html`)** | ✅ | ✅ | GitHub-flavored CSS styling, Pygments codehilite, safe regex code fence auto-repair |
| **JSON (`.json`)** | ✅ | ✅ | Tabular array-to-table conversion, nested key-value formatting, fenced code blocks |
| **YAML (`.yaml`, `.yml`)** | ✅ | ✅ | Structured tree formatting, pipe table conversion, safe PyYAML parsing |
| **Audio/Video Media (`.mp3`, `.wav`, `.m4a`, `.mp4`, `.mkv`, `.flac`, `.webm`)** | ✅ | — | 100% Offline Whisper AI speech-to-text with Silero VAD, hardware detection (CUDA/CPU), PyAV 16kHz resampling |
| **YouTube & Google Drive (`URL`)** | ✅ | — | Subtitles & Whisper AI fallback, clickable timestamps, In-App Companion Player |
| **Batch Archives (`.zip`, `.rar`, `.7z`, `.tar.gz`)** | ✅ | — | Multi-threaded folder & archive batch extraction to Markdown or target formats with .zip packaging |

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

### Packaging & Installer (PyInstaller + Inno Setup 7)

```powershell
# 1-Click Automated Build (PyInstaller --onedir + Inno Setup 7 Setup.exe)
powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1

# Or manual PyInstaller --onedir build
python -m PyInstaller "Document Converter.spec"
```
The standalone desktop bundle will be generated at `dist/Document Converter/` and the Windows installer at `dist/installer/Document_Converter_Setup_v1.9.2.exe`.

---

## 🗺️ Version History

- **v1.9.2 — Recent History, Welcome Studio Dashboard & Multi-Window Focus (Current)**: Persistent Recent Files & Folders history at `%APPDATA%\DocConvert\recent_history.json` with Pinning (`📌 Pin`), Search & Filter tabs, 2-column Welcome Studio Dashboard, Home button navigation from Activity Bar, Multi-Window (`Ctrl+Shift+N`) with Win32 foreground elevation, and Close Workspace button.
- **v1.9.1 — OCR Scanned PDF Engine & Preview Scroll Synchronization**: OCR scanned PDF text extraction engine (`pdf_scan_to_md`) and 2-Pass Frame Layout scroll locking for preview formatting.
- **v1.9.0 — AI Model Hub, Offline Whisper Transcriber & Background Transcription**: 100% Offline Whisper speech transcriber with CTranslate2 int8, Model Hub marketplace with SHA256 integrity checks, hardware detector (CPU/RAM/GPU VRAM), Silero VAD segmentation `[mm:ss]`, and background transcription with smart tab routing.
- **v1.8.3 — Bounded LRU Base64 Cache & Session Memory Optimization**: `OrderedDict` LRU cache (128 max) with session-based observer purge hooks freeing 100% image memory on tab closure.
- **v1.8.2 — Floating Image Formatting, Word Alignment & Multi-Tab Footer Sync**: Floating image formatting toolbar, image sizing dialog, Word (`.docx`) image alignment engine (`WD_ALIGN_PARAGRAPH`), per-tab conversion state hydration, and Explorer scrolling/clipping fixes.
- **v1.8.0 / v1.8.1 — Studio Workspace, Multi-Tab Architecture, Batch & Archive Converter**: Activity Bar, File Explorer, Quick Open (`Ctrl+P`), Draggable Splitters, Multi-Tab Workspace, Explorer Context Menu with Win32 Recycle Bin, Smart Drag & Drop, and multi-threaded Batch & Archive Converter (`.zip`, `.rar`, `.7z`, `.tar.gz`).
- **v1.7.0 / v1.7.2 — YouTube Companion Player, Single-Row Ribbon & Inno Setup 7 Installer**: In-app WebView2 YouTube Companion Player with interactive timestamps `[mm:ss]`, local HTTP bridge server, simplified single-row Ribbon Bar, and Inno Setup 7 desktop installer (`--onedir`).
- **v1.0 – v1.6.6 — Core Multiformat Conversion Engines**: Word (`.docx`), PowerPoint (`.pptx`), Excel (`.xlsx`), CSV (`.csv`), PDF (`.pdf`), HTML (`.html`), JSON (`.json`), YAML (`.yaml`), and Flet 3-Tier MVC architecture.

> [!NOTE]
> Detailed developer documentation, technical architecture summaries, and feature logs are organized in the [`docs/`](docs/) directory.

---

## ⚠️ Known Limitations

* **Windows Clipboard History (`Win + V`):** Due to Windows OS architecture, the `Win + V` clipboard panel is rendered in an isolated system shell process that de-focuses the application upon opening. Please use the standard **`Ctrl + V`** or right-click **Paste** to insert text from the clipboard.
* **Large Documents:** Document preview is optimized for smooth editing performance; full file contents are converted completely during processing.
* **Complex Styles:** Advanced Office layout elements (floating text boxes, multi-column macros) are simplified into clean, standardized Markdown structures.

---

## 👥 Authors & Contributors

* **Duy Phan** ([@duyphan1410](https://github.com/duyphan1410)) — Core Architecture, UI Framework & Conversion Service Lead.
* **Satoou19 (Huy)** — Document Modules Overhaul, PDF & Image Handling Specialist.

---

## 📄 License

GNU AGPLv3 — Copyright (c) 2026 Duy Phan & Contributors

