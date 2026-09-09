import unittest
from unittest.mock import MagicMock, patch
import fitz
from src.modules.pdf_module import PDFModule


class TestPDFModuleBBox(unittest.TestCase):
    def setUp(self):
        self.module = PDFModule()

    @patch("pdfplumber.open")
    @patch("fitz.open")
    @patch("os.path.exists", return_value=True)
    def test_load_to_markdown_with_offset_bbox(self, mock_exists, mock_fitz_open, mock_pdfplumber_open):
        """Tests that pages with non-zero origin (e.g. MediaBox 39, -39, 651, 744) crop safely."""
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        
        # Simulating Pearson textbook bbox
        mock_page.bbox = (39.0, -39.0, 651.0, 744.0)
        mock_page.width = 612.0
        mock_page.height = 783.0
        mock_page.filter.return_value = mock_page
        
        # Mock table with bbox in page coordinate system
        mock_table = MagicMock()
        mock_table.bbox = (50.0, 100.0, 600.0, 200.0)
        mock_table.extract.return_value = [
            ["Service Category", "Description Details"],
            ["Hospitality Management", "Core principles of hotel operations and tourism"]
        ]
        mock_table.columns = 2
        mock_page.find_tables.return_value = [mock_table]

        # Crop behavior: verify proposed bbox is within page.bbox
        def mock_crop(bbox):
            x0, top, x1, bottom = bbox
            p_x0, p_top, p_x1, p_bottom = mock_page.bbox
            if not (p_x0 <= x0 < x1 <= p_x1 and p_top <= top < bottom <= p_bottom):
                raise ValueError(f"Bounding box {bbox} is not fully within parent page bounding box {mock_page.bbox}")
            cropped = MagicMock()
            cropped.extract_words.return_value = []
            cropped.chars = []
            return cropped

        mock_page.crop.side_effect = mock_crop
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__.return_value = mock_pdf

        mock_pdfplumber_open.return_value = mock_pdf

        # Run conversion
        result = self.module.load_to_markdown("test_pearson_offset.pdf")
        self.assertIsInstance(result, str)
        self.assertIn("Service Category", result)
        self.assertIn("Hospitality Management", result)

    @patch("pdfplumber.open", side_effect=Exception("Simulated pdfplumber failure"))
    @patch("fitz.open")
    @patch("os.path.exists", return_value=True)
    def test_fitz_fallback_when_pdfplumber_fails(self, mock_exists, mock_fitz_open, mock_pdfplumber_open):
        """Tests that PyMuPDF fitz extracts text when pdfplumber fails and markitdown is unavailable."""
        mock_fitz_doc = MagicMock()
        mock_fitz_page = MagicMock()
        mock_fitz_page.get_text.return_value = "Extracted fallback text via PyMuPDF"
        mock_fitz_doc.__iter__.return_value = [mock_fitz_page]
        mock_fitz_open.return_value = mock_fitz_doc

        result = self.module.load_to_markdown("corrupted_or_offset.pdf")
        self.assertEqual(result, "Extracted fallback text via PyMuPDF")


if __name__ == "__main__":
    unittest.main()
