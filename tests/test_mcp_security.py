"""
Unit tests for MCP Security Guard and Path Traversal Prevention.
Verifies UUID validation, ID-only path resolution, format sanitization, and traversal blocking.
"""
import os
import json
import unittest
import tempfile
import uuid
from unittest.mock import patch
from src.mcp.security import (
    is_valid_uuid,
    resolve_safe_doc_path,
    sanitize_target_format,
    is_path_in_workspace,
    get_active_workspace_dir,
    SUPPORTED_CONVERT_FORMATS,
)
from src.services.metadata_index import MetadataIndex


class TestMCPSecurity(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.orig_env_ws = os.environ.get("DOCCONVERT_WORKSPACE")
        os.environ["DOCCONVERT_WORKSPACE"] = self.temp_dir.name

        self.db_path = os.path.join(self.temp_dir.name, "test_index.db")
        self.index = MetadataIndex(db_path=self.db_path)

        # Create a sample valid document file inside temp workspace
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
        if self.orig_env_ws is not None:
            os.environ["DOCCONVERT_WORKSPACE"] = self.orig_env_ws
        else:
            os.environ.pop("DOCCONVERT_WORKSPACE", None)
        self.temp_dir.cleanup()

    def test_is_valid_uuid_strict_v4(self):
        """Test UUID validation helper strictly accepts RFC 4122 UUID v4 and rejects Nil, v1, v3, v5."""
        # Valid UUID v4
        self.assertTrue(is_valid_uuid(str(uuid.uuid4())))
        self.assertTrue(is_valid_uuid("c877fa1b-f3b0-4987-8bde-7b9f6fb84408"))
        
        # Nil UUID
        self.assertFalse(is_valid_uuid("00000000-0000-0000-0000-000000000000"))
        
        # UUID v1, v3, v5
        v1_id = str(uuid.uuid1())
        v3_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, "example.com"))
        v5_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.com"))
        self.assertFalse(is_valid_uuid(v1_id))
        self.assertFalse(is_valid_uuid(v3_id))
        self.assertFalse(is_valid_uuid(v5_id))

        # Invalid strings
        self.assertFalse(is_valid_uuid(None))
        self.assertFalse(is_valid_uuid(""))
        self.assertFalse(is_valid_uuid("12345"))
        self.assertFalse(is_valid_uuid("../../etc/passwd"))
        self.assertFalse(is_valid_uuid("C:\\Windows\\System32\\cmd.exe"))
        self.assertFalse(is_valid_uuid(12345))

    def test_resolve_safe_doc_path_valid(self):
        """Test resolving path for a valid indexed document within workspace."""
        is_valid, path, doc = resolve_safe_doc_path(self.valid_doc_id, self.index)
        self.assertTrue(is_valid)
        self.assertEqual(os.path.normpath(path), os.path.normpath(self.doc_file))
        self.assertEqual(doc["title"], "Valid Note")

    def test_resolve_safe_doc_path_outside_workspace_boundary(self):
        """Test that documents located outside active workspace boundary are strictly rejected."""
        with tempfile.TemporaryDirectory() as other_dir:
            # Document is inside self.temp_dir, but workspace is set to other_dir
            with patch.dict(os.environ, {"DOCCONVERT_WORKSPACE": other_dir}):
                is_valid, path, doc = resolve_safe_doc_path(self.valid_doc_id, self.index)
                self.assertFalse(is_valid)
                self.assertIsNone(path)
                self.assertIsNotNone(doc)  # doc found in DB but blocked by boundary guard

    def test_boundary_check_different_drive_returns_false(self):
        """Test cross-drive containment returns False safely on Windows without unhandled exceptions."""
        with patch("os.path.commonpath", side_effect=ValueError("Paths don't have the same drive")):
            in_ws = is_path_in_workspace("D:\\Projects\\note.md", "C:\\Users\\Workspace")
            self.assertFalse(in_ws)

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

    def test_get_active_workspace_dir_mtime_freshness(self):
        """Test get_active_workspace_dir reloads correctly when settings.json changes mtime."""
        with tempfile.TemporaryDirectory() as fake_appdata:
            settings_dir = os.path.join(fake_appdata, "DocConvert")
            os.makedirs(settings_dir, exist_ok=True)
            settings_file = os.path.join(settings_dir, "settings.json")

            ws1 = os.path.join(self.temp_dir.name, "ws1")
            ws2 = os.path.join(self.temp_dir.name, "ws2")
            os.makedirs(ws1, exist_ok=True)
            os.makedirs(ws2, exist_ok=True)

            with patch.dict(os.environ, {"APPDATA": fake_appdata}, clear=False):
                # Unset DOCCONVERT_WORKSPACE if set
                os.environ.pop("DOCCONVERT_WORKSPACE", None)

                # Write initial settings with ws1
                with open(settings_file, "w", encoding="utf-8") as f:
                    json.dump({"workspace_folder": ws1}, f)

                res1 = get_active_workspace_dir()
                self.assertEqual(res1, os.path.normpath(os.path.abspath(ws1)))

                # Update settings with ws2 and change mtime
                with open(settings_file, "w", encoding="utf-8") as f:
                    json.dump({"workspace_folder": ws2}, f)
                # Set mtime forward
                new_mtime = os.path.getmtime(settings_file) + 5
                os.utime(settings_file, (new_mtime, new_mtime))

                res2 = get_active_workspace_dir()
                self.assertEqual(res2, os.path.normpath(os.path.abspath(ws2)))

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
