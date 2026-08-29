"""
Unit tests for ImageTokenHelper: parsing, generation, offset detection, and aspect ratio calculation.
"""
import unittest
from src.ui_flet.helpers.image_token_helper import (
    find_all_image_tokens,
    find_image_token_at_offset,
    generate_image_token,
    calculate_scaled_dimensions,
    inspect_image_dimensions,
    ImageTokenInfo,
)


class TestImageTokenHelper(unittest.TestCase):
    def test_find_markdown_image(self):
        text = "Here is an image: ![Diagram](assets/chart.png) and some text."
        tokens = find_all_image_tokens(text)
        self.assertEqual(len(tokens), 1)
        tok = tokens[0]
        self.assertEqual(tok.alt, "Diagram")
        self.assertEqual(tok.src, "assets/chart.png")
        self.assertFalse(tok.is_html)
        self.assertEqual(tok.start, 18)
        self.assertEqual(tok.end, 46)

    def test_find_html_image_standalone(self):
        text = 'Header\n<img src="pic.jpg" alt="Photo" width="50%" height="auto" />\nFooter'
        tokens = find_all_image_tokens(text)
        self.assertEqual(len(tokens), 1)
        tok = tokens[0]
        self.assertEqual(tok.src, "pic.jpg")
        self.assertEqual(tok.alt, "Photo")
        self.assertEqual(tok.width, "50%")
        self.assertEqual(tok.height, "auto")
        self.assertTrue(tok.is_html)

    def test_find_html_image_with_paragraph_alignment(self):
        text = '<p align="center"><img width="300" src="logo.png" alt="Company Logo" /></p>'
        tokens = find_all_image_tokens(text)
        self.assertEqual(len(tokens), 1)
        tok = tokens[0]
        self.assertEqual(tok.src, "logo.png")
        self.assertEqual(tok.alt, "Company Logo")
        self.assertEqual(tok.width, "300")
        self.assertEqual(tok.align, "center")
        self.assertTrue(tok.is_html)

    def test_multiple_images_on_same_line(self):
        text = "![First](a.png) and ![Second](b.png) and <img src='c.png' width='25%' />"
        tokens = find_all_image_tokens(text)
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].src, "a.png")
        self.assertEqual(tokens[1].src, "b.png")
        self.assertEqual(tokens[2].src, "c.png")
        self.assertEqual(tokens[2].width, "25%")

    def test_find_image_token_at_offset(self):
        text = "012345 ![Test](img.png) 6789"
        # Token spans index 7 to 23
        self.assertIsNone(find_image_token_at_offset(text, 2, 4))
        # Cursor right at start of token (index 7)
        tok1 = find_image_token_at_offset(text, 7, 7)
        self.assertIsNotNone(tok1)
        self.assertEqual(tok1.src, "img.png")

        # Cursor inside token (index 12)
        tok2 = find_image_token_at_offset(text, 12, 15)
        self.assertIsNotNone(tok2)
        self.assertEqual(tok2.alt, "Test")

        # Cursor right after token (index 23)
        tok3 = find_image_token_at_offset(text, 23, 23)
        self.assertIsNotNone(tok3)

        # Cursor past token (index 25)
        self.assertIsNone(find_image_token_at_offset(text, 25, 27))

    def test_generate_image_token_markdown_default(self):
        res = generate_image_token("images/doc.png", alt="My Doc", width="", height="")
        self.assertEqual(res, "![My Doc](images/doc.png)")

        # 100% width reverts to standard clean markdown
        res100 = generate_image_token("images/doc.png", alt="My Doc", width="100%")
        self.assertEqual(res100, "![My Doc](images/doc.png)")

    def test_generate_image_token_html_percentage(self):
        res = generate_image_token("images/doc.png", alt="My Doc", width="50%")
        self.assertEqual(res, '<img src="images/doc.png" alt="My Doc" width="50%" />')

    def test_generate_image_token_html_with_alignment(self):
        res = generate_image_token("images/doc.png", alt="My Doc", width="400", height="300", align="center")
        self.assertEqual(res, '<p align="center"><img src="images/doc.png" alt="My Doc" width="400" height="300" /></p>')

    def test_calculate_scaled_dimensions_aspect_ratio(self):
        orig_w, orig_h = 1920, 1080  # 16:9
        # 50% scale
        w50, h50 = calculate_scaled_dimensions(orig_w, orig_h, target_scale_percent=50)
        self.assertEqual(w50, 960)
        self.assertEqual(h50, 540)

        # 25% scale
        w25, h25 = calculate_scaled_dimensions(orig_w, orig_h, target_scale_percent=25)
        self.assertEqual(w25, 480)
        self.assertEqual(h25, 270)

        # Custom width with lock_ratio
        w_custom, h_custom = calculate_scaled_dimensions(orig_w, orig_h, custom_w=800, lock_ratio=True)
        self.assertEqual(w_custom, 800)
        self.assertEqual(h_custom, 450)

    def test_inspect_image_dimensions_fallback(self):
        # Non-existent path should gracefully return (800, 600) without crashing
        w, h = inspect_image_dimensions("non_existent_file.png")
        self.assertEqual(w, 800)
        self.assertEqual(h, 600)


if __name__ == "__main__":
    unittest.main()
