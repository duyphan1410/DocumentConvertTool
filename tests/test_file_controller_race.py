"""
Unit tests specifically simulating async race conditions and generation token discarding
in FileController.open_file_by_path.
"""
import asyncio
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from src.ui_flet.state import AppState, DocumentTabState
from src.ui_flet.controllers.file_controller import FileController
from src.services.file_loader import LoadResult


class AsyncRaceConditionTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.state = AppState()
        self.page = MagicMock()
        self.page.overlay = []
        self.ribbon_bar = MagicMock()
        self.ribbon_bar.mode_dropdown = MagicMock(value="PDF -> MD")
        self.editor_view = MagicMock()
        self.preview = MagicMock()
        self.preview.doc_info_text = MagicMock()
        self.file_path_bar = MagicMock()
        self.footer_bar = MagicMock()

        self.app_controls = {
            "file_path_bar": self.file_path_bar,
            "editor_view": self.editor_view,
            "preview": self.preview,
            "footer_bar": self.footer_bar,
            "ribbon_bar": self.ribbon_bar,
            "file_picker_in": MagicMock(),
            "file_picker_out": MagicMock(),
            "workspace_tab_bar": MagicMock(),
        }

        self.controller = FileController(
            page=self.page,
            state=self.state,
            app_controls=self.app_controls,
        )
        self.controller.perform_autosave = MagicMock()
        self.controller.save_tab_session = MagicMock()

        self.temp_dir = tempfile.TemporaryDirectory()
        self.pdf_file = os.path.join(self.temp_dir.name, "sample.pdf")
        with open(self.pdf_file, "w", encoding="utf-8") as f:
            f.write("fake pdf")

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_stale_slow_load_discarded_by_newer_fast_load(self):
        """
        Simulates:
        1. Task 1 (regular PDF) starts loading slowly (takes 0.15s, returns SLOW_OLD).
        2. Task 2 (PDF Scan) triggered immediately after (takes 0.03s, returns FAST_NEW).
        3. Task 2 finishes first, then Task 1 finishes later.
        Verification:
        - target_tab.full_content MUST be FAST_NEW.
        - target_tab.load_generation MUST be 2.
        - SLOW_OLD MUST NOT overwrite the tab or UI editor.
        """
        call_count = [0]

        def mock_load_document(path, session_id=None, module_name=None, progress_callback=None):
            call_count[0] += 1
            current_call = call_count[0]
            if current_call == 1:
                # Simulating slow standard parser
                time.sleep(0.15)
                return LoadResult(
                    content="=== SLOW_OLD_REGULAR_PDF ===",
                    success=True,
                    path=path,
                    mode="PDF -> MD",
                )
            else:
                # Simulating faster subsequent parser/scan
                time.sleep(0.03)
                return LoadResult(
                    content="=== FAST_NEW_PDF_SCAN ===",
                    success=True,
                    path=path,
                    mode="PDF Scan -> MD",
                )

        with patch("src.ui_flet.controllers.file_controller.load_document", side_effect=mock_load_document), \
             patch("src.ui_flet.controllers.file_controller.process_markdown_media_async", side_effect=lambda c, **kw: c):

            # Dispatch task 1 (slow) and task 2 (fast) concurrently on the same tab
            task1 = asyncio.create_task(self.controller.open_file_by_path(self.pdf_file))
            # Yield event loop briefly so task 1 creates tab and spawns thread
            await asyncio.sleep(0.01)

            # Switch mode and trigger reload (task 2)
            self.ribbon_bar.mode_dropdown.value = "PDF Scan -> MD"
            task2 = asyncio.create_task(self.controller.open_file_by_path(self.pdf_file, force_reload=True))

            # Wait for both tasks to resolve
            await asyncio.gather(task1, task2)

        tab = self.state.active_tab
        self.assertIsNotNone(tab)
        self.assertEqual(tab.load_generation, 2)
        # Content MUST be from task 2, not overwritten by the slower task 1
        self.assertEqual(tab.full_content, "=== FAST_NEW_PDF_SCAN ===")
        self.assertEqual(tab.current_mode, "PDF Scan -> MD")


if __name__ == "__main__":
    unittest.main()
