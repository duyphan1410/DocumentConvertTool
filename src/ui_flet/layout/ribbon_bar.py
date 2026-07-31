"""
Office Ribbon Navbar Layout Component for Flet UI.
Provides a modern 4-Tab Office Ribbon Navbar (File, Edit, Convert, View)
with integrated Mode, Palette, Theme selectors, and Formatting Toolbar (Headings H1-H6).
"""
import flet as ft
from typing import Callable, Optional, TYPE_CHECKING
from src.__version__ import __version__
from src.ui_flet.constants import MODES
from src.ui_flet.theme import PALETTES, resolve_color
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
        self.search_replace_bar = search_replace_bar
        self._search_visible = False

        self.is_expanded = True
        self.active_tab = "edit"

        # ── Integrated Mode, Palette & Theme Selectors ───────────────────────────
        self.mode_dropdown = ft.Dropdown(
            label="Conversion Mode",
            value=current_mode,
            options=[ft.dropdown.Option(m) for m in MODES.keys()],
            width=175,
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
        self.btn_tab_options = ft.TextButton("Options", on_click=lambda _: self._select_tab("options"))

        self.btn_collapse = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_UP,
            tooltip="Toggle Ribbon Collapse/Expand",
            on_click=self._toggle_collapse
        )

        self.logo_icon = ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.PRIMARY, size=22)
        self.logo_text = ft.Text(
            f"DocConvert Workspace v{__version__}",
            weight=ft.FontWeight.BOLD,
            size=15
        )

        self.tab_strip = ft.Row(
            controls=[
                self.logo_icon,
                self.logo_text,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                self.btn_tab_file,
                self.btn_tab_edit,
                self.btn_tab_view,
                self.btn_tab_options,
                ft.Container(expand=True),
                self.mode_dropdown,
                self.btn_collapse,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4
        )

        # ── Tab Content Containers ───────────────────────────────────────────────
        self.file_tab_content = ft.Row(
            controls=[
                ft.OutlinedButton("Open Document", icon=ft.Icons.FOLDER_OPEN, on_click=self._on_browse_in_click),
                ft.OutlinedButton("Save Destination", icon=ft.Icons.SAVE_AS, on_click=self._on_browse_out_click),
                ft.OutlinedButton("Clear Editor", icon=ft.Icons.DELETE_OUTLINED, on_click=self._on_clear_click),
            ],
            spacing=8
        )

        # Edit tab: formatting toolbar row
        self.edit_tab_formatting = ft.Row(
            controls=[
                self.formatting_toolbar,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                ft.OutlinedButton("Find & Replace", icon=ft.Icons.SEARCH, on_click=self._on_search_click),
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

        self.view_tab_content = ft.Row(
            controls=[
                ft.OutlinedButton(
                    "Live Preview",
                    icon=ft.Icons.PREVIEW,
                    on_click=self._on_preview_click,
                    tooltip="Toggle Live Preview panel",
                ),
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                ft.OutlinedButton(
                    "File Path Bar",
                    icon=ft.Icons.FOLDER_OUTLINED,
                    on_click=self._on_toggle_file_path_bar_click,
                    tooltip="Toggle Input/Output path bar",
                ),
                ft.OutlinedButton(
                    "Editor Panel",
                    icon=ft.Icons.EDIT_NOTE_OUTLINED,
                    on_click=self._on_toggle_editor_click,
                    tooltip="Toggle Editor text panel",
                ),
                ft.OutlinedButton(
                    "Status Bar",
                    icon=ft.Icons.SPACE_DASHBOARD_OUTLINED,
                    on_click=self._on_toggle_status_bar_click,
                    tooltip="Toggle bottom status/action bar",
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.options_tab_content = ft.Row(
            controls=[
                self.palette_dropdown,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                self.theme_mode_dropdown,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8
        )

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
            spacing=2
        )
        self.content = self.main_column
        self.padding = ft.Padding(left=8, top=4, right=8, bottom=4)

    def update_mode_options(self, input_ext: str = ""):
        """Updates available modes in Ribbon mode dropdown."""
        if not input_ext:
            valid_modes = list(MODES.keys())
        else:
            valid_modes = [m for m, cfg in MODES.items() if cfg["in_ext"] == input_ext.lower()]
            if not valid_modes:
                valid_modes = list(MODES.keys())
        self.mode_dropdown.options = [ft.dropdown.Option(m) for m in valid_modes]
        if self.mode_dropdown.value not in valid_modes:
            self.mode_dropdown.value = valid_modes[0]
        if self.mode_dropdown.page:
            self.mode_dropdown.update()

    def _select_tab(self, tab_name: str):
        # Click active tab again to toggle collapse/expand
        if self.active_tab == tab_name and self.panel_container.visible:
            self._toggle_collapse(None)
            return

        self.active_tab = tab_name
        self.is_expanded = True
        self.panel_container.visible = True
        self.btn_collapse.icon = ft.Icons.KEYBOARD_ARROW_UP

        if tab_name == "file":
            self.panel_container.height = 60
            self.panel_container.content = self.file_tab_content
        elif tab_name == "edit":
            if self._search_visible:
                self._ensure_find_row_in_edit()
                self.panel_container.height = None
            else:
                self._remove_find_row_from_edit()
                self.panel_container.height = 60
            self.panel_container.content = self.edit_tab_content
        elif tab_name == "view":
            self.panel_container.height = 60
            self.panel_container.content = self.view_tab_content
        elif tab_name == "options":
            self.panel_container.height = 60
            self.panel_container.content = self.options_tab_content

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
        if visible is None:
            visible = not self._search_visible
        
        self._search_visible = visible
        if self.active_tab != "edit":
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

    def apply_palette(self, palette: dict, is_dark: bool):
        """Apply palette colors to the Ribbon bar and its dropdowns."""
        bg_header = resolve_color(palette, "bg_header", is_dark)
        bg_component = resolve_color(palette, "bg_component", is_dark)
        accent_primary = resolve_color(palette, "text_accent_primary", is_dark)
        btn_convert_fg = resolve_color(palette, "btn_convert_fg", is_dark)

        # Ribbon bar background (header area)
        self.bgcolor = bg_header

        # Panel container (active tab content area)
        self.panel_container.bgcolor = bg_component

        # Logo icon and text accent color
        self.logo_icon.color = accent_primary
        self.logo_text.color = accent_primary

        # Apply vibrant palette colors to all Ribbon dropdowns
        for dd in [self.mode_dropdown, self.palette_dropdown, self.theme_mode_dropdown]:
            dd.border_color = accent_primary
            dd.focused_border_color = accent_primary
            dd.color = accent_primary
            dd.label_style = ft.TextStyle(color=accent_primary)

        # Forward palette update to FormattingToolbar
        self.formatting_toolbar.apply_palette(palette, is_dark)

        try:
            self.update()
        except Exception:
            pass
