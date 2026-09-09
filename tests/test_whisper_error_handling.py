import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from src.services.whisper_service import transcribe_file, transcribe_audio_whisper
from src.services.model_manager import get_model_path


class TestWhisperErrorHandling(unittest.TestCase):
    @patch("src.services.whisper_service.get_best_installed_model", return_value=None)
    @patch("os.path.exists", return_value=True)
    def test_transcribe_file_no_local_model(self, mock_exists, mock_get_model):
        """Verify proper error code when no model is downloaded."""
        success, content, err = transcribe_file("test_audio.mp3", model_id=None)
        self.assertFalse(success)
        self.assertEqual(content, "")
        self.assertEqual(err, "ERR_NO_LOCAL_MODEL")

    @patch("src.services.whisper_service.get_best_installed_model", return_value="whisper-base")
    @patch("src.services.whisper_service.transcribe_audio_whisper", side_effect=RuntimeError("CUDA out of memory error"))
    @patch("os.path.exists", return_value=True)
    def test_transcribe_file_propagates_technical_error(self, mock_exists, mock_transcribe, mock_model):
        """Verify technical exceptions are reported accurately via i18n instead of masking as NO_SPEECH_DETECTED."""
        from src.i18n import set_locale

        # Test Vietnamese locale
        set_locale("vi")
        success_vi, _, err_vi = transcribe_file("test_audio.mp3", model_id="whisper-base")
        self.assertFalse(success_vi)
        self.assertIn("Lỗi kỹ thuật", err_vi)
        self.assertIn("CUDA out of memory error", err_vi)

        # Test English locale
        set_locale("en")
        success_en, _, err_en = transcribe_file("test_audio.mp3", model_id="whisper-base")
        self.assertFalse(success_en)
        self.assertIn("Technical error", err_en)
        self.assertIn("CUDA out of memory error", err_en)
        self.assertNotEqual(err_en, "ERR_NO_SPEECH_DETECTED")

    @patch("src.services.model_manager.get_model_path", return_value="C:/test/models/whisper-base")
    @patch("os.path.isdir", return_value=True)
    def test_transcribe_vad_fallback_retry(self, mock_isdir, mock_model_path):
        """Verify that if VAD filtering fails, it automatically retries with vad_filter=False."""
        with patch("faster_whisper.WhisperModel") as MockWhisperModel:
            mock_model_instance = MagicMock()
            MockWhisperModel.return_value = mock_model_instance

            # First call with vad_filter=True raises an error (simulating missing silero_vad / onnxruntime)
            # Second call with vad_filter=False succeeds
            seg_mock = MagicMock()
            seg_mock.text = "Hello world transcription"
            seg_mock.start = 0.0
            seg_mock.end = 2.0

            call_count = [0]
            def side_effect_transcribe(*args, **kwargs):
                call_count[0] += 1
                if kwargs.get("vad_filter") is True:
                    raise RuntimeError("Missing silero_vad.onnx in runtime environment")
                return [seg_mock], MagicMock(language="en", duration=2.0)

            mock_model_instance.transcribe.side_effect = side_effect_transcribe

            audio_dummy = np.zeros(32000, dtype=np.float32)
            results, lang = transcribe_audio_whisper(
                audio_dummy,
                model_id="whisper-base",
                language="en",
                return_info=True,
            )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][1], "Hello world transcription")
            self.assertEqual(call_count[0], 2)


if __name__ == "__main__":
    unittest.main()
