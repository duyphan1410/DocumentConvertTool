import flet as ft
from src.ui_flet.theme import PALETTES, resolve_color, get_style_color


class DragDropOverlay(ft.Container):
    """
    Visual drag-and-drop overlay container that displays a stylish drop zone
    with supported format badges when files are dragged into the window.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.expand = True
        self.alignment = ft.alignment.Alignment(0.0, 0.0)
        self.bgcolor = ft.Colors.with_opacity(0.85, ft.Colors.SURFACE_CONTAINER_HIGHEST)
        self.visible = False

        badges = [
            ("Word", ".docx", ft.Colors.BLUE_400),
            ("Excel", ".xlsx", ft.Colors.GREEN_400),
            ("PDF", ".pdf", ft.Colors.RED_400),
            ("Markdown", ".md", ft.Colors.PURPLE_400),
            ("CSV", ".csv", ft.Colors.AMBER_400),
            ("HTML", ".html", ft.Colors.ORANGE_400),
        ]

        badge_controls = []
        for name, ext, color in badges:
            badge_controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED, size=14, color=color),
                            ft.Text(f"{name} ({ext})", size=12, weight=ft.FontWeight.W_600, color=color),
                        ],
                        spacing=4,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(8, 4, 8, 4),
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.12, color),
                )
            )

        self.card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.CLOUD_UPLOAD_ROUNDED,
                        size=64,
                        color=ft.Colors.PRIMARY,
                    ),
                    ft.Text(
                        "Kéo & Thả tệp vào đây",
                        size=22,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "Thả tệp để tự động nạp và mở xem trước tài liệu",
                        size=14,
                        color=ft.Colors.GREY_400,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=10),
                    ft.Row(
                        controls=badge_controls,
                        alignment=ft.MainAxisAlignment.CENTER,
                        wrap=True,
                        spacing=8,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            ),
            width=560,
            padding=36,
            border_radius=16,
            border=ft.Border.all(2, ft.Colors.PRIMARY),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        )

        self.content = self.card

    def show_overlay(self):
        self.visible = True
        try:
            self.update()
        except Exception:
            pass

    def hide_overlay(self):
        self.visible = False
        try:
            self.update()
        except Exception:
            pass
