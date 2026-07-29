"""
Footer Bar Layout component.
Contains Convert Action button, Open File/Folder buttons, Progress bar, and Status console.
"""
from typing import Callable
import flet as ft


class FooterBar:
    def __init__(
        self,
        on_convert_clicked: Callable[[ft.ControlEvent], None],
        on_open_file: Callable[[ft.ControlEvent], None],
        on_open_folder: Callable[[ft.ControlEvent], None],
    ):
        self.on_convert_clicked = on_convert_clicked
        self.on_open_file = on_open_file
        self.on_open_folder = on_open_folder

        self.btn_convert = ft.ElevatedButton(
            "CONVERT NOW",
            icon=ft.Icons.TRANSFORM,
            on_click=self.on_convert_clicked,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=24, top=16, right=24, bottom=16),
                color=ft.Colors.WHITE,
            ),
        )
        self.btn_open_file = ft.ElevatedButton(
            "Open File",
            icon=ft.Icons.OPEN_IN_NEW,
            visible=False,
            on_click=self.on_open_file,
        )
        self.btn_open_folder = ft.ElevatedButton(
            "Open Folder",
            icon=ft.Icons.FOLDER_OPEN,
            visible=False,
            on_click=self.on_open_folder,
        )
        self.btn_copy_error = ft.ElevatedButton(
            "Copy Error",
            icon=ft.Icons.COPY,
            visible=False,
            style=ft.ButtonStyle(color=ft.Colors.RED_400),
            on_click=self._on_copy_error,
        )
        self.progress_bar = ft.ProgressBar(visible=False, expand=True)
        self.status_text = ft.Text("Ready", size=13)

        self.container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            self.btn_convert,
                            self.btn_open_file,
                            self.btn_open_folder,
                            self.btn_copy_error,
                            self.status_text,
                            self.progress_bar,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                ]
            ),
            padding=ft.Padding(left=12, top=8, right=12, bottom=8),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )

    def _on_copy_error(self, e):
        if self.container.page:
            self.container.page.set_clipboard(self.status_text.value or "")
            self.set_status("Error copied to clipboard!", ft.Colors.GREEN_400)

    def set_status(self, text: str, color=None, is_error: bool = False):
        self.status_text.value = text
        if color:
            self.status_text.color = color

        # Show Copy Error button ONLY when status is an error
        is_err = is_error or (color in (ft.Colors.RED_400, ft.Colors.RED, "#f44336", "#ef5350"))
        self.btn_copy_error.visible = is_err
        if self.btn_copy_error.page:
            self.btn_copy_error.update()

        if self.status_text.page:
            self.status_text.update()

    def set_processing(self, is_processing: bool):
        self.progress_bar.visible = is_processing
        self.btn_convert.disabled = is_processing
        if self.progress_bar.page:
            self.progress_bar.update()
        if self.btn_convert.page:
            self.btn_convert.update()

    def set_result_buttons_visible(self, visible: bool):
        self.btn_open_file.visible = visible
        self.btn_open_folder.visible = visible
        if self.btn_open_file.page:
            self.btn_open_file.update()
        if self.btn_open_folder.page:
            self.btn_open_folder.update()
