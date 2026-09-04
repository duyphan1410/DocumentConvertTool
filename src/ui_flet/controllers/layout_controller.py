"""
Layout Controller for Flet UI.
Manages panel visibility toggles (Preview pane, File path bar, Editor panel, Status bar) and editor dynamic height math.
"""
import os
import time
import asyncio
import flet as ft
from src.i18n import t
from src.ui_flet.state import AppState
from src.utils.settings_store import save_settings
from src.services.media_asset_manager import MediaAssetManager
from src.ui_flet.components.file_modals import show_unsaved_tab_dialog
from src.ui_flet.views.preview_view import process_markdown_media_async


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
            welcome_view = self.app_controls.get("welcome_view")
            if welcome_view and hasattr(welcome_view, "update_responsive_layout"):
                welcome_view.update_responsive_layout(int(w))

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
        self.state.is_ui_resizing = True
        editor_view = self.app_controls.get("editor_view")
        right_pane = self.app_controls.get("right_pane")
        editor_split_row = self.app_controls.get("editor_split_row")
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
            if editor_split_row and editor_split_row.page:
                editor_split_row.update()
            elif editor_workspace and editor_workspace.page:
                editor_workspace.update()
        except Exception:
            pass

    def on_editor_resize_end(self):
        """Persist editor ratio to settings when drag ends."""
        self.state.is_ui_resizing = False
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

        if is_open and current_active == tab_name:
            # Clicked active tab or pressed Ctrl+B while open -> collapse
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
        self.state.is_ui_resizing = True
        explorer_view = self.app_controls.get("explorer_view")
        if not explorer_view:
            return

        is_left = getattr(self.state, "sidebar_position", "left") == "left"
        actual_delta = delta_x if is_left else -delta_x

        cur_width = explorer_view.width or getattr(self.state, "sidebar_width", 240)
        target_width = cur_width + actual_delta

        # Snap-to-collapse threshold
        if target_width < 100:
            self.state.is_ui_resizing = False
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
        self.state.is_ui_resizing = False
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
            if right_pane.visible:
                editor_view = self.app_controls.get("editor_view")
                preview = self.app_controls.get("preview")
                if editor_view and preview:
                    active_tab = self.state.active_tab
                    session_id = active_tab.media_session_id if active_tab else None
                    base_dir = os.path.dirname(self.state.in_path) if self.state.in_path else None
                    current_text = editor_view.get_text()
                    preview.update_preview(current_text, base_dir=base_dir, session_id=session_id)
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
        Activates selected document tab, hydrates EditorView, FilePathBar, Mode dropdown, and Preview.
        Eagerly flushes outgoing tab buffer to prevent data-loss on fast clicking.
        """
        t_switch_0 = time.time()
        editor_view = self.app_controls.get("editor_view")
        file_path_bar = self.app_controls.get("file_path_bar")
        ribbon_bar = self.app_controls.get("ribbon_bar")
        preview = self.app_controls.get("preview")
        tab_bar = self.app_controls.get("workspace_tab_bar")
        file_controller = self.app_controls.get("file_controller")
        explorer_view = self.app_controls.get("explorer_view")

        outgoing_tab = self.state.active_tab
        print(f"[LOG][TAB_SWITCH] Starting switch: from={getattr(outgoing_tab, 'title', None)} ({self.state.active_tab_id}) -> to={tab_id}")

        # 1. Eagerly flush outgoing tab
        if (
            outgoing_tab
            and outgoing_tab.tab_id != tab_id
            and not outgoing_tab.is_loading
            and editor_view
            and not getattr(editor_view.editor, "read_only", False)
        ):
            current_text = editor_view.get_text()
            if current_text is not None and not current_text.startswith("⏳ Loading"):
                outgoing_tab.full_content = current_text
            if outgoing_tab.is_dirty and file_controller:
                file_controller.perform_autosave(outgoing_tab.tab_id)

        t_flush = time.time() - t_switch_0

        # 2. Activate incoming tab
        incoming_tab = self.state.activate_tab(tab_id)
        if not incoming_tab:
            print(f"[LOG][TAB_SWITCH][WARN] incoming_tab {tab_id} not found in state!")
            return

        MediaAssetManager().set_active_session(incoming_tab.media_session_id)

        # 3. Hydrate EditorView
        if editor_view:
            editor_view.set_text(incoming_tab.full_content)

        t_editor = time.time() - t_switch_0

        # 4. Hydrate FilePathBar
        if file_path_bar:
            file_path_bar.set_in_path(incoming_tab.in_path)
            file_path_bar.set_out_path(incoming_tab.out_path)

        # 5. Hydrate RibbonBar Mode
        if ribbon_bar:
            ext = os.path.splitext(incoming_tab.in_path)[1].lower() if incoming_tab.in_path else ""
            def_mode = getattr(self.state, "default_mode", "")
            ribbon_bar.update_mode_options(ext, preferred_mode=incoming_tab.current_mode or def_mode)

        # 6. Hydrate Preview
        if preview:
            base_dir = os.path.dirname(incoming_tab.in_path) if incoming_tab.in_path else None
            words = len(incoming_tab.full_content.split())
            chars = len(incoming_tab.full_content)
            preview.doc_info_text.value = t("editor.doc_info", words=f"{words:,}", chars=f"{chars:,}")

            has_cache = bool(incoming_tab.cached_preview_md)
            print(f"[LOG][TAB_SWITCH] Tab '{incoming_tab.title}' has cached preview: {has_cache} (len={len(incoming_tab.cached_preview_md) if has_cache else 0})")

            if incoming_tab.cached_preview_md:
                # 0ms Instant Hydration from RAM cache: zero disk I/O, zero base64 re-encoding, zero UI block!
                preview.set_processed_content(
                    incoming_tab.cached_preview_md,
                    incoming_tab.full_content,
                    base_dir=base_dir,
                    session_id=incoming_tab.media_session_id,
                )
                print(f"[LOG][TAB_SWITCH] 0ms Instant RAM preview applied for '{incoming_tab.title}' in {time.time() - t_switch_0:.3f}s")
            else:
                is_heavy = (
                    len(incoming_tab.full_content) > 10000
                    or "```mermaid" in incoming_tab.full_content
                    or "![" in incoming_tab.full_content
                )
                print(f"[LOG][TAB_SWITCH] No cache, is_heavy={is_heavy}. Launching hydration...")

                if is_heavy:
                    if not getattr(incoming_tab, "_is_hydrating", False):
                        incoming_tab._is_hydrating = True

                        async def _async_hydrate():
                            t_h0 = time.time()
                            try:
                                is_dark = getattr(preview, "_is_dark", False)
                                palette_name = getattr(preview, "_palette_name", "Deep Ocean")
                                processed_md = await process_markdown_media_async(
                                    incoming_tab.full_content,
                                    base_dir=base_dir,
                                    is_dark=is_dark,
                                    palette_name=palette_name,
                                    session_id=incoming_tab.media_session_id,
                                )
                                incoming_tab.cached_preview_md = processed_md
                                print(f"[LOG][TAB_SWITCH] Async hydration computed in {time.time() - t_h0:.3f}s (cached_len={len(processed_md)})")

                                # UI CONCURRENCY GUARD: Only mutate preview widget if incoming_tab is STILL the active tab
                                if self.state.active_tab_id == incoming_tab.tab_id:
                                    preview.set_processed_content(
                                        processed_md,
                                        incoming_tab.full_content,
                                        base_dir=base_dir,
                                        session_id=incoming_tab.media_session_id,
                                    )
                                    try:
                                        self.page.update()
                                    except Exception:
                                        pass
                            except Exception as e:
                                print(f"[DEBUG] Preview hydration error: {e}")
                            finally:
                                incoming_tab._is_hydrating = False
                                footer_bar = self.app_controls.get("footer_bar")
                                if footer_bar and self.state.active_tab_id == incoming_tab.tab_id:
                                    footer_bar.set_processing(getattr(incoming_tab, "is_loading", False))
                                if tab_bar and hasattr(tab_bar, "render_tabs"):
                                    tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)
                                try:
                                    self.page.update()
                                except Exception:
                                    pass

                        asyncio.create_task(_async_hydrate())
                else:
                    preview.update_preview(
                        incoming_tab.full_content,
                        base_dir=base_dir,
                        session_id=incoming_tab.media_session_id,
                    )
                    print(f"[LOG][TAB_SWITCH] Standard preview applied for '{incoming_tab.title}' in {time.time() - t_switch_0:.3f}s")

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

        # 11. Hydrate FooterBar (Per-Tab conversion result & status)
        footer_bar = self.app_controls.get("footer_bar")
        if footer_bar:
            footer_bar.set_processing(incoming_tab.is_loading)
            has_valid_converted = bool(
                incoming_tab.last_converted_path
                and os.path.exists(incoming_tab.last_converted_path)
            )
            footer_bar.set_result_buttons_visible(has_valid_converted)
            if has_valid_converted:
                fname = os.path.basename(incoming_tab.last_converted_path)
                footer_bar.set_status(
                    f"✓ {fname}",
                    color=ft.Colors.GREEN_400,
                )
            elif incoming_tab.is_loading:
                footer_bar.set_status_key("status.file_loading", filename=incoming_tab.title)
            else:
                footer_bar.set_status_key("footer.status_ready")

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

        # 1. Trích xuất media_session_id TRƯỚC KHI close_tab
        tab_to_close = self.state.find_tab_by_id(tab_id)
        sid = tab_to_close.media_session_id if tab_to_close else None

        self.state.close_tab(tab_id)

        if file_controller:
            file_controller.clear_tab_draft(tab_id, media_session_id=sid)
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
            if ribbon_bar and hasattr(ribbon_bar, "update_mode_options"):
                def_mode = getattr(self.state, "default_mode", "MD -> Excel")
                ribbon_bar.update_mode_options("", preferred_mode=def_mode)

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

    def _close_tabs_sequentially(self, tab_ids: list[str]):
        """
        Closes a sequence of tabs safely and sequentially.
        For clean tabs, closes them immediately.
        For dirty tabs, prompts confirmation one by one.
        If user clicks Cancel, the batch closing aborts.
        """
        if not tab_ids:
            return

        current_id = tab_ids[0]
        remaining_ids = tab_ids[1:]

        tab = self.state.find_tab_by_id(current_id)
        if not tab:
            self._close_tabs_sequentially(remaining_ids)
            return

        if tab.is_dirty or tab.is_orphaned:
            file_controller = self.app_controls.get("file_controller")

            # Switch to this tab so user clearly sees what document they are saving/discarding
            self.handle_doc_tab_selected(current_id)

            def on_save_confirm():
                async def _save_and_next():
                    if file_controller:
                        if tab.in_path and os.path.exists(os.path.dirname(tab.in_path)):
                            file_controller.handle_save_shortcut()
                            self._force_close_tab(current_id)
                            self._close_tabs_sequentially(remaining_ids)
                        elif hasattr(file_controller, "async_save_markdown"):
                            saved = await file_controller.async_save_markdown()
                            if saved:
                                self._force_close_tab(current_id)
                                self._close_tabs_sequentially(remaining_ids)
                asyncio.create_task(_save_and_next())

            def on_discard_confirm():
                self._force_close_tab(current_id)
                self._close_tabs_sequentially(remaining_ids)

            def on_cancel():
                # User cancelled -> abort closing the rest of tabs to avoid data loss
                pass

            show_unsaved_tab_dialog(
                page=self.page,
                tab_title=tab.title,
                on_save=on_save_confirm,
                on_discard=on_discard_confirm,
                on_cancel=on_cancel,
            )
        else:
            self._force_close_tab(current_id)
            self._close_tabs_sequentially(remaining_ids)

    def handle_close_other_tabs(self, keep_tab_id: str):
        """Closes all tabs except the specified keep_tab_id with sequential confirmation."""
        tabs_to_close = [t.tab_id for t in list(self.state.tabs) if t.tab_id != keep_tab_id]
        self._close_tabs_sequentially(tabs_to_close)

    def handle_close_tabs_to_right(self, from_tab_id: str):
        """Closes all tabs to the right of from_tab_id with sequential confirmation."""
        idx = self.state.get_tab_index(from_tab_id)
        if idx < 0:
            return
        tabs_to_close = [t.tab_id for t in list(self.state.tabs[idx + 1:])]
        self._close_tabs_sequentially(tabs_to_close)

    def handle_close_all_tabs(self):
        """Closes all document tabs with sequential confirmation for dirty tabs."""
        tabs_to_close = [t.tab_id for t in list(self.state.tabs)]
        self._close_tabs_sequentially(tabs_to_close)



