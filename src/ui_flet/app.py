"""
Main Flet UI Application Orchestrator for DocumentConvertTool.
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
from src.ui_flet.constants import (
    DRAFT_PATH,
    EDITOR_DISPLAY_LIMIT,
    MODES,
    IN_FILETYPES,
    OUT_FILETYPES,
)
from src.ui_flet.state import AppState
from src.ui_flet.theme import PALETTES, STYLE, apply_theme
from src.ui_flet.preview import MarkdownPreview
from src.ui_flet.native_dialogs import pick_input_file_async, pick_output_file_async
from src.ui_flet.layout.header_bar import HeaderBar
from src.ui_flet.layout.footer_bar import FooterBar
from src.ui_flet.components.file_path_bar import FilePathBar
from src.ui_flet.components.search_replace_bar import SearchReplaceBar
from src.ui_flet.views.editor_view import EditorView


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

        # Application State
        self.state = AppState()

        # Timers
        self._autosave_timer: threading.Timer | None = None
        self._undo_timer: threading.Timer | None = None
        self._preview_timer: threading.Timer | None = None

        # File Pickers for Web/Mobile fallback
        self.file_picker_in = ft.FilePicker()
        self.file_picker_out = ft.FilePicker()
        self.page.services.extend([self.file_picker_in, self.file_picker_out])

        # Apply Theme
        apply_theme(self.page, self.state.current_palette, self.state.current_theme_mode)

        # Build UI Controls & Layout
        self._build_controls()
        self._load_draft_if_exists()
        print(f"[DEBUG] App initialized successfully with Flet 3-tier Architecture")

    def _build_controls(self):
        # 1. Header Bar
        self.header_bar = HeaderBar(
            current_mode=self.state.current_mode,
            current_palette=self.state.current_palette,
            current_theme_mode=self.state.current_theme_mode,
            on_mode_changed=self._on_mode_changed,
            on_palette_changed=self._on_palette_changed,
            on_theme_mode_changed=self._on_theme_mode_changed,
        )

        # 2. File Path Bar
        self.file_path_bar = FilePathBar(
            on_browse_in=self._trigger_browse_input,
            on_browse_out=self._trigger_browse_output,
            on_out_path_changed=self._on_out_path_edited,
        )

        # 3. Search & Replace Bar
        self.search_replace_bar = SearchReplaceBar(
            on_search_changed=self._on_search_changed,
            on_find_next=self._find_next_via_button,
            on_find_prev=self._find_prev_via_button,
            on_replace=self._replace_current,
            on_replace_all=self._replace_all,
        )

        # 4. Editor View
        self.editor_view = EditorView(
            search_replace_bar=self.search_replace_bar,
            on_editor_changed=self._on_editor_changed,
            on_toggle_search=self._toggle_search_panel,
            on_undo=self._perform_undo,
            on_redo=self._perform_redo,
            on_clear=self._clear_editor,
        )

        # 5. Right Pane (Preview)
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
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(),
                    self.preview,
                ],
                expand=True,
            ),
            expand=True,
            padding=10,
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        )

        main_content = ft.Row(
            controls=[self.editor_view.container, self.right_pane],
            expand=True,
            spacing=10,
        )

        # 6. Footer Bar
        self.footer_bar = FooterBar(
            on_convert_clicked=self._on_convert_clicked,
            on_open_file=self._open_converted_file,
            on_open_folder=self._open_converted_folder,
        )

        # Assemble Page Tree
        self.page.add(
            self.header_bar.container,
            self.file_path_bar.container,
            main_content,
            self.footer_bar.container,
        )
        self._update_theme_colors()

    # ── Mode & Theme Handlers ────────────────────────────────────────────────
    def _on_mode_changed(self, e):
        self.state.current_mode = self.header_bar.mode_dropdown.value
        mode_cfg = MODES[self.state.current_mode]
        self.file_path_bar.set_in_label(mode_cfg['in_label'])
        self.file_path_bar.set_out_label(mode_cfg['out_label'])
        if self.state.in_path:
            in_base, _ = os.path.splitext(self.state.in_path)
            self.state.out_path = f"{in_base}{mode_cfg['out_ext']}"
            self.file_path_bar.set_out_path(self.state.out_path)

    def _on_palette_changed(self, e):
        self.state.current_palette = self.header_bar.palette_dropdown.value
        apply_theme(self.page, self.state.current_palette, self.state.current_theme_mode)
        self._update_theme_colors()

    def _on_theme_mode_changed(self, e):
        self.state.current_theme_mode = self.header_bar.theme_mode_dropdown.value
        apply_theme(self.page, self.state.current_palette, self.state.current_theme_mode)
        self._update_theme_colors()

    def _update_theme_colors(self):
        palette = PALETTES.get(self.state.current_palette, PALETTES["Violet Cyberpunk"])
        btn_fg = palette["btn_convert_fg"][1] if self.state.current_theme_mode != "Light" else palette["btn_convert_fg"][0]
        self.footer_bar.btn_convert.style.bgcolor = btn_fg
        self.page.update()

    # ── File Picking & Loading Handlers ──────────────────────────────────────
    def _trigger_browse_input(self, e):
        asyncio.create_task(self._async_browse_input())

    async def _async_browse_input(self):
        file_path = await pick_input_file_async(page=self.page, picker=self.file_picker_in)
        if file_path:
            filename = os.path.basename(file_path)
            self.editor_view.set_loading(filename)
            self.preview.set_content(f"*Loading {filename}...*")
            self.doc_info_text.value = "Loading..."
            self.doc_info_text.update()
            self.footer_bar.set_status(f"Loading file: {filename}...", ft.Colors.AMBER_400)
            self.footer_bar.set_processing(True)
            self.page.update()

            await asyncio.to_thread(self._load_file_into_workspace, file_path)
            self.page.update()

    def _trigger_browse_output(self, e):
        asyncio.create_task(self._async_browse_output())

    async def _async_browse_output(self):
        mode_cfg = MODES[self.state.current_mode]
        def_ext = mode_cfg["out_ext"]
        init_file = os.path.basename(self.state.out_path) if self.state.out_path else f"output{def_ext}"
        file_path = await pick_output_file_async(
            default_ext=def_ext, initial_file=init_file, page=self.page, picker=self.file_picker_out
        )
        if file_path:
            self.state.out_path = file_path
            self.file_path_bar.set_out_path(file_path)

    def _on_out_path_edited(self, e):
        self.state.out_path = self.file_path_bar.out_path_text.value.strip()

    def _load_file_into_workspace(self, file_path: str):
        t0 = time.time()
        try:
            self.state.in_path = file_path
            self.file_path_bar.set_in_path(file_path)
            ext = os.path.splitext(file_path)[1].lower()
            self.header_bar.update_mode_options(ext)
            self.state.current_mode = self.header_bar.mode_dropdown.value

            out_ext = MODES[self.state.current_mode]["out_ext"]
            base, _ = os.path.splitext(file_path)
            self.state.out_path = f"{base}{out_ext}"
            self.file_path_bar.set_out_path(self.state.out_path)

            # Step 1: Extract document via converter module
            t_start_extract = time.time()
            res = load_document(file_path)
            t_extract = time.time() - t_start_extract

            if not res.success:
                err_msg = res.error_short or "Failed to load document"
                self.footer_bar.set_status(f"Load failed: {err_msg}", ft.Colors.RED_400)
                return

            content = res.content
            self.state.full_content = content
            self.state.undo_stack.clear()
            self.state.redo_stack.clear()

            # Step 2: Update Editor View text
            t_start_editor = time.time()
            if len(content) > EDITOR_DISPLAY_LIMIT:
                self.editor_view.set_text(content[:EDITOR_DISPLAY_LIMIT])
            else:
                self.editor_view.set_text(content)
            t_editor = time.time() - t_start_editor

            self.state.undo_stack.append(self.editor_view.get_text())
            self.state.is_dirty = False

            words = len(content.split())
            chars = len(content)
            self.doc_info_text.value = f"{words:,} words | {chars:,} chars"
            self.doc_info_text.update()

            # Step 3: Update Preview
            t_start_preview = time.time()
            self._update_markdown_preview(content)
            t_preview = time.time() - t_start_preview

            t_total = time.time() - t0
            bench_msg = f"[BENCHMARK] Total load time: {t_total:.2f}s | Module extraction: {t_extract:.2f}s | Editor update: {t_editor:.2f}s | Preview update: {t_preview:.2f}s"
            print(bench_msg)

            if len(content) > EDITOR_DISPLAY_LIMIT:
                self.footer_bar.set_status(f"File truncated (>{EDITOR_DISPLAY_LIMIT} chars) ({t_total:.2f}s)", ft.Colors.ORANGE_400)
            else:
                self.footer_bar.set_status(f"Loaded: {os.path.basename(file_path)} ({t_total:.2f}s)", ft.Colors.GREEN_400)
        except Exception as ex:
            self.footer_bar.set_status(f"Failed to load file: {ex}", ft.Colors.RED_400)
        finally:
            self.footer_bar.set_processing(False)

    # ── Editor & Undo/Redo Handlers ──────────────────────────────────────────
    def _on_editor_changed(self, e):
        if not self.state.is_undo_redo_op:
            self.state.redo_stack.clear()
            if self._undo_timer:
                self._undo_timer.cancel()
            self._undo_timer = threading.Timer(0.8, self._push_undo_state)
            self._undo_timer.start()

        self.state.is_dirty = True
        current_text = self.editor_view.get_text()
        self.state.full_content = current_text

        words = len(current_text.split())
        chars = len(current_text)
        self.doc_info_text.value = f"{words:,} words | {chars:,} chars"
        self.doc_info_text.update()

        if self._preview_timer:
            self._preview_timer.cancel()
        self._preview_timer = threading.Timer(0.3, lambda: self._update_markdown_preview(current_text))
        self._preview_timer.start()

        if self._autosave_timer:
            self._autosave_timer.cancel()
        self._autosave_timer = threading.Timer(2.0, self._perform_autosave)
        self._autosave_timer.start()

    def _push_undo_state(self):
        txt = self.editor_view.get_text()
        if not self.state.undo_stack or self.state.undo_stack[-1] != txt:
            self.state.undo_stack.append(txt)
            if len(self.state.undo_stack) > 100:
                self.state.undo_stack.pop(0)

    def _perform_undo(self, e=None):
        if len(self.state.undo_stack) > 1:
            self.state.is_undo_redo_op = True
            current = self.state.undo_stack.pop()
            self.state.redo_stack.append(current)
            prev_text = self.state.undo_stack[-1]
            self.editor_view.set_text(prev_text)
            self.state.full_content = prev_text
            self._update_markdown_preview(prev_text)
            self.state.is_undo_redo_op = False

    def _perform_redo(self, e=None):
        if self.state.redo_stack:
            self.state.is_undo_redo_op = True
            next_text = self.state.redo_stack.pop()
            self.state.undo_stack.append(next_text)
            self.editor_view.set_text(next_text)
            self.state.full_content = next_text
            self._update_markdown_preview(next_text)
            self.state.is_undo_redo_op = False

    def _clear_editor(self, e=None):
        self.editor_view.set_text("")
        self.state.full_content = ""
        self.state.undo_stack.clear()
        self.state.redo_stack.clear()
        self.state.undo_stack.append("")
        self.doc_info_text.value = "0 words | 0 chars"
        self.doc_info_text.update()
        self.preview.update_preview("", base_dir=os.path.dirname(self.state.in_path) if self.state.in_path else None)

    # ── Search & Replace Handlers ───────────────────────────────────────────
    def _toggle_search_panel(self, e=None):
        self.search_replace_bar.toggle_visibility()

    def _on_search_changed(self, e=None):
        query = self.search_replace_bar.search_input.value
        content = self.editor_view.get_text()
        self.state.search_matches.clear()
        self.state.current_match_idx = -1

        if query:
            try:
                flags = 0 if self.search_replace_bar.chk_case.value else re.IGNORECASE
                pattern = query if self.search_replace_bar.chk_regex.value else re.escape(query)
                for match in re.finditer(pattern, content, flags):
                    self.state.search_matches.append(match.span())
            except Exception:
                pass

        count = len(self.state.search_matches)
        if count > 0:
            self.state.current_match_idx = 0
            self.search_replace_bar.set_match_label(f"1 of {count}")
        else:
            self.search_replace_bar.set_match_label("0 matches")

    def _find_next_via_button(self, e=None):
        if self.state.search_matches:
            self.state.current_match_idx = (self.state.current_match_idx + 1) % len(self.state.search_matches)
            self.search_replace_bar.set_match_label(f"{self.state.current_match_idx + 1} of {len(self.state.search_matches)}")

    def _find_prev_via_button(self, e=None):
        if self.state.search_matches:
            self.state.current_match_idx = (self.state.current_match_idx - 1) % len(self.state.search_matches)
            self.search_replace_bar.set_match_label(f"{self.state.current_match_idx + 1} of {len(self.state.search_matches)}")

    def _replace_current(self, e=None):
        if not self.state.search_matches or self.state.current_match_idx < 0:
            return
        find_val = self.search_replace_bar.search_input.value
        repl_val = self.search_replace_bar.replace_input.value or ""
        content = self.editor_view.get_text()
        start, end = self.state.search_matches[self.state.current_match_idx]

        new_content = content[:start] + repl_val + content[end:]
        self.editor_view.set_text(new_content)
        self._on_editor_changed(None)
        self._on_search_changed(None)

    def _replace_all(self, e=None):
        query = self.search_replace_bar.search_input.value
        repl_val = self.search_replace_bar.replace_input.value or ""
        content = self.editor_view.get_text()
        if not query:
            return
        try:
            flags = 0 if self.search_replace_bar.chk_case.value else re.IGNORECASE
            pattern = query if self.search_replace_bar.chk_regex.value else re.escape(query)
            new_content = re.sub(pattern, repl_val, content, flags=flags)
            self.editor_view.set_text(new_content)
            self._on_editor_changed(None)
            self._on_search_changed(None)
        except Exception as ex:
            self.footer_bar.set_status(f"Replace All failed: {ex}", ft.Colors.RED_400)

    # ── Markdown Preview & Autosave Helpers ──────────────────────────────────
    def _update_markdown_preview(self, content: str):
        base_dir = os.path.dirname(self.state.in_path) if self.state.in_path else None
        self.preview.update_preview(content, base_dir=base_dir)

    def _load_draft_if_exists(self):
        if os.path.exists(DRAFT_PATH):
            try:
                with open(DRAFT_PATH, "r", encoding="utf-8") as f:
                    draft = f.read()
                if draft.strip():
                    self.state.full_content = draft
                    self.editor_view.set_text(draft)
                    self.state.undo_stack.append(draft)
                    self._update_markdown_preview(draft)
                    self.footer_bar.set_status("Loaded autosaved draft", ft.Colors.GREEN_400)
            except Exception as e:
                print(f"[DEBUG] Failed to load draft: {e}")

    def _perform_autosave(self):
        try:
            os.makedirs(os.path.dirname(DRAFT_PATH), exist_ok=True)
            with open(DRAFT_PATH, "w", encoding="utf-8") as f:
                f.write(self.editor_view.get_text())
        except Exception as e:
            print(f"[DEBUG] Autosave error: {e}")

    # ── Conversion Execution ─────────────────────────────────────────────────
    def _on_convert_clicked(self, e):
        content = self.editor_view.get_text()
        if not content or not content.strip():
            self.footer_bar.set_status("Editor content is empty! Please type or load a document.", ft.Colors.RED_400)
            return

        out_path = self.file_path_bar.out_path_text.value.strip()
        if not out_path:
            self.footer_bar.set_status("Please specify output path", ft.Colors.RED_400)
            return

        if is_output_locked(out_path):
            self.footer_bar.set_status("Output file locked! Close target file and try again.", ft.Colors.RED_400)
            return

        self.state.is_processing = True
        self.footer_bar.set_processing(True)
        self.footer_bar.set_status("Converting...", ft.Colors.AMBER_400)

        threading.Thread(target=self._run_conversion_worker, args=(out_path,), daemon=True).start()

    def _run_conversion_worker(self, out_path: str):
        t0 = time.time()
        try:
            content = self.editor_view.get_text()
            msg = convert_content(self.state.current_mode, content, out_path)
            duration = time.time() - t0

            self.state.last_converted_path = out_path
            self.state.is_processing = False
            self.footer_bar.set_processing(False)
            self.footer_bar.set_result_buttons_visible(True)
            self.footer_bar.set_status(f"{msg} ({duration:.2f}s)", ft.Colors.GREEN_400)
        except Exception as ex:
            err_msg = str(ex)
            print(f"[DEBUG] Conversion error: {err_msg}")
            self.state.is_processing = False
            self.footer_bar.set_processing(False)
            self.footer_bar.set_status(f"Conversion failed: {err_msg}", ft.Colors.RED_400)

    def _open_converted_file(self, e):
        if self.state.last_converted_path and os.path.exists(self.state.last_converted_path):
            os.startfile(self.state.last_converted_path)

    def _open_converted_folder(self, e):
        if self.state.last_converted_path and os.path.exists(self.state.last_converted_path):
            folder = os.path.dirname(self.state.last_converted_path)
            os.startfile(folder)


def main(page: ft.Page):
    app = DocumentConvertApp(page)


if __name__ == "__main__":
    ft.app(target=main)
