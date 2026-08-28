"""
Modal Dialogs for Explorer File Operations: Rename, Safe Delete, and New File/Folder.
Guarantees clean validation, Windows reserved names protection, dark/light theme consistency,
and 100% i18n localization. Follows the repository standard AlertDialog lifecycle.
"""
from __future__ import annotations

import os
import flet as ft
from typing import Callable, Optional

from src.i18n import t
from src.utils.file_ops import sanitize_filename


def show_rename_dialog(
    page: ft.Page,
    current_path: str,
    on_confirmed: Callable[[str, str], None],
):
    """
    Displays a modal dialog to rename a file or folder.
    Dismissible by clicking outside or pressing Escape.
    """
    # Clean up previous unmounted dialogs
    page.overlay[:] = [c for c in page.overlay if not isinstance(c, ft.AlertDialog)]

    old_name = os.path.basename(current_path)

    error_text = ft.Text(
        value="",
        size=11,
        color=ft.Colors.RED_400,
        visible=False,
    )

    name_field = ft.TextField(
        value=old_name,
        text_size=13,
        autofocus=True,
        dense=True,
        border_radius=8,
        content_padding=ft.Padding(10, 8, 10, 8),
    )

    def close_dialog(e=None):
        dlg.open = False
        page.update()

    def validate_and_submit(e=None):
        new_name = name_field.value.strip()
        if new_name == old_name:
            close_dialog()
            return

        is_valid, msg = sanitize_filename(new_name)
        if not is_valid:
            error_text.value = msg
            error_text.visible = True
            page.update()
            return

        target_dir = os.path.dirname(current_path)
        new_full_path = os.path.join(target_dir, new_name)
        is_case_only_rename = (new_name.lower() == old_name.lower())
        if not is_case_only_rename and os.path.exists(new_full_path):
            error_text.value = t("explorer.file_already_exists", name=new_name)
            error_text.visible = True
            page.update()
            return

        close_dialog()
        on_confirmed(current_path, new_name)

    name_field.on_submit = validate_and_submit

    dlg = ft.AlertDialog(
        modal=False,
        on_dismiss=close_dialog,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.EDIT_ROUNDED, size=20, color=ft.Colors.PRIMARY),
                ft.Text(t("explorer.rename_title"), size=15, weight=ft.FontWeight.W_600),
            ],
            spacing=8,
        ),
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        t("explorer.rename_prompt") + f"'{old_name}'",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    name_field,
                    error_text,
                ],
                spacing=8,
                tight=True,
            ),
            width=360,
        ),
        actions=[
            ft.TextButton(
                t("dialog.btn_cancel"),
                on_click=close_dialog,
            ),
            ft.ElevatedButton(
                t("dialog.btn_save"),
                icon=ft.Icons.CHECK_ROUNDED,
                on_click=validate_and_submit,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(dlg)
    dlg.open = True
    page.update()


def show_safe_delete_dialog(
    page: ft.Page,
    target_path: str,
    is_active: bool,
    is_dirty: bool,
    on_confirmed: Callable[[str], None],
):
    """
    Displays a confirmation modal to move a file/folder to the Recycle Bin.
    Dismissible by clicking outside or pressing Escape.
    """
    # Clean up previous unmounted dialogs
    page.overlay[:] = [c for c in page.overlay if not isinstance(c, ft.AlertDialog)]

    name = os.path.basename(target_path)
    is_dir = os.path.isdir(target_path)

    def close_dialog(e=None):
        dlg.open = False
        page.update()

    def do_delete(e=None):
        close_dialog()
        on_confirmed(target_path)

    warning_controls = []
    if is_dirty and is_active:
        warning_controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=18, color=ft.Colors.AMBER_400),
                        ft.Text(
                            t("explorer.delete_unsaved_warning"),
                            size=12,
                            color=ft.Colors.AMBER_400,
                            weight=ft.FontWeight.W_500,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
                padding=ft.Padding(8, 6, 8, 6),
                border_radius=6,
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.AMBER_400),
            )
        )

    confirm_msg = (
        t("explorer.delete_confirm_folder", name=name)
        if is_dir
        else t("explorer.delete_confirm_file", name=name)
    )

    warning_controls.append(
        ft.Text(
            confirm_msg,
            size=13,
            color=ft.Colors.ON_SURFACE,
        )
    )

    dlg = ft.AlertDialog(
        modal=False,
        on_dismiss=close_dialog,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, size=22, color=ft.Colors.RED_400),
                ft.Text(t("explorer.delete_title"), size=15, weight=ft.FontWeight.W_600),
            ],
            spacing=8,
        ),
        content=ft.Container(
            content=ft.Column(
                warning_controls,
                spacing=10,
                tight=True,
            ),
            width=380,
        ),
        actions=[
            ft.TextButton(
                t("dialog.btn_cancel"),
                on_click=close_dialog,
            ),
            ft.ElevatedButton(
                t("explorer.move_to_trash"),
                icon=ft.Icons.DELETE_SWEEP_ROUNDED,
                bgcolor=ft.Colors.RED_700,
                color=ft.Colors.WHITE,
                on_click=do_delete,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(dlg)
    dlg.open = True
    page.update()


def show_new_entry_dialog(
    page: ft.Page,
    target_dir: str,
    is_folder: bool,
    on_confirmed: Callable[[str, str, bool], None],
):
    """
    Displays a modal dialog to create a new Markdown file or subfolder.
    Dismissible by clicking outside or pressing Escape.
    """
    # Clean up previous unmounted dialogs
    page.overlay[:] = [c for c in page.overlay if not isinstance(c, ft.AlertDialog)]

    default_name = "new_folder" if is_folder else "untitled.md"
    title_str = t("explorer.new_folder_title") if is_folder else t("explorer.new_file_title")
    icon_obj = ft.Icons.CREATE_NEW_FOLDER_ROUNDED if is_folder else ft.Icons.NOTE_ADD_ROUNDED

    error_text = ft.Text(
        value="",
        size=11,
        color=ft.Colors.RED_400,
        visible=False,
    )

    name_field = ft.TextField(
        value=default_name,
        text_size=13,
        autofocus=True,
        dense=True,
        border_radius=8,
        content_padding=ft.Padding(10, 8, 10, 8),
    )

    def close_dialog(e=None):
        dlg.open = False
        page.update()

    def validate_and_create(e=None):
        name = name_field.value.strip()
        if not is_folder and not os.path.splitext(name)[1]:
            name += ".md"

        is_valid, msg = sanitize_filename(name)
        if not is_valid:
            error_text.value = msg
            error_text.visible = True
            page.update()
            return

        new_full_path = os.path.join(target_dir, name)
        if os.path.exists(new_full_path):
            error_text.value = t("explorer.file_already_exists", name=name)
            error_text.visible = True
            page.update()
            return

        close_dialog()
        on_confirmed(target_dir, name, is_folder)

    name_field.on_submit = validate_and_create

    dlg = ft.AlertDialog(
        modal=False,
        on_dismiss=close_dialog,
        title=ft.Row(
            [
                ft.Icon(icon_obj, size=20, color=ft.Colors.PRIMARY),
                ft.Text(title_str, size=15, weight=ft.FontWeight.W_600),
            ],
            spacing=8,
        ),
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        t("explorer.create_inside") + f"{os.path.basename(target_dir) or target_dir}",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    name_field,
                    error_text,
                ],
                spacing=8,
                tight=True,
            ),
            width=360,
        ),
        actions=[
            ft.TextButton(
                t("dialog.btn_cancel"),
                on_click=close_dialog,
            ),
            ft.ElevatedButton(
                t("dialog.btn_create"),
                icon=ft.Icons.CHECK_ROUNDED,
                on_click=validate_and_create,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(dlg)
    dlg.open = True
    page.update()


def show_unsaved_tab_dialog(
    page: ft.Page,
    tab_title: str,
    on_save: Callable[[], None],
    on_discard: Callable[[], None],
    on_cancel: Optional[Callable[[], None]] = None,
):
    """
    Displays confirmation dialog when attempting to close an unsaved or orphaned document tab.
    Provides Save, Discard, and Cancel actions with clean i18n support.
    Dismissible by clicking outside (modal=False) or pressing Escape.
    """
    page.overlay[:] = [c for c in page.overlay if not isinstance(c, ft.AlertDialog)]

    def close_dialog(e=None):
        dlg.open = False
        page.update()
        if on_cancel:
            on_cancel()

    def handle_discard(e=None):
        dlg.open = False
        page.update()
        on_discard()

    def handle_save(e=None):
        dlg.open = False
        page.update()
        on_save()

    dlg = ft.AlertDialog(
        modal=False,
        on_dismiss=close_dialog,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=20, color=ft.Colors.AMBER_400),
                ft.Text(t("dialog.unsaved_tab_title"), size=15, weight=ft.FontWeight.W_600),
            ],
            spacing=8,
        ),
        content=ft.Container(
            content=ft.Text(
                t("dialog.unsaved_tab_message", title=tab_title),
                size=13,
                color=ft.Colors.ON_SURFACE,
            ),
            width=380,
        ),
        actions=[
            ft.TextButton(
                t("dialog.btn_cancel"),
                on_click=close_dialog,
            ),
            ft.TextButton(
                t("dialog.btn_discard"),
                style=ft.ButtonStyle(color=ft.Colors.RED_400),
                on_click=handle_discard,
            ),
            ft.ElevatedButton(
                t("dialog.btn_save"),
                icon=ft.Icons.SAVE_OUTLINED,
                on_click=handle_save,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(dlg)
    dlg.open = True
    page.update()

