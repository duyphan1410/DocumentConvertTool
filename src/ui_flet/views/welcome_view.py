"""
Welcome / Onboarding Dashboard View for Flet UI.
Displayed in the workspace center when no document or draft is currently loaded.
"""
import os
import flet as ft
from typing import Callable, Optional
from src.i18n import t
from src.ui_flet.theme import resolve_color, make_border


class WelcomeActionCard(ft.Container):
    """An interactive card representing a primary workspace action."""

    def __init__(
        self,
        icon: str,
        title_key: str,
        desc_key: str,
        shortcut: Optional[str] = None,
        on_click: Optional[Callable] = None,
        icon_color: Optional[str] = None,
        **kwargs,
    ):
        self.title_key = title_key
        self.desc_key = desc_key
        self.shortcut = shortcut
        self._action_callback = on_click
        self._custom_icon_color = icon_color

        self.icon_widget = ft.Icon(
            icon,
            size=26,
            color=icon_color or ft.Colors.PRIMARY,
        )
        self.icon_badge = ft.Container(
            content=self.icon_widget,
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
            padding=ft.Padding(left=10, top=10, right=10, bottom=10),
            border_radius=12,
            alignment=ft.alignment.Alignment(0.0, 0.0),
        )

        self.title_text = ft.Text(
            t(title_key),
            size=14,
            weight=ft.FontWeight.BOLD,
        )

        self.desc_text = ft.Text(
            t(desc_key),
            size=11,
            color=ft.Colors.OUTLINE,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        title_children = [self.title_text]
        if shortcut:
            self.badge_shortcut = ft.Container(
                content=ft.Text(
                    shortcut,
                    size=9,
                    font_family="Consolas",
                    weight=ft.FontWeight.BOLD,
                ),
                bgcolor=ft.Colors.PRIMARY_CONTAINER,
                padding=ft.Padding(left=6, top=2, right=6, bottom=2),
                border_radius=4,
                border=ft.Border(
                    left=ft.BorderSide(1, ft.Colors.PRIMARY),
                    top=ft.BorderSide(1, ft.Colors.PRIMARY),
                    right=ft.BorderSide(1, ft.Colors.PRIMARY),
                    bottom=ft.BorderSide(1, ft.Colors.PRIMARY),
                ),
            )
            title_children.append(self.badge_shortcut)

        title_row = ft.Row(
            title_children,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        text_column = ft.Column(
            [title_row, self.desc_text],
            spacing=3,
            expand=True,
        )

        card_content = ft.Row(
            [self.icon_badge, text_column],
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        super().__init__(
            content=card_content,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            padding=ft.Padding(left=16, top=14, right=16, bottom=14),
            border_radius=12,
            border=ft.Border(
                left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            ),
            ink=True,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            on_click=self._handle_click,
            on_hover=self._handle_hover,
            expand=True,
            **kwargs,
        )

    def _handle_click(self, e):
        if self._action_callback:
            self._action_callback(e)

    def _handle_hover(self, e):
        is_hovered = e.data == "true"
        if is_hovered:
            self.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGHEST
            self.border = ft.Border(
                left=ft.BorderSide(1, ft.Colors.PRIMARY),
                top=ft.BorderSide(1, ft.Colors.PRIMARY),
                right=ft.BorderSide(1, ft.Colors.PRIMARY),
                bottom=ft.BorderSide(1, ft.Colors.PRIMARY),
            )
        else:
            self.bgcolor = ft.Colors.SURFACE_CONTAINER
            self.border = ft.Border(
                left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            )
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def update_locale(self):
        self.title_text.value = t(self.title_key)
        self.desc_text.value = t(self.desc_key)

    def apply_palette(self, accent_primary: str):
        if not self._custom_icon_color:
            self.icon_widget.color = accent_primary
        if hasattr(self, "badge_shortcut") and self.badge_shortcut:
            self.badge_shortcut.border = ft.Border(
                left=ft.BorderSide(1, accent_primary),
                top=ft.BorderSide(1, accent_primary),
                right=ft.BorderSide(1, accent_primary),
                bottom=ft.BorderSide(1, accent_primary),
            )


class WelcomeView(ft.Container):
    def __init__(
        self,
        on_open_file: Optional[Callable] = None,
        on_open_folder: Optional[Callable] = None,
        on_create_blank: Optional[Callable] = None,
        on_import_youtube: Optional[Callable] = None,
        on_open_help: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.on_open_file = on_open_file
        self.on_open_folder = on_open_folder
        self.on_create_blank = on_create_blank
        self.on_import_youtube = on_import_youtube
        self.on_open_help = on_open_help

        self.expand = True
        self.alignment = ft.alignment.Alignment(0.0, 0.0)
        self.padding = ft.Padding(left=20, top=20, right=20, bottom=20)

        # ── 1. Hero Badge & Branding (Fixed Size Logo) ───────────────────────
        self.icon_logo = ft.Icon(
            ft.Icons.DESCRIPTION_ROUNDED,
            color=ft.Colors.PRIMARY,
            size=36,
        )
        self.logo_badge = ft.Container(
            content=self.icon_logo,
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
            width=64,
            height=64,
            border_radius=18,
            alignment=ft.alignment.Alignment(0.0, 0.0),
        )

        self.title_text = ft.Text(
            t("welcome.title"),
            size=22,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        self.subtitle_text = ft.Text(
            t("welcome.subtitle"),
            size=13,
            color=ft.Colors.OUTLINE,
            text_align=ft.TextAlign.CENTER,
        )

        # ── 2. Primary Action Cards (2x2 Grid) ────────────────────────────────
        self.card_open_file = WelcomeActionCard(
            icon=ft.Icons.FILE_OPEN_ROUNDED,
            title_key="welcome.btn_open",
            desc_key="welcome.desc_open",
            shortcut="Ctrl + O",
            on_click=lambda e: self._on_open_click(e),
        )

        self.card_open_folder = WelcomeActionCard(
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            title_key="welcome.btn_open_folder",
            desc_key="welcome.desc_open_folder",
            shortcut="Ctrl + B",
            on_click=lambda e: self._on_open_folder_click(e),
        )

        self.card_blank = WelcomeActionCard(
            icon=ft.Icons.NOTE_ADD_ROUNDED,
            title_key="welcome.btn_blank",
            desc_key="welcome.desc_blank",
            on_click=lambda e: self._on_blank_click(e),
        )

        self.card_youtube = WelcomeActionCard(
            icon=ft.Icons.SMART_DISPLAY_ROUNDED,
            title_key="welcome.btn_youtube",
            desc_key="welcome.desc_youtube",
            on_click=lambda e: self._on_youtube_click(e),
        )

        self.cards_list = [
            self.card_open_file,
            self.card_open_folder,
            self.card_blank,
            self.card_youtube,
        ]

        # ── 3. Quick Help CTA ────────────────────────────────────────────────
        self.btn_help = ft.TextButton(
            t("welcome.btn_help"),
            icon=ft.Icons.HELP_OUTLINE_ROUNDED,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(left=12, top=8, right=12, bottom=8),
            ),
            on_click=self._on_help_click,
        )

        # ── 4. Main Card Container ───────────────────────────────────────────
        self.card_container = ft.Container(
            content=ft.Column(
                controls=[
                    self.logo_badge,
                    self.title_text,
                    self.subtitle_text,
                    ft.Container(height=8),
                    ft.Row(
                        controls=[self.card_open_file, self.card_open_folder],
                        spacing=12,
                    ),
                    ft.Row(
                        controls=[self.card_blank, self.card_youtube],
                        spacing=12,
                    ),
                    ft.Container(height=4),
                    self.btn_help,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            ),
            width=700,
            padding=ft.Padding(left=32, top=28, right=32, bottom=20),
            border_radius=16,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border=ft.Border(
                left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            ),
        )

        self.content = self.card_container

    def _on_open_click(self, e):
        if self.on_open_file:
            self.on_open_file(e)

    def _on_open_folder_click(self, e):
        if self.on_open_folder:
            self.on_open_folder(e)

    def _on_blank_click(self, e):
        if self.on_create_blank:
            self.on_create_blank(e)

    def _on_youtube_click(self, e):
        if self.on_import_youtube:
            self.on_import_youtube(e)

    def _on_help_click(self, e):
        if self.on_open_help:
            self.on_open_help(e)

    def update_locale(self):
        """Refresh all text to current locale."""
        self.title_text.value = t("welcome.title")
        self.subtitle_text.value = t("welcome.subtitle")
        self.btn_help.content = t("welcome.btn_help")

        for card in self.cards_list:
            card.update_locale()

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
        self.btn_help.color = accent_primary

        for card in self.cards_list:
            card.apply_palette(accent_primary)

        self.card_container.bgcolor = bg_component
        self.card_container.border = make_border(1, border_color)

        try:
            if self.page:
                self.update()
        except Exception:
            pass
