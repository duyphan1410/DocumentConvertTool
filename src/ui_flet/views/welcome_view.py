"""
Welcome / Onboarding Dashboard View for Flet UI.
Displayed in the workspace center when no document or draft is currently loaded.
"""
import os
import flet as ft
from typing import Callable, Optional
from src.i18n import t
from src.ui_flet.theme import resolve_color, make_border


class WelcomeView(ft.Container):
    def __init__(
        self,
        on_open_file: Optional[Callable] = None,
        on_create_blank: Optional[Callable] = None,
        on_import_youtube: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.on_open_file = on_open_file
        self.on_create_blank = on_create_blank
        self.on_import_youtube = on_import_youtube

        self.expand = True
        self.alignment = ft.alignment.Alignment(0.0, 0.0)
        self.padding = 20

        self.icon_logo = ft.Icon(
            ft.Icons.DESCRIPTION_ROUNDED,
            color=ft.Colors.PRIMARY,
            size=56,
        )
        self.title_text = ft.Text(
            t("welcome.title"),
            size=24,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        self.subtitle_text = ft.Text(
            t("welcome.subtitle"),
            size=14,
            color=ft.Colors.GREY_400,
            text_align=ft.TextAlign.CENTER,
        )

        self.btn_open = ft.ElevatedButton(
            t("welcome.btn_open"),
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            height=44,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=16, top=10, right=16, bottom=10),
            ),
            on_click=self._on_open_click,
        )

        self.btn_blank = ft.OutlinedButton(
            t("welcome.btn_blank"),
            icon=ft.Icons.NOTE_ADD_OUTLINED,
            height=44,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=16, top=10, right=16, bottom=10),
            ),
            on_click=self._on_blank_click,
        )

        self.btn_youtube = ft.OutlinedButton(
            t("welcome.btn_youtube"),
            icon=ft.Icons.PLAY_CIRCLE_OUTLINE_ROUNDED,
            height=44,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=16, top=10, right=16, bottom=10),
            ),
            on_click=self._on_youtube_click,
        )

        self.card_container = ft.Container(
            content=ft.Column(
                controls=[
                    self.icon_logo,
                    self.title_text,
                    self.subtitle_text,
                    ft.Container(height=10),
                    ft.Row(
                        controls=[self.btn_open, self.btn_blank, self.btn_youtube],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=12,
                        wrap=True,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            ),
            width=580,
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

    def _on_youtube_click(self, e):
        if self.on_import_youtube:
            self.on_import_youtube(e)

    def update_locale(self):
        """Refresh all text to current locale."""
        self.title_text.value = t("welcome.title")
        self.subtitle_text.value = t("welcome.subtitle")
        self.btn_open.content = t("welcome.btn_open")
        self.btn_blank.content = t("welcome.btn_blank")
        self.btn_youtube.content = t("welcome.btn_youtube")
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def apply_palette(self, palette: dict, is_dark: bool):
        accent_primary = resolve_color(palette, "text_accent_primary", is_dark)
        bg_component = resolve_color(palette, "bg_component", is_dark)
        border_color = resolve_color(palette, "border_color", is_dark)

        self.icon_logo.color = accent_primary
        self.btn_open.bgcolor = accent_primary
        self.btn_open.color = ft.Colors.WHITE
        self.btn_blank.color = accent_primary
        self.btn_blank.border_side = ft.BorderSide(1, accent_primary)
        self.btn_youtube.color = accent_primary
        self.btn_youtube.border_side = ft.BorderSide(1, accent_primary)

        self.card_container.bgcolor = bg_component
        self.card_container.border = make_border(1, border_color)

        try:
            self.update()
        except Exception:
            pass

