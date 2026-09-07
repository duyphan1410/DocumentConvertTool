"""
Smoke test for PKB Phase 1 UI components & Controllers.
Verifies clean imports, initialization, and contract adherence.
"""
import unittest
import flet as ft
from src.services.metadata_index import MetadataIndex
from src.services.link_parser import extract_tags, extract_wikilinks, find_unlinked_mentions
from src.ui_flet.views.backlink_view import BacklinkView
from src.ui_flet.layout.activity_bar import ActivityBar


class TestPKBUISmoke(unittest.TestCase):
    def test_link_parser_smoke(self):
        text = "Hello #tag1 and #tag-two! Check [[Document Target|Display Note]] and [[BrokenLink]]."
        tags = extract_tags(text)
        self.assertIn("tag1", tags)
        self.assertIn("tag-two", tags)

        wikilinks = extract_wikilinks(text)
        self.assertEqual(len(wikilinks), 2)
        self.assertEqual(wikilinks[0].raw_target, "Document Target")
        self.assertEqual(wikilinks[0].display_text, "Display Note")
        self.assertEqual(wikilinks[1].raw_target, "BrokenLink")

        mentions = find_unlinked_mentions("This text mentions Document Target plainly without brackets.", "Document Target")
        self.assertEqual(len(mentions), 1)
        self.assertEqual(mentions[0].matched_text, "Document Target")

    def test_backlink_view_instantiation(self):
        view = BacklinkView(
            on_open_file=lambda path: None,
            on_convert_mention=lambda path, text: None,
        )
        self.assertIsNotNone(view.content)
        self.assertIsNotNone(view.sections_column)
        self.assertIsNotNone(view.filter_input)

        # Test updating view when no document is active
        view.set_active_document(None)
        self.assertIsNotNone(view.active_doc_text.value)

    def test_activity_bar_backlinks_item(self):
        def dummy_cb(item_id):
            pass

        bar = ActivityBar(on_tab_selected=dummy_cb)
        self.assertIsNotNone(bar.item_backlinks)
        self.assertEqual(bar.item_backlinks.name, "backlinks")

    def test_explorer_tag_filter_visibility_lifecycle(self):
        """Verifies tag filter label and dropdown visibility on init, load, and close workspace."""
        import tempfile
        import shutil
        from src.ui_flet.views.explorer_view import ExplorerView

        tmp_dir = tempfile.mkdtemp()
        try:
            # 1. Initial State (no workspace)
            explorer = ExplorerView(workspace_path=None)
            self.assertFalse(explorer.tag_filter_label.visible)
            self.assertFalse(explorer.tag_filter_dropdown.visible)
            self.assertTrue(explorer.empty_state.visible)

            # 2. Load Workspace State
            explorer.load_workspace(tmp_dir)
            self.assertTrue(explorer.tag_filter_label.visible)
            self.assertTrue(explorer.tag_filter_dropdown.visible)
            self.assertFalse(explorer.empty_state.visible)

            # 3. Close Workspace State (CRITICAL: ensure label is hidden along with dropdown)
            explorer.close_workspace()
            self.assertFalse(explorer.tag_filter_label.visible)
            self.assertFalse(explorer.tag_filter_dropdown.visible)
            self.assertTrue(explorer.empty_state.visible)
        finally:
            shutil.rmtree(tmp_dir)


if __name__ == "__main__":
    unittest.main()
