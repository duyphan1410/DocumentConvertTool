"""
Layer 2: Unit Test for Formatting & Heading Logic in EditorView.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.abspath("."))

from src.ui_flet.views.editor_view import EditorView
from src.ui_flet.components.search_replace_bar import SearchReplaceBar


class TestUIFormatting(unittest.TestCase):
    def setUp(self):
        self.search_bar = SearchReplaceBar(
            on_search_changed=lambda e: None,
            on_find_next=lambda e: None,
            on_find_prev=lambda e: None,
            on_replace=lambda e: None,
            on_replace_all=lambda e: None,
        )
        self.editor_view = EditorView(
            search_replace_bar=self.search_bar,
            on_editor_changed=lambda e: None,
            on_toggle_search=lambda e: None,
            on_undo=lambda e: None,
            on_redo=lambda e: None,
            on_clear=lambda e: None,
        )

    def test_apply_formatting_with_selection(self):
        self.editor_view.set_text("Hello World")
        self.editor_view.select_range(6, 11)
        self.editor_view.apply_formatting("**", "**")
        self.assertEqual(self.editor_view.get_text(), "Hello **World**")

    def test_apply_formatting_at_end(self):
        self.editor_view.set_text("Hello World")
        self.editor_view.select_range(11, 11)
        self.editor_view.apply_formatting("**", "**")
        self.assertEqual(self.editor_view.get_text(), "Hello World****")

    def test_apply_heading_h1(self):
        self.editor_view.set_text("My Document Title")
        self.editor_view.apply_heading(1)
        self.assertEqual(self.editor_view.get_text(), "# My Document Title")

    def test_apply_heading_h3(self):
        self.editor_view.set_text("Line 1\n# My Document Title\nLine 3")
        self.editor_view.select_range(7, 26)  # Line 2
        self.editor_view.apply_heading(3)
        self.assertEqual(self.editor_view.get_text(), "Line 1\n### My Document Title\nLine 3")

    def test_reset_heading_level_0(self):
        self.editor_view.set_text("### My Document Title")
        self.editor_view.apply_heading(0)
        self.assertEqual(self.editor_view.get_text(), "My Document Title")



if __name__ == "__main__":
    unittest.main()
