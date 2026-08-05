"""
Header Bar Layout component.
Contains App Title, Version badge, Conversion Mode, Palette, and Theme Mode selectors.
"""
from typing import Callable
import flet as ft
from src.__version__ import __version__
from src.ui_flet.constants import MODES
from src.ui_flet.theme import PALETTES


class HeaderBar:
    def __init__(
        self,
        current_mode: str,
        current_palette: str,
        current_theme_mode: str,
        on_mode_changed: Callable[[ft.ControlEvent], None],
        on_palette_changed: Callable[[ft.ControlEvent], None],
        on_theme_mode_changed: Callable[[ft.ControlEvent], None],
    ):
        self.on_mode_changed = on_mode_changed
        self.on_palette_changed = on_palette_changed
        self.on_theme_mode_changed = on_theme_mode_changed

        self.mode_dropdown = ft.Dropdown(
            label="Conversion Mode",
            value=current_mode,
            options=[ft.dropdown.Option(m) for m in MODES.keys()],
            width=180,
            dense=True,
        )
        self.mode_dropdown.on_change = self.on_mode_changed
        self.mode_dropdown.on_select = self.on_mode_changed

        self.palette_dropdown = ft.Dropdown(
            label="Palette",
            value=current_palette,
            options=[ft.dropdown.Option(p) for p in PALETTES.keys()],
            width=160,
            dense=True,
        )
        self.palette_dropdown.on_change = self.on_palette_changed
        self.palette_dropdown.on_select = self.on_palette_changed

        self.theme_mode_dropdown = ft.Dropdown(
            label="Theme",
            value=current_theme_mode,
            options=[
                ft.dropdown.Option("Dark"),
                ft.dropdown.Option("Light"),
                ft.dropdown.Option("System"),
            ],
            width=120,
            dense=True,
        )
        self.theme_mode_dropdown.on_change = self.on_theme_mode_changed
        self.theme_mode_dropdown.on_select = self.on_theme_mode_changed

        self.container = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.PRIMARY, size=24),
                    ft.Text(
                        f"DocConvert Workspace v{__version__}",
                        weight=ft.FontWeight.BOLD,
                        size=16,
                    ),
                    ft.Container(expand=True),
                    self.mode_dropdown,
                    self.palette_dropdown,
                    self.theme_mode_dropdown,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=12, top=8, right=12, bottom=8),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )

    def update_mode_options(self, input_ext: str = ""):
        if not input_ext:
            valid_modes = list(MODES.keys())
        else:
            valid_modes = [m for m, cfg in MODES.items() if cfg["in_ext"] == input_ext.lower()]
            if not valid_modes:
                valid_modes = list(MODES.keys())
        self.mode_dropdown.options = [ft.dropdown.Option(m) for m in valid_modes]
        if self.mode_dropdown.value not in valid_modes:
            self.mode_dropdown.value = valid_modes[0]
        if self.mode_dropdown.page:
            self.mode_dropdown.update()
