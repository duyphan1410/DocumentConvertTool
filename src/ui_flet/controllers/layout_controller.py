"""
Layout Controller for Flet UI.
Manages panel visibility toggles (Preview pane, File path bar, Editor panel, Status bar) and editor dynamic height math.
"""
import os
import asyncio
import flet as ft
from src.i18n import t
from src.ui_flet.state import AppState
from src.utils.settings_store import save_settings
from src.services.media_asset_manager import MediaAssetManager
from src.ui_flet.components.file_modals import show_unsaved_tab_dialog


class LayoutController:
    def __init__(self, page: ft.Page, state: AppState, app_controls: dict):
        self.page = page
        self.state = state
        self.app_controls = app_controls
        self._window_save_timer = None

    def on_window_event(self, e):
        """Track window geometry changes (resize, move, maximize, restore) and persist to settings."""
        evt_type = getattr(e, "data", None) or getattr(e, "type", None)
        evt_name = str(evt_type).lower() if evt_type is not None else ""

        def _sync_geometry():
            try:
                if "maximize" in evt_name and "un" not in evt_name:
                    self.state.window_maximized = True
                elif "unmaximize" in evt_name or "restore" in evt_name:
                    self.state.window_maximized = False
                elif hasattr(self.page.window, "maximized") and self.page.window.maximized is not None:
                    self.state.window_maximized = bool(self.page.window.maximized)

                if not self.state.window_maximized:
                    if self.page.window.width and self.page.window.width >= 900:
                        self.state.window_width = int(round(self.page.window.width))
                    if self.page.window.height and self.page.window.height >= 560:
                        self.state.window_height = int(round(self.page.window.height))
                    if self.page.window.top is not None:
                        self.state.window_top = int(round(self.page.window.top))
                    if self.page.window.left is not None:
                        self.state.window_left = int(round(self.page.window.left))
            except Exception:
                pass

        if "close" in evt_name:
            _sync_geometry()
            self._safe_save_settings()
            try:
                from src.services.youtube_player import YouTubePlayerManager
                YouTubePlayerManager.get_instance().close()
            except Exception:
                pass
            print(
                f"[DEBUG][WINDOW] 💾 Đã lưu khi đóng app: "
                f"width={self.state.window_width}, height={self.state.window_height}, "
                f"top={self.state.window_top}, left={self.state.window_left}, "
                f"maximized={self.state.window_maximized}"
            )
            return

        _sync_geometry()

        # Dynamic Responsive Ribbon Layout
        self.on_page_resized(None)

        # Debounce disk I/O by 500ms
        import threading
        if self._window_save_timer:
            try:
                self._window_save_timer.cancel()
            except Exception:
                pass

        def _delayed_save():
            _sync_geometry()
            self._safe_save_settings()
            print(
                f"[DEBUG][WINDOW] 💾 Đã lưu cấu hình (event: {evt_name}): "
                f"width={self.state.window_width}, height={self.state.window_height}, "
                f"top={self.state.window_top}, left={self.state.window_left}, "
                f"maximized={self.state.window_maximized}"
            )

        self._window_save_timer = threading.Timer(0.5, _delayed_save)
        self._window_save_timer.daemon = True
        self._window_save_timer.start()

    def on_page_resized(self, e=None):
        """Dispatched on live window/canvas resizing to update responsive UI."""
        w = None
        if e and hasattr(e, "width") and e.width:
            w = e.width
        elif hasattr(self.page, "width") and self.page.width:
            w = self.page.width
        elif hasattr(self.page.window, "width") and self.page.window.width:
            w = self.page.window.width

        if w:
            ribbon_bar = self.app_controls.get("ribbon_bar")
            if ribbon_bar and hasattr(ribbon_bar, "update_responsive_layout"):
                ribbon_bar.update_responsive_layout(int(w))

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

        ribbon_bar = self.app_controls.get("ribbon_bar")
        if ribbon_bar:
            if hasattr(ribbon_bar, "set_preview_visible"):
                ribbon_bar.set_preview_visible(getattr(self.state, "show_preview", True))
            if hasattr(ribbon_bar, "set_path_bar_visible"):
                ribbon_bar.set_path_bar_visible(getattr(self.state, "show_path_bar", True))

        # Restore sidebar visibility & width
        explorer_view = self.app_controls.get("explorer_view")
        sidebar_splitter = self.app_controls.get("sidebar_splitter")
        activity_bar = self.app_controls.get("activity_bar")
        is_sidebar_open = getattr(self.state, "show_sidebar", True)
        if explorer_view:
            explorer_view.visible = is_sidebar_open
            sw = getattr(self.state, "sidebar_width", 240)
            if hasattr(explorer_view, "update_responsive_width"):
                explorer_view.update_responsive_width(sw)
            else:
                explorer_view.width = sw
        if sidebar_splitter:
            sidebar_splitter.visible = is_sidebar_open
        if activity_bar:
            activity_bar.set_active_tab(
                getattr(self.state, "active_activity_tab", "explorer"),
                is_open=is_sidebar_open,
            )

        self.apply_sidebar_position()
        self.apply_editor_ratio()
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def apply_sidebar_position(self):
        """Reorders editor_workspace layout controls based on state.sidebar_position."""
        editor_workspace = self.app_controls.get("editor_workspace")
        activity_bar = self.app_controls.get("activity_bar")
        explorer_view = self.app_controls.get("explorer_view")
        sidebar_splitter = self.app_controls.get("sidebar_splitter")
        editor_view = self.app_controls.get("editor_view")
        editor_splitter = self.app_controls.get("editor_splitter")
        right_pane = self.app_controls.get("right_pane")

        if not (editor_workspace and activity_bar and explorer_view and sidebar_splitter and editor_view and right_pane):
            return

        is_left = getattr(self.state, "sidebar_position", "left") == "left"
        activity_bar.update_border_side(is_left)

        main_editor_area = self.app_controls.get("editor_main_column")
        if not main_editor_area:
            editor_ctrl = editor_view.container if hasattr(editor_view, "container") else editor_view
            main_editor_area = editor_ctrl

        controls_to_add = (
            [activity_bar, explorer_view, sidebar_splitter, main_editor_area]
            if is_left
            else [main_editor_area, sidebar_splitter, explorer_view, activity_bar]
        )

        editor_workspace.controls = [c for c in controls_to_add if c is not None]
        try:
            if editor_workspace.page:
                editor_workspace.update()
        except Exception:
            pass

    def apply_editor_ratio(self):
        """Applies the current editor_ratio to editor_view and right_pane."""
        editor_view = self.app_controls.get("editor_view")
        right_pane = self.app_controls.get("right_pane")
        if not (editor_view and right_pane):
            return

        ratio = getattr(self.state, "editor_ratio", 0.5)
        ratio = max(0.20, min(0.80, ratio))
        self.state.editor_ratio = ratio

        editor_flex = int(round(ratio * 1000))
        preview_flex = 1000 - editor_flex

        if hasattr(editor_view, "container"):
            editor_view.container.expand = editor_flex
        else:
            editor_view.expand = editor_flex
        right_pane.expand = preview_flex

    def on_editor_resized(self, delta_x: float):
        """Handles smooth 60fps drag resizing between editor and preview."""
        editor_view = self.app_controls.get("editor_view")
        right_pane = self.app_controls.get("right_pane")
        editor_workspace = self.app_controls.get("editor_workspace")
        if not (editor_view and right_pane):
            return

        page_w = self.page.width if hasattr(self.page, "width") and self.page.width else 1200
        sidebar_w = getattr(self.state, "sidebar_width", 240) if getattr(self.state, "show_sidebar", True) else 0
        available_w = max(400, page_w - sidebar_w - 48 - 40)

        delta_ratio = delta_x / available_w
        cur_ratio = getattr(self.state, "editor_ratio", 0.5)
        new_ratio = max(0.20, min(0.80, cur_ratio + delta_ratio))

        self.state.editor_ratio = new_ratio
        editor_flex = int(round(new_ratio * 1000))
        preview_flex = 1000 - editor_flex

        if hasattr(editor_view, "container"):
            editor_view.container.expand = editor_flex
        else:
            editor_view.expand = editor_flex
        right_pane.expand = preview_flex

        try:
            if editor_workspace and editor_workspace.page:
                editor_workspace.update()
        except Exception:
            pass

    def on_editor_resize_end(self):
        """Persist editor ratio to settings when drag ends."""
        self._safe_save_settings()

    def on_editor_double_tap(self):
        """Reset editor-preview ratio to 50:50."""
        self.state.editor_ratio = 0.5
        self.apply_editor_ratio()
        self._safe_save_settings()
        editor_workspace = self.app_controls.get("editor_workspace")
        try:
            if editor_workspace and editor_workspace.page:
                editor_workspace.update()
        except Exception:
            pass

    def toggle_sidebar(self, e=None, tab_name: str = "explorer"):
        """Toggle sidebar visibility or switch active tab on ActivityBar."""
        explorer_view = self.app_controls.get("explorer_view")
        sidebar_splitter = self.app_controls.get("sidebar_splitter")
        activity_bar = self.app_controls.get("activity_bar")

        current_active = getattr(self.state, "active_activity_tab", "explorer")
        is_open = getattr(self.state, "show_sidebar", True)

        if is_open and current_active == tab_name and e is not None:
            # Clicked active tab -> collapse
            self.state.show_sidebar = False
        else:
            # Switch to this tab or open
            self.state.show_sidebar = True
            self.state.active_activity_tab = tab_name

        new_open = self.state.show_sidebar
        if explorer_view:
            explorer_view.visible = new_open
        if sidebar_splitter:
            sidebar_splitter.visible = new_open
        if activity_bar:
            activity_bar.set_active_tab(self.state.active_activity_tab, is_open=new_open)

        self._safe_save_settings()
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def on_sidebar_resized(self, delta_x: float):
        """Handles smooth 60fps drag resizing of the sidebar."""
        explorer_view = self.app_controls.get("explorer_view")
        if not explorer_view:
            return

        is_left = getattr(self.state, "sidebar_position", "left") == "left"
        actual_delta = delta_x if is_left else -delta_x

        cur_width = explorer_view.width or getattr(self.state, "sidebar_width", 240)
        target_width = cur_width + actual_delta

        # Snap-to-collapse threshold
        if target_width < 100:
            self.state.show_sidebar = False
            self.toggle_sidebar(tab_name=self.state.active_activity_tab)
            return

        # Min & Max bounds (150px to 500px or 45% of page)
        page_w = self.page.width if hasattr(self.page, "width") and self.page.width else 1200
        max_allowed = min(500, int(page_w * 0.45))
        clamped_width = max(150, min(int(round(target_width)), max_allowed))

        if hasattr(explorer_view, "update_responsive_width"):
            explorer_view.update_responsive_width(clamped_width)
        else:
            explorer_view.width = clamped_width
        self.state.sidebar_width = clamped_width

        try:
            if explorer_view.page:
                explorer_view.update()
        except Exception:
            pass

    def on_sidebar_resize_end(self):
        """Persist new sidebar width to settings when drag ends."""
        self._safe_save_settings()

    def on_sidebar_double_tap(self):
        """Reset sidebar width to default 240px or toggle visibility."""
        explorer_view = self.app_controls.get("explorer_view")
        if explorer_view:
            explorer_view.width = 240
            self.state.sidebar_width = 240
            self._safe_save_settings()
            try:
                if explorer_view.page:
                    explorer_view.update()
            except Exception:
                pass

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
            ribbon_bar = self.app_controls.get("ribbon_bar")
            if ribbon_bar and hasattr(ribbon_bar, "set_preview_visible"):
                ribbon_bar.set_preview_visible(self.state.show_preview)
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
            ribbon_bar = self.app_controls.get("ribbon_bar")
            if ribbon_bar and hasattr(ribbon_bar, "set_path_bar_visible"):
                ribbon_bar.set_path_bar_visible(self.state.show_path_bar)
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
            self._safe_save_settings()
            try:
                self.page.update()
            except Exception:
                pass

    # ── Workspace Tab Lifecycle Handlers ───────────────────────────────

    def handle_doc_tab_selected(self, tab_id: str):
        """
        Switches active document tab.
        Eagerly flushes outgoing tab content from EditorView into DocumentTabState,
        then hydrates EditorView and Preview with incoming tab state in 0ms (RAM cache).
        """
        editor_view = self.app_controls.get("editor_view")
        file_path_bar = self.app_controls.get("file_path_bar")
        preview = self.app_controls.get("preview")
        ribbon_bar = self.app_controls.get("ribbon_bar")
        tab_bar = self.app_controls.get("workspace_tab_bar")
        file_controller = self.app_controls.get("file_controller")
        explorer_view = self.app_controls.get("explorer_view")

        # 1. Eagerly flush outgoing tab
        outgoing_tab = self.state.active_tab
        if outgoing_tab and editor_view:
            current_text = editor_view.get_text()
            if current_text is not None:
                outgoing_tab.full_content = current_text
            if outgoing_tab.is_dirty and file_controller:
                file_controller.perform_autosave(outgoing_tab.tab_id)

        # 2. Activate incoming tab
        incoming_tab = self.state.activate_tab(tab_id)
        if not incoming_tab:
            return

        MediaAssetManager().set_active_session(incoming_tab.media_session_id)

        # 3. Hydrate EditorView
        if editor_view:
            editor_view.set_text(incoming_tab.full_content)

        # 4. Hydrate FilePathBar
        if file_path_bar:
            file_path_bar.set_in_path(incoming_tab.in_path)
            file_path_bar.set_out_path(incoming_tab.out_path)

        # 5. Hydrate RibbonBar Mode
        if ribbon_bar:
            ext = os.path.splitext(incoming_tab.in_path)[1].lower() if incoming_tab.in_path else ""
            def_mode = getattr(self.state, "default_mode", "")
            ribbon_bar.update_mode_options(ext, preferred_mode=def_mode or incoming_tab.current_mode)

        # 6. Hydrate Preview
        if preview:
            base_dir = os.path.dirname(incoming_tab.in_path) if incoming_tab.in_path else None
            is_heavy = len(incoming_tab.full_content) > 10000 or "```mermaid" in incoming_tab.full_content

            words = len(incoming_tab.full_content.split())
            chars = len(incoming_tab.full_content)
            preview.doc_info_text.value = t("editor.doc_info", words=f"{words:,}", chars=f"{chars:,}")

            if is_heavy:
                incoming_tab.is_loading = True
                if tab_bar and hasattr(tab_bar, "render_tabs"):
                    tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)

                async def _async_hydrate():
                    try:
                        preview.update_preview(incoming_tab.full_content, base_dir=base_dir)
                    except Exception as e:
                        print(f"[DEBUG] Preview hydration error: {e}")
                    finally:
                        incoming_tab.is_loading = False
                        if tab_bar and hasattr(tab_bar, "render_tabs"):
                            tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)
                        try:
                            self.page.update()
                        except Exception:
                            pass

                asyncio.create_task(_async_hydrate())
            else:
                preview.update_preview(incoming_tab.full_content, base_dir=base_dir)

        # 7. Update Window Title
        from src.__version__ import __version__
        self.page.title = f"{incoming_tab.title} — Document Converter v{__version__}"

        # 8. Re-render TabBar Visuals
        if tab_bar and hasattr(tab_bar, "render_tabs"):
            tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)

        # 9. Sync Explorer Selection
        if explorer_view and hasattr(explorer_view, "set_active_file") and incoming_tab.in_path:
            explorer_view.set_active_file(incoming_tab.in_path)

        # 10. Persist Tab Session Manifest
        if file_controller:
            file_controller.save_tab_session()

        try:
            self.page.update()
        except Exception:
            pass

    def handle_doc_tab_closed(self, tab_id: str):
        """Handles user clicking close button or pressing Ctrl+W on a document tab."""
        tab = self.state.find_tab_by_id(tab_id)
        if not tab:
            return

        # Check if tab has unsaved changes or orphaned status
        if tab.is_dirty or tab.is_orphaned:
            file_controller = self.app_controls.get("file_controller")

            def on_save_confirm():
                async def _save_and_close():
                    if file_controller:
                        if tab.in_path and os.path.exists(os.path.dirname(tab.in_path)):
                            file_controller.handle_save_shortcut()
                            self._force_close_tab(tab_id)
                        elif hasattr(file_controller, "async_save_markdown"):
                            saved = await file_controller.async_save_markdown()
                            if saved:
                                self._force_close_tab(tab_id)
                asyncio.create_task(_save_and_close())

            def on_discard_confirm():
                self._force_close_tab(tab_id)

            show_unsaved_tab_dialog(
                page=self.page,
                tab_title=tab.title,
                on_save=on_save_confirm,
                on_discard=on_discard_confirm,
            )
        else:
            self._force_close_tab(tab_id)

    def _force_close_tab(self, tab_id: str):
        """Removes tab from state, cleans up draft cache, and manages last-tab transition."""
        file_controller = self.app_controls.get("file_controller")
        tab_bar = self.app_controls.get("workspace_tab_bar")
        workspace_view = self.app_controls.get("workspace_view")
        ribbon_bar = self.app_controls.get("ribbon_bar")
        editor_view = self.app_controls.get("editor_view")
        preview = self.app_controls.get("preview")
        file_path_bar = self.app_controls.get("file_path_bar")

        self.state.close_tab(tab_id)

        if file_controller:
            file_controller.clear_tab_draft(tab_id)
            file_controller.save_tab_session()

        if len(self.state.tabs) == 0:
            if tab_bar and hasattr(tab_bar, "render_tabs"):
                tab_bar.render_tabs([], None)
            if editor_view:
                editor_view.set_text("")
            if preview:
                preview.update_preview("")
            if file_path_bar:
                file_path_bar.set_in_path("")
                file_path_bar.set_out_path("")

            has_workspace = bool(getattr(self.state, "workspace_folder", "") and os.path.exists(self.state.workspace_folder))
            if not has_workspace:
                # 1. No workspace folder open: Return cleanly to WelcomeView
                if workspace_view and hasattr(workspace_view, "show_welcome"):
                    workspace_view.show_welcome(ribbon_bar=ribbon_bar)
                from src.__version__ import __version__
                self.page.title = t("app.title", version=__version__)
            else:
                # 2. Workspace folder active: Keep Editor Workspace (Sidebar/Explorer visible), show empty editor
                folder_name = os.path.basename(self.state.workspace_folder) or self.state.workspace_folder
                from src.__version__ import __version__
                self.page.title = f"{folder_name} — Document Converter v{__version__}"
        else:
            # Switch to newly active tab
            self.handle_doc_tab_selected(self.state.active_tab_id)
            if tab_bar and hasattr(tab_bar, "render_tabs"):
                tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)

        try:
            self.page.update()
        except Exception:
            pass

    def handle_new_doc_tab(self):
        """Creates a fresh Untitled document tab and switches workspace into edit mode."""
        workspace_view = self.app_controls.get("workspace_view")
        ribbon_bar = self.app_controls.get("ribbon_bar")
        file_controller = self.app_controls.get("file_controller")

        new_tab = self.state.create_tab(
            title=t("tab.untitled"),
            mode=self.state.default_mode,
            activate=True,
        )

        if workspace_view and hasattr(workspace_view, "show_editor"):
            workspace_view.show_editor(ribbon_bar=ribbon_bar)

        self.handle_doc_tab_selected(new_tab.tab_id)
        if file_controller:
            file_controller.save_tab_session()

    def handle_doc_tab_reordered(self, source_id: str, target_id: str):
        """Reorders tabs in AppState.tabs and refreshes TabBar."""
        self.state.reorder_tabs(source_id, target_id)
        tab_bar = self.app_controls.get("workspace_tab_bar")
        if tab_bar and hasattr(tab_bar, "render_tabs"):
            tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)
        file_controller = self.app_controls.get("file_controller")
        if file_controller:
            file_controller.save_tab_session()

    def handle_next_doc_tab(self):
        """Switches to the next document tab (Ctrl+Tab / Ctrl+PageDown)."""
        if not self.state.tabs or len(self.state.tabs) <= 1:
            return
        idx = self.state.get_tab_index(self.state.active_tab_id)
        next_idx = (idx + 1) % len(self.state.tabs)
        self.handle_doc_tab_selected(self.state.tabs[next_idx].tab_id)

    def handle_prev_doc_tab(self):
        """Switches to the previous document tab (Ctrl+Shift+Tab / Ctrl+PageUp)."""
        if not self.state.tabs or len(self.state.tabs) <= 1:
            return
        idx = self.state.get_tab_index(self.state.active_tab_id)
        prev_idx = (idx - 1) % len(self.state.tabs)
        self.handle_doc_tab_selected(self.state.tabs[prev_idx].tab_id)


