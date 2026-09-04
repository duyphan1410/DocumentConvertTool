"""
Activity Bar Layout Component for Flet UI.
Provides a slim 48px vertical icon rail for switching sidebar panels (Explorer, Search, YouTube).
Follows Flet Desktop standards and Material Design 3 guidelines.
"""
from __future__ import annotations

from typing import Callable, Optional
import flet as ft
from src.i18n import t


class ActivityBarItem(ft.Container):
    """An individual button item on the Activity Bar with an active indicator strip."""

    def __init__(
        self,
        name: str,
        icon: str,
        tooltip: str,
        on_click: Optional[Callable[[str], None]] = None,
        is_active: bool = False,
        **kwargs,
    ):
        self.name = name
        self._tooltip = tooltip
        self._on_click_callback = on_click
        self._is_active = is_active

        self.indicator = ft.Container(
            width=3,
            height=24,
            bgcolor=ft.Colors.PRIMARY if is_active else ft.Colors.TRANSPARENT,
            border_radius=2,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

        self.spinner = ft.ProgressRing(
            width=30,
            height=30,
            stroke_width=2.0,
            color=ft.Colors.PRIMARY,
            visible=False,
        )

        self.icon_btn = ft.IconButton(
            icon=icon,
            icon_size=20,
            icon_color=ft.Colors.PRIMARY if is_active else ft.Colors.OUTLINE,
            tooltip=tooltip,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=0, top=0, right=0, bottom=0),
            ),
            on_click=self._handle_click,
        )

        self.icon_stack = ft.Stack(
            controls=[
                ft.Container(
                    content=self.spinner,
                    alignment=ft.alignment.Alignment(0.0, 0.0),
                    width=40,
                    height=40,
                ),
                self.icon_btn,
            ],
            alignment=ft.alignment.Alignment(0.0, 0.0),
        )

        super().__init__(
            content=ft.Row(
                [
                    self.indicator,
                    ft.Container(
                        content=self.icon_stack,
                        expand=True,
                        alignment=ft.alignment.Alignment(0.0, 0.0),
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=48,
            height=44,
            alignment=ft.alignment.Alignment(0.0, 0.0),
            **kwargs,
        )

    def set_loading(self, is_loading: bool):
        self.spinner.visible = is_loading
        try:
            if self.page:
                self.spinner.update()
        except Exception:
            pass

    def set_active(self, is_active: bool):
        self._is_active = is_active
        self.indicator.bgcolor = ft.Colors.PRIMARY if is_active else ft.Colors.TRANSPARENT
        self.icon_btn.icon_color = ft.Colors.PRIMARY if is_active else ft.Colors.OUTLINE
        try:
            if self.page:
                self.indicator.update()
                self.icon_btn.update()
        except Exception:
            pass

    def update_tooltip(self, text: str):
        self._tooltip = text
        self.icon_btn.tooltip = text
        try:
            if self.page:
                self.icon_btn.update()
        except Exception:
            pass

    def _handle_click(self, e):
        if self._on_click_callback:
            self._on_click_callback(self.name)


class ActivityBar(ft.Container):
    """
    Slim 48px vertical rail hosting Explorer, Search, and YouTube tool actions.
    """

    def __init__(
        self,
        on_tab_selected: Optional[Callable[[str], None]] = None,
        active_tab: str = "explorer",
        **kwargs,
    ):
        self._on_tab_selected = on_tab_selected
        self._active_tab = active_tab

        self.item_home = ActivityBarItem(
            name="home",
            icon=ft.Icons.HOME_ROUNDED,
            tooltip=t("welcome.btn_home"),
            on_click=self._handle_item_click,
            is_active=False,
        )
        self.item_explorer = ActivityBarItem(
            name="explorer",
            icon=ft.Icons.FOLDER_COPY_OUTLINED,
            tooltip=t("activity_bar.explorer"),
            on_click=self._handle_item_click,
            is_active=(active_tab == "explorer"),
        )
        self.item_search = ActivityBarItem(
            name="search",
            icon=ft.Icons.SEARCH_ROUNDED,
            tooltip=t("activity_bar.search"),
            on_click=self._handle_item_click,
            is_active=(active_tab == "search"),
        )
        self.item_youtube = ActivityBarItem(
            name="youtube",
            icon=ft.Icons.SMART_DISPLAY_OUTLINED,
            tooltip=t("activity_bar.youtube"),
            on_click=self._handle_item_click,
            is_active=(active_tab == "youtube"),
        )

        self._items = {
            "home": self.item_home,
            "explorer": self.item_explorer,
            "search": self.item_search,
            "youtube": self.item_youtube,
        }

        self.top_column = ft.Column(
            [
                self.item_home,
                self.item_explorer,
                self.item_search,
                self.item_youtube,
            ],
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        super().__init__(
            content=ft.Column(
                [
                    self.top_column,
                    ft.Container(expand=True),
                ],
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=48,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border=ft.Border(
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            ),
            padding=ft.Padding(left=0, top=6, right=0, bottom=6),
            **kwargs,
        )

    def set_active_tab(self, tab_name: str, is_open: bool = True):
        """Update active highlight on ActivityBar icons."""
        self._active_tab = tab_name if is_open else ""
        for name, item in self._items.items():
            item.set_active(name == self._active_tab if is_open else False)

    def set_item_loading(self, item_name: str, is_loading: bool):
        """Toggle animated spinner on an ActivityBar item."""
        item = self._items.get(item_name)
        if item:
            item.set_loading(is_loading)

    def get_active_tab(self) -> str:
        return self._active_tab

    def _handle_item_click(self, tab_name: str):
        if self._on_tab_selected:
            self._on_tab_selected(tab_name)

    def update_border_side(self, is_left: bool):
        """Adjust border to right side when on left, or left side when on right."""
        if is_left:
            self.border = ft.Border(right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT))
        else:
            self.border = ft.Border(left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT))
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def update_locale(self):
        """Refresh tooltips when language changes."""
        self.item_home.update_tooltip(t("welcome.btn_home"))
        self.item_explorer.update_tooltip(t("activity_bar.explorer"))
        self.item_search.update_tooltip(t("activity_bar.search"))
        self.item_youtube.update_tooltip(t("activity_bar.youtube"))
