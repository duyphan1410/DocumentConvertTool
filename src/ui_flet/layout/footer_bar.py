"""
Footer Bar Layout component.
Contains Convert Action button, Open File/Folder buttons, Progress bar, and Status console.
"""
from typing import Callable, Optional
import flet as ft
from src.i18n import t
from src.ui_flet.theme import resolve_color, make_border


class FooterBar:
    def __init__(
        self,
        on_convert_clicked: Optional[Callable[[ft.ControlEvent], None]] = None,
        on_open_file: Optional[Callable[[ft.ControlEvent], None]] = None,
        on_open_folder: Optional[Callable[[ft.ControlEvent], None]] = None,
    ):
        self.on_convert_clicked = on_convert_clicked
        self.on_open_file = on_open_file
        self.on_open_folder = on_open_folder

        self.btn_convert_text = ft.Text(t("footer.btn_convert"), color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.W_600)
        self.btn_convert = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TRANSFORM, color=ft.Colors.WHITE, size=16),
                    self.btn_convert_text,
                ],
                spacing=6,
                tight=True,
            ),
            on_click=self.on_convert_clicked,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(left=14, top=6, right=14, bottom=6),
            ),
        )
        self.btn_open_file_text = ft.Text(t("footer.btn_open_file"), size=12)
        self.btn_open_file = ft.ElevatedButton(
            content=ft.Row(
                controls=[ft.Icon(ft.Icons.OPEN_IN_NEW, size=16), self.btn_open_file_text],
                spacing=6,
                tight=True,
            ),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(left=12, top=6, right=12, bottom=6),
            ),
            visible=False,
            on_click=self.on_open_file,
        )
        self.btn_open_folder_text = ft.Text(t("footer.btn_open_folder"), size=12)
        self.btn_open_folder = ft.ElevatedButton(
            content=ft.Row(
                controls=[ft.Icon(ft.Icons.FOLDER_OPEN, size=16), self.btn_open_folder_text],
                spacing=6,
                tight=True,
            ),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(left=12, top=6, right=12, bottom=6),
            ),
            visible=False,
            on_click=self.on_open_folder,
        )

        self.progress_bar = ft.ProgressBar(visible=False, expand=True)
        self.status_text = ft.Text(t("footer.status_ready"), size=12)

        self.status_container = ft.Container(
            content=self.status_text,
            on_click=self._on_status_clicked,
        )

        self.container = ft.Container(
            content=ft.Row(
                controls=[
                    self.btn_convert,
                    self.btn_open_file,
                    self.btn_open_folder,
                    self.status_container,
                    self.progress_bar,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            padding=ft.Padding(left=10, top=4, right=10, bottom=4),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )

    def _on_status_clicked(self, e):
        """If an error occurred and user clicks the status bar, re-open the rich details modal."""
        doc_err = getattr(self, "_current_doc_err", None)
        if doc_err:
            page = getattr(e, "page", None) or getattr(self.container, "page", None)
            if page:
                from src.ui_flet.components.message_dialog import show_message_dialog
                show_message_dialog(page, doc_err)

    def set_status_key(self, key: str, color=None, is_error: bool = False, doc_err=None, **kwargs):
        """Set status using an i18n key so it automatically updates when language changes."""
        self._current_status_key = key
        self._current_status_kwargs = kwargs
        self._current_status_color = color
        self._current_status_is_error = is_error
        self._current_doc_err = doc_err

        if doc_err is not None and "error" not in kwargs:
            from src.core.errors import ErrorCode
            ERROR_CODE_TITLE_KEYS = {
                ErrorCode.FILE_NOT_FOUND: "error.file_not_found_title",
                ErrorCode.UNSUPPORTED_EXTENSION: "validator.unsupported_ext_title",
                ErrorCode.IS_DIRECTORY: "error.is_directory_title",
                ErrorCode.FILE_LOCKED: "error.file_locked_title",
                ErrorCode.FILE_EMPTY: "validator.empty_title",
                ErrorCode.FILE_TOO_LARGE: "validator.too_large_title",
                ErrorCode.CORRUPTED_STRUCTURE: "validator.corrupted_title",
                ErrorCode.MISSING_DEPENDENCY: "error.missing_dep_title",
                ErrorCode.CONVERSION_FAILED: "error.conversion_val_title",
                ErrorCode.READ_ONLY_SAVE_ERROR: "error.save_permission_title",
                ErrorCode.UNKNOWN_ERROR: "error.unknown_title",
            }
            title_key = ERROR_CODE_TITLE_KEYS.get(doc_err.code)
            translated_title = t(title_key) if title_key else getattr(doc_err, "title", str(doc_err))
            kwargs["error"] = translated_title
        elif doc_err is not None:
            self._current_doc_err = doc_err

        text = t(key, **kwargs)
        self.set_status(text, color=color, is_error=is_error, _from_key=True)

    def set_status(self, text: str, color=None, is_error: bool = False, _from_key: bool = False):
        if not _from_key:
            self._current_status_key = None
            self._current_status_kwargs = {}
            self._current_doc_err = None
        self.status_text.value = text
        if color:
            self.status_text.color = color

        if self.status_text.page:
            self.status_text.update()

    def set_processing(self, is_processing: bool):
        self.progress_bar.visible = is_processing
        self.btn_convert.disabled = is_processing
        if is_processing:
            self.btn_convert.tooltip = t("footer.loading_wait") if t("footer.loading_wait") != "footer.loading_wait" else "Đang xử lý tài liệu, vui lòng đợi hoàn tất..."
        else:
            self.btn_convert.tooltip = None
        if self.progress_bar.page:
            self.progress_bar.update()
        if self.btn_convert.page:
            self.btn_convert.update()

    def set_result_buttons_visible(self, visible: bool):
        self.btn_open_file.visible = visible
        self.btn_open_folder.visible = visible
        if self.btn_open_file.page:
            self.btn_open_file.update()
        if self.btn_open_folder.page:
            self.btn_open_folder.update()

    def apply_palette(self, palette: dict, is_dark: bool, palette_name: str = ""):
        """Apply active palette theme to footer background and convert button."""
        bg_bar = resolve_color(palette, "bg_header", is_dark)
        border_col = resolve_color(palette, "border_color", is_dark)
        btn_bg = resolve_color(palette, "text_accent_primary", is_dark)

        self.container.bgcolor = bg_bar
        self.container.border = make_border(1, border_col)

        self.btn_convert.style = ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            bgcolor={
                ft.ControlState.DISABLED: ft.Colors.with_opacity(0.35, btn_bg),
                ft.ControlState.DEFAULT: btn_bg,
            },
            color={
                ft.ControlState.DISABLED: ft.Colors.WHITE38,
                ft.ControlState.DEFAULT: ft.Colors.WHITE,
            },
            padding=ft.Padding(left=24, top=16, right=24, bottom=16),
        )

        try:
            if self.container.page:
                self.container.update()
        except Exception:
            pass

    def update_locale(self):
        """Refresh all text to current locale."""
        self.btn_convert_text.value = t("footer.btn_convert")
        self.btn_open_file_text.value = t("footer.btn_open_file")
        self.btn_open_folder_text.value = t("footer.btn_open_folder")
        if getattr(self, "_current_doc_err", None) and hasattr(self, "_current_status_key") and self._current_status_key:
            from src.core.errors import ErrorCode
            ERROR_CODE_TITLE_KEYS = {
                ErrorCode.FILE_NOT_FOUND: "error.file_not_found_title",
                ErrorCode.UNSUPPORTED_EXTENSION: "validator.unsupported_ext_title",
                ErrorCode.IS_DIRECTORY: "error.is_directory_title",
                ErrorCode.FILE_LOCKED: "error.file_locked_title",
                ErrorCode.FILE_EMPTY: "validator.empty_title",
                ErrorCode.FILE_TOO_LARGE: "validator.too_large_title",
                ErrorCode.CORRUPTED_STRUCTURE: "validator.corrupted_title",
                ErrorCode.MISSING_DEPENDENCY: "error.missing_dep_title",
                ErrorCode.CONVERSION_FAILED: "error.conversion_val_title",
                ErrorCode.READ_ONLY_SAVE_ERROR: "error.save_permission_title",
                ErrorCode.UNKNOWN_ERROR: "error.unknown_title",
            }
            title_key = ERROR_CODE_TITLE_KEYS.get(self._current_doc_err.code)
            translated_title = t(title_key) if title_key else getattr(self._current_doc_err, "title", str(self._current_doc_err))
            kwargs = dict(self._current_status_kwargs)
            kwargs["error"] = translated_title
            self.status_text.value = t(self._current_status_key, **kwargs)
        elif hasattr(self, "_current_status_key") and self._current_status_key:
            self.status_text.value = t(self._current_status_key, **self._current_status_kwargs)
        elif self.status_text.value in ("Ready", "Sẵn sàng", t("footer.status_ready")):
            self.status_text.value = t("footer.status_ready")

        for ctrl in [
            self.btn_convert_text,
            self.btn_open_file_text,
            self.btn_open_folder_text,
            self.status_text,
            self.btn_convert,
            self.btn_open_file,
            self.btn_open_folder,
        ]:
            try:
                ctrl.update()
            except Exception:
                pass

        try:
            if self.container.page:
                self.container.update()
        except Exception:
            pass
