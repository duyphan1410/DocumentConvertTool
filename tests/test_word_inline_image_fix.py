import os
import shutil
import tempfile
import unittest
from PIL import Image as PILImage
from src.modules.word_module import WordModule

class TestWordInlineImageFix(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.word_module = WordModule()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_save_from_markdown_preserves_inline_heading_and_text(self):
        # Create a valid PNG image
        img_path = os.path.join(self.test_dir, "test.png")
        img = PILImage.new("RGB", (50, 50), color="blue")
        img.save(img_path)

        # Markdown where heading and image are on the same line
        md_content = f"# **PHAN TIEN DUY**![TestImg]({img_path})\n### Software Engineer"
        out_docx = os.path.join(self.test_dir, "output.docx")

        # Convert to Word
        self.word_module.save_from_markdown(md_content, out_docx)
        self.assertTrue(os.path.exists(out_docx))

        # Re-read Word file back to Markdown to verify no heading text was swallowed
        extracted_md = self.word_module.load_to_markdown(out_docx)

        self.assertIn("PHAN TIEN DUY", extracted_md, "Heading text 'PHAN TIEN DUY' must not be lost")
        self.assertIn("Software Engineer", extracted_md, "Sub-heading text 'Software Engineer' must not be lost")

    def test_word_table_inline_formatting(self):
        md_content = (
            "| Header **Bold** | Header *Italic* |\n"
            "| --- | --- |\n"
            "| Line 1<br>Line 2 | `code_cell` |"
        )
        out_docx = os.path.join(self.test_dir, "table_output.docx")
        self.word_module.save_from_markdown(md_content, out_docx)
        self.assertTrue(os.path.exists(out_docx))

        extracted_md = self.word_module.load_to_markdown(out_docx)
        self.assertIn("Header Bold", extracted_md)
        self.assertIn("code_cell", extracted_md)

if __name__ == "__main__":
    unittest.main()
