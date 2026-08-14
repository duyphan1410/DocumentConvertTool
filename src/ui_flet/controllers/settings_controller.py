"""
Settings Controller for DocConvert Workspace.
Handles all interactions from SettingsView: palette, theme, autosave, font size, default mode.
Saves to %APPDATA%/DocConvert/settings.json only on explicit Apply (apply_all).
"""
from __future__ import annotations

import os
import flet as ft
from src.ui_flet.state import AppState
from src.ui_flet.theme import PALETTES, apply_theme
from src.utils.settings_store import save_settings, load_settings_into


class SettingsController:
    """Bridges SettingsView UI events with AppState and persistence."""

    def __init__(self, page: ft.Page, state: AppState, app_controls: dict):
        self.page = page
        self.state = state
        self.app_controls = app_controls

    # ─────────────────────────────────────────────────────────────────────────
    # Startup
    # ─────────────────────────────────────────────────────────────────────────

    def load_and_apply(self):
        """Load settings.json -> AppState -> sync SettingsView and RibbonBar controls."""
        load_settings_into(self.state)
        if self.state.default_mode:
            self.state.current_mode = self.state.default_mode
        self._sync_ribbon_dropdowns()
        self._sync_settings_view()
        self.apply_word_wrap()
        from src.i18n import set_locale
        set_locale(self.state.language)
        self._rebuild_all_ui_text()
        theme_ctrl = self.app_controls.get("theme_controller")
        if theme_ctrl:
            theme_ctrl.update_theme_colors()
        layout_ctrl = self.app_controls.get("layout_controller")
        if layout_ctrl and hasattr(layout_ctrl, "apply_panel_visibility"):
            layout_ctrl.apply_panel_visibility()

    # ─────────────────────────────────────────────────────────────────────────
    # Explicit Apply / Discard
    # ─────────────────────────────────────────────────────────────────────────

    def apply_all(self, e=None):
        """Persist current AppState settings to JSON. Called when user clicks Apply."""
        from src.i18n import t
        from src.ui_flet.constants import MODES
        if self.state.default_mode and self.state.default_mode in MODES:
            ext = os.path.splitext(self.state.in_path)[1].lower() if self.state.in_path else ""
            if not ext or MODES[self.state.default_mode]["in_ext"] == ext:
                self.state.current_mode = self.state.default_mode
                self._sync_ribbon_dropdowns()
                file_path_bar = self.app_controls.get("file_path_bar")
                if file_path_bar:
                    mode_cfg = MODES[self.state.current_mode]
                    file_path_bar.set_in_label(mode_cfg["in_label"])
                    file_path_bar.set_out_label(mode_cfg["out_label"])
                    expected_ext = mode_cfg["out_ext"]
                    if self.state.out_path:
                        base, _ = os.path.splitext(self.state.out_path)
                        self.state.out_path = f"{base}{expected_ext}"
                        file_path_bar.set_out_path(self.state.out_path)
        save_settings(self.state)
        import time
        timestamp = time.strftime("%H:%M:%S")
        print(f"[LOG][SETTINGS][{timestamp}] Settings saved to settings.json")
        footer_bar = self.app_controls.get("footer_bar")
        if footer_bar:
            footer_bar.set_status_key("settings.saved_status", color=ft.Colors.GREEN_400, timestamp=timestamp)
            try:
                if self.page:
                    self.page.update()
            except Exception:
                pass
        settings_view = self.app_controls.get("settings_view")
        if settings_view and hasattr(settings_view, "mark_clean"):
            settings_view.mark_clean()

    def discard_all(self, e=None):
        """Reload state from JSON and revert UI. Called when user clicks Discard."""
        load_settings_into(self.state)
        if self.state.default_mode:
            self.state.current_mode = self.state.default_mode
        # Re-apply theme from restored state
        apply_theme(self.page, self.state.current_palette, self.state.current_theme_mode)
        theme_ctrl = self.app_controls.get("theme_controller")
        if theme_ctrl:
            theme_ctrl.update_theme_colors()
        self._sync_ribbon_dropdowns()
        from src.i18n import set_locale
        set_locale(self.state.language)
        self._rebuild_all_ui_text()
        self._sync_settings_view()
        self.apply_word_wrap()
        self.apply_font_size()
        layout_ctrl = self.app_controls.get("layout_controller")
        if layout_ctrl and hasattr(layout_ctrl, "apply_panel_visibility"):
            layout_ctrl.apply_panel_visibility()

    # ─────────────────────────────────────────────────────────────────────────
    # Individual setting handlers (preview-only, no JSON save)
    # ─────────────────────────────────────────────────────────────────────────

    def on_palette_changed(self, e):
        """
        Palette changed from SettingsView dropdown.
        FIX: reads value directly from event/dropdown, bypasses ThemeController.on_palette_changed
        (which reads from ribbon_bar.palette_dropdown and would overwrite our state update).
        """
        # 1. Read new value from event control first, fallback to settings_view dropdown
        new_palette = None
        if e and hasattr(e, "control") and e.control is not None:
            new_palette = getattr(e.control, "value", None)
        if not new_palette:
            sv = self.app_controls.get("settings_view")
            if sv and hasattr(sv, "_palette_dropdown"):
                new_palette = sv._palette_dropdown.value

        if not new_palette:
            return

        # 2. Update AppState
        self.state.current_palette = new_palette

        # 3. Sync ribbon palette dropdown BEFORE applying theme
        ribbon_bar = self.app_controls.get("ribbon_bar")
        if ribbon_bar and hasattr(ribbon_bar, "palette_dropdown"):
            ribbon_bar.palette_dropdown.value = new_palette
            try:
                if ribbon_bar.palette_dropdown.page:
                    ribbon_bar.palette_dropdown.update()
            except Exception:
                pass

        # 4. Apply theme & refresh all UI colors directly (bypass ThemeController.on_palette_changed)
        apply_theme(self.page, self.state.current_palette, self.state.current_theme_mode)
        theme_ctrl = self.app_controls.get("theme_controller")
        if theme_ctrl:
            theme_ctrl.update_theme_colors()

    def on_theme_mode_changed(self, e):
        """Theme mode changed from SettingsView radio group."""
        new_mode = None
        if e and hasattr(e, "control") and e.control is not None:
            new_mode = getattr(e.control, "value", None)
        if not new_mode:
            sv = self.app_controls.get("settings_view")
            if sv and hasattr(sv, "_theme_radio"):
                new_mode = sv._theme_radio.value

        if not new_mode:
            return

        self.state.current_theme_mode = new_mode
        apply_theme(self.page, self.state.current_palette, self.state.current_theme_mode)

        theme_ctrl = self.app_controls.get("theme_controller")
        if theme_ctrl:
            theme_ctrl.update_theme_colors()

        # Sync ribbon theme dropdown
        ribbon_bar = self.app_controls.get("ribbon_bar")
        if ribbon_bar and hasattr(ribbon_bar, "theme_mode_dropdown"):
            ribbon_bar.theme_mode_dropdown.value = new_mode
            try:
                if ribbon_bar.theme_mode_dropdown.page:
                    ribbon_bar.theme_mode_dropdown.update()
            except Exception:
                pass

    def on_autosave_toggled(self, e):
        """Autosave switch toggled -> update state (no JSON save yet)."""
        sv = self.app_controls.get("settings_view")
        if sv and hasattr(sv, "_autosave_switch"):
            self.state.autosave_enabled = sv._autosave_switch.value

    def on_autosave_interval_changed(self, e):
        """Autosave interval changed -> update state (no JSON save yet)."""
        # Read from event control value directly
        val_str = None
        if e and hasattr(e, "control") and e.control is not None:
            val_str = getattr(e.control, "value", None)
        if not val_str:
            sv = self.app_controls.get("settings_view")
            if sv and hasattr(sv, "_autosave_interval_dropdown"):
                val_str = sv._autosave_interval_dropdown.value
        try:
            self.state.autosave_interval_sec = int(val_str or "30")
        except (ValueError, TypeError):
            pass

    def apply_font_size(self):
        """Apply current font size from AppState to EditorView and MarkdownPreview."""
        size = getattr(self.state, "editor_font_size", 13)
        editor_view = self.app_controls.get("editor_view")
        if editor_view and hasattr(editor_view, "set_font_size"):
            editor_view.set_font_size(size)

        preview = self.app_controls.get("preview")
        if preview and hasattr(preview, "set_font_size"):
            preview.set_font_size(size)

    def on_font_size_changed(self, value: int):
        """Font size slider changed -> update AppState and EditorView text field."""
        self.state.editor_font_size = value
        self.apply_font_size()

    def on_default_mode_changed(self, e):
        """
        Default mode dropdown changed -> update state and RibbonBar mode.
        """
        new_mode = None
        if e and hasattr(e, "control") and e.control is not None:
            new_mode = getattr(e.control, "value", None)
        if not new_mode:
            sv = self.app_controls.get("settings_view")
            if sv and hasattr(sv, "_default_mode_dropdown"):
                new_mode = sv._default_mode_dropdown.value
        if new_mode:
            self.state.default_mode = new_mode
            self.state.current_mode = new_mode
            self._sync_ribbon_dropdowns()

    def on_word_wrap_changed(self, e):
        """Word wrap switch toggled -> update state and apply to Editor & Preview."""
        val = None
        if e and hasattr(e, "control") and e.control is not None:
            val = getattr(e.control, "value", None)
        if val is None:
            sv = self.app_controls.get("settings_view")
            if sv and hasattr(sv, "_word_wrap_switch"):
                val = sv._word_wrap_switch.value
        if val is not None:
            self.state.word_wrap = bool(val)
            self.apply_word_wrap()

    def apply_word_wrap(self):
        """Applies state.word_wrap setting to both EditorView and MarkdownPreview."""
        editor_view = self.app_controls.get("editor_view")
        preview = self.app_controls.get("preview")
        is_wrap = getattr(self.state, "word_wrap", True)

        if editor_view and hasattr(editor_view, "set_word_wrap"):
            try:
                editor_view.set_word_wrap(is_wrap)
            except Exception:
                pass

        if preview and hasattr(preview, "set_word_wrap"):
            try:
                preview.set_word_wrap(is_wrap)
            except Exception:
                pass

    def on_language_changed(self, e):
        """Language dropdown changed -> set locale and refresh all UI text."""
        new_lang = None
        if e and hasattr(e, "control") and e.control is not None:
            new_lang = getattr(e.control, "value", None)
        if not new_lang:
            sv = self.app_controls.get("settings_view")
            if sv and hasattr(sv, "_language_dropdown"):
                new_lang = sv._language_dropdown.value
        if new_lang:
            self.state.language = new_lang
            from src.i18n import set_locale
            set_locale(new_lang)
            self._rebuild_all_ui_text()

    def _rebuild_all_ui_text(self):
        """Walk all registered UI components and trigger update_locale()."""
        from src.i18n import t
        from src.__version__ import __version__
        try:
            self.page.title = t("app.title", version=__version__)
        except Exception:
            pass

        for key in [
            "ribbon_bar",
            "welcome_view",
            "editor_view",
            "preview",
            "settings_view",
            "file_path_bar",
            "search_replace_bar",
            "footer_bar",
            "formatting_toolbar",
        ]:
            ctrl = self.app_controls.get(key)
            if ctrl and hasattr(ctrl, "update_locale"):
                try:
                    ctrl.update_locale()
                except Exception as ex:
                    print(f"[DEBUG] Error updating locale for {key}: {ex}")

        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # Internal sync helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _sync_ribbon_dropdowns(self):
        """Push loaded AppState values to RibbonBar selectors."""
        ribbon_bar = self.app_controls.get("ribbon_bar")
        if not ribbon_bar:
            return
        try:
            ribbon_bar.palette_dropdown.value = self.state.current_palette
            ribbon_bar.theme_mode_dropdown.value = self.state.current_theme_mode
            if hasattr(ribbon_bar, "mode_dropdown"):
                ribbon_bar.mode_dropdown.value = self.state.current_mode
                if ribbon_bar.mode_dropdown.page:
                    ribbon_bar.mode_dropdown.update()
        except Exception:
            pass

        # Trigger mode change event in App if registered
        on_mode_changed = self.app_controls.get("on_mode_changed")
        if on_mode_changed:
            try:
                on_mode_changed()
            except Exception:
                pass

    def _sync_settings_view(self):
        """Push loaded AppState values to SettingsView controls (rebuild active panel)."""
        sv = self.app_controls.get("settings_view")
        if sv and hasattr(sv, "sync_from_state"):
            try:
                sv.sync_from_state(self.state)
            except Exception:
                pass

