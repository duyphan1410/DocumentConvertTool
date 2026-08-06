"""
Main Flet UI Application Orchestrator for DocumentConvertTool.
Pure Orchestrator connecting AppState, WorkspaceView, and specialized Controllers (MVC architecture).
"""

import os
import flet as ft

from src.i18n import t, set_locale

# Force document modules to load and register
from src.core.registry import ModuleRegistry
import src.modules  # noqa: F401

from src.__version__ import __version__
from src.ui_flet.constants import MODES
from src.ui_flet.state import AppState
from src.ui_flet.theme import apply_theme
from src.ui_flet.layout.footer_bar import FooterBar
from src.ui_flet.layout.ribbon_bar import RibbonBar
from src.ui_flet.components.drag_drop_overlay import DragDropOverlay
from src.ui_flet.components.file_path_bar import FilePathBar
from src.ui_flet.components.search_replace_bar import SearchReplaceBar
from src.ui_flet.views.editor_view import EditorView
from src.ui_flet.views.preview_view import MarkdownPreview
from src.ui_flet.views.welcome_view import WelcomeView
from src.ui_flet.views.workspace_view import WorkspaceView
from src.ui_flet.views.settings_view import SettingsView
from src.ui_flet.views.help_view import HelpView
from src.ui_flet.helpers.shortcut_manager import ShortcutManager
from src.utils import settings_store

from src.ui_flet.controllers import (
    SearchController,
    FileController,
    ConversionController,
    EditorController,
    ThemeController,
    LayoutController,
    SettingsController,
)


class DocumentConvertApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = t("app.title", version=__version__)
        self.page.window.width = 1360
        self.page.window.height = 800
        self.page.window.min_width = 900
        self.page.window.min_height = 560
        self.page.padding = 12
        self.page.spacing = 10

        # Set Window Title Bar & Taskbar Icon
        import sys
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("docconvert.workspace.1.0")
            except Exception:
                pass

        # ── Test different window icons for Taskbar & OS Title Bar ───────────
        from src.utils.assets import resolve_icon_path
        icon_path = (
            # Option 1: High-res 256x256 ICO chỉ nhận được file ico, nhưng vẫn bị mờ
            resolve_icon_path("icon256x256px.ico")
        )
        if icon_path:
            self.page.window.icon = icon_path

        # Application State
        self.state = AppState()

        # Load persisted user settings into state before building UI
        settings_store.load_settings_into(self.state)

        # Initialize i18n locale from saved settings
        set_locale(self.state.language)
        if self.state.default_mode:
            self.state.current_mode = self.state.default_mode

        # File Pickers
        self.file_picker_in = ft.FilePicker()
        self.file_picker_out = ft.FilePicker()
        self.page.services.extend([self.file_picker_in, self.file_picker_out])

        # Apply Initial Theme (uses restored palette/theme_mode from settings)
        apply_theme(
            self.page, self.state.current_palette, self.state.current_theme_mode
        )

        # Build UI Shell & Controllers
        self._build_controls()

        # Register Global Keyboard Shortcuts (Ctrl+O, Ctrl+S, Ctrl+F, Ctrl+Z, Ctrl+Y)
        ShortcutManager.register(
            self.page,
            on_open_file=self.file_controller.trigger_browse_input,
            on_save_convert=self.conversion_controller.on_convert_clicked,
            on_find_replace=lambda: self.search_controller.toggle_search(True),
            on_undo=self.editor_controller.perform_undo,
            on_redo=self.editor_controller.perform_redo,
        )

        # Load & sync settings into UI controls (after controls are built)
        self.settings_controller.load_and_apply()

        # Restore Draft or Show Welcome Screen
        has_draft = self.file_controller.load_draft_if_exists()
        if has_draft:
            self._show_editor_view()
        else:
            self._show_welcome_view()

        print("[DEBUG] App initialized successfully with Pure Orchestrator MVC Architecture")

    def _build_controls(self):
        # 1. Component Shells
        self.search_replace_bar = SearchReplaceBar(
            on_search_changed=lambda e: self.search_controller.on_search_changed(e),
            on_find_next=lambda e: self.search_controller.find_next(e),
            on_find_prev=lambda e: self.search_controller.find_prev(e),
            on_replace=lambda e: self.search_controller.replace_current(
                e, self.editor_controller.on_editor_changed
            ),
            on_replace_all=lambda e: self.search_controller.replace_all(
                e,
                self.editor_controller.on_editor_changed,
                lambda msg: self.footer_bar.set_status(msg, ft.Colors.RED_400),
            ),
            on_match_click=lambda s, end: self.search_controller.on_search_match_clicked(
                s, end
            ),
        )

        self.welcome_view = WelcomeView(
            on_open_file=lambda e: self.file_controller.trigger_browse_input(e),
            on_create_blank=lambda e: self._on_create_blank_note(e),
        )

        self.settings_view = SettingsView(
            state=self.state,
            on_palette_changed=lambda e: self.settings_controller.on_palette_changed(e),
            on_theme_mode_changed=lambda e: self.settings_controller.on_theme_mode_changed(e),
            on_autosave_toggled=lambda e: self.settings_controller.on_autosave_toggled(e),
            on_autosave_interval_changed=lambda e: self.settings_controller.on_autosave_interval_changed(e),
            on_font_size_changed=lambda v: self.settings_controller.on_font_size_changed(v),
            on_default_mode_changed=lambda e: self.settings_controller.on_default_mode_changed(e),
            on_word_wrap_changed=lambda e: self.settings_controller.on_word_wrap_changed(e),
            on_language_changed=lambda e: self.settings_controller.on_language_changed(e),
            on_apply=lambda e: self.settings_controller.apply_all(e),
            on_discard=lambda e: self.settings_controller.discard_all(e),
            on_close=lambda e: self._show_editor_view(),
        )

        self.help_view = HelpView(
            on_get_started=lambda e: self._on_get_started(e),
            on_close=lambda e: self._show_editor_view(),
        )

        self.ribbon_bar = RibbonBar(
            current_mode=self.state.current_mode,
            current_palette=self.state.current_palette,
            current_theme_mode=self.state.current_theme_mode,
            on_mode_changed=lambda e: self._on_mode_changed(e),
            on_palette_changed=lambda e: self.theme_controller.on_palette_changed(e),
            on_theme_mode_changed=lambda e: self.theme_controller.on_theme_mode_changed(
                e
            ),
            on_browse_in=lambda e: self.file_controller.trigger_browse_input(e),
            on_browse_out=lambda e: self.file_controller.trigger_browse_output(e),
            on_clear_editor=lambda e: self.editor_controller.clear_editor(e),
            on_format_action=lambda p, s: self.editor_controller.on_format_action(p, s),
            on_heading_change=lambda lvl: self.editor_controller.on_heading_change(lvl),
            on_toggle_search=lambda e: self.search_controller.toggle_search_panel(e),
            on_convert_click=lambda e: self.conversion_controller.on_convert_clicked(e),
            on_toggle_preview=lambda e: self.layout_controller.toggle_preview_pane(e),
            on_toggle_file_path_bar=lambda e: self.layout_controller.toggle_file_path_bar(
                e
            ),
            on_toggle_editor=lambda e: self.layout_controller.toggle_editor_panel(e),
            on_toggle_status_bar=lambda e: self.layout_controller.toggle_status_bar(e),
            on_insert_image=lambda e: self.file_controller.trigger_insert_image(e),
            on_ribbon_toggle=lambda: self.layout_controller.update_editor_dynamic_height(),
            on_show_settings=lambda: self._show_settings_view(),
            on_show_help=lambda: self._show_help_view(),
            on_show_editor=lambda: self._show_editor_view(auto_select_edit=False),
            search_replace_bar=self.search_replace_bar,
        )

        self.file_path_bar = FilePathBar(
            on_browse_in=lambda e: self.file_controller.trigger_browse_input(e),
            on_browse_out=lambda e: self.file_controller.trigger_browse_output(e),
            on_out_path_changed=lambda e: setattr(
                self.state, "out_path", self.file_path_bar.out_path_text.value.strip()
            ),
        )

        self.editor_view = EditorView(
            search_replace_bar=self.search_replace_bar,
            on_editor_changed=lambda e: self.editor_controller.on_editor_changed(
                e, self.file_controller
            ),
            on_toggle_search=lambda e: self.search_controller.toggle_search_panel(e),
            on_undo=lambda e: self.editor_controller.perform_undo(e),
            on_redo=lambda e: self.editor_controller.perform_redo(e),
            on_clear=lambda e: self.editor_controller.clear_editor(e),
            on_open_file=lambda e: self.file_controller.trigger_browse_input(e),
        )

        self.preview = MarkdownPreview()
        self.right_pane = ft.Container(
            content=self.preview,
            expand=True,
            padding=10,
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        )

        self.editor_workspace = ft.Row(
            controls=[self.editor_view.container, self.right_pane],
            expand=True,
            spacing=10,
        )

        self.workspace_view = WorkspaceView(
            welcome_view=self.welcome_view,
            editor_workspace=self.editor_workspace,
            settings_view=self.settings_view,
            help_view=self.help_view,
        )

        self.footer_bar = FooterBar(
            on_convert_clicked=lambda e: self.conversion_controller.on_convert_clicked(e),
            on_open_file=lambda e: self.conversion_controller.open_converted_file(e),
            on_open_folder=lambda e: self.conversion_controller.open_converted_folder(e),
        )

        # 2. Control Registry Dict
        app_controls = {
            "file_path_bar": self.file_path_bar,
            "editor_view": self.editor_view,
            "preview": self.preview,
            "right_pane": self.right_pane,
            "footer_bar": self.footer_bar,
            "ribbon_bar": self.ribbon_bar,
            "welcome_view": self.welcome_view,
            "settings_view": self.settings_view,
            "help_view": self.help_view,
            "file_picker_in": self.file_picker_in,
            "file_picker_out": self.file_picker_out,
            "on_show_editor": self._show_editor_view,
            "on_mode_changed": self._on_mode_changed,
        }

        # 3. Modular Controllers
        self.theme_controller = ThemeController(self.page, self.state, app_controls)
        self.layout_controller = LayoutController(self.page, self.state, app_controls)
        self.editor_controller = EditorController(self.page, self.state, app_controls)
        self.file_controller = FileController(self.page, self.state, app_controls)
        self.conversion_controller = ConversionController(
            self.page, self.state, app_controls
        )
        self.search_controller = SearchController(
            self.page,
            self.state,
            self.search_replace_bar,
            self.editor_view,
            self.ribbon_bar,
        )
        self.settings_controller = SettingsController(self.page, self.state, app_controls)

        # Back-reference so controllers can find theme_controller, file_controller, search_replace_bar, layout_controller
        app_controls["theme_controller"] = self.theme_controller
        app_controls["file_controller"] = self.file_controller
        app_controls["search_replace_bar"] = self.search_replace_bar
        app_controls["layout_controller"] = self.layout_controller

        self.drag_drop_overlay = DragDropOverlay()
        self.main_stack = ft.Stack(
            controls=[
                self.workspace_view,
                self.drag_drop_overlay,
            ],
            expand=True,
        )

        # 4. Assemble Page Tree
        self.page.add(
            self.ribbon_bar,
            self.file_path_bar.container,
            self.main_stack,
            self.footer_bar.container,
        )
        self.theme_controller.update_theme_colors()

    # ── Unsaved Settings Guard ─────────────────────────────────────────────

    def _check_settings_unsaved(self, on_proceed):
        """If settings_view has unsaved changes, show a Flet modal before proceeding."""
        is_dirty = getattr(getattr(self, "settings_view", None), "_is_dirty", False)
        if not is_dirty:
            on_proceed()
            return

        # Build Flet 0.86.4 modal (overlay-based, synchronous callbacks)
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.SETTINGS_ROUNDED, color=ft.Colors.ORANGE_400, size=20),
                    ft.Text(t("dialog.unsaved_title"), weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Text(
                t("dialog.unsaved_message"),
                size=13,
            ),
            actions=[
                ft.TextButton(t("dialog.btn_save"),    on_click=lambda e: _close("save")),
                ft.TextButton(t("dialog.btn_discard"), on_click=lambda e: _close("discard")),
                ft.TextButton(t("dialog.btn_cancel"),  on_click=lambda e: _close("cancel")),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        def _close(action: str):
            dialog.open = False
            self.page.update()
            if action == "save":
                self.settings_controller.apply_all()
                on_proceed()
            elif action == "discard":
                self.settings_controller.discard_all()
                on_proceed()
            # cancel: stay on settings, do nothing

        # Flet 0.86.4 modal pattern from SKILL.md
        self.page.overlay[:] = [c for c in self.page.overlay if not isinstance(c, ft.AlertDialog)]
        if dialog not in self.page.overlay:
            self.page.overlay.append(dialog)
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    # ── View navigation (all guarded by unsaved-settings check) ───────────

    def _show_welcome_view(self):
        self._check_settings_unsaved(
            lambda: self.workspace_view.show_welcome(ribbon_bar=self.ribbon_bar)
        )

    def _show_editor_view(self, auto_select_edit: bool = True):
        self._check_settings_unsaved(
            lambda: self.workspace_view.show_editor(ribbon_bar=self.ribbon_bar, auto_select_edit=auto_select_edit)
        )

    def _show_settings_view(self):
        self.workspace_view.show_settings(ribbon_bar=self.ribbon_bar)

    def _show_help_view(self):
        self._check_settings_unsaved(
            lambda: self.workspace_view.show_help(ribbon_bar=self.ribbon_bar)
        )

    def _on_get_started(self, e=None):
        """Help view 'Get Started' CTA -> go to welcome view."""
        self._check_settings_unsaved(
            lambda: self.workspace_view.show_welcome(ribbon_bar=self.ribbon_bar)
        )

    def _on_create_blank_note(self, e=None):
        self.workspace_view.show_editor(ribbon_bar=self.ribbon_bar)
        self.editor_controller.clear_editor()

    def _on_mode_changed(self, e=None):
        self.state.current_mode = self.ribbon_bar.mode_dropdown.value
        mode_cfg = MODES.get(self.state.current_mode, MODES["MD -> Excel"])
        self.file_path_bar.set_in_label(mode_cfg["in_label"])
        self.file_path_bar.set_out_label(mode_cfg["out_label"])
        out_ext = mode_cfg["out_ext"]

        if self.state.in_path:
            in_base, _ = os.path.splitext(self.state.in_path)
            self.state.out_path = f"{in_base}{out_ext}"
        else:
            self.state.out_path = os.path.abspath(f"output{out_ext}")

        self.file_path_bar.set_out_path(self.state.out_path)
        try:
            self.page.update()
        except Exception:
            pass


def main(page: ft.Page):
    app = DocumentConvertApp(page)


if __name__ == "__main__":
    ft.app(target=main)
