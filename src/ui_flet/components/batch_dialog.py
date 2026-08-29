"""
Batch & Archive Conversion Modal Dialog for Flet UI.
Supports converting whole folders or compressed archives (.zip, .rar, .7z, .tar.gz)
with dismissible modal lifecycle, real-time progress, and structured logging.
"""

import os
import threading
from typing import Optional, Callable

import flet as ft

from src.services.batch_service import BatchConversionService, BatchResult, BatchItemResult
from src.ui_flet.native_dialogs import (
    pick_directory_sync,
    pick_input_file_sync,
    pick_output_file_sync,
    pick_archive_file_sync,
)
from src.utils.file_ops import reveal_in_windows_explorer

from src.ui_flet.theme import make_border
from src.i18n import t



SUPPORTED_TARGET_FORMATS = [
    (".md", "Markdown (.md)"),
    (".docx", "Word (.docx)"),
    (".pdf", "PDF (.pdf)"),
    (".html", "HTML (.html)"),
    (".xlsx", "Excel (.xlsx)"),
    (".csv", "CSV (.csv)"),
    (".json", "JSON (.json)"),
    (".yaml", "YAML (.yaml)"),
    (".pptx", "PowerPoint (.pptx)"),
]


class BatchDialog:
    """
    Controller and UI generator for the Batch Document Conversion Modal.
    """

    def __init__(
        self,
        page: ft.Page,
        initial_source: str = "",
        on_completed: Optional[Callable[[BatchResult], None]] = None,
    ):
        self.page = page
        self.initial_source = initial_source
        self.on_completed = on_completed
        self.batch_service = BatchConversionService(max_workers=3)
        self._worker_thread: Optional[threading.Thread] = None

        is_archive = bool(
            self.initial_source
            and self.initial_source.lower().endswith((".zip", ".rar", ".7z", ".tar.gz", ".tgz", ".tar", ".bz2"))
        )
        self._saved_folder_path = self.initial_source if (self.initial_source and not is_archive) else ""
        self._saved_archive_path = self.initial_source if is_archive else ""

        self._build_ui()

    def _build_ui(self):
        # 1. Source selector
        is_archive = bool(
            self.initial_source
            and self.initial_source.lower().endswith((".zip", ".rar", ".7z", ".tar.gz", ".tgz", ".tar", ".bz2"))
        )

        self.source_type_seg = ft.SegmentedButton(
            selected=["archive" if is_archive else "folder"],
            segments=[
                ft.Segment(
                    value="folder",
                    label=ft.Text(t("batch.tab_folder"), size=12, weight=ft.FontWeight.W_500),
                    icon=ft.Icon(ft.Icons.FOLDER_ROUNDED, size=15),
                ),
                ft.Segment(
                    value="archive",
                    label=ft.Text(t("batch.tab_archive"), size=12, weight=ft.FontWeight.W_500),
                    icon=ft.Icon(ft.Icons.ARCHIVE_ROUNDED, size=15),
                ),
            ],
            on_change=self._on_source_type_changed,
        )

        self.source_path_field = ft.TextField(
            value=self.initial_source,
            hint_text=t("batch.label_source"),
            text_size=12,
            dense=True,
            expand=True,
            border_radius=8,
        )

        self.btn_browse_source = ft.OutlinedButton(
            t("batch.btn_browse"),
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            on_click=self._handle_browse_source,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(12, 10, 14, 10),
            ),
        )

        source_row = ft.Row(
            [self.source_path_field, self.btn_browse_source],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 2. Target format selector (clean without duplicated label)
        self.target_format_dropdown = ft.Dropdown(
            value=".md",
            options=[
                ft.dropdown.Option(key=fmt[0], text=fmt[1])
                for fmt in SUPPORTED_TARGET_FORMATS
            ],
            text_size=12,
            dense=True,
            border_radius=8,
        )




        # 3. Output destination & type
        self.output_type_radio = ft.RadioGroup(
            content=ft.Row(
                [
                    ft.Radio(value="folder", label=t("batch.opt_folder")),
                    ft.Radio(value="zip", label=t("batch.opt_zip")),
                ],
                spacing=20,
            ),
            value="folder",
            on_change=self._on_output_type_changed,
        )

        self.output_path_field = ft.TextField(
            value="",
            hint_text=t("batch.label_output_dest"),
            text_size=12,
            dense=True,
            expand=True,
            border_radius=8,
        )

        self.btn_browse_output = ft.OutlinedButton(
            t("batch.btn_browse"),
            icon=ft.Icons.SAVE_AS_ROUNDED,
            on_click=self._handle_browse_output,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(12, 10, 14, 10),
            ),
        )

        output_row = ft.Row(
            [self.output_path_field, self.btn_browse_output],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 4. Progress bar & status log
        self.progress_bar = ft.ProgressBar(
            value=0.0,
            visible=False,
            height=4,
            border_radius=2,
            color=ft.Colors.PRIMARY,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )
        self.progress_label = ft.Text(
            t("batch.status_ready"),
            size=12,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )

        self.log_list = ft.ListView(
            spacing=4,
            height=125,
            padding=ft.Padding(6, 6, 6, 6),
        )

        # Initial placeholder in log list
        self.log_placeholder = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=15, color=ft.Colors.OUTLINE),
                    ft.Text(t("batch.status_ready"), size=11, color=ft.Colors.OUTLINE),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(8, 8, 8, 8),
        )
        self.log_list.controls.append(self.log_placeholder)

        log_container = ft.Container(
            content=self.log_list,
            border=make_border(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            height=125,
        )

        # 5. Dialog Actions
        self.btn_start = ft.FilledButton(
            t("batch.btn_start"),
            icon=ft.Icons.PLAY_ARROW_ROUNDED,
            on_click=self._handle_start_clicked,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(16, 10, 18, 10),
            ),
        )

        self.btn_cancel = ft.OutlinedButton(
            t("batch.btn_cancel"),
            icon=ft.Icons.STOP_ROUNDED,
            visible=False,
            on_click=self._handle_cancel_clicked,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                color=ft.Colors.AMBER_400,
            ),
        )

        self.btn_open_result = ft.OutlinedButton(
            t("batch.btn_open_folder"),
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            visible=False,
            on_click=self._handle_open_result_clicked,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
        )

        self.btn_close = ft.TextButton(
            t("batch.btn_close"),
            on_click=lambda _: self._close_dialog(),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
        )

        # Structured sections
        source_section = ft.Container(
            content=ft.Column(
                [
                    ft.Text(t("batch.label_source"), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    self.source_type_seg,
                    source_row,
                ],
                spacing=8,
                tight=True,
            ),
            padding=ft.Padding(12, 10, 12, 10),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border=make_border(1, ft.Colors.OUTLINE_VARIANT),
        )

        options_section = ft.Container(
            content=ft.Column(
                [
                    ft.Text(t("batch.label_target_format"), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    self.target_format_dropdown,
                    ft.Text(t("batch.label_output_dest"), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    self.output_type_radio,
                    output_row,
                ],
                spacing=8,
                tight=True,
            ),
            padding=ft.Padding(12, 10, 12, 10),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            border=make_border(1, ft.Colors.OUTLINE_VARIANT),
        )

        progress_section = ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.TERMINAL_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                        self.progress_label,
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.progress_bar,
                log_container,
            ],
            spacing=6,
            tight=True,
        )

        # Content column
        content = ft.Container(
            content=ft.Column(
                [
                    source_section,
                    options_section,
                    progress_section,
                ],
                spacing=12,
                tight=True,
            ),
            width=540,
            padding=ft.Padding(4, 0, 4, 0),
        )

        self.dialog = ft.AlertDialog(
            modal=False,
            title=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(ft.Icons.DYNAMIC_FEED_ROUNDED, size=20, color=ft.Colors.PRIMARY),
                        padding=6,
                        border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                    ),
                    ft.Text(t("batch.dialog_title"), size=15, weight=ft.FontWeight.BOLD),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=content,
            actions=[
                self.btn_open_result,
                self.btn_cancel,
                self.btn_close,
                self.btn_start,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            on_dismiss=lambda _: self._close_dialog(),
        )


    def show(self):
        """Displays dialog safely on page with overlay cleanup."""
        # Purge any zombie AlertDialogs from overlay
        self.page.overlay[:] = [
            c for c in self.page.overlay if not isinstance(c, ft.AlertDialog)
        ]
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def _close_dialog(self):
        """Clean dialog dismissal for all inner buttons and outside backdrop click."""
        if self.batch_service.is_running():
            self.batch_service.cancel()

        self.dialog.open = False
        try:
            self.page.update()
        except Exception:
            pass

    def _on_source_type_changed(self, e):
        # Save current typed/selected path before switching
        current_val = (self.source_path_field.value or "").strip()
        is_archive = "archive" in (self.source_type_seg.selected or [])

        if is_archive:
            # Switched to Archive: if previous value was a folder, save it
            if current_val and not current_val.lower().endswith((".zip", ".rar", ".7z", ".tar.gz", ".tgz", ".tar", ".bz2")):
                self._saved_folder_path = current_val
            self.source_path_field.value = self._saved_archive_path
        else:
            # Switched to Folder: if previous value was an archive, save it
            if current_val and current_val.lower().endswith((".zip", ".rar", ".7z", ".tar.gz", ".tgz", ".tar", ".bz2")):
                self._saved_archive_path = current_val
            self.source_path_field.value = self._saved_folder_path

        try:
            self.dialog.update()
        except Exception:
            pass

    def _on_output_type_changed(self, e):
        # Adjust extension hint for output if needed
        val = self.output_path_field.value.strip()
        if val:
            if self.output_type_radio.value == "zip" and not val.lower().endswith(".zip"):
                self.output_path_field.value = f"{os.path.splitext(val)[0]}.zip"
            elif self.output_type_radio.value == "folder" and val.lower().endswith(".zip"):
                self.output_path_field.value = os.path.splitext(val)[0]
        try:
            self.dialog.update()
        except Exception:
            pass

    def _handle_browse_source(self, e):
        is_archive = "archive" in (self.source_type_seg.selected or [])
        if is_archive:
            path = pick_archive_file_sync()
            if path:
                self._saved_archive_path = path
        else:
            path = pick_directory_sync()
            if path:
                self._saved_folder_path = path


        if path:
            self.source_path_field.value = path
            # Auto-suggest output path in same directory
            if not self.output_path_field.value:
                base_dir = os.path.dirname(path) if os.path.isfile(path) else path
                name = os.path.splitext(os.path.basename(path))[0]
                if self.output_type_radio.value == "zip":
                    self.output_path_field.value = os.path.join(base_dir, f"{name}_converted.zip")
                else:
                    self.output_path_field.value = os.path.join(base_dir, f"{name}_converted")
            try:
                self.dialog.update()
            except Exception:
                pass


    def _handle_browse_output(self, e):
        if self.output_type_radio.value == "zip":
            path = pick_output_file_sync(
                default_ext=".zip",
                initial_file="converted_documents.zip",
            )
        else:
            path = pick_directory_sync()

        if path:
            self.output_path_field.value = path
            try:
                self.dialog.update()
            except Exception:
                pass


    def _handle_start_clicked(self, e):
        src = (self.source_path_field.value or "").strip()
        out = (self.output_path_field.value or "").strip()
        target_ext = self.target_format_dropdown.value or ".md"
        out_type = self.output_type_radio.value or "folder"

        if not src or not os.path.exists(src):
            self.progress_label.value = t("validator.move_src_not_found", name=src or "N/A")
            self.progress_label.color = ft.Colors.RED_400
            try:
                self.dialog.update()
            except Exception:
                pass
            return

        if not out:
            # Default output next to source
            base_dir = os.path.dirname(src) if os.path.isfile(src) else src
            name = os.path.splitext(os.path.basename(src))[0]
            if out_type == "zip":
                out = os.path.join(base_dir, f"{name}_converted.zip")
            else:
                out = os.path.join(base_dir, f"{name}_converted")
            self.output_path_field.value = out

        # Switch UI to converting state
        self.btn_start.visible = False
        self.btn_cancel.visible = True
        self.btn_open_result.visible = False
        self.progress_bar.visible = True
        self.progress_bar.value = None  # indeterminate until total is known
        self.progress_label.value = t("status.converting")
        self.progress_label.color = ft.Colors.PRIMARY
        self.log_list.controls.clear()
        try:
            self.dialog.update()
        except Exception:
            pass

        def _worker():
            def _progress_cb(current, total, filename, item_res: BatchItemResult):
                def _ui_update():
                    self.progress_bar.value = current / total if total > 0 else 0
                    self.progress_label.value = t(
                        "batch.progress_label",
                        current=current,
                        total=total,
                        filename=filename,
                    )

                    # Add item to log
                    if item_res.status == "success":
                        icon = ft.Icons.CHECK_CIRCLE_ROUNDED
                        color = ft.Colors.GREEN_400
                        text = t(
                            "batch.log_success",
                            name=os.path.basename(item_res.source_file),
                            out_name=os.path.basename(item_res.output_file),
                        )
                    elif item_res.status == "failed":
                        icon = ft.Icons.ERROR_ROUNDED
                        color = ft.Colors.RED_400
                        text = t(
                            "batch.log_failed",
                            name=os.path.basename(item_res.source_file),
                            error=item_res.error_message,
                        )
                    else:
                        icon = ft.Icons.SKIP_NEXT_ROUNDED
                        color = ft.Colors.OUTLINE
                        text = t(
                            "batch.log_skipped",
                            name=os.path.basename(item_res.source_file),
                            reason="Skipped",
                        )

                    self.log_list.controls.append(
                        ft.Row(
                            [
                                ft.Icon(icon, size=14, color=color),
                                ft.Text(text, size=11, color=color, expand=True),
                            ],
                            spacing=6,
                        )
                    )
                    try:
                        self.dialog.update()
                    except Exception:
                        pass

                try:
                    if self.page:
                        _ui_update()
                except Exception:
                    pass

            batch_res = self.batch_service.run_batch(
                source_path=src,
                target_ext=target_ext,
                output_destination=out,
                output_type=out_type,
                preserve_structure=True,
                on_progress=_progress_cb,
            )

            # Completion UI update
            def _on_finish():
                self.btn_cancel.visible = False
                self.btn_start.visible = True
                self.progress_bar.visible = False

                if self.batch_service.is_cancelled():
                    self.progress_label.value = t("batch.status_cancelled")
                    self.progress_label.color = ft.Colors.AMBER_400
                elif batch_res.total == 0:
                    self.progress_label.value = t("batch.no_files_found")
                    self.progress_label.color = ft.Colors.AMBER_400
                else:

                    self.progress_label.value = t(
                        "batch.status_completed",
                        succeeded=batch_res.succeeded,
                        total=batch_res.total,
                        duration=batch_res.duration,
                    )
                    self.progress_label.color = (
                        ft.Colors.GREEN_400 if batch_res.failed == 0 else ft.Colors.AMBER_400
                    )
                    self.btn_open_result.visible = bool(batch_res.output_path and os.path.exists(batch_res.output_path))
                    self._last_result_path = batch_res.output_path

                if self.on_completed:
                    self.on_completed(batch_res)

                try:
                    self.dialog.update()
                except Exception:
                    pass

            try:
                _on_finish()
            except Exception:
                pass

        self._worker_thread = threading.Thread(target=_worker, daemon=True)
        self._worker_thread.start()

    def _handle_cancel_clicked(self, e):
        self.batch_service.cancel()
        self.progress_label.value = t("batch.status_cancelled")
        self.progress_label.color = ft.Colors.AMBER_400
        self.btn_cancel.visible = False
        self.btn_start.visible = True
        try:
            self.dialog.update()
        except Exception:
            pass

    def _handle_open_result_clicked(self, e):
        res_path = getattr(self, "_last_result_path", "")
        if res_path and os.path.exists(res_path):
            reveal_in_windows_explorer(res_path)
            self._close_dialog()
