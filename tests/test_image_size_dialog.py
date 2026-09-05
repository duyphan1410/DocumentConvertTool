"""
Unit tests for ImageSizeDialog component and preset behaviors.
"""
import unittest
import flet as ft
from src.ui_flet.helpers.image_token_helper import ImageTokenInfo
from src.ui_flet.components.image_size_dialog import ImageSizeDialog, show_image_size_dialog
from src.ui_flet.theme import PALETTES


class MockPage:
    def __init__(self):
        self.dialog = None

    def open(self, dlg):
        self.dialog = dlg

    def close(self, dlg):
        self.dialog = None


class TestImageSizeDialog(unittest.TestCase):
    def setUp(self):
        self.mock_page = MockPage()
        self.sample_info = ImageTokenInfo(
            raw_token="![Sample](assets/logo.png)",
            start=0,
            end=28,
            src="assets/logo.png",
            alt="Sample",
            width="50%",
            height="",
            align="center",
            is_html=False,
        )

    def test_dialog_initialization_with_50_percent(self):
        applied_results = []

        def on_apply(tok, w, h, align, alt, src):
            applied_results.append((w, h, align, alt, src))

        dlg = ImageSizeDialog(
            page=self.mock_page,
            image_info=self.sample_info,
            on_apply=on_apply,
            current_palette="Violet Cyberpunk",
            is_dark=True,
        )
        self.assertEqual(dlg.current_preset, "50")
        self.assertEqual(dlg.txt_width.value, "50")
        self.assertEqual(dlg.dd_unit.value, "%")
        self.assertEqual(dlg.selected_align, "center")

    def test_dialog_apply_preset_25(self):
        applied_results = []

        def on_apply(tok, w, h, align, alt, src):
            applied_results.append((w, h, align, alt, src))

        dlg = ImageSizeDialog(
            page=self.mock_page,
            image_info=self.sample_info,
            on_apply=on_apply,
            current_palette="Emerald Tech",
            is_dark=False,
        )
        dlg._apply_preset("25")
        self.assertEqual(dlg.txt_width.value, "25")
        self.assertEqual(dlg.current_preset, "25")

        dlg._on_apply_clicked(None)
        self.assertEqual(len(applied_results), 1)
        w, h, align, alt, src = applied_results[0]
        self.assertEqual(w, "25%")
        self.assertEqual(align, "center")
        self.assertEqual(alt, "Sample")

    def test_dialog_palettes_smoke(self):
        """Verify dialog initializes smoothly across all palettes and light/dark modes."""
        for pal_name in PALETTES.keys():
            for is_dark in (True, False):
                dlg = ImageSizeDialog(
                    page=self.mock_page,
                    image_info=self.sample_info,
                    on_apply=lambda *args: None,
                    current_palette=pal_name,
                    is_dark=is_dark,
                )
                self.assertIsNotNone(dlg.dialog)


if __name__ == "__main__":
    unittest.main()
