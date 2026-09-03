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

    @patch("src.services.youtube_service._fetch_via_ytdlp", return_value=(False, {}))
    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_fetch_youtube_transcript_no_subtitles(self, mock_api_cls, mock_ytdlp):
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
            {"text": "Xin chào các bạn.", "start": 0.5, "duration": 2.0},
            {"text": "Hôm nay chúng ta cùng học Python.", "start": 3.0, "duration": 3.0},
        ]

        mock_transcript_list = MagicMock()
        mock_transcript_list.find_transcript.return_value = mock_transcript
        mock_instance.list.return_value = mock_transcript_list

        success, content, error, lang = fetch_youtube_transcript(
            "https://youtu.be/dQw4w9WgXcQ", preferred_languages=["vi"]
        )
        self.assertTrue(success)
        self.assertEqual(lang, "vi")
        self.assertIn("Xin chào các bạn.", content)
        self.assertIn("[00:00]", content)

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_fetch_youtube_transcript_auto_translate(self, mock_api_cls):
        mock_instance = MagicMock()
        mock_api_cls.return_value = mock_instance

        # English transcript that is translatable to vi
        mock_en_transcript = MagicMock()
        mock_en_transcript.language_code = "en"
        mock_en_transcript.language = "English"
        mock_en_transcript.is_translatable = True

        mock_vi_translated = MagicMock()
        mock_vi_translated.language_code = "vi"
        mock_vi_translated.language = "Vietnamese"
        mock_vi_translated.fetch.return_value = [
            {"text": "Bản dịch tiếng Việt tự động.", "start": 1.0, "duration": 2.0}
        ]
        mock_en_transcript.translate.return_value = mock_vi_translated

        mock_transcript_list = MagicMock()
        mock_transcript_list.find_transcript.side_effect = Exception("Not found")
        mock_transcript_list.__iter__.return_value = [mock_en_transcript]
        mock_instance.list.return_value = mock_transcript_list

        success, content, error, lang = fetch_youtube_transcript(
            "https://youtu.be/dQw4w9WgXcQ", preferred_languages=["vi"], allow_auto_translate=True
        )
        self.assertTrue(success)
        self.assertEqual(lang, "vi")
        self.assertIn("Auto-translated from English", content)
        self.assertIn("Bản dịch tiếng Việt tự động.", content)

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

    def test_group_snippets_complete_sentence_rule(self):
        from src.services.youtube_service import _group_snippets_into_sentences

        # Snippets where sentence 1 finishes at 6.0s (ends with '.')
        # and sentence 2 finishes at 16.0s (>= 15s interval)
        snippets = [
            {"start": 0.0, "text": "Xin chào"},
            {"start": 2.0, "text": "các bạn,"},
            {"start": 4.0, "text": "chúc mọi người"},
            {"start": 6.0, "text": "một ngày tốt lành."},  # Sentence 1 ends
            {"start": 10.0, "text": "Hôm nay"},
            {"start": 12.0, "text": "chúng ta sẽ học"},
            {"start": 16.0, "text": "lập trình Python."},  # Sentence 2 ends (duration 16.0 >= 15s)
            {"start": 20.0, "text": "Bắt đầu ngay thôi nào!"},  # Sentence 3
        ]

        timestamps, paragraphs = _group_snippets_into_sentences(snippets, group_interval_seconds=15.0, pause_threshold=5.0)

        # Paragraph 1 should include all of sentence 1 and sentence 2, ending with '.'
        self.assertEqual(len(timestamps), 2)
        self.assertEqual(timestamps[0], 0.0)
        self.assertEqual(
            paragraphs[0],
            "Xin chào các bạn, chúc mọi người một ngày tốt lành. Hôm nay chúng ta sẽ học lập trình Python."
        )
        self.assertTrue(paragraphs[0].endswith("."))

        # Paragraph 2 starts at 20.0s
        self.assertEqual(timestamps[1], 20.0)
        self.assertEqual(paragraphs[1], "Bắt đầu ngay thôi nào!")


if __name__ == "__main__":
    unittest.main()
