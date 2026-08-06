"""
Help View for DocConvert Workspace.
Contains two internal tabs: Help (shortcuts, format matrix, FAQ) and User Guide (step-by-step cards).
Pure Flet layout — no Markdown rendering. Follows Flet 0.86.4 Desktop standards.
"""
from __future__ import annotations

from typing import Callable, Optional
import flet as ft
from src.i18n import t

from src.ui_flet.theme import resolve_color, make_border


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
        self.padding = ft.Padding(left=20, top=14, right=20, bottom=14)

        self._active_tab = "help"

        # ── Internal Tab Buttons ──────────────────────────────────────────────
        self._btn_help = ft.TextButton(
            t("help.tab_help"),
            icon=ft.Icons.HELP_OUTLINE_ROUNDED,
            on_click=lambda _: self._switch_tab("help"),
        )
        self._btn_guide = ft.TextButton(
            t("help.tab_guide"),
            icon=ft.Icons.MENU_BOOK_ROUNDED,
            on_click=lambda _: self._switch_tab("guide"),
        )

        self._tab_row = ft.Row(
            [self._btn_help, self._btn_guide],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # ── Content Area ─────────────────────────────────────────────────────
        self._content_area = ft.Container(
            content=self._build_help_tab(),
            expand=True,
            padding=ft.Padding(left=0, top=8, right=0, bottom=0),
        )

        # ── Close Button ─────────────────────────────────────────────────────
        self._btn_close = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_size=20,
            tooltip=t("help.tooltip_close"),
            on_click=self._on_close_click,
        )

        # ── Page Header ──────────────────────────────────────────────────────
        self._title_text = ft.Text(t("help.title"), size=20, weight=ft.FontWeight.BOLD)
        header = ft.Row(
            [
                ft.Icon(ft.Icons.HELP_CENTER_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                self._title_text,
                ft.Container(expand=True),
                self._btn_close,
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.content = ft.Column(
            [
                header,
                ft.Divider(height=1),
                self._tab_row,
                ft.Divider(height=1),
                self._content_area,
            ],
            spacing=10,
            expand=True,
        )
        self._highlight_tabs()

    # ─────────────────────────────────────────────────────────────────────────
    # Internal tab builder
    # ─────────────────────────────────────────────────────────────────────────

    def _build_help_tab(self) -> ft.Column:
        return ft.Column(
            [
                self._build_shortcuts_section(),
                ft.Container(height=16),
                self._build_format_matrix_section(),
                ft.Container(height=16),
                self._build_faq_section(),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            expand=True,
        )

    def _build_shortcuts_section(self) -> ft.Container:
        shortcuts = [
            ("Ctrl + O", t("help.sc_open")),
            ("Ctrl + S", t("help.sc_save")),
            ("Ctrl + Z", t("help.sc_undo")),
            ("Ctrl + Y / Ctrl + Shift + Z", t("help.sc_redo")),
            ("Ctrl + F", t("help.sc_find")),
            ("Ctrl + A", t("help.sc_select_all")),
        ]
        rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Container(
                    content=ft.Text(shortcut, size=12, font_family="Consolas", weight=ft.FontWeight.BOLD),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    padding=ft.Padding(left=8, top=4, right=8, bottom=4),
                    border_radius=4,
                )),
                ft.DataCell(ft.Text(desc, size=13)),
            ])
            for shortcut, desc in shortcuts
        ]
        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(t("help.col_shortcut"), weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(t("help.col_action"), weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            column_spacing=24,
            data_row_max_height=40,
        )
        return ft.Container(
            content=ft.Column(
                [self._section_header(t("help.sec_shortcuts")), table],
                spacing=8,
            ),
        )

    def _build_format_matrix_section(self) -> ft.Container:
        formats = [
            ("Markdown (.md)", True, True),
            ("Word (.docx)", True, True),
            ("Excel (.xlsx)", True, True),
            ("CSV (.csv)", True, True),
            ("PDF (.pdf)", True, True),
            ("HTML (.html)", True, True),
        ]

        def _check(val: bool):
            return ft.Icon(
                ft.Icons.CHECK_CIRCLE_ROUNDED if val else ft.Icons.CANCEL_ROUNDED,
                color=ft.Colors.GREEN_400 if val else ft.Colors.RED_400,
                size=18,
            )

        rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(fmt, size=13)),
                ft.DataCell(_check(load)),
                ft.DataCell(_check(save)),
            ])
            for fmt, load, save in formats
        ]
        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(t("help.col_format"), weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(t("help.col_load"), weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(t("help.col_save"), weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            column_spacing=32,
            data_row_max_height=40,
        )
        return ft.Container(
            content=ft.Column(
                [self._section_header(t("help.sec_matrix")), table],
                spacing=8,
            ),
        )

    def _build_faq_section(self) -> ft.Container:
        faqs = [
            (t("help.faq_q1"), t("help.faq_a1")),
            (t("help.faq_q2"), t("help.faq_a2")),
            (t("help.faq_q3"), t("help.faq_a3")),
            (t("help.faq_q4"), t("help.faq_a4")),
            (t("help.faq_q5"), t("help.faq_a5")),
        ]

        panels = [
            ft.ExpansionPanel(
                header=ft.Container(
                    content=ft.Text(q, size=13, weight=ft.FontWeight.W_500),
                    padding=ft.Padding(left=8, top=0, right=8, bottom=0),
                ),
                content=ft.Container(
                    content=ft.Text(a, size=12, color=ft.Colors.OUTLINE),
                    padding=ft.Padding(left=16, top=0, right=16, bottom=12),
                ),
            )
            for q, a in faqs
        ]

        panel_list = ft.ExpansionPanelList(controls=panels, spacing=4)

        return ft.Container(
            content=ft.Column(
                [self._section_header(t("help.sec_faq")), panel_list],
                spacing=8,
            ),
        )

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
                            content=ft.Icon(icon, color=ft.Colors.ON_PRIMARY, size=28),
                            bgcolor=ft.Colors.PRIMARY,
                            border_radius=12,
                            padding=12,
                            width=52,
                            height=52,
                            alignment=ft.alignment.Alignment(0.0, 0.0),
                        ),
                        ft.Column(
                            [
                                ft.Text(title, size=14, weight=ft.FontWeight.BOLD),
                                ft.Text(desc, size=12, color=ft.Colors.OUTLINE),
                            ],
                            spacing=4,
                            expand=True,
                        ),
                    ],
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                border_radius=10,
                padding=ft.Padding(left=16, top=12, right=16, bottom=12),
            )
            step_cards.append(card)

        cta_button = ft.FilledButton(
            t("help.btn_get_started"),
            icon=ft.Icons.ROCKET_LAUNCH_ROUNDED,
            height=44,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=24, top=10, right=24, bottom=10),
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.WHITE,
            ),
            on_click=self._on_get_started_click,
        )

        return ft.Column(
            [
                self._section_header(t("help.sec_guide")),
                *step_cards,
                ft.Container(height=8),
                ft.Row([cta_button], alignment=ft.MainAxisAlignment.CENTER),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
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
                shape=ft.RoundedRectangleBorder(radius=8),
                bgcolor=ft.Colors.PRIMARY_CONTAINER if is_active else None,
                color=ft.Colors.ON_PRIMARY_CONTAINER if is_active else None,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _section_header(self, text: str) -> ft.Text:
        return ft.Text(text, size=14, weight=ft.FontWeight.BOLD)

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
        self._btn_help.content = t("help.tab_help")
        self._btn_guide.content = t("help.tab_guide")
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
