"""
Floating Context Menu Component for DocConvert Studio Workspace.
Renders IDE-style right-click menus for files and folders with dark/light theme tokens,
precise coordinates positioning, click-outside backdrop dismissal, and hover-triggered secondary flyout submenus.
Fully integrated with i18n localization.
"""
from __future__ import annotations

import os
import flet as ft
from typing import Callable, Optional, List

from src.i18n import t


class ContextMenuItem(ft.Container):
    """An individual actionable item inside the Context Menu with native gesture hover enter/exit hooks."""

    def __init__(
        self,
        title: str,
        icon: str,
        on_click: Optional[Callable[[], None]] = None,
        on_hover: Optional[Callable[[bool], None]] = None,
        color: Optional[str] = None,
        icon_color: Optional[str] = None,
        trailing_icon: Optional[str] = None,
    ):
        self._action_callback = on_click
        self._hover_callback = on_hover

        trailing_ctrl = (
            ft.Icon(trailing_icon, size=14, color=ft.Colors.OUTLINE)
            if trailing_icon
            else ft.Container()
        )

        row_content = ft.Row(
            [
                ft.Icon(icon, size=15, color=icon_color or color or ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(
                    title,
                    size=12,
                    weight=ft.FontWeight.W_500,
                    color=color or ft.Colors.ON_SURFACE,
                    no_wrap=True,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    expand=True,
                ),
                trailing_ctrl,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        super().__init__(
            content=ft.GestureDetector(
                content=row_content,
                on_tap=self._handle_click,
                on_enter=self._handle_enter,
                on_exit=self._handle_exit,
            ),
            padding=ft.Padding(left=10, top=6, right=10, bottom=6),
            border_radius=6,
            ink=True,
            on_hover=self._handle_hover,
        )

    def _handle_click(self, e=None):
        if self._action_callback:
            self._action_callback()

    def _handle_enter(self, e=None):
        self.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)
        try:
            if self.page:
                self.update()
        except Exception:
            pass
        if self._hover_callback:
            self._hover_callback(True)

    def _handle_exit(self, e=None):
        self.bgcolor = ft.Colors.TRANSPARENT
        try:
            if self.page:
                self.update()
        except Exception:
            pass
        if self._hover_callback:
            self._hover_callback(False)

    def _handle_hover(self, e):
        # Fallback for platforms triggering container hover
        is_hover = e.data == "true"
        if is_hover:
            self._handle_enter()
        else:
            self._handle_exit()


class ContextMenuDivider(ft.Container):
    """Subtle horizontal divider separating menu item groups."""

    def __init__(self):
        super().__init__(
            content=ft.Divider(height=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
            padding=ft.Padding(left=4, top=2, right=4, bottom=2),
        )


class ExplorerContextMenu:
    """
    Manages floating context menu lifecycle, backdrop overlay, hover submenus, and action dispatching.
    """

    def __init__(self, page: ft.Page):
        self.page = page
        self._overlay_container: Optional[ft.Container] = None
        self._submenu_card: Optional[ft.Container] = None
        self._is_showing: bool = False
        self._menu_x: float = 0
        self._menu_y: float = 0
        self._menu_width: float = 220

    def hide(self, e=None):
        """Dismisses the context menu and any active submenu from the page overlay."""
        if self._overlay_container and self._overlay_container in self.page.overlay:
            self.page.overlay.remove(self._overlay_container)
            self._overlay_container = None
            self._submenu_card = None
            self._is_showing = False
            self.page.update()

    def _hide_submenu(self):
        """Hides only the secondary flyout submenu if open."""
        if self._overlay_container and self._submenu_card:
            stack: ft.Stack = self._overlay_container.content
            if self._submenu_card in stack.controls:
                stack.controls.remove(self._submenu_card)
                self._submenu_card = None
                self.page.update()

    def show_file_menu(
        self,
        x: float,
        y: float,
        file_path: str,
        on_quick_convert: Callable[[str, str], None],
        on_reveal: Callable[[str], None],
        on_copy_path: Callable[[str], None],
        on_rename: Callable[[str], None],
        on_delete: Callable[[str], None],
        on_batch_convert: Optional[Callable[[str], None]] = None,
    ):
        """Opens right-click menu for a file node with smart 2-tier Quick Convert and Archive Batch Convert."""
        self.hide()

        name = os.path.basename(file_path)
        ext = os.path.splitext(name)[1].lower()
        is_markdown = ext in (".md", ".markdown")
        is_archive = ext in (".zip", ".rar", ".7z", ".tar.gz", ".tgz", ".tbz2", ".tar")

        items: List[ft.Control] = []

        # 0. Archive Batch Convert (when right-clicking .zip, .rar, .7z, .tar.gz)
        if is_archive and on_batch_convert:
            items.append(
                ContextMenuItem(
                    title=t("explorer.batch_convert"),
                    icon=ft.Icons.DYNAMIC_FEED_ROUNDED,
                    icon_color=ft.Colors.AMBER_500,
                    on_click=lambda: self._wrap_action(on_batch_convert, file_path),
                )
            )
            items.append(ContextMenuDivider())

        # 1. Smart Quick Convert Section
        if is_markdown:
            # Markdown file -> Hoverable Flyout Submenu for all 8 supported formats
            items.append(
                ContextMenuItem(
                    title=t("explorer.quick_convert_menu"),
                    icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                    icon_color=ft.Colors.AMBER_500,
                    trailing_icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,
                    on_click=lambda: self._show_convert_submenu(file_path, on_quick_convert),
                    on_hover=lambda is_hover: self._show_convert_submenu(file_path, on_quick_convert) if is_hover else None,
                )
            )
            items.append(ContextMenuDivider())
        elif ext in (
            ".docx", ".doc", ".pdf", ".pptx", ".ppt", ".xlsx", ".xls", ".csv",
            ".html", ".htm", ".json", ".yaml", ".yml", ".txt",
        ):
            # Non-Markdown file -> Single direct 1-click Convert to Markdown (.md)
            items.append(
                ContextMenuItem(
                    title=t("explorer.quick_convert_to_md"),
                    icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                    icon_color=ft.Colors.AMBER_500,
                    on_click=lambda: self._wrap_action(on_quick_convert, file_path, ".md"),
                    on_hover=lambda is_hover: self._hide_submenu() if is_hover else None,
                )
            )
            items.append(ContextMenuDivider())


        # 2. File Operations
        items.append(
            ContextMenuItem(
                title=t("explorer.reveal_explorer"),
                icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                on_click=lambda: self._wrap_action(on_reveal, file_path),
                on_hover=lambda is_hover: self._hide_submenu() if is_hover else None,
            )
        )
        items.append(
            ContextMenuItem(
                title=t("explorer.copy_path"),
                icon=ft.Icons.CONTENT_COPY_ROUNDED,
                on_click=lambda: self._wrap_action(on_copy_path, file_path),
                on_hover=lambda is_hover: self._hide_submenu() if is_hover else None,
            )
        )
        items.append(ContextMenuDivider())

        # 3. Rename & Safe Delete
        items.append(
            ContextMenuItem(
                title=t("explorer.rename"),
                icon=ft.Icons.EDIT_OUTLINED,
                on_click=lambda: self._wrap_action(on_rename, file_path),
                on_hover=lambda is_hover: self._hide_submenu() if is_hover else None,
            )
        )
        items.append(
            ContextMenuItem(
                title=t("explorer.delete"),
                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                color=ft.Colors.RED_400,
                icon_color=ft.Colors.RED_400,
                on_click=lambda: self._wrap_action(on_delete, file_path),
                on_hover=lambda is_hover: self._hide_submenu() if is_hover else None,
            )
        )

        self._render_menu(x, y, items)

    def _show_convert_submenu(
        self,
        file_path: str,
        on_quick_convert: Callable[[str, str], None],
    ):
        """Displays the secondary flyout submenu with all 8 supported export formats."""
        if not self._overlay_container or not self._is_showing:
            return

        # Complete suite of 8 export formats supported by DocumentConvertTool
        md_targets = [
            (".docx", "Word (.docx)", ft.Icons.EDIT_DOCUMENT, ft.Colors.LIGHT_BLUE_400),
            (".pdf", "PDF (.pdf)", ft.Icons.PICTURE_AS_PDF_ROUNDED, ft.Colors.RED_400),
            (".pptx", "PowerPoint (.pptx)", ft.Icons.SLIDESHOW_ROUNDED, ft.Colors.DEEP_ORANGE_400),
            (".html", "HTML (.html)", ft.Icons.CODE_ROUNDED, ft.Colors.PURPLE_400),
            (".xlsx", "Excel (.xlsx)", ft.Icons.TABLE_CHART_ROUNDED, ft.Colors.GREEN_400),
            (".csv", "CSV (.csv)", ft.Icons.TABLE_CHART_ROUNDED, ft.Colors.TEAL_400),
            (".json", "JSON (.json)", ft.Icons.DATA_OBJECT_ROUNDED, ft.Colors.AMBER_400),
            (".yaml", "YAML (.yaml)", ft.Icons.DATA_OBJECT_ROUNDED, ft.Colors.ORANGE_400),
        ]

        sub_items: List[ft.Control] = []
        for out_ext, label, icon_name, icon_col in md_targets:
            sub_items.append(
                ContextMenuItem(
                    title=label,
                    icon=icon_name,
                    icon_color=icon_col,
                    on_click=lambda oe=out_ext: self._wrap_action(on_quick_convert, file_path, oe),
                )
            )

        submenu_width = 185
        submenu_height = (len(sub_items) * 32) + 16

        win_w = getattr(self.page.window, "width", 1000) or 1000
        win_h = getattr(self.page.window, "height", 700) or 700

        # Place submenu to the right of main menu, or flip to left if edge reached
        sub_pos_x = self._menu_x + self._menu_width + 4
        if sub_pos_x + submenu_width > win_w - 15:
            sub_pos_x = max(10, self._menu_x - submenu_width - 4)

        sub_pos_y = min(self._menu_y, win_h - submenu_height - 25)
        sub_pos_y = max(10, sub_pos_y)

        self._submenu_card = ft.Container(
            content=ft.Column(
                sub_items,
                spacing=2,
                tight=True,
            ),
            width=submenu_width,
            padding=ft.Padding(5, 5, 5, 5),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border(
                top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            ),
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=12,
                color=ft.Colors.with_opacity(0.35, ft.Colors.BLACK),
                offset=ft.Offset(2, 4),
            ),
            left=sub_pos_x,
            top=sub_pos_y,
        )

        stack: ft.Stack = self._overlay_container.content
        if len(stack.controls) > 2:
            stack.controls[2] = self._submenu_card
        else:
            stack.controls.append(self._submenu_card)
        self.page.update()

    def show_folder_menu(
        self,
        x: float,
        y: float,
        folder_path: str,
        on_new_file: Callable[[str], None],
        on_new_folder: Callable[[str], None],
        on_reveal: Callable[[str], None],
        on_copy_path: Callable[[str], None],
        on_batch_convert: Optional[Callable[[str], None]] = None,
    ):
        """Opens right-click menu for a directory node."""
        self.hide()

        items: List[ft.Control] = []

        if on_batch_convert:
            items.append(
                ContextMenuItem(
                    title=t("explorer.batch_convert"),
                    icon=ft.Icons.DYNAMIC_FEED_ROUNDED,
                    icon_color=ft.Colors.AMBER_500,
                    on_click=lambda: self._wrap_action(on_batch_convert, folder_path),
                )
            )
            items.append(ContextMenuDivider())

        items.extend([
            ContextMenuItem(
                title=t("explorer.new_file"),
                icon=ft.Icons.NOTE_ADD_ROUNDED,
                icon_color=ft.Colors.PRIMARY,
                on_click=lambda: self._wrap_action(on_new_file, folder_path),
            ),
            ContextMenuItem(
                title=t("explorer.new_folder"),
                icon=ft.Icons.CREATE_NEW_FOLDER_ROUNDED,
                icon_color=ft.Colors.PRIMARY,
                on_click=lambda: self._wrap_action(on_new_folder, folder_path),
            ),
            ContextMenuDivider(),
            ContextMenuItem(
                title=t("explorer.reveal_explorer"),
                icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                on_click=lambda: self._wrap_action(on_reveal, folder_path),
            ),
            ContextMenuItem(
                title=t("explorer.copy_path"),
                icon=ft.Icons.CONTENT_COPY_ROUNDED,
                on_click=lambda: self._wrap_action(on_copy_path, folder_path),
            ),
        ])

        self._render_menu(x, y, items)


    def show_header_menu(
        self,
        x: float,
        y: float,
        on_open_folder: Optional[Callable] = None,
        on_collapse_all: Optional[Callable] = None,
        on_refresh: Optional[Callable] = None,
    ):
        """Opens sleek floating dropdown menu for Explorer Header when compact."""
        self.hide()

        items: List[ft.Control] = []
        if on_collapse_all:
            items.append(
                ContextMenuItem(
                    title=t("explorer.collapse_all"),
                    icon=ft.Icons.UNFOLD_LESS_ROUNDED,
                    icon_color=ft.Colors.OUTLINE,
                    on_click=lambda: self._wrap_action(on_collapse_all),
                )
            )
        if on_open_folder:
            items.append(
                ContextMenuItem(
                    title=t("explorer.open_folder"),
                    icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                    icon_color=ft.Colors.PRIMARY,
                    on_click=lambda: self._wrap_action(on_open_folder),
                )
            )
        if on_refresh:
            items.append(
                ContextMenuItem(
                    title=t("explorer.refresh"),
                    icon=ft.Icons.REFRESH_ROUNDED,
                    icon_color=ft.Colors.OUTLINE,
                    on_click=lambda: self._wrap_action(on_refresh),
                )
            )

        self._render_menu(x, y, items)

    def show_tab_menu(
        self,
        x: float,
        y: float,
        tab_id: str,
        in_path: str,
        can_close_others: bool,
        can_close_to_right: bool,
        on_close: Callable[[str], None],
        on_close_others: Optional[Callable[[str], None]] = None,
        on_close_to_right: Optional[Callable[[str], None]] = None,
        on_close_all: Optional[Callable[[], None]] = None,
        on_copy_path: Optional[Callable[[str], None]] = None,
        on_reveal: Optional[Callable[[str], None]] = None,
    ):
        """Opens right-click context menu for workspace document tab."""
        self.hide()
        items: List[ft.Control] = [
            ContextMenuItem(
                title=t("tab.close"),
                icon=ft.Icons.CLOSE,
                on_click=lambda: self._wrap_action(on_close, tab_id),
            ),
        ]
        if can_close_others and on_close_others:
            items.append(
                ContextMenuItem(
                    title=t("tab.close_others"),
                    icon=ft.Icons.CLOSE_FULLSCREEN_ROUNDED,
                    on_click=lambda: self._wrap_action(on_close_others, tab_id),
                )
            )
        if can_close_to_right and on_close_to_right:
            items.append(
                ContextMenuItem(
                    title=t("tab.close_to_right"),
                    icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                    on_click=lambda: self._wrap_action(on_close_to_right, tab_id),
                )
            )

        if on_close_all:
            items.append(
                ContextMenuItem(
                    title=t("tab.close_all"),
                    icon=ft.Icons.CLEAR_ALL_ROUNDED,
                    on_click=lambda: self._wrap_action(on_close_all),
                )
            )

        if in_path and os.path.exists(in_path):
            items.append(ContextMenuDivider())
            if on_copy_path:
                items.append(
                    ContextMenuItem(
                        title=t("explorer.copy_path"),
                        icon=ft.Icons.CONTENT_COPY_ROUNDED,
                        on_click=lambda: self._wrap_action(on_copy_path, in_path),
                    )
                )
            if on_reveal:
                items.append(
                    ContextMenuItem(
                        title=t("explorer.reveal_explorer"),
                        icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                        on_click=lambda: self._wrap_action(on_reveal, in_path),
                    )
                )

        self._render_menu(x, y, items)


    def _wrap_action(self, callback: Callable, *args):
        self.hide()
        if callback:
            callback(*args)

    def _render_menu(self, x: float, y: float, items: List[ft.Control]):
        self._menu_width = 230
        item_count = len(items)
        menu_height = (item_count * 32) + 16

        # Boundary clamping to keep within window dimensions
        win_w = getattr(self.page.window, "width", 1000) or 1000
        win_h = getattr(self.page.window, "height", 700) or 700

        pos_x = min(x, win_w - self._menu_width - 15)
        pos_y = min(y, win_h - menu_height - 25)
        pos_x = max(10, pos_x)
        pos_y = max(10, pos_y)

        self._menu_x = pos_x
        self._menu_y = pos_y

        menu_card = ft.Container(
            content=ft.Column(
                items,
                spacing=2,
                tight=True,
            ),
            width=self._menu_width,
            padding=ft.Padding(5, 5, 5, 5),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border(
                top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            ),
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=12,
                color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            left=pos_x,
            top=pos_y,
        )

        # Backdrop overlay to capture click outside and dismiss
        self._overlay_container = ft.Container(
            content=ft.Stack(
                [
                    ft.GestureDetector(
                        on_tap=self.hide,
                        on_secondary_tap=self.hide,
                        expand=True,
                    ),
                    menu_card,
                ],
                expand=True,
            ),
            expand=True,
            left=0,
            top=0,
            right=0,
            bottom=0,
        )

        self.page.overlay.append(self._overlay_container)
        self._is_showing = True
        self.page.update()
