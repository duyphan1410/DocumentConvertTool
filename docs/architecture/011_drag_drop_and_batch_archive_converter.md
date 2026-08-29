# Architecture Decision Record 011: Smart Drag & Drop Token Insertion, Move Validation Pipeline, and Batch Archive Conversion Service

## 1. Overview & Business Context

In Milestone 1.8.1c, Document Converter Tool introduces three critical capabilities:
1. **Smart Drag & Drop Token Insertion**: Dragging document or image entries from the Workspace Explorer into the Editor workspace silently inserts relative Markdown tokens (`![name](rel_path)` for images or `[name](rel_path)` for documents) directly at the current caret position, without triggering file navigation or tab switching.
2. **Move Validation & Tab Synchronization**: Dragging entries within the Explorer tree reorganizes files/folders with strict safety validation (preventing circular moves, overwriting, moving into current parent) and synchronizes open editor tabs and active workspace paths in real-time.
3. **Batch & Archive Conversion Service**: Multi-threaded document converter supporting entire directories or compressed archives (`.zip`, `.rar`, `.7z`, `.tar.gz`), with per-file error isolation, background cancellation, live progress reporting, and packaging directly to folders or compressed `.zip` packages.

---

4. **In-App Local Document Link Navigation**: Clicking relative or local document links (`.md`, `.docx`, `.html`, `.xlsx`, `.csv`, `.pdf`, `.pptx`, `.json`, `.yaml`) within Markdown Preview automatically resolves the target against the active document directory / workspace and opens the document as a new Tab within the application, eliminating unnecessary external OS app switching.

---

## 2. Component Architecture & Design Patterns

### 2.1 Drag & Drop Gesture Isolation
To prevent gesture conflicts between workspace tab reordering and file explorer tree manipulation:
- **`group="doc_tabs"`**: Dedicated exclusively to `WorkspaceTabBar` tab reordering and tearing.
- **`group="doc_explorer"`**: Dedicated to `FileTreeItem` (Draggable), `DirectoryTreeItem` (Draggable + DragTarget header), `tree_list` (DragTarget root), and `EditorView` (DragTarget for Markdown token insertion).

### 2.2 Relative Path Resolution & In-App Navigation Logic
When a file is dropped into `EditorView`, the editor computes the cleanest relative path:
1. If an active document is opened, compute `os.path.relpath(dropped_path, os.path.dirname(active_path))`.
2. Otherwise, if a workspace root is opened, compute `os.path.relpath(dropped_path, workspace_root)`.
3. Normalize all Windows backslashes `\` to forward slashes `/` for cross-platform Markdown compliance.
4. When clicked in `MarkdownPreview`, `_on_markdown_link_clicked` checks if the target is a local file relative to `_base_dir` with a supported document extension, invoking `on_open_file` to spawn a new Workspace Tab.

### 2.3 Filesystem Move Safety Validator
The `validate_move_operation(src_path, dest_dir)` in `src/utils/file_ops.py` ensures 100% i18n validated moves:
- Rejects non-existent sources or destinations.
- Rejects identical paths.
- Rejects moving an entry into its own current parent folder.
- Rejects circular moves (e.g. moving a parent directory into its own subfolder).
- Rejects destination name collisions.

### 2.4 Multi-threaded Batch & Archive Service (`BatchConversionService`)
- **Decompression**: Automatically detects and safely extracts `.zip` and `.tar.gz`/`.tgz`/`.tbz2` into isolated temporary scratch directories.
- **Scanning**: Recursively discovers all convertible files while ignoring `.git`, `__pycache__`, `node_modules`, `.venv`, `.idea`, and system volume directories.
- **ThreadPoolExecutor**: Uses a worker pool (`max_workers=3`) with fine-grained cancellation checking via `threading.Event`.
- **Error Isolation**: Each file is processed in an isolated `try...except` block using `load_document` -> `convert_content`. Corrupt files log failures without halting the batch pipeline.
- **Packaging**: Direct export to destination folder or automated packaging into a single `.zip` archive via `zipfile.ZipFile`.

---

## 3. UI/UX Modal Lifecycle & Flet 0.86.4 Compatibility

`BatchDialog` in `src/ui_flet/components/batch_dialog.py` strictly follows the Flet 0.86.4 Desktop modal specification:
- `modal = False`: Allows dismissal when the user clicks the outside backdrop.
- `on_dismiss = self._close_dialog`: Automatically cleans up state, cancels active conversions, and closes the dialog.
- Explicit `close_dialog()` calls on all action buttons ("Đóng", "Hủy", "Mở kết quả").
- Purges zombie `AlertDialog` instances from `page.overlay` before appending new dialog instances.
- 100% of labels, tooltips, buttons, error messages, and log chips are localized using `t(...)` from `src.i18n`.

---

## 4. Verification & Testing Strategy

- **`tests/test_validator_and_file_ops.py`**: Unit tests for `validate_archive_file` and `validate_move_operation`.
- **`tests/test_batch_service.py`**: Integration tests for recursive file scanning, multi-format conversion, archive extraction, `.zip` packaging, error isolation, and cancellation.
- **`tests/test_explorer_drag_drop.py`**: Token insertion tests and draggable group isolation tests.
- **`tests/test_document_preview.py`**: In-App local document link resolution and tab open delegation tests.
- **`tests/test_batch_dialog_smoke.py`**: Modal lifecycle and control state validation.
- **Full Suite**: 114/114 automated tests passing cleanly.

