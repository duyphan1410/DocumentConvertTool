"""
Unit and Integration Tests for MCP Safe Patch and Legacy Backups Cleanup (FEAT_001 Phase 4).
"""
import os
import tempfile
import unittest
from unittest.mock import patch
from src.services.metadata_index import MetadataIndex
from src.mcp.tools import (
    handle_patch_document_content,
    handle_cleanup_legacy_backups,
    handle_get_document_history,
)


class TestMCPPatchAndCleanup(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_dir = os.path.join(self.temp_dir.name, "workspace")
        os.makedirs(self.workspace_dir, exist_ok=True)

        self.db_path = os.path.join(self.temp_dir.name, "test_index.db")
        self.index = MetadataIndex(db_path=self.db_path)

        self.orig_env_ws = os.environ.get("DOCCONVERT_WORKSPACE")
        os.environ["DOCCONVERT_WORKSPACE"] = self.workspace_dir

        # Setup sample document
        self.doc_path = os.path.join(self.workspace_dir, "sample.md")
        self.initial_content = "# Section One\n\nTarget line to replace.\n\n# Section Two"
        with open(self.doc_path, "w", encoding="utf-8") as f:
            f.write(self.initial_content)

        self.doc_id = self.index.upsert_document(
            self.doc_path, "Sample Document", self.index.calculate_hash(self.initial_content)
        )

    def tearDown(self):
        if self.orig_env_ws is not None:
            os.environ["DOCCONVERT_WORKSPACE"] = self.orig_env_ws
        else:
            os.environ.pop("DOCCONVERT_WORKSPACE", None)
        self.temp_dir.cleanup()

    def test_patch_document_single_match_success(self):
        """Tests safe patch replacement when target string appears exactly once."""
        target = "Target line to replace."
        replacement = "Replaced line with new information."
        res = handle_patch_document_content(
            document_id=self.doc_id,
            target_content=target,
            replacement_content=replacement,
            change_summary="Update target line",
            index=self.index
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["version"], 1)
        self.assertGreater(res["bytes_written"], 0)

        # Check content on disk
        with open(self.doc_path, "r", encoding="utf-8") as f:
            new_disk = f.read()
        self.assertIn(replacement, new_disk)
        self.assertNotIn(target, new_disk)

        # Check history recorded
        hist = handle_get_document_history(document_id=self.doc_id, index=self.index)
        self.assertEqual(hist["total_versions"], 2)  # v0 baseline + v1 patch

    def test_patch_document_target_not_found(self):
        """Tests patch returns TARGET_NOT_FOUND when target string does not exist."""
        res = handle_patch_document_content(
            document_id=self.doc_id,
            target_content="Non-existent string in doc",
            replacement_content="Whatever",
            index=self.index
        )
        self.assertEqual(res["error"], "TARGET_NOT_FOUND")

        # Verify disk unchanged
        with open(self.doc_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), self.initial_content)

    def test_patch_document_multiple_matches_rejected(self):
        """Tests patch returns MULTIPLE_MATCHES_FOUND when target string appears >1 times."""
        # Overwrite with duplicate text
        dup_text = "Repeated phrase here.\nMiddle text.\nRepeated phrase here."
        with open(self.doc_path, "w", encoding="utf-8") as f:
            f.write(dup_text)

        res = handle_patch_document_content(
            document_id=self.doc_id,
            target_content="Repeated phrase here.",
            replacement_content="New Unique Phrase",
            index=self.index
        )
        self.assertEqual(res["error"], "MULTIPLE_MATCHES_FOUND")
        self.assertEqual(res["match_count"], 2)

        # Verify disk unchanged
        with open(self.doc_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), dup_text)

    def test_patch_document_invalid_uuid(self):
        """Tests patch rejects invalid UUID format."""
        res = handle_patch_document_content(
            document_id="invalid-uuid",
            target_content="Target",
            replacement_content="Repl",
            index=self.index
        )
        self.assertEqual(res["error"], "INVALID_UUID")

    def test_cleanup_legacy_backups_no_workspace(self):
        """Tests cleanup returns WORKSPACE_NOT_FOUND when workspace directory is not set or invalid."""
        os.environ.pop("DOCCONVERT_WORKSPACE", None)
        with patch("src.mcp.tools.get_active_workspace_dir", return_value=None):
            res = handle_cleanup_legacy_backups()
            self.assertEqual(res["error"], "WORKSPACE_NOT_FOUND")

    def test_cleanup_legacy_backups_dry_run(self):
        """Tests cleanup dry_run lists legacy backups without deleting them."""
        # Create legacy backup files in workspace
        bak1 = os.path.join(self.workspace_dir, "notes.md.bak")
        bak2 = os.path.join(self.workspace_dir, "report.old")
        normal_file = os.path.join(self.workspace_dir, "normal.txt")

        with open(bak1, "w", encoding="utf-8") as f:
            f.write("backup 1")
        with open(bak2, "w", encoding="utf-8") as f:
            f.write("backup 2 old")
        with open(normal_file, "w", encoding="utf-8") as f:
            f.write("keep me")

        res = handle_cleanup_legacy_backups(dry_run=True)
        self.assertEqual(res["status"], "preview")
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["files_found_count"], 1)  # Only files ending with .bak match
        self.assertGreater(res["total_bytes"], 0)

        # Files must still exist on disk
        self.assertTrue(os.path.exists(bak1))
        self.assertTrue(os.path.exists(bak2))
        self.assertTrue(os.path.exists(normal_file))

    def test_cleanup_legacy_backups_confirm_required(self):
        """Tests cleanup dry_run=False with confirm=False returns CONFIRMATION_REQUIRED."""
        bak1 = os.path.join(self.workspace_dir, "doc.bak")
        with open(bak1, "w", encoding="utf-8") as f:
            f.write("backup")

        res = handle_cleanup_legacy_backups(
            dry_run=False,
            confirm=False
        )
        self.assertEqual(res["error"], "CONFIRMATION_REQUIRED")
        self.assertTrue(os.path.exists(bak1))

    def test_cleanup_legacy_backups_execute_success(self):
        """Tests cleanup dry_run=False with confirm=True safely removes legacy files."""
        bak1 = os.path.join(self.workspace_dir, "notes.md.bak")
        bak2 = os.path.join(self.workspace_dir, "sub", "data.bak")
        os.makedirs(os.path.dirname(bak2), exist_ok=True)
        normal = os.path.join(self.workspace_dir, "keep.md")

        with open(bak1, "w", encoding="utf-8") as f:
            f.write("backup content 1")
        with open(bak2, "w", encoding="utf-8") as f:
            f.write("backup content 2")
        with open(normal, "w", encoding="utf-8") as f:
            f.write("normal document")

        # Mock safe_delete_to_recycle_bin to verify it's called and remove files
        def mock_recycle(path):
            os.remove(path)
            return True

        with patch("src.mcp.tools.safe_delete_to_recycle_bin", side_effect=mock_recycle) as mock_del:
            res = handle_cleanup_legacy_backups(
                dry_run=False,
                confirm=True
            )
            self.assertEqual(res["status"], "success")
            self.assertFalse(res["dry_run"])
            self.assertEqual(res["deleted_count"], 2)
            self.assertEqual(mock_del.call_count, 2)

        # Legacy backups removed, normal file preserved
        self.assertFalse(os.path.exists(bak1))
        self.assertFalse(os.path.exists(bak2))
        self.assertTrue(os.path.exists(normal))

    def test_cleanup_legacy_backups_skips_symlink(self):
        """Tests anti-symlink traversal skips symlink files to prevent escaping workspace boundary."""
        real_outside = os.path.join(self.temp_dir.name, "outside_target.bak")
        with open(real_outside, "w", encoding="utf-8") as f:
            f.write("outside secret backup")

        symlink_in_ws = os.path.join(self.workspace_dir, "symlink_test.bak")
        try:
            os.symlink(real_outside, symlink_in_ws)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not supported or privileged on this environment")

        res = handle_cleanup_legacy_backups(dry_run=True)
        self.assertEqual(res["status"], "preview")
        found_paths = [f["path"] for f in res["files"]]
        self.assertNotIn(symlink_in_ws, found_paths)
        self.assertNotIn(real_outside, found_paths)

    def test_cleanup_legacy_backups_no_fallback_on_total_failure(self):
        """Tests that when safe_delete_to_recycle_bin fails, CLEANUP_FAILED is returned and NO file is permanently deleted."""
        bak1 = os.path.join(self.workspace_dir, "critical_backup.bak")
        with open(bak1, "w", encoding="utf-8") as f:
            f.write("precious content")

        with patch("src.mcp.tools.safe_delete_to_recycle_bin", side_effect=OSError("Recycle bin service unavailable")):
            res = handle_cleanup_legacy_backups(
                dry_run=False,
                confirm=True
            )
            self.assertEqual(res["error"], "CLEANUP_FAILED")
            self.assertIn("failed_files", res)
            self.assertEqual(len(res["failed_files"]), 1)

            # CRITICAL SECURITY INVARIANT: File must NOT be deleted via fallback os.remove
            self.assertTrue(os.path.exists(bak1))
            with open(bak1, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "precious content")


if __name__ == "__main__":
    unittest.main()
