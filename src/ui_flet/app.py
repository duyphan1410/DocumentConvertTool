"""
Main Flet UI Application Orchestrator for DocumentConvertTool.
"""
import os
import re
import time
import json
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
    DRAFT_META_PATH,
    EDITOR_DISPLAY_LIMIT,
    MODES,
    IN_FILETYPES,
    OUT_FILETYPES,
)
from src.ui_flet.state import AppState
from src.ui_flet.theme import PALETTES, STYLE, apply_theme, resolve_color, make_border
from src.ui_flet.native_dialogs import (
    pick_input_file_async,
    pick_output_file_async,
    pick_image_file_async,
    confirm_overwrite_sync,
)
from src.ui_flet.layout.footer_bar import FooterBar
from src.ui_flet.layout.ribbon_bar import RibbonBar
from src.ui_flet.components.file_path_bar import FilePathBar
from src.ui_flet.components.search_replace_bar import SearchReplaceBar
from src.ui_flet.views.editor_view import EditorView
from src.ui_flet.views.preview_view import MarkdownPreview


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

        # Timers & Tasks
        self._autosave_timer: threading.Timer | None = None
        self._undo_timer: threading.Timer | None = None
        self._preview_task: asyncio.Task | None = None

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
        # 1. Search & Replace Bar (created first — used by RibbonBar and EditorView)
        self.search_replace_bar = SearchReplaceBar(
            on_search_changed=self._on_search_changed,
            on_find_next=self._find_next_via_button,
            on_find_prev=self._find_prev_via_button,
            on_replace=self._replace_current,
            on_replace_all=self._replace_all,
            on_match_click=self._on_search_match_clicked,
        )

        # 2. Ribbon Bar (Root Top Navigation)
        self.ribbon_bar = RibbonBar(
            current_mode=self.state.current_mode,
            current_palette=self.state.current_palette,
            current_theme_mode=self.state.current_theme_mode,
            on_mode_changed=self._on_mode_changed,
            on_palette_changed=self._on_palette_changed,
            on_theme_mode_changed=self._on_theme_mode_changed,
            on_browse_in=self._trigger_browse_input,
            on_browse_out=self._trigger_browse_output,
            on_clear_editor=self._clear_editor,
            on_format_action=self._on_format_action,
            on_heading_change=self._on_heading_change,
            on_toggle_search=self._toggle_search_panel,
            on_convert_click=self._on_convert_clicked,
            on_toggle_preview=self._toggle_preview_pane,
            on_toggle_file_path_bar=self._toggle_file_path_bar,
            on_toggle_editor=self._toggle_editor_panel,
            on_toggle_status_bar=self._toggle_status_bar,
            on_insert_image=self._trigger_insert_image,
            on_ribbon_toggle=self._update_editor_dynamic_height,
            search_replace_bar=self.search_replace_bar,
        )

        # 3. File Path Bar
        self.file_path_bar = FilePathBar(
            on_browse_in=self._trigger_browse_input,
            on_browse_out=self._trigger_browse_output,
            on_out_path_changed=self._on_out_path_edited,
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

        # 5. Right Pane (Preview) — header is owned by MarkdownPreview
        self.preview = MarkdownPreview()

        # doc_info_text is owned by preview (accessible via self.preview.doc_info_text)
        self.doc_info_text = self.preview.doc_info_text

        self.right_pane = ft.Container(
            content=self.preview,
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

        # Assemble Page Tree (Clean unified layout with RibbonBar at the top)
        self.page.add(
            self.ribbon_bar,
            self.file_path_bar.container,
            main_content,
            self.footer_bar.container,
        )
        self._update_theme_colors()

    def _on_format_action(self, prefix: str, suffix: str):
        self.editor_view.apply_formatting(prefix, suffix)

    def _on_heading_change(self, level: int):
        self.editor_view.apply_heading(level)

    def _update_editor_dynamic_height(self):
        file_path_vis = self.file_path_bar.container.visible
        status_vis = self.footer_bar.container.visible
        ribbon_vis = self.ribbon_bar.is_expanded

        lines = 21
        if not file_path_vis:
            lines += 4
        if not status_vis:
            lines += 3
        if not ribbon_vis:
            lines += 3

        self.editor_view.set_min_lines(lines)

    def _toggle_preview_pane(self, e=None):
        self.right_pane.visible = not self.right_pane.visible
        try:
            self.page.update()
        except Exception:
            pass

    def _toggle_file_path_bar(self, e=None):
        """Toggle visibility of the Input/Output file path bar."""
        self.file_path_bar.container.visible = not self.file_path_bar.container.visible
        self._update_editor_dynamic_height()
        try:
            self.page.update()
        except Exception:
            pass

    def _toggle_editor_panel(self, e=None):
        """Toggle visibility of the editor text panel."""
        self.editor_view.container.visible = not self.editor_view.container.visible
        try:
            self.page.update()
        except Exception:
            pass

    def _toggle_status_bar(self, e=None):
        """Toggle visibility of the bottom status/action bar."""
        self.footer_bar.container.visible = not self.footer_bar.container.visible
        self._update_editor_dynamic_height()
        try:
            self.page.update()
        except Exception:
            pass

    def _toggle_theme_quick(self, e=None):
        new_mode = "Dark" if self.state.current_theme_mode == "Light" else "Light"
        self.state.current_theme_mode = new_mode
        self.ribbon_bar.theme_mode_dropdown.value = new_mode
        apply_theme(self.page, self.state.current_palette, new_mode)
        self._update_theme_colors()

    # ── Mode & Theme Handlers ────────────────────────────────────────────────
    def _on_mode_changed(self, e):
        self.state.current_mode = self.ribbon_bar.mode_dropdown.value
        mode_cfg = MODES[self.state.current_mode]
        self.file_path_bar.set_in_label(mode_cfg['in_label'])
        self.file_path_bar.set_out_label(mode_cfg['out_label'])
        if self.state.in_path:
            in_base, _ = os.path.splitext(self.state.in_path)
            self.state.out_path = f"{in_base}{mode_cfg['out_ext']}"
            self.file_path_bar.set_out_path(self.state.out_path)

    def _on_palette_changed(self, e):
        self.state.current_palette = self.ribbon_bar.palette_dropdown.value
        apply_theme(self.page, self.state.current_palette, self.state.current_theme_mode)
        self._update_theme_colors()

    def _on_theme_mode_changed(self, e):
        self.state.current_theme_mode = self.ribbon_bar.theme_mode_dropdown.value
        apply_theme(self.page, self.state.current_palette, self.state.current_theme_mode)
        self._update_theme_colors()

    def _update_theme_colors(self):
        palette = PALETTES.get(self.state.current_palette, PALETTES["Violet Cyberpunk"])
        is_dark = (self.state.current_theme_mode != "Light")

        # 1. Ribbon bar (header background + panel container)
        self.ribbon_bar.apply_palette(palette, is_dark)

        # 2. File path bar (bg_component background + border)
        self.file_path_bar.apply_palette(palette, is_dark)

        # 3. Editor view (bg_pure_dark + accent title color + border)
        self.editor_view.apply_palette(palette, is_dark)

        # 4. Right pane — bg_pure_dark + preview header palette
        bg_pure_dark = resolve_color(palette, "bg_pure_dark", is_dark)
        border = resolve_color(palette, "border_color", is_dark)
        self.right_pane.bgcolor = bg_pure_dark
        self.right_pane.border = make_border(1, border)
        self.preview.apply_palette(palette, is_dark, self.state.current_palette)

        # 5. Footer bar (bg_component, btn_convert, btn_open, progress bar)
        self.footer_bar.apply_palette(palette, is_dark)

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

            t0 = time.time()
            res = await asyncio.to_thread(load_document, file_path)
            t_extract = time.time() - t0

            if not res.success:
                err_msg = res.error_short or "Failed to load document"
                self.footer_bar.set_status(f"Load failed: {err_msg}", ft.Colors.RED_400)
                self.footer_bar.set_processing(False)
                self.page.update()
                return

            content = res.content
            self.state.in_path = file_path
            self.file_path_bar.set_in_path(file_path)

            ext = os.path.splitext(file_path)[1].lower()
            self.ribbon_bar.update_mode_options(ext)
            self.state.current_mode = self.ribbon_bar.mode_dropdown.value

            out_ext = MODES[self.state.current_mode]["out_ext"]
            base, _ = os.path.splitext(file_path)
            self.state.out_path = f"{base}{out_ext}"
            self.file_path_bar.set_out_path(self.state.out_path)

            self.state.full_content = content
            self.state.undo_stack.clear()
            self.state.redo_stack.clear()

            # Step 2: Synchronous main thread Editor & Preview update
            if len(content) > EDITOR_DISPLAY_LIMIT:
                self.editor_view.set_text(content[:EDITOR_DISPLAY_LIMIT])
            else:
                self.editor_view.set_text(content)

            self.state.undo_stack.append(self.editor_view.get_text())
            self.state.is_dirty = False

            words = len(content.split())
            chars = len(content)
            self.doc_info_text.value = f"{words:,} words | {chars:,} chars"

            self._update_markdown_preview(content)

            t_total = time.time() - t0
            bench_msg = f"[BENCHMARK] Total load time: {t_total:.2f}s | Module extraction: {t_extract:.2f}s"
            print(bench_msg)

            if len(content) > EDITOR_DISPLAY_LIMIT:
                self.footer_bar.set_status(f"File truncated (>{EDITOR_DISPLAY_LIMIT} chars) ({t_total:.2f}s)", ft.Colors.ORANGE_400)
            else:
                self.footer_bar.set_status(f"Loaded: {os.path.basename(file_path)} ({t_total:.2f}s)", ft.Colors.GREEN_400)

            self.footer_bar.set_processing(False)
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

    def _trigger_insert_image(self, e=None):
        asyncio.create_task(self._async_insert_image())

    async def _async_insert_image(self):
        img_path = await pick_image_file_async(page=self.page, picker=self.file_picker_in)
        if img_path:
            img_name = os.path.basename(img_path)
            alt_text = os.path.splitext(img_name)[0]
            normalized_path = img_path.replace("\\", "/")
            token = f"![{alt_text}](file:///{normalized_path})"
            self.editor_view.apply_formatting(token, "")

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

        # Debounced preview update (300ms) on Main asyncio Event Loop to prevent Flet UI thread blocking
        if self._preview_task and not self._preview_task.done():
            self._preview_task.cancel()
        self._preview_task = asyncio.create_task(self._async_update_markdown_preview_debounced(current_text))

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
        """Toggle search panel in Ribbon Edit Tab (Ctrl+F shortcut support or callback)."""
        if isinstance(e, bool):
            # Callback from RibbonBar indicating the new visibility state
            if not e:
                # Clear search matches and hide results container
                self.state.search_matches.clear()
                self.state.current_match_idx = -1
                self.search_replace_bar.set_match_label("0 matches")
                self.search_replace_bar.results_container.visible = False
                self.search_replace_bar.update_results([])
                # Clear selection highlight in Editor
                self.editor_view.editor.selection = None
                try:
                    self.editor_view.editor.update()
                except Exception:
                    pass
            else:
                # Re-run search query to restore highlights/matches
                self._on_search_changed(None)
            return

        # Triggered programmatically or by shortcut
        self.ribbon_bar.toggle_search()

    def _highlight_current_match(self, focus: bool = False):
        if not self.state.search_matches or self.state.current_match_idx < 0:
            return
        if self.state.current_match_idx >= len(self.state.search_matches):
            self.state.current_match_idx = 0

        start, end = self.state.search_matches[self.state.current_match_idx]
        self.editor_view.select_range(start, end, focus=focus)

    def _on_search_match_clicked(self, start: int, end: int):
        """Called when a user clicks a result in the Search Navigation Results List."""
        if self.state.search_matches:
            for idx, (s, e) in enumerate(self.state.search_matches):
                if s == start and e == end:
                    self.state.current_match_idx = idx
                    break
        self.search_replace_bar.set_match_label(f"{self.state.current_match_idx + 1} of {len(self.state.search_matches)}")
        self._on_search_changed(None, keep_active_idx=True)
        self.editor_view.select_range(start, end, focus=True)

    def _on_search_changed(self, e=None, keep_active_idx: bool = False):
        query = self.search_replace_bar.search_input.value
        content = self.editor_view.get_text()
        content_lf = content.replace("\r\n", "\n")

        if not keep_active_idx:
            self.state.search_matches.clear()
            self.state.current_match_idx = -1

        if query:
            try:
                flags = 0 if self.search_replace_bar.chk_case.value else re.IGNORECASE
                pattern = query if self.search_replace_bar.chk_regex.value else re.escape(query)
                matches = []
                for match in re.finditer(pattern, content_lf, flags):
                    matches.append(match.span())
                self.state.search_matches = matches
            except Exception:
                pass

        count = len(self.state.search_matches)
        matches_data = []

        if count > 0:
            if self.state.current_match_idx < 0 or self.state.current_match_idx >= count:
                self.state.current_match_idx = 0
            self.search_replace_bar.set_match_label(f"{self.state.current_match_idx + 1} of {count}")

            lines = content_lf.split("\n")
            line_starts = []
            curr = 0
            for l in lines:
                line_starts.append(curr)
                curr += len(l) + 1

            for start, end in self.state.search_matches:
                line_num = 1
                snippet = ""
                for idx, l_start in enumerate(line_starts):
                    l_end = l_start + len(lines[idx])
                    if l_start <= start <= l_end or (idx == len(lines) - 1 and start >= l_start):
                        line_num = idx + 1
                        snippet = lines[idx]
                        break
                matches_data.append({
                    "start": start,
                    "end": end,
                    "line": line_num,
                    "snippet": f"L{line_num}: {snippet.strip()[:60]}"
                })

            self._highlight_current_match(focus=False)
        else:
            self.search_replace_bar.set_match_label("0 matches")

        self.search_replace_bar.update_results(matches_data, self.state.current_match_idx)

    def _find_next_via_button(self, e=None):
        if self.state.search_matches:
            self.state.current_match_idx = (self.state.current_match_idx + 1) % len(self.state.search_matches)
            self.search_replace_bar.set_match_label(f"{self.state.current_match_idx + 1} of {len(self.state.search_matches)}")
            start, end = self.state.search_matches[self.state.current_match_idx]
            self._on_search_changed(None, keep_active_idx=True)
            self.editor_view.select_range(start, end, focus=True)
            self.search_replace_bar.focus_search_input()

    def _find_prev_via_button(self, e=None):
        if self.state.search_matches:
            self.state.current_match_idx = (self.state.current_match_idx - 1) % len(self.state.search_matches)
            self.search_replace_bar.set_match_label(f"{self.state.current_match_idx + 1} of {len(self.state.search_matches)}")
            start, end = self.state.search_matches[self.state.current_match_idx]
            self._on_search_changed(None, keep_active_idx=True)
            self.editor_view.select_range(start, end, focus=True)
            self.search_replace_bar.focus_search_input()





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

    async def _async_update_markdown_preview_debounced(self, content: str):
        try:
            await asyncio.sleep(0.3)
            self._update_markdown_preview(content)
            self.page.update()
        except asyncio.CancelledError:
            pass
        except Exception as ex:
            print(f"[DEBUG] Debounced preview update error: {ex}")

    def _load_draft_if_exists(self):
        if os.path.exists(DRAFT_PATH):
            try:
                with open(DRAFT_PATH, "r", encoding="utf-8") as f:
                    draft = f.read()
                if draft.strip():
                    self.state.full_content = draft
                    self.editor_view.set_text(draft)
                    self.state.undo_stack.append(draft)
                    
                    if os.path.exists(DRAFT_META_PATH):
                        try:
                            with open(DRAFT_META_PATH, "r", encoding="utf-8") as mf:
                                meta = json.load(mf)
                            if meta.get("in_path"):
                                self.state.in_path = meta["in_path"]
                                self.file_path_bar.set_in_path(meta["in_path"])
                            if meta.get("out_path"):
                                self.state.out_path = meta["out_path"]
                                self.file_path_bar.set_out_path(meta["out_path"])
                        except Exception as me:
                            print(f"[DEBUG] Failed to load draft metadata: {me}")

                    self._update_markdown_preview(draft)
                    self.footer_bar.set_status("Loaded autosaved draft", ft.Colors.GREEN_400)
            except Exception as e:
                print(f"[DEBUG] Failed to load draft: {e}")

    def _perform_autosave(self):
        try:
            os.makedirs(os.path.dirname(DRAFT_PATH), exist_ok=True)
            with open(DRAFT_PATH, "w", encoding="utf-8") as f:
                f.write(self.editor_view.get_text())
            meta = {
                "in_path": self.state.in_path or "",
                "out_path": self.state.out_path or "",
            }
            with open(DRAFT_META_PATH, "w", encoding="utf-8") as mf:
                json.dump(meta, mf)
        except Exception as e:
            print(f"[DEBUG] Autosave error: {e}")

    # ── Conversion Execution ─────────────────────────────────────────────────
    def _on_convert_clicked(self, e):
        t0 = time.time()  # Start timer at the instant Convert button is clicked

        content = self.editor_view.get_text()
        if not content or not content.strip():
            self.footer_bar.set_status("Editor content is empty! Please type or load a document.", ft.Colors.RED_400)
            return

        raw_out = self.file_path_bar.out_path_text.value or ""
        out_path = raw_out.strip('"\' ')
        if not out_path:
            mode_cfg = MODES.get(self.state.current_mode, {})
            out_ext = mode_cfg.get("out_ext", ".html")
            docs_dir = os.path.expanduser("~/Documents")
            if not os.path.exists(docs_dir):
                docs_dir = os.getcwd()
            fallback_path = os.path.normpath(os.path.join(docs_dir, f"Converted_Draft{out_ext}"))
            out_path = fallback_path
            self.state.out_path = fallback_path
            self.file_path_bar.set_out_path(fallback_path)

        out_path = os.path.normpath(out_path)
        print(f"[DEBUG] Convert clicked: out_path='{out_path}', exists={os.path.exists(out_path)}")

        if os.path.exists(out_path):
            if is_output_locked(out_path):
                file_name = os.path.basename(out_path)
                self.footer_bar.set_status(
                    f"Cannot overwrite! File '{file_name}' is currently open in another program. Please close the file and try again.",
                    ft.Colors.RED_400,
                    is_error=True,
                )
                return
            self._show_overwrite_confirmation_dialog(
                out_path,
                on_confirm_callback=lambda: self._start_conversion_process(content, out_path, t0)
            )
            return

        self._start_conversion_process(content, out_path, t0)

    def _show_overwrite_confirmation_dialog(self, out_path: str, on_confirm_callback):
        """Shows a Flet AlertDialog styled with current palette for file overwrite confirmation."""
        from src.ui_flet.theme import resolve_color, get_style_color
        palette = PALETTES.get(self.state.current_palette, PALETTES.get("Violet Cyberpunk", {}))
        is_dark = self.page.theme_mode != ft.ThemeMode.LIGHT

        bg_card = resolve_color(palette, "bg_component", is_dark)
        bg_pill = resolve_color(palette, "bg_header", is_dark)
        accent_color = resolve_color(palette, "text_accent_secondary", is_dark)
        text_primary = get_style_color("text_primary", is_dark)
        text_secondary = get_style_color("text_secondary", is_dark)
        border_color = resolve_color(palette, "border_color", is_dark)

        file_name = os.path.basename(out_path)

        def close_dialog(e, confirmed: bool):
            print("[DEBUG] Closing overwrite dialog")

            dialog.open = False
            self.page.update()

            if confirmed:
                on_confirm_callback()
            else:
                self.footer_bar.set_status(
                    "Conversion cancelled: File overwrite rejected.",
                    ft.Colors.AMBER_400,
                )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.WARNING_ROUNDED, color=ft.Colors.AMBER_400, size=24),
                    ft.Text("Confirm File Overwrite", weight=ft.FontWeight.BOLD, size=18, color=text_primary),
                ],
                spacing=10,
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "The target output file already exists on disk:",
                            size=13,
                            color=text_secondary,
                        ),
                        ft.Container(
                            content=ft.Text(
                                file_name,
                                weight=ft.FontWeight.W_600,
                                size=13,
                                color=accent_color,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            padding=10,
                            bgcolor=bg_pill,
                            border_radius=6,
                            border=make_border(1, border_color),
                        ),
                        ft.Text(
                            "Do you want to overwrite and replace this file?",
                            size=13,
                            color=text_secondary,
                        ),
                    ],
                    tight=True,
                    spacing=12,
                ),
                width=420,
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda e: close_dialog(e, False),
                    style=ft.ButtonStyle(color=text_secondary),
                ),
                ft.Button(
                    "Overwrite / Replace",
                    icon=ft.Icons.AUTORENEW_ROUNDED,
                    on_click=lambda e: close_dialog(e, True),
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        bgcolor=ft.Colors.RED_600,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=bg_card,
            shape=ft.RoundedRectangleBorder(radius=10),
        )

        if dialog not in self.page.overlay:
            self.page.overlay.append(dialog)
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _start_conversion_process(self, content: str, out_path: str, t0: float | None = None):
        asyncio.create_task(self._async_start_conversion(content, out_path, t0))

    async def _async_start_conversion(self, content: str, out_path: str, t0: float | None = None):
        self.state.is_processing = True
        self.footer_bar.set_processing(True)
        self.footer_bar.set_status("Converting...", ft.Colors.AMBER_400)
        self.page.update()

        if t0 is None:
            t0 = time.time()

        try:
            msg = await asyncio.to_thread(convert_content, self.state.current_mode, content, out_path)
            duration = time.time() - t0

            self.state.last_converted_path = out_path
            self.state.is_processing = False
            self.footer_bar.set_processing(False)
            self.footer_bar.set_result_buttons_visible(True)
            self.footer_bar.set_status(f"{msg} ({duration:.2f}s)", ft.Colors.GREEN_400)
            self.page.update()
            print(f"[BENCHMARK] Full Perceived Time (Click Convert -> UI Complete): {duration:.3f}s")
        except Exception as ex:
            raw_err = str(ex)
            print(f"[DEBUG] Conversion error: {raw_err}")
            
            if isinstance(ex, PermissionError) or "Permission denied" in raw_err or "WinError 32" in raw_err or "WinError 5" in raw_err:
                file_name = os.path.basename(out_path)
                display_err = f"Cannot overwrite! File '{file_name}' is currently open in another program. Please close the file and try again."
            else:
                display_err = f"Conversion failed: {raw_err}"

            self.state.is_processing = False
            self.footer_bar.set_processing(False)
            self.footer_bar.set_status(display_err, ft.Colors.RED_400, is_error=True)
            self.page.update()

    def _open_converted_file(self, e):
        if self.state.last_converted_path and os.path.exists(self.state.last_converted_path):
            file_path = os.path.normpath(self.state.last_converted_path)
            try:
                import sys
                if sys.platform == "win32":
                    os.startfile(file_path)
                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.Popen(["open", file_path])
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", file_path])
            except Exception as ex:
                print(f"[DEBUG] Failed to open file '{file_path}': {ex}")

    def _open_converted_folder(self, e):
        if self.state.last_converted_path and os.path.exists(self.state.last_converted_path):
            file_path = os.path.normpath(self.state.last_converted_path)
            try:
                import sys
                if sys.platform == "win32":
                    import subprocess
                    subprocess.Popen(f'explorer /select,"{file_path}"')
                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.Popen(["open", "-R", file_path])
                else:
                    import subprocess
                    folder = os.path.dirname(file_path)
                    subprocess.Popen(["xdg-open", folder])
            except Exception as ex:
                print(f"[DEBUG] Failed to open folder for '{file_path}': {ex}")
                folder = os.path.dirname(file_path)
                if hasattr(os, "startfile"):
                    os.startfile(folder)


def main(page: ft.Page):
    app = DocumentConvertApp(page)


if __name__ == "__main__":
    ft.app(target=main)
