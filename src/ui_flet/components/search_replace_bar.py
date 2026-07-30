"""
Search & Replace UI Panel Component.
"""
from typing import Callable
import flet as ft


class SearchReplaceBar:
    def __init__(
        self,
        on_search_changed: Callable[[ft.ControlEvent], None],
        on_find_next: Callable[[ft.ControlEvent], None],
        on_find_prev: Callable[[ft.ControlEvent], None],
        on_replace: Callable[[ft.ControlEvent], None],
        on_replace_all: Callable[[ft.ControlEvent], None],
        on_match_click: Callable[[int, int], None] = None,
    ):
        self.on_search_changed = on_search_changed
        self.on_find_next = on_find_next
        self.on_find_prev = on_find_prev
        self.on_replace = on_replace
        self.on_replace_all = on_replace_all
        self.on_match_click = on_match_click

        self.search_input = ft.TextField(
            label="Find",
            dense=True,
            expand=True,
            on_submit=self.on_find_next,
            on_change=self.on_search_changed,
        )
        self.replace_input = ft.TextField(
            label="Replace",
            dense=True,
            expand=True,
            on_submit=self.on_replace,
        )
        self.chk_regex = ft.Checkbox(
            label="Regex",
            value=False,
            on_change=self.on_search_changed,
        )
        self.chk_case = ft.Checkbox(
            label="Match Case",
            value=False,
            on_change=self.on_search_changed,
        )
        self.lbl_search_match = ft.Text(
            "0 matches",
            size=12,
            color=ft.Colors.GREY_500,
        )


        # ── Results List Panel (goes into EditorView) ────────────────────────
        self.results_column = ft.Column(
            spacing=3,
            scroll=ft.ScrollMode.AUTO,
        )
        side = ft.BorderSide(width=1, color=ft.Colors.OUTLINE_VARIANT)
        self.results_container = ft.Container(
            content=self.results_column,
            height=130,
            visible=False,
            padding=ft.Padding(left=10, top=6, right=10, bottom=6),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border=ft.Border(left=side, top=side, right=side, bottom=side),
        )

        # ── Toggle Replace ▼/▲ ───────────────────────────────────────────────
        self.btn_toggle_replace = ft.IconButton(
            icon=ft.Icons.EXPAND_MORE,
            tooltip="Show Replace options",
            on_click=self._toggle_replace_row,
        )

        self.replace_row = ft.Row(
            controls=[
                self.replace_input,
                ft.ElevatedButton("Replace", on_click=self.on_replace),
                ft.ElevatedButton("Replace All", on_click=self.on_replace_all),
            ],
        )

        # ── Find Row (inline in Ribbon) ──────────────────────────────────────
        self.find_row = ft.Row(
            controls=[
                self.search_input,
                ft.IconButton(
                    ft.Icons.NAVIGATE_BEFORE,
                    tooltip="Find Previous",
                    on_click=self.on_find_prev,
                ),
                ft.IconButton(
                    ft.Icons.NAVIGATE_NEXT,
                    tooltip="Find Next",
                    on_click=self.on_find_next,
                ),
                self.chk_regex,
                self.chk_case,
                self.btn_toggle_replace,
                self.lbl_search_match,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        )

        # ── Containers with padding for clean layout ─────────────────────────
        self.find_container = ft.Container(
            content=self.find_row,
            padding=ft.Padding(left=2, top=6, right=12, bottom=2),
        )

        self.replace_container = ft.Container(
            content=self.replace_row,
            padding=ft.Padding(left=2, top=6, right=12, bottom=6),
            visible=False,
        )

        # ── Ribbon Search Panel (Find row + collapsible Replace row) ─────────
        # This Column is placed inside RibbonBar's panel_container
        self.ribbon_search_panel = ft.Column(
            controls=[
                self.find_container,
                self.replace_container,
            ],
            spacing=4,
        )

        # Legacy container kept for backward compatibility but no longer used
        # in EditorView. Use ribbon_search_panel + results_container separately.
        self.container = ft.Container(
            content=self.ribbon_search_panel,
            visible=False,
        )

    def _toggle_replace_row(self, e=None):
        self.replace_container.visible = not self.replace_container.visible
        self.btn_toggle_replace.icon = (
            ft.Icons.EXPAND_LESS if self.replace_container.visible else ft.Icons.EXPAND_MORE
        )
        try:
            if self.replace_container.page:
                self.replace_container.update()
        except Exception:
            pass
        try:
            if self.btn_toggle_replace.page:
                self.btn_toggle_replace.update()
        except Exception:
            pass

    def toggle_visibility(self) -> bool:
        self.container.visible = not self.container.visible
        try:
            if self.container.page:
                self.container.update()
        except Exception:
            pass
        return self.container.visible

    def set_match_label(self, text: str):
        self.lbl_search_match.value = text
        try:
            if self.lbl_search_match.page:
                self.lbl_search_match.update()
        except Exception:
            pass

    def focus_search_input(self):
        try:
            if self.search_input.page:
                import asyncio
                res = self.search_input.focus()
                if asyncio.iscoroutine(res):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        pass
        except Exception:
            pass

    def update_results(self, matches: list[dict], current_idx: int = -1):
        """Populates the Word/VS Code style Search Navigation Results list panel."""
        self.results_column.controls.clear()
        if not matches:
            self.results_container.visible = False
        else:
            self.results_container.visible = True
            for i, m in enumerate(matches[:40]):
                start = m["start"]
                end = m["end"]
                snippet = m.get("snippet", "")
                is_active = (i == current_idx)

                def make_click_handler(s, e):
                    return lambda _: self.on_match_click(s, e) if self.on_match_click else None

                item = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.SEARCH,
                                size=14,
                                color=ft.Colors.PRIMARY if is_active else ft.Colors.OUTLINE,
                            ),
                            ft.Text(
                                snippet,
                                size=12,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                                color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE,
                            ),
                        ],
                        spacing=6,
                    ),
                    padding=ft.Padding(left=8, top=4, right=8, bottom=4),
                    border_radius=4,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST if is_active else None,
                    on_click=make_click_handler(start, end),
                    ink=True,
                    tooltip="Click to jump to match line in Editor",
                )
                self.results_column.controls.append(item)

        try:
            if self.results_container.page:
                self.results_container.update()
        except Exception:
            pass
