"""
Unit Test Suite for Model Manager Service.
Validates model catalog, dynamic drive detection, storage calculations,
file verification with vocabulary.txt, and import order safety rule.
"""
import os
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch, MagicMock

from src.services.model_manager import (
    AVAILABLE_MODELS,
    get_models_dir,
    get_target_drive,
    get_storage_usage,
    is_model_installed,
    verify_model_files,
    verify_model_runtime,
    download_model,
    delete_model,
    clean_all_models,
)


class TestModelManager(unittest.TestCase):
    """Test cases for AI model lifecycle and 2-layer verification."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_available_models_catalog(self):
        """Ensures all 3 official Systran models exist in catalog with correct required_files."""
        self.assertIn("whisper-tiny", AVAILABLE_MODELS)
        self.assertIn("whisper-base", AVAILABLE_MODELS)
        self.assertIn("whisper-small", AVAILABLE_MODELS)

        for m_id, meta in AVAILABLE_MODELS.items():
            self.assertTrue(meta.repo_id.startswith("Systran/faster-whisper-"))
            self.assertIn("model.bin", meta.required_files)
            self.assertIn("config.json", meta.required_files)
            self.assertIn("vocabulary.txt", meta.required_files)
            self.assertIn("tokenizer.json", meta.required_files)

    @patch("src.services.model_manager.get_models_dir")
    def test_get_target_drive(self, mock_get_models_dir):
        """Verifies drive detection correctly resolves drive letter."""
        mock_get_models_dir.return_value = r"D:\Profiles\AppData\DocConvert\models"
        drive = get_target_drive()
        self.assertEqual(drive, "D:")

    @patch("src.services.model_manager.get_models_dir")
    def test_is_model_installed_and_verify_files(self, mock_get_models_dir):
        """Tests Layer 1 verification with valid and incomplete files."""
        mock_get_models_dir.return_value = self.temp_dir
        model_dir = os.path.join(self.temp_dir, "whisper-tiny")
        os.makedirs(model_dir, exist_ok=True)

        # Incomplete -> should be False
        self.assertFalse(is_model_installed("whisper-tiny"))

        # Create all required files
        for fname in ["model.bin", "config.json", "vocabulary.txt", "tokenizer.json"]:
            with open(os.path.join(model_dir, fname), "w") as f:
                f.write("mock_content")

        self.assertTrue(is_model_installed("whisper-tiny"))
        self.assertTrue(verify_model_files("whisper-tiny"))

    @patch("src.services.model_manager.get_models_dir")
    def test_storage_usage_calculation(self, mock_get_models_dir):
        """Verifies storage calculation aggregates files accurately."""
        mock_get_models_dir.return_value = self.temp_dir
        m_dir = os.path.join(self.temp_dir, "whisper-base")
        os.makedirs(m_dir, exist_ok=True)

        # Write 1MB file
        with open(os.path.join(m_dir, "model.bin"), "wb") as f:
            f.write(b"0" * (1024 * 1024))

        used_mb, free_gb, drive = get_storage_usage()
        self.assertAlmostEqual(used_mb, 1.0, delta=0.1)
        self.assertGreater(free_gb, 0.0)

    @patch("src.services.model_manager.get_models_dir")
    def test_delete_and_clean_all_models(self, mock_get_models_dir):
        """Tests model deletion and full directory clean-up."""
        mock_get_models_dir.return_value = self.temp_dir
        t_dir = os.path.join(self.temp_dir, "whisper-tiny")
        b_dir = os.path.join(self.temp_dir, "whisper-base")
        os.makedirs(t_dir, exist_ok=True)
        os.makedirs(b_dir, exist_ok=True)

        # Delete single model
        self.assertTrue(delete_model("whisper-tiny"))
        self.assertFalse(os.path.exists(t_dir))
        self.assertTrue(os.path.exists(b_dir))

        # Clean all
        self.assertTrue(clean_all_models())
        self.assertFalse(os.path.exists(b_dir))

    def test_import_order_safety_rule(self):
        """
        Validates the runtime safety rule:
        Import numpy before importing ctranslate2 or faster_whisper.
        """
        # Execute in sequence
        import numpy as np
        import ctranslate2
        from faster_whisper import WhisperModel

        self.assertIsNotNone(np.__version__)
        self.assertIsNotNone(ctranslate2.__version__)
        self.assertIsNotNone(WhisperModel)


if __name__ == "__main__":
    unittest.main()
