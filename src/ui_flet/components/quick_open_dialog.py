"""
Quick Open / File Switcher Modal Dialog (Ctrl+P / Activity Bar Search).
Provides fuzzy file search across the active workspace folder with instant preview loading.
"""
from __future__ import annotations

import os
from typing import Callable, Optional, List
import flet as ft
from src.i18n import t
from src.ui_flet.views.explorer_view import EXT_CONFIG, IGNORED_DIRS


class QuickOpenDialog(ft.AlertDialog):
    """Floating modal dialog for fast file jumping across project workspace."""

    def __init__(
        self,
        get_workspace_path: Callable[[], str],
        on_file_selected: Callable[[str], None],
        **kwargs,
    ):
        self._get_workspace_path = get_workspace_path
        self._on_file_selected = on_file_selected
        self._all_files: List[str] = []
        self._filtered_files: List[str] = []
        self._selected_idx: int = 0

        self.search_input = ft.TextField(
            hint_text=t("quick_open.hint"),
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            text_size=13,
            dense=True,
            autofocus=True,
            border_radius=8,
            on_change=self._on_search_changed,
            on_submit=self._on_submit_first,
        )

        self.results_list = ft.ListView(
            expand=True,
            spacing=2,
            height=260,
        )

        self.no_results_text = ft.Text(
            t("quick_open.no_results"),
            size=12,
            color=ft.Colors.OUTLINE,
            text_align=ft.TextAlign.CENTER,
            visible=False,
        )

        content_container = ft.Container(
            content=ft.Column(
                [
                    self.search_input,
                    ft.Divider(height=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
                    self.results_list,
                    self.no_results_text,
                ],
                spacing=8,
                tight=True,
            ),
            width=520,
            padding=ft.Padding(left=12, top=12, right=12, bottom=12),
        )

        super().__init__(
            modal=False,
            on_dismiss=lambda _: self.close(),
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.FIND_IN_PAGE_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                    ft.Text(t("quick_open.title"), size=14, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.IconButton(
                        ft.Icons.CLOSE,
                        icon_size=16,
                        on_click=lambda _: self.close(),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=content_container,
            **kwargs,
        )

    def show(self, page: ft.Page):
        """Pre-scans the workspace files and opens the modal dialog."""
        self._scan_workspace()
        self.search_input.value = ""
        self._filter_and_render("")
        self.open = True
        if self not in page.overlay:
            page.overlay.append(self)
        try:
            page.update()
        except Exception:
            pass

    def close(self):
        """Closes the dialog."""
        self.open = False
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def _scan_workspace(self):
        """Quickly scans all document files in workspace."""
        self._all_files.clear()
        ws = self._get_workspace_path()
        if not ws or not os.path.isdir(ws):
            return

        for root, dirs, files in os.walk(ws):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
            for f in sorted(files):
                if f.startswith(".") and f not in (".env",):
                    continue
                ext = os.path.splitext(f)[1].lower()
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, ws)
                self._all_files.append((rel_path, full_path, f, ext))

    def _filter_and_render(self, query: str):
        q = query.strip().lower()
        self.results_list.controls.clear()
        self._filtered_files.clear()

        ws = self._get_workspace_path()
        if not ws:
            self.no_results_text.value = t("quick_open.no_workspace")
            self.no_results_text.visible = True
            return

        matches = []
        for rel_path, full_path, filename, ext in self._all_files:
            if not q or q in filename.lower() or q in rel_path.lower():
                matches.append((rel_path, full_path, filename, ext))

        self._filtered_files = matches
        self.no_results_text.value = t("quick_open.no_results")
        self.no_results_text.visible = len(matches) == 0

        for idx, (rel_path, full_path, filename, ext) in enumerate(matches[:30]):
            icon, color = EXT_CONFIG.get(ext, (ft.Icons.INSERT_DRIVE_FILE_OUTLINED, ft.Colors.OUTLINE))
            folder_dir = os.path.dirname(rel_path)

            spans = [
                ft.TextSpan(
                    filename,
                    style=ft.TextStyle(
                        size=12,
                        weight=ft.FontWeight.W_500,
                    ),
                )
            ]
            if folder_dir and folder_dir != ".":
                spans.append(
                    ft.TextSpan(
                        f"  {folder_dir}",
                        style=ft.TextStyle(
                            size=12,
                            color=ft.Colors.OUTLINE,
                        ),
                    )
                )

            item = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(icon, size=16, color=color),
                        ft.Text(
                            spans=spans,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(left=10, top=6, right=10, bottom=6),
                border_radius=6,
                ink=True,
                on_click=lambda _, p=full_path: self._select_file(p),
            )
            self.results_list.controls.append(item)

        try:
            if self.page:
                self.results_list.update()
                self.no_results_text.update()
        except Exception:
            pass

    def _on_search_changed(self, e):
        self._filter_and_render(e.control.value or "")

    def _on_submit_first(self, _):
        if self._filtered_files:
            first_path = self._filtered_files[0][1]
            self._select_file(first_path)

    def _select_file(self, full_path: str):
        self.close()
        if self._on_file_selected:
            self._on_file_selected(full_path)
