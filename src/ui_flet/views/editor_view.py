"""
Editor Workspace View component for editing document text content.
"""
from typing import Callable
import flet as ft
from src.ui_flet.theme import STYLE
from src.ui_flet.components.search_replace_bar import SearchReplaceBar


class EditorView:
    def __init__(
        self,
        search_replace_bar: SearchReplaceBar,
        on_editor_changed: Callable[[ft.ControlEvent], None],
        on_toggle_search: Callable[[ft.ControlEvent], None],
        on_undo: Callable[[ft.ControlEvent], None],
        on_redo: Callable[[ft.ControlEvent], None],
        on_clear: Callable[[ft.ControlEvent], None],
    ):
        self.search_replace_bar = search_replace_bar
        self.on_editor_changed = on_editor_changed
        self.on_toggle_search = on_toggle_search
        self.on_undo = on_undo
        self.on_redo = on_redo
        self.on_clear = on_clear

        self.btn_toggle_search = ft.IconButton(
            ft.Icons.SEARCH,
            tooltip="Toggle Search & Replace Panel",
            on_click=self.on_toggle_search,
        )
        self.btn_undo = ft.IconButton(
            ft.Icons.UNDO,
            tooltip="Undo (Ctrl+Z)",
            on_click=self.on_undo,
        )
        self.btn_redo = ft.IconButton(
            ft.Icons.REDO,
            tooltip="Redo (Ctrl+Y)",
            on_click=self.on_redo,
        )
        self.btn_clear_editor = ft.IconButton(
            ft.Icons.DELETE_SWEEP,
            tooltip="Clear Editor",
            on_click=self.on_clear,
        )

        self.toolbar = ft.Row(
            controls=[
                ft.Text("Editor Buffer", weight=ft.FontWeight.W_600),
                ft.Container(expand=True),
                self.btn_toggle_search,
                self.btn_undo,
                self.btn_redo,
                self.btn_clear_editor,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.editor = ft.TextField(
            multiline=True,
            expand=True,
            min_lines=18,
            text_style=ft.TextStyle(font_family=STYLE["font_family_mono"]),
            text_size=13,
            on_change=self.on_editor_changed,
            hint_text="Document text content will appear here...",
        )

        self.container = ft.Container(
            content=ft.Column(
                controls=[
                    self.toolbar,
                    self.search_replace_bar.container,
                    self.editor,
                ],
                expand=True,
            ),
            expand=True,
            padding=10,
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        )

    def get_text(self) -> str:
        return self.editor.value or ""

    def set_loading(self, filename: str = ""):
        name_str = f"'{filename}'" if filename else "document"
        self.editor.value = f"⏳ Loading {name_str}, please wait..."
        self.editor.read_only = True
        if self.editor.page:
            self.editor.update()

    def set_text(self, text: str):
        self.editor.value = text
        self.editor.read_only = False
        if self.editor.page:
            self.editor.update()
