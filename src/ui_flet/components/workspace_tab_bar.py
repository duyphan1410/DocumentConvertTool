"""
WorkspaceTabBar component for DocumentConvertTool Flet UI.
Provides a modern IDE multi-tab strip with Draggable/DragTarget reordering,
orphaned file indicators, dirty dots, and context actions.
"""
import os
import flet as ft
from typing import Callable, Optional
from src.ui_flet.state import DocumentTabState
from src.i18n import t


def _get_file_icon(in_path: str, is_orphaned: bool = False) -> tuple[str, str]:
    """Returns (icon_name, color) based on file extension."""
    if is_orphaned:
        return ft.Icons.WARNING_AMBER_ROUNDED, ft.Colors.AMBER_400

    if not in_path:
        return ft.Icons.EDIT_DOCUMENT, ft.Colors.PRIMARY

    ext = os.path.splitext(in_path)[1].lower()
    if ext == ".md":
        return ft.Icons.DESCRIPTION_OUTLINED, ft.Colors.PRIMARY
    elif ext in (".xlsx", ".xls", ".csv"):
        return ft.Icons.TABLE_CHART_OUTLINED, ft.Colors.TEAL_400
    elif ext in (".docx", ".doc"):
        return ft.Icons.ARTICLE_OUTLINED, ft.Colors.BLUE_400
    elif ext == ".pdf":
        return ft.Icons.PICTURE_AS_PDF_OUTLINED, ft.Colors.RED_400
    elif ext in (".html", ".htm"):
        return ft.Icons.CODE_OUTLINED, ft.Colors.ORANGE_400
    elif ext in (".json", ".yaml", ".yml"):
        return ft.Icons.DATA_OBJECT_OUTLINED, ft.Colors.PURPLE_400
    elif ext == ".pptx":
        return ft.Icons.CO_PRESENT_OUTLINED, ft.Colors.DEEP_ORANGE_400
    return ft.Icons.INSERT_DRIVE_FILE_OUTLINED, ft.Colors.ON_SURFACE_VARIANT


class DocumentTabItem(ft.Container):
    """Visual representation of a single DocumentTabState with Draggable reordering."""

    def __init__(
        self,
        tab: DocumentTabState,
        is_active: bool,
        on_select: Callable[[str], None],
        on_close: Callable[[str], None],
        on_reorder: Callable[[str, str], None],
        on_context_menu: Optional[Callable[[str, ft.ControlEvent], None]] = None,
    ):
        self.tab = tab
        self.is_active = is_active
        self.on_select = on_select
        self.on_close = on_close
        self.on_reorder = on_reorder
        self.on_context_menu = on_context_menu

        icon_name, icon_col = _get_file_icon(tab.in_path, tab.is_orphaned)

        # Tab Title Display
        display_title = tab.title or t("tab.untitled")
        title_color = ft.Colors.AMBER_300 if tab.is_orphaned else (
            ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE
        )

        title_text = ft.Text(
            display_title,
            size=12,
            weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_400,
            color=title_color,
            italic=tab.is_orphaned,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        # Close button
        self.close_btn = ft.IconButton(
            icon=ft.Icons.CLOSE,
            icon_size=12,
            icon_color=ft.Colors.ON_SURFACE_VARIANT,
            width=20,
            height=20,
            padding=0,
            tooltip=t("tab.close"),
            on_click=lambda e: self._on_close_clicked(e),
        )

        # Dirty Indicator Dot
        self.dirty_dot = ft.Container(
            width=8,
            height=8,
            border_radius=4,
            bgcolor=ft.Colors.PRIMARY,
            margin=ft.Margin(left=4, top=0, right=4, bottom=0),
            visible=tab.is_dirty,
        )

        # Leading Icon or Animated Progress Spinner for heavy loading tabs
        if getattr(tab, "is_loading", False):
            leading_icon = ft.Container(
                content=ft.ProgressRing(width=12, height=12, stroke_width=1.8, color=icon_col),
                width=14,
                height=14,
                alignment=ft.Alignment(0, 0),
            )
        else:
            leading_icon = ft.Icon(icon_name, size=14, color=icon_col)

        # Tab Title & Icon Click Area (isolated from close button)
        title_click_area = ft.Container(
            content=ft.GestureDetector(
                content=ft.Row(
                    controls=[
                        leading_icon,
                        ft.Container(content=title_text, expand=True),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=6,
                ),
                on_tap=lambda e: self.on_select(self.tab.tab_id),
                on_secondary_tap_down=lambda e: self._handle_secondary_tap(e) if self.on_context_menu else None,
                on_long_press=lambda e: self._handle_secondary_tap(e) if self.on_context_menu else None,
            ),
            expand=True,
        )

        # Tab Content Row
        content_row = ft.Row(
            controls=[
                title_click_area,
                self.dirty_dot,
                self.close_btn,
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        )

        tooltip_text = (
            f"{tab.title}\n({t('tab.orphaned_tooltip')})"
            if tab.is_orphaned
            else (tab.in_path or tab.title or t("tab.untitled"))
        )

        # Inner Tab Box (Visual styling container)
        tab_box = ft.Container(
            content=content_row,
            padding=ft.Padding(left=8, top=4, right=4, bottom=4),
            border_radius=ft.BorderRadius(top_left=6, top_right=6, bottom_left=0, bottom_right=0),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST if is_active else ft.Colors.SURFACE_CONTAINER,
            border=ft.Border(
                top=ft.BorderSide(2, ft.Colors.PRIMARY if is_active else ft.Colors.TRANSPARENT),
                left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                bottom=ft.BorderSide(0, ft.Colors.TRANSPARENT),
            ),
            width=160,
            tooltip=tooltip_text,
        )

        # Draggable wrapper
        draggable = ft.Draggable(
            group="doc_tabs",
            data=tab.tab_id,
            content=tab_box,
            content_feedback=ft.Container(
                content=ft.Text(display_title, size=12, color=ft.Colors.PRIMARY),
                padding=ft.Padding(left=10, top=4, right=10, bottom=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border_radius=6,
                shadow=ft.BoxShadow(spread_radius=1, blur_radius=4, color=ft.Colors.BLACK38),
            ),
        )

        # DragTarget wrapper
        drag_target = ft.DragTarget(
            group="doc_tabs",
            content=draggable,
            on_accept=lambda e: self._on_drag_accept(e),
        )

        super().__init__(content=drag_target)

    def _on_close_clicked(self, e):
        self.on_close(self.tab.tab_id)

    def _handle_secondary_tap(self, e):
        if self.on_context_menu:
            gx = 300.0
            gy = 80.0
            if hasattr(e, "global_position") and e.global_position:
                gx = float(e.global_position.x)
                gy = float(e.global_position.y)
            elif hasattr(e, "local_position") and e.local_position:
                gx = float(e.local_position.x)
                gy = float(e.local_position.y)
            self.on_context_menu(self.tab.tab_id, gx, gy)

    def _on_drag_accept(self, e):
        src_ctrl_id = getattr(e, "src_id", None)
        source_id = None
        if src_ctrl_id and self.page:
            try:
                src_ctrl = self.page.get_control(src_ctrl_id)
                if src_ctrl and hasattr(src_ctrl, "data") and src_ctrl.data:
                    source_id = str(src_ctrl.data)
            except Exception:
                pass

        if not source_id:
            source_id = getattr(e, "data", None) or src_ctrl_id

        target_id = self.tab.tab_id
        if source_id and target_id and source_id != target_id:
            self.on_reorder(source_id, target_id)


class WorkspaceTabBar(ft.Container):
    """
    Top Tab Bar component positioned above the Editor & Preview area.
    Manages document tabs, dynamic active highlight, 3px micro scrollbar, and context menus.
    """

    def __init__(
        self,
        on_tab_select: Callable[[str], None],
        on_tab_close: Callable[[str], None],
        on_tab_reorder: Callable[[str, str], None],
        on_new_tab: Callable[[], None],
        on_close_others: Optional[Callable[[str], None]] = None,
        on_close_to_right: Optional[Callable[[str], None]] = None,
        on_close_all: Optional[Callable[[], None]] = None,
        on_copy_path: Optional[Callable[[str], None]] = None,
        on_reveal: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.on_tab_select = on_tab_select
        self.on_tab_close = on_tab_close
        self.on_tab_reorder = on_tab_reorder
        self.on_new_tab = on_new_tab
        self.on_close_others = on_close_others
        self.on_close_to_right = on_close_to_right
        self.on_close_all = on_close_all
        self.on_copy_path = on_copy_path
        self.on_reveal = on_reveal
        self.context_menu = None

        # TabBar-specific ultra-sleek micro scrollbar (3px) matching RibbonBar
        self.theme = ft.Theme(
            scrollbar_theme=ft.ScrollbarTheme(
                thickness=3,
                radius=2,
                track_visibility=False,
                thumb_visibility=False,
                interactive=True,
            )
        )
        self.dark_theme = self.theme

        self._cached_tabs: list[DocumentTabState] = []
        self._cached_active_id: str | None = None

        self.tab_row = ft.Row(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            spacing=2,
            vertical_alignment=ft.CrossAxisAlignment.END,
            expand=True,
        )

        self.new_tab_btn = ft.IconButton(
            icon=ft.Icons.ADD,
            icon_size=16,
            icon_color=ft.Colors.ON_SURFACE_VARIANT,
            tooltip=t("tab.new_tab"),
            width=28,
            height=28,
            padding=0,
            on_click=lambda e: self.on_new_tab(),
        )

        self.content = ft.Row(
            controls=[
                self.tab_row,
                ft.Container(content=self.new_tab_btn, margin=ft.Margin(left=4, top=0, right=4, bottom=0)),
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        )

        self.height = 36
        self.padding = ft.Padding(left=4, top=2, right=4, bottom=0)
        self.bgcolor = ft.Colors.SURFACE_CONTAINER_LOW
        self.border = ft.Border(
            top=ft.BorderSide(0, ft.Colors.TRANSPARENT),
            left=ft.BorderSide(0, ft.Colors.TRANSPARENT),
            right=ft.BorderSide(0, ft.Colors.TRANSPARENT),
            bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
        )

    def render_tabs(self, tabs: list[DocumentTabState], active_tab_id: str | None):
        """Re-renders all tab items in the tab strip."""
        self._cached_tabs = tabs
        self._cached_active_id = active_tab_id

        tab_controls = []
        for tab in tabs:
            is_active = (tab.tab_id == active_tab_id)
            item = DocumentTabItem(
                tab=tab,
                is_active=is_active,
                on_select=self.on_tab_select,
                on_close=self.on_tab_close,
                on_reorder=self.on_tab_reorder,
                on_context_menu=self._show_tab_context_menu,
            )
            tab_controls.append(item)

        self.tab_row.controls = tab_controls
        self.visible = len(tabs) > 0
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def set_tab_loading(self, tab_id: str, is_loading: bool):
        """Toggles the animated loading spinner for a specific tab."""
        for tab in self._cached_tabs:
            if tab.tab_id == tab_id:
                tab.is_loading = is_loading
                break
        self.render_tabs(self._cached_tabs, self._cached_active_id)

    def _show_tab_context_menu(self, tab_id: str, x: float, y: float):
        """Context menu for document tabs."""
        if not self.page:
            return
        from src.ui_flet.components.context_menu import ExplorerContextMenu
        if not self.context_menu:
            self.context_menu = ExplorerContextMenu(self.page)

        tab = next((t for t in self._cached_tabs if t.tab_id == tab_id), None)
        if not tab:
            return

        idx = next((i for i, t in enumerate(self._cached_tabs) if t.tab_id == tab_id), -1)
        can_close_others = len(self._cached_tabs) > 1
        can_close_to_right = (idx >= 0 and idx < len(self._cached_tabs) - 1)

        self.context_menu.show_tab_menu(
            x=x,
            y=y,
            tab_id=tab_id,
            in_path=tab.in_path or "",
            can_close_others=can_close_others,
            can_close_to_right=can_close_to_right,
            on_close=self.on_tab_close,
            on_close_others=self.on_close_others,
            on_close_to_right=self.on_close_to_right,
            on_close_all=self.on_close_all,
            on_copy_path=self.on_copy_path,
            on_reveal=self.on_reveal,
        )

    def update_locale(self):
        """Refreshes tooltips on locale change."""
        self.new_tab_btn.tooltip = t("tab.new_tab")
        if self._cached_tabs:
            self.render_tabs(self._cached_tabs, self._cached_active_id)

