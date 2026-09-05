"""
Workspace Manager View component for Flet UI.
Houses WelcomeView, Editor Workspace, SettingsView, and HelpView in a unified container.
"""
import flet as ft
from src.ui_flet.views.welcome_view import WelcomeView


class WorkspaceView(ft.Container):
    def __init__(
        self,
        welcome_view: WelcomeView,
        editor_workspace: ft.Row,
        loading_view=None,
        settings_view=None,
        help_view=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.welcome_view = welcome_view
        self.editor_workspace = editor_workspace
        self.loading_view = loading_view
        self.settings_view = settings_view
        self.help_view = help_view

        self.expand = True
        self.content = self.welcome_view

    def show_loading(self, message: str = ""):
        """Switch workspace to LoadingView."""
        if self.loading_view:
            if message:
                self.loading_view.set_message(message)
            if hasattr(self.loading_view, "update_locale"):
                self.loading_view.update_locale()
            self.content = self.loading_view
            try:
                if self.page:
                    self.page.update()
            except Exception:
                pass

    def show_welcome(self, ribbon_bar=None):
        if hasattr(self.welcome_view, "refresh_history"):
            self.welcome_view.refresh_history(silent=True)
        if hasattr(self.welcome_view, "update_locale"):
            self.welcome_view.update_locale()
        self.content = self.welcome_view
        if ribbon_bar:
            try:
                ribbon_bar.deselect_all_tabs()
            except Exception:
                pass
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def show_editor(self, ribbon_bar=None, auto_select_edit: bool = True):
        # Update controls in editor_workspace
        if hasattr(self.editor_workspace, "controls"):
            for ctrl in self.editor_workspace.controls:
                if hasattr(ctrl, "update_locale"):
                    ctrl.update_locale()
                elif hasattr(ctrl, "content") and hasattr(ctrl.content, "update_locale"):
                    ctrl.content.update_locale()
        self.content = self.editor_workspace
        if auto_select_edit and ribbon_bar:
            try:
                ribbon_bar.select_tab("edit", force=True)
            except Exception:
                pass
        elif ribbon_bar and getattr(ribbon_bar, "active_tab", None) in ("settings", "help"):
            try:
                ribbon_bar.active_tab = "edit"
                ribbon_bar._update_tab_highlights()
            except Exception:
                pass
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def show_settings(self, ribbon_bar=None):
        """Switch workspace to SettingsView."""
        if self.settings_view is None:
            return
        if hasattr(self.settings_view, "update_locale"):
            self.settings_view.update_locale()
        self.content = self.settings_view
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def show_help(self, ribbon_bar=None):
        """Switch workspace to HelpView."""
        if self.help_view is None:
            return
        if hasattr(self.help_view, "update_locale"):
            self.help_view.update_locale()
        self.content = self.help_view
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

