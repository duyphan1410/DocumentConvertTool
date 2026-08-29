"""
Image Sizing & Format Modal Dialog Component for Flet UI.
Provides a balanced visual interface for adjusting image dimensions, quick presets (25%, 50%, 75%, 100%),
aspect ratio locking, alignment (Left/Center/Right), and alt text.
Follows standard repository modal lifecycle (like file_modals & quick_open_dialog) with click-outside cancel.
"""
from __future__ import annotations

import os
import flet as ft
from typing import Callable, Optional

from src.i18n import t
from src.ui_flet.theme import PALETTES, resolve_color, make_border
from src.ui_flet.helpers.image_token_helper import (
    ImageTokenInfo,
    inspect_image_dimensions,
)
from src.ui_flet.views.preview_view import image_to_base64_uri
from src.ui_flet.native_dialogs import pick_image_file_sync


class ImageSizeDialog:
    """Manages the modal dialog for resizing and formatting document images."""

    def __init__(
        self,
        page: ft.Page,
        image_info: ImageTokenInfo,
        on_apply: Callable[[ImageTokenInfo, str, str, str, str, str], None],
        base_dir: Optional[str] = None,
        current_palette: str = "Violet Cyberpunk",
        is_dark: bool = True,
    ):
        self.page = page
        self.image_info = image_info
        self.on_apply = on_apply
        self.base_dir = base_dir
        self.palette_name = current_palette
        self.is_dark = is_dark

        self.palette = PALETTES.get(current_palette, PALETTES["Violet Cyberpunk"])
        self.accent_color = resolve_color(self.palette, "text_accent_primary", is_dark)
        self.bg_modal = resolve_color(self.palette, "bg_component", is_dark)
        self.border_color = resolve_color(self.palette, "border_color", is_dark)

        # 1. Inspect original dimensions safely
        self.orig_w, self.orig_h = inspect_image_dimensions(image_info.src, base_dir=base_dir)

        # 2. Parse initial width & height
        raw_w = (image_info.width or "").strip()
        raw_h = (image_info.height or "").strip()
        self.initial_unit = "%" if raw_w.endswith("%") else "px"
        self.initial_width_val = raw_w.rstrip("%").rstrip("px").strip()
        self.initial_height_val = raw_h.rstrip("px").strip()

        # Determine initial preset
        if not raw_w or raw_w in ("100%", "100"):
            self.current_preset = "100"
            if not self.initial_width_val:
                self.initial_width_val = "100"
        elif raw_w == "25%":
            self.current_preset = "25"
        elif raw_w == "50%":
            self.current_preset = "50"
        elif raw_w == "75%":
            self.current_preset = "75"
        else:
            self.current_preset = "custom"

        self.lock_aspect_ratio = True
        self.selected_align = image_info.align.lower() or ""

        self._build_ui()

    def _build_ui(self):
        # ── A. Left Column: Thumbnail Preview & Info ──────────────────────────
        thumb_src = None
        is_preview_valid = False
        target_path = self.image_info.src

        if not os.path.isabs(target_path) and self.base_dir:
            candidate = os.path.normpath(os.path.abspath(os.path.join(self.base_dir, target_path)))
            if os.path.exists(candidate):
                target_path = candidate

        if os.path.exists(target_path) and os.path.isfile(target_path):
            try:
                thumb_src = image_to_base64_uri(target_path, max_width=400)
                is_preview_valid = True
            except Exception:
                thumb_src = None

        if is_preview_valid and thumb_src:
            self.img_control = ft.Image(
                src=thumb_src,
                fit=ft.BoxFit.CONTAIN,
                width=260,
                height=185,
                border_radius=6,
            )
        else:
            self.img_control = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.IMAGE_OUTLINED, size=44, color=ft.Colors.OUTLINE),
                        ft.Text(os.path.basename(self.image_info.src) or "Image", size=11, color=ft.Colors.OUTLINE, text_align=ft.TextAlign.CENTER, no_wrap=True),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                width=260,
                height=185,
                border_radius=6,
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                alignment=ft.Alignment(0.0, 0.0),
            )

        self.preview_container = ft.Container(
            content=self.img_control,
            width=270,
            height=195,
            border_radius=8,
            border=make_border(1, self.border_color),
            alignment=ft.Alignment(0.0, 0.0),
            padding=4,
        )

        self.orig_res_text = ft.Text(
            t("image_dialog.orig_res", w=self.orig_w, h=self.orig_h),
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        self.applied_scale_text = ft.Text(
            self._get_applied_scale_label(),
            size=11,
            weight=ft.FontWeight.W_600,
            color=self.accent_color,
        )

        left_column = ft.Column(
            controls=[
                self.preview_container,
                ft.Container(
                    content=self.orig_res_text,
                    padding=ft.Padding(8, 3, 8, 3),
                    border_radius=4,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                ),
                ft.Container(
                    content=self.applied_scale_text,
                    padding=ft.Padding(8, 3, 8, 3),
                    border_radius=4,
                    bgcolor=ft.Colors.with_opacity(0.12, self.accent_color),
                ),
            ],
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # ── B. Right Column: Controls ──────────────────────────────────────────
        # 1. Preset Buttons
        self.btn_preset_25 = ft.OutlinedButton("25%", on_click=lambda _: self._apply_preset("25"), height=30)
        self.btn_preset_50 = ft.OutlinedButton("50%", on_click=lambda _: self._apply_preset("50"), height=30)
        self.btn_preset_75 = ft.OutlinedButton("75%", on_click=lambda _: self._apply_preset("75"), height=30)
        self.btn_preset_100 = ft.OutlinedButton("100%", on_click=lambda _: self._apply_preset("100"), height=30)

        preset_row = ft.Row(
            controls=[
                self.btn_preset_25,
                self.btn_preset_50,
                self.btn_preset_75,
                self.btn_preset_100,
            ],
            spacing=6,
        )

        # 2. Dimensions Inputs
        self.txt_width = ft.TextField(
            label=t("image_dialog.width"),
            value=self.initial_width_val,
            width=90,
            text_size=12,
            content_padding=ft.Padding(10, 11, 10, 11),
            on_change=self._on_dimension_text_changed,
        )
        self.dd_unit = ft.Dropdown(
            options=[ft.dropdown.Option("%"), ft.dropdown.Option("px")],
            value=self.initial_unit,
            width=90,
            content_padding=ft.Padding(8, 7, 8, 7),
        )
        self.dd_unit.on_change = self._on_unit_changed

        self.txt_height = ft.TextField(
            label=t("image_dialog.height"),
            value=self.initial_height_val or "auto",
            width=90,
            text_size=12,
            content_padding=ft.Padding(10, 11, 10, 11),
            on_change=self._on_dimension_text_changed,
        )
        self.btn_lock_ratio = ft.IconButton(
            icon=ft.Icons.LOCK_ROUNDED if self.lock_aspect_ratio else ft.Icons.LOCK_OPEN_ROUNDED,
            tooltip=t("image_dialog.lock_aspect"),
            icon_color=self.accent_color if self.lock_aspect_ratio else None,
            icon_size=20,
            on_click=self._toggle_lock_ratio,
        )

        dim_row = ft.Row(
            controls=[
                self.txt_width,
                self.dd_unit,
                ft.Text("×", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.OUTLINE),
                self.txt_height,
                self.btn_lock_ratio,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        )

        # 3. Alignment Buttons
        self.btn_align_default = self._create_align_btn(ft.Icons.FORMAT_ALIGN_JUSTIFY_ROUNDED, t("image_dialog.align_default"), "")
        self.btn_align_left = self._create_align_btn(ft.Icons.FORMAT_ALIGN_LEFT_ROUNDED, t("image_dialog.align_left"), "left")
        self.btn_align_center = self._create_align_btn(ft.Icons.FORMAT_ALIGN_CENTER_ROUNDED, t("image_dialog.align_center"), "center")
        self.btn_align_right = self._create_align_btn(ft.Icons.FORMAT_ALIGN_RIGHT_ROUNDED, t("image_dialog.align_right"), "right")

        align_row = ft.Row(
            controls=[
                ft.Text(f"{t('image_dialog.alignment')}:", size=12, weight=ft.FontWeight.W_500),
                self.btn_align_default,
                self.btn_align_left,
                self.btn_align_center,
                self.btn_align_right,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        )

        # 4. Alt Text & Path with Browse button
        self.txt_alt = ft.TextField(
            label=t("image_dialog.alt_text"),
            value=self.image_info.alt,
            text_size=12,
            expand=True,
            content_padding=ft.Padding(12, 12, 12, 12),
        )
        self.txt_src = ft.TextField(
            label=t("image_dialog.src_path"),
            value=self.image_info.src,
            text_size=12,
            expand=True,
            content_padding=ft.Padding(12, 12, 12, 12),
        )
        self.btn_browse = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            tooltip="Browse Image...",
            icon_size=20,
            on_click=self._on_browse_clicked,
        )
        src_row = ft.Row(
            controls=[self.txt_src, self.btn_browse],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        )

        right_column = ft.Column(
            controls=[
                ft.Text(t("image_dialog.quick_presets"), size=12, weight=ft.FontWeight.BOLD),
                preset_row,
                ft.Divider(height=6, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
                ft.Text(t("image_dialog.dimensions"), size=12, weight=ft.FontWeight.BOLD),
                dim_row,
                align_row,
                ft.Divider(height=6, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
                self.txt_alt,
                src_row,
            ],
            spacing=8,
            expand=True,
        )

        content_body = ft.Row(
            controls=[
                left_column,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                right_column,
            ],
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # ── C. Footer Buttons (Guaranteed Horizontal Row Layout) ───────────────
        self.btn_reset = ft.TextButton(
            t("image_dialog.btn_reset"),
            icon=ft.Icons.RESTORE_ROUNDED,
            on_click=self._on_reset_clicked,
            style=ft.ButtonStyle(padding=ft.Padding(8, 4, 8, 4)),
        )
        self.btn_cancel = ft.OutlinedButton(
            t("image_dialog.btn_cancel"),
            on_click=self._on_cancel_clicked,
            height=30,
            style=ft.ButtonStyle(padding=ft.Padding(14, 2, 14, 2)),
        )
        self.btn_apply = ft.FilledButton(
            t("image_dialog.btn_apply"),
            icon=ft.Icons.CHECK_ROUNDED,
            style=ft.ButtonStyle(bgcolor=self.accent_color, padding=ft.Padding(14, 2, 14, 2)),
            on_click=self._on_apply_clicked,
            height=30,
        )

        footer_row = ft.Row(
            controls=[
                self.btn_reset,
                ft.Container(expand=True),
                self.btn_cancel,
                self.btn_apply,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        )

        dialog_content = ft.Container(
            content=ft.Column(
                controls=[
                    content_body,
                    ft.Divider(height=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
                    footer_row,
                ],
                spacing=8,
                tight=True,
            ),
            width=660,
            padding=ft.Padding(0, 0, 0, 0),
        )

        # ── D. AlertDialog Setup with compact, tight padding ───────────────────
        self.dialog = ft.AlertDialog(
            modal=False,
            on_dismiss=lambda _: self._close_dialog(),
            title_padding=ft.Padding(18, 12, 18, 2),
            content_padding=ft.Padding(18, 6, 18, 10),
            actions_padding=ft.Padding(0, 0, 0, 0),
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ASPECT_RATIO_ROUNDED, color=self.accent_color, size=18),
                    ft.Text(t("image_dialog.title"), size=14, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.IconButton(
                        ft.Icons.CLOSE,
                        icon_size=17,
                        tooltip="Close (Esc)",
                        on_click=lambda _: self._close_dialog(),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=dialog_content,
        )

        self._update_preset_button_styles()
        self._update_align_button_styles()

    def _create_align_btn(self, icon: str, tooltip: str, align_val: str):
        is_active = (self.selected_align == align_val)
        btn = ft.Container(
            content=ft.Icon(icon, size=16, color=self.accent_color if is_active else ft.Colors.ON_SURFACE_VARIANT),
            width=30,
            height=28,
            alignment=ft.Alignment(0, 0),
            border_radius=4,
            ink=True,
            tooltip=tooltip,
            bgcolor=ft.Colors.with_opacity(0.15, self.accent_color) if is_active else ft.Colors.TRANSPARENT,
            border=make_border(1, self.accent_color) if is_active else None,
            on_click=lambda _: self._set_alignment(align_val),
        )
        btn._align_val = align_val
        return btn

    def _update_align_button_styles(self):
        for btn in [self.btn_align_default, self.btn_align_left, self.btn_align_center, self.btn_align_right]:
            is_active = (self.selected_align == btn._align_val)
            btn.content.color = self.accent_color if is_active else ft.Colors.ON_SURFACE_VARIANT
            btn.bgcolor = ft.Colors.with_opacity(0.15, self.accent_color) if is_active else ft.Colors.TRANSPARENT
            btn.border = make_border(1, self.accent_color) if is_active else None
        try:
            if self.page:
                self.dialog.update()
        except Exception:
            pass

    def _get_applied_scale_label(self) -> str:
        w_val = (self.txt_width.value if hasattr(self, "txt_width") and self.txt_width.value else self.initial_width_val).strip()
        unit = self.dd_unit.value if hasattr(self, "dd_unit") and self.dd_unit.value else self.initial_unit
        if unit == "%":
            return t("image_dialog.applied_scale", scale=f"{w_val}%")
        try:
            w_px = int(w_val)
            h_px = int(self.txt_height.value.strip()) if hasattr(self, "txt_height") and self.txt_height.value and self.txt_height.value != "auto" else int(w_px * (self.orig_h / max(1, self.orig_w)))
            return t("image_dialog.applied_scale", scale=f"{w_px} × {h_px} px")
        except Exception:
            return t("image_dialog.applied_scale", scale=f"{w_val}{unit}")

    def _update_preset_button_styles(self):
        active_bg = ft.Colors.with_opacity(0.15, self.accent_color)
        for val, btn in [("25", self.btn_preset_25), ("50", self.btn_preset_50), ("75", self.btn_preset_75), ("100", self.btn_preset_100)]:
            if self.current_preset == val:
                btn.style = ft.ButtonStyle(
                    bgcolor=active_bg,
                    color=self.accent_color,
                    side=ft.BorderSide(1, self.accent_color),
                )
            else:
                btn.style = None
        try:
            if self.page:
                self.dialog.update()
        except Exception:
            pass

    def _apply_preset(self, preset: str):
        self.current_preset = preset
        self.dd_unit.value = "%"
        self.txt_width.value = preset
        self.txt_height.value = "auto"
        self.applied_scale_text.value = self._get_applied_scale_label()
        self._update_preset_button_styles()

    def _on_unit_changed(self, e):
        new_unit = self.dd_unit.value
        current_w = self.txt_width.value.strip()

        if new_unit == "px":
            if current_w.endswith("%") or self.current_preset in ("25", "50", "75", "100"):
                try:
                    pct = float(current_w.rstrip("%"))
                    px_w = int(self.orig_w * (pct / 100.0))
                    self.txt_width.value = str(px_w)
                except Exception:
                    self.txt_width.value = str(self.orig_w)
            elif not current_w:
                self.txt_width.value = str(self.orig_w)
            self.current_preset = "custom"
        elif new_unit == "%":
            try:
                px = float(current_w)
                pct = int((px / max(1, self.orig_w)) * 100)
                pct = max(5, min(200, pct))
                self.txt_width.value = str(pct)
                if str(pct) in ("25", "50", "75", "100"):
                    self.current_preset = str(pct)
                else:
                    self.current_preset = "custom"
            except Exception:
                self.txt_width.value = "100"
                self.current_preset = "100"

        self.applied_scale_text.value = self._get_applied_scale_label()
        self._update_preset_button_styles()

    def _on_dimension_text_changed(self, e):
        self.current_preset = "custom"
        self._update_preset_button_styles()

        if self.lock_aspect_ratio and self.orig_w > 0 and self.orig_h > 0:
            if e.control == self.txt_width:
                w_str = self.txt_width.value.strip()
                if w_str.isdigit() and self.dd_unit.value == "px":
                    w = int(w_str)
                    calc_h = int(w * (self.orig_h / self.orig_w))
                    self.txt_height.value = str(calc_h)
            elif e.control == self.txt_height:
                h_str = self.txt_height.value.strip()
                if h_str.isdigit() and self.dd_unit.value == "px":
                    h = int(h_str)
                    calc_w = int(h * (self.orig_w / self.orig_h))
                    self.txt_width.value = str(calc_w)

        self.applied_scale_text.value = self._get_applied_scale_label()
        try:
            if self.page:
                self.dialog.update()
        except Exception:
            pass

    def _toggle_lock_ratio(self, e):
        self.lock_aspect_ratio = not self.lock_aspect_ratio
        self.btn_lock_ratio.icon = ft.Icons.LOCK_ROUNDED if self.lock_aspect_ratio else ft.Icons.LOCK_OPEN_ROUNDED
        self.btn_lock_ratio.icon_color = self.accent_color if self.lock_aspect_ratio else None
        try:
            if self.page:
                self.dialog.update()
        except Exception:
            pass

    def _set_alignment(self, align: str):
        self.selected_align = align
        self._update_align_button_styles()

    def _on_browse_clicked(self, e):
        picked = pick_image_file_sync()
        if picked and os.path.exists(picked):
            if self.base_dir:
                try:
                    rel = os.path.relpath(picked, self.base_dir).replace("\\", "/")
                    target_display = rel
                except Exception:
                    target_display = picked
            else:
                target_display = picked

            self.txt_src.value = target_display
            self.orig_w, self.orig_h = inspect_image_dimensions(picked, base_dir=self.base_dir)
            self.orig_res_text.value = t("image_dialog.orig_res", w=self.orig_w, h=self.orig_h)

            try:
                new_thumb = image_to_base64_uri(picked, max_width=400)
                if isinstance(self.img_control, ft.Image):
                    self.img_control.src = new_thumb
                else:
                    self.img_control = ft.Image(
                        src=new_thumb,
                        fit=ft.BoxFit.CONTAIN,
                        width=260,
                        height=185,
                        border_radius=6,
                    )
                    self.preview_container.content = self.img_control
            except Exception:
                pass

            self.applied_scale_text.value = self._get_applied_scale_label()
            try:
                if self.page:
                    self.dialog.update()
            except Exception:
                pass

    def _on_reset_clicked(self, e):
        self._apply_preset("100")
        self._set_alignment("")

    def _close_dialog(self, e=None):
        self.dialog.open = False
        try:
            self.dialog.update()
        except Exception:
            pass
        try:
            if hasattr(self.page, "update"):
                self.page.update()
        except Exception:
            pass

    def _on_cancel_clicked(self, e=None):
        self._close_dialog()

    def _on_apply_clicked(self, e=None):
        w_val = (self.txt_width.value or "").strip()
        h_val = (self.txt_height.value or "").strip()
        unit = self.dd_unit.value or "%"

        final_w = ""
        final_h = ""

        if w_val:
            if unit == "%":
                final_w = f"{w_val}%" if not w_val.endswith("%") else w_val
            else:
                final_w = w_val

        if h_val and h_val.lower() != "auto":
            final_h = h_val

        # If width is 100% and height is empty, simplify to empty width (clean markdown)
        if final_w == "100%" and not final_h and not self.selected_align:
            final_w = ""

        alt_text = self.txt_alt.value or ""
        src_path = self.txt_src.value or self.image_info.src

        self._close_dialog()

        if self.on_apply:
            self.on_apply(
                self.image_info,
                final_w,
                final_h,
                self.selected_align,
                alt_text,
                src_path,
            )

    def show(self):
        """Displays the dialog modally on the page, ensuring clean overlay registration."""
        if hasattr(self.page, "overlay"):
            if self.dialog not in self.page.overlay:
                self.page.overlay.append(self.dialog)
        self.dialog.open = True
        try:
            self.dialog.update()
        except Exception:
            pass
        try:
            if hasattr(self.page, "update"):
                self.page.update()
        except Exception:
            pass


def show_image_size_dialog(
    page: ft.Page,
    image_info: ImageTokenInfo,
    on_apply: Callable[[ImageTokenInfo, str, str, str, str, str], None],
    base_dir: Optional[str] = None,
    current_palette: str = "Violet Cyberpunk",
    is_dark: bool = True,
):
    """Convenience helper to create and open an ImageSizeDialog."""
    dlg = ImageSizeDialog(
        page=page,
        image_info=image_info,
        on_apply=on_apply,
        base_dir=base_dir,
        current_palette=current_palette,
        is_dark=is_dark,
    )
    dlg.show()
    return dlg
