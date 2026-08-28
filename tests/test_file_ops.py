"""
Unit tests for safe file operations, reserved device names, and safe recycle bin deletion.
Supports standard unittest and pytest runners.
"""
import os
import sys
import unittest
import tempfile

from src.utils.file_ops import (
    sanitize_filename,
    safe_delete_to_recycle_bin,
    reveal_in_windows_explorer,
)


class TestFileOps(unittest.TestCase):

    def test_sanitize_filename_valid(self):
        valid_names = [
            "document.md",
            "Báo cáo tiến độ 2026.docx",
            "my_project_v1.0.pdf",
            "README",
            "nested-name-test.html",
        ]
        for name in valid_names:
            is_valid, err = sanitize_filename(name)
            self.assertTrue(is_valid, f"Expected '{name}' to be valid, got error: {err}")

    def test_sanitize_filename_empty(self):
        for empty in ["", "   ", "\t"]:
            is_valid, err = sanitize_filename(empty)
            self.assertFalse(is_valid)
            self.assertIn("empty", err.lower())

    def test_sanitize_filename_forbidden_chars(self):
        invalid_names = [
            "doc/test.md",
            "doc\\test.md",
            "hello:world.txt",
            "test*.pdf",
            "question?.docx",
            'quote"name.md',
            "<tag>.html",
            "pipe|name.md",
        ]
        for name in invalid_names:
            is_valid, err = sanitize_filename(name)
            self.assertFalse(is_valid, f"Expected '{name}' to be invalid")
            self.assertIn("cannot contain", err.lower())

    def test_sanitize_filename_reserved_device_names(self):
        reserved_cases = [
            "CON", "con", "Con", "CON.txt", "con.md", "CON.txt.bak",
            "PRN", "prn.docx", "AUX", "aux.html", "aux.tar.gz", "NUL", "nul.json",
            "COM1", "com1.pdf", "com9.txt", "LPT1", "lpt1.csv",
        ]
        for name in reserved_cases:
            is_valid, err = sanitize_filename(name)
            self.assertFalse(is_valid, f"Expected reserved name '{name}' to fail")
            self.assertIn("reserved", err.lower())

    def test_sanitize_filename_trailing_dot_or_space(self):
        for name in ["test.", "test ", "doc.md. ", " leading"]:
            is_valid, err = sanitize_filename(name)
            self.assertFalse(is_valid)
            self.assertIn("cannot start/end with", err.lower())

    def test_safe_delete_to_recycle_bin(self):
        # Create temporary file with Vietnamese name
        temp_dir = tempfile.mkdtemp()
        test_file = os.path.join(temp_dir, "tập_tin_thử_nghiệm_xóa.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Nội dung thử nghiệm safe delete")

        self.assertTrue(os.path.exists(test_file))

        # Perform safe delete
        res = safe_delete_to_recycle_bin(test_file)
        self.assertTrue(res)
        self.assertFalse(os.path.exists(test_file))

        # Test delete non-existent file raises FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            safe_delete_to_recycle_bin(test_file)

        # Clean up parent temp directory
        try:
            os.rmdir(temp_dir)
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
