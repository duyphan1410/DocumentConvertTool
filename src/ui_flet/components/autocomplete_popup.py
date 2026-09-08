"""
Autocomplete / Suggestion Popup Component for Flet Markdown Editor (PKB Phase 1.5).
Provides instant, responsive suggestions when typing `[[` (Wikilinks) or `#` (Tags).
Follows Material Design 3 and Flet standard theming with smooth animations.
"""
from __future__ import annotations

import os
from typing import Callable, Optional, List, Dict, Any
import flet as ft
from src.i18n import t
from src.ui_flet.theme import make_border, get_style_color, resolve_color, PALETTES


class AutocompletePopup(ft.Container):
    """
    Floating suggestion popup displaying matching wikilinks or tags.
    """

    def __init__(
        self,
        on_select_suggestion: Callable[[str, Dict[str, Any]], None],
        on_close: Optional[Callable[[], None]] = None,
        width: int = 340,
        max_height: int = 240,
        **kwargs,
    ):
        self.on_select_suggestion = on_select_suggestion
        self.on_close_callback = on_close
        self.mode: str = "wikilink"  # "wikilink" or "tag"
        self._items: List[Dict[str, Any]] = []
        self._selected_index: int = 0
        self._is_dark: bool = False
        self._palette: dict = {}

        # 1. Header Icon & Title
        self.header_icon = ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=14, color=ft.Colors.PRIMARY)
        self.header_title = ft.Text(
            t("autocomplete.wikilinks_title") if t("autocomplete.wikilinks_title") != "autocomplete.wikilinks_title" else "Gợi ý liên kết [[...]]",
            size=11,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.PRIMARY,
            expand=True,
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.btn_close = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_size=13,
            tooltip=t("common.close") if t("common.close") != "common.close" else "Đóng",
            style=ft.ButtonStyle(
                padding=ft.Padding(0, 0, 0, 0),
                shape=ft.RoundedRectangleBorder(radius=4),
            ),
            on_click=lambda _: self.hide(),
        )

        self.header_row = ft.Row(
            controls=[
                self.header_icon,
                self.header_title,
                self.btn_close,
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 2. Results List
        self.list_view = ft.ListView(
            controls=[],
            spacing=2,
            padding=ft.Padding(0, 2, 0, 2),
            height=180,
        )

        # 3. Empty State Text
        self.empty_text = ft.Text(
            t("autocomplete.no_matches") if t("autocomplete.no_matches") != "autocomplete.no_matches" else "Không có kết quả phù hợp",
            size=11,
            italic=True,
            color=ft.Colors.OUTLINE,
            text_align=ft.TextAlign.CENTER,
            visible=False,
        )

        self.content_column = ft.Column(
            controls=[
                self.header_row,
                ft.Divider(height=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
                self.list_view,
                self.empty_text,
            ],
            spacing=4,
            tight=True,
        )

        super().__init__(
            content=self.content_column,
            width=width,
            visible=False,
            padding=ft.Padding(left=10, top=8, right=10, bottom=8),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=make_border(1, ft.Colors.PRIMARY),
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=10,
                color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            **kwargs,
        )

    def show_suggestions(self, mode: str, items: List[Dict[str, Any]], query: str = ""):
        """Populates suggestions and makes popup visible."""
        self.mode = mode
        self._items = list(items)
        self._selected_index = 0

        if mode == "wikilink":
            self.header_icon.name = ft.Icons.LINK_ROUNDED
            self.header_icon.color = ft.Colors.PRIMARY
            title_txt = t("autocomplete.wikilinks_title")
            self.header_title.value = title_txt if title_txt != "autocomplete.wikilinks_title" else "Gợi ý liên kết [[...]]"
            self.header_title.color = ft.Colors.PRIMARY
            self.border = make_border(1, ft.Colors.PRIMARY)
        else:
            self.header_icon.name = ft.Icons.TAG_ROUNDED
            self.header_icon.color = ft.Colors.AMBER_400
            title_txt = t("autocomplete.tags_title")
            self.header_title.value = title_txt if title_txt != "autocomplete.tags_title" else "Gợi ý thẻ #..."
            self.header_title.color = ft.Colors.AMBER_400
            self.border = make_border(1, ft.Colors.AMBER_400)

        self.list_view.controls.clear()

        if not items:
            self.list_view.visible = False
            self.empty_text.visible = True
        else:
            self.list_view.visible = True
            self.empty_text.visible = False
            for idx, item in enumerate(items):
                card = self._build_item_card(item, idx == self._selected_index)
                self.list_view.controls.append(card)

        self.visible = True
        self._safe_update()

    def hide(self):
        """Hides the autocomplete popup cleanly."""
        if self.visible:
            self.visible = False
            self._items.clear()
            self._safe_update()
            if self.on_close_callback:
                try:
                    self.on_close_callback()
                except Exception:
                    pass

    def select_next(self):
        """Moves active selection down by 1."""
        if not self._items:
            return
        self._selected_index = (self._selected_index + 1) % len(self._items)
        self._rehighlight()

    def select_prev(self):
        """Moves active selection up by 1."""
        if not self._items:
            return
        self._selected_index = (self._selected_index - 1 + len(self._items)) % len(self._items)
        self._rehighlight()

    def select_current(self):
        """Dispatches the currently highlighted suggestion."""
        if self._items and 0 <= self._selected_index < len(self._items):
            self._handle_click_item(self._items[self._selected_index])

    def _rehighlight(self):
        for idx, ctrl in enumerate(self.list_view.controls):
            if isinstance(ctrl, ft.Container):
                is_sel = (idx == self._selected_index)
                ctrl.bgcolor = ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY) if is_sel else ft.Colors.SURFACE_CONTAINER
                try:
                    if ctrl.page:
                        ctrl.update()
                except Exception:
                    pass

    def _build_item_card(self, item: Dict[str, Any], is_selected: bool) -> ft.Container:
        if self.mode == "wikilink":
            title = item.get("title", "Note")
            rel_path = item.get("relative_path", os.path.basename(item.get("path", "")))
            content_ctrl = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ARTICLE_OUTLINED, size=13, color=ft.Colors.PRIMARY),
                    ft.Column(
                        controls=[
                            ft.Text(
                                title,
                                size=11,
                                weight=ft.FontWeight.W_600,
                                no_wrap=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                rel_path,
                                size=9,
                                color=ft.Colors.OUTLINE,
                                no_wrap=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=0,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.KEYBOARD_RETURN_ROUNDED, size=11, color=ft.Colors.OUTLINE),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        else:
            tag_name = item.get("name", "tag")
            doc_count = item.get("doc_count", 0)
            content_ctrl = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TAG_ROUNDED, size=13, color=ft.Colors.AMBER_400),
                    ft.Text(
                        f"#{tag_name}",
                        size=11,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.AMBER_400,
                        expand=True,
                        no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Container(
                        content=ft.Text(f"{doc_count} note{'s' if doc_count != 1 else ''}", size=9, color=ft.Colors.OUTLINE),
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_400),
                        border_radius=6,
                        padding=ft.Padding(4, 1, 4, 1),
                    ),
                    ft.Icon(ft.Icons.KEYBOARD_RETURN_ROUNDED, size=11, color=ft.Colors.OUTLINE),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        container = ft.Container(
            content=content_ctrl,
            padding=ft.Padding(left=8, top=5, right=8, bottom=5),
            border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY) if is_selected else ft.Colors.SURFACE_CONTAINER,
            border=make_border(1, ft.Colors.OUTLINE_VARIANT),
            ink=True,
            on_click=lambda e, it=item: self._handle_click_item(it),
        )
        return container

    def _handle_click_item(self, item: Dict[str, Any]):
        self.hide()
        if self.on_select_suggestion:
            self.on_select_suggestion(self.mode, item)

    def apply_palette(self, palette: dict, is_dark: bool):
        self._is_dark = is_dark
        self._palette = palette
        self._safe_update()

    def _safe_update(self):
        try:
            if hasattr(self, "page") and self.page:
                self.update()
        except Exception:
            pass
