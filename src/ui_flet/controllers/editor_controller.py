"""
Editor & Formatting Controller for Flet UI.
Decouples editor text changes, Undo/Redo stack management, formatting shortcuts, and clear operations.
"""
import os
import threading
import flet as ft
from src.i18n import t
from src.ui_flet.state import AppState


class EditorController:
    def __init__(self, page: ft.Page, state: AppState, app_controls: dict):
        self.page = page
        self.state = state
        self.app_controls = app_controls
        self.editor_view = app_controls["editor_view"]
        self.preview = app_controls["preview"]
        self.footer_bar = app_controls["footer_bar"]

        self._undo_timer: threading.Timer | None = None
        self._autosave_timer: threading.Timer | None = None

    def on_format_action(self, prefix: str, suffix: str):
        self._push_undo_state()
        self.editor_view.apply_formatting(prefix, suffix)

    def on_heading_change(self, level: int):
        self._push_undo_state()
        self.editor_view.apply_heading(level)

    def apply_image_size(self, image_info, width: str = "", height: str = "", align: str = "", alt: str | None = None, src: str | None = None):
        self._push_undo_state()
        self.editor_view.apply_image_size(image_info, width=width, height=height, align=align, alt=alt, src=src)

    def on_editor_changed(self, e=None, file_controller=None):
        if not self.state.is_undo_redo_op:
            self.state.redo_stack.clear()
            current_text = self.editor_view.get_text()
            last_pushed = self.state.undo_stack[-1] if self.state.undo_stack else ""
            if abs(len(current_text) - len(last_pushed)) >= 5 or (current_text and current_text[-1] in (" ", "\n", ".", ",", "!", "?", ";", ":")):
                self._push_undo_state()
            else:
                if self._undo_timer:
                    self._undo_timer.cancel()
                self._undo_timer = threading.Timer(0.3, self._push_undo_state)
                self._undo_timer.start()

        was_dirty = getattr(self.state, "is_dirty", False)
        self.state.is_dirty = True
        current_text = self.editor_view.get_text()
        self.state.full_content = current_text

        # Update WorkspaceTabBar dirty dot if status changed
        if not was_dirty:
            tab_bar = self.app_controls.get("workspace_tab_bar")
            if tab_bar and hasattr(tab_bar, "render_tabs"):
                tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)

        words = len(current_text.split())
        chars = len(current_text)
        self.preview.doc_info_text.value = t("editor.doc_info", words=f"{words:,}", chars=f"{chars:,}")
        if self.preview.doc_info_text.page:
            try:
                self.preview.doc_info_text.update()
            except Exception:
                pass

        active_tab = self.state.active_tab
        if active_tab:
            active_tab.full_content = current_text
            session_id = active_tab.media_session_id
        else:
            session_id = None

        base_dir = (
            os.path.dirname(self.state.in_path) if self.state.in_path else None
        )
        self.preview.update_preview(current_text, base_dir=base_dir, session_id=session_id)
        if active_tab:
            active_tab.cached_preview_md = getattr(self.preview, "_cached_processed_text", "")

        fc = file_controller or self.app_controls.get("file_controller")
        if fc and getattr(self.state, "autosave_enabled", True):
            if self._autosave_timer:
                self._autosave_timer.cancel()
            interval_sec = float(getattr(self.state, "autosave_interval_sec", 30))
            self._autosave_timer = threading.Timer(
                interval_sec, fc.perform_autosave
            )
            self._autosave_timer.start()

    def _push_undo_state(self):
        txt = self.editor_view.get_text()
        if not self.state.undo_stack or self.state.undo_stack[-1] != txt:
            self.state.undo_stack.append(txt)
            if len(self.state.undo_stack) > 100:
                self.state.undo_stack.pop(0)

    def _compute_diff_range(self, old_text: str, new_text: str) -> tuple[int, int]:
        """Computes the character range [start, end] in new_text that changed or was restored."""
        if old_text == new_text:
            return 0, 0

        prefix_len = 0
        min_len = min(len(old_text), len(new_text))
        while prefix_len < min_len and old_text[prefix_len] == new_text[prefix_len]:
            prefix_len += 1

        suffix_len = 0
        while (
            suffix_len < (min_len - prefix_len)
            and old_text[len(old_text) - 1 - suffix_len] == new_text[len(new_text) - 1 - suffix_len]
        ):
            suffix_len += 1

        start_idx = prefix_len
        end_idx = len(new_text) - suffix_len

        if start_idx <= end_idx:
            return start_idx, end_idx
        return start_idx, start_idx

    def perform_undo(self, e=None):
        if self._undo_timer:
            self._undo_timer.cancel()
            self._undo_timer = None

        live_text = self.editor_view.get_text()
        if not self.state.undo_stack or self.state.undo_stack[-1] != live_text:
            self._push_undo_state()

        if len(self.state.undo_stack) > 1:
            self.state.is_undo_redo_op = True
            current = self.state.undo_stack.pop()
            self.state.redo_stack.append(current)
            prev_text = self.state.undo_stack[-1]
            self.state.full_content = prev_text

            start_idx, end_idx = self._compute_diff_range(current, prev_text)
            self.editor_view.set_text_with_selection(prev_text, start_idx, end_idx, focus=True)

            base_dir = (
                os.path.dirname(self.state.in_path) if self.state.in_path else None
            )
            self.preview.update_preview(prev_text, base_dir=base_dir)
            self.state.is_undo_redo_op = False

    def perform_redo(self, e=None):
        if self._undo_timer:
            self._undo_timer.cancel()
            self._undo_timer = None

        if self.state.redo_stack:
            self.state.is_undo_redo_op = True
            prev_text = self.editor_view.get_text()
            next_text = self.state.redo_stack.pop()
            if not self.state.undo_stack or self.state.undo_stack[-1] != prev_text:
                self.state.undo_stack.append(prev_text)
            self.state.undo_stack.append(next_text)
            self.state.full_content = next_text

            start_idx, end_idx = self._compute_diff_range(prev_text, next_text)
            self.editor_view.set_text_with_selection(next_text, start_idx, end_idx, focus=True)

            base_dir = (
                os.path.dirname(self.state.in_path) if self.state.in_path else None
            )
            self.preview.update_preview(next_text, base_dir=base_dir)
            self.state.is_undo_redo_op = False

    def clear_editor(self, e=None):
        # Cancel any pending autosave timer to prevent race conditions writing old text
        if self._autosave_timer:
            self._autosave_timer.cancel()
            self._autosave_timer = None

        current_text = self.editor_view.get_text()
        if current_text and current_text.strip():
            # Push current text to undo stack before clearing so user can Ctrl+Z!
            self._push_undo_state()

        self.editor_view.set_text("")
        self.state.full_content = ""
        self.state.in_path = ""
        self.state.out_path = ""
        self.state.is_dirty = False
        self.state.redo_stack.clear()
        self.state.undo_stack.append("")

        if self.preview:
            self.preview.doc_info_text.value = t("editor.doc_info", words="0", chars="0")
            try:
                self.preview.doc_info_text.update()
            except Exception:
                pass
            self.preview.update_preview("", base_dir=None)

        file_path_bar = self.app_controls.get("file_path_bar")
        if file_path_bar:
            file_path_bar.set_in_path("")
            file_path_bar.set_out_path("")

        explorer_view = self.app_controls.get("explorer_view")
        if explorer_view:
            explorer_view.set_active_file("")

        file_controller = self.app_controls.get("file_controller")
        if file_controller:
            file_controller.clear_draft_file()
