# Document Converter Workspace

![Python](<https://img.shields.io/badge/Python-3.12%20--%203.13-blue>)
![Platform](<https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-green>)
![License](https://img.shields.io/badge/License-MIT-yellow)

A modern desktop workspace for editing and converting documents between **Markdown**, **Excel**, and **Word** formats.

The application provides a unified Markdown-centric workflow, allowing users to extract content from Office documents, edit it in Markdown, and export it back into structured formats.

---

## Screenshots & Themes

| Dark Mode (Violet Cyberpunk) |      Light Mode (Light Theme)      |
| :--------------------------: | :---------------------------------: |
| ![Dark Mode](screenshot.png) | ![Light Mode](screenshot_light.png) |

---

## Features

### Document Conversion

* **Markdown → Excel (.xlsx)**

  * Styled worksheet generation
  * Frozen header row
  * Auto-sized columns
  * Auto-filter support
* **Markdown → Word (.docx)**

  * Heading support
  * Lists support
  * Bold text support
  * Table rendering
* **Excel (.xlsx) → Markdown**

  * Multi-sheet extraction
  * Markdown table generation
* **Word (.docx) → Markdown**

  * Clean document extraction
  * Markdown-friendly formatting

### Workspace Features

* Unified Markdown editor
* Drag & drop file support
* Live content extraction on load
* One-click document opening
* Background-thread conversion pipeline
* Responsive UI (auto-compact labels, 2-row toolbar, debounce resize)
* High-DPI aware (Per-Monitor v2 on Windows)
* Cross-platform support

---

## Supported Formats

The application uses **Markdown as a central interchange workspace**. You can import external documents into Markdown, edit them, and export them back to structured formats.

```mermaid
graph LR
    subgraph Import [Import to Workspace]
        Word_In[.docx] --> Hub((Markdown Hub))
        Excel_In[.xlsx] --> Hub
        CSV_In[.csv] --> Hub
        PDF_In[.pdf] --> Hub
        HTML_In[.html] --> Hub
    end

    subgraph Export [Export from Workspace]
        Hub --> Word_Out[.docx]
        Hub --> Excel_Out[.xlsx]
        Hub --> CSV_Out[.csv]
        Hub --> HTML_Out[.html]
        Hub -.-> PDF_Out[.pdf v2.0]
    end
```

### Conversion Matrix

| Format                                    | Import to Markdown (`➔ .md`) | Export from Markdown (`.md ➔`) |      Mode      |  Status  |
| :---------------------------------------- | :-----------------------------: | :-------------------------------: | :------------: | :-------: |
| **Word Document (`.docx`)**       |               ✅               |                ✅                |   ↔ Two-Way   | ✅ Ready |
| **Excel Spreadsheet (`.xlsx`)**   |               ✅               |                ✅                |   ↔ Two-Way   | ✅ Ready |
| **CSV File (`.csv`)**             |               ✅               |                ✅                |   ↔ Two-Way   | ✅ Ready |
| **HTML Page (`.html`, `.htm`)** |               ✅               |                ✅                |   ↔ Two-Way   | ✅ Ready |
| **PDF Document (`.pdf`)**         |               ✅               |         🔄 Planned (v2.0)         | ➔ Import Only | ⚡ Active |

---

## Requirements

* Python 3.12 – 3.13
* Windows / macOS / Linux

---

## Quick Start

Clone the repository:

```bash
git clone https://github.com/duyphan1410/DocumentConvertTool
cd DocumentConvertTool
```

Create, activate virtual environment, install dependencies, and run:

### Windows (PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

---

## Drag & Drop

The application supports drag-and-drop input files.

### Supported Behaviors

* Drop a `.md` file to edit it directly.
* Drop a `.docx` file to extract its content into Markdown.
* Drop a `.xlsx` file to extract worksheets into Markdown tables.
* Paths containing spaces or Unicode characters are supported.

---

## Build Executable

### Install PyInstaller

```bash
pip install pyinstaller
```

### Windows (Recommended — using optimized .spec file)

```powershell
venv\Scripts\pyinstaller "Document Converter.spec"
```

> The `.spec` file excludes heavy unused packages (`onnxruntime`, `cryptography`, `matplotlib`, `scipy`, etc.) for faster build times.

### Windows (Manual — generates a new .spec from scratch)

```cmd
pyinstaller --onefile --windowed --name "Document Converter" --icon=favicon.ico --collect-all customtkinter --collect-all tkinterdnd2 --add-data "src/ui/theme.json;src/ui" run.py
```

### macOS

```bash
pyinstaller --onefile --windowed --name "Document Converter" --collect-all customtkinter --collect-all tkinterdnd2 --add-data "src/ui/theme.json:src/ui" run.py
```

### Linux

```bash
pyinstaller --onefile --name "Document Converter" --collect-all customtkinter --collect-all tkinterdnd2 --add-data "src/ui/theme.json:src/ui" run.py
```

Build output:

```text
dist/
```

---

## Project Structure

```text
DocumentConvertTool/
│
├── src/
│   ├── __version__.py
│   ├── main.py
│   │
│   ├── core/
│   │   ├── base_module.py
│   │   ├── converters.py
│   │   ├── registry.py
│   │   └── validator.py
│   │
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── csv_module.py
│   │   ├── excel_module.py
│   │   ├── html_module.py
│   │   ├── pdf_module.py
│   │   └── word_module.py
│   │
│   ├── services/
│   │   ├── conversion_service.py
│   │   └── file_loader.py
│   │
│   ├── ui/
│   │   ├── app.py
│   │   ├── document_preview.py
│   │   └── theme.json
│   │
│   └── utils/
│       └── env.py
│
├── run.py
├── requirements.txt
├── favicon.ico
├── Document Converter.spec
└── README.md
```

### Directory Overview

| Path                           | Purpose                                                      |
| ------------------------------ | ------------------------------------------------------------ |
| `src/__version__.py`         | SemVer version config                                        |
| `src/main.py`                | Application entry point & initialization                     |
| `src/core/base_module.py`    | Base abstract document module                                |
| `src/core/registry.py`       | Document module registry                                     |
| `src/core/converters.py`     | Markdown parsing utilities                                   |
| `src/core/validator.py`      | Document structure validation                                |
| `src/modules/`               | Document conversion plugins (Word, Excel, CSV, PDF, HTML)    |
| `src/services/`              | Core conversion background services                          |
| `src/ui/app.py`              | Main customtkinter GUI (responsive, debounce resize)         |
| `src/ui/document_preview.py` | Visual Markdown document preview panel (debounce wraplength) |
| `src/ui/theme.json`          | App CustomTkinter theme settings                             |
| `src/utils/env.py`           | UTF-8 encoding, Tcl/Tk path & High-DPI configuration         |
| `Document Converter.spec`    | Optimized PyInstaller build spec                             |
| `run.py`                     | Launcher script                                              |

---

## Dependencies

| Library       | Purpose                      |
| ------------- | ---------------------------- |
| customtkinter | Modern UI framework          |
| tkinterdnd2   | Drag & drop support          |
| pandas        | Data processing              |
| openpyxl      | Excel export/import          |
| python-docx   | Word document generation     |
| mammoth       | Word document extraction     |
| markdown2     | Markdown → HTML conversion  |
| pdfplumber    | PDF layout table extraction  |
| markitdown    | Fallback PDF text extraction |

---

## Roadmap

### ✅ P0 — Stabilization (Completed)

* [X] Fix drag & drop path parser
* [X] File extension validation
* [X] Overwrite confirmation
* [X] Dependency fallback handling
* [X] File size warning
* [X] Progress indicator
* [X] Unsaved changes warning
* [X] Word → Markdown: images replaced with [image] placeholder

### ✅ Phase 1 — UX & Format Improvements (Completed)

* [X] CSV ↔ Markdown support
* [X] Smart table validator (pipe escaping, table detection)
* [X] Search & replace panel (integrated into editor)
* [X] Formatting toolbar in editor (Bold, Italic, Strikethrough, Underline, Code, Link, Headings, Lists, Tables)
* [X] Autosave draft (restore when reopening app)
* [ ] Markdown syntax highlighting (in the raw text editor)

### 🔄 Phase 2 — Format Expansion

* [X] PDF → Markdown (using pdfplumber + markitdown layout extraction, preserving tables, fonts, bullets, and list numbering)
* [X] HTML ↔ Markdown (HTML export with GitHub Markdown CSS styling & import fallback)
* [X] Visual document preview in editor (renders formatting, tables, lists in-app)
* [ ] Markdown → PDF (with embedded image & table rendering)

### 🔄 Phase 3 — Polish & Release

* [X] Resizable window support (adapts to varying screen sizes)
* [X] Responsive UI (auto-compact labels, 2-row toolbar at narrow widths)
* [X] High-DPI awareness (Per-Monitor v2 on Windows)
* [X] Optimized PyInstaller build via `.spec` file (excludes unused heavy packages)
* [X] Debounce resize events for smooth window dragging (150ms `after()` timer)
* [X] v1.2.1 executable release (PyInstaller packaging with resource bundles)

### 🔄 Phase 4–8 — v2.0 Roadmap (Planned)

* [ ] Two-Way Image Pipeline (`MediaAssetManager`, Word/PDF/HTML 2-way image import & export)
* [ ] Multi-document tabs & global keyboard shortcuts
* [ ] Markdown syntax highlighting in editor
* [ ] Batch conversion & ZIP archive auto-extract/repack (`zipfile`)
* [ ] GitHub Markdown CSS Theme Engine for HTML & PDF exports (with PDF engine POC)
* [ ] Persistent Settings panel & conversion presets
* [ ] Command-Line Interface (CLI mode)
* [ ] Interactive User Guide Window Upgrade (`MD Guide ❔` with 6 detailed tabs)
* [ ] Optimized `Document Converter.spec` build & Windows Setup Installer (`DocumentConverter_Setup_v2.0.0.exe` via Inno Setup)

---

## Known Limitations

* **Large files:** File preview is truncated at 500KB to prevent UI lag. Full content will still be converted.
* **Word documents with images:** In v1.2.x, images are replaced with `[image]` placeholders. Full two-way image extraction and embedding (Word, PDF, HTML export) is planned for v2.0 (Phase 4).
* **Complex Word formatting:** Some advanced Word styles (columns, text boxes, etc.) may not be fully preserved in Markdown conversion.
* **PDF support:** PDF import (v1.1.0+) supports layout-preserving extraction with page-break table stitching and cell continuation. Exporting Markdown to PDF is planned for v2.0 (Phase 6).
* **CSV support:** CSV ↔ Markdown conversion is fully supported.
* **Resize smoothness:** CustomTkinter redraws rounded-corner canvas polygons on every frame resize. Inner frames use reduced `corner_radius` (4px vs 12px) to minimize redraw cost. Some minor visual stutter may persist on complex layouts — this is a framework-level limitation of CustomTkinter.

---

## Development

Recommended branch strategy:

```text
main
├── fix/p0-stabilization
├── feature/progress-api
├── feature/html-export
└── feature/plugin-system
```

Commit example:

```bash
git commit -m "feat: add html export engine"
git commit -m "fix: improve drag drop parser"
```

---

## Contributing

Contributions are welcome.

Before opening a Pull Request:

1. Follow PEP 8 conventions.
2. Add type hints to new APIs.
3. Test conversion workflows.
4. Keep UI responsive during long-running operations.

---

## License

MIT License

You are free to use, modify, distribute, and build upon this project under the terms of the MIT License.
