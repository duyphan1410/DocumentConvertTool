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
    ):
        self.on_search_changed = on_search_changed
        self.on_find_next = on_find_next
        self.on_find_prev = on_find_prev
        self.on_replace = on_replace
        self.on_replace_all = on_replace_all

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

        self.container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(controls=[
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
                        self.lbl_search_match,
                    ]),
                    ft.Row(controls=[
                        self.replace_input,
                        ft.ElevatedButton("Replace", on_click=self.on_replace),
                        ft.ElevatedButton("Replace All", on_click=self.on_replace_all),
                    ]),
                ],
                spacing=6,
            ),
            padding=8,
            border_radius=6,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            visible=False,
        )

    def toggle_visibility(self) -> bool:
        self.container.visible = not self.container.visible
        if self.container.page:
            self.container.update()
        return self.container.visible

    def set_match_label(self, text: str):
        self.lbl_search_match.value = text
        if self.lbl_search_match.page:
            self.lbl_search_match.update()
