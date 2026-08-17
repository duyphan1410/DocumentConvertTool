"""
Theme Controller for Flet UI.
Manages color palettes, theme modes (Light/Dark/System), control theme updates, and Win32 OS title bar sync.
"""
import flet as ft
from src.ui_flet.state import AppState
from src.ui_flet.theme import PALETTES, apply_theme, resolve_color, make_border, is_theme_dark


class ThemeController:
    def __init__(self, page: ft.Page, state: AppState, app_controls: dict):
        self.page = page
        self.state = state
        self.app_controls = app_controls

    def on_palette_changed(self, e=None):
        ribbon_bar = self.app_controls.get("ribbon_bar")
        if ribbon_bar:
            self.state.current_palette = ribbon_bar.palette_dropdown.value
        apply_theme(
            self.page, self.state.current_palette, self.state.current_theme_mode
        )
        self.update_theme_colors()

    def on_theme_mode_changed(self, e=None):
        ribbon_bar = self.app_controls.get("ribbon_bar")
        if ribbon_bar:
            self.state.current_theme_mode = ribbon_bar.theme_mode_dropdown.value
        apply_theme(
            self.page, self.state.current_palette, self.state.current_theme_mode
        )
        self.update_theme_colors()

    def toggle_theme_quick(self, e=None):
        new_mode = "Dark" if self.state.current_theme_mode == "Light" else "Light"
        self.state.current_theme_mode = new_mode
        ribbon_bar = self.app_controls.get("ribbon_bar")
        if ribbon_bar:
            ribbon_bar.theme_mode_dropdown.value = new_mode
        apply_theme(self.page, self.state.current_palette, new_mode)
        self.update_theme_colors()

    def update_theme_colors(self):
        palette = PALETTES.get(
            self.state.current_palette, PALETTES["Violet Cyberpunk"]
        )
        is_dark = is_theme_dark(self.state.current_theme_mode)

        ribbon_bar = self.app_controls.get("ribbon_bar")
        file_path_bar = self.app_controls.get("file_path_bar")
        welcome_view = self.app_controls.get("welcome_view")
        editor_view = self.app_controls.get("editor_view")
        preview = self.app_controls.get("preview")
        right_pane = self.app_controls.get("right_pane")
        footer_bar = self.app_controls.get("footer_bar")
        settings_view = self.app_controls.get("settings_view")
        help_view = self.app_controls.get("help_view")

        if ribbon_bar:
            ribbon_bar.apply_palette(palette, is_dark)
        if file_path_bar:
            file_path_bar.apply_palette(palette, is_dark)
        if welcome_view:
            welcome_view.apply_palette(palette, is_dark)
        if editor_view:
            editor_view.apply_palette(palette, is_dark)

        if right_pane and preview:
            bg_pure_dark = resolve_color(palette, "bg_pure_dark", is_dark)
            border = resolve_color(palette, "border_color", is_dark)
            right_pane.bgcolor = bg_pure_dark
            right_pane.border = make_border(1, border)
            preview.apply_palette(palette, is_dark, self.state.current_palette)

        if footer_bar:
            footer_bar.apply_palette(palette, is_dark)

        if settings_view:
            settings_view.apply_palette(palette, is_dark)

        if help_view:
            help_view.apply_palette(palette, is_dark)

        try:
            self.page.update()
        except Exception:
            pass

