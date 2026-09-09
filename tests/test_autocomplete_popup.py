"""
Unit tests for AutocompletePopup and EditorView autocomplete trigger detection (PKB Phase 1.5).
"""
import unittest
from unittest.mock import MagicMock
import flet as ft
from src.ui_flet.components.autocomplete_popup import AutocompletePopup
from src.ui_flet.views.editor_view import EditorView
from src.ui_flet.components.search_replace_bar import SearchReplaceBar


class TestAutocompletePopup(unittest.TestCase):
    def test_popup_initialization_and_show_hide(self):
        selected_items = []

        def on_select(mode, item):
            selected_items.append((mode, item))

        popup = AutocompletePopup(on_select_suggestion=on_select)
        self.assertFalse(popup.visible)

        # Show wikilinks
        items = [
            {"title": "Note Alpha", "path": "/path/to/alpha.md", "relative_path": "alpha.md"},
            {"title": "Note Beta", "path": "/path/to/beta.md", "relative_path": "beta.md"},
        ]
        popup.show_suggestions(mode="wikilink", items=items, query="Note")
        self.assertTrue(popup.visible)
        self.assertEqual(len(popup.list_view.controls), 2)
        self.assertEqual(popup.mode, "wikilink")

        # Select item
        popup._handle_click_item(items[0])
        self.assertFalse(popup.visible)
        self.assertEqual(len(selected_items), 1)
        self.assertEqual(selected_items[0], ("wikilink", items[0]))

    def test_popup_tag_mode(self):
        selected_items = []
        popup = AutocompletePopup(on_select_suggestion=lambda m, it: selected_items.append((m, it)))

        tags = [
            {"name": "ai", "doc_count": 5},
            {"name": "python", "doc_count": 2},
        ]
        popup.show_suggestions(mode="tag", items=tags, query="ai")
        self.assertTrue(popup.visible)
        self.assertEqual(popup.mode, "tag")

        popup.select_current()
        self.assertFalse(popup.visible)
        self.assertEqual(len(selected_items), 1)
        self.assertEqual(selected_items[0], ("tag", tags[0]))

    def test_editor_view_autocomplete_trigger_detection(self):
        search_bar = MagicMock(spec=SearchReplaceBar)
        search_bar.results_container = ft.Container()
        on_change = MagicMock()

        editor_view = EditorView(
            search_replace_bar=search_bar,
            on_editor_changed=on_change,
        )

        # 1. Test Wikilink trigger [[
        editor_view.editor.value = "Hello [[Note"
        editor_view.selection_start = 12
        editor_view.selection_end = 12
        editor_view.check_autocomplete_trigger()
        self.assertEqual(editor_view.autocomplete_popup.mode, "wikilink")

        # 2. Test Tag trigger #
        editor_view.editor.value = "Some text #tag"
        editor_view.selection_start = 14
        editor_view.selection_end = 14
        editor_view.check_autocomplete_trigger()
        self.assertEqual(editor_view.autocomplete_popup.mode, "tag")

        # 3. Test Markdown heading does NOT trigger tag popup
        editor_view.editor.value = "# Heading One"
        editor_view.selection_start = 13
        editor_view.selection_end = 13
        editor_view.check_autocomplete_trigger()
        self.assertFalse(editor_view.autocomplete_popup.visible)

    def test_estimate_cursor_position_unikey_replacement(self):
        search_bar = MagicMock(spec=SearchReplaceBar)
        search_bar.results_container = ft.Container()
        editor_view = EditorView(
            search_replace_bar=search_bar,
            on_editor_changed=MagicMock(),
        )

        # Unikey Telex: typing [ produces ơ, typing second [ replaces ơ with [[
        old_val = "Hello ơ"
        new_val = "Hello [["
        pos = editor_view._estimate_cursor_position(old_val, new_val)
        self.assertEqual(pos, len(new_val))  # Position should be at the end of [[

        # Replacement in the middle of a line
        old_mid = "Hello ơ world"
        new_mid = "Hello [[ world"
        pos_mid = editor_view._estimate_cursor_position(old_mid, new_mid)
        self.assertEqual(pos_mid, len("Hello [["))


if __name__ == "__main__":
    unittest.main()
