import unittest
import os
import flet as ft
from unittest.mock import MagicMock
from src.ui_flet.components.quick_open_dialog import QuickOpenDialog


class TestQuickOpenDialog(unittest.TestCase):
    def setUp(self):
        self.workspace_dir = os.path.abspath("src")
        self.selected_path = None

        def on_selected(path):
            self.selected_path = path

        self.dialog = QuickOpenDialog(
            get_workspace_path=lambda: self.workspace_dir,
            on_file_selected=on_selected,
        )

    def test_scan_and_filter(self):
        self.dialog._scan_workspace()
        self.assertTrue(len(self.dialog._all_files) > 0)

        # Filter by a known file part
        self.dialog._filter_and_render("app.py")
        self.assertTrue(any("app.py" in p[2] for p in self.dialog._filtered_files))

    def test_submit_first(self):
        self.dialog._scan_workspace()
        self.dialog._filter_and_render("app.py")
        self.dialog._on_submit_first(None)
        self.assertIsNotNone(self.selected_path)
        self.assertTrue(self.selected_path.endswith("app.py"))


if __name__ == "__main__":
    unittest.main()
