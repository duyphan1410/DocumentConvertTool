"""
Dedicated Loading Screen Component for DocumentConvertTool.
Displays a modern, hardware-accelerated loading view with ProgressRing & status feedback.
"""
import flet as ft
from src.i18n import t


from src.ui_flet.theme import make_border


class LoadingView(ft.Container):
    def __init__(self, message: str = "", **kwargs):
        super().__init__(**kwargs)
        self.expand = True
        self.alignment = ft.alignment.Alignment(0.0, 0.0)

        self.logo_icon = ft.Icon(
            ft.Icons.AUTO_AWESOME_ROUNDED,
            color=ft.Colors.PRIMARY,
            size=48,
        )

        self.title_text = ft.Text(
            t("ribbon.logo"),
            size=22,
            weight=ft.FontWeight.BOLD,
        )

        self.spinner = ft.ProgressRing(
            value=None,
            width=42,
            height=42,
            stroke_width=3.5,
            color=ft.Colors.PRIMARY,
        )

        self.status_text = ft.Text(
            message or t("status.draft_loading"),
            size=14,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.PRIMARY_CONTAINER,
            text_align=ft.TextAlign.CENTER,
        )

        self.card = ft.Container(
            content=ft.Column(
                controls=[
                    self.logo_icon,
                    self.title_text,
                    ft.Container(height=10),
                    self.spinner,
                    ft.Container(height=5),
                    self.status_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            ),
            padding=30,
            border_radius=16,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border=make_border(1, ft.Colors.OUTLINE_VARIANT),
            shadow=ft.BoxShadow(
                blur_radius=15,
                spread_radius=1,
                color=ft.Colors.BLACK26,
            ),
        )

        self.content = self.card

    def set_message(self, message: str):
        self.status_text.value = message
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def update_locale(self):
        self.title_text.value = t("ribbon.logo")
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass
