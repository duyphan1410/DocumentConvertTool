import flet as ft
from typing import Union, Optional

from src.core.errors import DocumentError, ErrorCode
from src.utils.logger import log_error
from src.utils.clipboard import set_clipboard_text
from src.ui_flet.theme import PALETTES, resolve_color, get_style_color
from src.i18n import t


class DialogType:
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    SUCCESS = "success"


def show_message_dialog(
    page: ft.Page,
    payload: Union[DocumentError, str],
    title: Optional[str] = None,
    dialog_type: str = DialogType.ERROR,
):
    """
    Displays a modern, theme-aware, production-grade unified MessageDialog.
    Automatically logs DocumentErrors to persistent log file.
    """
    # Clean up previous unmounted dialogs from overlay list
    page.overlay[:] = [c for c in page.overlay if not isinstance(c, ft.AlertDialog)]

    # Normalize payload into DocumentError
    if isinstance(payload, DocumentError):
        doc_err = payload
        log_error(doc_err)
    else:
        doc_err = DocumentError(
            code=ErrorCode.UNKNOWN_ERROR if dialog_type == DialogType.ERROR else ErrorCode.FILE_EMPTY,
            title=title or (t("dialog.info_title_default") if dialog_type == DialogType.INFO else t("dialog.error_title_default")),
            message=str(payload),
        )

    # Determine Theme Colors
    is_dark = page.theme_mode != ft.ThemeMode.LIGHT
    palette = PALETTES.get("Violet Cyberpunk", {})

    text_primary = get_style_color("text_primary", is_dark)
    text_secondary = get_style_color("text_secondary", is_dark)

    if dialog_type == DialogType.ERROR:
        icon_data = ft.Icons.ERROR_ROUNDED
        accent_color = ft.Colors.RED_400
    elif dialog_type == DialogType.WARNING:
        icon_data = ft.Icons.WARNING_ROUNDED
        accent_color = ft.Colors.AMBER_400
    elif dialog_type == DialogType.SUCCESS:
        icon_data = ft.Icons.CHECK_CIRCLE_ROUNDED
        accent_color = ft.Colors.GREEN_400
    else:
        icon_data = ft.Icons.INFO_ROUNDED
        accent_color = ft.Colors.BLUE_400

    # Build Content Components
    content_controls = []

    # 1. Message Description
    content_controls.append(
        ft.Text(
            doc_err.message,
            size=14,
            color=text_primary,
            weight=ft.FontWeight.W_500,
        )
    )

    # 2. Actionable Suggestion Box
    if doc_err.suggestion:
        content_controls.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.LIGHTBULB_OUTLINED, color=ft.Colors.AMBER_400, size=18),
                        ft.Text(
                            doc_err.suggestion,
                            size=13,
                            color=text_secondary,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                    alignment=ft.MainAxisAlignment.START,
                ),
                padding=10,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.1, accent_color),
            )
        )

    # 3. Pip Install Command Box (if present)
    if doc_err.install_command:
        def copy_cmd(e):
            set_clipboard_text(doc_err.install_command, page=page)
            try:
                snack = ft.SnackBar(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                            ft.Text(t("dialog.install_cmd_copied_toast", command=doc_err.install_command), color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
                        ],
                        spacing=8,
                    ),
                    bgcolor=ft.Colors.GREEN_700,
                    duration=3000,
                )
                page.snack_bar = snack
                snack.open = True
            except Exception as ex_snack:
                print(f"[DEBUG] SnackBar display error: {ex_snack}")
            dialog.open = False
            page.update()

        content_controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(t("dialog.install_cmd_label"), size=12, weight=ft.FontWeight.BOLD, color=text_primary),
                        ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Text(
                                        doc_err.install_command,
                                        size=12,
                                        font_family="Consolas, monospace",
                                        color=ft.Colors.GREEN_300 if is_dark else ft.Colors.GREEN_800,
                                    ),
                                    padding=8,
                                    bgcolor=ft.Colors.BLACK54 if is_dark else ft.Colors.GREY_200,
                                    border_radius=6,
                                    expand=True,
                                 ),
                                ft.IconButton(
                                    icon=ft.Icons.COPY_ROUNDED,
                                    tooltip=t("dialog.install_cmd_copy_tooltip"),
                                    icon_color=accent_color,
                                    on_click=copy_cmd,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        )
                    ],
                    spacing=6,
                ),
                margin=ft.Margin(0, 4, 0, 4),
            )
        )

    # 4. Error ID & Technical Detail Section
    if doc_err.detail:
        detail_container = ft.Container(
            content=ft.TextField(
                value=doc_err.to_log_string(),
                multiline=True,
                read_only=True,
                min_lines=4,
                max_lines=8,
                text_size=11,
                text_style=ft.TextStyle(font_family="Consolas, monospace"),
            ),
            visible=False,
            margin=ft.Margin(0, 6, 0, 0),
        )

        def toggle_details(e):
            detail_container.visible = not detail_container.visible
            toggle_btn.content = ft.Text("Technical Details" if detail_container.visible else "Technical Details")
            dialog.update()

        toggle_btn = ft.TextButton(
            content=ft.Text("Technical Details"),
            icon=ft.Icons.CODE_ROUNDED,
            style=ft.ButtonStyle(color=text_secondary),
            on_click=toggle_details,
        )

        content_controls.append(toggle_btn)
        content_controls.append(detail_container)

    def close_dialog(e):
        dialog.open = False
        page.update()

    def copy_full_log(e):
        set_clipboard_text(doc_err.to_log_string(), page=page)
        try:
            snack = ft.SnackBar(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                        ft.Text(t("dialog.details_copied_toast"), color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
                    ],
                    spacing=8,
                ),
                bgcolor=ft.Colors.GREEN_700,
                duration=3000,
            )
            page.snack_bar = snack
            snack.open = True
        except Exception as ex_snack:
            print(f"[DEBUG] SnackBar display error: {ex_snack}")
        dialog.open = False
        page.update()

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Icon(icon_data, color=accent_color, size=28),
                ft.Text(
                    doc_err.title,
                    weight=ft.FontWeight.BOLD,
                    size=18,
                    color=text_primary,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    expand=True,
                ),
            ],
            spacing=10,
        ),
        content=ft.Container(
            content=ft.Column(
                controls=content_controls,
                tight=True,
                spacing=10,
            ),
            width=500,
            padding=10,
        ),
        actions=[
            ft.TextButton(
                t("dialog.btn_copy_details"),
                icon=ft.Icons.COPY_ALL_ROUNDED,
                on_click=copy_full_log,
            ),
            ft.ElevatedButton(
                t("dialog.btn_close"),
                on_click=close_dialog,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=6),
                ),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(dialog)
    dialog.open = True
    page.update()
