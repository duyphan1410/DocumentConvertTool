import unittest
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ui_flet.helpers.image_token_helper import find_all_image_tokens, find_image_token_at_offset
from src.ui_flet.views.preview_view import process_markdown_media, MarkdownPreview
import flet as ft


class TestImagePathParentheses(unittest.TestCase):
    def test_markdown_image_with_parentheses_in_path(self):
        text = "![image](C:/Users/Admin/Desktop/Test/Vanguard_Engineering_Impact_(2)_assets/pptx_slide1_img_1955840945536.png)"
        tokens = find_all_image_tokens(text)
        self.assertEqual(len(tokens), 1)
        tok = tokens[0]
        self.assertEqual(tok.raw_token, text)
        self.assertEqual(
            tok.src,
            "C:/Users/Admin/Desktop/Test/Vanguard_Engineering_Impact_(2)_assets/pptx_slide1_img_1955840945536.png",
        )
        self.assertEqual(tok.alt, "image")
        self.assertEqual(tok.start, 0)
        self.assertEqual(tok.end, len(text))

    def test_multiple_images_with_parentheses_and_titles(self):
        text = (
            '![img1](path/to/folder_(1)/a.png "Title 1")\n\n'
            '![img2](<path/to/folder (2)/b.png>)\n\n'
            '<p align="center">![img3](path/to/folder_(copy)_(3)/c.png)</p>'
        )
        tokens = find_all_image_tokens(text)
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].src, "path/to/folder_(1)/a.png")
        self.assertEqual(tokens[1].src, "path/to/folder (2)/b.png")
        self.assertEqual(tokens[2].src, "path/to/folder_(copy)_(3)/c.png")
        self.assertEqual(tokens[2].align, "center")

    def test_process_markdown_media_preserves_parentheses_url(self):
        text = "![image](C:/Users/Admin/Desktop/Test/Vanguard_Engineering_Impact_(2)_assets/pptx_slide1_img_1955840945536.png)"
        processed = process_markdown_media(text)
        # Ensure no stray text is left behind
        self.assertNotIn("_assets/pptx_slide1_img_1955840945536.png)", processed.replace(text, ""))
        self.assertIn("imgaction://select?", processed)

    def test_preview_in_place_update_stability(self):
        preview = MarkdownPreview()
        text_v1 = (
            "# Heading\n\n"
            "Paragraph 1\n\n"
            "![image](https://example.com/img1.png)\n\n"
            "Paragraph 2\n\n"
            "![image](https://example.com/img2.png)"
        )
        processed_v1 = process_markdown_media(text_v1)
        preview._render_processed_content(processed_v1)
        initial_controls = list(preview.scroll_column.controls)
        self.assertEqual(len(initial_controls), 4)  # text, row_img1, text, row_img2

        # Now simulate resizing img1 to center alignment in text
        text_v2 = (
            "# Heading\n\n"
            "Paragraph 1\n\n"
            '<p align="center">![image](https://example.com/img1.png)</p>\n\n'
            "Paragraph 2\n\n"
            "![image](https://example.com/img2.png)"
        )
        processed_v2 = process_markdown_media(text_v2)
        preview._render_processed_content(processed_v2)

        # Controls list instance should remain the same (in-place updated, no full list recreation)
        self.assertEqual(preview.scroll_column.controls, initial_controls)
        # img1 row alignment should be updated to CENTER
        self.assertEqual(initial_controls[1].alignment, ft.MainAxisAlignment.CENTER)


if __name__ == "__main__":
    unittest.main()
