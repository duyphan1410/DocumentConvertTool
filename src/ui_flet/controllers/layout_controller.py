"""
Layout Controller for Flet UI.
Manages panel visibility toggles (Preview pane, File path bar, Editor panel, Status bar) and editor dynamic height math.
"""
import flet as ft
from src.ui_flet.state import AppState
from src.utils.settings_store import save_settings


class LayoutController:
    def __init__(self, page: ft.Page, state: AppState, app_controls: dict):
        self.page = page
        self.state = state
        self.app_controls = app_controls

    def apply_panel_visibility(self):
        """Restore panel visibilities from AppState."""
        right_pane = self.app_controls.get("right_pane")
        if right_pane:
            right_pane.visible = getattr(self.state, "show_preview", True)

        file_path_bar = self.app_controls.get("file_path_bar")
        if file_path_bar and hasattr(file_path_bar, "container"):
            file_path_bar.container.visible = getattr(self.state, "show_path_bar", True)

        footer_bar = self.app_controls.get("footer_bar")
        if footer_bar and hasattr(footer_bar, "container"):
            footer_bar.container.visible = getattr(self.state, "show_status_bar", True)

        self.update_editor_dynamic_height()
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def update_editor_dynamic_height(self):
        file_path_bar = self.app_controls.get("file_path_bar")
        footer_bar = self.app_controls.get("footer_bar")
        ribbon_bar = self.app_controls.get("ribbon_bar")
        editor_view = self.app_controls.get("editor_view")

        if not editor_view:
            return

        file_path_vis = (
            file_path_bar.container.visible if file_path_bar else True
        )
        status_vis = footer_bar.container.visible if footer_bar else True
        ribbon_vis = ribbon_bar.is_expanded if ribbon_bar else True

        lines = 20
        if not file_path_vis:
            lines += 4
        if not status_vis:
            lines += 3
        if not ribbon_vis:
            lines += 3

        editor_view.set_min_lines(lines)

    def _safe_save_settings(self):
        """Persist settings, but skip if Settings tab has unsaved (unapplied) changes
        to avoid leaking dirty state (e.g. unapplied palette) via panel toggles."""
        settings_view = self.app_controls.get("settings_view")
        if getattr(settings_view, "_is_dirty", False):
            print("[DEBUG] LayoutController: skip save_settings, settings_view is dirty")
            return
        save_settings(self.state)

    def toggle_preview_pane(self, e=None):
        right_pane = self.app_controls.get("right_pane")
        if right_pane:
            right_pane.visible = not right_pane.visible
            self.state.show_preview = right_pane.visible
            self._safe_save_settings()
            try:
                self.page.update()
            except Exception:
                pass

    def toggle_file_path_bar(self, e=None):
        file_path_bar = self.app_controls.get("file_path_bar")
        if file_path_bar:
            file_path_bar.container.visible = not file_path_bar.container.visible
            self.state.show_path_bar = file_path_bar.container.visible
            self.update_editor_dynamic_height()
            self._safe_save_settings()
            try:
                self.page.update()
            except Exception:
                pass

    def toggle_editor_panel(self, e=None):
        editor_view = self.app_controls.get("editor_view")
        if editor_view:
            editor_view.container.visible = not editor_view.container.visible
            try:
                self.page.update()
            except Exception:
                pass

    def toggle_status_bar(self, e=None):
        footer_bar = self.app_controls.get("footer_bar")
        if footer_bar:
            footer_bar.container.visible = not footer_bar.container.visible
            self.state.show_status_bar = footer_bar.container.visible
            self.update_editor_dynamic_height()
            self._safe_save_settings()
            try:
                self.page.update()
            except Exception:
                pass

