import unittest
import hashlib

class TestDocumentPreviewLogic(unittest.TestCase):
    def test_content_hashing(self):
        text1 = "# Hello World\n![img](test.png)"
        base_dir1 = "/path/to/dir"
        hash1 = hashlib.md5(f"{text1}::{base_dir1}".encode("utf-8")).hexdigest()
        hash2 = hashlib.md5(f"{text1}::{base_dir1}".encode("utf-8")).hexdigest()
        self.assertEqual(hash1, hash2)

        text2 = "# Hello World\n![img](test2.png)"
        hash3 = hashlib.md5(f"{text2}::{base_dir1}".encode("utf-8")).hexdigest()
        self.assertNotEqual(hash1, hash3)

    def test_image_rescaling_math(self):
        orig_w, orig_h = 2000, 1000
        target_w = 400
        
        ratio = target_w / orig_w
        scaled_w = int(orig_w * ratio)
        scaled_h = int(orig_h * ratio)
        
    def test_local_document_link_click(self):
        import os
        import tempfile
        from unittest.mock import MagicMock
        from src.ui_flet.views.preview_view import MarkdownPreview

        opened_paths = []
        mock_open = lambda path: opened_paths.append(path)

        preview = MarkdownPreview(on_open_file=mock_open)
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_doc = os.path.join(tmp_dir, "report.docx")
            with open(target_doc, "w") as f:
                f.write("mock")

            preview._base_dir = tmp_dir

            # Simulate link click on relative doc path
            mock_event = MagicMock()
            mock_event.data = "report.docx"

            preview._on_markdown_link_clicked(mock_event)

            self.assertEqual(len(opened_paths), 1)
            self.assertEqual(os.path.normpath(opened_paths[0]), os.path.normpath(target_doc))


if __name__ == "__main__":
    unittest.main()

