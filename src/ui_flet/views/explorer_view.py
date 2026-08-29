"""
File Explorer Sidebar View for DocConvert Workspace.
Provides a folder tree view with on-demand lazy loading, async directory scanning,
contextual file extension icons, and smart IDE-style right-click context menu.
"""
from __future__ import annotations

import os
import asyncio
from typing import Callable, Optional
import flet as ft

from src.i18n import t
from src.utils.file_ops import safe_delete_to_recycle_bin, reveal_in_windows_explorer
from src.utils.clipboard import set_clipboard_text
from src.ui_flet.components.context_menu import ExplorerContextMenu
from src.ui_flet.components.file_modals import (
    show_rename_dialog,
    show_safe_delete_dialog,
    show_new_entry_dialog,
)

# Ignored directory names to maintain high performance
IGNORED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    ".pytest_cache",
    "build",
    "dist",
}

# Icon and color mapping for document extensions
EXT_CONFIG = {
    ".md": (ft.Icons.ARTICLE_ROUNDED, ft.Colors.BLUE_400),
    ".markdown": (ft.Icons.ARTICLE_ROUNDED, ft.Colors.BLUE_400),
    ".pdf": (ft.Icons.PICTURE_AS_PDF_ROUNDED, ft.Colors.RED_400),
    ".docx": (ft.Icons.EDIT_DOCUMENT, ft.Colors.LIGHT_BLUE_400),
    ".doc": (ft.Icons.EDIT_DOCUMENT, ft.Colors.LIGHT_BLUE_400),
    ".pptx": (ft.Icons.SLIDESHOW_ROUNDED, ft.Colors.DEEP_ORANGE_400),
    ".ppt": (ft.Icons.SLIDESHOW_ROUNDED, ft.Colors.DEEP_ORANGE_400),
    ".xlsx": (ft.Icons.TABLE_CHART_ROUNDED, ft.Colors.GREEN_400),
    ".xls": (ft.Icons.TABLE_CHART_ROUNDED, ft.Colors.GREEN_400),
    ".csv": (ft.Icons.TABLE_CHART_ROUNDED, ft.Colors.TEAL_400),
    ".json": (ft.Icons.DATA_OBJECT_ROUNDED, ft.Colors.AMBER_400),
    ".yaml": (ft.Icons.DATA_OBJECT_ROUNDED, ft.Colors.ORANGE_400),
    ".yml": (ft.Icons.DATA_OBJECT_ROUNDED, ft.Colors.ORANGE_400),
    ".html": (ft.Icons.CODE_ROUNDED, ft.Colors.PURPLE_400),
    ".htm": (ft.Icons.CODE_ROUNDED, ft.Colors.PURPLE_400),
    ".txt": (ft.Icons.DESCRIPTION_OUTLINED, ft.Colors.OUTLINE),
    ".py": (ft.Icons.CODE_ROUNDED, ft.Colors.YELLOW_600),
    ".js": (ft.Icons.CODE_ROUNDED, ft.Colors.AMBER_300),
    ".css": (ft.Icons.STYLE_ROUNDED, ft.Colors.CYAN_400),
}


def _extract_tap_position(e: ft.TapEvent) -> tuple[float, float]:
    """Safely extracts global (x, y) coordinates from Flet TapEvent across all versions."""
    try:
        if hasattr(e, "global_position") and e.global_position:
            return float(e.global_position.x), float(e.global_position.y)
        if hasattr(e, "local_position") and e.local_position:
            return float(e.local_position.x), float(e.local_position.y)
        if hasattr(e, "global_x") and hasattr(e, "global_y"):
            return float(e.global_x), float(e.global_y)
        if hasattr(e, "data") and e.data:
            import json
            d = json.loads(e.data)
            gx = d.get("gx", d.get("g", {}).get("x", d.get("lx", 150)))
            gy = d.get("gy", d.get("g", {}).get("y", d.get("ly", 150)))
            return float(gx), float(gy)
    except Exception:
        pass
    return 150.0, 150.0


class FileTreeItem(ft.Container):
    """An individual file entry in the Explorer tree with Draggable support."""

    def __init__(
        self,
        file_path: str,
        name: str,
        depth: int,
        on_click: Optional[Callable[[str], None]] = None,
        on_secondary_tap_down: Optional[Callable[[str, float, float], None]] = None,
        is_active: bool = False,
        **kwargs,
    ):
        self.file_path = file_path
        self.file_name = name
        self.depth = depth
        self._on_click_callback = on_click
        self._on_secondary_callback = on_secondary_tap_down
        self.is_active = is_active

        ext = os.path.splitext(name)[1].lower()
        icon, color = EXT_CONFIG.get(ext, (ft.Icons.INSERT_DRIVE_FILE_OUTLINED, ft.Colors.OUTLINE))

        self.label = ft.Text(
            name,
            size=12,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL,
            color=ft.Colors.PRIMARY if is_active else None,
            expand=True,
        )

        row_content = ft.Row(
            [
                ft.Icon(icon, size=15, color=color),
                self.label,
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.item_box = ft.Container(
            content=ft.GestureDetector(
                content=row_content,
                on_tap=self._handle_click,
                on_enter=self._handle_enter,
                on_exit=self._handle_exit,
                on_secondary_tap_down=self._handle_secondary_tap,
            ),
            padding=ft.Padding(left=12 + (depth * 14), top=3, right=6, bottom=3),
            border_radius=4,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY) if is_active else ft.Colors.TRANSPARENT,
            ink=True,
        )

        feedback_chip = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=14, color=color),
                    ft.Text(name, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
                ],
                spacing=4,
                tight=True,
            ),
            padding=ft.Padding(8, 4, 8, 4),
            border_radius=6,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=6, color=ft.Colors.BLACK38),
        )

        self.draggable = ft.Draggable(
            group="doc_explorer",
            data=file_path,
            content=self.item_box,
            content_feedback=feedback_chip,
        )

        super().__init__(
            content=self.draggable,
            padding=0,
            **kwargs,
        )

    def _handle_enter(self, e=None):
        if not self.is_active:
            self.item_box.bgcolor = ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)
            try:
                if self.page:
                    self.item_box.update()
            except Exception:
                pass

    def _handle_exit(self, e=None):
        if not self.is_active:
            self.item_box.bgcolor = ft.Colors.TRANSPARENT
            try:
                if self.page:
                    self.item_box.update()
            except Exception:
                pass

    def set_active(self, is_active: bool):
        self.is_active = is_active
        self.label.weight = ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL
        self.label.color = ft.Colors.PRIMARY if is_active else None
        self.item_box.bgcolor = (
            ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY)
            if is_active
            else ft.Colors.TRANSPARENT
        )
        try:
            if self.page:
                self.item_box.update()
        except Exception:
            pass

    def _handle_click(self, e=None):
        if self._on_click_callback:
            self._on_click_callback(self.file_path)

    def _handle_secondary_tap(self, e: ft.TapEvent):
        if self._on_secondary_callback:
            gx, gy = _extract_tap_position(e)
            self._on_secondary_callback(self.file_path, gx, gy)


class DirectoryTreeItem(ft.Column):
    """A directory node supporting lazy-loading, Draggable, and DragTarget move operations."""

    def __init__(
        self,
        dir_path: str,
        name: str,
        depth: int,
        on_file_click: Optional[Callable[[str], None]] = None,
        on_file_secondary: Optional[Callable[[str, float, float], None]] = None,
        on_folder_secondary: Optional[Callable[[str, float, float], None]] = None,
        on_move_entry: Optional[Callable[[str, str], None]] = None,
        active_path: str = "",
        **kwargs,
    ):
        self.dir_path = dir_path
        self.dir_name = name
        self.depth = depth
        self.on_file_click = on_file_click
        self.on_file_secondary = on_file_secondary
        self.on_folder_secondary = on_folder_secondary
        self.on_move_entry = on_move_entry
        self.active_path = active_path
        self.is_expanded = False
        self._is_loaded = False

        self.icon_arrow = ft.Icon(
            ft.Icons.KEYBOARD_ARROW_RIGHT_ROUNDED,
            size=14,
            color=ft.Colors.OUTLINE,
        )
        self.icon_folder = ft.Icon(
            ft.Icons.FOLDER_ROUNDED,
            size=15,
            color=ft.Colors.AMBER_500,
        )
        self.label = ft.Text(
            name,
            size=12,
            weight=ft.FontWeight.W_500,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
        )

        header_row = ft.Row(
            [
                self.icon_arrow,
                self.icon_folder,
                self.label,
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.header_box = ft.Container(
            content=ft.GestureDetector(
                content=header_row,
                on_tap=self._toggle_expand,
                on_enter=self._handle_header_enter,
                on_exit=self._handle_header_exit,
                on_secondary_tap_down=self._handle_folder_secondary_tap,
            ),
            padding=ft.Padding(left=4 + (depth * 14), top=3, right=6, bottom=3),
            border_radius=4,
            ink=True,
        )

        feedback_chip = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.FOLDER_ROUNDED, size=14, color=ft.Colors.AMBER_500),
                    ft.Text(name, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
                ],
                spacing=4,
                tight=True,
            ),
            padding=ft.Padding(8, 4, 8, 4),
            border_radius=6,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=6, color=ft.Colors.BLACK38),
        )

        draggable_header = ft.Draggable(
            group="doc_explorer",
            data=dir_path,
            content=self.header_box,
            content_feedback=feedback_chip,
        )

        self.header = ft.DragTarget(
            group="doc_explorer",
            content=draggable_header,
            on_accept=self._handle_drag_accept,
            on_will_accept=self._handle_will_accept,
            on_leave=self._handle_drag_leave,
        )

        self.children_column = ft.Column(spacing=1, visible=False)

        super().__init__(
            controls=[self.header, self.children_column],
            spacing=0,
            **kwargs,
        )

    def _handle_will_accept(self, e):
        self.header_box.bgcolor = ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY)
        try:
            if self.page:
                self.header_box.update()
        except Exception:
            pass

    def _handle_drag_leave(self, e):
        self.header_box.bgcolor = ft.Colors.TRANSPARENT
        try:
            if self.page:
                self.header_box.update()
        except Exception:
            pass

    def _handle_drag_accept(self, e):
        self.header_box.bgcolor = ft.Colors.TRANSPARENT
        try:
            if self.page:
                self.header_box.update()
        except Exception:
            pass

        src_path = None
        src_ctrl_id = getattr(e, "src_id", None)
        if src_ctrl_id and self.page:
            try:
                src_ctrl = self.page.get_control(src_ctrl_id)
                if src_ctrl and hasattr(src_ctrl, "data") and src_ctrl.data:
                    src_path = str(src_ctrl.data)
            except Exception:
                pass

        if not src_path:
            src_path = getattr(e, "data", None)

        if src_path and self.on_move_entry:
            self.on_move_entry(src_path, self.dir_path)

    def _handle_header_enter(self, e=None):
        self.header_box.bgcolor = ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)
        try:
            if self.page:
                self.header_box.update()
        except Exception:
            pass

    def _handle_header_exit(self, e=None):
        self.header_box.bgcolor = ft.Colors.TRANSPARENT
        try:
            if self.page:
                self.header_box.update()
        except Exception:
            pass

    def _handle_folder_secondary_tap(self, e: ft.TapEvent):
        if self.on_folder_secondary:
            gx, gy = _extract_tap_position(e)
            self.on_folder_secondary(self.dir_path, gx, gy)

    def _toggle_expand(self, e=None):
        self.is_expanded = not self.is_expanded
        self.icon_arrow.name = (
            ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
            if self.is_expanded
            else ft.Icons.KEYBOARD_ARROW_RIGHT_ROUNDED
        )
        self.icon_folder.name = (
            ft.Icons.FOLDER_OPEN_ROUNDED
            if self.is_expanded
            else ft.Icons.FOLDER_ROUNDED
        )

        if self.is_expanded:
            if not self._is_loaded:
                self._load_children()
            self.children_column.visible = True
        else:
            self.children_column.visible = False

        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def _load_children(self):
        self._is_loaded = True
        self.children_column.controls.clear()
        try:
            entries = sorted(os.scandir(self.dir_path), key=lambda e: (not e.is_dir(), e.name.lower()))
            for entry in entries:
                if entry.name.startswith(".") and entry.name not in (".env",):
                    continue
                if entry.is_dir():
                    if entry.name in IGNORED_DIRS:
                        continue
                    self.children_column.controls.append(
                        DirectoryTreeItem(
                            dir_path=entry.path,
                            name=entry.name,
                            depth=self.depth + 1,
                            on_file_click=self.on_file_click,
                            on_file_secondary=self.on_file_secondary,
                            on_folder_secondary=self.on_folder_secondary,
                            on_move_entry=self.on_move_entry,
                            active_path=self.active_path,
                        )
                    )
                elif entry.is_file():
                    is_act = (
                        os.path.normpath(entry.path) == os.path.normpath(self.active_path)
                        if self.active_path
                        else False
                    )
                    self.children_column.controls.append(
                        FileTreeItem(
                            file_path=entry.path,
                            name=entry.name,
                            depth=self.depth + 1,
                            on_click=self.on_file_click,
                            on_secondary_tap_down=self.on_file_secondary,
                            is_active=is_act,
                        )
                    )
        except Exception as ex:
            print(f"[ExplorerView] Failed to scan {self.dir_path}: {ex}")

    def collapse_all(self):
        """Recursively collapses this directory and any expanded child directories."""
        self.is_expanded = False
        self.icon_arrow.name = ft.Icons.KEYBOARD_ARROW_RIGHT_ROUNDED
        self.icon_folder.name = ft.Icons.FOLDER_ROUNDED
        self.children_column.visible = False
        for ctrl in self.children_column.controls:
            if isinstance(ctrl, DirectoryTreeItem):
                ctrl.collapse_all()
        try:
            if self.page:
                self.update()
        except Exception:
            pass



class ExplorerView(ft.Container):
    """
    Explorer Sidebar panel displaying the current Workspace directory tree.
    Supports on-demand lazy loading, search filter, and floating context menu operations.
    """

    def __init__(
        self,
        on_open_folder: Optional[Callable] = None,
        on_file_click: Optional[Callable[[str], None]] = None,
        on_rename: Optional[Callable[[str, str], None]] = None,
        on_delete: Optional[Callable[[str], None]] = None,
        on_quick_convert: Optional[Callable[[str, str], None]] = None,
        on_new_file: Optional[Callable[[str], None]] = None,
        on_new_folder: Optional[Callable[[str], None]] = None,
        on_status_message: Optional[Callable[[str, Optional[str]], None]] = None,
        on_batch_convert: Optional[Callable[[str], None]] = None,
        get_is_dirty: Optional[Callable[[], bool]] = None,
        get_active_file: Optional[Callable[[], str]] = None,
        workspace_path: str = "",
        active_file_path: str = "",
        width: int = 240,
        **kwargs,
    ):
        self._on_open_folder = on_open_folder
        self._on_file_click = on_file_click
        self._on_rename = on_rename
        self._on_delete = on_delete
        self._on_quick_convert = on_quick_convert
        self._on_new_file = on_new_file
        self._on_new_folder = on_new_folder
        self._on_status_message = on_status_message
        self._on_batch_convert = on_batch_convert
        self._get_is_dirty = get_is_dirty
        self._get_active_file = get_active_file

        self.workspace_path = workspace_path
        self.active_file_path = active_file_path
        self._is_scanning = False
        self.context_menu: Optional[ExplorerContextMenu] = None

        # Header controls
        self.title_text = ft.Text(
            t("explorer.title"),
            size=11,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.OUTLINE,
        )
        self.folder_name_text = ft.Text(
            os.path.basename(workspace_path) if workspace_path else "",
            size=12,
            weight=ft.FontWeight.BOLD,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
        )
        is_compact = width < 210

        self.btn_collapse_all = ft.IconButton(
            icon=ft.Icons.UNFOLD_LESS_ROUNDED,
            icon_size=15,
            tooltip=t("explorer.collapse_all"),
            on_click=lambda _: self.collapse_all(),
            visible=bool(workspace_path),
        )
        self.btn_open_folder = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            icon_size=15,
            tooltip=t("explorer.open_folder"),
            on_click=lambda e: self._on_open_folder(e) if self._on_open_folder else None,
        )
        self.btn_refresh = ft.IconButton(
            icon=ft.Icons.REFRESH_ROUNDED,
            icon_size=15,
            tooltip=t("explorer.refresh"),
            on_click=lambda _: self.refresh_tree(),
            visible=bool(workspace_path),
        )

        self.btn_actions_row = ft.Row(
            [
                self.btn_collapse_all,
                self.btn_open_folder,
                self.btn_refresh,
            ],
            spacing=0,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            visible=not is_compact,
        )

        self.btn_more = ft.IconButton(
            icon=ft.Icons.MORE_HORIZ_ROUNDED,
            icon_size=15,
            tooltip=t("explorer.more_actions"),
            on_click=self._handle_more_clicked,
            visible=is_compact,
        )

        self.header_row = ft.Row(
            [
                self.title_text,
                ft.Container(expand=True),
                self.btn_actions_row,
                self.btn_more,
            ],
            spacing=2,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.folder_title_row = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.FOLDER_SPECIAL_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                    self.folder_name_text,
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=4, top=2, right=4, bottom=2),
            visible=bool(workspace_path),
        )

        # Inline File Filter Input
        self.filter_input = ft.TextField(
            hint_text=t("explorer.filter_hint"),
            text_size=11,
            dense=True,
            prefix_icon=ft.Icons.SEARCH,
            border_radius=6,
            content_padding=ft.Padding(left=6, top=2, right=6, bottom=2),
            on_change=self._on_filter_changed,
            visible=bool(workspace_path),
        )

        # Tree Container
        self.tree_list = ft.ListView(
            expand=True,
            spacing=1,
            padding=ft.Padding(left=0, top=0, right=0, bottom=0),
        )

        self.tree_list_drag_target = ft.DragTarget(
            group="doc_explorer",
            content=self.tree_list,
            on_accept=self._handle_root_drag_accept,
        )

        # Empty State
        self.empty_state = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.FOLDER_OFF_OUTLINED, size=32, color=ft.Colors.OUTLINE),
                    ft.Text(t("explorer.no_folder"), size=12, color=ft.Colors.OUTLINE, text_align=ft.TextAlign.CENTER),
                    ft.Button(
                        t("explorer.btn_open"),
                        icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=6),
                            padding=ft.Padding(left=12, top=6, right=12, bottom=6),
                        ),
                        on_click=lambda e: self._on_open_folder(e) if self._on_open_folder else None,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.Padding(left=16, top=32, right=16, bottom=16),
            visible=not bool(workspace_path),
        )

        self.content_column = ft.Column(
            [
                self.header_row,
                ft.Divider(height=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
                self.folder_title_row,
                self.filter_input,
                self.empty_state,
                self.tree_list_drag_target,
            ],
            spacing=4,
            expand=True,
        )

        super().__init__(
            content=self.content_column,
            width=width,
            padding=ft.Padding(left=8, top=6, right=6, bottom=6),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            **kwargs,
        )

        if workspace_path:
            self.load_workspace(workspace_path, active_file_path)

    def _handle_root_drag_accept(self, e):
        if not self.workspace_path or not os.path.isdir(self.workspace_path):
            return
        src_path = None
        src_ctrl_id = getattr(e, "src_id", None)
        if src_ctrl_id and self.page:
            try:
                src_ctrl = self.page.get_control(src_ctrl_id)
                if src_ctrl and hasattr(src_ctrl, "data") and src_ctrl.data:
                    src_path = str(src_ctrl.data)
            except Exception:
                pass
        if not src_path:
            src_path = getattr(e, "data", None)
        if src_path:
            self._handle_move_entry(src_path, self.workspace_path)

    def _handle_move_entry(self, src_path: str, dest_dir: str):
        from src.utils.file_ops import validate_move_operation
        import shutil

        is_valid, err_msg = validate_move_operation(src_path, dest_dir)
        if not is_valid:
            if self._on_status_message:
                self._on_status_message(err_msg, ft.Colors.AMBER_400)
            return

        dest_name = os.path.basename(dest_dir) or dest_dir
        src_name = os.path.basename(src_path)
        dest_target = os.path.join(dest_dir, src_name)

        try:
            shutil.move(src_path, dest_target)
            if self._on_rename:
                self._on_rename(src_path, dest_target)
            if self._on_status_message:
                self._on_status_message(
                    t("explorer.moved_status", name=src_name, folder=dest_name),
                    ft.Colors.GREEN_400,
                )
            self.refresh_tree()
        except Exception as ex:
            if self._on_status_message:
                self._on_status_message(
                    t("explorer.move_error", error=str(ex)),
                    ft.Colors.RED_400,
                )

    def _ensure_context_menu(self):
        if not self.context_menu and self.page:
            self.context_menu = ExplorerContextMenu(self.page)

    def _handle_more_clicked(self, e: ft.ControlEvent):
        self._ensure_context_menu()
        if self.context_menu:
            gx = float(getattr(self, "width", 180) or 180) + 30
            gy = 60.0
            if hasattr(e, "global_position") and e.global_position:
                gx = float(e.global_position.x)
                gy = float(e.global_position.y)
            self.context_menu.show_header_menu(
                x=gx,
                y=gy,
                on_open_folder=lambda: self._on_open_folder(None) if self._on_open_folder else None,
                on_collapse_all=self.collapse_all,
                on_refresh=self.refresh_tree,
            )

    def _show_file_context_menu(self, file_path: str, x: float, y: float):
        self._ensure_context_menu()
        if not self.context_menu:
            return

        is_active = (
            os.path.normpath(file_path) == os.path.normpath(self.active_file_path)
            if self.active_file_path
            else False
        )
        is_dirty = self._get_is_dirty() if self._get_is_dirty else False

        self.context_menu.show_file_menu(
            x=x,
            y=y,
            file_path=file_path,
            on_quick_convert=self._handle_quick_convert_action,
            on_reveal=reveal_in_windows_explorer,
            on_copy_path=self._handle_copy_path,
            on_rename=lambda p: show_rename_dialog(self.page, p, self._handle_rename_confirmed),
            on_delete=lambda p: show_safe_delete_dialog(
                self.page, p, is_active, is_dirty, self._handle_delete_confirmed
            ),
            on_batch_convert=self._on_batch_convert if self._on_batch_convert else None,
        )


    def _show_folder_context_menu(self, folder_path: str, x: float, y: float):
        self._ensure_context_menu()
        if not self.context_menu:
            return

        self.context_menu.show_folder_menu(
            x=x,
            y=y,
            folder_path=folder_path,
            on_new_file=lambda p: show_new_entry_dialog(
                self.page, p, is_folder=False, on_confirmed=self._handle_new_entry_confirmed
            ),
            on_new_folder=lambda p: show_new_entry_dialog(
                self.page, p, is_folder=True, on_confirmed=self._handle_new_entry_confirmed
            ),
            on_reveal=reveal_in_windows_explorer,
            on_copy_path=self._handle_copy_path,
            on_batch_convert=self._on_batch_convert if self._on_batch_convert else None,
        )

    def _handle_copy_path(self, path: str):
        set_clipboard_text(path, self.page)
        if self._on_status_message:
            self._on_status_message(t("explorer.copied_status", name=os.path.basename(path)), ft.Colors.BLUE_400)

    def _handle_quick_convert_action(self, file_path: str, target_ext: str):
        if self._on_quick_convert:
            self._on_quick_convert(file_path, target_ext)

    def _handle_rename_confirmed(self, old_path: str, new_name: str):
        target_dir = os.path.dirname(old_path)
        new_full_path = os.path.join(target_dir, new_name)
        try:
            os.rename(old_path, new_full_path)
            if self._on_rename:
                self._on_rename(old_path, new_full_path)
            if self._on_status_message:
                self._on_status_message(
                    t("explorer.renamed_status", old=os.path.basename(old_path), new=new_name),
                    ft.Colors.GREEN_400,
                )
            self.refresh_tree()
        except Exception as ex:
            print(f"[ExplorerView] Rename error: {ex}")

    def _handle_delete_confirmed(self, target_path: str):
        try:
            safe_delete_to_recycle_bin(target_path)
            if self._on_delete:
                self._on_delete(target_path)
            if self._on_status_message:
                self._on_status_message(
                    t("explorer.deleted_status", name=os.path.basename(target_path)),
                    ft.Colors.AMBER_400,
                )
            self.refresh_tree()
        except Exception as ex:
            print(f"[ExplorerView] Delete error: {ex}")

    def _handle_new_entry_confirmed(self, target_dir: str, name: str, is_folder: bool):
        new_full_path = os.path.join(target_dir, name)
        try:
            if is_folder:
                os.makedirs(new_full_path, exist_ok=True)
                if self._on_new_folder:
                    self._on_new_folder(new_full_path)
            else:
                with open(new_full_path, "w", encoding="utf-8") as f:
                    f.write("")
                if self._on_new_file:
                    self._on_new_file(new_full_path)
            if self._on_status_message:
                self._on_status_message(
                    t("explorer.created_status", name=name),
                    ft.Colors.GREEN_400,
                )
            self.refresh_tree()
        except Exception as ex:
            print(f"[ExplorerView] Create entry error: {ex}")

    def update_responsive_width(self, new_width: int):
        """Switches between inline 3-button row and 3-dots dropdown menu based on sidebar width."""
        is_compact = new_width < 210
        self.btn_actions_row.visible = not is_compact
        self.btn_more.visible = is_compact
        self.width = new_width
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def collapse_all(self, e=None):
        """Recursively collapses all expanded directories across the entire tree."""
        for item in self.tree_list.controls:
            if isinstance(item, DirectoryTreeItem):
                item.collapse_all()
        try:
            if self.page:
                self.tree_list.update()
        except Exception:
            pass

    def load_workspace(self, folder_path: str, active_file: str = ""):
        """Sets the root workspace directory and asynchronously scans files."""
        self.workspace_path = folder_path
        self.active_file_path = active_file
        self.folder_name_text.value = os.path.basename(folder_path) or folder_path
        self.folder_title_row.visible = bool(folder_path)
        self.btn_collapse_all.visible = bool(folder_path)
        self.btn_refresh.visible = bool(folder_path)
        self.filter_input.visible = bool(folder_path)
        self.filter_input.value = ""
        self.empty_state.visible = not bool(folder_path)
        self.tree_list.visible = bool(folder_path)
        self.refresh_tree()

    def _on_filter_changed(self, e):
        """Dispatched when user types into the inline search filter."""
        query = (e.control.value or "").strip().lower()
        if not query:
            self.refresh_tree()
            return
        asyncio.create_task(self._async_filter_files(query))

    async def _async_filter_files(self, query: str):
        if not self.workspace_path or not os.path.isdir(self.workspace_path):
            return
        folder = self.workspace_path

        def _search():
            matches = []
            for root, dirs, files in os.walk(folder):
                dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
                for f in sorted(files):
                    if f.startswith(".") and f not in (".env",):
                        continue
                    if query in f.lower():
                        full_path = os.path.join(root, f)
                        rel_dir = os.path.relpath(root, folder)
                        matches.append((full_path, f, rel_dir))
            return matches

        matches = await asyncio.to_thread(_search)
        self.tree_list.controls.clear()
        for full_path, filename, rel_dir in matches[:60]:
            is_act = (
                os.path.normpath(full_path) == os.path.normpath(self.active_file_path)
                if self.active_file_path
                else False
            )
            display_name = f"{filename}  [{rel_dir}]" if rel_dir != "." else filename
            self.tree_list.controls.append(
                FileTreeItem(
                    file_path=full_path,
                    name=display_name,
                    depth=0,
                    on_click=self._handle_file_click,
                    on_secondary_tap_down=self._show_file_context_menu,
                    is_active=is_act,
                )
            )
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def refresh_tree(self):
        """Scans the root workspace folder asynchronously."""
        if not self.workspace_path or not os.path.isdir(self.workspace_path):
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._async_scan_root())
        except RuntimeError:
            if self.page and hasattr(self.page, "run_task"):
                self.page.run_task(self._async_scan_root)
            else:
                try:
                    asyncio.run(self._async_scan_root())
                except Exception:
                    pass


    async def _async_scan_root(self):
        if self._is_scanning:
            return
        self._is_scanning = True
        try:
            self.tree_list.controls.clear()
            folder = self.workspace_path

            def _scan():
                items = []
                try:
                    entries = sorted(
                        os.scandir(folder),
                        key=lambda e: (not e.is_dir(), e.name.lower()),
                    )
                    for entry in entries:
                        if entry.name.startswith(".") and entry.name not in (".env",):
                            continue
                        if entry.is_dir() and entry.name in IGNORED_DIRS:
                            continue
                        items.append((entry.path, entry.name, entry.is_dir()))
                except Exception as ex:
                    print(f"[ExplorerView] Scan error: {ex}")
                return items

            items = await asyncio.to_thread(_scan)

            for path, name, is_dir in items:
                if is_dir:
                    self.tree_list.controls.append(
                        DirectoryTreeItem(
                            dir_path=path,
                            name=name,
                            depth=0,
                            on_file_click=self._handle_file_click,
                            on_file_secondary=self._show_file_context_menu,
                            on_folder_secondary=self._show_folder_context_menu,
                            on_move_entry=self._handle_move_entry,
                            active_path=self.active_file_path,
                        )
                    )
                else:
                    is_act = (
                        os.path.normpath(path) == os.path.normpath(self.active_file_path)
                        if self.active_file_path
                        else False
                    )
                    self.tree_list.controls.append(
                        FileTreeItem(
                            file_path=path,
                            name=name,
                            depth=0,
                            on_click=self._handle_file_click,
                            on_secondary_tap_down=self._show_file_context_menu,
                            is_active=is_act,
                        )
                    )

            try:
                if self.page:
                    self.page.update()
            except Exception:
                pass
        finally:
            self._is_scanning = False

    def set_active_file(self, file_path: str):
        """Highlights the active open file in the tree."""
        self.active_file_path = file_path
        # Recursively update active status on items
        def _update_items(controls):
            for ctrl in controls:
                if isinstance(ctrl, FileTreeItem):
                    ctrl.set_active(
                        os.path.normpath(ctrl.file_path) == os.path.normpath(file_path)
                        if file_path
                        else False
                    )
                elif isinstance(ctrl, DirectoryTreeItem):
                    ctrl.active_path = file_path
                    _update_items(ctrl.children_column.controls)

        _update_items(self.tree_list.controls)

    def _handle_file_click(self, file_path: str):
        self.set_active_file(file_path)
        if self._on_file_click:
            self._on_file_click(file_path)

    def update_locale(self):
        """Refreshes text on language toggle."""
        self.title_text.value = t("explorer.title")
        self.btn_open_folder.tooltip = t("explorer.open_folder")
        self.btn_refresh.tooltip = t("explorer.refresh")
        try:
            if self.page:
                self.update()
        except Exception:
            pass
