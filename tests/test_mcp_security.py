"""
Unit tests for MCP Security Guard and Path Traversal Prevention.
Verifies UUID validation, ID-only path resolution, format sanitization, and traversal blocking.
"""
import os
import unittest
import tempfile
import uuid
from src.mcp.security import (
    is_valid_uuid,
    resolve_safe_doc_path,
    sanitize_target_format,
    SUPPORTED_CONVERT_FORMATS,
)
from src.services.metadata_index import MetadataIndex


class TestMCPSecurity(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_index.db")
        self.index = MetadataIndex(db_path=self.db_path)

        # Create a sample valid document file
        self.doc_file = os.path.join(self.temp_dir.name, "valid_note.md")
        with open(self.doc_file, "w", encoding="utf-8") as f:
            f.write("# Valid Note\n\nContent for testing.")
        
        self.valid_doc_id = str(uuid.uuid4())
        self.index.upsert_document(
            path=self.doc_file,
            title="Valid Note",
            content_hash="dummyhash123",
            doc_id=self.valid_doc_id
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_is_valid_uuid(self):
        """Test UUID validation helper."""
        self.assertTrue(is_valid_uuid(str(uuid.uuid4())))
        self.assertTrue(is_valid_uuid("c877fa1b-f3b0-4987-cbde-7b9f6fb84408"))
        
        # Invalid cases
        self.assertFalse(is_valid_uuid(None))
        self.assertFalse(is_valid_uuid(""))
        self.assertFalse(is_valid_uuid("12345"))
        self.assertFalse(is_valid_uuid("../../etc/passwd"))
        self.assertFalse(is_valid_uuid("C:\\Windows\\System32\\cmd.exe"))
        self.assertFalse(is_valid_uuid(12345))

    def test_resolve_safe_doc_path_valid(self):
        """Test resolving path for a valid indexed document."""
        is_valid, path, doc = resolve_safe_doc_path(self.valid_doc_id, self.index)
        self.assertTrue(is_valid)
        self.assertEqual(os.path.normpath(path), os.path.normpath(self.doc_file))
        self.assertEqual(doc["title"], "Valid Note")

    def test_resolve_safe_doc_path_nonexistent_id(self):
        """Test resolving an unknown UUID."""
        random_id = str(uuid.uuid4())
        is_valid, path, doc = resolve_safe_doc_path(random_id, self.index)
        self.assertFalse(is_valid)
        self.assertIsNone(path)
        self.assertIsNone(doc)

    def test_resolve_safe_doc_path_malicious_input(self):
        """Test that path traversal strings are blocked immediately at UUID validation."""
        for malicious_str in [
            "../../secret.txt",
            "../../../Windows/System32",
            "/etc/shadow",
            "C:\\boot.ini"
        ]:
            is_valid, path, doc = resolve_safe_doc_path(malicious_str, self.index)
            self.assertFalse(is_valid)
            self.assertIsNone(path)
            self.assertIsNone(doc)

    def test_resolve_safe_doc_path_missing_file_on_disk(self):
        """Test when DB record exists but physical file was deleted on disk."""
        ghost_id = str(uuid.uuid4())
        ghost_path = os.path.join(self.temp_dir.name, "ghost.md")
        self.index.upsert_document(path=ghost_path, title="Ghost", content_hash="ghost", doc_id=ghost_id)

        # File is not created on disk
        is_valid, path, doc = resolve_safe_doc_path(ghost_id, self.index)
        self.assertFalse(is_valid)
        self.assertIsNone(path)
        self.assertIsNotNone(doc)

    def test_sanitize_target_format(self):
        """Test format validation and normalization."""
        for fmt in SUPPORTED_CONVERT_FORMATS:
            self.assertEqual(sanitize_target_format(fmt), fmt)
            self.assertEqual(sanitize_target_format(f".{fmt}"), fmt)
            self.assertEqual(sanitize_target_format(fmt.upper()), fmt)

        with self.assertRaises(ValueError):
            sanitize_target_format("exe")

        with self.assertRaises(ValueError):
            sanitize_target_format("../pdf")

        with self.assertRaises(ValueError):
            sanitize_target_format("")


if __name__ == "__main__":
    unittest.main()
