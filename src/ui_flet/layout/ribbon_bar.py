"""
Simplified Single-Row Ribbon Layout Component for Flet UI.
Provides a modern, ultra-compact single-row Ribbon Bar (38–40px)
integrating File I/O actions, Heading selector (H1-H6), Markdown formatting tools,
Search & Replace toggle, Conversion Mode selector, and View toggles.
"""
import os
import flet as ft
from typing import Callable, Optional, TYPE_CHECKING
from src.__version__ import __version__
from src.i18n import t
from src.ui_flet.constants import MODES, MODE_DISPLAY_KEYS
from src.ui_flet.theme import PALETTES, resolve_color, make_border
from src.ui_flet.components.formatting_toolbar import FormattingToolbar

from src.ui_flet.helpers.image_token_helper import ImageTokenInfo

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
        on_import_youtube: Optional[Callable] = None,
        on_open_model_hub: Optional[Callable] = None,
        on_format_action: Optional[Callable[[str, str], None]] = None,
        on_heading_change: Optional[Callable[[int], None]] = None,
        on_toggle_search: Optional[Callable] = None,
        on_convert_click: Optional[Callable] = None,
        on_toggle_preview: Optional[Callable] = None,
        on_toggle_file_path_bar: Optional[Callable] = None,
        on_toggle_editor: Optional[Callable] = None,
        on_toggle_status_bar: Optional[Callable] = None,
        on_insert_image: Optional[Callable] = None,
        on_image_size_preset: Optional[Callable[[str], None]] = None,
        on_image_align_preset: Optional[Callable[[str], None]] = None,
        on_open_image_size_dialog: Optional[Callable[[], None]] = None,
        on_replace_image: Optional[Callable[[], None]] = None,
        on_reset_image_size: Optional[Callable[[], None]] = None,
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
        self.on_import_youtube = on_import_youtube
        self.on_open_model_hub = on_open_model_hub
        self.on_format_action = on_format_action
        self.on_heading_change = on_heading_change
        self.on_toggle_search = on_toggle_search
        self.on_convert_click = on_convert_click
        self.on_toggle_preview = on_toggle_preview
        self.on_toggle_file_path_bar = on_toggle_file_path_bar
        self.on_toggle_editor = on_toggle_editor
        self.on_toggle_status_bar = on_toggle_status_bar
        self.on_insert_image = on_insert_image
        self.on_image_size_preset = on_image_size_preset
        self.on_image_align_preset = on_image_align_preset
        self.on_open_image_size_dialog = on_open_image_size_dialog
        self.on_replace_image = on_replace_image
        self.on_reset_image_size = on_reset_image_size
        self.on_ribbon_toggle = on_ribbon_toggle
        self.on_show_settings = on_show_settings
        self.on_show_help = on_show_help
        self.on_show_editor = on_show_editor
        self.search_replace_bar = search_replace_bar

        self.active_image_token: Optional[ImageTokenInfo] = None

        self._search_visible = False
        self._search_toggling = False
        self.is_expanded = True
        self.active_tab = "edit"
        self._is_preview_visible = True
        self._is_path_bar_visible = True

        # Ribbon-specific ultra-sleek micro scrollbar (3px) for both Light and Dark modes
        self.theme = ft.Theme(
            scrollbar_theme=ft.ScrollbarTheme(
                thickness=3,
                radius=2,
                track_visibility=False,
                thumb_visibility=False,
                interactive=True,
            )
        )
        self.dark_theme = self.theme

        # ── 1. Branding / Logo ──────────────────────────────────────────────────
        self.logo_icon = ft.Icon(
            ft.Icons.AUTO_AWESOME_ROUNDED,
            color=ft.Colors.PRIMARY,
            size=20,
        )
        self.logo_text = ft.Text(
            "DocConvert",
            weight=ft.FontWeight.BOLD,
            size=13,
        )

        # ── 2. Integrated Mode, Palette & Theme Selectors ────────────────────────
        self.mode_dropdown = ft.Dropdown(
            label="Conversion Mode",
            value=current_mode,
            options=[ft.dropdown.Option(m, t(MODE_DISPLAY_KEYS.get(m, m))) for m in MODES.keys()],
            width=165,
            dense=True,
        )
        self.mode_dropdown.on_change = self.on_mode_changed
        self.mode_dropdown.on_select = self.on_mode_changed

        self.palette_dropdown = ft.Dropdown(
            label="Palette",
            value=current_palette,
            options=[ft.dropdown.Option(p) for p in PALETTES.keys()],
            dense=True,
            visible=False,  # Accessible via Settings dialog/view
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
            dense=True,
            visible=False,  # Accessible via Settings dialog/view
        )
        self.theme_mode_dropdown.on_change = self.on_theme_mode_changed
        self.theme_mode_dropdown.on_select = self.on_theme_mode_changed

        # ── 3. File Action Buttons (Vector Icons) ────────────────────────────────
        self.btn_file_open = ft.IconButton(
            icon=ft.Icons.FILE_OPEN_ROUNDED,
            tooltip=t("ribbon.btn_open"),
            icon_size=18,
            on_click=self._on_browse_in_click,
        )
        self.btn_file_save = ft.IconButton(
            icon=ft.Icons.SAVE_OUTLINED,
            tooltip=t("ribbon.btn_save"),
            icon_size=18,
            on_click=self._on_browse_out_click,
        )
        self.btn_file_clear = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINED,
            tooltip=t("ribbon.btn_clear"),
            icon_size=18,
            on_click=self._on_clear_click,
        )
        self.btn_youtube = ft.IconButton(
            icon=ft.Icons.PLAY_CIRCLE_OUTLINE_ROUNDED,
            tooltip=t("ribbon.btn_youtube"),
            icon_size=18,
            on_click=self._on_youtube_click,
        )
        self.btn_model_hub = ft.IconButton(
            icon=ft.Icons.AUTO_AWESOME_MOSAIC_ROUNDED,
            tooltip=t("ribbon.btn_model_hub"),
            icon_size=18,
            on_click=self._on_model_hub_click,
        )

        # Backward compatibility references for tests and legacy callers
        self.btn_tab_file = ft.TextButton("File", on_click=lambda _: self._select_tab("file"))
        self.btn_tab_edit = ft.TextButton("Edit", on_click=lambda _: self._select_tab("edit"))
        self.btn_tab_view = ft.TextButton("View", on_click=lambda _: self._select_tab("view"))
        self.btn_tab_settings = ft.TextButton("Settings", on_click=lambda _: self._select_tab("settings"))
        self.btn_tab_help = ft.TextButton("Help", on_click=lambda _: self._select_tab("help"))
        self.btn_tab_file_open = self.btn_file_open
        self.btn_tab_file_save = self.btn_file_save
        self.btn_tab_file_clear = self.btn_file_clear

        self._tabs_map = {
            "file": self.btn_tab_file,
            "edit": self.btn_tab_edit,
            "view": self.btn_tab_view,
            "settings": self.btn_tab_settings,
            "help": self.btn_tab_help,
        }

        # ── 4. Formatting Toolbar (Headings & Markdown tools) ───────────────────
        self.formatting_toolbar = FormattingToolbar(
            on_format_action=self.on_format_action,
            on_heading_change=self.on_heading_change,
            on_insert_image=self.on_insert_image,
        )

        # ── 5. Search & Replace Toggle Button ────────────────────────────────────
        self.btn_tab_edit_search = ft.IconButton(
            icon=ft.Icons.SEARCH_ROUNDED,
            tooltip=t("ribbon.btn_search"),
            icon_size=18,
            on_click=self._on_search_click,
        )

        # ── 6. View & Navigation Actions ─────────────────────────────────────────
        self.btn_tab_view_preview = ft.IconButton(
            icon=ft.Icons.PREVIEW_ROUNDED,
            tooltip=t("ribbon.tooltip_preview"),
            icon_size=18,
            on_click=self._on_preview_click,
        )
        self.btn_tab_view_pathbar = ft.IconButton(
            icon=ft.Icons.ALT_ROUTE_ROUNDED,
            tooltip=t("ribbon.tooltip_pathbar"),
            icon_size=18,
            on_click=self._on_toggle_file_path_bar_click,
        )
        self.btn_tab_view_editor = ft.IconButton(
            icon=ft.Icons.EDIT_NOTE_OUTLINED,
            tooltip=t("ribbon.tooltip_editor"),
            icon_size=18,
            on_click=self._on_toggle_editor_click,
        )
        self.btn_tab_view_statusbar = ft.IconButton(
            icon=ft.Icons.SPACE_DASHBOARD_OUTLINED,
            tooltip=t("ribbon.tooltip_statusbar"),
            icon_size=18,
            on_click=self._on_toggle_status_bar_click,
        )
        self.btn_settings = ft.IconButton(
            icon=ft.Icons.SETTINGS_OUTLINED,
            tooltip=t("ribbon.tab_settings"),
            icon_size=18,
            on_click=lambda _: self.select_tab("settings"),
        )
        self.btn_help = ft.IconButton(
            icon=ft.Icons.HELP_OUTLINE_ROUNDED,
            tooltip=t("ribbon.tab_help"),
            icon_size=18,
            on_click=lambda _: self.select_tab("help"),
        )

        self.btn_collapse = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_UP,
            tooltip="Toggle Ribbon Collapse/Expand",
            icon_size=18,
            on_click=self._toggle_collapse,
            visible=False,
        )

        # ── 7. Single-Row Unified Ribbon Strip ──────────────────────────────────
        self.mode_dropdown_container = ft.Container(
            content=self.mode_dropdown,
            padding=ft.Padding(left=4, top=0, right=4, bottom=0),
            alignment=ft.alignment.Alignment(0.0, 0.0),
        )

        self.ribbon_spacer = ft.Container(expand=True)

        self.ribbon_row = ft.Row(
            controls=[
                self.logo_icon,
                self.logo_text,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                self.btn_file_open,
                self.btn_file_save,
                self.btn_file_clear,
                self.btn_model_hub,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                self.formatting_toolbar,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                self.btn_tab_edit_search,
                self.ribbon_spacer,
                self.mode_dropdown_container,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                self.btn_tab_view_preview,
                self.btn_tab_view_pathbar,
                self.btn_settings,
                self.btn_help,
            ],
            scroll=None,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=3,
        )

        # ── 8. Collapsible Search Panel Container ────────────────────────────────
        self.search_panel_container = ft.Container(
            visible=False,
            padding=ft.Padding(left=4, top=2, right=4, bottom=2),
        )

        # Backward compatibility panel_container placeholder
        self.panel_container = self.search_panel_container

        self.main_column = ft.Column(
            controls=[
                self.ribbon_row,
                self.search_panel_container,
            ],
            spacing=2,
        )

        self.content = self.main_column
        self.border_radius = 8
        self.padding = ft.Padding(left=8, top=2, right=8, bottom=2)

        self._refresh_locale_strings()

    # ─────────────────────────────────────────────────────────────────────────
    # Public APIs & Mode Selection
    # ─────────────────────────────────────────────────────────────────────────

    def update_mode_options(self, input_ext: str = "", preferred_mode: str = ""):
        """Updates available modes in Ribbon mode dropdown, prioritizing preferred_mode if valid."""
        if not input_ext:
            valid_modes = list(MODES.keys())
        else:
            valid_modes = [m for m, cfg in MODES.items() if cfg["in_ext"] == input_ext.lower()]
            if not valid_modes:
                valid_modes = list(MODES.keys())
        self.mode_dropdown.options = [
            ft.dropdown.Option(m, t(MODE_DISPLAY_KEYS.get(m, m))) for m in valid_modes
        ]
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

    def update_responsive_layout(self, width: int):
        """Dynamically manages responsive modes and switches scroll mode when squeezed."""
        if not width:
            return

        # Calibrated width thresholds guaranteeing scroll stays OFF at all standard desktop sizes
        full_needed = 1360          # Wide desktop / Full size: Full tools + Full logo + Float Right
        compact_with_logo = 1080    # Medium size: Compact ('⋯ More') + Full logo + Float Right
        compact_min = 1000           # Minimum standard window (900px): Compact + Icon-only logo + Float Right

        # 1. Mode dropdown width: Always fixed at 165px
        self.mode_dropdown.width = 165

        # 2. Dynamic state switching with Scroll On/Off control
        if width >= full_needed:
            # Full size: Full formatting tools + Full logo text + Scroll OFF (Native Float Right)
            self.logo_text.visible = True
            if hasattr(self, "formatting_toolbar"):
                self.formatting_toolbar.set_compact_mode(False)
                self.formatting_toolbar.heading_dropdown.width = 165
            self.ribbon_spacer.visible = True
            self.ribbon_row.scroll = None
        elif width >= compact_with_logo:
            # Medium size: Compact formatting tools ('⋯ More') + Full logo text + Scroll OFF
            self.logo_text.visible = True
            if hasattr(self, "formatting_toolbar"):
                self.formatting_toolbar.set_compact_mode(True)
                self.formatting_toolbar.heading_dropdown.width = 165
            self.ribbon_spacer.visible = True
            self.ribbon_row.scroll = None
        elif width >= compact_min:
            # Small size: Compact formatting tools + Hide logo text + Scroll OFF
            self.logo_text.visible = False
            if hasattr(self, "formatting_toolbar"):
                self.formatting_toolbar.set_compact_mode(True)
                self.formatting_toolbar.heading_dropdown.width = 165
            self.ribbon_spacer.visible = True
            self.ribbon_row.scroll = None
        else:
            # Extra small (< 1000px): Turn ON Scroll to allow smooth unified scrolling across entire menu
            self.logo_text.visible = False
            if hasattr(self, "formatting_toolbar"):
                self.formatting_toolbar.set_compact_mode(True)
                self.formatting_toolbar.heading_dropdown.width = 165
            self.ribbon_spacer.visible = False
            self.ribbon_row.scroll = ft.ScrollMode.AUTO

        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def select_tab(self, tab_name: str, force: bool = False):
        """
        Safe API to switch views or toggle panel for callers (WorkspaceView, FileController).
        """
        self.active_tab = tab_name
        if tab_name == "settings":
            if self.on_show_settings:
                self.on_show_settings()
        elif tab_name == "help":
            if self.on_show_help:
                self.on_show_help()
        elif tab_name in ("edit", "file", "view", ""):
            if self.on_show_editor:
                self.on_show_editor()

        self._update_tab_highlights()
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def _select_tab(self, tab_name: str):
        self.select_tab(tab_name, force=False)

    def deselect_all_tabs(self):
        """Clear active tab selection (for Welcome Screen or clean state)."""
        self.active_tab = ""
        self._update_tab_highlights()
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def _toggle_collapse(self, e):
        self.is_expanded = not self.is_expanded
        if self.on_ribbon_toggle:
            self.on_ribbon_toggle()

    def _update_tab_highlights(self):
        """Update button active visual states based on active_tab."""
        palette = getattr(self, "_current_palette", None)
        is_dark = getattr(self, "_is_dark", True)
        accent_primary = resolve_color(palette, "text_accent_primary", is_dark) if palette else ft.Colors.PRIMARY

        if hasattr(self, "btn_settings"):
            self.btn_settings.icon_color = accent_primary if self.active_tab == "settings" else None
        if hasattr(self, "btn_help"):
            self.btn_help.icon_color = accent_primary if self.active_tab == "help" else None

        self._update_toggle_states()

    def set_preview_visible(self, is_visible: bool):
        """Update Preview toggle visual state (icon, accent color, tooltip)."""
        self._is_preview_visible = is_visible
        self._update_toggle_states()
        try:
            if hasattr(self, "btn_tab_view_preview") and self.btn_tab_view_preview.page:
                self.btn_tab_view_preview.update()
        except Exception:
            pass

    def set_path_bar_visible(self, is_visible: bool):
        """Update Path Bar toggle visual state (icon, accent color, tooltip)."""
        self._is_path_bar_visible = is_visible
        self._update_toggle_states()
        try:
            if hasattr(self, "btn_tab_view_pathbar") and self.btn_tab_view_pathbar.page:
                self.btn_tab_view_pathbar.update()
        except Exception:
            pass

    def _update_toggle_states(self):
        """Update toggle button icons and colors to reflect current active/inactive status."""
        palette = getattr(self, "_current_palette", None)
        is_dark = getattr(self, "_is_dark", True)
        accent_primary = resolve_color(palette, "text_accent_primary", is_dark) if palette else ft.Colors.PRIMARY

        if hasattr(self, "btn_tab_view_preview"):
            if getattr(self, "_is_preview_visible", True):
                self.btn_tab_view_preview.icon = ft.Icons.PREVIEW_ROUNDED
                self.btn_tab_view_preview.icon_color = accent_primary
            else:
                self.btn_tab_view_preview.icon = ft.Icons.PREVIEW_OUTLINED
                self.btn_tab_view_preview.icon_color = None

        if hasattr(self, "btn_tab_view_pathbar"):
            if getattr(self, "_is_path_bar_visible", True):
                self.btn_tab_view_pathbar.icon = ft.Icons.ALT_ROUTE_ROUNDED
                self.btn_tab_view_pathbar.icon_color = accent_primary
            else:
                self.btn_tab_view_pathbar.icon = ft.Icons.ROUTE_OUTLINED
                self.btn_tab_view_pathbar.icon_color = None

    # ─────────────────────────────────────────────────────────────────────────
    # Action Click Handlers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_browse_in_click(self, e):
        if self.on_browse_in:
            self.on_browse_in(e)

    def _on_browse_out_click(self, e):
        if self.on_browse_out:
            self.on_browse_out(e)

    def _on_clear_click(self, e):
        if self.on_clear_editor:
            self.on_clear_editor(e)

    def _on_youtube_click(self, e):
        if self.on_import_youtube:
            self.on_import_youtube(e)

    def _on_model_hub_click(self, e):
        if self.on_open_model_hub:
            self.on_open_model_hub(e)

    def _on_search_click(self, e):
        self.toggle_search()

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

    def _on_img_preset_click(self, preset: str):
        if self.on_image_size_preset:
            self.on_image_size_preset(preset)

    def _on_img_align_click(self, align: str):
        if self.on_image_align_preset:
            self.on_image_align_preset(align)

    def _on_img_custom_click(self, e):
        if self.on_open_image_size_dialog:
            self.on_open_image_size_dialog()

    def _on_img_replace_click(self, e):
        if self.on_replace_image:
            self.on_replace_image()

    def _on_img_reset_click(self, e):
        if self.on_reset_image_size:
            self.on_reset_image_size()

    def set_image_context(self, image_info: Optional[ImageTokenInfo]):
        """Backward-compatibility stub for image context updates."""
        self.active_image_token = image_info

    # ─────────────────────────────────────────────────────────────────────────
    # Search & Replace Panel Toggle
    # ─────────────────────────────────────────────────────────────────────────

    def toggle_search(self, visible: Optional[bool] = None):
        """Programmatically toggle or set search panel visibility in Ribbon Bar."""
        if self._search_toggling:
            return
        self._search_toggling = True
        try:
            if visible is None:
                visible = not self._search_visible

            self._search_visible = visible

            if self._search_visible and self.search_replace_bar:
                self.search_panel_container.content = self.search_replace_bar.ribbon_search_panel
                self.search_panel_container.visible = True
                self.search_replace_bar.focus_search_input()
            else:
                self.search_panel_container.visible = False
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
                if self.search_panel_container.page:
                    self.search_panel_container.update()
                if self.page:
                    self.update()
            except Exception:
                pass
        finally:
            self._search_toggling = False

    # ─────────────────────────────────────────────────────────────────────────
    # Palette & Theming
    # ─────────────────────────────────────────────────────────────────────────

    def apply_palette(self, palette: dict, is_dark: bool):
        """Apply palette colors to the Ribbon bar and its dropdowns/buttons."""
        self._current_palette = palette
        self._is_dark = is_dark

        bg_header = resolve_color(palette, "bg_header", is_dark)
        accent_primary = resolve_color(palette, "text_accent_primary", is_dark)
        border_color = resolve_color(palette, "border_color", is_dark)

        self.bgcolor = bg_header
        self.border_radius = 8
        self.border = make_border(1, border_color)

        self.logo_icon.color = accent_primary
        self.logo_text.color = ft.Colors.WHITE if is_dark else ft.Colors.BLACK87

        for dd in [self.mode_dropdown, self.palette_dropdown, self.theme_mode_dropdown]:
            dd.border_color = accent_primary
            dd.focused_border_color = accent_primary
            dd.color = ft.Colors.WHITE if is_dark else ft.Colors.BLACK87
            dd.label_style = ft.TextStyle(color=accent_primary, size=12)

        self.formatting_toolbar.apply_palette(palette, is_dark)

        # Apply palette to Picture Format container and controls
        if hasattr(self, "picture_format_container"):
            self.picture_format_container.border = make_border(1, accent_primary)
            self.picture_format_container.bgcolor = ft.Colors.with_opacity(0.08, accent_primary)
            self.badge_picture_format_icon.color = accent_primary
            self.badge_picture_format_text.color = accent_primary

        self._update_tab_highlights()

        try:
            if self.page:
                self.update()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # i18n Localization
    # ─────────────────────────────────────────────────────────────────────────

    def _refresh_locale_strings(self):
        """Refresh string values on tooltips and dropdowns."""
        self.logo_text.value = t("ribbon.logo")
        self.btn_file_open.tooltip = t("ribbon.btn_open")
        self.btn_file_save.tooltip = t("ribbon.btn_save")
        self.btn_file_clear.tooltip = t("ribbon.btn_clear")
        self.btn_youtube.tooltip = t("ribbon.btn_youtube")
        self.btn_tab_edit_search.tooltip = t("ribbon.btn_search")

        self.btn_tab_view_preview.tooltip = t("ribbon.tooltip_preview")
        self.btn_tab_view_pathbar.tooltip = t("ribbon.tooltip_pathbar")
        self.btn_tab_view_editor.tooltip = t("ribbon.tooltip_editor")
        self.btn_tab_view_statusbar.tooltip = t("ribbon.tooltip_statusbar")
        self.btn_settings.tooltip = t("ribbon.tab_settings")
        self.btn_help.tooltip = t("ribbon.tab_help")

        if hasattr(self, "badge_picture_format_text"):
            self.badge_picture_format_text.value = t("ribbon.picture_format")
            self.btn_img_align_left.tooltip = t("image_dialog.align_left")
            self.btn_img_align_center.tooltip = t("image_dialog.align_center")
            self.btn_img_align_right.tooltip = t("image_dialog.align_right")
            self.btn_img_custom.tooltip = t("ribbon.img_custom_size")
            self.btn_img_replace.tooltip = t("ribbon.img_replace")
            self.btn_img_reset.tooltip = t("ribbon.img_reset")

        # Text button backward compatibility
        self.btn_tab_file.content = ft.Text(t("ribbon.tab_file"))
        self.btn_tab_edit.content = ft.Text(t("ribbon.tab_edit"))
        self.btn_tab_view.content = ft.Text(t("ribbon.tab_view"))
        self.btn_tab_settings.content = ft.Text(t("ribbon.tab_settings"))
        self.btn_tab_help.content = ft.Text(t("ribbon.tab_help"))

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
            self.logo_text,
            self.btn_file_open,
            self.btn_file_save,
            self.btn_file_clear,
            self.btn_youtube,
            self.btn_tab_edit_search,
            self.btn_tab_view_preview,
            self.btn_tab_view_pathbar,
            self.btn_settings,
            self.btn_help,
            self.mode_dropdown,
            self.palette_dropdown,
            self.theme_mode_dropdown,
        ]:
            try:
                if hasattr(ctrl, "page") and ctrl.page:
                    ctrl.update()
            except Exception:
                pass

        try:
            if self.page:
                self.update()
        except Exception:
            pass
