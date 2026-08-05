"""
Help View for DocConvert Workspace.
Contains two internal tabs: Help (shortcuts, format matrix, FAQ) and User Guide (step-by-step cards).
Pure Flet layout — no Markdown rendering. Follows Flet 0.86.4 Desktop standards.
"""
from __future__ import annotations

from typing import Callable, Optional
import flet as ft

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
            "Help",
            icon=ft.Icons.HELP_OUTLINE_ROUNDED,
            on_click=lambda _: self._switch_tab("help"),
        )
        self._btn_guide = ft.TextButton(
            "User Guide",
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
        btn_close = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_size=20,
            tooltip="Close Help (Return to Editor)",
            on_click=self._on_close_click,
        )

        # ── Page Header ──────────────────────────────────────────────────────
        header = ft.Row(
            [
                ft.Icon(ft.Icons.HELP_CENTER_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                ft.Text("Help & User Guide", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                btn_close,
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
            ("Ctrl + O", "Open document"),
            ("Ctrl + S", "Save / Convert"),
            ("Ctrl + Z", "Undo"),
            ("Ctrl + Y", "Redo"),
            ("Ctrl + F", "Find & Replace"),
            ("Ctrl + A", "Select all text"),
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
                ft.DataColumn(ft.Text("Shortcut", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Action", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            column_spacing=24,
            data_row_max_height=40,
        )
        return ft.Container(
            content=ft.Column(
                [self._section_header("⌨  Keyboard Shortcuts"), table],
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
                ft.DataColumn(ft.Text("Format", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Load", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Save", weight=ft.FontWeight.BOLD)),
            ],
            rows=rows,
            column_spacing=32,
            data_row_max_height=40,
        )
        return ft.Container(
            content=ft.Column(
                [self._section_header("📄  Format Support Matrix"), table],
                spacing=8,
            ),
        )

    def _build_faq_section(self) -> ft.Container:
        faqs = [
            (
                "How do I convert a Word file to Markdown?",
                "Go to File tab → Open Document, select your .docx file. The app auto-detects the format. "
                "Choose 'Word → MD' mode in the ribbon, set an output path, then click Convert Now.",
            ),
            (
                "Why is my PDF conversion blank?",
                "PDF export requires WeasyPrint or ReportLab. Run 'pip install weasyprint' in your environment "
                "and restart the app. A dependency warning will appear in the footer if they are missing.",
            ),
            (
                "Can I edit the Markdown directly in the app?",
                "Yes — the Editor panel is fully editable. Use the Edit tab in the ribbon for formatting shortcuts "
                "like Heading H1–H6, Bold, Italic, and Code blocks.",
            ),
            (
                "Where are my auto-saved drafts stored?",
                "Drafts are saved to %APPDATA%\\DocConvert\\draft_autosave.md and restored automatically "
                "when you reopen the app.",
            ),
            (
                "How do I change the color theme?",
                "Use the Settings tab in the ribbon. You can choose from 4 palettes (Violet Cyberpunk, "
                "Emerald Obsidian, Deep Ocean, Sunset Gold) and switch between Dark, Light, or System mode.",
            ),
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
                [self._section_header("❓  Frequently Asked Questions"), panel_list],
                spacing=8,
            ),
        )

    def _build_guide_tab(self) -> ft.Column:
        steps = [
            (
                ft.Icons.FOLDER_OPEN_ROUNDED,
                "Step 1 — Open a Document",
                "Click 'Open Document' in the File tab or press Ctrl+O. "
                "Supported formats: .md, .docx, .xlsx, .csv, .pdf, .html",
            ),
            (
                ft.Icons.TRANSFORM,
                "Step 2 — Choose a Conversion Mode",
                "Select your target format from the mode dropdown (e.g. 'Word → MD'). "
                "The mode is automatically suggested based on the file you opened.",
            ),
            (
                ft.Icons.SAVE_AS,
                "Step 3 — Set Output Path",
                "The output path is pre-filled automatically. You can browse to a custom location "
                "using 'Save Destination' in the File tab.",
            ),
            (
                ft.Icons.PLAY_CIRCLE_OUTLINE,
                "Step 4 — Convert",
                "Click the 'CONVERT NOW' button in the action bar at the bottom. "
                "A progress bar shows conversion status.",
            ),
            (
                ft.Icons.OPEN_IN_NEW,
                "Step 5 — Open Your Result",
                "Once complete, use the 'Open File' or 'Open Folder' buttons to access your output. "
                "The converted file can be found at the path shown in the status bar.",
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
            "Get Started →",
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
                self._section_header("🚀  Quick Start Guide"),
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
