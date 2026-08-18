import unittest
from unittest.mock import MagicMock, patch
from src.services.youtube_service import (
    extract_video_id,
    format_timestamp,
    fetch_youtube_transcript,
)


class TestYouTubeService(unittest.TestCase):
    def test_extract_video_id_valid_formats(self):
        cases = [
            ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=10s", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ?si=abcd", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ]
        for url, expected_id in cases:
            with self.subTest(url=url):
                self.assertEqual(extract_video_id(url), expected_id)

    def test_extract_video_id_invalid(self):
        cases = [
            "",
            "https://google.com",
            "not_a_valid_id",
            "https://youtube.com/feed/subscriptions",
        ]
        for url in cases:
            with self.subTest(url=url):
                self.assertIsNone(extract_video_id(url))

    def test_format_timestamp(self):
        self.assertEqual(format_timestamp(0), "00:00")
        self.assertEqual(format_timestamp(59), "00:59")
        self.assertEqual(format_timestamp(75), "01:15")
        self.assertEqual(format_timestamp(3665), "01:01:05")

    def test_fetch_youtube_transcript_invalid_url(self):
        success, content, error, lang = fetch_youtube_transcript("https://invalid-url.com")
        self.assertFalse(success)
        self.assertEqual(error, "ERR_INVALID_URL")

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_fetch_youtube_transcript_no_subtitles(self, mock_api_cls):
        from youtube_transcript_api._errors import NoTranscriptFound

        mock_instance = MagicMock()
        mock_api_cls.return_value = mock_instance
        mock_instance.list.side_effect = NoTranscriptFound("dQw4w9WgXcQ", ["vi", "en"], None)

        success, content, error, lang = fetch_youtube_transcript("https://youtu.be/dQw4w9WgXcQ")
        self.assertFalse(success)
        self.assertEqual(error, "ERR_NO_SUBTITLES")

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_fetch_youtube_transcript_success(self, mock_api_cls):
        mock_instance = MagicMock()
        mock_api_cls.return_value = mock_instance

        mock_transcript = MagicMock()
        mock_transcript.language_code = "vi"
        mock_transcript.language = "Vietnamese"
        mock_transcript.is_generated = False
        mock_transcript.fetch.return_value = [
            {"text": "Xin chào các bạn", "start": 0.5, "duration": 2.0},
            {"text": "Hôm nay chúng ta cùng học Python", "start": 3.0, "duration": 3.0},
        ]

        mock_transcript_list = MagicMock()
        mock_transcript_list.find_transcript.return_value = mock_transcript
        mock_instance.list.return_value = mock_transcript_list

        success, content, error, lang = fetch_youtube_transcript(
            "https://youtu.be/dQw4w9WgXcQ", preferred_languages=["vi"]
        )
        self.assertTrue(success)
        self.assertEqual(lang, "vi")
        self.assertIn("Xin chào các bạn", content)
        self.assertIn("**[00:00]**", content)

    @patch("urllib.request.urlopen")
    def test_fetch_video_metadata(self, mock_urlopen):
        import io
        import json
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "title": "Learn Python in 10 Minutes",
            "author_name": "Tech Channel"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        from src.services.youtube_service import fetch_video_metadata
        meta = fetch_video_metadata("dQw4w9WgXcQ")
        self.assertEqual(meta["title"], "Learn Python in 10 Minutes")
        self.assertEqual(meta["author"], "Tech Channel")


if __name__ == "__main__":
    unittest.main()
