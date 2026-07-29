"""
File Path Bar component for selecting input document and destination output paths.
"""
from typing import Callable
import flet as ft


class FilePathBar:
    def __init__(
        self,
        on_browse_in: Callable[[ft.ControlEvent], None],
        on_browse_out: Callable[[ft.ControlEvent], None],
        on_out_path_changed: Callable[[ft.ControlEvent], None],
    ):
        self.on_browse_in = on_browse_in
        self.on_browse_out = on_browse_out
        self.on_out_path_changed = on_out_path_changed

        self.in_path_text = ft.TextField(
            label="Input File Path",
            value="",
            read_only=True,
            expand=True,
            dense=True,
        )
        self.btn_browse_in = ft.ElevatedButton(
            "Browse Input",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self.on_browse_in,
        )

        self.out_path_text = ft.TextField(
            label="Output Destination",
            value="",
            expand=True,
            dense=True,
            on_change=self.on_out_path_changed,
        )
        self.btn_browse_out = ft.ElevatedButton(
            "Select Output",
            icon=ft.Icons.SAVE,
            on_click=self.on_browse_out,
        )

        self.container = ft.Column(
            controls=[
                ft.Row(controls=[self.in_path_text, self.btn_browse_in]),
                ft.Row(controls=[self.out_path_text, self.btn_browse_out]),
            ],
            spacing=6,
        )

    def set_in_path(self, path: str):
        self.in_path_text.value = path
        if self.in_path_text.page:
            self.in_path_text.update()

    def set_out_path(self, path: str):
        self.out_path_text.value = path
        if self.out_path_text.page:
            self.out_path_text.update()

    def set_out_label(self, label: str):
        self.out_path_text.label = label
        if self.out_path_text.page:
            self.out_path_text.update()

    def set_in_label(self, label: str):
        self.in_path_text.label = label
        if self.in_path_text.page:
            self.in_path_text.update()
