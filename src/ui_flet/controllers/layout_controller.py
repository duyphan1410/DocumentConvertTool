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

        editor_ctrl = editor_view.container if hasattr(editor_view, "container") else editor_view
        controls_to_add = (
            [activity_bar, explorer_view, sidebar_splitter, editor_ctrl, editor_splitter, right_pane]
            if is_left
            else [editor_ctrl, editor_splitter, right_pane, sidebar_splitter, explorer_view, activity_bar]
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

