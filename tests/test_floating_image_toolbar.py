"""
Unit tests for FloatingImageToolbar component and is_dirty undo baseline tracking.
"""
import unittest
import flet as ft
from unittest.mock import MagicMock

from src.ui_flet.components.floating_image_toolbar import FloatingImageToolbar
from src.ui_flet.helpers.image_token_helper import ImageTokenInfo
from src.ui_flet.state import AppState, DocumentTabState
from src.ui_flet.controllers.editor_controller import EditorController
from src.ui_flet.views.editor_view import EditorView
from src.ui_flet.views.preview_view import MarkdownPreview
from src.ui_flet.components.search_replace_bar import SearchReplaceBar


class TestFloatingImageToolbar(unittest.TestCase):
    def test_toolbar_initialization_and_visibility(self):
        toolbar = FloatingImageToolbar()
        self.assertFalse(toolbar.visible)
        self.assertIsNotNone(toolbar.btn_p25)
        self.assertIsNotNone(toolbar.btn_p50)
        self.assertIsNotNone(toolbar.btn_p75)
        self.assertIsNotNone(toolbar.btn_p100)
        self.assertIsNotNone(toolbar.btn_align_left)
        self.assertIsNotNone(toolbar.btn_align_center)
        self.assertIsNotNone(toolbar.btn_align_right)

    def test_toolbar_set_image_context(self):
        toolbar = FloatingImageToolbar()
        tok = ImageTokenInfo(
            raw_token="![Sample Photo](images/chart.png)",
            start=0,
            end=33,
            src="images/chart.png",
            alt="Sample Photo",
            width="50%",
            align="center",
        )
        toolbar.set_image_context(tok)
        self.assertTrue(toolbar.visible)
        self.assertEqual(toolbar.badge_label.value, "chart.png")
        self.assertEqual(toolbar.current_token, tok)

        # Clear context
        toolbar.set_image_context(None)
        self.assertFalse(toolbar.visible)
        self.assertIsNone(toolbar.current_token)

    def test_toolbar_callbacks(self):
        presets = []
        aligns = []
        custom_called = []
        replace_called = []
        reset_called = []
        dismiss_called = []

        toolbar = FloatingImageToolbar(
            on_preset_click=lambda p: presets.append(p),
            on_align_click=lambda a: aligns.append(a),
            on_custom_click=lambda: custom_called.append(True),
            on_replace_click=lambda: replace_called.append(True),
            on_reset_click=lambda: reset_called.append(True),
            on_dismiss_click=lambda: dismiss_called.append(True),
        )

        toolbar._handle_preset("75%")
        self.assertEqual(presets, ["75%"])

        toolbar._handle_align("right")
        self.assertEqual(aligns, ["right"])

        toolbar._handle_custom()
        self.assertEqual(custom_called, [True])

        toolbar._handle_replace()
        self.assertEqual(replace_called, [True])

        toolbar._handle_reset()
        self.assertEqual(reset_called, [True])

        toolbar._handle_dismiss()
        self.assertEqual(dismiss_called, [True])
        self.assertFalse(toolbar.visible)


class TestIsDirtyUndoBaseline(unittest.TestCase):
    def setUp(self):
        self.state = AppState()
        tab = self.state.create_tab(title="Doc1.md", activate=True)
        tab.saved_content = "Original baseline content"
        tab.full_content = "Original baseline content"
        tab.is_dirty = False

        self.mock_tab_bar = MagicMock()
        self.mock_search_bar = SearchReplaceBar(
            on_search_changed=lambda e: None,
            on_find_next=lambda e: None,
            on_find_prev=lambda e: None,
            on_replace=lambda e: None,
            on_replace_all=lambda e: None,
        )
        self.editor_view = EditorView(
            search_replace_bar=self.mock_search_bar,
            on_editor_changed=lambda e: self.editor_controller.on_editor_changed(e),
        )
        self.preview = MarkdownPreview()

        self.mock_footer = MagicMock()
        self.mock_page = MagicMock()
        self.editor_controller = EditorController(
            page=self.mock_page,
            state=self.state,
            app_controls={
                "editor_view": self.editor_view,
                "preview": self.preview,
                "footer_bar": self.mock_footer,
                "workspace_tab_bar": self.mock_tab_bar,
            },
        )
        self.editor_view.set_text("Original baseline content")
        self.state.undo_stack.clear()
        self.state.undo_stack.append("Original baseline content")

    def test_typing_sets_dirty_and_undo_clears_dirty(self):
        # 1. Initially not dirty
        self.assertFalse(self.state.is_dirty)

        # 2. Type new text -> becomes dirty
        self.editor_view.editor.value = "Original baseline content - edited"
        self.editor_controller.on_editor_changed()
        self.assertTrue(self.state.is_dirty)
        self.assertTrue(self.state.active_tab.is_dirty)

        # 3. Undo -> returns to baseline -> is_dirty becomes False!
        self.editor_controller.perform_undo()
        self.assertEqual(self.editor_view.get_text(), "Original baseline content")
        self.assertFalse(self.state.is_dirty)
        self.assertFalse(self.state.active_tab.is_dirty)

        # 4. Redo -> becomes dirty again
        self.editor_controller.perform_redo()
        self.assertEqual(self.editor_view.get_text(), "Original baseline content - edited")
        self.assertTrue(self.state.is_dirty)
        self.assertTrue(self.state.active_tab.is_dirty)


if __name__ == "__main__":
    unittest.main()
