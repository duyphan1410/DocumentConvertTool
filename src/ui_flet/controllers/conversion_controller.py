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


from src.ui_flet.native_dialogs import confirm_overwrite_async


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

        task = asyncio.create_task(self._async_check_overwrite_and_convert(out_path))
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)

    async def _async_check_overwrite_and_convert(self, out_path: str):
        if os.path.exists(out_path):
            confirmed = await confirm_overwrite_async(out_path)
            if not confirmed:
                self.footer_bar.set_status("Conversion cancelled", ft.Colors.AMBER_400)
                self.page.update()
                return

        if is_output_locked(out_path):
            self.footer_bar.set_status(
                "Output file locked by another application! Close target file and try again.", ft.Colors.RED_400
            )
            self.page.update()
            return

        self.state.is_processing = True
        self.footer_bar.set_processing(True)
        self.footer_bar.set_status("Converting...", ft.Colors.AMBER_400)
        self.page.update()

        await self._async_run_conversion_worker(out_path)

    async def confirm_overwrite_dialog(self, out_path: str) -> bool:
        file_name = os.path.basename(out_path)
        loop = asyncio.get_running_loop()
        fut = loop.create_future()

        def _close(result: bool):
            try:
                self.page.close(dlg)
            except Exception:
                pass
            if not fut.done():
                fut.set_result(result)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.AMBER_400, size=28
                    ),
                    ft.Text("Confirm File Overwrite", weight=ft.FontWeight.BOLD, size=18),
                ],
                spacing=10,
            ),
            content=ft.Column(
                [
                    ft.Text(f"The target file '{file_name}' already exists at destination:"),
                    ft.Container(
                        content=ft.Text(
                            out_path, size=12, color=ft.Colors.PRIMARY, selectable=True
                        ),
                        padding=10,
                        border_radius=6,
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    ),
                    ft.Text("Do you want to overwrite it?", weight=ft.FontWeight.W_500),
                ],
                tight=True,
                spacing=12,
            ),
            actions=[
                ft.OutlinedButton("Cancel", on_click=lambda e: _close(False)),
                ft.ElevatedButton(
                    "Overwrite",
                    icon=ft.Icons.DELETE_SWEEP_OUTLINED,
                    bgcolor=ft.Colors.RED_700,
                    color=ft.Colors.WHITE,
                    on_click=lambda e: _close(True),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.open(dlg)
        await asyncio.sleep(0.05)
        return await fut

    async def _async_run_conversion_worker(self, out_path: str):
        t0 = time.time()
        try:
            content = self.editor_view.get_text()
            mode = self.state.current_mode
            msg = await asyncio.to_thread(convert_content, mode, content, out_path)
            duration = time.time() - t0

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
            print(f"[DEBUG] Conversion error: {err_msg}")
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
