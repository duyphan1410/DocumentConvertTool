"""
Formatting Toolbar Component for Flet UI.
Provides a Heading Selector (H1-H6) and quick Markdown formatting action buttons
(Bold, Italic, Code, Table, Link, Image, Lists, Quotes) for the Editor View.
"""
import flet as ft
from typing import Callable, Optional
from src.i18n import t

class FormattingToolbar(ft.Container):
    def __init__(
        self,
        on_format_action: Optional[Callable[[str, str], None]] = None,
        on_heading_change: Optional[Callable[[int], None]] = None,
        on_insert_image: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.on_format_action = on_format_action
        self.on_heading_change = on_heading_change
        self.on_insert_image = on_insert_image
        self.padding = ft.Padding(left=1, top=4, right=2, bottom=1)
        self.border_radius = 6

        # ── Heading Level Dropdown ────────────────────────────────────────────────
        self.heading_dropdown = ft.Dropdown(
            label=t("format.label_heading"),
            value="0",
            width=165,
            dense=True,
            options=[
                ft.dropdown.Option("0", t("format.opt_normal")),
                ft.dropdown.Option("1", t("format.opt_h1")),
                ft.dropdown.Option("2", t("format.opt_h2")),
                ft.dropdown.Option("3", t("format.opt_h3")),
                ft.dropdown.Option("4", t("format.opt_h4")),
                ft.dropdown.Option("5", t("format.opt_h5")),
                ft.dropdown.Option("6", t("format.opt_h6")),
            ],
            tooltip=t("format.tooltip_heading")
        )
        self.heading_dropdown.on_change = self._handle_heading_change
        self.heading_dropdown.on_select = self._handle_heading_change

        # ── Formatting Buttons ───────────────────────────────────────────────────
        self.btn_bold = ft.IconButton(
            icon=ft.Icons.FORMAT_BOLD,
            tooltip=t("format.tooltip_bold"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("**", "**")
        )
        self.btn_italic = ft.IconButton(
            icon=ft.Icons.FORMAT_ITALIC,
            tooltip=t("format.tooltip_italic"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("*", "*")
        )
        self.btn_strike = ft.IconButton(
            icon=ft.Icons.STRIKETHROUGH_S,
            tooltip=t("format.tooltip_strike"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("~~", "~~")
        )
        self.btn_code = ft.IconButton(
            icon=ft.Icons.CODE,
            tooltip=t("format.tooltip_code"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("`", "`")
        )
        self.btn_codeblock = ft.IconButton(
            icon=ft.Icons.DATA_OBJECT,
            tooltip=t("format.tooltip_codeblock"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("```\n", "\n```")
        )
        self.btn_quote = ft.IconButton(
            icon=ft.Icons.FORMAT_QUOTE,
            tooltip=t("format.tooltip_quote"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("> ", "")
        )
        self.btn_ulist = ft.IconButton(
            icon=ft.Icons.FORMAT_LIST_BULLETED,
            tooltip=t("format.tooltip_ulist"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("- ", "")
        )
        self.btn_olist = ft.IconButton(
            icon=ft.Icons.FORMAT_LIST_NUMBERED,
            tooltip=t("format.tooltip_olist"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("1. ", "")
        )
        self.btn_table = ft.IconButton(
            icon=ft.Icons.TABLE_CHART,
            tooltip=t("format.tooltip_table"),
            icon_size=18,
            on_click=lambda _: self._trigger_format(
                "\n| Header 1 | Header 2 |\n| --- | --- |\n| Cell 1 | Cell 2 |\n", ""
            )
        )
        self.btn_link = ft.IconButton(
            icon=ft.Icons.INSERT_LINK,
            tooltip=t("format.tooltip_link"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("[", "](https://)")
        )
        self.btn_image = ft.IconButton(
            icon=ft.Icons.IMAGE,
            tooltip=t("format.tooltip_image"),
            icon_size=18,
            on_click=self._trigger_image_insert
        )

        self.row = ft.Row(
            controls=[
                self.heading_dropdown,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                self.btn_bold,
                self.btn_italic,
                self.btn_strike,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                self.btn_code,
                self.btn_codeblock,
                self.btn_quote,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                self.btn_ulist,
                self.btn_olist,
                self.btn_table,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                self.btn_link,
                self.btn_image,
            ],
            scroll=ft.ScrollMode.AUTO,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2
        )
        self.content = self.row

    def _handle_heading_change(self, e):
        try:
            level = int(self.heading_dropdown.value or "0")
            if self.on_heading_change:
                self.on_heading_change(level)
        except ValueError:
            pass

    def _trigger_format(self, prefix: str, suffix: str):
        if self.on_format_action:
            self.on_format_action(prefix, suffix)

    def _trigger_image_insert(self, e):
        if self.on_insert_image:
            self.on_insert_image(e)
        else:
            self._trigger_format("![Alt Text](", ")")

    def apply_palette(self, palette: dict, is_dark: bool):
        from src.ui_flet.theme import resolve_color
        accent_primary = resolve_color(palette, "text_accent_primary", is_dark)
        border_color = resolve_color(palette, "border_color", is_dark)
        self.heading_dropdown.border_color = accent_primary
        self.heading_dropdown.focused_border_color = accent_primary
        self.heading_dropdown.color = ft.Colors.WHITE if is_dark else ft.Colors.BLACK87
        self.heading_dropdown.label_style = ft.TextStyle(color=accent_primary, size=12)

        for btn in [
            self.btn_bold, self.btn_italic, self.btn_strike, self.btn_code,
            self.btn_codeblock, self.btn_quote, self.btn_ulist, self.btn_olist,
            self.btn_table, self.btn_link, self.btn_image
        ]:
            btn.icon_color = ft.Colors.WHITE if is_dark else ft.Colors.BLACK87

        try:
            if self.heading_dropdown.page:
                self.heading_dropdown.update()
        except Exception:
            pass

    def update_locale(self):
        """Refresh all text to current locale."""
        self.heading_dropdown.label = t("format.label_heading")
        self.heading_dropdown.tooltip = t("format.tooltip_heading")
        self.heading_dropdown.options = [
            ft.dropdown.Option("0", t("format.opt_normal")),
            ft.dropdown.Option("1", t("format.opt_h1")),
            ft.dropdown.Option("2", t("format.opt_h2")),
            ft.dropdown.Option("3", t("format.opt_h3")),
            ft.dropdown.Option("4", t("format.opt_h4")),
            ft.dropdown.Option("5", t("format.opt_h5")),
            ft.dropdown.Option("6", t("format.opt_h6")),
        ]
        self.btn_bold.tooltip = t("format.tooltip_bold")
        self.btn_italic.tooltip = t("format.tooltip_italic")
        self.btn_strike.tooltip = t("format.tooltip_strike")
        self.btn_code.tooltip = t("format.tooltip_code")
        self.btn_codeblock.tooltip = t("format.tooltip_codeblock")
        self.btn_quote.tooltip = t("format.tooltip_quote")
        self.btn_ulist.tooltip = t("format.tooltip_ulist")
        self.btn_olist.tooltip = t("format.tooltip_olist")
        self.btn_table.tooltip = t("format.tooltip_table")
        self.btn_link.tooltip = t("format.tooltip_link")
        self.btn_image.tooltip = t("format.tooltip_image")
        try:
            if self.page:
                self.update()
        except Exception:
            pass
