"""
Unit tests for Unified Background TranscriptionManager, Cancellation, and Tab Disambiguation.
"""
import asyncio
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import flet as ft

from src.services.transcription_manager import (
    TranscriptionJobManager,
    TranscriptionJob,
    JobStatus,
)
from src.ui_flet.state import AppState
from src.ui_flet.controllers.file_controller import FileController


class TestTranscriptionManager(unittest.TestCase):
    def setUp(self):
        # Reset singleton instance for test isolation
        TranscriptionJobManager._instance = None
        self.manager = TranscriptionJobManager.get_instance()

    def tearDown(self):
        TranscriptionJobManager._instance = None

    def test_job_lifecycle_success(self):
        """Tests successful job submission, execution, progress dispatch, and completion."""
        received_progress = []

        def mock_worker(job: TranscriptionJob, progress_cb):
            progress_cb("Processing audio...", 0.5)
            progress_cb("Transcribing with Whisper...", 0.9)
            return True, "# Video Title\n\nSample transcript content.", None

        success_result = []

        def on_success(content, source, title):
            success_result.append((content, source, title))

        job = self.manager.submit_job(
            job_type="youtube",
            source="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            display_name="Test Video",
            execution_fn=mock_worker,
            on_success=on_success,
        )

        def listener(j):
            received_progress.append((j.status, j.stage_message, j.progress))

        job.subscribe(listener)

        # Wait for worker execution to complete
        start = time.time()
        while job.status == JobStatus.RUNNING or job.status == JobStatus.QUEUED:
            time.sleep(0.05)
            if time.time() - start > 5.0:
                self.fail("Job execution timed out")

        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertEqual(job.progress, 1.0)
        self.assertIn("# Video Title", job.result_markdown)
        self.assertEqual(len(success_result), 1)
        self.assertFalse(self.manager.is_running())

    def test_job_cancellation_and_temp_cleanup(self):
        """Tests canceling a running job and verifying temporary file cleanup."""
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, "test_audio.m4a")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write("dummy audio stream data")

        self.assertTrue(os.path.isfile(temp_file))

        def slow_worker(job: TranscriptionJob, progress_cb):
            job.temp_files.append(temp_file)
            job.temp_files.append(temp_dir)
            progress_cb("Downloading...", 0.2)
            # Simulate long running work checking cancel_event
            for _ in range(50):
                if job.cancel_event.is_set():
                    return False, "", "ERR_CANCELLED"
                time.sleep(0.05)
            return True, "Done", None

        job = self.manager.submit_job(
            job_type="drive",
            source="https://drive.google.com/file/d/123",
            display_name="Large Drive Video",
            execution_fn=slow_worker,
        )

        time.sleep(0.1)
        self.assertTrue(self.manager.is_running())

        # Cancel the job
        cancelled = self.manager.cancel_job(job.job_id)
        self.assertTrue(cancelled)

        time.sleep(0.2)
        self.assertIn(job.status, (JobStatus.CANCELLED, JobStatus.FAILED))
        # Temp files must be cleaned
        self.assertFalse(os.path.exists(temp_file))

    def test_job_type_filtering(self):
        """Tests that get_active_job properly filters by job_types."""
        def dummy_worker(job, cb):
            time.sleep(0.3)
            return True, "Content", None

        job = self.manager.submit_job(
            job_type="local_media",
            source="C:/test.mp3",
            display_name="test.mp3",
            execution_fn=dummy_worker,
        )

        time.sleep(0.05)
        # Should be found when querying local_media
        self.assertIsNotNone(self.manager.get_active_job(job_types=["local_media"]))
        # Should NOT be found when querying youtube/drive
        self.assertIsNone(self.manager.get_active_job(job_types=["youtube", "drive"]))

    def test_transcript_tab_disambiguation_and_non_intrusive(self):
        """Tests tab creation disambiguation (e.g. video.md -> video (1).md) and focus preservation."""
        page = MagicMock(spec=ft.Page)
        state = AppState()
        
        # User is actively editing on Tab 1 with dirty content
        tab1 = state.create_tab(title="video.md", content="Existing custom notes", activate=True)
        tab1.is_dirty = True
        
        app_controls = {
            "ribbon_bar": MagicMock(),
            "editor_view": MagicMock(),
            "preview": MagicMock(),
            "file_path_bar": MagicMock(),
            "footer_bar": MagicMock(),
            "workspace_tab_bar": MagicMock(),
            "file_picker_in": MagicMock(),
            "file_picker_out": MagicMock(),
        }
        app_controls["ribbon_bar"].mode_dropdown = MagicMock()
        app_controls["ribbon_bar"].mode_dropdown.value = "MD -> Markdown"
        
        controller = FileController(page=page, state=state, app_controls=app_controls)
        controller.save_tab_session = MagicMock()
        
        # New transcript arrives with identical name "video.md"
        controller.handle_youtube_transcript_loaded(
            content="# video\nNew transcript",
            source_url="https://youtube.com/watch?v=123",
        )
        
        # Must create a 2nd tab named "video (1).md" in background without changing active_tab_id
        self.assertEqual(len(state.tabs), 2)
        self.assertEqual(state.tabs[0].title, "video.md")
        self.assertEqual(state.tabs[1].title, "video (1).md")
        # Active tab must still be Tab 1 (focus preserved!)
        self.assertEqual(state.active_tab_id, tab1.tab_id)


if __name__ == "__main__":
    unittest.main()
