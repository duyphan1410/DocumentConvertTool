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
        trailing_color: Optional[str] = None,
        is_selected: bool = False,
    ):
        self._action_callback = on_click
        self._hover_callback = on_hover
        self._is_selected = is_selected

        trailing_ctrl = (
            ft.Icon(trailing_icon, size=14, color=trailing_color or (ft.Colors.PRIMARY if is_selected else ft.Colors.OUTLINE))
            if trailing_icon
            else ft.Container()
        )

        item_color = color or (ft.Colors.PRIMARY if is_selected else ft.Colors.ON_SURFACE)
        item_icon_color = icon_color or (ft.Colors.PRIMARY if is_selected else ft.Colors.ON_SURFACE_VARIANT)

        row_content = ft.Row(
            [
                ft.Icon(icon, size=15, color=item_icon_color),
                ft.Text(
                    title,
                    size=12,
                    weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.W_500,
                    color=item_color,
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
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_selected else ft.Colors.TRANSPARENT,
            ink=True,
            on_hover=self._handle_hover,
        )

    def _handle_click(self, e=None):
        if self._action_callback:
            self._action_callback()

    def _handle_enter(self, e=None):
        self.bgcolor = ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY)
        try:
            if self.page:
                self.update()
        except Exception:
            pass
        if self._hover_callback:
            self._hover_callback(True)

    def _handle_exit(self, e=None):
        self.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if getattr(self, "_is_selected", False) else ft.Colors.TRANSPARENT
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
        self.on_dismiss: Optional[Callable[[], None]] = None

    def hide(self, e=None):
        """Dismisses the context menu and any active submenu from the page overlay."""
        if self._overlay_container and self._overlay_container in self.page.overlay:
            self.page.overlay.remove(self._overlay_container)
            self._overlay_container = None
            self._submenu_card = None
            self._is_showing = False
            self.page.update()
            if hasattr(self, "on_dismiss") and self.on_dismiss:
                try:
                    self.on_dismiss()
                except Exception:
                    pass

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

    def show_image_menu(
        self,
        x: float,
        y: float,
        image_info,
        on_size_preset: Callable[[str], None],
        on_align_preset: Callable[[str], None],
        on_custom_size: Callable[[], None],
        on_replace_image: Callable[[], None],
        on_reset_image: Callable[[], None],
    ):
        """Opens contextual popup menu for an image with 2-tier submenus matching Explorer styling."""
        self.hide()

        src_name = os.path.basename(getattr(image_info, "src", "")) or getattr(image_info, "alt", "") or "Image"
        if len(src_name) > 16:
            src_name = src_name[:14] + "…"

        items: List[ft.Control] = []

        # 0. Header with Image Name
        items.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.IMAGE_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                        ft.Text(src_name, size=11, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY, no_wrap=True),
                    ],
                    spacing=6,
                ),
                padding=ft.Padding(left=10, top=4, right=10, bottom=4),
            )
        )
        items.append(ContextMenuDivider())

        # 1. Size Preset Submenu (25%, 50%, 75%, 100%, Custom...)
        items.append(
            ContextMenuItem(
                title=t("image_dialog.title") if t("image_dialog.title") != "image_dialog.title" else "Image Size",
                icon=ft.Icons.PHOTO_SIZE_SELECT_LARGE_ROUNDED,
                icon_color=ft.Colors.TEAL_400,
                trailing_icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,
                on_click=lambda: self._show_image_size_submenu(image_info, on_size_preset, on_custom_size),
                on_hover=lambda is_hover: self._show_image_size_submenu(image_info, on_size_preset, on_custom_size) if is_hover else None,
            )
        )

        # 2. Alignment Submenu (Left, Center, Right)
        items.append(
            ContextMenuItem(
                title=t("image_dialog.align_label") if t("image_dialog.align_label") != "image_dialog.align_label" else "Alignment",
                icon=ft.Icons.FORMAT_ALIGN_CENTER_ROUNDED,
                icon_color=ft.Colors.CYAN_400,
                trailing_icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,
                on_click=lambda: self._show_image_align_submenu(image_info, on_align_preset),
                on_hover=lambda is_hover: self._show_image_align_submenu(image_info, on_align_preset) if is_hover else None,
            )
        )

        items.append(ContextMenuDivider())

        # 3. Replace Image
        items.append(
            ContextMenuItem(
                title=t("ribbon.img_replace") if t("ribbon.img_replace") != "ribbon.img_replace" else "Replace Image...",
                icon=ft.Icons.IMAGE_SEARCH_ROUNDED,
                icon_color=ft.Colors.BLUE_400,
                on_click=lambda: self._wrap_action(on_replace_image),
                on_hover=lambda is_hover: self._hide_submenu() if is_hover else None,
            )
        )

        # 4. Custom WxH Dialog
        items.append(
            ContextMenuItem(
                title=t("ribbon.img_custom_size") if t("ribbon.img_custom_size") != "ribbon.img_custom_size" else "Custom Size & Dimensions...",
                icon=ft.Icons.ASPECT_RATIO_ROUNDED,
                icon_color=ft.Colors.AMBER_400,
                on_click=lambda: self._wrap_action(on_custom_size),
                on_hover=lambda is_hover: self._hide_submenu() if is_hover else None,
            )
        )

        # 5. Reset Size
        items.append(
            ContextMenuItem(
                title=t("ribbon.img_reset") if t("ribbon.img_reset") != "ribbon.img_reset" else "Reset to Original",
                icon=ft.Icons.RESTORE_ROUNDED,
                icon_color=ft.Colors.ORANGE_400,
                on_click=lambda: self._wrap_action(on_reset_image),
                on_hover=lambda is_hover: self._hide_submenu() if is_hover else None,
            )
        )

        self._render_menu(x, y, items)

    def _show_image_size_submenu(self, image_info, on_size_preset: Callable[[str], None], on_custom_size: Callable[[], None]):
        """Displays flyout submenu for image size presets with active selection highlight."""
        self._hide_submenu()
        if not self._overlay_container:
            return

        curr_w = (getattr(image_info, "width", "") or "").strip()
        has_h = bool(getattr(image_info, "height", None))

        is_p25 = (curr_w == "25%")
        is_p50 = (curr_w == "50%")
        is_p75 = (curr_w == "75%")
        is_p100 = (curr_w in ("100%", "") and not has_h)
        is_custom = (curr_w not in ("25%", "50%", "75%", "100%", "") or has_h)

        sub_items: List[ft.Control] = [
            ContextMenuItem(
                title="25% (Quarter Width)",
                icon=ft.Icons.CROP_PORTRAIT_ROUNDED,
                trailing_icon=ft.Icons.CHECK_ROUNDED if is_p25 else None,
                is_selected=is_p25,
                on_click=lambda: self._wrap_action(on_size_preset, "25%"),
            ),
            ContextMenuItem(
                title="50% (Half Width)",
                icon=ft.Icons.CROP_SQUARE_ROUNDED,
                trailing_icon=ft.Icons.CHECK_ROUNDED if is_p50 else None,
                is_selected=is_p50,
                on_click=lambda: self._wrap_action(on_size_preset, "50%"),
            ),
            ContextMenuItem(
                title="75% (Three Quarters)",
                icon=ft.Icons.CROP_LANDSCAPE_ROUNDED,
                trailing_icon=ft.Icons.CHECK_ROUNDED if is_p75 else None,
                is_selected=is_p75,
                on_click=lambda: self._wrap_action(on_size_preset, "75%"),
            ),
            ContextMenuItem(
                title="100% (Original / Full)",
                icon=ft.Icons.FULLSCREEN_ROUNDED,
                trailing_icon=ft.Icons.CHECK_ROUNDED if is_p100 else None,
                is_selected=is_p100,
                on_click=lambda: self._wrap_action(on_size_preset, "100%"),
            ),
            ContextMenuDivider(),
            ContextMenuItem(
                title="Custom Dimensions...",
                icon=ft.Icons.SETTINGS_OVERSCAN_ROUNDED,
                icon_color=ft.Colors.AMBER_400,
                trailing_icon=ft.Icons.CHECK_ROUNDED if is_custom else None,
                is_selected=is_custom,
                on_click=lambda: self._wrap_action(on_custom_size),
            ),
        ]

        sub_w = 200
        sub_h = (len(sub_items) * 32) + 16

        win_w = getattr(self.page.window, "width", 1000) or 1000
        win_h = getattr(self.page.window, "height", 700) or 700

        sub_x = self._menu_x + self._menu_width + 4
        if sub_x + sub_w > win_w - 15:
            sub_x = self._menu_x - sub_w - 4

        sub_y = min(self._menu_y + 35, win_h - sub_h - 20)
        sub_y = max(10, sub_y)

        self._submenu_card = ft.Container(
            content=ft.Column(sub_items, spacing=2, tight=True),
            width=sub_w,
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
            left=sub_x,
            top=sub_y,
        )

        stack: ft.Stack = self._overlay_container.content
        stack.controls.append(self._submenu_card)
        self.page.update()

    def _show_image_align_submenu(self, image_info, on_align_preset: Callable[[str], None]):
        """Displays flyout submenu for image alignment presets with active selection highlight."""
        self._hide_submenu()
        if not self._overlay_container:
            return

        curr_align = (getattr(image_info, "align", "") or "").lower().strip()
        is_left = (curr_align in ("left", ""))
        is_center = (curr_align == "center")
        is_right = (curr_align == "right")

        sub_items: List[ft.Control] = [
            ContextMenuItem(
                title=t("image_dialog.align_left") if t("image_dialog.align_left") != "image_dialog.align_left" else "Align Left",
                icon=ft.Icons.FORMAT_ALIGN_LEFT_ROUNDED,
                trailing_icon=ft.Icons.CHECK_ROUNDED if is_left else None,
                is_selected=is_left,
                on_click=lambda: self._wrap_action(on_align_preset, "left"),
            ),
            ContextMenuItem(
                title=t("image_dialog.align_center") if t("image_dialog.align_center") != "image_dialog.align_center" else "Align Center",
                icon=ft.Icons.FORMAT_ALIGN_CENTER_ROUNDED,
                trailing_icon=ft.Icons.CHECK_ROUNDED if is_center else None,
                is_selected=is_center,
                on_click=lambda: self._wrap_action(on_align_preset, "center"),
            ),
            ContextMenuItem(
                title=t("image_dialog.align_right") if t("image_dialog.align_right") != "image_dialog.align_right" else "Align Right",
                icon=ft.Icons.FORMAT_ALIGN_RIGHT_ROUNDED,
                trailing_icon=ft.Icons.CHECK_ROUNDED if is_right else None,
                is_selected=is_right,
                on_click=lambda: self._wrap_action(on_align_preset, "right"),
            ),
        ]

        sub_w = 180
        sub_h = (len(sub_items) * 32) + 16

        win_w = getattr(self.page.window, "width", 1000) or 1000
        win_h = getattr(self.page.window, "height", 700) or 700

        sub_x = self._menu_x + self._menu_width + 4
        if sub_x + sub_w > win_w - 15:
            sub_x = self._menu_x - sub_w - 4

        sub_y = min(self._menu_y + 70, win_h - sub_h - 20)
        sub_y = max(10, sub_y)

        self._submenu_card = ft.Container(
            content=ft.Column(sub_items, spacing=2, tight=True),
            width=sub_w,
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
            left=sub_x,
            top=sub_y,
        )

        stack: ft.Stack = self._overlay_container.content
        stack.controls.append(self._submenu_card)
        self.page.update()

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
