"""
Help View for DocConvert Workspace.
Contains two internal tabs: Help (shortcuts, format matrix, markdown cheat sheet, pro tips, FAQ)
and User Guide (step-by-step cards).
Follows Flet 0.86.4 Desktop standards and modern UX/UI 4/8dp rhythm.
"""
from __future__ import annotations

from typing import Callable, Optional
import flet as ft
from src.i18n import t
from src.ui_flet.theme import resolve_color, make_border


class FaqItem(ft.Container):
    """Sleek collapsible FAQ accordion item with crisp left alignment."""

    def __init__(self, question: str, answer: str, **kwargs):
        super().__init__(**kwargs)
        self.question = question
        self.answer = answer
        self._is_open = False

        self.icon_arrow = ft.Icon(
            ft.Icons.KEYBOARD_ARROW_RIGHT_ROUNDED,
            size=16,
            color=ft.Colors.OUTLINE,
        )
        self.lbl_question = ft.Text(
            question,
            size=12,
            weight=ft.FontWeight.W_600,
            expand=True,
        )

        self.header_row = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.HELP_OUTLINE_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                    self.lbl_question,
                    self.icon_arrow,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=8, top=6, right=8, bottom=6),
            border_radius=6,
            ink=True,
            on_click=self._toggle,
        )

        self.answer_box = ft.Container(
            content=ft.Text(
                answer,
                size=12,
                color=ft.Colors.OUTLINE,
                text_align=ft.TextAlign.START,
            ),
            padding=ft.Padding(left=31, top=2, right=12, bottom=8),
            alignment=ft.alignment.Alignment(-1.0, 0.0),
            visible=False,
        )

        self.content = ft.Column(
            [self.header_row, self.answer_box],
            spacing=0,
        )
        self.border_radius = 6

    def _toggle(self, e):
        self._is_open = not self._is_open
        self.answer_box.visible = self._is_open
        self.icon_arrow.name = (
            ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED if self._is_open else ft.Icons.KEYBOARD_ARROW_RIGHT_ROUNDED
        )
        self.icon_arrow.color = ft.Colors.PRIMARY if self._is_open else ft.Colors.OUTLINE
        if self.page:
            try:
                self.update()
            except Exception:
                pass


class HelpView(ft.Container):
    """Full-workspace Help & User Guide view with internal tab switcher."""

    def __init__(
        self,
        on_get_started: Optional[Callable] = None,
        on_close: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._on_get_started = on_get_started
        self._on_close = on_close
        self.expand = True
        self.padding = ft.Padding(left=16, top=10, right=16, bottom=10)

        self._active_tab = "help"

        # ── Internal Tab Buttons ──────────────────────────────────────────────
        self._btn_help = ft.TextButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.HELP_OUTLINE_ROUNDED, size=16), ft.Text(t("help.tab_help"), size=12)],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=lambda _: self._switch_tab("help"),
        )
        self._btn_guide = ft.TextButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=16), ft.Text(t("help.tab_guide"), size=12)],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=lambda _: self._switch_tab("guide"),
        )

        self._tab_row = ft.Row(
            [self._btn_help, self._btn_guide],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # ── Content Area ─────────────────────────────────────────────────────
        self._content_area = ft.Container(
            content=self._build_help_tab(),
            expand=True,
            padding=ft.Padding(left=0, top=4, right=0, bottom=0),
        )

        # ── Close Button ─────────────────────────────────────────────────────
        self._btn_close = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_size=18,
            tooltip=t("help.tooltip_close"),
            on_click=self._on_close_click,
        )

        # ── Page Header ──────────────────────────────────────────────────────
        self._title_text = ft.Text(t("help.title"), size=16, weight=ft.FontWeight.BOLD)
        header = ft.Row(
            [
                ft.Icon(ft.Icons.HELP_CENTER_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                self._title_text,
                ft.Container(expand=True),
                self._btn_close,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.content = ft.Column(
            [
                header,
                ft.Divider(height=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
                self._tab_row,
                ft.Divider(height=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
                self._content_area,
            ],
            spacing=8,
            expand=True,
        )
        self._highlight_tabs()

    # ─────────────────────────────────────────────────────────────────────────
    # Internal tab builder - Help & Documentation
    # ─────────────────────────────────────────────────────────────────────────

    def _build_help_tab(self) -> ft.Column:
        left_col = ft.Column(
            [
                self._build_shortcuts_card(),
                self._build_markdown_syntax_card(),
            ],
            spacing=10,
            expand=True,
        )

        right_col = ft.Column(
            [
                self._build_format_matrix_card(),
                self._build_pro_tips_card(),
            ],
            spacing=10,
            expand=True,
        )

        grid_row = ft.Row(
            [left_col, right_col],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        faq_card = self._build_faq_card()

        return ft.Column(
            [
                grid_row,
                ft.Container(height=2),
                faq_card,
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
            expand=True,
        )

    # ── 1. Shortcuts Card ────────────────────────────────────────────────────

    def _build_shortcuts_card(self) -> ft.Container:
        shortcuts = [
            ("Ctrl + O", t("help.sc_open")),
            ("Ctrl + S", t("help.sc_save")),
            ("Ctrl + F", t("help.sc_find")),
            ("Ctrl + Z", t("help.sc_undo")),
            ("Ctrl + Y", t("help.sc_redo")),
            ("Ctrl + A", t("help.sc_select_all")),
        ]
        rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Container(
                    content=ft.Text(sc, size=11, font_family="Consolas", weight=ft.FontWeight.BOLD),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    padding=ft.Padding(left=6, top=2, right=6, bottom=2),
                    border_radius=4,
                )),
                ft.DataCell(ft.Text(desc, size=12)),
            ])
            for sc, desc in shortcuts
        ]
        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(t("help.col_shortcut"), size=12, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(t("help.col_action"), size=12, weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            column_spacing=16,
            data_row_max_height=32,
            heading_row_height=34,
        )
        return self._make_card(
            title=t("help.sec_shortcuts"),
            icon=ft.Icons.KEYBOARD_ROUNDED,
            content=table,
        )

    # ── 2. Markdown Syntax Card ──────────────────────────────────────────────

    def _build_markdown_syntax_card(self) -> ft.Container:
        items = [
            ("# Header", t("help.md_h1")),
            ("**Bold**", t("help.md_bold")),
            ("*Italic*", t("help.md_italic")),
            ("~~Strike~~", t("help.md_strike")),
            ("`code`", t("help.md_code")),
            ("> Quote", t("help.md_quote")),
            ("| Col 1 | Col 2 |", t("help.md_table")),
            ("![Alt](img.png)", t("help.md_image")),
        ]
        rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Container(
                    content=ft.Text(syntax, size=11, font_family="Consolas", weight=ft.FontWeight.BOLD),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    padding=ft.Padding(left=6, top=2, right=6, bottom=2),
                    border_radius=4,
                )),
                ft.DataCell(ft.Text(meaning, size=12)),
            ])
            for syntax, meaning in items
        ]
        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Cú pháp / Syntax", size=12, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Kết quả / Meaning", size=12, weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            column_spacing=16,
            data_row_max_height=32,
            heading_row_height=34,
        )
        return self._make_card(
            title=t("help.sec_markdown"),
            icon=ft.Icons.EDIT_NOTE_ROUNDED,
            content=table,
        )

    # ── 3. Format Support Matrix Card ────────────────────────────────────────

    def _build_format_matrix_card(self) -> ft.Container:
        formats = [
            ("Markdown (.md)", True, True),
            ("Word (.docx)", True, True),
            ("Excel (.xlsx)", True, True),
            ("CSV (.csv)", True, True),
            ("PDF (.pdf)", True, True),
            ("HTML (.html)", True, True),
            ("JSON / YAML", True, True),
            ("PowerPoint (.pptx)", True, True),
        ]

        def _check(val: bool):
            return ft.Icon(
                ft.Icons.CHECK_CIRCLE_ROUNDED if val else ft.Icons.CANCEL_ROUNDED,
                color=ft.Colors.GREEN_400 if val else ft.Colors.RED_400,
                size=16,
            )

        rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(fmt, size=12)),
                ft.DataCell(_check(load)),
                ft.DataCell(_check(save)),
            ])
            for fmt, load, save in formats
        ]
        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(t("help.col_format"), size=12, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(t("help.col_load"), size=12, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(t("help.col_save"), size=12, weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            column_spacing=24,
            data_row_max_height=32,
            heading_row_height=34,
        )
        return self._make_card(
            title=t("help.sec_matrix"),
            icon=ft.Icons.DESCRIPTION_ROUNDED,
            content=table,
        )

    # ── 4. Pro Tips Card ─────────────────────────────────────────────────────

    def _build_pro_tips_card(self) -> ft.Container:
        tips = [
            (ft.Icons.RESTORE_ROUNDED, t("help.tip_autosave")),
            (ft.Icons.PALETTE_OUTLINED, t("help.tip_palette")),
            (ft.Icons.IMAGE_OUTLINED, t("help.tip_images")),
            (ft.Icons.SEARCH_ROUNDED, t("help.tip_search")),
        ]
        tip_rows = [
            ft.Row(
                [
                    ft.Icon(icon, size=16, color=ft.Colors.PRIMARY),
                    ft.Text(text, size=12, expand=True),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.START,
            )
            for icon, text in tips
        ]
        content_col = ft.Column(tip_rows, spacing=8)
        return self._make_card(
            title=t("help.sec_tips"),
            icon=ft.Icons.LIGHTBULB_OUTLINE_ROUNDED,
            content=content_col,
        )

    # ── 5. FAQ Card ──────────────────────────────────────────────────────────

    def _build_faq_card(self) -> ft.Container:
        faqs = [
            (t("help.faq_q1"), t("help.faq_a1")),
            (t("help.faq_q2"), t("help.faq_a2")),
            (t("help.faq_q3"), t("help.faq_a3")),
            (t("help.faq_q4"), t("help.faq_a4")),
            (t("help.faq_q5"), t("help.faq_a5")),
        ]

        faq_items = [FaqItem(q, a) for q, a in faqs]
        faq_col = ft.Column(faq_items, spacing=2)

        return self._make_card(
            title=t("help.sec_faq"),
            icon=ft.Icons.HELP_ROUNDED,
            content=faq_col,
        )

    # ── Card Builder Helper ──────────────────────────────────────────────────

    def _make_card(self, title: str, icon: str, content: ft.Control) -> ft.Container:
        header = ft.Row(
            [
                ft.Icon(icon, size=16, color=ft.Colors.PRIMARY),
                ft.Text(title, size=13, weight=ft.FontWeight.BOLD),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return ft.Container(
            content=ft.Column(
                [
                    header,
                    ft.Divider(height=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
                    content,
                ],
                spacing=6,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border_radius=8,
            padding=ft.Padding(left=12, top=8, right=12, bottom=10),
            border=ft.Border(
                left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Internal tab builder - Quick Start User Guide
    # ─────────────────────────────────────────────────────────────────────────

    def _build_guide_tab(self) -> ft.Column:
        steps = [
            (
                ft.Icons.FOLDER_OPEN_ROUNDED,
                t("help.step1_title"),
                t("help.step1_desc"),
            ),
            (
                ft.Icons.TRANSFORM,
                t("help.step2_title"),
                t("help.step2_desc"),
            ),
            (
                ft.Icons.SAVE_AS,
                t("help.step3_title"),
                t("help.step3_desc"),
            ),
            (
                ft.Icons.PLAY_CIRCLE_OUTLINE,
                t("help.step4_title"),
                t("help.step4_desc"),
            ),
            (
                ft.Icons.OPEN_IN_NEW,
                t("help.step5_title"),
                t("help.step5_desc"),
            ),
        ]

        step_cards = []
        for icon, title, desc in steps:
            card = ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(icon, color=ft.Colors.ON_PRIMARY, size=20),
                            bgcolor=ft.Colors.PRIMARY,
                            border_radius=8,
                            padding=8,
                            width=38,
                            height=38,
                            alignment=ft.alignment.Alignment(0.0, 0.0),
                        ),
                        ft.Column(
                            [
                                ft.Text(title, size=13, weight=ft.FontWeight.BOLD),
                                ft.Text(desc, size=12, color=ft.Colors.OUTLINE),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                border_radius=8,
                padding=ft.Padding(left=12, top=8, right=12, bottom=8),
                border=ft.Border(
                    left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                ),
            )
            step_cards.append(card)

        cta_button = ft.FilledButton(
            t("help.btn_get_started"),
            icon=ft.Icons.ROCKET_LAUNCH_ROUNDED,
            height=36,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(left=18, top=6, right=18, bottom=6),
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.WHITE,
            ),
            on_click=self._on_get_started_click,
        )

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                        ft.Text(t("help.sec_guide"), size=13, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=6,
                ),
                *step_cards,
                ft.Container(height=4),
                ft.Row([cta_button], alignment=ft.MainAxisAlignment.CENTER),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=8,
            expand=True,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Tab switching
    # ─────────────────────────────────────────────────────────────────────────

    def _switch_tab(self, tab: str):
        self._active_tab = tab
        self._content_area.content = (
            self._build_help_tab() if tab == "help" else self._build_guide_tab()
        )
        self._highlight_tabs()
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def _highlight_tabs(self):
        for tab, btn in [("help", self._btn_help), ("guide", self._btn_guide)]:
            is_active = tab == self._active_tab
            btn.style = ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                bgcolor=ft.Colors.PRIMARY_CONTAINER if is_active else None,
                color=ft.Colors.ON_PRIMARY_CONTAINER if is_active else None,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers & Handlers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_get_started_click(self, e):
        if self._on_get_started:
            self._on_get_started(e)

    def _on_close_click(self, e):
        if self._on_close:
            self._on_close(e)

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

    def update_locale(self):
        """Refresh header title, tabs, tooltip, and inner content in HelpView."""
        if hasattr(self, "_btn_help") and hasattr(self._btn_help, "content") and hasattr(self._btn_help.content, "controls"):
            self._btn_help.content.controls[1].value = t("help.tab_help")
        if hasattr(self, "_btn_guide") and hasattr(self._btn_guide, "content") and hasattr(self._btn_guide.content, "controls"):
            self._btn_guide.content.controls[1].value = t("help.tab_guide")

        self._btn_close.tooltip = t("help.tooltip_close")
        self._title_text.value = t("help.title")
        self._content_area.content = (
            self._build_help_tab() if self._active_tab == "help" else self._build_guide_tab()
        )
        try:
            if self.page:
                self.update()
        except Exception:
            pass
