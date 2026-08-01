"""
Editor & Formatting Controller for Flet UI.
Decouples editor text changes, Undo/Redo stack management, formatting shortcuts, and clear operations.
"""
import os
import threading
import flet as ft
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
        self.editor_view.apply_formatting(prefix, suffix)

    def on_heading_change(self, level: int):
        self.editor_view.apply_heading(level)

    def on_editor_changed(self, e=None, file_controller=None):
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
        self.preview.doc_info_text.value = f"{words:,} words | {chars:,} chars"
        if self.preview.doc_info_text.page:
            try:
                self.preview.doc_info_text.update()
            except Exception:
                pass

        base_dir = (
            os.path.dirname(self.state.in_path) if self.state.in_path else None
        )
        self.preview.update_preview(current_text, base_dir=base_dir)

        if file_controller:
            if self._autosave_timer:
                self._autosave_timer.cancel()
            self._autosave_timer = threading.Timer(
                2.0, file_controller.perform_autosave
            )
            self._autosave_timer.start()

    def _push_undo_state(self):
        txt = self.editor_view.get_text()
        if not self.state.undo_stack or self.state.undo_stack[-1] != txt:
            self.state.undo_stack.append(txt)
            if len(self.state.undo_stack) > 100:
                self.state.undo_stack.pop(0)

    def perform_undo(self, e=None):
        if len(self.state.undo_stack) > 1:
            self.state.is_undo_redo_op = True
            current = self.state.undo_stack.pop()
            self.state.redo_stack.append(current)
            prev_text = self.state.undo_stack[-1]
            self.editor_view.set_text(prev_text)
            self.state.full_content = prev_text
            base_dir = (
                os.path.dirname(self.state.in_path) if self.state.in_path else None
            )
            self.preview.update_preview(prev_text, base_dir=base_dir)
            self.state.is_undo_redo_op = False

    def perform_redo(self, e=None):
        if self.state.redo_stack:
            self.state.is_undo_redo_op = True
            next_text = self.state.redo_stack.pop()
            self.state.undo_stack.append(next_text)
            self.editor_view.set_text(next_text)
            self.state.full_content = next_text
            base_dir = (
                os.path.dirname(self.state.in_path) if self.state.in_path else None
            )
            self.preview.update_preview(next_text, base_dir=base_dir)
            self.state.is_undo_redo_op = False

    def clear_editor(self, e=None):
        """
        Clears editor text buffer.
        FIX: Preserves Undo history so clearing text can be UNDONE via Ctrl+Z!
        """
        current_text = self.editor_view.get_text()
        if current_text and current_text.strip():
            # Push current text to undo stack before clearing so user can Ctrl+Z!
            self._push_undo_state()

        self.editor_view.set_text("")
        self.state.full_content = ""
        self.state.redo_stack.clear()
        self.state.undo_stack.append("")

        self.preview.doc_info_text.value = "0 words | 0 chars"
        if self.preview.doc_info_text.page:
            try:
                self.preview.doc_info_text.update()
            except Exception:
                pass
        self.preview.update_preview(
            "", base_dir=os.path.dirname(self.state.in_path) if self.state.in_path else None
        )
