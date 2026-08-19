import unittest
from unittest.mock import MagicMock, patch
import flet as ft
from src.ui_flet.components.youtube_dialog import show_youtube_dialog


class TestYouTubeDialog(unittest.TestCase):
    def setUp(self):
        self.page = MagicMock(spec=ft.Page)
        self.page.overlay = []
        self.page.theme_mode = ft.ThemeMode.DARK
        self.callback = MagicMock()

    def test_show_youtube_dialog_appends_alert_dialog(self):
        show_youtube_dialog(
            page=self.page,
            on_transcript_loaded=self.callback,
            current_palette="Violet Cyberpunk",
        )
        self.assertEqual(len(self.page.overlay), 1)
        dialog = self.page.overlay[0]
        self.assertIsInstance(dialog, ft.AlertDialog)
        self.assertTrue(dialog.open)
        self.assertTrue(dialog.modal)

    def test_show_youtube_dialog_cleans_stale_dialogs(self):
        stale_dialog = ft.AlertDialog()
        self.page.overlay.append(stale_dialog)

        show_youtube_dialog(
            page=self.page,
            on_transcript_loaded=self.callback,
        )
        self.assertEqual(len(self.page.overlay), 1)
        self.assertNotEqual(self.page.overlay[0], stale_dialog)


if __name__ == "__main__":
    unittest.main()
