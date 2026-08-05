"""
Welcome / Onboarding Dashboard View for Flet UI.
Displayed in the workspace center when no document or draft is currently loaded.
"""
import os
import flet as ft
from typing import Callable, Optional
from src.ui_flet.theme import resolve_color, make_border


class WelcomeView(ft.Container):
    def __init__(
        self,
        on_open_file: Optional[Callable] = None,
        on_create_blank: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.on_open_file = on_open_file
        self.on_create_blank = on_create_blank

        self.expand = True
        self.alignment = ft.alignment.Alignment(0.0, 0.0)
        self.padding = 20

        self.icon_logo = ft.Icon(
            ft.Icons.DESCRIPTION_ROUNDED,
            color=ft.Colors.PRIMARY,
            size=56,
        )
        self.title_text = ft.Text(
            "Welcome to DocConvert Workspace",
            size=24,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        self.subtitle_text = ft.Text(
            "Convert and edit Markdown, Word, Excel, PDF, CSV, and HTML seamlessly",
            size=14,
            color=ft.Colors.GREY_400,
            text_align=ft.TextAlign.CENTER,
        )

        self.btn_open = ft.ElevatedButton(
            "Open Document",
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            height=46,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=20, top=10, right=20, bottom=10),
            ),
            on_click=self._on_open_click,
        )

        self.btn_blank = ft.OutlinedButton(
            "Create Blank Note",
            icon=ft.Icons.NOTE_ADD_OUTLINED,
            height=46,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=18, top=10, right=18, bottom=10),
            ),
            on_click=self._on_blank_click,
        )

        self.card_container = ft.Container(
            content=ft.Column(
                controls=[
                    self.icon_logo,
                    self.title_text,
                    self.subtitle_text,
                    ft.Container(height=10),
                    ft.Row(
                        controls=[self.btn_open, self.btn_blank],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=14,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            ),
            width=540,
            padding=32,
            border_radius=14,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        )

        self.content = self.card_container

    def _on_open_click(self, e):
        if self.on_open_file:
            self.on_open_file(e)

    def _on_blank_click(self, e):
        if self.on_create_blank:
            self.on_create_blank(e)

    def apply_palette(self, palette: dict, is_dark: bool):
        accent_primary = resolve_color(palette, "text_accent_primary", is_dark)
        bg_component = resolve_color(palette, "bg_component", is_dark)
        border_color = resolve_color(palette, "border_color", is_dark)

        self.icon_logo.color = accent_primary
        self.btn_open.bgcolor = accent_primary
        self.btn_open.color = ft.Colors.WHITE
        self.btn_blank.color = accent_primary
        self.btn_blank.border_side = ft.BorderSide(1, accent_primary)

        self.card_container.bgcolor = bg_component
        self.card_container.border = make_border(1, border_color)

        try:
            self.update()
        except Exception:
            pass
