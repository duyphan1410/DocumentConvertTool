"""
Main Flet UI Application Orchestrator for DocumentConvertTool.
Pure Orchestrator connecting AppState, WorkspaceView, and specialized Controllers (MVC architecture).
"""

import os
import asyncio
from typing import Optional, Callable, Any
import flet as ft

from src.i18n import t, set_locale
from src.ui_flet.helpers.image_token_helper import ImageTokenInfo

# Force document modules to load and register
from src.core.registry import ModuleRegistry
import src.modules  # noqa: F401

from src.__version__ import __version__
from src.ui_flet.constants import MODES
from src.ui_flet.state import AppState
from src.ui_flet.theme import apply_theme
from src.ui_flet.layout.footer_bar import FooterBar
from src.ui_flet.layout.ribbon_bar import RibbonBar
from src.ui_flet.layout.activity_bar import ActivityBar
from src.ui_flet.components.file_path_bar import FilePathBar
from src.ui_flet.components.search_replace_bar import SearchReplaceBar
from src.ui_flet.components.draggable_splitter import DraggableSplitter
from src.ui_flet.components.quick_open_dialog import QuickOpenDialog
from src.ui_flet.components.workspace_tab_bar import WorkspaceTabBar
from src.ui_flet.views.editor_view import EditorView
from src.ui_flet.views.preview_view import MarkdownPreview
from src.ui_flet.views.welcome_view import WelcomeView
from src.ui_flet.views.loading_view import LoadingView
from src.ui_flet.views.workspace_view import WorkspaceView
from src.ui_flet.views.settings_view import SettingsView
from src.ui_flet.views.help_view import HelpView
from src.ui_flet.views.explorer_view import ExplorerView
from src.ui_flet.native_dialogs import pick_directory_async
from src.ui_flet.helpers.shortcut_manager import ShortcutManager
from src.utils import settings_store
from src.utils.window import validate_and_sanitize_window_bounds

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
            resolve_icon_path("icon256x256px.ico")
        )
        if icon_path:
            self.page.window.icon = icon_path

        # Application State
        self.state = AppState()

        # Load persisted user settings into state before building UI
        settings_store.load_settings_into(self.state)

        # Initialize i18n locale from saved settings and set page title
        set_locale(self.state.language)
        self.page.title = t("app.title", version=__version__)
        if self.state.default_mode:
            self.state.current_mode = self.state.default_mode

        # Configure Window Dimensions & Native UX Persistence (with DPI & boundary rollback)
        self.page.window.min_width = 900
        self.page.window.min_height = 560

        safe_w, safe_h, safe_top, safe_left = validate_and_sanitize_window_bounds(
            self.state.window_width,
            self.state.window_height,
            self.state.window_top,
            self.state.window_left,
        )
        self.page.window.width = safe_w
        self.page.window.height = safe_h
        if safe_top is not None:
            self.page.window.top = safe_top
        if safe_left is not None:
            self.page.window.left = safe_left

        # Maximize window on fresh first launch or if previously saved as maximized
        self.page.window.maximized = bool(self.state.window_maximized)

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

        # Register Window State & Resize Tracking Events through LayoutController (MVC pattern)
        self.page.window.on_event = self.layout_controller.on_window_event
        self.page.on_resized = self.layout_controller.on_page_resized
        self.layout_controller.on_page_resized(None)

        # Register Global Keyboard Shortcuts (Ctrl+O, Ctrl+P, Ctrl+S, Ctrl+F, Ctrl+B, Ctrl+T, Ctrl+W, Ctrl+Tab, Ctrl+Z, Ctrl+Y)
        ShortcutManager.register(
            self.page,
            on_open_file=self.file_controller.trigger_browse_input,
            on_quick_open=lambda: self.quick_open_dialog.show(self.page),
            on_save_convert=self.file_controller.handle_save_shortcut,
            on_find_replace=lambda: self.search_controller.toggle_search(),
            on_toggle_sidebar=lambda: self.layout_controller.toggle_sidebar(tab_name="explorer"),
            on_undo=self.editor_controller.perform_undo,
            on_redo=self.editor_controller.perform_redo,
            on_new_tab=self.layout_controller.handle_new_doc_tab,
            on_close_tab=lambda: self.layout_controller.handle_doc_tab_closed(self.state.active_tab_id) if self.state.active_tab_id else None,
            on_next_tab=self.layout_controller.handle_next_doc_tab,
            on_prev_tab=self.layout_controller.handle_prev_doc_tab,
        )

        # Load & sync settings into UI controls (after controls are built)
        self.settings_controller.load_and_apply()

        # Restore Draft asynchronously with loading view, or Show Editor if Workspace Folder exists, or Show Welcome Screen
        if self.file_controller.has_draft_on_disk():
            asyncio.create_task(self.file_controller.async_load_draft_if_exists())
        elif self.state.workspace_folder and os.path.exists(self.state.workspace_folder):
            self._show_editor_view(auto_select_edit=False)
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
            on_open_folder=lambda e: asyncio.create_task(self._on_open_workspace_folder(e)),
            on_create_blank=lambda e: self._on_create_blank_note(e),
            on_import_youtube=lambda e: self.file_controller.trigger_youtube_import(e),
            on_transcribe_media=lambda e: self.file_controller.trigger_media_transcribe(e),
            on_open_model_hub=lambda e=None: self._open_model_hub_dialog(),
            on_open_help=lambda e: self._show_help_view(),
        )

        self.loading_view = LoadingView()

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
            on_sidebar_position_changed=lambda e: self.settings_controller.on_sidebar_position_changed(e),
            on_open_model_hub=lambda: self._open_model_hub_dialog(),
            on_apply=lambda e: self.settings_controller.apply_all(e),
            on_discard=lambda e: self.settings_controller.discard_all(e),
            on_close=lambda e: self._show_editor_view(auto_select_edit=False),
        )

        self.help_view = HelpView(
            on_get_started=lambda e: self._on_get_started(e),
            on_close=lambda e: self._show_editor_view(auto_select_edit=False),
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
            on_import_youtube=lambda e: self.file_controller.trigger_youtube_import(e),
            on_open_model_hub=lambda e=None: self._open_model_hub_dialog(),
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
            on_image_size_preset=lambda preset: self._on_image_size_preset(preset),
            on_image_align_preset=lambda align: self._on_image_align_preset(align),
            on_open_image_size_dialog=lambda: self._open_image_size_dialog(),
            on_replace_image=lambda: self.file_controller.trigger_replace_image(),
            on_reset_image_size=lambda: self._on_image_size_preset("100%"),
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
            on_save_md=lambda e: self.file_controller.trigger_save_markdown(e),
            on_image_context_changed=lambda tok: self._on_image_context_changed(tok),
        )
        self.editor_view.set_image_action_handlers(
            on_preset=lambda preset: self._on_image_size_preset(preset),
            on_align=lambda align: self._on_image_align_preset(align),
            on_custom=lambda: self._open_image_size_dialog(),
            on_replace=lambda: self.file_controller.trigger_replace_image(),
            on_reset=lambda: self._on_image_size_preset("100%"),
            on_open_menu=lambda x, y: self._show_image_context_menu_at(x, y),
        )

        self.preview = MarkdownPreview(
            on_open_file=lambda path: asyncio.create_task(
                self.file_controller.open_file_by_path(path)
            ),
            get_workspace_path=lambda: getattr(self.state, "workspace_folder", "") or (os.path.dirname(self.state.in_path) if self.state.in_path else ""),
            on_image_link_clicked=lambda url: self._handle_preview_image_clicked(url),
            on_insert_sample_table=lambda: self.editor_view.insert_sample_table(),
        )

        self.right_pane = ft.Container(
            content=self.preview,
            expand=True,
            padding=10,
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        )

        self.activity_bar = ActivityBar(
            on_tab_selected=lambda tab: self._on_activity_bar_item_clicked(tab),
            active_tab=getattr(self.state, "active_activity_tab", "explorer"),
        )

        from src.services.transcription_manager import TranscriptionJobManager, TranscriptionJob
        manager = TranscriptionJobManager.get_instance()
        try:
            manager.set_event_loop(asyncio.get_running_loop())
        except Exception:
            pass

        def _on_global_job_changed(job: Optional[TranscriptionJob]):
            is_running = job is not None
            self.activity_bar.set_item_loading("youtube", is_running)

        manager.subscribe_global(_on_global_job_changed)

        self.quick_open_dialog = QuickOpenDialog(
            get_workspace_path=lambda: getattr(self.state, "workspace_folder", "")
            or (os.path.dirname(self.state.in_path) if self.state.in_path else ""),
            on_file_selected=lambda path: asyncio.create_task(
                self._on_explorer_file_clicked(path)
            ),
        )

        self.editor_view.set_path_providers(
            get_active_file_path=lambda: getattr(self.state, "in_path", ""),
            get_workspace_path=lambda: getattr(self.state, "workspace_folder", ""),
        )

        self.explorer_view = ExplorerView(
            on_open_folder=lambda e: asyncio.create_task(self._on_open_workspace_folder(e)),
            on_file_click=lambda path: asyncio.create_task(self._on_explorer_file_clicked(path)),
            on_rename=lambda old_p, new_p: self.file_controller.handle_file_renamed(old_p, new_p),
            on_delete=lambda del_p: self.file_controller.handle_file_deleted(del_p),
            on_quick_convert=lambda file_p, target_ext: asyncio.create_task(
                self.conversion_controller.async_quick_convert_file(file_p, target_ext)
            ),
            on_new_file=lambda new_p: asyncio.create_task(self.file_controller.open_file_by_path(new_p)),
            on_new_folder=lambda new_folder: None,
            on_status_message=lambda msg, col=None: self.footer_bar.set_status(msg, color=col),
            on_batch_convert=lambda p: self._show_batch_converter(p),
            get_is_dirty=lambda: getattr(self.state, "is_dirty", False),
            get_active_file=lambda: getattr(self.state, "in_path", ""),
            workspace_path=getattr(self.state, "workspace_folder", ""),
            active_file_path=getattr(self.state, "in_path", ""),
            width=getattr(self.state, "sidebar_width", 240),
            visible=getattr(self.state, "show_sidebar", True),
        )

        self.sidebar_splitter = DraggableSplitter(
            on_drag_update=lambda d: self.layout_controller.on_sidebar_resized(d),
            on_drag_end=lambda: self.layout_controller.on_sidebar_resize_end(),
            on_double_tap=lambda: self.layout_controller.on_sidebar_double_tap(),
            splitter_width=6,
            is_vertical=True,
            visible=getattr(self.state, "show_sidebar", True),
        )

        self.editor_splitter = DraggableSplitter(
            on_drag_update=lambda d: self.layout_controller.on_editor_resized(d),
            on_drag_end=lambda: self.layout_controller.on_editor_resize_end(),
            on_double_tap=lambda: self.layout_controller.on_editor_double_tap(),
            splitter_width=6,
            is_vertical=True,
        )

        from src.utils.clipboard import set_clipboard_text
        from src.utils.file_ops import reveal_in_windows_explorer

        self.workspace_tab_bar = WorkspaceTabBar(
            on_tab_select=lambda tid: self.layout_controller.handle_doc_tab_selected(tid),
            on_tab_close=lambda tid: self.layout_controller.handle_doc_tab_closed(tid),
            on_tab_reorder=lambda sid, tid: self.layout_controller.handle_doc_tab_reordered(sid, tid),
            on_new_tab=lambda: self.layout_controller.handle_new_doc_tab(),
            on_close_others=lambda tid: self.layout_controller.handle_close_other_tabs(tid),
            on_close_to_right=lambda tid: self.layout_controller.handle_close_tabs_to_right(tid),
            on_close_all=lambda: self.layout_controller.handle_close_all_tabs(),
            on_copy_path=lambda path: set_clipboard_text(path, self.page),
            on_reveal=lambda path: reveal_in_windows_explorer(path),
        )


        self.editor_split_row = ft.Row(
            controls=[
                self.editor_view.container,
                self.editor_splitter,
                self.right_pane,
            ],
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=0,
        )

        self.editor_main_column = ft.Column(
            controls=[
                self.workspace_tab_bar,
                self.editor_split_row,
            ],
            expand=True,
            spacing=0,
        )

        self.editor_workspace = ft.Row(
            controls=[
                self.activity_bar,
                self.explorer_view,
                self.sidebar_splitter,
                self.editor_main_column,
            ],
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=0,
        )

        self.workspace_view = WorkspaceView(
            welcome_view=self.welcome_view,
            editor_workspace=self.editor_workspace,
            loading_view=self.loading_view,
            settings_view=self.settings_view,
            help_view=self.help_view,
        )

        self.footer_bar = FooterBar(
            on_convert_clicked=lambda e: self.conversion_controller.on_convert_clicked(e),
            on_open_file=lambda e: self.conversion_controller.open_converted_file(e),
            on_open_folder=lambda e: self.conversion_controller.open_converted_folder(e),
        )

        # Central Context Menu mounted at startup in page.overlay
        from src.ui_flet.components.context_menu import ExplorerContextMenu
        self.context_menu = ExplorerContextMenu(self.page)
        self.explorer_view.context_menu = self.context_menu
        self.workspace_tab_bar.context_menu = self.context_menu
        self._image_context_menu = self.context_menu

        # 2. Control Registry Dict
        app_controls = {
            "file_path_bar": self.file_path_bar,
            "editor_view": self.editor_view,
            "preview": self.preview,
            "right_pane": self.right_pane,
            "footer_bar": self.footer_bar,
            "ribbon_bar": self.ribbon_bar,
            "welcome_view": self.welcome_view,
            "loading_view": self.loading_view,
            "workspace_view": self.workspace_view,
            "settings_view": self.settings_view,
            "help_view": self.help_view,
            "activity_bar": self.activity_bar,
            "explorer_view": self.explorer_view,
            "sidebar_splitter": self.sidebar_splitter,
            "editor_splitter": self.editor_splitter,
            "editor_split_row": self.editor_split_row,
            "editor_main_column": self.editor_main_column,
            "workspace_tab_bar": self.workspace_tab_bar,
            "editor_workspace": self.editor_workspace,
            "file_picker_in": self.file_picker_in,
            "file_picker_out": self.file_picker_out,
            "on_show_editor": self._show_editor_view,
            "on_mode_changed": self._on_mode_changed,
            "show_batch_converter": self._show_batch_converter,
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

        # 4. Assemble Page Tree
        self.page.add(
            self.ribbon_bar,
            self.file_path_bar.container,
            self.workspace_view,
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
        def _apply():
            self.workspace_view.show_editor(ribbon_bar=self.ribbon_bar, auto_select_edit=auto_select_edit)
            if self.state.workspace_folder and os.path.exists(self.state.workspace_folder) and not self.state.active_tab:
                from src.__version__ import __version__
                folder_name = os.path.basename(self.state.workspace_folder) or self.state.workspace_folder
                self.page.title = f"{folder_name} — Document Converter v{__version__}"
                try:
                    self.page.update()
                except Exception:
                    pass
        self._check_settings_unsaved(_apply)

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
        self.layout_controller.handle_new_doc_tab()

    def _on_mode_changed(self, e=None):
        old_mode = getattr(self.state, "current_mode", "") or ""
        new_mode = self.ribbon_bar.mode_dropdown.value or ""
        self.state.current_mode = new_mode
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

        # Adaptive Preview Mode: Switch to spreadsheet view for Excel/CSV target modes
        cur_mode = self.state.current_mode or ""
        if cur_mode in ("MD -> Excel", "MD -> CSV") or out_ext in (".xlsx", ".xls", ".csv"):
            if hasattr(self.preview, "set_preview_mode"):
                self.preview.set_preview_mode("spreadsheet")
        else:
            if hasattr(self.preview, "set_preview_mode"):
                self.preview.set_preview_mode("document")

        cur_text = self.editor_view.get_text() if hasattr(self, "editor_view") else ""
        if cur_text and hasattr(self.preview, "set_content"):
            base_dir = os.path.dirname(self.state.in_path) if self.state.in_path else None
            active_tab = self.state.active_tab
            sid = active_tab.media_session_id if active_tab else None
            self.preview.set_content(cur_text, base_dir=base_dir, session_id=sid)

        # Trigger dynamic reload if user switches between regular PDF -> MD and PDF Scan -> MD
        if (
            self.state.in_path
            and self.state.in_path.lower().endswith(".pdf")
            and old_mode != new_mode
            and (old_mode in ("PDF -> MD", "PDF Scan -> MD") or new_mode in ("PDF -> MD", "PDF Scan -> MD"))
            and hasattr(self, "file_controller")
        ):
            active_tab = self.state.active_tab
            if active_tab:
                active_tab.current_mode = new_mode
            import asyncio
            asyncio.create_task(self.file_controller.open_file_by_path(self.state.in_path, force_reload=True))

        try:
            self.page.update()
        except Exception:
            pass

    def _on_activity_bar_item_clicked(self, tab_name: str):
        if tab_name == "explorer":
            self.layout_controller.toggle_sidebar(e=True, tab_name="explorer")
        elif tab_name == "search":
            self.quick_open_dialog.show(self.page)
        elif tab_name == "youtube":
            from src.services.transcription_manager import TranscriptionJobManager
            mgr = TranscriptionJobManager.get_instance()
            local_job = mgr.get_active_job(job_types=["local_media", "local_audio", "local_video"])
            if local_job:
                self.file_controller.trigger_media_transcribe(default_file_path=local_job.source)
            else:
                self.file_controller.trigger_youtube_import(None)

    async def _on_open_workspace_folder(self, e=None):
        folder = await pick_directory_async(self.page, self.file_picker_in)
        if folder:
            self.state.workspace_folder = folder
            self.explorer_view.load_workspace(folder, active_file=self.state.in_path)
            settings_store.save_settings(self.state)
            self._show_editor_view(auto_select_edit=False)

    async def _on_explorer_file_clicked(self, file_path: str):
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (
            ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg",
            ".mp4", ".mkv", ".avi", ".mov", ".webm",
        ):
            self.file_controller.trigger_media_transcribe(default_file_path=file_path)
        else:
            await self.file_controller.open_file_by_path(file_path)

    def _show_batch_converter(self, initial_source: str = ""):
        """Opens the Batch & Archive Converter modal dialog."""
        from src.ui_flet.components.batch_dialog import BatchDialog
        src = initial_source or getattr(self.state, "workspace_folder", "")
        dlg = BatchDialog(
            page=self.page,
            initial_source=src,
            on_completed=lambda res: self.explorer_view.refresh_tree(),
        )
        dlg.show()

    def _on_image_size_preset(self, preset: str, image_token=None):
        tok = image_token or getattr(self.editor_view, "pinned_image_token", None) or getattr(self.editor_view, "active_image_token", None)
        if tok:
            w_val = "" if preset in ("100%", "100") else preset
            self.editor_view.apply_image_size(tok, width=w_val, height="", align=tok.align)

    def _on_image_align_preset(self, align: str, image_token=None):
        tok = image_token or getattr(self.editor_view, "pinned_image_token", None) or getattr(self.editor_view, "active_image_token", None)
        if tok:
            self.editor_view.apply_image_size(tok, width=tok.width, height=tok.height, align=align)

    def _open_image_size_dialog(self, image_token=None):
        tok = image_token or getattr(self.editor_view, "pinned_image_token", None) or getattr(self.editor_view, "active_image_token", None)
        if not tok:
            return
        from src.ui_flet.components.image_size_dialog import show_image_size_dialog
        base_dir = os.path.dirname(self.state.in_path) if self.state.in_path else getattr(self.state, "workspace_folder", None)
        is_dark = (self.state.current_theme_mode != "Light")
        show_image_size_dialog(
            page=self.page,
            image_info=tok,
            on_apply=self._handle_image_dialog_apply,
            base_dir=base_dir,
            current_palette=self.state.current_palette,
            is_dark=is_dark,
        )

    def _handle_image_dialog_apply(self, tok, width, height, align, alt, src):
        self.editor_view.apply_image_size(tok, width=width, height=height, align=align, alt=alt, src=src)

    def _show_image_context_menu_at(self, x: float, y: float, image_token: Optional[ImageTokenInfo] = None):
        """Displays the Explorer-style floating context menu for the currently selected image."""
        tok = image_token or getattr(self.editor_view, "pinned_image_token", None) or getattr(self.editor_view, "active_image_token", None)
        if not tok:
            return
        if not hasattr(self, "context_menu") or not self.context_menu:
            from src.ui_flet.components.context_menu import ExplorerContextMenu
            self.context_menu = ExplorerContextMenu(self.page)
        self.context_menu.on_dismiss = self._on_image_menu_dismissed

        saved_offset = getattr(self.preview, "_saved_scroll_offset", 0.0) if hasattr(self, "preview") and self.preview else 0.0

        self.context_menu.show_image_menu(
            x=x,
            y=y,
            image_info=tok,
            on_size_preset=lambda p: self._on_image_size_preset(p, image_token=tok),
            on_align_preset=lambda a: self._on_image_align_preset(a, image_token=tok),
            on_custom_size=lambda: self._open_image_size_dialog(image_token=tok),
            on_replace_image=lambda: self.file_controller.trigger_replace_image(),
            on_reset_image=lambda: self._on_image_size_preset("100%", image_token=tok),
        )

        if hasattr(self, "preview") and self.preview and saved_offset > 0:
            self.preview.restore_scroll(target_offset=saved_offset)

    def _on_image_menu_dismissed(self):
        if hasattr(self, "editor_view"):
            self.editor_view._dismissed_token_raw = None
        if hasattr(self, "preview") and self.preview:
            saved_offset = getattr(self.preview, "_saved_scroll_offset", 0.0)
            if saved_offset > 0:
                self.preview.restore_scroll(target_offset=saved_offset)
        print("[DEBUG][_on_image_menu_dismissed] context menu dismissed")

    def _on_image_context_changed(self, tok):
        self.ribbon_bar.set_image_context(tok)

    def _handle_preview_image_clicked(self, url: str):
        """Handles user clicking directly on an image in Live Document Preview."""
        import urllib.parse
        from src.ui_flet.helpers.image_token_helper import find_all_image_tokens

        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        src_list = params.get("src", [])
        idx_list = params.get("idx", [])
        start_list = params.get("start", [])

        target_src = urllib.parse.unquote(src_list[0]) if src_list else ""
        target_idx = int(idx_list[0]) if idx_list else -1
        start_offset = int(start_list[0]) if start_list else -1
        click_x_list = params.get("click_x", [])
        click_y_list = params.get("click_y", [])
        click_x = float(click_x_list[0]) if click_x_list else None
        click_y = float(click_y_list[0]) if click_y_list else None

        raw_val = self.editor_view.editor.value or ""
        tokens = find_all_image_tokens(raw_val)

        target_tok = None
        # 1. Match by token index if in range
        if 0 <= target_idx < len(tokens):
            candidate = tokens[target_idx]
            if not target_src or (os.path.basename(candidate.src) == os.path.basename(target_src)):
                target_tok = candidate

        # 2. Match by exact or normalized src
        if not target_tok and target_src:
            clean_target = target_src.strip().replace("\\", "/")
            for t in tokens:
                t_src = t.src.strip().replace("\\", "/")
                if t_src == clean_target or os.path.basename(t_src) == os.path.basename(clean_target):
                    target_tok = t
                    break

        # 3. Match by offset range in editor.value
        if not target_tok and start_offset >= 0:
            for t in tokens:
                if t.start <= start_offset <= t.end:
                    target_tok = t
                    break

        # 4. Fallback to closest token by offset
        if not target_tok and tokens and start_offset >= 0:
            target_tok = min(tokens, key=lambda t: abs(t.start - start_offset))

        if target_tok:
            try:
                # Show the Explorer-style context menu right next to the clicked image location without moving the preview scroll
                win_w = getattr(self.page.window, "width", 1000) or 1000
                win_h = getattr(self.page.window, "height", 800) or 800
                if click_x is not None and click_y is not None:
                    menu_x = min(max(20, click_x - 60), win_w - 240)
                    # If clicking near bottom of screen, open menu upward above cursor
                    if click_y > win_h - 260:
                        menu_y = max(40, click_y - 220)
                    else:
                        menu_y = max(60, click_y + 10)
                else:
                    menu_x = win_w / 2 + 30
                    menu_y = 200

                print(f"[DEBUG][APP_IMAGE_CLICK] matched target_tok={target_tok.src}, menu_pos=({menu_x}, {menu_y})")
                self._show_image_context_menu_at(menu_x, menu_y, target_tok)
            except Exception as ex:
                print(f"[DEBUG] _handle_preview_image_clicked error: {ex}")

    def _open_model_hub_dialog(self):
        """Displays the AI Model Hub & Marketplace Modal."""
        from src.ui_flet.components.model_hub_dialog import show_model_hub_dialog
        show_model_hub_dialog(
            self.page,
            current_palette=self.state.current_palette,
        )


def main(page: ft.Page):
    app = DocumentConvertApp(page)



if __name__ == "__main__":
    ft.app(target=main)
