"""
Settings View for DocConvert Workspace.
Full-screen settings panel with left-nav + right content panel.
Supports staged Apply/Discard with unsaved-changes dirty tracking.
Follows Flet 0.86.4 Desktop standards.
"""
from __future__ import annotations

from typing import Callable, Optional
import flet as ft

from src.ui_flet.constants import MODES
from src.ui_flet.theme import PALETTES, resolve_color, make_border


class SettingsView(ft.Container):
    """Full-workspace settings view with category navigation and preference panels."""

    _CATEGORIES = ["Appearance", "Editor", "Conversion", "About"]

    def __init__(
        self,
        state=None,
        on_palette_changed: Optional[Callable] = None,
        on_theme_mode_changed: Optional[Callable] = None,
        on_autosave_toggled: Optional[Callable] = None,
        on_autosave_interval_changed: Optional[Callable] = None,
        on_font_size_changed: Optional[Callable] = None,
        on_default_mode_changed: Optional[Callable] = None,
        on_word_wrap_changed: Optional[Callable] = None,
        on_apply: Optional[Callable] = None,
        on_discard: Optional[Callable] = None,
        on_close: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._state = state
        self._on_palette_changed = on_palette_changed
        self._on_theme_mode_changed = on_theme_mode_changed
        self._on_autosave_toggled = on_autosave_toggled
        self._on_autosave_interval_changed = on_autosave_interval_changed
        self._on_font_size_changed = on_font_size_changed
        self._on_default_mode_changed = on_default_mode_changed
        self._on_word_wrap_changed = on_word_wrap_changed
        self._on_apply = on_apply
        self._on_discard = on_discard
        self._on_close = on_close

        self._is_dirty = False
        self._active_category = "Appearance"
        self.expand = True
        self.padding = ft.Padding(left=20, top=14, right=20, bottom=14)

        # ── Dirty bar (hidden until changes made) ────────────────────────────
        self._dirty_indicator = ft.Text(
            "● Unsaved changes",
            size=12,
            color=ft.Colors.ORANGE_400,
            italic=True,
        )
        self._btn_apply = ft.FilledButton(
            "Apply",
            icon=ft.Icons.SAVE_ROUNDED,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=self._on_apply_click,
        )
        self._btn_discard = ft.OutlinedButton(
            "Discard",
            icon=ft.Icons.UNDO_ROUNDED,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=self._on_discard_click,
        )
        self._dirty_bar = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.EDIT_ROUNDED, size=14, color=ft.Colors.ORANGE_400),
                    self._dirty_indicator,
                    ft.Container(expand=True),
                    self._btn_discard,
                    self._btn_apply,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border_radius=8,
            padding=ft.Padding(left=14, top=8, right=14, bottom=8),
            visible=False,
        )

        # ── Left Navigation ───────────────────────────────────────────────────
        self._nav_buttons: dict[str, ft.TextButton] = {}
        nav_items = []
        for cat in self._CATEGORIES:
            icon = self._category_icon(cat)
            btn = ft.TextButton(
                content=ft.Row(
                    [ft.Icon(icon, size=18), ft.Text(cat, size=13)],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                on_click=lambda e, c=cat: self._select_category(c),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding(left=14, top=10, right=14, bottom=10),
                ),
            )
            self._nav_buttons[cat] = btn
            nav_items.append(btn)

        self._left_nav = ft.Container(
            content=ft.Column(nav_items, spacing=4),
            width=180,
            padding=ft.Padding(left=0, top=4, right=12, bottom=0),
        )

        # ── Right Content Panel ───────────────────────────────────────────────
        self._content_panel = ft.Container(
            content=ft.Container(),  # placeholder before first category select
            expand=True,
            padding=ft.Padding(left=24, top=4, right=16, bottom=12),
        )

        # ── Close Button ─────────────────────────────────────────────────────
        btn_close = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_size=20,
            tooltip="Close Settings (Return to Editor)",
            on_click=self._on_close_click,
        )

        # ── Page Header ──────────────────────────────────────────────────────
        header = ft.Row(
            [
                ft.Icon(ft.Icons.SETTINGS_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                ft.Text("Settings", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                btn_close,
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        body = ft.Row(
            [self._left_nav, ft.VerticalDivider(width=1), self._content_panel],
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        self.content = ft.Column(
            [header, ft.Divider(height=1), self._dirty_bar, body],
            spacing=12,
            expand=True,
        )
        self._select_category("Appearance", update=False)

    # ─────────────────────────────────────────────────────────────────────────
    # Category panels
    # ─────────────────────────────────────────────────────────────────────────

    def _build_appearance_panel(self) -> ft.Column:
        palette_val = getattr(self._state, "current_palette", "Deep Ocean") if self._state else "Deep Ocean"
        theme_val = getattr(self._state, "current_theme_mode", "System") if self._state else "System"

        self._palette_dropdown = ft.Dropdown(
            label="Color Palette",
            value=palette_val,
            options=[ft.dropdown.Option(p) for p in PALETTES.keys()],
            width=260,
            dense=True,
        )
        self._palette_dropdown.on_change = self._on_palette_change
        self._palette_dropdown.on_select = self._on_palette_change

        self._theme_radio = ft.RadioGroup(
            content=ft.Row(
                [
                    ft.Radio(value="Dark", label="Dark"),
                    ft.Radio(value="Light", label="Light"),
                    ft.Radio(value="System", label="System"),
                ],
                spacing=12,
            ),
            value=theme_val,
        )
        self._theme_radio.on_change = self._on_theme_mode_change

        return ft.Column(
            [
                self._section_title("Color Palette"),
                ft.Text(
                    "Changes preview immediately. Click Apply to save.",
                    size=12,
                    color=ft.Colors.OUTLINE,
                ),
                ft.Container(height=4),
                self._palette_dropdown,
                ft.Container(height=16),
                self._section_title("Theme Mode"),
                self._theme_radio,
            ],
            spacing=8,
        )

    def _build_editor_panel(self) -> ft.Column:
        font_size_val = getattr(self._state, "editor_font_size", 13) if self._state else 13
        word_wrap_val = getattr(self._state, "word_wrap", True) if self._state else True
        autosave_val = getattr(self._state, "autosave_enabled", True) if self._state else True
        interval_val = str(getattr(self._state, "autosave_interval_sec", 30)) if self._state else "30"

        self._font_size_label = ft.Text(f"Font Size: {font_size_val}px", size=13, weight=ft.FontWeight.W_500)

        # Live preview sample text with refined padding & border
        self._font_preview = ft.Container(
            content=ft.Text(
                "Aa Bb Cc  123  — The quick brown fox jumps over the lazy dog.",
                size=float(font_size_val),
                font_family="Consolas",
                color=ft.Colors.ON_SURFACE,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border=make_border(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
            padding=ft.Padding(left=16, top=12, right=16, bottom=12),
            width=520,
        )

        self._font_size_slider = ft.Slider(
            min=10,
            max=22,
            value=float(font_size_val),
            divisions=12,
            label="{value}px",
            width=340,
            on_change=self._on_font_size_slide,
        )

        self._word_wrap_switch = ft.Switch(
            label="Word Wrap",
            value=word_wrap_val,
        )
        self._word_wrap_switch.on_change = self._on_word_wrap_change

        self._autosave_switch = ft.Switch(
            label="Auto-Save Draft",
            value=autosave_val,
        )
        self._autosave_switch.on_change = self._on_autosave_toggle

        self._autosave_interval_dropdown = ft.Dropdown(
            label="Auto-Save Interval",
            value=interval_val,
            options=[
                ft.dropdown.Option("5", "5 seconds"),
                ft.dropdown.Option("15", "15 seconds"),
                ft.dropdown.Option("30", "30 seconds"),
                ft.dropdown.Option("60", "1 minute"),
                ft.dropdown.Option("300", "5 minutes"),
            ],
            width=220,
            dense=True,
            disabled=not autosave_val,
        )
        self._autosave_interval_dropdown.on_change = self._on_autosave_interval_change
        self._autosave_interval_dropdown.on_select = self._on_autosave_interval_change

        return ft.Column(
            [
                self._section_title("Editor Font"),
                ft.Container(
                    content=ft.Column(
                        [
                            self._font_size_label,
                            self._font_size_slider,
                            self._font_preview,
                        ],
                        spacing=8,
                    ),
                    padding=ft.Padding(left=4, top=0, right=0, bottom=0),
                ),
                ft.Container(height=16),
                self._section_title("Text Options"),
                ft.Container(
                    content=self._word_wrap_switch,
                    padding=ft.Padding(left=4, top=0, right=0, bottom=0),
                ),
                ft.Container(height=16),
                self._section_title("Auto-Save"),
                ft.Container(
                    content=ft.Column(
                        [
                            self._autosave_switch,
                            ft.Container(height=4),
                            self._autosave_interval_dropdown,
                        ],
                        spacing=6,
                    ),
                    padding=ft.Padding(left=4, top=0, right=0, bottom=0),
                ),
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        )

    def _build_conversion_panel(self) -> ft.Column:
        default_mode_val = getattr(self._state, "default_mode", "MD -> Excel") if self._state else "MD -> Excel"

        self._default_mode_dropdown = ft.Dropdown(
            label="Default Conversion Mode",
            value=default_mode_val,
            options=[ft.dropdown.Option(m) for m in MODES.keys()],
            width=280,
            dense=True,
        )
        self._default_mode_dropdown.on_change = self._on_default_mode_change
        self._default_mode_dropdown.on_select = self._on_default_mode_change

        return ft.Column(
            [
                self._section_title("Default Conversion Mode"),
                ft.Text(
                    "This mode is pre-selected every time you open the app.",
                    size=12,
                    color=ft.Colors.OUTLINE,
                ),
                ft.Container(height=6),
                self._default_mode_dropdown,
            ],
            spacing=8,
        )

    def _build_about_panel(self) -> ft.Column:
        try:
            from src.__version__ import __version__
        except Exception:
            __version__ = "—"

        deps = [
            ("flet", "0.86.4"),
            ("python-docx", "required for Word"),
            ("openpyxl", "required for Excel"),
            ("weasyprint / reportlab", "required for PDF"),
            ("mistune", "required for Markdown"),
        ]
        dep_rows = [
            ft.Row(
                [
                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=16, color=ft.Colors.PRIMARY),
                    ft.Text(f"{name} — {note}", size=12),
                ],
                spacing=8,
            )
            for name, note in deps
        ]

        return ft.Column(
            [
                self._section_title("About DocConvert Workspace"),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.PRIMARY, size=32),
                        ft.Column(
                            [
                                ft.Text("DocConvert Workspace", size=16, weight=ft.FontWeight.BOLD),
                                ft.Text(f"Version {__version__}", size=13, color=ft.Colors.OUTLINE),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=16),
                self._section_title("Dependencies"),
                *dep_rows,
            ],
            spacing=8,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Dirty tracking
    # ─────────────────────────────────────────────────────────────────────────

    def mark_dirty(self):
        """Show unsaved-changes bar."""
        self._is_dirty = True
        self._dirty_bar.visible = True
        try:
            if self._dirty_bar.page:
                self._dirty_bar.update()
        except Exception:
            pass

    def mark_clean(self):
        """Hide unsaved-changes bar."""
        self._is_dirty = False
        self._dirty_bar.visible = False
        try:
            if self._dirty_bar.page:
                self._dirty_bar.update()
        except Exception:
            pass

    def _on_apply_click(self, e):
        if self._on_apply:
            self._on_apply(e)

    def _on_discard_click(self, e):
        if self._on_discard:
            self._on_discard(e)

    def _on_close_click(self, e):
        if self._on_close:
            self._on_close(e)

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _section_title(self, text: str) -> ft.Text:
        return ft.Text(text, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.OUTLINE)

    def _category_icon(self, category: str) -> str:
        return {
            "Appearance": ft.Icons.PALETTE_OUTLINED,
            "Editor": ft.Icons.EDIT_NOTE_OUTLINED,
            "Conversion": ft.Icons.TRANSFORM,
            "About": ft.Icons.INFO_OUTLINE,
        }.get(category, ft.Icons.SETTINGS_OUTLINED)

    def _select_category(self, category: str, update: bool = True):
        self._active_category = category

        panels = {
            "Appearance": self._build_appearance_panel,
            "Editor": self._build_editor_panel,
            "Conversion": self._build_conversion_panel,
            "About": self._build_about_panel,
        }
        builder = panels.get(category, self._build_appearance_panel)
        self._content_panel.content = builder()

        # Update button highlight styles
        for cat, btn in self._nav_buttons.items():
            is_active = cat == category
            btn.style = ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=12, top=10, right=12, bottom=10),
                bgcolor=ft.Colors.PRIMARY_CONTAINER if is_active else None,
                color=ft.Colors.ON_PRIMARY_CONTAINER if is_active else None,
            )

        if update:
            try:
                if self.page:
                    self.page.update()
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # Event handlers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_palette_change(self, e):
        if self._on_palette_changed:
            self._on_palette_changed(e)
        self.mark_dirty()

    def _on_theme_mode_change(self, e):
        if self._on_theme_mode_changed:
            self._on_theme_mode_changed(e)
        self.mark_dirty()

    def _on_autosave_toggle(self, e):
        is_on = self._autosave_switch.value
        try:
            self._autosave_interval_dropdown.disabled = not is_on
            if self._autosave_interval_dropdown.page:
                self._autosave_interval_dropdown.update()
        except Exception:
            pass
        if self._on_autosave_toggled:
            self._on_autosave_toggled(e)
        self.mark_dirty()

    def _on_autosave_interval_change(self, e):
        if self._on_autosave_interval_changed:
            self._on_autosave_interval_changed(e)
        self.mark_dirty()

    def _on_font_size_slide(self, e):
        val = int(e.control.value)
        try:
            self._font_size_label.value = f"Font Size: {val}px"
            self._font_preview.content.size = float(val)
            if self._font_size_label.page:
                self._font_size_label.update()
            if self._font_preview.page:
                self._font_preview.update()
        except Exception:
            pass
        if self._on_font_size_changed:
            self._on_font_size_changed(val)
        self.mark_dirty()

    def _on_word_wrap_change(self, e):
        if self._on_word_wrap_changed:
            self._on_word_wrap_changed(e)
        self.mark_dirty()

    def _on_default_mode_change(self, e):
        if self._on_default_mode_changed:
            self._on_default_mode_changed(e)
        self.mark_dirty()

    # ─────────────────────────────────────────────────────────────────────────
    # Theme sync
    # ─────────────────────────────────────────────────────────────────────────

    def apply_palette(self, palette: dict, is_dark: bool):
        """Sync background and border colors with the current palette."""
        bg = resolve_color(palette, "bg_component", is_dark)
        border = resolve_color(palette, "border_color", is_dark)
        self.bgcolor = bg
        self.border = make_border(1, border)
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def sync_from_state(self, state):
        """Update all controls to reflect current AppState values (called after discard)."""
        self._state = state
        self._select_category(self._active_category)
        self.mark_clean()
