"""
Global Keyboard Shortcut Manager for Flet UI.
Centralizes event routing for Ctrl+O, Ctrl+F, etc.
"""
import flet as ft
from typing import Callable, Optional


class ShortcutManager:
    @staticmethod
    def register(page: ft.Page, on_open_file: Optional[Callable] = None):
        def _on_keyboard_event(e: ft.KeyboardEvent):
            if e.ctrl and e.key.upper() == "O":
                if on_open_file:
                    on_open_file()

        page.on_keyboard_event = _on_keyboard_event
