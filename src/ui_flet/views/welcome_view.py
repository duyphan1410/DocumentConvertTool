"""
Welcome / Onboarding Dashboard View for Flet UI.
Displays a modern 2-column studio layout with primary actions on the left
and real-time Recent Files & Folders history on the right.
Fully responsive: adapts smoothly between maximized full-screen and compact window sizes.
"""
import os
import time
import flet as ft
from typing import Callable, Optional, List, Dict, Any

from src.i18n import t
from src.services.history_service import HistoryService
from src.ui_flet.theme import resolve_color, make_border


def _get_format_icon_meta(path: str, is_folder: bool = False) -> tuple[str, str]:
    """Returns (icon_name, color_hex_or_constant) based on file type."""
    if is_folder:
        return ft.Icons.FOLDER_ROUNDED, ft.Colors.AMBER_400

    ext = os.path.splitext(path)[1].lower()
    if ext in (".docx", ".doc"):
        return ft.Icons.ARTICLE_ROUNDED, ft.Colors.BLUE_400
    elif ext in (".xlsx", ".xls", ".csv"):
        return ft.Icons.TABLE_CHART_ROUNDED, ft.Colors.GREEN_400
    elif ext == ".pdf":
        return ft.Icons.PICTURE_AS_PDF_ROUNDED, ft.Colors.ORANGE_400
    elif ext in (".md", ".markdown", ".txt"):
        return ft.Icons.DESCRIPTION_ROUNDED, ft.Colors.TEAL_400
    elif ext in (".html", ".htm"):
        return ft.Icons.CODE_ROUNDED, ft.Colors.AMBER_500
    elif ext in (".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"):
        return ft.Icons.AUDIO_FILE_ROUNDED, ft.Colors.PURPLE_400
    elif ext in (".mp4", ".mkv", ".avi", ".mov", ".webm"):
        return ft.Icons.VIDEO_FILE_ROUNDED, ft.Colors.DEEP_PURPLE_400
    return ft.Icons.INSERT_DRIVE_FILE_ROUNDED, ft.Colors.PRIMARY


def _format_relative_time(timestamp: float) -> str:
    """Formats timestamp into friendly relative time string."""
    diff = max(0, time.time() - timestamp)
    if diff < 60:
        return t("welcome.time_just_now")
    elif diff < 3600:
        mins = max(1, int(diff / 60))
        return t("welcome.time_mins_ago", n=mins)
    elif diff < 86400:
        hrs = max(1, int(diff / 3600))
        return t("welcome.time_hours_ago", n=hrs)
    elif diff < 172800:
        return t("welcome.time_yesterday")
    else:
        days = max(2, int(diff / 86400))
        return t("welcome.time_days_ago", n=days)


class WelcomeActionCard(ft.Container):
    """An interactive card representing a primary workspace action."""

    def __init__(
        self,
        icon: str,
        title_key: str,
        desc_key: str,
        shortcut: Optional[str] = None,
        on_click: Optional[Callable] = None,
        icon_color: Optional[str] = None,
        **kwargs,
    ):
        self.title_key = title_key
        self.desc_key = desc_key
        self.shortcut = shortcut
        self._action_callback = on_click
        self._custom_icon_color = icon_color

        self.icon_widget = ft.Icon(
            icon,
            size=20,
            color=icon_color or ft.Colors.PRIMARY,
        )
        self.icon_badge = ft.Container(
            content=self.icon_widget,
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
            padding=ft.Padding(left=7, top=7, right=7, bottom=7),
            border_radius=8,
            alignment=ft.alignment.Alignment(0.0, 0.0),
        )

        self.title_text = ft.Text(
            t(title_key),
            size=12,
            weight=ft.FontWeight.BOLD,
        )

        self.desc_text = ft.Text(
            t(desc_key),
            size=10,
            color=ft.Colors.OUTLINE,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        title_children = [self.title_text]
        if shortcut:
            self.badge_shortcut = ft.Container(
                content=ft.Text(
                    shortcut,
                    size=8,
                    font_family="Consolas",
                    weight=ft.FontWeight.BOLD,
                ),
                bgcolor=ft.Colors.PRIMARY_CONTAINER,
                padding=ft.Padding(left=4, top=1, right=4, bottom=1),
                border_radius=4,
                border=ft.Border(
                    left=ft.BorderSide(1, ft.Colors.PRIMARY),
                    top=ft.BorderSide(1, ft.Colors.PRIMARY),
                    right=ft.BorderSide(1, ft.Colors.PRIMARY),
                    bottom=ft.BorderSide(1, ft.Colors.PRIMARY),
                ),
            )
            title_children.append(self.badge_shortcut)

        title_row = ft.Row(
            title_children,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        text_column = ft.Column(
            [title_row, self.desc_text],
            spacing=1,
            expand=True,
        )

        card_content = ft.Row(
            [self.icon_badge, text_column],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        super().__init__(
            content=card_content,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            padding=ft.Padding(left=10, top=7, right=10, bottom=7),
            border_radius=9,
            border=ft.Border(
                left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            ),
            ink=True,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            on_click=self._handle_click,
            on_hover=self._handle_hover,
            **kwargs,
        )

    def _handle_click(self, e):
        if self._action_callback:
            self._action_callback(e)

    def _handle_hover(self, e):
        is_hovered = e.data == "true"
        if is_hovered:
            self.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGHEST
            self.border = ft.Border(
                left=ft.BorderSide(1, ft.Colors.PRIMARY),
                top=ft.BorderSide(1, ft.Colors.PRIMARY),
                right=ft.BorderSide(1, ft.Colors.PRIMARY),
                bottom=ft.BorderSide(1, ft.Colors.PRIMARY),
            )
        else:
            self.bgcolor = ft.Colors.SURFACE_CONTAINER
            self.border = ft.Border(
                left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            )
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def update_locale(self):
        self.title_text.value = t(self.title_key)
        self.desc_text.value = t(self.desc_key)

    def apply_palette(self, accent_primary: str):
        if not self._custom_icon_color:
            self.icon_widget.color = accent_primary
        if hasattr(self, "badge_shortcut") and self.badge_shortcut:
            self.badge_shortcut.border = ft.Border(
                left=ft.BorderSide(1, accent_primary),
                top=ft.BorderSide(1, accent_primary),
                right=ft.BorderSide(1, accent_primary),
                bottom=ft.BorderSide(1, accent_primary),
            )


class RecentItemTile(ft.Container):
    """An interactive item representing a recent file or folder in the history list."""

    def __init__(
        self,
        item: Dict[str, Any],
        on_open: Callable[[str, str], None],
        on_remove: Callable[[str, str], None],
        on_toggle_pin: Callable[[str, str], None],
    ):
        self.item = item
        self.item_path = item.get("path", "")
        self.item_name = item.get("name", "")
        self.item_type = item.get("type", "file")
        self.is_pinned = item.get("pinned", False)
        self.exists = item.get("exists", True)
        self.last_opened = item.get("last_opened", time.time())

        self._on_open = on_open
        self._on_remove = on_remove
        self._on_toggle_pin = on_toggle_pin

        icon_name, icon_color = _get_format_icon_meta(self.item_path, self.item_type == "folder")
        self.icon = ft.Icon(
            icon_name,
            size=18,
            color=icon_color if self.exists else ft.Colors.OUTLINE,
        )
        self.icon_badge = ft.Container(
            content=self.icon,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST if self.exists else ft.Colors.SURFACE_CONTAINER,
            padding=ft.Padding(left=6, top=6, right=6, bottom=6),
            border_radius=8,
            alignment=ft.alignment.Alignment(0.0, 0.0),
        )

        title_controls: List[ft.Control] = [
            ft.Text(
                self.item_name,
                size=12,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE if self.exists else ft.Colors.OUTLINE,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
        ]

        if not self.exists:
            title_controls.append(
                ft.Container(
                    content=ft.Text(
                        t("welcome.recent_missing_file"),
                        size=9,
                        color=ft.Colors.RED_400,
                        italic=True,
                    ),
                    padding=ft.Padding(left=4, top=1, right=4, bottom=1),
                    border_radius=4,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                )
            )

        # Parent directory path
        parent_dir = os.path.dirname(self.item_path)
        self.subtitle_text = ft.Text(
            parent_dir,
            size=10,
            color=ft.Colors.OUTLINE,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        # Relative time text
        self.time_text = ft.Text(
            _format_relative_time(self.last_opened),
            size=10,
            color=ft.Colors.OUTLINE,
        )

        text_col = ft.Column(
            [
                ft.Row(title_controls, spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row(
                    [
                        ft.Container(content=self.subtitle_text, expand=True),
                        self.time_text,
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=2,
            expand=True,
        )

        # Action buttons (Pin and Remove)
        self.btn_pin = ft.IconButton(
            icon=ft.Icons.PUSH_PIN if self.is_pinned else ft.Icons.PUSH_PIN_OUTLINED,
            icon_size=14,
            icon_color=ft.Colors.PRIMARY if self.is_pinned else ft.Colors.OUTLINE,
            tooltip=t("welcome.recent_unpin_item") if self.is_pinned else t("welcome.recent_pin_item"),
            on_click=self._handle_pin_click,
            style=ft.ButtonStyle(padding=ft.Padding(left=4, top=4, right=4, bottom=4)),
        )

        self.btn_remove = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_size=14,
            icon_color=ft.Colors.OUTLINE,
            tooltip=t("welcome.recent_remove_item"),
            on_click=self._handle_remove_click,
            style=ft.ButtonStyle(padding=ft.Padding(left=4, top=4, right=4, bottom=4)),
        )

        row_content = ft.Row(
            [
                self.icon_badge,
                text_col,
                self.btn_pin,
                self.btn_remove,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        super().__init__(
            content=row_content,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            padding=ft.Padding(left=10, top=5, right=6, bottom=5),
            border_radius=8,
            border=ft.Border(
                left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            ),
            ink=True,
            tooltip=self.item_path,
            on_click=self._handle_tile_click,
            on_hover=self._handle_hover,
        )

    def _handle_tile_click(self, e):
        if self._on_open:
            self._on_open(self.item_path, self.item_type)

    def _handle_pin_click(self, e):
        if self._on_toggle_pin:
            self._on_toggle_pin(self.item_path, self.item_type)

    def _handle_remove_click(self, e):
        if self._on_remove:
            self._on_remove(self.item_path, self.item_type)

    def _handle_hover(self, e):
        is_hovered = e.data == "true"
        if is_hovered:
            self.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGH
            self.border = ft.Border(
                left=ft.BorderSide(1, ft.Colors.PRIMARY_CONTAINER),
                top=ft.BorderSide(1, ft.Colors.PRIMARY_CONTAINER),
                right=ft.BorderSide(1, ft.Colors.PRIMARY_CONTAINER),
                bottom=ft.BorderSide(1, ft.Colors.PRIMARY_CONTAINER),
            )
        else:
            self.bgcolor = ft.Colors.SURFACE_CONTAINER_LOW
            self.border = ft.Border(
                left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            )
        try:
            if self.page:
                self.update()
        except Exception:
            pass


class WelcomeView(ft.Container):
    """
    Studio Welcome View:
    Left: Branding & Quick Action Cards (Scrollable).
    Right: Recent Files & Folders Activity History (Expands dynamically).
    Responsive on both small windows and full-screen maximization.
    """

    def __init__(
        self,
        on_open_file: Optional[Callable] = None,
        on_open_folder: Optional[Callable] = None,
        on_create_blank: Optional[Callable] = None,
        on_import_youtube: Optional[Callable] = None,
        on_transcribe_media: Optional[Callable] = None,
        on_open_model_hub: Optional[Callable] = None,
        on_open_help: Optional[Callable] = None,
        on_open_recent_file: Optional[Callable[[str], None]] = None,
        on_open_recent_folder: Optional[Callable[[str], None]] = None,
        on_new_window: Optional[Callable] = None,
        on_return_editor: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.on_open_file = on_open_file
        self.on_open_folder = on_open_folder
        self.on_create_blank = on_create_blank
        self.on_import_youtube = on_import_youtube
        self.on_transcribe_media = on_transcribe_media
        self.on_open_model_hub = on_open_model_hub
        self.on_open_help = on_open_help
        self.on_open_recent_file = on_open_recent_file
        self.on_open_recent_folder = on_open_recent_folder
        self.on_new_window = on_new_window
        self.on_return_editor = on_return_editor

        self.history_service = HistoryService.get_instance()
        self.current_filter = "all"
        self.search_query = ""
        self._is_compact_layout = False

        self.expand = True
        self.alignment = ft.alignment.Alignment(0.0, 0.0)
        self.padding = ft.Padding(left=0, top=4, right=0, bottom=4)

        # ── LEFT COLUMN: Actions & Branding ──────────────────────────────────
        self.icon_logo = ft.Icon(
            ft.Icons.DESCRIPTION_ROUNDED,
            color=ft.Colors.PRIMARY,
            size=28,
        )
        self.logo_badge = ft.Container(
            content=self.icon_logo,
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
            width=46,
            height=46,
            border_radius=12,
            alignment=ft.alignment.Alignment(0.0, 0.0),
        )

        self.title_text = ft.Text(
            t("welcome.title"),
            size=16,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.LEFT,
        )
        self.subtitle_text = ft.Text(
            t("welcome.subtitle"),
            size=11,
            color=ft.Colors.OUTLINE,
            text_align=ft.TextAlign.LEFT,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        header_text_col = ft.Column(
            [self.title_text, self.subtitle_text],
            spacing=1,
            expand=True,
        )
        header_row = ft.Row(
            [self.logo_badge, header_text_col],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Action Cards
        self.card_open_file = WelcomeActionCard(
            icon=ft.Icons.FILE_OPEN_ROUNDED,
            title_key="welcome.btn_open",
            desc_key="welcome.desc_open",
            shortcut="Ctrl + O",
            on_click=lambda e: self._on_open_click(e),
        )

        self.card_open_folder = WelcomeActionCard(
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            title_key="welcome.btn_open_folder",
            desc_key="welcome.desc_open_folder",
            shortcut="Ctrl + B",
            on_click=lambda e: self._on_open_folder_click(e),
        )

        self.card_blank = WelcomeActionCard(
            icon=ft.Icons.NOTE_ADD_ROUNDED,
            title_key="welcome.btn_blank",
            desc_key="welcome.desc_blank",
            shortcut="Ctrl + T",
            on_click=lambda e: self._on_blank_click(e),
        )

        self.card_youtube = WelcomeActionCard(
            icon=ft.Icons.SMART_DISPLAY_ROUNDED,
            title_key="welcome.btn_youtube",
            desc_key="welcome.desc_youtube",
            on_click=lambda e: self._on_youtube_click(e),
        )

        self.card_transcribe = WelcomeActionCard(
            icon=ft.Icons.MIC_ROUNDED,
            title_key="welcome.btn_transcribe",
            desc_key="welcome.desc_transcribe",
            on_click=lambda e: self._on_transcribe_click(e),
        )

        self.cards_list = [
            self.card_open_file,
            self.card_open_folder,
            self.card_blank,
            self.card_youtube,
            self.card_transcribe,
        ]

        # Bottom auxiliary action buttons
        self.btn_model_hub = ft.TextButton(
            t("welcome.btn_model_hub"),
            icon=ft.Icons.AUTO_AWESOME_MOSAIC_ROUNDED,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(left=6, top=4, right=6, bottom=4),
            ),
            on_click=self._on_model_hub_click,
        )

        self.btn_help = ft.TextButton(
            t("welcome.btn_help"),
            icon=ft.Icons.HELP_OUTLINE_ROUNDED,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(left=6, top=4, right=6, bottom=4),
            ),
            on_click=self._on_help_click,
        )

        self.btn_new_window = ft.TextButton(
            t("welcome.btn_new_window"),
            icon=ft.Icons.OPEN_IN_NEW_ROUNDED,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(left=6, top=4, right=6, bottom=4),
            ),
            on_click=self._on_new_window_click,
        )

        self.btn_return_editor = ft.TextButton(
            t("welcome.btn_return_editor"),
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=ft.Colors.PRIMARY,
            style=ft.ButtonStyle(
                color=ft.Colors.PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(left=6, top=4, right=6, bottom=4),
            ),
            on_click=lambda e: self.on_return_editor() if self.on_return_editor else None,
            visible=False,
        )

        self.left_col_content = ft.Column(
            controls=[
                header_row,
                ft.Container(height=2),
                ft.Column(
                    controls=[
                        self.card_open_file,
                        self.card_open_folder,
                        self.card_blank,
                        self.card_youtube,
                        self.card_transcribe,
                    ],
                    spacing=6,
                ),
                ft.Container(height=4),
                ft.Row(
                    controls=[self.btn_return_editor, self.btn_model_hub, self.btn_help, self.btn_new_window],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=4,
                    wrap=True,
                ),
            ],
            spacing=6,
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )

        self.left_column_container = ft.Container(
            content=self.left_col_content,
            width=360,
            expand=False,
        )

        # ── RIGHT COLUMN: Recent Files & Folders ─────────────────────────────
        self.recent_title_text = ft.Text(
            t("welcome.recent_title"),
            size=14,
            weight=ft.FontWeight.BOLD,
        )
        self.btn_clear_history = ft.TextButton(
            t("welcome.recent_clear_all"),
            icon=ft.Icons.DELETE_SWEEP_ROUNDED,
            icon_color=ft.Colors.OUTLINE,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(left=6, top=4, right=6, bottom=4),
            ),
            on_click=self._on_clear_history_click,
        )

        recent_header = ft.Row(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.HISTORY_ROUNDED, size=18, color=ft.Colors.PRIMARY),
                        self.recent_title_text,
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.btn_clear_history,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Search box
        self.search_field = ft.TextField(
            hint_text=t("welcome.recent_search_placeholder"),
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            dense=True,
            text_size=12,
            border_radius=8,
            content_padding=ft.Padding(left=8, top=6, right=8, bottom=6),
            on_change=self._on_search_change,
            expand=True,
        )

        # Filter Tabs (Segmented Buttons: All, Files, Folders)
        self.btn_filter_all = ft.OutlinedButton(
            t("welcome.recent_filter_all"),
            style=self._get_filter_btn_style("all"),
            on_click=lambda e: self._on_filter_click("all"),
        )
        self.btn_filter_files = ft.OutlinedButton(
            t("welcome.recent_filter_files"),
            style=self._get_filter_btn_style("files"),
            on_click=lambda e: self._on_filter_click("files"),
        )
        self.btn_filter_folders = ft.OutlinedButton(
            t("welcome.recent_filter_folders"),
            style=self._get_filter_btn_style("folders"),
            on_click=lambda e: self._on_filter_click("folders"),
        )

        self.filter_row = ft.Row(
            [
                self.search_field,
                self.btn_filter_all,
                self.btn_filter_files,
                self.btn_filter_folders,
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Recent list container
        self.recent_list_view = ft.ListView(
            spacing=5,
            expand=True,
            padding=ft.Padding(left=2, top=4, right=2, bottom=4),
        )

        self.empty_state_container = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.HISTORY_ROUNDED, size=40, color=ft.Colors.OUTLINE_VARIANT),
                    ft.Text(t("welcome.recent_empty"), size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.OUTLINE),
                    ft.Text(
                        t("welcome.recent_empty_desc"),
                        size=11,
                        color=ft.Colors.OUTLINE,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
            alignment=ft.alignment.Alignment(0.0, 0.0),
            expand=True,
            padding=ft.Padding(left=16, top=32, right=16, bottom=32),
        )

        self.recent_content_host = ft.Container(
            content=self.recent_list_view,
            expand=True,
        )

        self.right_column_content = ft.Column(
            controls=[
                recent_header,
                self.filter_row,
                ft.Container(
                    content=self.recent_content_host,
                    expand=True,
                    border_radius=8,
                ),
            ],
            spacing=8,
            expand=True,
        )

        self.right_column_container = ft.Container(
            content=self.right_column_content,
            expand=True,
        )

        # ── MAIN RESPONSIVE CONTAINERS ───────────────────────────────────────
        self.divider = ft.VerticalDivider(width=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT)
        self.horizontal_divider = ft.Divider(height=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT)

        self.main_row = ft.Row(
            controls=[self.left_column_container, self.divider, self.right_column_container],
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            expand=True,
        )

        self.stacked_column = ft.Column(
            controls=[
                self.left_column_container,
                self.horizontal_divider,
                self.right_column_container,
            ],
            spacing=12,
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )

        self.card_container = ft.Container(
            content=self.main_row,
            expand=True,
            padding=ft.Padding(left=20, top=16, right=20, bottom=16),
            border_radius=16,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border=ft.Border(
                left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            ),
        )

        self.content = self.card_container

        # Initial data hydration
        self.refresh_history(silent=True)

    def update_responsive_layout(self, width: int, height: int = 0):
        """Switches between 2-column side-by-side and stacked vertical layout dynamically."""
        is_compact = width < 780
        if is_compact != self._is_compact_layout:
            self._is_compact_layout = is_compact
            if is_compact:
                self.left_column_container.width = None
                self.left_column_container.expand = False
                self.card_container.content = self.stacked_column
            else:
                self.left_column_container.width = 360
                self.left_column_container.expand = False
                self.card_container.content = self.main_row
            try:
                if self.page:
                    self.update()
            except Exception:
                pass

    def _get_filter_btn_style(self, filter_type: str) -> ft.ButtonStyle:
        is_active = self.current_filter == filter_type
        return ft.ButtonStyle(
            bgcolor=ft.Colors.PRIMARY_CONTAINER if is_active else ft.Colors.TRANSPARENT,
            color=ft.Colors.ON_PRIMARY_CONTAINER if is_active else ft.Colors.ON_SURFACE,
            shape=ft.RoundedRectangleBorder(radius=6),
            padding=ft.Padding(left=8, top=4, right=8, bottom=4),
            side=ft.BorderSide(1, ft.Colors.PRIMARY if is_active else ft.Colors.OUTLINE_VARIANT),
        )

    def _update_filter_buttons(self):
        self.btn_filter_all.style = self._get_filter_btn_style("all")
        self.btn_filter_files.style = self._get_filter_btn_style("files")
        self.btn_filter_folders.style = self._get_filter_btn_style("folders")

    def _on_filter_click(self, filter_type: str):
        self.current_filter = filter_type
        self._update_filter_buttons()
        self.refresh_history()

    def _on_search_change(self, e):
        self.search_query = e.data or ""
        self.refresh_history()

    def refresh_history(self, silent: bool = False):
        """Re-reads history items from HistoryService and rebuilds the recent list."""
        items = self.history_service.get_items(filter_type=self.current_filter, query=self.search_query)
        self.recent_list_view.controls.clear()

        if not items:
            self.recent_content_host.content = self.empty_state_container
        else:
            for item in items:
                tile = RecentItemTile(
                    item=item,
                    on_open=self._on_recent_item_open,
                    on_remove=self._on_recent_item_remove,
                    on_toggle_pin=self._on_recent_item_toggle_pin,
                )
                self.recent_list_view.controls.append(tile)
            self.recent_content_host.content = self.recent_list_view

        if not silent:
            try:
                if self.page:
                    self.update()
            except Exception:
                pass

    def _on_recent_item_open(self, path: str, item_type: str):
        if item_type == "folder":
            if self.on_open_recent_folder:
                self.on_open_recent_folder(path)
        else:
            if self.on_open_recent_file:
                self.on_open_recent_file(path)

    def _on_recent_item_remove(self, path: str, item_type: str):
        self.history_service.remove_item(path, item_type)
        self.refresh_history()

    def _on_recent_item_toggle_pin(self, path: str, item_type: str):
        self.history_service.toggle_pin(path, item_type)
        self.refresh_history()

    def _on_clear_history_click(self, e):
        self.history_service.clear_all(self.current_filter)
        self.refresh_history()

    def _on_open_click(self, e):
        if self.on_open_file:
            self.on_open_file(e)

    def _on_open_folder_click(self, e):
        if self.on_open_folder:
            self.on_open_folder(e)

    def _on_blank_click(self, e):
        if self.on_create_blank:
            self.on_create_blank(e)

    def _on_youtube_click(self, e):
        if self.on_import_youtube:
            self.on_import_youtube(e)

    def _on_transcribe_click(self, e):
        if self.on_transcribe_media:
            self.on_transcribe_media(e)

    def _on_model_hub_click(self, e):
        if self.on_open_model_hub:
            self.on_open_model_hub(e)

    def _on_help_click(self, e):
        if self.on_open_help:
            self.on_open_help(e)

    def _on_new_window_click(self, e):
        if self.on_new_window:
            self.on_new_window()

    def set_has_open_tabs(self, has_open: bool):
        """Shows or hides the Back to Editor button based on active tabs."""
        self.btn_return_editor.visible = has_open
        try:
            if self.page:
                self.btn_return_editor.update()
        except Exception:
            pass

    def update_locale(self):
        """Refresh all text to current locale."""
        self.title_text.value = t("welcome.title")
        self.subtitle_text.value = t("welcome.subtitle")
        self.btn_return_editor.text = t("welcome.btn_return_editor")
        self.btn_help.content = t("welcome.btn_help")
        self.btn_model_hub.content = t("welcome.btn_model_hub")
        self.btn_new_window.content = t("welcome.btn_new_window")
        self.recent_title_text.value = t("welcome.recent_title")
        self.btn_clear_history.content = t("welcome.recent_clear_all")
        self.search_field.hint_text = t("welcome.recent_search_placeholder")
        self.btn_filter_all.text = t("welcome.recent_filter_all")
        self.btn_filter_files.text = t("welcome.recent_filter_files")
        self.btn_filter_folders.text = t("welcome.recent_filter_folders")

        for card in self.cards_list:
            card.update_locale()

        self.refresh_history(silent=True)
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def apply_palette(self, palette: dict, is_dark: bool):
        accent_primary = resolve_color(palette, "text_accent_primary", is_dark)
        bg_component = resolve_color(palette, "bg_component", is_dark)
        border_color = resolve_color(palette, "border_color", is_dark)

        self.icon_logo.color = accent_primary
        self.btn_help.color = accent_primary
        self.btn_model_hub.color = accent_primary
        self.btn_new_window.color = accent_primary

        for card in self.cards_list:
            card.apply_palette(accent_primary)

        self.card_container.bgcolor = bg_component
        self.card_container.border = make_border(1, border_color)

        self.refresh_history(silent=True)
        try:
            if self.page:
                self.update()
        except Exception:
            pass
