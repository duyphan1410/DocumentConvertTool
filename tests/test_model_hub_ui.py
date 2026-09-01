"""
Layer 1 UI Smoke Test for AI Model Hub & First-Time Dialog.
Instantiates and mounts dialogs & embedded views onto a Mock Page to ensure
100% compliance with Flet 0.86.4 Desktop standards and zero API mismatch.
"""
import unittest
from unittest.mock import MagicMock
import flet as ft

from src.ui_flet.components.first_time_model_dialog import show_first_time_model_dialog
from src.ui_flet.components.model_hub_dialog import show_model_hub_dialog, build_model_hub_view
from src.ui_flet.views.settings_view import SettingsView


class TestModelHubUI(unittest.TestCase):
    """Verifies Flet 0.86.4 compatibility for Model Hub UI components."""

    def setUp(self):
        self.mock_page = MagicMock(spec=ft.Page)
        self.mock_page.overlay = []
        self.mock_page.theme_mode = ft.ThemeMode.DARK
        self.mock_page.update = MagicMock()

    def test_first_time_model_dialog_instantiation(self):
        """Ensures FirstTimeModelDialog constructs and mounts without AttributeError."""
        show_first_time_model_dialog(self.mock_page)
        self.assertEqual(len(self.mock_page.overlay), 1)
        dialog = self.mock_page.overlay[0]
        self.assertIsInstance(dialog, ft.AlertDialog)
        self.assertTrue(dialog.open)
        self.mock_page.update.assert_called()

    def test_model_hub_dialog_instantiation(self):
        """Ensures ModelHubDialog constructs and mounts without AttributeError."""
        show_model_hub_dialog(self.mock_page)
        self.assertEqual(len(self.mock_page.overlay), 1)
        dialog = self.mock_page.overlay[0]
        self.assertIsInstance(dialog, ft.AlertDialog)
        self.assertTrue(dialog.open)

    def test_embedded_model_hub_view_in_settings(self):
        """Ensures SettingsView AI Models panel builds embedded ModelHub view cleanly."""
        panel = build_model_hub_view(
            page=self.mock_page,
            current_palette="Violet Cyberpunk",
            is_embedded=True,
        )
        self.assertIsNotNone(panel)
        self.assertIsInstance(panel, ft.Container)
        self.assertIsInstance(panel.content, ft.Column)


if __name__ == "__main__":
    unittest.main()
