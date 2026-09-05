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

    def test_word_export_and_import_html_image_with_width_and_align(self):
        img_path = os.path.join(self.test_dir, "test_resized.png")
        img = PILImage.new("RGB", (800, 600), color="green")
        img.save(img_path)

        norm_path = img_path.replace("\\", "/")
        md_content = f'## Header 2\n\n<p align="center"><img src="{norm_path}" alt="diagram" width="75%" /></p>\n\nFooter paragraph'
        out_docx = os.path.join(self.test_dir, "resized_output.docx")

        self.word_module.save_from_markdown(md_content, out_docx)
        self.assertTrue(os.path.exists(out_docx))

        # Ensure python-docx can open and parse it cleanly (no XML corruption)
        import docx
        doc = docx.Document(out_docx)
        self.assertGreater(len(doc.paragraphs), 0)

        # Re-read Word file back to Markdown to verify width 75% was extracted cleanly
        extracted_md = self.word_module.load_to_markdown(out_docx)
        self.assertIn("Header 2", extracted_md)
        self.assertIn("Footer paragraph", extracted_md)
        self.assertIn('width="75%"', extracted_md)
        self.assertNotIn("/>", extracted_md.replace('<img', '').replace('/>', ''))


if __name__ == "__main__":
    unittest.main()

