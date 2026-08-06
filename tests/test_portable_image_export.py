import os
import shutil
import tempfile
import unittest
from src.services.media_asset_manager import MediaAssetManager

class TestPortableImageExport(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.asset_mgr = MediaAssetManager()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_export_assets_creates_relative_folder_and_rewrites_links(self):
        # Create a dummy image on disk (simulating local image or resolved @media image)
        img1_path = os.path.join(self.test_dir, "sample1.png")
        with open(img1_path, "wb") as f:
            f.write(b"\x89PNG\x0d\x0a\x1a\x0aDummyImageData1")

        img2_path = os.path.join(self.test_dir, "sample2.png")
        with open(img2_path, "wb") as f:
            f.write(b"\x89PNG\x0d\x0a\x1a\x0aDummyImageData2")

        # Markdown content referencing local images
        md_content = f"# Document Test\n\n![Image One]({img1_path})\n\n![Image Two]({img2_path})"
        target_md_path = os.path.join(self.test_dir, "output_doc.md")

        exported_md = self.asset_mgr.export_assets(md_content, target_md_path)

        expected_assets_dir = os.path.join(self.test_dir, "output_doc_assets")
        self.assertTrue(os.path.exists(expected_assets_dir), "output_doc_assets folder should be created")

        # Verify files were copied to output_doc_assets
        self.assertTrue(os.path.exists(os.path.join(expected_assets_dir, "sample1.png")))
        self.assertTrue(os.path.exists(os.path.join(expected_assets_dir, "sample2.png")))

        # Verify Markdown links were rewritten to relative paths
        self.assertIn("![Image One](./output_doc_assets/sample1.png)", exported_md)
        self.assertIn("![Image Two](./output_doc_assets/sample2.png)", exported_md)

    def test_export_assets_deduplicates_filename_collision(self):
        # Create two images in different locations with same filename but different contents
        sub1 = os.path.join(self.test_dir, "sub1")
        sub2 = os.path.join(self.test_dir, "sub2")
        os.makedirs(sub1, exist_ok=True)
        os.makedirs(sub2, exist_ok=True)

        path1 = os.path.join(sub1, "photo.png")
        path2 = os.path.join(sub2, "photo.png")
        with open(path1, "wb") as f:
            f.write(b"PHOTO_CONTENT_A")
        with open(path2, "wb") as f:
            f.write(b"PHOTO_CONTENT_B")

        md_content = f"![Photo 1]({path1})\n![Photo 2]({path2})"
        target_md_path = os.path.join(self.test_dir, "report.md")

        exported_md = self.asset_mgr.export_assets(md_content, target_md_path)

        assets_dir = os.path.join(self.test_dir, "report_assets")
        self.assertTrue(os.path.exists(os.path.join(assets_dir, "photo.png")))
        self.assertTrue(os.path.exists(os.path.join(assets_dir, "photo_1.png")))

        self.assertIn("![Photo 1](./report_assets/photo.png)", exported_md)
        self.assertIn("![Photo 2](./report_assets/photo_1.png)", exported_md)

    def test_export_assets_same_file_reused(self):
        path1 = os.path.join(self.test_dir, "same.png")
        with open(path1, "wb") as f:
            f.write(b"SAME_CONTENT")

        # Same image referenced twice in document
        md_content = f"![First]({path1})\n![Second]({path1})"
        target_md_path = os.path.join(self.test_dir, "reuse.md")

        exported_md = self.asset_mgr.export_assets(md_content, target_md_path)

        assets_dir = os.path.join(self.test_dir, "reuse_assets")
        # Should only copy once
        copied_files = os.listdir(assets_dir)
        self.assertEqual(len(copied_files), 1)
        self.assertEqual(copied_files[0], "same.png")

        self.assertIn("![First](./reuse_assets/same.png)", exported_md)
        self.assertIn("![Second](./reuse_assets/same.png)", exported_md)

if __name__ == "__main__":
    unittest.main()
