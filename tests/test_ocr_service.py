import unittest
from unittest.mock import patch, MagicMock
from src.services.ocr_service import OCRService


class TestOCRService(unittest.TestCase):
    def test_find_tesseract_binary(self):
        bin_path = OCRService.find_tesseract_binary()
        self.assertIsNotNone(bin_path)
        self.assertTrue(bin_path.endswith("tesseract.exe") or "tesseract" in bin_path.lower())

    def test_get_tessdata_dir(self):
        tessdata = OCRService.get_tessdata_dir()
        self.assertIsNotNone(tessdata)
        self.assertTrue(len(tessdata) > 0)

    def test_check_ocr_readiness(self):
        ready, msg = OCRService.check_ocr_readiness("vie")
        self.assertTrue(ready)
        self.assertEqual(msg, "Ready")

    def test_reconstruct_layout_from_data(self):
        # Mock Tesseract image_to_data output structure
        mock_data = {
            "level": [5, 5, 5, 5, 5, 5],
            "page_num": [1, 1, 1, 1, 1, 1],
            "block_num": [1, 1, 1, 2, 2, 2],
            "par_num": [1, 1, 1, 1, 1, 1],
            "line_num": [1, 1, 1, 1, 1, 1],
            "word_num": [1, 2, 3, 1, 2, 3],
            "left": [10, 50, 90, 10, 50, 90],
            "top": [10, 10, 10, 50, 50, 50],
            "width": [30, 30, 30, 30, 30, 30],
            "height": [15, 15, 15, 15, 15, 15],
            "conf": [95, 92, 90, 88, 85, 96],
            "text": ["CỘNG", "HÒA", "XÃ", "HỘI", "CHỦ", "NGHĨA"],
        }
        lines = OCRService.reconstruct_layout_from_data(mock_data)
        self.assertIn("CỘNG HÒA XÃ", lines)
        self.assertIn("HỘI CHỦ NGHĨA", lines)

    def test_reconstruct_layout_empty(self):
        lines = OCRService.reconstruct_layout_from_data({})
        self.assertEqual(lines, [])

    def test_filter_low_confidence_noise(self):
        mock_data = {
            "block_num": [1, 1],
            "par_num": [1, 1],
            "line_num": [1, 1],
            "conf": [5, 95],  # 5 is low confidence noise
            "text": [".", "Chương"],
        }
        lines = OCRService.reconstruct_layout_from_data(mock_data, min_confidence=15)
        self.assertEqual(lines, ["Chương"])

    def test_structural_tokens_preserved_despite_low_confidence(self):
        """Confirms short structural tokens like '1.', 'a)', 'đ)' are never dropped by confidence filter."""
        mock_data = {
            "block_num": [1, 1, 1, 2, 2, 2, 3, 3],
            "par_num": [1, 1, 1, 1, 1, 1, 1, 1],
            "line_num": [1, 1, 1, 1, 1, 1, 1, 1],
            "conf": [8, 95, 90, 5, 92, 91, 3, 95],  # 8, 5, 3 are all below min_confidence 15
            "text": ["1.", "Tài", "nguyên", "đ)", "Quy", "hoạch", "x", "Nội dung"],  # 'x' is noise, '1.' & 'đ)' are structural
        }
        lines = OCRService.reconstruct_layout_from_data(mock_data, min_confidence=15)
        self.assertIn("1. Tài nguyên", lines)
        self.assertIn("đ) Quy hoạch", lines)
        self.assertIn("Nội dung", lines)  # 'x' noise token was dropped



if __name__ == "__main__":
    unittest.main()
