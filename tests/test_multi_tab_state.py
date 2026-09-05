"""
Comprehensive Unit Tests for Multi-Tab AppState, DocumentTabState, Property Delegation,
and Session Isolation in DocumentConvertTool.
"""
import os
import shutil
import tempfile
import unittest

from src.ui_flet.state import AppState, DocumentTabState
from src.services.media_asset_manager import MediaAssetManager
from src.ui_flet.constants import DRAFTS_DIR, TAB_SESSION_PATH


class TestDocumentTabState(unittest.TestCase):
    def test_default_initialization(self):
        tab = DocumentTabState()
        self.assertTrue(tab.tab_id.startswith("tab_"))
        self.assertEqual(tab.in_path, "")
        self.assertEqual(tab.out_path, "")
        self.assertEqual(tab.title, "Untitled")
        self.assertEqual(tab.full_content, "")
        self.assertFalse(tab.is_dirty)
        self.assertFalse(tab.is_orphaned)
        self.assertEqual(tab.media_session_id, f"session_{tab.tab_id}")

    def test_initialization_with_path(self):
        tab = DocumentTabState(in_path="/path/to/my_doc.md")
        self.assertEqual(tab.in_path, "/path/to/my_doc.md")
        self.assertEqual(tab.title, "my_doc.md")


class TestAppStatePropertyDelegation(unittest.TestCase):
    def test_empty_tabs_safe_fallbacks(self):
        """When AppState has 0 tabs, all delegated properties must safely return defaults without throwing."""
        state = AppState()
        self.assertIsNone(state.active_tab)
        self.assertEqual(state.in_path, "")
        self.assertEqual(state.out_path, "")
        self.assertEqual(state.last_converted_path, "")
        self.assertEqual(state.current_mode, "MD -> Excel")
        self.assertEqual(state.full_content, "")
        self.assertFalse(state.is_dirty)
        self.assertFalse(state.is_orphaned)
        self.assertEqual(state.undo_stack, [])
        self.assertEqual(state.redo_stack, [])
        self.assertFalse(state.is_undo_redo_op)
        self.assertEqual(state.search_matches, [])
        self.assertEqual(state.current_match_idx, -1)

    def test_single_tab_property_delegation(self):
        """Setters/getters on AppState should transparently mutate and read from the active tab."""
        state = AppState()
        tab = state.create_tab(title="Tab1")
        self.assertEqual(state.active_tab, tab)

        # In path
        state.in_path = "C:/docs/report.md"
        self.assertEqual(state.in_path, "C:/docs/report.md")
        self.assertEqual(tab.in_path, "C:/docs/report.md")

        # Content
        state.full_content = "# Hello Multi-Tab"
        self.assertEqual(state.full_content, "# Hello Multi-Tab")
        self.assertEqual(tab.full_content, "# Hello Multi-Tab")

        # Dirty & Orphaned
        state.is_dirty = True
        state.is_orphaned = True
        self.assertTrue(state.is_dirty)
        self.assertTrue(state.is_orphaned)
        self.assertTrue(tab.is_dirty)
        self.assertTrue(tab.is_orphaned)

        # Undo stack
        state.undo_stack.append("prev_text")
        self.assertEqual(state.undo_stack, ["prev_text"])
        self.assertEqual(tab.undo_stack, ["prev_text"])

    def test_multi_tab_context_switch(self):
        """Property delegation must track active_tab accurately when switching tabs."""
        state = AppState()
        tab1 = state.create_tab(title="Doc 1", content="Content 1")
        tab2 = state.create_tab(title="Doc 2", content="Content 2")

        # Tab 2 is active by default
        self.assertEqual(state.active_tab_id, tab2.tab_id)
        self.assertEqual(state.full_content, "Content 2")

        # Switch to Tab 1
        state.activate_tab(tab1.tab_id)
        self.assertEqual(state.active_tab_id, tab1.tab_id)
        self.assertEqual(state.full_content, "Content 1")

        # Mutate while Tab 1 is active
        state.full_content = "Updated Content 1"
        self.assertEqual(tab1.full_content, "Updated Content 1")
        self.assertEqual(tab2.full_content, "Content 2")


class TestTabLifecycleAndGuards(unittest.TestCase):
    def test_find_tab_by_path_guard(self):
        """find_tab_by_path MUST return None for empty string to prevent Untitled false positives."""
        state = AppState()
        state.create_tab(title="Untitled 1")
        state.create_tab(title="Untitled 2")

        self.assertIsNone(state.find_tab_by_path(""))
        self.assertIsNone(state.find_tab_by_path("   "))

    def test_find_tab_by_valid_path(self):
        state = AppState()
        tab1 = state.create_tab(in_path="C:/project/readme.md")
        tab2 = state.create_tab(in_path="C:/project/notes.txt")

        self.assertEqual(state.find_tab_by_path("C:/project/readme.md"), tab1)
        self.assertEqual(state.find_tab_by_path("c:/project/README.MD"), tab1)
        self.assertEqual(state.find_tab_by_path("C:\\project\\notes.txt"), tab2)
        self.assertIsNone(state.find_tab_by_path("C:/project/other.md"))

    def test_close_tab_and_active_tab_rebalancing(self):
        state = AppState()
        tab1 = state.create_tab(title="Tab 1")
        tab2 = state.create_tab(title="Tab 2")
        tab3 = state.create_tab(title="Tab 3")

        state.activate_tab(tab2.tab_id)
        self.assertEqual(state.active_tab_id, tab2.tab_id)

        # Close active Tab 2 -> should rebalance to neighboring Tab 3 (at index 1)
        state.close_tab(tab2.tab_id)
        self.assertEqual(len(state.tabs), 2)
        self.assertEqual(state.active_tab_id, tab3.tab_id)

        # Close Tab 3 -> should rebalance to Tab 1
        state.close_tab(tab3.tab_id)
        self.assertEqual(len(state.tabs), 1)
        self.assertEqual(state.active_tab_id, tab1.tab_id)

        # Close Tab 1 -> 0 tabs left
        state.close_tab(tab1.tab_id)
        self.assertEqual(len(state.tabs), 0)
        self.assertIsNone(state.active_tab_id)
        self.assertIsNone(state.active_tab)

    def test_reorder_tabs(self):
        state = AppState()
        tab1 = state.create_tab(title="Tab 1")
        tab2 = state.create_tab(title="Tab 2")
        tab3 = state.create_tab(title="Tab 3")

        # Move Tab 3 to index 0
        state.reorder_tabs(tab3.tab_id, tab1.tab_id)
        self.assertEqual([t.tab_id for t in state.tabs], [tab3.tab_id, tab1.tab_id, tab2.tab_id])


class TestMediaAssetManagerSessionIsolation(unittest.TestCase):
    def test_multi_session_directories(self):
        manager = MediaAssetManager()
        session1_dir = manager.get_session_dir(session_id="session_tab_1")
        session2_dir = manager.get_session_dir(session_id="session_tab_2")

        self.assertTrue(os.path.exists(session1_dir))
        self.assertTrue(os.path.exists(session2_dir))
        self.assertNotEqual(session1_dir, session2_dir)
        self.assertIn("session_tab_1", session1_dir)
        self.assertIn("session_tab_2", session2_dir)

        # Image registration in session 1
        fake_bytes = b"PNG_IMAGE_DATA_123"
        img1 = manager.register_image(fake_bytes, "img1.png", session_id="session_tab_1")
        self.assertTrue(os.path.exists(img1))
        self.assertIn("session_tab_1", img1)

        # Clear session 1
        manager.clear_session("session_tab_1")
        self.assertFalse(os.path.exists(session1_dir))
        self.assertTrue(os.path.exists(session2_dir))

        # Cleanup session 2
        manager.clear_session("session_tab_2")

    def test_resolve_uri_cross_session_bleed_prevention(self):
        """Verifies that resolve_uri with @media/ never leaks or resolves images from another tab's session."""
        manager = MediaAssetManager()
        # Session A registers image1.png
        manager.register_image(b"CAT_IMAGE", "image1.png", session_id="session_tab_A")

        # Session B tries to resolve @media/image1.png (which does NOT exist in session B)
        resolved_b = manager.resolve_uri("@media/image1.png", session_id="session_tab_B")

        # Must point to session B's path, NOT session A's cat image
        expected_b = os.path.normpath(os.path.join(manager.get_session_dir("session_tab_B"), "image1.png"))
        self.assertEqual(resolved_b, expected_b)
        self.assertNotIn("session_tab_A", resolved_b)

        # Cleanup
        manager.clear_session("session_tab_A")
        manager.clear_session("session_tab_B")


if __name__ == "__main__":
    unittest.main()

