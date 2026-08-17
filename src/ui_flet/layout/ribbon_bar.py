"""
Office Ribbon Navbar Layout Component for Flet UI.
Provides a modern 4-Tab Office Ribbon Navbar (File, Edit, Convert, View)
with integrated Mode, Palette, Theme selectors, and Formatting Toolbar (Headings H1-H6).
"""
import os
import flet as ft
from typing import Callable, Optional, TYPE_CHECKING
from src.__version__ import __version__
from src.i18n import t
from src.ui_flet.constants import MODES, MODE_DISPLAY_KEYS
from src.ui_flet.theme import PALETTES, resolve_color, make_border
from src.ui_flet.components.formatting_toolbar import FormattingToolbar

if TYPE_CHECKING:
    from src.ui_flet.components.search_replace_bar import SearchReplaceBar

class RibbonBar(ft.Container):
    def __init__(
        self,
        current_mode: str = "MD -> Excel",
        current_palette: str = "Violet Cyberpunk",
        current_theme_mode: str = "Dark",
        on_mode_changed: Optional[Callable] = None,
        on_palette_changed: Optional[Callable] = None,
        on_theme_mode_changed: Optional[Callable] = None,
        on_browse_in: Optional[Callable] = None,
        on_browse_out: Optional[Callable] = None,
        on_clear_editor: Optional[Callable] = None,
        on_format_action: Optional[Callable[[str, str], None]] = None,
        on_heading_change: Optional[Callable[[int], None]] = None,
        on_toggle_search: Optional[Callable] = None,
        on_convert_click: Optional[Callable] = None,
        on_toggle_preview: Optional[Callable] = None,
        on_toggle_file_path_bar: Optional[Callable] = None,
        on_toggle_editor: Optional[Callable] = None,
        on_toggle_status_bar: Optional[Callable] = None,
        on_insert_image: Optional[Callable] = None,
        on_ribbon_toggle: Optional[Callable] = None,
        on_show_settings: Optional[Callable] = None,
        on_show_help: Optional[Callable] = None,
        on_show_editor: Optional[Callable] = None,
        search_replace_bar: Optional["SearchReplaceBar"] = None,
        **kwargs
    ):

        super().__init__(**kwargs)
        self.on_mode_changed = on_mode_changed
        self.on_palette_changed = on_palette_changed
        self.on_theme_mode_changed = on_theme_mode_changed
        self.on_browse_in = on_browse_in
        self.on_browse_out = on_browse_out
        self.on_clear_editor = on_clear_editor
        self.on_format_action = on_format_action
        self.on_heading_change = on_heading_change
        self.on_toggle_search = on_toggle_search
        self.on_convert_click = on_convert_click
        self.on_toggle_preview = on_toggle_preview
        self.on_toggle_file_path_bar = on_toggle_file_path_bar
        self.on_toggle_editor = on_toggle_editor
        self.on_toggle_status_bar = on_toggle_status_bar
        self.on_insert_image = on_insert_image
        self.on_ribbon_toggle = on_ribbon_toggle
        self.on_show_settings = on_show_settings
        self.on_show_help = on_show_help
        self.on_show_editor = on_show_editor
        self.search_replace_bar = search_replace_bar
        self._search_visible = False
        self._search_toggling = False  # re-entrant guard for toggle_search

        self.is_expanded = True
        self.active_tab = "edit"

        # ── Integrated Mode, Palette & Theme Selectors ───────────────────────────
        self.mode_dropdown = ft.Dropdown(
            label="Conversion Mode",
            value=current_mode,
            options=[ft.dropdown.Option(m) for m in MODES.keys()],
            width=210,
            dense=True,
        )
        self.mode_dropdown.on_change = self.on_mode_changed
        self.mode_dropdown.on_select = self.on_mode_changed

        self.palette_dropdown = ft.Dropdown(
            label="Palette",
            value=current_palette,
            options=[ft.dropdown.Option(p) for p in PALETTES.keys()],
            dense=True,
        )
        self.palette_dropdown.on_change = self.on_palette_changed
        self.palette_dropdown.on_select = self.on_palette_changed

        self.theme_mode_dropdown = ft.Dropdown(
            label="Theme",
            value=current_theme_mode,
            options=[
                ft.dropdown.Option("Dark"),
                ft.dropdown.Option("Light"),
                ft.dropdown.Option("System"),
            ],
            # width=110,
            dense=True,
        )
        self.theme_mode_dropdown.on_change = self.on_theme_mode_changed
        self.theme_mode_dropdown.on_select = self.on_theme_mode_changed

        # ── Formatting Toolbar Instance ──────────────────────────────────────────
        self.formatting_toolbar = FormattingToolbar(
            on_format_action=self.on_format_action,
            on_heading_change=self.on_heading_change,
            on_insert_image=self.on_insert_image,
        )

        # ── Tab Navigation Buttons ───────────────────────────────────────────────
        self.btn_tab_file = ft.TextButton("File", on_click=lambda _: self._select_tab("file"))
        self.btn_tab_edit = ft.TextButton("Edit", on_click=lambda _: self._select_tab("edit"))
        self.btn_tab_view = ft.TextButton("View", on_click=lambda _: self._select_tab("view"))
        self.btn_tab_settings = ft.TextButton("Settings", on_click=lambda _: self._select_tab("settings"))
        self.btn_tab_help = ft.TextButton("Help", on_click=lambda _: self._select_tab("help"))

        self._tabs_map = {
            "file": self.btn_tab_file,
            "edit": self.btn_tab_edit,
            "view": self.btn_tab_view,
            "settings": self.btn_tab_settings,
            "help": self.btn_tab_help,
        }

        self.btn_collapse = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_UP,
            tooltip="Toggle Ribbon Collapse/Expand",
            on_click=self._toggle_collapse
        )

        self.logo_icon = ft.Icon(
            ft.Icons.AUTO_AWESOME_ROUNDED,
            color=ft.Colors.PRIMARY,
            size=22,
        )

        self.logo_text = ft.Text(
            "DocConvert",
            weight=ft.FontWeight.BOLD,
            size=14,
        )

        self.mode_dropdown_container = ft.Container(
            content=self.mode_dropdown,
            padding=ft.Padding(left=8, top=4, right=8, bottom=8),
        )

        self.tab_strip = ft.Row(
            controls=[
                self.logo_icon,
                self.logo_text,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                self.btn_tab_file,
                self.btn_tab_edit,
                self.btn_tab_view,
                self.btn_tab_settings,
                self.btn_tab_help,
                ft.Container(expand=True),
                self.mode_dropdown_container,
                self.btn_collapse,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        )

        # ── Tab Content Containers ───────────────────────────────────────────────
        self.btn_tab_file_open = ft.OutlinedButton(content=ft.Text(t("ribbon.btn_open")), icon=ft.Icons.FOLDER_OPEN, on_click=self._on_browse_in_click)
        self.btn_tab_file_save = ft.OutlinedButton(content=ft.Text(t("ribbon.btn_save")), icon=ft.Icons.SAVE_AS, on_click=self._on_browse_out_click)
        self.btn_tab_file_clear = ft.OutlinedButton(content=ft.Text(t("ribbon.btn_clear")), icon=ft.Icons.DELETE_OUTLINED, on_click=self._on_clear_click)

        self.file_tab_content = ft.Row(
            controls=[
                self.btn_tab_file_open,
                self.btn_tab_file_save,
                self.btn_tab_file_clear,
            ],
            spacing=8
        )

        # Edit tab: formatting toolbar row
        self.btn_tab_edit_search = ft.OutlinedButton(content=ft.Text(t("ribbon.btn_search")), icon=ft.Icons.SEARCH, on_click=self._on_search_click)
        self.edit_tab_formatting = ft.Row(
            controls=[
                self.formatting_toolbar,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                self.btn_tab_edit_search,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        )

        # Edit tab: Find row always visible + collapsible Replace row via ▼
        self.edit_tab_content = ft.Column(
            controls=[
                self.edit_tab_formatting,
            ],
            spacing=4,
        )

        self.btn_tab_view_preview = ft.OutlinedButton(
            content=ft.Text(t("ribbon.btn_preview")),
            icon=ft.Icons.PREVIEW,
            on_click=self._on_preview_click,
            tooltip=t("ribbon.tooltip_preview"),
        )
        self.btn_tab_view_pathbar = ft.OutlinedButton(
            content=ft.Text(t("ribbon.btn_pathbar")),
            icon=ft.Icons.FOLDER_OUTLINED,
            on_click=self._on_toggle_file_path_bar_click,
            tooltip=t("ribbon.tooltip_pathbar"),
        )
        self.btn_tab_view_editor = ft.OutlinedButton(
            content=ft.Text(t("ribbon.btn_editor")),
            icon=ft.Icons.EDIT_NOTE_OUTLINED,
            on_click=self._on_toggle_editor_click,
            tooltip=t("ribbon.tooltip_editor"),
        )
        self.btn_tab_view_statusbar = ft.OutlinedButton(
            content=ft.Text(t("ribbon.btn_statusbar")),
            icon=ft.Icons.SPACE_DASHBOARD_OUTLINED,
            on_click=self._on_toggle_status_bar_click,
            tooltip=t("ribbon.tooltip_statusbar"),
        )

        self.view_tab_content = ft.Row(
            controls=[
                self.btn_tab_view_preview,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                self.btn_tab_view_pathbar,
                self.btn_tab_view_editor,
                self.btn_tab_view_statusbar,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Settings / Help tabs: panel is collapsed (workspace view takes over)
        self.settings_tab_content = ft.Container(height=0)
        self.help_tab_content = ft.Container(height=0)

        self.panel_container = ft.Container(
            content=self.edit_tab_content,
            padding=ft.Padding(left=12, top=2, right=12, bottom=2),
            height=60,
            alignment=ft.alignment.Alignment(-1.0, 0.0),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )

        self.main_column = ft.Column(
            controls=[
                self.tab_strip,
                self.panel_container,
            ],
            spacing=4
        )
        self.content = self.main_column
        self.border_radius = 10
        self.padding = ft.Padding(left=10, top=6, right=10, bottom=6)

        # Synchronize default active tab highlight and panel content at startup
        self._update_tab_highlights()

    def update_mode_options(self, input_ext: str = "", preferred_mode: str = ""):
        """Updates available modes in Ribbon mode dropdown, prioritizing preferred_mode if valid."""
        if not input_ext:
            valid_modes = list(MODES.keys())
        else:
            valid_modes = [m for m, cfg in MODES.items() if cfg["in_ext"] == input_ext.lower()]
            if not valid_modes:
                valid_modes = list(MODES.keys())
        self.mode_dropdown.options = [ft.dropdown.Option(m) for m in valid_modes]
        if preferred_mode and preferred_mode in valid_modes:
            self.mode_dropdown.value = preferred_mode
        elif self.mode_dropdown.value and self.mode_dropdown.value in valid_modes:
            pass
        else:
            self.mode_dropdown.value = valid_modes[0]

        if self.mode_dropdown.page:
            self.mode_dropdown.update()
        if self.on_mode_changed:
            try:
                self.on_mode_changed(None)
            except Exception as ex:
                print(f"[DEBUG] on_mode_changed error in update_mode_options: {ex}")

    def select_tab(self, tab_name: str, force: bool = False):
        """Programmatically or manually select a ribbon tab. If force=True, never toggle-collapse."""
        # Click active tab again to toggle collapse/expand or close settings/help unless force=True
        if not force and self.active_tab == tab_name:
            if tab_name in ("settings", "help"):
                if self.on_show_editor:
                    self.on_show_editor()
                return
            elif self.panel_container.visible:
                self._toggle_collapse(None)
                return

        self.active_tab = tab_name
        self.is_expanded = True
        self.panel_container.visible = True
        self.btn_collapse.icon = ft.Icons.KEYBOARD_ARROW_UP

        self._refresh_locale_strings()

        if tab_name == "file":
            self.panel_container.height = 60
            self.panel_container.content = self.file_tab_content
            if self.on_show_editor:
                self.on_show_editor()
        elif tab_name == "edit":
            if self._search_visible:
                self._ensure_find_row_in_edit()
                self.panel_container.height = None
            else:
                self._remove_find_row_from_edit()
                self.panel_container.height = 60
            self.panel_container.content = self.edit_tab_content
            if self.on_show_editor:
                self.on_show_editor()
        elif tab_name == "view":
            self.panel_container.height = 60
            self.panel_container.content = self.view_tab_content
            if self.on_show_editor:
                self.on_show_editor()
        elif tab_name == "settings":
            # SettingsView occupies workspace — collapse ribbon panel
            self.panel_container.visible = False
            self.is_expanded = False
            self.btn_collapse.icon = ft.Icons.KEYBOARD_ARROW_DOWN
            if self.on_show_settings:
                self.on_show_settings()
        elif tab_name == "help":
            # HelpView occupies workspace — collapse ribbon panel
            self.panel_container.visible = False
            self.is_expanded = False
            self.btn_collapse.icon = ft.Icons.KEYBOARD_ARROW_DOWN
            if self.on_show_help:
                self.on_show_help()

        # Hide or show results container based on tab visibility
        if self.search_replace_bar:
            if tab_name == "edit" and self._search_visible:
                # Trigger search matches update
                if self.on_toggle_search:
                    self.on_toggle_search(True)
            else:
                self.search_replace_bar.results_container.visible = False
                try:
                    if self.search_replace_bar.results_container.page:
                        self.search_replace_bar.results_container.update()
                except Exception:
                    pass
                if self.on_toggle_search:
                    self.on_toggle_search(False)

        if self.on_ribbon_toggle:
            self.on_ribbon_toggle()

        self._update_tab_highlights()
        try:
            self.update()
        except Exception:
            pass

    def _select_tab(self, tab_name: str):
        self.select_tab(tab_name, force=False)

    def deselect_all_tabs(self):
        """Collapse ribbon panel and clear active tab selection for Welcome Screen."""
        self.active_tab = ""
        self.is_expanded = False
        self.panel_container.visible = False
        self.btn_collapse.icon = ft.Icons.KEYBOARD_ARROW_DOWN
        if self.on_ribbon_toggle:
            self.on_ribbon_toggle()
        self._update_tab_highlights()
        try:
            self.update()
        except Exception:
            pass

    def _toggle_collapse(self, e):
        self.is_expanded = not self.is_expanded
        self.panel_container.visible = self.is_expanded
        self.btn_collapse.icon = ft.Icons.KEYBOARD_ARROW_UP if self.is_expanded else ft.Icons.KEYBOARD_ARROW_DOWN
        if self.on_ribbon_toggle:
            self.on_ribbon_toggle()
        self._update_tab_highlights()
        try:
            self.update()
        except Exception:
            pass

    def _on_browse_in_click(self, e):
        if self.on_browse_in:
            self.on_browse_in(e)

    def _on_browse_out_click(self, e):
        if self.on_browse_out:
            self.on_browse_out(e)

    def _on_clear_click(self, e):
        if self.on_clear_editor:
            self.on_clear_editor(e)

    def toggle_search(self, visible: Optional[bool] = None):
        """Programmatically toggle or set search panel visibility in Ribbon Bar."""
        # Guard against re-entrant / spammed calls while a toggle is still processing.
        if self._search_toggling:
            return
        self._search_toggling = True
        try:
            currently_viewing_find = (
                self.active_tab == "edit"
                and self.panel_container.visible
            )
            if visible is None:
                # Only close if user is actively on Edit tab seeing the Find bar.
                # If they've switched to another tab, Ctrl+F always re-opens.
                if currently_viewing_find:
                    visible = not self._search_visible
                else:
                    visible = True

            self._search_visible = visible
            # Re-open Edit tab only when not currently viewing it.
            if not currently_viewing_find:
                self._select_tab("edit")

            if self._search_visible:
                self._ensure_find_row_in_edit()
                self.panel_container.height = None
                if self.search_replace_bar:
                    self.search_replace_bar.focus_search_input()
            else:
                self._remove_find_row_from_edit()
                self.panel_container.height = 60
                if self.search_replace_bar:
                    self.search_replace_bar.results_container.visible = False
                    try:
                        if self.search_replace_bar.results_container.page:
                            self.search_replace_bar.results_container.update()
                    except Exception:
                        pass

            if self.on_toggle_search:
                self.on_toggle_search(self._search_visible)

            try:
                self.update()
            except Exception:
                pass
        finally:
            self._search_toggling = False


    def _on_search_click(self, e):
        """Toggle Find & Replace panel in Edit tab."""
        self.toggle_search()

    def _ensure_find_row_in_edit(self):
        """Adds Find container + Replace container to edit_tab_content."""
        if not self.search_replace_bar:
            return
        find_container = self.search_replace_bar.find_container
        replace_container = self.search_replace_bar.replace_container
        if find_container not in self.edit_tab_content.controls:
            self.edit_tab_content.controls.append(find_container)
        if replace_container not in self.edit_tab_content.controls:
            self.edit_tab_content.controls.append(replace_container)

    def _remove_find_row_from_edit(self):
        """Removes Find container + Replace container from edit_tab_content."""
        if not self.search_replace_bar:
            return
        find_container = self.search_replace_bar.find_container
        replace_container = self.search_replace_bar.replace_container
        if find_container in self.edit_tab_content.controls:
            self.edit_tab_content.controls.remove(find_container)
        if replace_container in self.edit_tab_content.controls:
            self.edit_tab_content.controls.remove(replace_container)

    def _on_convert_click_handler(self, e):
        if self.on_convert_click:
            self.on_convert_click(e)

    def _on_preview_click(self, e):
        if self.on_toggle_preview:
            self.on_toggle_preview(e)

    def _on_toggle_file_path_bar_click(self, e):
        if self.on_toggle_file_path_bar:
            self.on_toggle_file_path_bar(e)

    def _on_toggle_editor_click(self, e):
        if self.on_toggle_editor:
            self.on_toggle_editor(e)

    def _on_toggle_status_bar_click(self, e):
        if self.on_toggle_status_bar:
            self.on_toggle_status_bar(e)

    def _update_tab_highlights(self):
        """Highlight active tab with background container fill of palette accent_primary and clean white text."""
        palette = getattr(self, "_current_palette", None)
        is_dark = getattr(self, "_is_dark", True)
        accent_primary = resolve_color(palette, "text_accent_primary", is_dark) if palette else ft.Colors.PRIMARY

        for tab_name, btn in self._tabs_map.items():
            if tab_name in ("settings", "help"):
                is_active = (tab_name == self.active_tab)
            else:
                is_active = (tab_name == self.active_tab and self.panel_container.visible)

            if is_active:
                btn.style = ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding(left=14, top=8, right=14, bottom=8),
                    bgcolor=accent_primary,
                    color=ft.Colors.WHITE,
                )
            else:
                btn.style = ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding(left=14, top=8, right=14, bottom=8),
                    bgcolor=None,
                    color=ft.Colors.WHITE70 if is_dark else ft.Colors.BLACK87,
                )

    def apply_palette(self, palette: dict, is_dark: bool):
        """Apply palette colors to the Ribbon bar, active tabs, and its dropdowns."""
        self._current_palette = palette
        self._is_dark = is_dark

        bg_header = resolve_color(palette, "bg_header", is_dark)
        bg_component = resolve_color(palette, "bg_component", is_dark)
        accent_primary = resolve_color(palette, "text_accent_primary", is_dark)
        border_color = resolve_color(palette, "border_color", is_dark)

        # Ribbon bar background (header area)
        self.bgcolor = bg_header
        self.border_radius = 10
        self.border = make_border(1, border_color)

        # Panel container (active tab content area)
        self.panel_container.bgcolor = bg_component

        # Logo icon and text
        self.logo_icon.color = accent_primary
        self.logo_text.color = ft.Colors.WHITE if is_dark else ft.Colors.BLACK87

        # Apply clean readable styles to Ribbon dropdowns (White text, colored label & focus border)
        for dd in [self.mode_dropdown, self.palette_dropdown, self.theme_mode_dropdown]:
            dd.border_color = accent_primary
            dd.focused_border_color = accent_primary
            dd.color = ft.Colors.WHITE if is_dark else ft.Colors.BLACK87
            dd.label_style = ft.TextStyle(color=accent_primary, size=12)

        # Apply tab active highlights
        self._update_tab_highlights()

        # Style outlined buttons inside tab panel with Palette accent border and clean white text
        for btn in [
            self.btn_tab_file_open, self.btn_tab_file_save, self.btn_tab_file_clear,
            self.btn_tab_edit_search,
            self.btn_tab_view_preview, self.btn_tab_view_pathbar, self.btn_tab_view_editor, self.btn_tab_view_statusbar
        ]:
            if hasattr(btn, "style"):
                btn.style = ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    color=ft.Colors.WHITE if is_dark else ft.Colors.BLACK87,
                    side=ft.BorderSide(1, accent_primary),
                )

        # Forward palette update to FormattingToolbar
        self.formatting_toolbar.apply_palette(palette, is_dark)

        try:
            self.update()
        except Exception:
            pass

    def _refresh_locale_strings(self):
        """Refresh string values on ribbon tabs, buttons, tooltips, and mode dropdown."""
        def set_btn_text(btn, text_key):
            if hasattr(btn, "content"):
                if isinstance(btn.content, ft.Text):
                    btn.content.value = t(text_key)
                else:
                    btn.content = ft.Text(t(text_key))

        set_btn_text(self.btn_tab_file, "ribbon.tab_file")
        set_btn_text(self.btn_tab_edit, "ribbon.tab_edit")
        set_btn_text(self.btn_tab_view, "ribbon.tab_view")
        set_btn_text(self.btn_tab_settings, "ribbon.tab_settings")
        set_btn_text(self.btn_tab_help, "ribbon.tab_help")

        set_btn_text(self.btn_tab_file_open, "ribbon.btn_open")
        set_btn_text(self.btn_tab_file_save, "ribbon.btn_save")
        set_btn_text(self.btn_tab_file_clear, "ribbon.btn_clear")

        set_btn_text(self.btn_tab_edit_search, "ribbon.btn_search")

        set_btn_text(self.btn_tab_view_preview, "ribbon.btn_preview")
        set_btn_text(self.btn_tab_view_pathbar, "ribbon.btn_pathbar")
        set_btn_text(self.btn_tab_view_editor, "ribbon.btn_editor")
        set_btn_text(self.btn_tab_view_statusbar, "ribbon.btn_statusbar")

        self.logo_text.value = t("ribbon.logo")
        self.btn_collapse.tooltip = t("ribbon.tooltip_collapse")

        self.btn_tab_view_preview.tooltip = t("ribbon.tooltip_preview")
        self.btn_tab_view_pathbar.tooltip = t("ribbon.tooltip_pathbar")
        self.btn_tab_view_editor.tooltip = t("ribbon.tooltip_editor")
        self.btn_tab_view_statusbar.tooltip = t("ribbon.tooltip_statusbar")

        self.mode_dropdown.label = t("ribbon.label_mode")
        current_mode = self.mode_dropdown.value
        current_options = [opt.key for opt in self.mode_dropdown.options]
        self.mode_dropdown.options = [
            ft.dropdown.Option(m, t(MODE_DISPLAY_KEYS.get(m, m))) for m in current_options
        ]
        self.mode_dropdown.value = current_mode

        self.palette_dropdown.label = t("ribbon.label_palette")
        self.theme_mode_dropdown.label = t("ribbon.label_theme")
        self.theme_mode_dropdown.options = [
            ft.dropdown.Option("Dark", t("settings.theme_dark")),
            ft.dropdown.Option("Light", t("settings.theme_light")),
            ft.dropdown.Option("System", t("settings.theme_system")),
        ]

        if hasattr(self.formatting_toolbar, "update_locale"):
            self.formatting_toolbar.update_locale()
        if hasattr(self.search_replace_bar, "update_locale"):
            self.search_replace_bar.update_locale()

    def update_locale(self):
        """Refresh all text to current locale and force update controls."""
        self._refresh_locale_strings()

        for ctrl in [
            self.btn_tab_file, self.btn_tab_edit, self.btn_tab_view,
            self.btn_tab_settings, self.btn_tab_help, self.logo_text, self.btn_collapse,
            self.btn_tab_file_open, self.btn_tab_file_save, self.btn_tab_file_clear,
            self.btn_tab_edit_search,
            self.btn_tab_view_preview, self.btn_tab_view_pathbar,
            self.btn_tab_view_editor, self.btn_tab_view_statusbar,
            self.mode_dropdown, self.palette_dropdown, self.theme_mode_dropdown
        ]:
            try:
                if hasattr(ctrl, "page") and ctrl.page:
                    ctrl.update()
            except Exception:
                pass

        try:
            if self.tab_strip.page:
                self.tab_strip.update()
            if self.panel_container.page:
                self.panel_container.update()
            if self.page:
                self.update()
        except Exception:
            pass
