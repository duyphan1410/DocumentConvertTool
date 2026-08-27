"""
File Explorer Sidebar View for DocConvert Workspace.
Provides a folder tree view with on-demand lazy loading, async directory scanning,
and contextual file extension icons.
"""
from __future__ import annotations

import os
import asyncio
from typing import Callable, Optional
import flet as ft
from src.i18n import t

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


class FileTreeItem(ft.Container):
    """An individual file entry in the Explorer tree."""

    def __init__(
        self,
        file_path: str,
        name: str,
        depth: int,
        on_click: Optional[Callable[[str], None]] = None,
        is_active: bool = False,
        **kwargs,
    ):
        self.file_path = file_path
        self.file_name = name
        self.depth = depth
        self._on_click_callback = on_click
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

        super().__init__(
            content=ft.Row(
                [
                    ft.Icon(icon, size=15, color=color),
                    self.label,
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=12 + (depth * 14), top=3, right=6, bottom=3),
            border_radius=4,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY) if is_active else ft.Colors.TRANSPARENT,
            ink=True,
            on_click=self._handle_click,
            **kwargs,
        )

    def set_active(self, is_active: bool):
        self.is_active = is_active
        self.label.weight = ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL
        self.label.color = ft.Colors.PRIMARY if is_active else None
        self.bgcolor = (
            ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY)
            if is_active
            else ft.Colors.TRANSPARENT
        )
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def _handle_click(self, e):
        if self._on_click_callback:
            self._on_click_callback(self.file_path)


class DirectoryTreeItem(ft.Column):
    """A directory node supporting lazy-loading of child items on expansion."""

    def __init__(
        self,
        dir_path: str,
        name: str,
        depth: int,
        on_file_click: Optional[Callable[[str], None]] = None,
        active_path: str = "",
        **kwargs,
    ):
        self.dir_path = dir_path
        self.dir_name = name
        self.depth = depth
        self.on_file_click = on_file_click
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

        self.header = ft.Container(
            content=ft.Row(
                [
                    self.icon_arrow,
                    self.icon_folder,
                    self.label,
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=4 + (depth * 14), top=3, right=6, bottom=3),
            border_radius=4,
            ink=True,
            on_click=self._toggle_expand,
        )

        self.children_column = ft.Column(spacing=1, visible=False)

        super().__init__(
            controls=[self.header, self.children_column],
            spacing=0,
            **kwargs,
        )

    def _toggle_expand(self, e):
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
                            is_active=is_act,
                        )
                    )
        except Exception as ex:
            print(f"[ExplorerView] Failed to scan {self.dir_path}: {ex}")


class ExplorerView(ft.Container):
    """
    Explorer Sidebar panel displaying the current Workspace directory tree.
    """

    def __init__(
        self,
        on_open_folder: Optional[Callable] = None,
        on_file_click: Optional[Callable[[str], None]] = None,
        workspace_path: str = "",
        active_file_path: str = "",
        width: int = 240,
        **kwargs,
    ):
        self._on_open_folder = on_open_folder
        self._on_file_click = on_file_click
        self.workspace_path = workspace_path
        self.active_file_path = active_file_path
        self._is_scanning = False

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
        self.btn_open_folder = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            icon_size=16,
            tooltip=t("explorer.open_folder"),
            on_click=lambda e: self._on_open_folder(e) if self._on_open_folder else None,
        )
        self.btn_refresh = ft.IconButton(
            icon=ft.Icons.REFRESH_ROUNDED,
            icon_size=16,
            tooltip=t("explorer.refresh"),
            on_click=lambda _: self.refresh_tree(),
        )

        self.header_row = ft.Row(
            [
                self.title_text,
                ft.Container(expand=True),
                self.btn_open_folder,
                self.btn_refresh,
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
                self.tree_list,
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

    def load_workspace(self, folder_path: str, active_file: str = ""):
        """Sets the root workspace directory and asynchronously scans files."""
        self.workspace_path = folder_path
        self.active_file_path = active_file
        self.folder_name_text.value = os.path.basename(folder_path) or folder_path
        self.folder_title_row.visible = bool(folder_path)
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
        asyncio.create_task(self._async_scan_root())

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
