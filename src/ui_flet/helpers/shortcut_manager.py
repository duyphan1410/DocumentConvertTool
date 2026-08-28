"""
Global Keyboard Shortcut Manager for Flet UI.
Centralizes event routing for Ctrl+O, Ctrl+S, Ctrl+F, Ctrl+Z, Ctrl+Shift+Z, Ctrl+Y.
"""
import flet as ft
from typing import Callable, Optional


class ShortcutManager:
    @staticmethod
    def register(
        page: ft.Page,
        on_open_file: Optional[Callable] = None,
        on_save_convert: Optional[Callable] = None,
        on_find_replace: Optional[Callable] = None,
        on_undo: Optional[Callable] = None,
        on_redo: Optional[Callable] = None,
        on_toggle_sidebar: Optional[Callable] = None,
        on_quick_open: Optional[Callable] = None,
        on_new_tab: Optional[Callable] = None,
        on_close_tab: Optional[Callable] = None,
        on_next_tab: Optional[Callable] = None,
        on_prev_tab: Optional[Callable] = None,
    ):
        def _on_keyboard_event(e: ft.KeyboardEvent):
            if not e.ctrl:
                return

            key = e.key.upper()
            if key == "O":
                if on_open_file:
                    on_open_file()
            elif key == "P":
                if on_quick_open:
                    on_quick_open()
            elif key == "S":
                if on_save_convert:
                    on_save_convert()
            elif key == "F":
                if on_find_replace:
                    on_find_replace()
            elif key == "B":
                if on_toggle_sidebar:
                    on_toggle_sidebar()
            elif key == "T":
                if on_new_tab:
                    on_new_tab()
            elif key == "W":
                if on_close_tab:
                    on_close_tab()
            elif key in ("TAB", "PAGEDOWN"):
                if e.shift:
                    if on_prev_tab:
                        on_prev_tab()
                else:
                    if on_next_tab:
                        on_next_tab()
            elif key == "PAGEUP":
                if on_prev_tab:
                    on_prev_tab()
            elif key == "Z":
                if e.shift:
                    if on_redo:
                        on_redo()
                else:
                    if on_undo:
                        on_undo()
            elif key == "Y":
                if on_redo:
                    on_redo()

        page.on_keyboard_event = _on_keyboard_event

