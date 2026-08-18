"""
File Path Bar component for displaying input document and destination output paths.
"""
from typing import Callable, Optional
import flet as ft
from src.i18n import t
from src.ui_flet.theme import resolve_color, make_border


class FilePathBar:
    def __init__(
        self,
        on_browse_in: Optional[Callable[[ft.ControlEvent], None]] = None,
        on_browse_out: Optional[Callable[[ft.ControlEvent], None]] = None,
        on_out_path_changed: Optional[Callable[[ft.ControlEvent], None]] = None,
    ):
        self.on_browse_in = on_browse_in
        self.on_browse_out = on_browse_out
        self.on_out_path_changed = on_out_path_changed

        self.btn_browse_in = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            tooltip=t("pathbar.tooltip_browse_in"),
            icon_size=18,
            on_click=self.on_browse_in,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(4, 4, 4, 4),
            )
        )

        self.in_path_text = ft.TextField(
            label=t("pathbar.label_input"),
            value="",
            expand=True,
            dense=True,
            text_size=12,
            border_radius=6,
        )

        self.btn_browse_out = ft.IconButton(
            icon=ft.Icons.SAVE_OUTLINED,
            tooltip=t("pathbar.tooltip_browse_out"),
            icon_size=18,
            on_click=self.on_browse_out,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(4, 4, 4, 4),
            )
        )

        self.out_path_text = ft.TextField(
            label=t("pathbar.label_output"),
            value="",
            expand=True,
            dense=True,
            text_size=12,
            border_radius=6,
            on_change=self.on_out_path_changed,
        )

        self.in_row = ft.Row(
            controls=[self.in_path_text, self.btn_browse_in],
            expand=True,
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.out_row = ft.Row(
            controls=[self.out_path_text, self.btn_browse_out],
            expand=True,
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.container = ft.Container(
            content=ft.Row(
                controls=[
                    self.in_row,
                    ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                    self.out_row,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=8, top=2, right=8, bottom=2),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            visible=False,
        )

        self._in_ext = ".md"
        self._out_ext = ".docx"

    def set_in_path(self, path: str):
        self.in_path_text.value = path
        if self.in_path_text.page:
            self.in_path_text.update()

    def set_out_path(self, path: str):
        self.out_path_text.value = path
        if self.out_path_text.page:
            self.out_path_text.update()

    def set_out_label(self, label_or_ext: str):
        if not label_or_ext:
            return
        ext = label_or_ext.split()[-1] if " " in label_or_ext else label_or_ext
        if not ext.startswith("."):
            ext = f".{ext}"
        self._out_ext = ext
        self.out_path_text.label = t("pathbar.out_label", ext=ext)
        if self.out_path_text.page:
            self.out_path_text.update()

    def set_in_label(self, label_or_ext: str):
        if not label_or_ext:
            return
        ext = label_or_ext.split()[-1] if " " in label_or_ext else label_or_ext
        if not ext.startswith("."):
            ext = f".{ext}"
        self._in_ext = ext
        self.in_path_text.label = t("pathbar.in_label", ext=ext)
        if self.in_path_text.page:
            self.in_path_text.update()

    def toggle_visibility(self):
        """Toggle the visibility of the file path bar."""
        self.container.visible = not self.container.visible
        if self.container.page:
            self.container.update()

    def apply_palette(self, palette: dict, is_dark: bool):
        """Apply palette colors to the file path bar container and its controls."""
        bg = resolve_color(palette, "bg_component", is_dark)
        border = resolve_color(palette, "border_color", is_dark)
        accent = resolve_color(palette, "text_accent_primary", is_dark)
        self.container.bgcolor = bg
        self.container.border = make_border(1, border)
        self.btn_browse_in.icon_color = accent
        self.btn_browse_out.icon_color = accent
        self.in_path_text.border_color = border
        self.in_path_text.focused_border_color = accent
        self.out_path_text.border_color = border
        self.out_path_text.focused_border_color = accent
        try:
            self.container.update()
        except Exception:
            pass

    def update_locale(self, in_ext: str = "", out_ext: str = ""):
        """Refresh all text to current locale."""
        self.btn_browse_in.tooltip = t("pathbar.tooltip_browse_in")
        self.btn_browse_out.tooltip = t("pathbar.tooltip_browse_out")
        if in_ext:
            self._in_ext = in_ext if in_ext.startswith(".") else f".{in_ext}"
        if out_ext:
            self._out_ext = out_ext if out_ext.startswith(".") else f".{out_ext}"
        self.in_path_text.label = t("pathbar.in_label", ext=self._in_ext)
        self.out_path_text.label = t("pathbar.out_label", ext=self._out_ext)
        for ctrl in [self.in_path_text, self.out_path_text, self.btn_browse_in, self.btn_browse_out]:
            try:
                ctrl.update()
            except Exception:
                pass
        try:
            if self.container.page:
                self.container.update()
        except Exception:
            pass
