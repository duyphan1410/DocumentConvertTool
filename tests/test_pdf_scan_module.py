import unittest
from src.core.registry import ModuleRegistry
from src.modules.pdf_scan_module import PDFScanModule


class TestPDFScanModule(unittest.TestCase):
    def setUp(self):
        self.module = PDFScanModule()

    def test_module_metadata(self):
        self.assertEqual(self.module.name, "PDF Scan")
        self.assertIn("pytesseract", self.module.required_dependencies)
        self.assertIn("pymupdf", self.module.required_dependencies)
        self.assertIn("Pillow", self.module.required_dependencies)

    def test_module_registered_in_registry(self):
        registered = ModuleRegistry.get_module_by_name("PDF Scan")
        self.assertIsNotNone(registered)
        self.assertIsInstance(registered, PDFScanModule)

    def test_parse_chuong_and_dieu(self):
        raw_pages = [[
            "Chương Ï",
            "NHỮNG QUY ĐỊNH CHUNG",
            "",
            "Điều 1. Phạm vi điều chỉnh",
            "Luật này quy định về tài nguyên du lịch...",
        ]]
        md = PDFScanModule.parse_legal_structure(raw_pages)
        self.assertIn("# Chương I: NHỮNG QUY ĐỊNH CHUNG", md)
        self.assertIn("### Điều 1. Phạm vi điều chỉnh", md)
        self.assertIn("Luật này quy định về tài nguyên du lịch...", md)

    def test_parse_khoan_and_quotes(self):
        raw_pages = [[
            "Điều 3. Giải thích từ ngữ",
            "Trong Luật này, các từ ngữ dưới đây được hiểu như sau:",
            '1. "Du lịch" là các hoạt động có liên quan...',
            '2. Khách du lịch là người đi du lịch...',
        ]]
        md = PDFScanModule.parse_legal_structure(raw_pages)
        self.assertIn('### Điều 3. Giải thích từ ngữ', md)
        self.assertIn('**1.** "Du lịch" là các hoạt động có liên quan...', md)
        self.assertIn('**2.** Khách du lịch là người đi du lịch...', md)

    def test_parse_diem_with_vietnamese_chars(self):
        raw_pages = [[
            "Điều 5. Chính sách phát triển du lịch",
            "1. Nhà nước có chính sách sau:",
            "a) Ưu đãi đầu tư cơ sở hạ tầng;",
            "đ) Ứng dụng khoa học công nghệ;",
            "e) Phát triển du lịch tại nơi có tiềm năng;",
        ]]
        md = PDFScanModule.parse_legal_structure(raw_pages)
        self.assertIn("- **a)** Ưu đãi đầu tư cơ sở hạ tầng;", md)
        self.assertIn("- **đ)** Ứng dụng khoa học công nghệ;", md)
        self.assertIn("- **e)** Phát triển du lịch tại nơi có tiềm năng;", md)

    def test_ignore_dates_as_khoan(self):
        raw_pages = [[
            "Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam",
            "Ngày 19. 6. 2017 Quốc hội thông qua",
        ]]
        md = PDFScanModule.parse_legal_structure(raw_pages)
        # Should not format date as a bold clause
        self.assertNotIn("**19.**", md)

    def test_page_number_removal_and_sentence_stitching(self):
        page1 = [
            "Điều 2. Đối tượng áp dụng",
            "1. Cơ quan, tổ chức,",
            "1",  # Standalone page number
        ]
        page2 = [
            "2",  # Standalone page number
            "cá nhân hoạt động du lịch tại Việt Nam.",
        ]
        md = PDFScanModule.parse_legal_structure([page1, page2])
        self.assertNotIn("\n1\n", md)
        self.assertNotIn("\n2\n", md)
        # Check cross-page sentence stitching
        self.assertIn("**1.** Cơ quan, tổ chức, cá nhân hoạt động du lịch tại Việt Nam.", md)

    def test_corrupted_khoan_inferred_from_sequence(self):
        """Tests that OCR noise like '_ lỗ.' following Khoản 17 is inferred as Khoản 18."""
        raw_pages = [[
            "### Điều 3. Giải thích từ ngữ",
            "17. Du lịch văn hóa là loại hình du lịch...",
            "_ lỗ. Môi trường du lịch là môi trường tự nhiên...",
        ]]
        md = PDFScanModule.parse_legal_structure(raw_pages)
        self.assertIn("**17.** Du lịch văn hóa là loại hình du lịch...", md)
        self.assertIn("**18.** Môi trường du lịch là môi trường tự nhiên...", md)


if __name__ == "__main__":
    unittest.main()

