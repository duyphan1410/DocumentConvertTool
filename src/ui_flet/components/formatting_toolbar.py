"""
Formatting Toolbar Component for Flet UI.
Provides a Heading Selector (H1-H6) and quick Markdown formatting action buttons
(Bold, Italic, Code, Table, Link, Image, Lists, Quotes) for the Editor View.
"""
import flet as ft
from typing import Callable, Optional

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
            label="Heading",
            value="0",
            width=165,
            dense=True,
            options=[
                ft.dropdown.Option("0", "Normal Text"),
                ft.dropdown.Option("1", "Heading 1 (#)"),
                ft.dropdown.Option("2", "Heading 2 (##)"),
                ft.dropdown.Option("3", "Heading 3 (###)"),
                ft.dropdown.Option("4", "Heading 4 (####)"),
                ft.dropdown.Option("5", "Heading 5 (#####)"),
                ft.dropdown.Option("6", "Heading 6 (######)"),
            ],
            tooltip="Apply Heading Style (H1 - H6)"
        )
        self.heading_dropdown.on_change = self._handle_heading_change
        self.heading_dropdown.on_select = self._handle_heading_change

        # ── Formatting Buttons ───────────────────────────────────────────────────
        self.btn_bold = ft.IconButton(
            icon=ft.Icons.FORMAT_BOLD,
            tooltip="Bold (**text**)",
            icon_size=18,
            on_click=lambda _: self._trigger_format("**", "**")
        )
        self.btn_italic = ft.IconButton(
            icon=ft.Icons.FORMAT_ITALIC,
            tooltip="Italic (*text*)",
            icon_size=18,
            on_click=lambda _: self._trigger_format("*", "*")
        )
        self.btn_strike = ft.IconButton(
            icon=ft.Icons.STRIKETHROUGH_S,
            tooltip="Strikethrough (~~text~~)",
            icon_size=18,
            on_click=lambda _: self._trigger_format("~~", "~~")
        )
        self.btn_code = ft.IconButton(
            icon=ft.Icons.CODE,
            tooltip="Inline Code (`code`)",
            icon_size=18,
            on_click=lambda _: self._trigger_format("`", "`")
        )
        self.btn_codeblock = ft.IconButton(
            icon=ft.Icons.DATA_OBJECT,
            tooltip="Code Block (```)",
            icon_size=18,
            on_click=lambda _: self._trigger_format("```\n", "\n```")
        )
        self.btn_quote = ft.IconButton(
            icon=ft.Icons.FORMAT_QUOTE,
            tooltip="Blockquote (> text)",
            icon_size=18,
            on_click=lambda _: self._trigger_format("> ", "")
        )
        self.btn_ulist = ft.IconButton(
            icon=ft.Icons.FORMAT_LIST_BULLETED,
            tooltip="Bullet List (- item)",
            icon_size=18,
            on_click=lambda _: self._trigger_format("- ", "")
        )
        self.btn_olist = ft.IconButton(
            icon=ft.Icons.FORMAT_LIST_NUMBERED,
            tooltip="Numbered List (1. item)",
            icon_size=18,
            on_click=lambda _: self._trigger_format("1. ", "")
        )
        self.btn_table = ft.IconButton(
            icon=ft.Icons.TABLE_CHART,
            tooltip="Insert Markdown Table",
            icon_size=18,
            on_click=lambda _: self._trigger_format(
                "\n| Header 1 | Header 2 |\n| --- | --- |\n| Cell 1 | Cell 2 |\n", ""
            )
        )
        self.btn_link = ft.IconButton(
            icon=ft.Icons.INSERT_LINK,
            tooltip="Insert Hyperlink",
            icon_size=18,
            on_click=lambda _: self._trigger_format("[", "](https://)")
        )
        self.btn_image = ft.IconButton(
            icon=ft.Icons.IMAGE,
            tooltip="Insert Image File",
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
        self.heading_dropdown.border_color = accent_primary
        self.heading_dropdown.focused_border_color = accent_primary
        self.heading_dropdown.color = accent_primary
        self.heading_dropdown.label_style = ft.TextStyle(color=accent_primary)
        try:
            if self.heading_dropdown.page:
                self.heading_dropdown.update()
        except Exception:
            pass
