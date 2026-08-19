"""
Formatting Toolbar Component for Flet UI.
Provides a Heading Selector (H1-H6), Formatting Tools (Bold, Italic, Strike, Code, Code Block, Quote, Lists, Table, Link, Image),
and an Adaptive Compact Mode that automatically collapses extended tools into a 'More (⋯)' PopupMenu when the window shrinks.
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
        self.is_compact = False

        # ── 1. Heading Level Dropdown (165px for full text display) ─────────────
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
            tooltip=t("format.tooltip_heading"),
        )
        self.heading_dropdown.on_change = self._handle_heading_change
        self.heading_dropdown.on_select = self._handle_heading_change

        # ── 2. Primary Formatting Action Buttons ────────────────────────────────
        self.btn_bold = ft.IconButton(
            icon=ft.Icons.FORMAT_BOLD,
            tooltip=t("format.tooltip_bold"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("**", "**"),
        )
        self.btn_italic = ft.IconButton(
            icon=ft.Icons.FORMAT_ITALIC,
            tooltip=t("format.tooltip_italic"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("*", "*"),
        )
        self.btn_code = ft.IconButton(
            icon=ft.Icons.CODE,
            tooltip=t("format.tooltip_code"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("`", "`"),
        )

        # ── 3. Extended Formatting Action Buttons (Full Mode) ───────────────────
        self.btn_strike = ft.IconButton(
            icon=ft.Icons.STRIKETHROUGH_S,
            tooltip=t("format.tooltip_strike"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("~~", "~~"),
        )
        self.btn_codeblock = ft.IconButton(
            icon=ft.Icons.DATA_OBJECT,
            tooltip=t("format.tooltip_codeblock"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("```\n", "\n```"),
        )
        self.btn_quote = ft.IconButton(
            icon=ft.Icons.FORMAT_QUOTE,
            tooltip=t("format.tooltip_quote"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("> ", ""),
        )
        self.btn_ulist = ft.IconButton(
            icon=ft.Icons.FORMAT_LIST_BULLETED,
            tooltip=t("format.tooltip_ulist"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("- ", ""),
        )
        self.btn_olist = ft.IconButton(
            icon=ft.Icons.FORMAT_LIST_NUMBERED,
            tooltip=t("format.tooltip_olist"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("1. ", ""),
        )
        self.btn_table = ft.IconButton(
            icon=ft.Icons.TABLE_CHART,
            tooltip=t("format.tooltip_table"),
            icon_size=18,
            on_click=lambda _: self._trigger_format(
                "\n| Header 1 | Header 2 |\n| --- | --- |\n| Cell 1 | Cell 2 |\n", ""
            ),
        )
        self.btn_link = ft.IconButton(
            icon=ft.Icons.INSERT_LINK,
            tooltip=t("format.tooltip_link"),
            icon_size=18,
            on_click=lambda _: self._trigger_format("[", "](https://)"),
        )
        self.btn_image = ft.IconButton(
            icon=ft.Icons.IMAGE,
            tooltip=t("format.tooltip_image"),
            icon_size=18,
            on_click=self._trigger_image_insert,
        )

        # ── 4. PopupMenu Items for Compact Mode ─────────────────────────────────
        self.item_strike = ft.PopupMenuItem(
            content=t("format.tooltip_strike"),
            icon=ft.Icons.STRIKETHROUGH_S,
            on_click=lambda _: self._trigger_format("~~", "~~"),
        )
        self.item_codeblock = ft.PopupMenuItem(
            content=t("format.tooltip_codeblock"),
            icon=ft.Icons.DATA_OBJECT,
            on_click=lambda _: self._trigger_format("```\n", "\n```"),
        )
        self.item_quote = ft.PopupMenuItem(
            content=t("format.tooltip_quote"),
            icon=ft.Icons.FORMAT_QUOTE,
            on_click=lambda _: self._trigger_format("> ", ""),
        )
        self.item_ulist = ft.PopupMenuItem(
            content=t("format.tooltip_ulist"),
            icon=ft.Icons.FORMAT_LIST_BULLETED,
            on_click=lambda _: self._trigger_format("- ", ""),
        )
        self.item_olist = ft.PopupMenuItem(
            content=t("format.tooltip_olist"),
            icon=ft.Icons.FORMAT_LIST_NUMBERED,
            on_click=lambda _: self._trigger_format("1. ", ""),
        )
        self.item_table = ft.PopupMenuItem(
            content=t("format.tooltip_table"),
            icon=ft.Icons.TABLE_CHART,
            on_click=lambda _: self._trigger_format(
                "\n| Header 1 | Header 2 |\n| --- | --- |\n| Cell 1 | Cell 2 |\n", ""
            ),
        )
        self.item_link = ft.PopupMenuItem(
            content=t("format.tooltip_link"),
            icon=ft.Icons.INSERT_LINK,
            on_click=lambda _: self._trigger_format("[", "](https://)"),
        )
        self.item_image = ft.PopupMenuItem(
            content=t("format.tooltip_image"),
            icon=ft.Icons.IMAGE,
            on_click=self._trigger_image_insert,
        )

        self.btn_more = ft.PopupMenuButton(
            icon=ft.Icons.MORE_HORIZ_ROUNDED,
            tooltip=t("format.tooltip_more"),
            visible=False,
            items=[
                self.item_strike,
                self.item_codeblock,
                self.item_quote,
                self.item_ulist,
                self.item_olist,
                self.item_table,
                self.item_link,
                self.item_image,
            ],
        )

        # ── 5. Dividers ─────────────────────────────────────────────────────────
        self.div_primary = ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT)
        self.div_code = ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT)
        self.div_lists = ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT)
        self.div_media = ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT)

        # ── 6. Row Layout ───────────────────────────────────────────────────────
        self.row = ft.Row(
            controls=[
                self.heading_dropdown,
                self.div_primary,
                self.btn_bold,
                self.btn_italic,
                self.btn_strike,
                self.div_code,
                self.btn_code,
                self.btn_codeblock,
                self.btn_quote,
                self.div_lists,
                self.btn_ulist,
                self.btn_olist,
                self.btn_table,
                self.div_media,
                self.btn_link,
                self.btn_image,
                self.btn_more,
            ],
            scroll=None,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
        )
        self.content = self.row

    def set_compact_mode(self, is_compact: bool):
        """Switches between full expanded toolbar and compact 'More (⋯)' popup mode."""
        if self.is_compact == is_compact:
            return
        self.is_compact = is_compact

        # In compact mode: hide extended buttons and dividers, show More popup
        extended_visible = not is_compact
        self.btn_strike.visible = extended_visible
        self.btn_codeblock.visible = extended_visible
        self.btn_quote.visible = extended_visible
        self.btn_ulist.visible = extended_visible
        self.btn_olist.visible = extended_visible
        self.btn_table.visible = extended_visible
        self.btn_link.visible = extended_visible
        self.btn_image.visible = extended_visible
        self.div_code.visible = extended_visible
        self.div_lists.visible = extended_visible
        self.div_media.visible = extended_visible
        self.btn_more.visible = is_compact

        try:
            if self.page:
                self.update()
        except Exception:
            pass

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
        self.heading_dropdown.color = ft.Colors.WHITE if is_dark else ft.Colors.BLACK87
        self.heading_dropdown.label_style = ft.TextStyle(color=accent_primary, size=12)

        for btn in [
            self.btn_bold, self.btn_italic, self.btn_strike, self.btn_code,
            self.btn_codeblock, self.btn_quote, self.btn_ulist, self.btn_olist,
            self.btn_table, self.btn_link, self.btn_image
        ]:
            btn.icon_color = ft.Colors.WHITE if is_dark else ft.Colors.BLACK87

        if hasattr(self, "btn_more"):
            self.btn_more.icon_color = ft.Colors.WHITE if is_dark else ft.Colors.BLACK87

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

        if hasattr(self, "btn_more"):
            self.btn_more.tooltip = t("format.tooltip_more")
            self.item_strike.content = t("format.tooltip_strike")
            self.item_codeblock.content = t("format.tooltip_codeblock")
            self.item_quote.content = t("format.tooltip_quote")
            self.item_ulist.content = t("format.tooltip_ulist")
            self.item_olist.content = t("format.tooltip_olist")
            self.item_table.content = t("format.tooltip_table")
            self.item_link.content = t("format.tooltip_link")
            self.item_image.content = t("format.tooltip_image")

        try:
            if self.page:
                self.update()
        except Exception:
            pass
