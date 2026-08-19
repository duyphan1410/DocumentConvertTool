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
        self.assertFalse(dialog.modal)

    def test_show_youtube_dialog_cleans_stale_dialogs(self):
        stale_dialog = ft.AlertDialog()
        self.page.overlay.append(stale_dialog)

        show_youtube_dialog(
            page=self.page,
            on_transcript_loaded=self.callback,
        )
        self.assertEqual(len(self.page.overlay), 1)
    def test_handle_youtube_transcript_loaded_switches_mode_to_save_as_md(self):
        from src.ui_flet.controllers.file_controller import FileController
        from src.ui_flet.state import AppState

        state = AppState()
        state.default_mode = "MD -> JSON"  # Non-default setting
        app_controls = {
            "ribbon_bar": MagicMock(),
            "editor_view": MagicMock(),
            "preview": MagicMock(),
            "file_path_bar": MagicMock(),
            "footer_bar": MagicMock(),
            "file_picker_in": MagicMock(),
            "file_picker_out": MagicMock(),
        }
        app_controls["ribbon_bar"].mode_dropdown = MagicMock()
        app_controls["ribbon_bar"].mode_dropdown.value = "MD -> Markdown"

        controller = FileController(page=self.page, state=state, app_controls=app_controls)
        controller.handle_youtube_transcript_loaded(
            content="# Video Title\nTranscript content here",
            source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )

        app_controls["ribbon_bar"].update_mode_options.assert_called_once_with(
            ".md", preferred_mode="MD -> Markdown"
        )
        self.assertEqual(state.current_mode, "MD -> Markdown")


if __name__ == "__main__":
    unittest.main()
