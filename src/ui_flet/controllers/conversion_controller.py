"""
Conversion Controller for Flet UI.
Decouples conversion execution, overwrite confirmation dialogs, and result file/folder launches.
"""
import os
import time
import asyncio
import flet as ft

from src.i18n import t

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
            self.footer_bar.set_status_key(
                "status.empty_editor",
                color=ft.Colors.RED_400,
                is_error=True,
            )
            return

        out_path = self.file_path_bar.out_path_text.value.strip()
        mode_cfg = MODES.get(self.state.current_mode, MODES["MD -> PDF"])
        expected_ext = mode_cfg.get("out_ext", ".pdf")

        if not out_path:
            # Fallback default output path for draft or blank note
            out_path = os.path.abspath(f"output{expected_ext}")
            self.state.out_path = out_path
            self.file_path_bar.set_out_path(out_path)
        else:
            base, cur_ext = os.path.splitext(out_path)
            if expected_ext and cur_ext.lower() != expected_ext.lower():
                out_path = f"{base}{expected_ext}"
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
                self.footer_bar.set_status_key(
                    "status.file_locked",
                    color=ft.Colors.RED_400,
                    filename=file_name,
                    is_error=True,
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

        # 1-Click Smart Auto-Rename unique path calculation
        base_dir, orig_name = os.path.split(out_path)
        name_no_ext, ext = os.path.splitext(orig_name)
        counter = 1
        new_path = os.path.join(base_dir, f"{name_no_ext}_{counter}{ext}")
        while os.path.exists(new_path):
            counter += 1
            new_path = os.path.join(base_dir, f"{name_no_ext}_{counter}{ext}")
        new_filename = os.path.basename(new_path)

        # Reset selection state when dialog opens
        self.file_path_bar.out_path_text.selection = None

        def handle_cancel(e):
            print(f"[DEBUG] Overwrite canceled by user.")
            dialog.open = False
            self.footer_bar.set_status_key(
                "status.conversion_cancelled",
                color=ft.Colors.AMBER_400,
            )
            # Ensure File Path Bar is visible & focus on output path field for easy manual editing
            if not self.file_path_bar.container.visible:
                self.file_path_bar.container.visible = True

            val = self.file_path_bar.out_path_text.value or ""
            try:
                if val:
                    base_dir, filename = os.path.split(val)
                    name_no_ext, ext = os.path.splitext(filename)
                    start_idx = len(base_dir) + (1 if base_dir and not base_dir.endswith(os.sep) and not base_dir.endswith("/") else 0)
                    end_idx = start_idx + len(name_no_ext)
                    # Reset selection to None first so Flet property diff engine ALWAYS detects selection property change
                    self.file_path_bar.out_path_text.selection = None
                    try:
                        self.file_path_bar.out_path_text.update()
                    except Exception:
                        pass
                    self.file_path_bar.out_path_text.selection = ft.TextSelection(start_idx, end_idx)
            except Exception as sel_ex:
                print(f"[DEBUG] TextSelection error: {sel_ex}")
            self.page.update()

            try:
                asyncio.create_task(self.file_path_bar.out_path_text.focus())
            except Exception as ex:
                print(f"[DEBUG] Failed to focus out_path_text: {ex}")

        def handle_save_new(e):
            print(f"[DEBUG] 1-Click Save as New selected: '{new_path}'")
            dialog.open = False
            self.state.out_path = new_path
            self.file_path_bar.set_out_path(new_path)
            self.page.update()
            self.start_conversion_process(new_path)

        def handle_overwrite(e):
            print(f"[DEBUG] Overwrite confirmed for target file: '{out_path}'")
            dialog.open = False
            self.page.update()
            on_confirm_callback()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.WARNING_ROUNDED, color=ft.Colors.AMBER_400, size=24
                    ),
                    ft.Text(
                        t("dialog.overwrite_title"),
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
                            t("dialog.overwrite_exists"),
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
                            t("dialog.overwrite_confirm"),
                            size=13,
                            color=text_secondary,
                        ),
                    ],
                    tight=True,
                    spacing=12,
                ),
                width=460,
            ),
            actions=[
                ft.TextButton(
                    t("dialog.btn_cancel"),
                    on_click=handle_cancel,
                    style=ft.ButtonStyle(color=text_secondary),
                ),
                ft.OutlinedButton(
                    t("dialog.btn_save_new", filename=new_filename),
                    icon=ft.Icons.COPY_ROUNDED,
                    on_click=handle_save_new,
                    style=ft.ButtonStyle(color=accent_color),
                ),
                ft.Button(
                    t("dialog.overwrite_btn"),
                    icon=ft.Icons.AUTORENEW_ROUNDED,
                    on_click=handle_overwrite,
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
        self.state.is_processing = True
        self.footer_bar.set_processing(True)
        self.footer_bar.set_result_buttons_visible(False)
        self.footer_bar.set_status_key(
            "status.converting",
            color=ft.Colors.AMBER_400,
        )
        self.page.update()

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
            self.footer_bar.set_status_key(
                "status.conversion_success",
                color=ft.Colors.GREEN_400,
                message=msg,
                duration=f"{duration:.2f}",
            )

            # Play completion chime sound on Windows
            if os.name == "nt":
                try:
                    import winsound
                    winsound.MessageBeep(winsound.MB_OK)
                except Exception:
                    pass

            # Display a clean SnackBar notification popup
            try:
                snack = ft.SnackBar(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE),
                            ft.Text(f"{msg} ({duration:.2f}s)", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
                        ],
                        spacing=8,
                    ),
                    bgcolor=ft.Colors.GREEN_700,
                    duration=3500,
                )
                self.page.snack_bar = snack
                self.page.snack_bar.open = True
            except Exception as ex_snack:
                print(f"[DEBUG] SnackBar error: {ex_snack}")

            self.page.update()
        except Exception as ex:
            from src.core.error_mapper import ErrorMapper
            from src.ui_flet.components.message_dialog import show_message_dialog

            doc_err = ErrorMapper.map_exception(ex, context_path=out_path, stage="write")
            timestamp = time.strftime("%H:%M:%S")
            print(f"[LOG][SAVE/CONVERT][ERROR][{timestamp}] Conversion failed: {doc_err.to_log_string()}")

            self.state.is_processing = False
            self.footer_bar.set_processing(False)
            self.footer_bar.set_status_key(
                "status.conversion_failed",
                color=ft.Colors.RED_400,
                doc_err=doc_err,
                is_error=True,
            )

            # Play error chime sound on Windows
            if os.name == "nt":
                try:
                    import winsound
                    winsound.MessageBeep(winsound.MB_ICONHAND)
                except Exception:
                    pass

            self.page.update()
            show_message_dialog(self.page, doc_err)

    def open_converted_file(self, e=None):
        target = self.state.last_converted_path or self.state.out_path or (self.file_path_bar.out_path_text.value if self.file_path_bar else "")
        if target and os.path.exists(target):
            file_path = os.path.normpath(os.path.abspath(target))
            try:
                open_file_or_folder_foreground(file_path, is_folder=False)
            except Exception as ex:
                print(f"[DEBUG] Failed to open file '{file_path}': {ex}")
                try:
                    os.startfile(file_path)
                except Exception as e_start:
                    print(f"[DEBUG] os.startfile fallback error: {e_start}")
        else:
            print(f"[DEBUG] Cannot open file: target path does not exist '{target}'")

    def open_converted_folder(self, e=None):
        target = self.state.last_converted_path or self.state.out_path or (self.file_path_bar.out_path_text.value if self.file_path_bar else "")
        if target:
            folder_path = target if os.path.isdir(target) else os.path.dirname(target)
            if os.path.exists(folder_path):
                folder_path = os.path.normpath(os.path.abspath(folder_path))
                try:
                    open_file_or_folder_foreground(folder_path, is_folder=True)
                except Exception as ex:
                    print(f"[DEBUG] Failed to open folder for '{folder_path}': {ex}")
                    try:
                        os.startfile(folder_path)
                    except Exception as e_start:
                        print(f"[DEBUG] os.startfile folder fallback error: {e_start}")
            else:
                print(f"[DEBUG] Cannot open folder: path does not exist '{folder_path}'")
