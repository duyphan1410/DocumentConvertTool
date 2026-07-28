"""
Main Flet UI Application for DocumentConvertTool (Milestone 1 - Desktop Skeleton).
Provides responsive editor, file loader, conversion service integration,
theme switcher, undo/redo stack, and search/replace panel.
"""
import os
import re
import time
import threading
import asyncio
import flet as ft

# Force document modules to load and register
from src.core.registry import ModuleRegistry
import src.modules  # noqa: F401

from src.services.file_loader import load_document
from src.services.conversion_service import (
    convert_content,
    get_md_table_warnings,
    has_md_tables,
    is_output_locked,
)
from src.__version__ import __version__
from src.ui_flet.theme import PALETTES, STYLE, apply_theme
from src.ui_flet.preview import MarkdownPreview
from src.ui_flet.native_dialogs import pick_input_file_async, pick_output_file_async

# ── AppData & Configuration Constants ───────────────────────────────────────
appdata_dir = os.getenv('APPDATA')
if not appdata_dir:
    appdata_dir = os.path.join(os.path.expanduser("~"), ".config")

DRAFT_PATH = os.path.join(appdata_dir, "DocConvert", "draft_autosave.md")
EDITOR_DISPLAY_LIMIT = 500_000

MODES = {
    "MD -> Excel":  {"in_ext": ".md",   "out_ext": ".xlsx", "in_label": "File .md",   "out_label": "Save .xlsx"},
    "MD -> Word":   {"in_ext": ".md",   "out_ext": ".docx", "in_label": "File .md",   "out_label": "Save .docx"},
    "MD -> CSV":    {"in_ext": ".md",   "out_ext": ".csv",  "in_label": "File .md",   "out_label": "Save .csv"},
    "MD -> PDF":    {"in_ext": ".md",   "out_ext": ".pdf",  "in_label": "File .md",   "out_label": "Save .pdf"},
    "MD -> HTML":   {"in_ext": ".md",   "out_ext": ".html", "in_label": "File .md",   "out_label": "Save .html"},
    "Excel -> MD":  {"in_ext": ".xlsx", "out_ext": ".md",   "in_label": "File .xlsx", "out_label": "Save .md"},
    "Word -> MD":   {"in_ext": ".docx", "out_ext": ".md",   "in_label": "File .docx", "out_label": "Save .md"},
    "CSV -> MD":    {"in_ext": ".csv",  "out_ext": ".md",   "in_label": "File .csv",  "out_label": "Save .md"},
    "PDF -> MD":    {"in_ext": ".pdf",  "out_ext": ".md",   "in_label": "File .pdf",  "out_label": "Save .md"},
    "HTML -> MD":   {"in_ext": ".html", "out_ext": ".md",   "in_label": "File .html", "out_label": "Save .md"},
}

IN_FILETYPES = {
    ".md":   ["md"],
    ".xlsx": ["xlsx", "xls"],
    ".docx": ["docx"],
    ".csv":  ["csv"],
    ".pdf":  ["pdf"],
    ".html": ["html", "htm"],
}

OUT_FILETYPES = {
    ".xlsx": ["xlsx"],
    ".docx": ["docx"],
    ".md":   ["md"],
    ".csv":  ["csv"],
    ".pdf":  ["pdf"],
    ".html": ["html", "htm"],
}


class DocumentConvertApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = f"Document Converter Workspace v{__version__}"
        self.page.window.width = 1360
        self.page.window.height = 800
        self.page.window.min_width = 900
        self.page.window.min_height = 560
        self.page.padding = 12
        self.page.spacing = 10

        # State variables
        self.in_path = ""
        self.out_path = ""
        self.current_mode = "MD -> Excel"
        self.current_palette = "Violet Cyberpunk"
        self.current_theme_mode = "Dark"
        self.full_content = ""
        self.is_dirty = False
        self.is_processing = False

        # Undo/Redo stack state
        self.undo_stack: list[str] = []
        self.redo_stack: list[str] = []
        self._is_undo_redo_op = False

        # Search panel state
        self.search_matches: list[tuple[int, int]] = []
        self.current_match_idx = -1

        # Debounce timer state
        self._autosave_timer: threading.Timer | None = None
        self._undo_timer: threading.Timer | None = None
        self._preview_timer: threading.Timer | None = None

        # File Pickers
        self.file_picker_in = ft.FilePicker()
        self.file_picker_out = ft.FilePicker()
        self.page.services.extend([self.file_picker_in, self.file_picker_out])



        # Apply Initial Theme
        apply_theme(self.page, self.current_palette, self.current_theme_mode)

        # Build UI Controls
        self._build_controls()
        self._load_draft_if_exists()
        print(f"[DEBUG] App initialized successfully with Flet UI")

    def _build_controls(self):
        # ── Header Bar Controls ─────────────────────────────────────────────
        self.mode_dropdown = ft.Dropdown(
            label="Conversion Mode",
            value=self.current_mode,
            options=[ft.dropdown.Option(m) for m in MODES.keys()],
            width=180,
            dense=True
        )
        self.mode_dropdown.on_select = self._on_mode_changed
        self.mode_dropdown.on_change = self._on_mode_changed

        self.palette_dropdown = ft.Dropdown(
            label="Palette",
            value=self.current_palette,
            options=[ft.dropdown.Option(p) for p in PALETTES.keys()],
            width=160,
            dense=True
        )
        self.palette_dropdown.on_select = self._on_palette_changed
        self.palette_dropdown.on_change = self._on_palette_changed

        self.theme_mode_dropdown = ft.Dropdown(
            label="Theme",
            value=self.current_theme_mode,
            options=[
                ft.dropdown.Option("Dark"),
                ft.dropdown.Option("Light"),
                ft.dropdown.Option("System"),
            ],
            width=120,
            dense=True
        )
        self.theme_mode_dropdown.on_select = self._on_theme_mode_changed
        self.theme_mode_dropdown.on_change = self._on_theme_mode_changed

        self.header_container = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.PRIMARY, size=24),
                    ft.Text(
                        f"DocConvert Workspace v{__version__}",
                        weight=ft.FontWeight.BOLD,
                        size=16
                    ),
                    ft.Container(expand=True),
                    self.mode_dropdown,
                    self.palette_dropdown,
                    self.theme_mode_dropdown,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            padding=ft.Padding(left=12, top=8, right=12, bottom=8),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST
        )

        # ── File Path Action Bar ────────────────────────────────────────────
        self.in_path_text = ft.TextField(
            label="Input File Path",
            value="",
            read_only=True,
            expand=True,
            dense=True
        )
        self.btn_browse_in = ft.ElevatedButton(
            "Browse Input",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self._trigger_browse_input
        )

        self.out_path_text = ft.TextField(
            label="Output Destination",
            value="",
            expand=True,
            dense=True,
            on_change=self._on_out_path_edited
        )
        self.btn_browse_out = ft.ElevatedButton(
            "Select Output",
            icon=ft.Icons.SAVE,
            on_click=self._trigger_browse_output
        )

        file_bar = ft.Column(
            controls=[
                ft.Row(controls=[self.in_path_text, self.btn_browse_in]),
                ft.Row(controls=[self.out_path_text, self.btn_browse_out]),
            ],
            spacing=6
        )

        # ── Search & Replace Panel ──────────────────────────────────────────
        self.search_input = ft.TextField(
            label="Find",
            dense=True,
            expand=True,
            on_submit=self._find_next_via_enter,
            on_change=self._on_search_changed
        )
        self.replace_input = ft.TextField(
            label="Replace",
            dense=True,
            expand=True,
            on_submit=self._replace_current
        )
        self.chk_regex = ft.Checkbox(label="Regex", value=False, on_change=self._on_search_changed)
        self.chk_case = ft.Checkbox(label="Match Case", value=False, on_change=self._on_search_changed)
        self.lbl_search_match = ft.Text("0 matches", size=12, color=ft.Colors.GREY_500)

        self.search_panel = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(controls=[
                        self.search_input,
                        ft.IconButton(ft.Icons.NAVIGATE_BEFORE, tooltip="Find Previous", on_click=self._find_prev_via_button),
                        ft.IconButton(ft.Icons.NAVIGATE_NEXT, tooltip="Find Next", on_click=self._find_next_via_button),
                        self.chk_regex,
                        self.chk_case,
                        self.lbl_search_match,
                    ]),
                    ft.Row(controls=[
                        self.replace_input,
                        ft.ElevatedButton("Replace", on_click=self._replace_current),
                        ft.ElevatedButton("Replace All", on_click=self._replace_all),
                    ])
                ],
                spacing=6
            ),
            padding=8,
            border_radius=6,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            visible=False
        )

        # ── Toolbar & Editor Controls ───────────────────────────────────────
        self.btn_toggle_search = ft.IconButton(
            ft.Icons.SEARCH,
            tooltip="Toggle Search & Replace Panel",
            on_click=self._toggle_search_panel
        )
        self.btn_undo = ft.IconButton(
            ft.Icons.UNDO,
            tooltip="Undo (Ctrl+Z)",
            on_click=self._perform_undo
        )
        self.btn_redo = ft.IconButton(
            ft.Icons.REDO,
            tooltip="Redo (Ctrl+Y)",
            on_click=self._perform_redo
        )
        self.btn_clear_editor = ft.IconButton(
            ft.Icons.DELETE_SWEEP,
            tooltip="Clear Editor",
            on_click=self._clear_editor
        )

        toolbar = ft.Row(
            controls=[
                ft.Text("Editor Buffer", weight=ft.FontWeight.W_600),
                ft.Container(expand=True),
                self.btn_toggle_search,
                self.btn_undo,
                self.btn_redo,
                self.btn_clear_editor
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )

        self.editor = ft.TextField(
            multiline=True,
            expand=True,
            min_lines=18,
            text_style=ft.TextStyle(font_family=STYLE["font_family_mono"]),
            text_size=13,
            on_change=self._on_editor_changed,
            hint_text="Document text content will appear here..."
        )

        self.left_pane = ft.Container(
            content=ft.Column(
                controls=[
                    toolbar,
                    self.search_panel,
                    self.editor
                ],
                expand=True
            ),
            expand=True,
            padding=10,
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER
        )

        # ── Right Pane (M2 Live Markdown Preview) ───────────────────────────
        self.doc_info_text = ft.Text("No document loaded.", size=12)
        self.preview = MarkdownPreview()

        self.right_pane = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.PREVIEW, size=18),
                            ft.Text("Live Document Preview", weight=ft.FontWeight.W_600),
                            ft.Container(expand=True),
                            self.doc_info_text,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    ft.Divider(),
                    self.preview
                ],
                expand=True
            ),
            expand=True,
            padding=10,
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER
        )

        # ── Main 2-Pane Split ───────────────────────────────────────────────
        main_content = ft.Row(
            controls=[self.left_pane, self.right_pane],
            expand=True,
            spacing=10
        )

        # ── Conversion Action Footer ────────────────────────────────────────
        self.last_converted_path = ""
        self.btn_convert = ft.ElevatedButton(
            "CONVERT NOW",
            icon=ft.Icons.TRANSFORM,
            on_click=self._on_convert_clicked,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=24, top=16, right=24, bottom=16),
                color=ft.Colors.WHITE
            )
        )
        self.btn_open_file = ft.ElevatedButton(
            "Open File",
            icon=ft.Icons.OPEN_IN_NEW,
            visible=False,
            on_click=self._open_converted_file
        )
        self.btn_open_folder = ft.ElevatedButton(
            "Open Folder",
            icon=ft.Icons.FOLDER_OPEN,
            visible=False,
            on_click=self._open_converted_folder
        )
        self.progress_bar = ft.ProgressBar(visible=False, expand=True)
        self.status_text = ft.Text("Ready", size=13)

        self.footer_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            self.btn_convert,
                            self.btn_open_file,
                            self.btn_open_folder,
                            self.status_text,
                            self.progress_bar
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    )
                ]
            ),
            padding=ft.Padding(left=12, top=8, right=12, bottom=8),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST
        )

        # Build Page Tree
        self.page.add(
            self.header_container,
            file_bar,
            main_content,
            self.footer_container
        )
        self._update_theme_colors()

    # ── Mode & Theme Handlers ────────────────────────────────────────────────
    def _on_mode_changed(self, e):
        self.current_mode = self.mode_dropdown.value
        mode_cfg = MODES[self.current_mode]
        print(f"[DEBUG] Conversion mode changed to: {self.current_mode}")

        # Update output extension if output path is specified
        if self.out_path:
            base, _ = os.path.splitext(self.out_path)
            self.out_path = base + mode_cfg["out_ext"]
            self.out_path_text.value = self.out_path

        if self.in_path:
            self.doc_info_text.value = (
                f"Loaded: {os.path.basename(self.in_path)} | Size: {len(self.full_content)} chars\n"
                f"Mode: {self.current_mode}"
            )
        else:
            self.doc_info_text.value = f"Mode: {self.current_mode}"

        self.page.update()

    def _update_theme_colors(self):
        from src.ui_flet.theme import get_palette_color
        is_dark = self.current_theme_mode == "Dark" or (self.current_theme_mode == "System")
        apply_theme(self.page, self.current_palette, self.current_theme_mode)
        
        header_bg = get_palette_color(self.current_palette, "bg_header", is_dark)
        pane_bg = get_palette_color(self.current_palette, "bg_pane", is_dark)
        comp_bg = get_palette_color(self.current_palette, "bg_component", is_dark)
        convert_bg = get_palette_color(self.current_palette, "btn_convert_fg", is_dark)

        self.page.bgcolor = pane_bg
        if hasattr(self, 'header_container'):
            self.header_container.bgcolor = header_bg
            try: self.header_container.update()
            except Exception: pass
        if hasattr(self, 'left_pane'):
            self.left_pane.bgcolor = comp_bg
            try: self.left_pane.update()
            except Exception: pass
        if hasattr(self, 'right_pane'):
            self.right_pane.bgcolor = comp_bg
            try: self.right_pane.update()
            except Exception: pass
        if hasattr(self, 'footer_container'):
            self.footer_container.bgcolor = header_bg
            try: self.footer_container.update()
            except Exception: pass
        if hasattr(self, 'btn_convert'):
            self.btn_convert.style = ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=24, top=16, right=24, bottom=16),
                color=ft.Colors.WHITE,
                bgcolor=convert_bg
            )
            try: self.btn_convert.update()
            except Exception: pass
        if hasattr(self, 'editor'):
            self.editor.bgcolor = comp_bg
            try: self.editor.update()
            except Exception: pass
        if hasattr(self, 'preview'):
            self.preview.bgcolor = comp_bg
            try: self.preview.update()
            except Exception: pass
        try: self.page.update()
        except Exception: pass

    def _on_palette_changed(self, e):
        self.current_palette = self.palette_dropdown.value
        self._update_theme_colors()
        print(f"[DEBUG] Palette changed to: {self.current_palette}")

    def _on_theme_mode_changed(self, e):
        self.current_theme_mode = self.theme_mode_dropdown.value
        self._update_theme_colors()
        print(f"[DEBUG] Theme mode changed to: {self.current_theme_mode}")

    # ── File Dialog & Loader Handlers ───────────────────────────────────────
    async def _trigger_browse_input(self, e):
        selected_path = await pick_input_file_async()
        if selected_path:
            print(f"[DEBUG] Native filedialog selected input: {selected_path}")
            await self._load_file_path(selected_path)
            self.page.update()

    async def _trigger_browse_output(self, e):
        mode_cfg = MODES.get(self.current_mode, {})
        out_ext = mode_cfg.get("out_ext", ".docx")
        initial_filename = os.path.basename(self.out_path) if self.out_path else f"output{out_ext}"

        save_path = await pick_output_file_async(default_ext=out_ext, initial_file=initial_filename)
        if save_path:
            print(f"[DEBUG] Native filedialog selected output: {save_path}")
            self.out_path = save_path
            self.out_path_text.value = save_path
            self.page.update()

    def _on_out_path_edited(self, e):
        self.out_path = self.out_path_text.value

    async def _load_file_path(self, path: str):
        print(f"[DEBUG] Loading file from path: {path}")
        self.in_path = path
        self.in_path_text.value = path

        # Auto-filter dropdown mode options based on file extension
        _, ext = os.path.splitext(path)
        ext = ext.lower()

        valid_modes = [m for m, cfg in MODES.items() if cfg["in_ext"] == ext]
        if not valid_modes:
            valid_modes = list(MODES.keys())

        # Update dropdown options dynamically to only show valid modes for selected file
        self.mode_dropdown.options = [ft.dropdown.Option(m) for m in valid_modes]

        if self.current_mode not in valid_modes and valid_modes:
            self.current_mode = valid_modes[0]

        self.mode_dropdown.value = self.current_mode
        print(f"[DEBUG] Filtered mode dropdown options for '{ext}': {valid_modes}, selected: {self.current_mode}")

        # Set default output path
        out_ext = MODES[self.current_mode]["out_ext"]
        base_name = os.path.splitext(path)[0]
        self.out_path = f"{base_name}_converted{out_ext}"
        self.out_path_text.value = self.out_path

        # 1. Visual loading status feedback - painted immediately to screen
        self.status_text.value = f"Loading document '{os.path.basename(path)}'..."
        self.status_text.color = ft.Colors.BLUE_400
        self.page.update()

        # 2. Asynchronously execute heavy load_document in background thread
        res = await asyncio.to_thread(load_document, path)
        if not res.success:
            err_msg = res.error_detail or res.error_short or "Unknown error loading file."
            print(f"[DEBUG] File load failed: {err_msg}")
            self.status_text.value = f"Error loading file: {err_msg}"
            self.status_text.color = ft.Colors.RED_400
            self.page.update()
            return

        # Check missing dependencies if any
        if getattr(res, 'missing_dependencies', None):
            deps_str = ", ".join(res.missing_dependencies)
            print(f"[DEBUG] Missing dependencies for file load: {deps_str}")
            self.status_text.value = f"Warning: Missing optional dependencies ({deps_str})"
            self.status_text.color = ft.Colors.ORANGE_400

        self.full_content = res.content
        self.editor.value = self.full_content[:EDITOR_DISPLAY_LIMIT]
        self.editor.update()
        if hasattr(self, 'preview'):
            self.preview.set_content(self.full_content)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.undo_stack.append(self.editor.value)

        self.doc_info_text.value = (
            f"Loaded: {os.path.basename(path)} | Size: {len(self.full_content)} chars\n"
            f"Mode: {self.current_mode}"
        )
        self.status_text.value = f"Loaded successfully ({len(self.full_content)} chars)"
        self.status_text.color = ft.Colors.GREEN_400
        print(f"[DEBUG] File loaded successfully ({len(self.full_content)} characters)")
        self.page.update()

    # ── Undo / Redo & Editor Handlers ───────────────────────────────────────
    def _on_editor_changed(self, e):
        if self._is_undo_redo_op:
            return

        self.is_dirty = True

        # Instant live preview update
        if hasattr(self, 'preview') and self.editor:
            self.preview.set_content(self.editor.value or "")

        # Debounce undo snapshot (500ms pause)
        if self._undo_timer:
            self._undo_timer.cancel()
        self._undo_timer = threading.Timer(0.5, self._snapshot_undo_state)
        self._undo_timer.start()

        # Debounce draft autosave (1.5s pause)
        if self._autosave_timer:
            self._autosave_timer.cancel()
        self._autosave_timer = threading.Timer(1.5, self._trigger_draft_autosave)
        self._autosave_timer.start()

    def _on_search_changed(self, e):
        pass

    def _snapshot_undo_state(self):
        val = self.editor.value
        if not self.undo_stack or self.undo_stack[-1] != val:
            self.undo_stack.append(val)
            if len(self.undo_stack) > 50:
                self.undo_stack.pop(0)
            self.redo_stack.clear()
            print(f"[DEBUG] Snapshot undo state (total: {len(self.undo_stack)})")

    def _perform_undo(self, e):
        if len(self.undo_stack) > 1:
            self._is_undo_redo_op = True
            current_state = self.undo_stack.pop()
            self.redo_stack.append(current_state)
            self.editor.value = self.undo_stack[-1]
            if hasattr(self, 'preview'):
                self.preview.set_content(self.editor.value or "")
            self.page.update()
            self._is_undo_redo_op = False
            print("[DEBUG] Perform Undo")

    def _perform_redo(self, e):
        if self.redo_stack:
            self._is_undo_redo_op = True
            next_state = self.redo_stack.pop()
            self.undo_stack.append(next_state)
            self.editor.value = next_state
            if hasattr(self, 'preview'):
                self.preview.set_content(self.editor.value or "")
            self.page.update()
            self._is_undo_redo_op = False
            print("[DEBUG] Perform Redo")

    def _clear_editor(self, e):
        self.editor.value = ""
        self.undo_stack.append("")
        if hasattr(self, 'preview'):
            self.preview.set_content("")
        self.page.update()

    # ── Search & Replace Operations ─────────────────────────────────────────
    async def _toggle_search_panel(self, e):
        self.search_panel.visible = not self.search_panel.visible
        self.page.update()
        if self.search_panel.visible:
            await self.search_input.focus()

    def _find_matches(self) -> list[tuple[int, int]]:
        query = self.search_input.value
        content = self.editor.value
        if not query or not content:
            return []

        is_regex = self.chk_regex.value
        is_case = self.chk_case.value

        flags = 0 if is_case else re.IGNORECASE
        matches = []
        try:
            pattern = query if is_regex else re.escape(query)
            for m in re.finditer(pattern, content, flags=flags):
                matches.append((m.start(), m.end()))
        except Exception as ex:
            print(f"[DEBUG] Regex search error: {ex}")

        return matches

    async def _do_find_next(self):
        self.search_matches = self._find_matches()
        if not self.search_matches:
            self.lbl_search_match.value = "0 matches"
            self.page.update()
            return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.search_matches)
        start, end = self.search_matches[self.current_match_idx]
        self.lbl_search_match.value = f"Match {self.current_match_idx + 1} of {len(self.search_matches)}"
        self.editor.selection = ft.TextSelection(base_offset=start, extent_offset=end)
        self.editor.update()
        self.page.update()

    async def _do_find_prev(self):
        self.search_matches = self._find_matches()
        if not self.search_matches:
            self.lbl_search_match.value = "0 matches"
            self.page.update()
            return
        self.current_match_idx = (self.current_match_idx - 1) % len(self.search_matches)
        start, end = self.search_matches[self.current_match_idx]
        self.lbl_search_match.value = f"Match {self.current_match_idx + 1} of {len(self.search_matches)}"
        self.editor.selection = ft.TextSelection(base_offset=start, extent_offset=end)
        self.editor.update()
        self.page.update()

    async def _find_next_via_enter(self, e):
        await self._do_find_next()
        await self.search_input.focus()

    async def _find_prev_via_enter(self, e):
        await self._do_find_prev()
        await self.search_input.focus()

    async def _find_next_via_button(self, e):
        await self._do_find_next()
        await self.editor.focus()

    async def _find_prev_via_button(self, e):
        await self._do_find_prev()
        await self.editor.focus()

    def _replace_current(self, e):
        query = self.search_input.value
        replacement = self.replace_input.value
        if not query:
            return

        content = self.editor.value
        is_regex = self.chk_regex.value
        is_case = self.chk_case.value
        flags = 0 if is_case else re.IGNORECASE

        pattern = query if is_regex else re.escape(query)
        new_content, num_subs = re.subn(pattern, replacement, content, count=1, flags=flags)
        if num_subs > 0:
            self.editor.value = new_content
            self._on_editor_changed(None)
            self.search_matches = self._find_matches()
            self.lbl_search_match.value = f"Replaced 1 match ({len(self.search_matches)} remaining)"
            print(f"[DEBUG] Replaced match of '{query}'")
            self.page.update()

    def _replace_all(self, e):
        query = self.search_input.value
        replacement = self.replace_input.value
        if not query:
            return

        content = self.editor.value
        is_regex = self.chk_regex.value
        is_case = self.chk_case.value
        flags = 0 if is_case else re.IGNORECASE

        pattern = query if is_regex else re.escape(query)
        new_content, count = re.subn(pattern, replacement, content, flags=flags)
        self.editor.value = new_content
        self._on_editor_changed(None)
        self.search_matches = []
        self.lbl_search_match.value = f"Replaced {count} matches"
        print(f"[DEBUG] Replaced all {count} matches of '{query}'")
        self.page.update()

    # ── Draft Autosave Handler ──────────────────────────────────────────────
    def _load_draft_if_exists(self):
        if os.path.exists(DRAFT_PATH):
            try:
                with open(DRAFT_PATH, "r", encoding="utf-8") as f:
                    content = f.read()
                if content.strip():
                    self.editor.value = content
                    self.undo_stack.append(content)
                    if hasattr(self, 'preview'):
                        self.preview.set_content(content)
                    self.status_text.value = "Restored draft autosave."
                    print(f"[DEBUG] Restored draft autosave from: {DRAFT_PATH}")
            except Exception as e:
                print(f"[DEBUG] Error restoring draft: {e}")

    def _trigger_draft_autosave(self):
        try:
            os.makedirs(os.path.dirname(DRAFT_PATH), exist_ok=True)
            with open(DRAFT_PATH, "w", encoding="utf-8") as f:
                f.write(self.editor.value or "")
            print(f"[DEBUG] Draft autosaved to: {DRAFT_PATH}")
        except Exception as e:
            print(f"[DEBUG] Draft autosave failed: {e}")

    # ── Conversion Background Task ──────────────────────────────────────────
    def _on_convert_clicked(self, e):
        if self.is_processing:
            return

        out_path = self.out_path_text.value.strip()
        if not out_path:
            self.status_text.value = "Error: Please specify output destination."
            self.status_text.color = ft.Colors.RED_400
            self.page.update()
            return

        content = self.editor.value
        if not content.strip():
            self.status_text.value = "Error: Editor is empty."
            self.status_text.color = ft.Colors.RED_400
            self.page.update()
            return

        # Check if output file is locked by another program (Word/Excel/etc)
        if is_output_locked(out_path):
            self.status_text.value = f"Error: File '{os.path.basename(out_path)}' is currently open in Microsoft Word/Excel. Please close it first."
            self.status_text.color = ft.Colors.RED_400
            self.page.update()
            return

        # Check if output file already exists -> confirm overwrite
        if os.path.exists(out_path):
            self._confirm_overwrite_dialog(self.current_mode, content, out_path)
        else:
            self._start_conversion(self.current_mode, content, out_path)

    def _confirm_overwrite_dialog(self, mode: str, content: str, out_path: str):
        def on_overwrite(e):
            dlg.open = False
            self.page.update()
            if is_output_locked(out_path):
                self.status_text.value = f"Error: File '{os.path.basename(out_path)}' is open in another program (Word/Excel). Close it to overwrite."
                self.status_text.color = ft.Colors.RED_400
                self.page.update()
                return
            self._start_conversion(mode, content, out_path)

        def on_cancel(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Overwrite Output File?"),
            content=ft.Text(f"File '{os.path.basename(out_path)}' already exists.\nDo you want to overwrite it?"),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.ElevatedButton("Overwrite", on_click=on_overwrite),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _start_conversion(self, mode: str, content: str, out_path: str):
        self.is_processing = True
        self.progress_bar.visible = True
        self.btn_convert.disabled = True
        self.status_text.value = "Converting document..."
        self.status_text.color = ft.Colors.BLUE_400
        self.page.update()

        # Execute conversion asynchronously in background thread
        self.page.run_thread(self._background_conversion_worker, mode, content, out_path)

    def _open_converted_file(self, e):
        if self.last_converted_path and os.path.exists(self.last_converted_path):
            path = os.path.normpath(self.last_converted_path)
            print(f"[DEBUG] Opening converted file: {path}")
            os.startfile(path)
            snack = ft.SnackBar(
                content=ft.Text(f"Opened {os.path.basename(path)} — check taskbar if window is obscured."),
                duration=3000
            )
            self.page.overlay.append(snack)
            snack.open = True
            self.page.update()

    def _open_converted_folder(self, e):
        if self.last_converted_path and os.path.exists(self.last_converted_path):
            path = os.path.normpath(self.last_converted_path)
            print(f"[DEBUG] Opening destination folder with selection: {path}")
            import subprocess
            subprocess.Popen(f'explorer /select,"{path}"')
            snack = ft.SnackBar(
                content=ft.Text("Opened Explorer — check taskbar if window is obscured."),
                duration=3000
            )
            self.page.overlay.append(snack)
            snack.open = True
            self.page.update()

    def _background_conversion_worker(self, mode: str, content: str, out_path: str):
        print(f"[DEBUG] Starting background conversion job: mode='{mode}', out_path='{out_path}'")
        start_time = time.time()
        try:
            msg = convert_content(mode=mode, content=content, out_path=out_path)
            duration = time.time() - start_time
            print(f"[DEBUG] Conversion result: {msg} ({duration:.2f}s)")

            self.last_converted_path = out_path
            self.is_processing = False
            self.progress_bar.visible = False
            self.btn_convert.disabled = False
            self.btn_open_file.visible = True
            self.btn_open_folder.visible = True
            self.status_text.value = f"{msg} ({duration:.2f}s)"
            self.status_text.color = ft.Colors.GREEN_400
            self.page.update()
        except Exception as ex:
            err_msg = str(ex)
            print(f"[DEBUG] Conversion error: {err_msg}")

            self.is_processing = False
            self.progress_bar.visible = False
            self.btn_convert.disabled = False
            self.status_text.value = f"Conversion failed: {err_msg}"
            self.status_text.color = ft.Colors.RED_400
            self.page.update()


def main(page: ft.Page):
    app = DocumentConvertApp(page)

if __name__ == "__main__":
    ft.app(target=main)
