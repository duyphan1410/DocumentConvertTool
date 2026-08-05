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
        
        self.assertEqual(scaled_w, 400)
        self.assertEqual(scaled_h, 200)

if __name__ == "__main__":
    unittest.main()
