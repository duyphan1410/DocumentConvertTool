"""
Conversion Controller for Flet UI.
Decouples conversion execution, overwrite confirmation dialogs, and result file/folder launches.
"""
import os
import time
import asyncio
import flet as ft

from src.services.conversion_service import convert_content, is_output_locked
from src.utils.env import open_file_or_folder_foreground
from src.ui_flet.state import AppState


from src.ui_flet.constants import MODES


from src.ui_flet.theme import PALETTES, resolve_color, get_style_color, make_border


class ConversionController:
    def __init__(self, page: ft.Page, state: AppState, app_controls: dict):
        self.page = page
        self.state = state
        self.editor_view = app_controls["editor_view"]
        self.file_path_bar = app_controls["file_path_bar"]
        self.footer_bar = app_controls["footer_bar"]
        self._active_tasks = set()

    def on_convert_clicked(self, e=None):
        content = self.editor_view.get_text()
        if not content or not content.strip():
            self.footer_bar.set_status(
                "Editor content is empty! Please type or load a document.",
                ft.Colors.RED_400,
            )
            return

        out_path = self.file_path_bar.out_path_text.value.strip()
        if not out_path:
            # Fallback default output path for draft or blank note
            mode_cfg = MODES.get(self.state.current_mode, MODES["MD -> Excel"])
            out_ext = mode_cfg.get("out_ext", ".xlsx")
            out_path = os.path.abspath(f"output{out_ext}")
            self.state.out_path = out_path
            self.file_path_bar.set_out_path(out_path)

        out_path = os.path.normpath(out_path)

        task = asyncio.create_task(self._async_check_file_and_convert(out_path))
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)

    async def _async_check_file_and_convert(self, out_path: str):
        if os.path.exists(out_path):
            # Reveal File Path Bar if hidden so user can inspect or change destination path
            if not self.file_path_bar.container.visible:
                self.file_path_bar.container.visible = True
                try:
                    self.file_path_bar.container.update()
                except Exception:
                    pass

            locked = await asyncio.to_thread(is_output_locked, out_path)
            if locked:
                file_name = os.path.basename(out_path)
                self.footer_bar.set_status(
                    f"Cannot overwrite! File '{file_name}' is currently open in another program. Please close the file and try again.",
                    ft.Colors.RED_400,
                )
                self.page.update()
                return
            self.show_overwrite_confirmation_dialog(
                out_path,
                on_confirm_callback=lambda: self.start_conversion_process(out_path),
            )
            return

        self.start_conversion_process(out_path)

    def show_overwrite_confirmation_dialog(self, out_path: str, on_confirm_callback):
        """Shows a Flet AlertDialog styled with current palette for file overwrite confirmation."""
        # Clean up any previously unmounted AlertDialog instances from overlay list to prevent memory leaks
        self.page.overlay[:] = [
            c for c in self.page.overlay if not isinstance(c, ft.AlertDialog)
        ]

        print(
            f"[DEBUG] [BEFORE POPUP] Target file exists at '{out_path}'. Preparing Theme Overwrite Modal..."
        )
        palette = PALETTES.get(
            self.state.current_palette, PALETTES.get("Violet Cyberpunk", {})
        )
        is_dark = self.page.theme_mode != ft.ThemeMode.LIGHT

        bg_card = resolve_color(palette, "bg_component", is_dark)
        bg_pill = resolve_color(palette, "bg_header", is_dark)
        accent_color = resolve_color(palette, "text_accent_secondary", is_dark)
        text_primary = get_style_color("text_primary", is_dark)
        text_secondary = get_style_color("text_secondary", is_dark)
        border_color = resolve_color(palette, "border_color", is_dark)

        file_name = os.path.basename(out_path)

        def close_dialog(e, confirmed: bool):
            print(f"[DEBUG] Closing overwrite dialog, confirmed={confirmed}")
            dialog.open = False
            self.page.update()

            if confirmed:
                on_confirm_callback()
            else:
                self.footer_bar.set_status(
                    "Conversion cancelled: File overwrite rejected.",
                    ft.Colors.AMBER_400,
                )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.WARNING_ROUNDED, color=ft.Colors.AMBER_400, size=24
                    ),
                    ft.Text(
                        "Confirm File Overwrite",
                        weight=ft.FontWeight.BOLD,
                        size=18,
                        color=text_primary,
                    ),
                ],
                spacing=10,
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "The target output file already exists on disk:",
                            size=13,
                            color=text_secondary,
                        ),
                        ft.Container(
                            content=ft.Text(
                                file_name,
                                weight=ft.FontWeight.W_600,
                                size=13,
                                color=accent_color,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            padding=10,
                            bgcolor=bg_pill,
                            border_radius=6,
                            border=make_border(1, border_color),
                        ),
                        ft.Text(
                            "Do you want to overwrite and replace this file?",
                            size=13,
                            color=text_secondary,
                        ),
                    ],
                    tight=True,
                    spacing=12,
                ),
                width=420,
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda e: close_dialog(e, False),
                    style=ft.ButtonStyle(color=text_secondary),
                ),
                ft.Button(
                    "Overwrite / Replace",
                    icon=ft.Icons.AUTORENEW_ROUNDED,
                    on_click=lambda e: close_dialog(e, True),
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        bgcolor=ft.Colors.RED_600,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=bg_card,
            shape=ft.RoundedRectangleBorder(radius=10),
        )

        if dialog not in self.page.overlay:
            self.page.overlay.append(dialog)
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
        print("[DEBUG] Overwrite dialog opened")

    def start_conversion_process(self, out_path: str):
        task = asyncio.create_task(self._async_run_conversion_worker(out_path))
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)

    async def _async_run_conversion_worker(self, out_path: str):
        t0 = time.time()
        try:
            content = self.editor_view.get_text()
            mode = self.state.current_mode
            msg = await asyncio.to_thread(convert_content, mode, content, out_path)
            duration = time.time() - t0
            timestamp = time.strftime("%H:%M:%S")
            print(f"[LOG][SAVE/CONVERT][{timestamp}] {msg} ({duration:.2f}s) -> {out_path}")

            self.state.last_converted_path = out_path
            self.state.is_processing = False
            self.footer_bar.set_processing(False)
            self.footer_bar.set_result_buttons_visible(True)
            self.footer_bar.set_status(
                f"{msg} ({duration:.2f}s)", ft.Colors.GREEN_400
            )
            self.page.update()
        except Exception as ex:
            err_msg = str(ex)
            timestamp = time.strftime("%H:%M:%S")
            print(f"[LOG][SAVE/CONVERT][ERROR][{timestamp}] Conversion failed: {err_msg}")
            self.state.is_processing = False
            self.footer_bar.set_processing(False)
            self.footer_bar.set_status(
                f"Conversion failed: {err_msg}", ft.Colors.RED_400
            )
            self.page.update()

    def open_converted_file(self, e=None):
        if self.state.last_converted_path and os.path.exists(
            self.state.last_converted_path
        ):
            file_path = os.path.normpath(
                os.path.abspath(self.state.last_converted_path)
            )
            try:
                open_file_or_folder_foreground(file_path, is_folder=False)
            except Exception as ex:
                print(f"[DEBUG] Failed to open file '{file_path}': {ex}")

    def open_converted_folder(self, e=None):
        if self.state.last_converted_path and os.path.exists(
            self.state.last_converted_path
        ):
            file_path = os.path.normpath(
                os.path.abspath(self.state.last_converted_path)
            )
            try:
                open_file_or_folder_foreground(file_path, is_folder=True)
            except Exception as ex:
                print(f"[DEBUG] Failed to open folder for '{file_path}': {ex}")
