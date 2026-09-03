"""
Unit Tests for Whisper AI Core Engine (whisper_service) and AudioModule.
Validates safe import order, audio preprocessing, Markdown metadata formatting,
and module registry integration.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from src.core.registry import ModuleRegistry
from src.modules.audio_module import AudioModule
from src.services.whisper_service import (
    get_best_installed_model,
    get_optimal_device_and_compute_type,
    transcribe_file,
)


class TestWhisperService(unittest.TestCase):
    def test_import_order_safety(self):
        """
        Verify that importing numpy before ctranslate2 is safe and does not trigger segfaults.
        """
        import numpy as np
        import ctranslate2
        self.assertTrue(hasattr(np, "ndarray"))
        self.assertTrue(hasattr(ctranslate2, "StorageView"))

    def test_audio_module_registered(self):
        """
        Verify AudioModule is properly registered in ModuleRegistry for all media extensions.
        """
        module = ModuleRegistry.get_module_by_extension(".mp3")
        self.assertIsNotNone(module)
        self.assertEqual(module.name, "Audio")

        for ext in [".mp3", ".wav", ".m4a", ".mp4", ".mkv", ".flac", ".aac", ".webm"]:
            mod = ModuleRegistry.get_module_by_extension(ext)
            self.assertIsNotNone(mod, f"Expected module for {ext}")
            self.assertEqual(mod.name, "Audio")

    def test_audio_module_dependency_names(self):
        """
        Verify AudioModule declares required dependencies properly.
        """
        module = AudioModule()
        self.assertIn("faster-whisper", module.required_dependencies)
        self.assertIn("av", module.required_dependencies)

    def test_optimal_device_cpu_fallback(self):
        """
        Verify that device detection returns CPU int8 when no usable CUDA GPU is available.
        """
        with patch("src.services.hardware_detector.get_hardware_info") as mock_hw:
            mock_info = MagicMock()
            mock_info.cuda_usable = False
            mock_info.vram_free_mb = 0
            mock_hw.return_value = mock_info

            device, compute_type = get_optimal_device_and_compute_type()
            self.assertEqual(device, "cpu")
            self.assertEqual(compute_type, "int8")

    def test_optimal_device_cuda_selection(self):
        """
        Verify that device detection returns CUDA float16 when an NVIDIA GPU with usable CUDA is available.
        """
        with patch("src.services.hardware_detector.get_hardware_info") as mock_hw:
            mock_info = MagicMock()
            mock_info.cuda_usable = True
            mock_info.vram_free_mb = 4000
            mock_hw.return_value = mock_info

            device, compute_type = get_optimal_device_and_compute_type()
            self.assertEqual(device, "cuda")
            self.assertEqual(compute_type, "float16")

    def test_transcribe_file_not_found(self):
        """
        Verify error handling when audio file does not exist.
        """
        success, content, err = transcribe_file("non_existent_file.mp3")
        self.assertFalse(success)
        self.assertEqual(err, "ERR_FILE_NOT_FOUND")

    @patch("src.services.whisper_service.get_best_installed_model")
    def test_transcribe_no_local_model(self, mock_model):
        """
        Verify error handling when no Whisper model is installed locally.
        """
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        temp_file.close()

        try:
            mock_model.return_value = None
            success, content, err = transcribe_file(temp_file.name)
            self.assertFalse(success)
            self.assertEqual(err, "ERR_NO_LOCAL_MODEL")
        finally:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)

    @patch("src.services.whisper_service.transcribe_audio_whisper")
    @patch("src.services.whisper_service.get_best_installed_model")
    def test_transcribe_file_success(self, mock_model, mock_transcribe):
        """
        Verify successful transcription produces formatted Markdown with metadata table and timestamps.
        """
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        temp_file.write(b"dummy audio content")
        temp_file.close()

        try:
            mock_model.return_value = "whisper-base"
            mock_transcribe.return_value = (
                [
                    (0.0, "Chào các bạn."),
                    (3.0, "Hôm nay chúng ta sẽ tìm hiểu về Whisper AI."),
                    (20.0, "Đây là đoạn văn thứ hai sau khoảng lặng."),
                ],
                "vi",
            )

            success, content, err = transcribe_file(
                file_path=temp_file.name,
                model_id="whisper-base",
                language="vi",
                include_timestamps=True,
            )

            from src.i18n import t
            self.assertTrue(success)
            self.assertIsNone(err)
            self.assertIn(f"| {t('transcript.info_table_info')} | {t('transcript.info_table_detail')} |", content)
            self.assertIn(f"**{t('transcript.info_ai_model')}**", content)
            self.assertIn("Tiếng Việt (vi)", content)
            self.assertIn(f"## {t('transcript.section_speech_transcript')}", content)
            self.assertIn("[00:00]", content)
            self.assertIn("Chào các bạn.", content)
            self.assertIn("[00:20]", content)
            self.assertIn("Đây là đoạn văn thứ hai", content)
        finally:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)

    def test_show_transcribe_dialog_instantiation(self):
        """
        Verify show_transcribe_dialog can be initialized without theme or import errors.
        """
        import flet as ft
        from src.ui_flet.components.transcribe_dialog import show_transcribe_dialog

        mock_page = MagicMock(spec=ft.Page)
        mock_page.overlay = []
        mock_page.theme_mode = ft.ThemeMode.DARK
        mock_callback = MagicMock()

        show_transcribe_dialog(
            page=mock_page,
            current_palette="Violet Cyberpunk",
            on_success=mock_callback,
        )
        self.assertTrue(len(mock_page.overlay) > 0)
        self.assertTrue(any(isinstance(c, ft.AlertDialog) for c in mock_page.overlay))


if __name__ == "__main__":
    unittest.main()
