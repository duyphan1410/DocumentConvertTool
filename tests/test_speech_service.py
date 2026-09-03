import unittest
from unittest.mock import MagicMock, patch
from src.services.speech_service import transcribe_youtube_speech, transcribe_drive_speech


class TestSpeechService(unittest.TestCase):
    def test_transcribe_invalid_url(self):
        success, content, error = transcribe_youtube_speech("https://invalid-site.com")
        self.assertFalse(success)
        self.assertEqual(error, "ERR_INVALID_URL")

    @patch("src.services.speech_service.get_best_installed_model")
    @patch("src.services.speech_service.download_youtube_audio")
    @patch("src.services.speech_service.fetch_video_metadata")
    def test_transcribe_audio_download_failed(self, mock_meta, mock_download, mock_model):
        mock_model.return_value = "whisper-tiny"
        mock_meta.return_value = {"title": "Test Video", "author": "Channel"}
        mock_download.return_value = None

        success, content, error = transcribe_youtube_speech("https://youtu.be/dQw4w9WgXcQ")
        self.assertFalse(success)
        self.assertEqual(error, "ERR_AUDIO_DOWNLOAD_FAILED")

    @patch("src.services.speech_service.get_best_installed_model")
    @patch("src.services.speech_service.download_youtube_audio")
    @patch("src.services.speech_service.transcribe_audio_whisper")
    @patch("src.services.speech_service.fetch_video_metadata")
    def test_transcribe_youtube_speech_success(self, mock_meta, mock_transcribe, mock_download, mock_model):
        import tempfile
        import os

        mock_model.return_value = "whisper-base"
        temp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_audio.close()

        try:
            mock_meta.return_value = {"title": "Phỏng Vấn Lập Trình Viên", "author": "Dev Channel"}
            mock_download.return_value = temp_audio.name
            mock_transcribe.return_value = (
                [
                    (0.0, "Chào mừng các bạn đến với buổi phỏng vấn hôm nay"),
                    (15.0, "Chúng ta sẽ trao đổi về kiến trúc phần mềm"),
                ],
                "vi",
            )

            success, content, error = transcribe_youtube_speech(
                "https://youtu.be/dQw4w9WgXcQ",
                language="vi",
                include_timestamps=True,
            )

            self.assertTrue(success)
            self.assertIsNone(error)
            self.assertIn("# Phỏng Vấn Lập Trình Viên", content)
            self.assertIn("- **Channel / Author**: Dev Channel", content)
            self.assertIn("AI Transcription", content)
            self.assertIn("[00:00]", content)
            self.assertIn("Chào mừng các bạn", content)
            self.assertIn("Chúng ta sẽ trao đổi", content)
        finally:
            if os.path.exists(temp_audio.name):
                os.remove(temp_audio.name)

    @patch("src.services.speech_service.get_best_installed_model")
    @patch("src.services.speech_service.transcribe_audio_whisper")
    def test_transcribe_drive_speech_success(self, mock_transcribe, mock_model):
        import tempfile
        import os

        mock_model.return_value = "whisper-base"
        temp_audio = tempfile.NamedTemporaryFile(suffix=".m4a", delete=False)
        temp_audio.close()

        try:
            mock_transcribe.return_value = (
                [
                    (5.0, "Báo cáo tiến độ dự án tuần này"),
                ],
                "vi",
            )

            success, content, error = transcribe_drive_speech(
                file_id="abc123xyz",
                audio_path=temp_audio.name,
                file_name="Hop_Giao_Ban",
                language="vi",
                include_timestamps=True,
            )

            self.assertTrue(success)
            self.assertIsNone(error)
            self.assertIn("# Hop_Giao_Ban", content)
            self.assertIn("https://drive.google.com/file/d/abc123xyz/view", content)
            self.assertIn("[00:05]", content)
            self.assertIn("Báo cáo tiến độ dự án", content)
        finally:
            if os.path.exists(temp_audio.name):
                os.remove(temp_audio.name)


if __name__ == "__main__":
    unittest.main()

