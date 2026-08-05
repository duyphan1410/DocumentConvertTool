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
        settings_view=None,
        help_view=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.welcome_view = welcome_view
        self.editor_workspace = editor_workspace
        self.settings_view = settings_view
        self.help_view = help_view

        self.expand = True
        self.content = self.welcome_view

    def show_welcome(self, ribbon_bar=None):
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
        self.content = self.editor_workspace
        if auto_select_edit and ribbon_bar:
            try:
                ribbon_bar._select_tab("edit")
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
        self.content = self.help_view
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

