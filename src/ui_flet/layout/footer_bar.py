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

        self.btn_convert = ft.ElevatedButton(
            t("footer.btn_convert"),
            icon=ft.Icons.TRANSFORM,
            on_click=self.on_convert_clicked,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=24, top=16, right=24, bottom=16),
                color=ft.Colors.WHITE,
            ),
        )
        self.btn_open_file = ft.ElevatedButton(
            t("footer.btn_open_file"),
            icon=ft.Icons.OPEN_IN_NEW,
            visible=False,
            on_click=self.on_open_file,
        )
        self.btn_open_folder = ft.ElevatedButton(
            t("footer.btn_open_folder"),
            icon=ft.Icons.FOLDER_OPEN,
            visible=False,
            on_click=self.on_open_folder,
        )
        self.btn_copy_error = ft.ElevatedButton(
            t("footer.btn_copy_error"),
            icon=ft.Icons.COPY,
            visible=False,
            style=ft.ButtonStyle(color=ft.Colors.RED_400),
            on_click=self._on_copy_error,
        )
        self.progress_bar = ft.ProgressBar(visible=False, expand=True)
        self.status_text = ft.Text(t("footer.status_ready"), size=13)

        self.container = ft.Container(
            content=ft.Row(
                controls=[
                    self.btn_convert,
                    self.btn_open_file,
                    self.btn_open_folder,
                    self.btn_copy_error,
                    self.status_text,
                    self.progress_bar,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            padding=ft.Padding(left=12, top=8, right=12, bottom=8),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )

    def _on_copy_error(self, e):
        err_text = self.status_text.value or ""
        if err_text:
            page = getattr(e, "page", None) or getattr(self.container, "page", None)
            if page:
                try:
                    page.clipboard = err_text
                except Exception:
                    try:
                        if hasattr(page, "set_clipboard"):
                            page.set_clipboard(err_text)
                    except Exception:
                        pass
            import sys, subprocess
            try:
                if sys.platform == "win32":
                    subprocess.run("clip", input=err_text, text=True, encoding="utf-8", shell=True)
                elif sys.platform == "darwin":
                    subprocess.run("pbcopy", input=err_text, text=True, encoding="utf-8")
                else:
                    subprocess.run(["xclip", "-selection", "clipboard"], input=err_text, text=True, encoding="utf-8")
            except Exception as ex:
                print(f"[DEBUG] Clipboard copy failed: {ex}")
            self.set_status(t("footer.status_copied"), ft.Colors.GREEN_400)

    def set_status_key(self, key: str, color=None, is_error: bool = False, **kwargs):
        """Set status using an i18n key so it automatically updates when language changes."""
        self._current_status_key = key
        self._current_status_kwargs = kwargs
        self._current_status_color = color
        self._current_status_is_error = is_error
        text = t(key, **kwargs)
        self.set_status(text, color=color, is_error=is_error, _from_key=True)

    def set_status(self, text: str, color=None, is_error: bool = False, _from_key: bool = False):
        if not _from_key:
            self._current_status_key = None
            self._current_status_kwargs = {}
        self.status_text.value = text
        if color:
            self.status_text.color = color

        is_err = is_error or (color in (ft.Colors.RED_400, ft.Colors.RED, "#f44336", "#ef5350"))
        self.btn_copy_error.visible = is_err
        if self.btn_copy_error.page:
            self.btn_copy_error.update()

        if self.status_text.page:
            self.status_text.update()

    def set_processing(self, is_processing: bool):
        self.progress_bar.visible = is_processing
        self.btn_convert.disabled = is_processing
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

    def apply_palette(self, palette: dict, is_dark: bool):
        """Apply palette colors to the footer bar."""
        bg = resolve_color(palette, "bg_component", is_dark)
        border = resolve_color(palette, "border_color", is_dark)
        btn_fg = resolve_color(palette, "btn_convert_fg", is_dark)
        btn_hover = resolve_color(palette, "btn_convert_hover", is_dark)
        btn_open_fg = resolve_color(palette, "btn_open_fg", is_dark)
        btn_open_hover = resolve_color(palette, "btn_open_hover", is_dark)
        accent_secondary = resolve_color(palette, "text_accent_secondary", is_dark)

        # Container background and border
        self.container.bgcolor = bg
        self.container.border = make_border(1, border)

        # Convert button
        self.btn_convert.style = ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            padding=ft.Padding(left=24, top=16, right=24, bottom=16),
            color=ft.Colors.WHITE,
            bgcolor=btn_fg,
            overlay_color=btn_hover,
        )

        # Open File / Open Folder buttons (only if visible/enabled)
        if self.btn_open_file.visible:
            self.btn_open_file.style = ft.ButtonStyle(
                bgcolor=btn_open_fg,
                overlay_color=btn_open_hover,
                color=ft.Colors.WHITE,
            )
        if self.btn_open_folder.visible:
            self.btn_open_folder.style = ft.ButtonStyle(
                bgcolor=btn_open_fg,
                overlay_color=btn_open_hover,
                color=ft.Colors.WHITE,
            )

        # Progress bar color
        self.progress_bar.color = accent_secondary

        try:
            self.container.update()
        except Exception:
            pass

    def update_locale(self):
        """Refresh all text to current locale."""
        self.btn_convert.text = t("footer.btn_convert")
        self.btn_open_file.text = t("footer.btn_open_file")
        self.btn_open_folder.text = t("footer.btn_open_folder")
        self.btn_copy_error.text = t("footer.btn_copy_error")
        if hasattr(self, "_current_status_key") and self._current_status_key:
            self.status_text.value = t(self._current_status_key, **self._current_status_kwargs)
        elif self.status_text.value in ("Ready", "Sẵn sàng", t("footer.status_ready")):
            self.status_text.value = t("footer.status_ready")

        for ctrl in [self.btn_convert, self.btn_open_file, self.btn_open_folder, self.btn_copy_error, self.status_text]:
            try:
                if hasattr(ctrl, "page") and ctrl.page:
                    ctrl.update()
            except Exception:
                pass

        try:
            if self.container.page:
                self.container.update()
        except Exception:
            pass
