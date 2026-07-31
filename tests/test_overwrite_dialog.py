import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))

import flet as ft
from src.ui_flet.state import AppState
from src.ui_flet.theme import PALETTES, STYLE, resolve_color, get_style_color, make_border

class TestOverwriteDialog(unittest.TestCase):
    def test_dialog_construction(self):
        """Test constructing the overwrite confirmation dialog without raising AttributeError or Flet exceptions."""
        app_state = AppState()
        palette_name = app_state.current_palette
        palette = PALETTES.get(palette_name, PALETTES["Violet Cyberpunk"])
        is_dark = app_state.current_theme_mode == "dark"

        bg_card = resolve_color(palette, "bg_component", is_dark)
        accent_color = resolve_color(palette, "text_accent_primary", is_dark)
        text_primary = get_style_color("text_primary", is_dark)
        text_secondary = get_style_color("text_secondary", is_dark)
        border_color = resolve_color(palette, "border_color", is_dark)

        file_name = "test_document.html"

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.WARNING_ROUNDED, color=ft.Colors.AMBER_400, size=24),
                    ft.Text("Confirm File Overwrite", weight=ft.FontWeight.BOLD, size=18, color=text_primary),
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
                            bgcolor=resolve_color(palette, "bg_main", is_dark),
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
                ft.TextButton("Cancel"),
                ft.Button(
                    "Overwrite / Replace",
                    icon=ft.Icons.AUTORENEW_ROUNDED,
                ),
            ],
            bgcolor=bg_card,
            shape=ft.RoundedRectangleBorder(radius=10),
        )

        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.bgcolor, bg_card)
        print("[SUCCESS] TestOverwriteDialog passed cleanly!")

if __name__ == "__main__":
    unittest.main()
