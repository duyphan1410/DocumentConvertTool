"""
Floating Contextual Mini-Toolbar & Menu Trigger Component for Document Images.
Provides ultra-compact quick presets and an Explorer-style flyout Context Menu.
"""
from typing import Callable, Optional
import os
import flet as ft
from src.i18n import t
from src.ui_flet.theme import PALETTES, resolve_color, make_border
from src.ui_flet.helpers.image_token_helper import ImageTokenInfo


class FloatingImageToolbar(ft.Container):
    """A floating mini-toolbar and context menu trigger for image resizing, alignment, and formatting."""

    def __init__(
        self,
        on_open_context_menu: Optional[Callable[[float, float], None]] = None,
        on_preset_click: Optional[Callable[[str], None]] = None,
        on_align_click: Optional[Callable[[str], None]] = None,
        on_custom_click: Optional[Callable[[], None]] = None,
        on_replace_click: Optional[Callable[[], None]] = None,
        on_reset_click: Optional[Callable[[], None]] = None,
        on_dismiss_click: Optional[Callable[[], None]] = None,
        current_palette: str = "Violet Cyberpunk",
        is_dark: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.on_open_context_menu = on_open_context_menu
        self.on_preset_click = on_preset_click
        self.on_align_click = on_align_click
        self.on_custom_click = on_custom_click
        self.on_replace_click = on_replace_click
        self.on_reset_click = on_reset_click
        self.on_dismiss_click = on_dismiss_click

        self.palette_name = current_palette
        self.is_dark = is_dark
        self.current_token: Optional[ImageTokenInfo] = None

        # Container styling
        self.visible = False
        self.border_radius = 5
        self.padding = ft.Padding(left=3, top=1, right=3, bottom=1)
        self.height = 26
        self.animate_opacity = 150
        self.opacity = 1.0

        self._build_ui()
        self.apply_palette(PALETTES.get(current_palette, PALETTES["Violet Cyberpunk"]), is_dark)

    def _create_preset_btn(self, label: str, preset_val: str):
        text_ctrl = ft.Text(label, size=10.5, weight=ft.FontWeight.W_600)
        btn = ft.Container(
            content=text_ctrl,
            width=28,
            height=20,
            alignment=ft.Alignment(0, 0),
            border_radius=4,
            ink=True,
            tooltip=f"Set width to {preset_val}",
            on_click=lambda _: self._handle_preset(preset_val),
        )
        btn._text_ctrl = text_ctrl
        btn._preset_val = preset_val
        return btn

    def _build_ui(self):
        # 1. Main Menu Trigger Pill [🖼️ Name ▾]
        self.badge_icon = ft.Icon(ft.Icons.IMAGE_ROUNDED, size=13)
        self.badge_label = ft.Text("Image", size=11, weight=ft.FontWeight.W_600, no_wrap=True, max_lines=1)
        self.badge_chevron = ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, size=15)

        self.menu_trigger = ft.Container(
            content=ft.Row(
                controls=[self.badge_icon, self.badge_label, self.badge_chevron],
                spacing=2,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=5, top=0, right=2, bottom=0),
            height=20,
            border_radius=4,
            ink=True,
            tooltip="Click to open Image Actions Menu",
            on_click=self._handle_menu_click,
        )

        # 2. Ultra-compact Quick Presets (28px each)
        self.btn_p25 = self._create_preset_btn("25%", "25%")
        self.btn_p50 = self._create_preset_btn("50%", "50%")
        self.btn_p75 = self._create_preset_btn("75%", "75%")
        self.btn_p100 = self._create_preset_btn("100%", "100%")

        # 3. Action Buttons
        self.btn_align_left = ft.Container()
        self.btn_align_center = ft.Container()
        self.btn_align_right = ft.Container()
        self.btn_custom = ft.Container()
        self.btn_replace = ft.Container()
        self.btn_reset = ft.Container()

        self.btn_dismiss_icon = ft.Icon(ft.Icons.CLOSE_ROUNDED, size=13)
        self.btn_dismiss = ft.Container(
            content=self.btn_dismiss_icon,
            width=20,
            height=20,
            alignment=ft.Alignment(0, 0),
            border_radius=4,
            ink=True,
            tooltip="Close (Esc)",
            on_click=lambda _: self._handle_dismiss(),
        )

        def make_v_divider():
            return ft.Container(
                width=1,
                height=12,
                bgcolor=ft.Colors.OUTLINE_VARIANT,
                margin=ft.Margin(left=1, right=1, top=0, bottom=0),
            )

        self.row = ft.Row(
            controls=[
                self.menu_trigger,
                make_v_divider(),
                self.btn_p25,
                self.btn_p50,
                self.btn_p75,
                self.btn_p100,
                self.btn_dismiss,
            ],
            spacing=1,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )
        self.content = self.row

    def _handle_menu_click(self, e=None):
        if self.on_open_context_menu and self.current_token:
            # Approximate popup coordinates beneath the editor header
            self.on_open_context_menu(260, 110)

    def _handle_preset(self, preset: str):
        if self.on_preset_click:
            self.on_preset_click(preset)

    def _handle_align(self, align: str):
        if self.on_align_click:
            self.on_align_click(align)

    def _handle_custom(self):
        if self.on_custom_click:
            self.on_custom_click()

    def _handle_replace(self):
        if self.on_replace_click:
            self.on_replace_click()

    def _handle_reset(self):
        if self.on_reset_click:
            self.on_reset_click()

    def _handle_dismiss(self):
        self.visible = False
        if self.on_dismiss_click:
            self.on_dismiss_click()
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def set_image_context(self, image_info: Optional[ImageTokenInfo]):
        """Updates toolbar visibility, label, and active button highlights."""
        if image_info == self.current_token and self.visible == bool(image_info):
            return

        self.current_token = image_info
        self.visible = bool(image_info)

        if image_info:
            src_name = os.path.basename(image_info.src) or image_info.alt or "Image"
            if len(src_name) > 14:
                src_name = src_name[:12] + "…"
            self.badge_label.value = src_name

            w = (image_info.width or "").strip()
            accent = self.accent_color if hasattr(self, "accent_color") else ft.Colors.PRIMARY
            active_bg = ft.Colors.with_opacity(0.18, accent)
            border_active = make_border(1, ft.Colors.with_opacity(0.4, accent))

            # Update Preset Highlights
            for btn in [self.btn_p25, self.btn_p50, self.btn_p75, self.btn_p100]:
                p_str = btn._preset_val
                is_active = (w == p_str) or (p_str == "100%" and not w)
                if is_active:
                    btn.bgcolor = active_bg
                    btn.border = border_active
                    btn._text_ctrl.color = accent
                else:
                    btn.bgcolor = None
                    btn.border = None
                    btn._text_ctrl.color = None

        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def apply_palette(self, palette: dict, is_dark: bool):
        """Applies subtle theme palette styling without overwhelming backgrounds."""
        self.palette = palette
        self.is_dark = is_dark

        self.accent_color = resolve_color(palette, "text_accent_primary", is_dark)
        border_col = resolve_color(palette, "border_color", is_dark)
        bg_surface = resolve_color(palette, "bg_component", is_dark)

        self.bgcolor = bg_surface
        self.border = make_border(1, border_col)
        self.shadow = ft.BoxShadow(
            spread_radius=0,
            blur_radius=6,
            color=ft.Colors.with_opacity(0.20 if is_dark else 0.06, ft.Colors.BLACK),
            offset=ft.Offset(0, 2),
        )

        self.badge_icon.color = self.accent_color
        self.badge_label.color = self.accent_color
        self.badge_chevron.color = self.accent_color

        if self.current_token:
            self.set_image_context(self.current_token)
        else:
            try:
                if self.page:
                    self.update()
            except Exception:
                pass
