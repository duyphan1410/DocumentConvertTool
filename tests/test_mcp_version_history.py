"""
Unit and Integration Tests for MCP Document Version History & Rollback Engine (FEAT_001 Phase 4).
"""
import os
import uuid
import shutil
import tempfile
import sqlite3
import threading
import unittest
from unittest.mock import patch
from src.services.metadata_index import MetadataIndex
from src.mcp.tools import (
    handle_write_document_content,
    handle_get_document_history,
    handle_rollback_document,
)


class TestMCPVersionHistory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_dir = os.path.join(self.temp_dir.name, "workspace")
        os.makedirs(self.workspace_dir, exist_ok=True)

        self.db_path = os.path.join(self.temp_dir.name, "test_index.db")
        self.index = MetadataIndex(db_path=self.db_path)

        self.orig_env_ws = os.environ.get("DOCCONVERT_WORKSPACE")
        os.environ["DOCCONVERT_WORKSPACE"] = self.workspace_dir

        # Create a sample document
        self.doc_path = os.path.join(self.workspace_dir, "notes.md")
        self.initial_content = "# Human Baseline Title\n\nOriginal human-written notes."
        with open(self.doc_path, "w", encoding="utf-8") as f:
            f.write(self.initial_content)

        self.doc_id = self.index.upsert_document(
            self.doc_path, "Human Baseline Title", self.index.calculate_hash(self.initial_content)
        )

    def tearDown(self):
        if self.orig_env_ws is not None:
            os.environ["DOCCONVERT_WORKSPACE"] = self.orig_env_ws
        else:
            os.environ.pop("DOCCONVERT_WORKSPACE", None)
        self.temp_dir.cleanup()

    def test_schema_constraints(self):
        """Verifies UNIQUE(document_id, version) and CHECK(author) constraints in SQLite schema."""
        with self.index.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Insert valid record
            cursor.execute("""
                INSERT INTO document_history (document_id, version, content, change_summary, author)
                VALUES (?, 0, 'baseline', 'User baseline', 'USER')
            """, (self.doc_id,))
            conn.commit()

            # 2. Duplicate (document_id, version) must fail with IntegrityError
            with self.assertRaises(sqlite3.IntegrityError):
                cursor.execute("""
                    INSERT INTO document_history (document_id, version, content, change_summary, author)
                    VALUES (?, 0, 'duplicate version 0', 'Fail duplicate', 'USER')
                """, (self.doc_id,))
                conn.commit()

            # 3. Invalid author must fail CHECK constraint
            with self.assertRaises(sqlite3.IntegrityError):
                cursor.execute("""
                    INSERT INTO document_history (document_id, version, content, change_summary, author)
                    VALUES (?, 1, 'content', 'Invalid author', 'HACKER')
                """, (self.doc_id,))
                conn.commit()

    def test_ensure_baseline_version(self):
        """Tests that ensure_baseline_version captures version 0 authored by USER."""
        res = self.index.ensure_baseline_version(self.doc_id)
        self.assertTrue(res)

        versions = self.index.get_document_versions(self.doc_id)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]["version"], 0)
        self.assertEqual(versions[0]["author"], "USER")

        content = self.index.get_version_content(self.doc_id, 0)
        self.assertEqual(content, self.initial_content)

        # Idempotent call should return True without duplicate insert
        res2 = self.index.ensure_baseline_version(self.doc_id)
        self.assertTrue(res2)
        self.assertEqual(self.index.count_document_versions(self.doc_id), 1)

    def test_append_version_invariant_starts_at_one(self):
        """Verifies AI revisions always have version >= 1, preserving version 0 for USER."""
        # 1. Append when no baseline exists yet
        v1 = self.index.append_document_version(self.doc_id, "Revision 1 content", "First AI edit", author="AI")
        self.assertEqual(v1, 1)

        v2 = self.index.append_document_version(self.doc_id, "Revision 2 content", "Second AI edit", author="AI")
        self.assertEqual(v2, 2)

        self.assertEqual(self.index.count_document_versions(self.doc_id), 2)

    def test_retention_pruning_preserves_version_zero(self):
        """Verifies retention pruning purges oldest intermediate versions while preserving version 0 baseline."""
        # Ensure baseline v0
        self.index.ensure_baseline_version(self.doc_id)

        # Append 10 revisions with max_versions = 5
        for i in range(1, 11):
            self.index.append_document_version(
                self.doc_id,
                f"Content revision {i}",
                f"Edit {i}",
                author="AI",
                max_versions=5
            )

        # Total versions should be 1 (v0 baseline) + 5 (revisions 6..10) = 6
        total = self.index.count_document_versions(self.doc_id)
        self.assertEqual(total, 6)

        # Version 0 must still exist
        v0_content = self.index.get_version_content(self.doc_id, 0)
        self.assertEqual(v0_content, self.initial_content)

        # Oldest revisions (1..5) should be pruned, recent ones (6..10) kept
        versions = self.index.get_document_versions(self.doc_id, limit=20)
        ver_numbers = [v["version"] for v in versions]
        self.assertIn(0, ver_numbers)
        self.assertIn(10, ver_numbers)
        self.assertIn(6, ver_numbers)
        self.assertNotIn(1, ver_numbers)
        self.assertNotIn(5, ver_numbers)

    def test_get_document_versions_metadata_no_pk_leak(self):
        """Verifies get_document_versions computes bytes_count and does not leak internal primary key."""
        self.index.ensure_baseline_version(self.doc_id)
        self.index.append_document_version(self.doc_id, "Updated notes content with extra lines", "Update", author="AI")

        versions = self.index.get_document_versions(self.doc_id)
        self.assertEqual(len(versions), 2)
        for v in versions:
            self.assertNotIn("id", v)  # Internal PK must not be leaked
            self.assertIn("version", v)
            self.assertIn("author", v)
            self.assertIn("change_summary", v)
            self.assertIn("created_at", v)
            self.assertIn("char_count", v)
            self.assertIn("bytes_count", v)
            self.assertGreater(v["bytes_count"], 0)

    def test_handle_write_document_content_history_integration(self):
        """Tests write_document_content creates baseline v0, creates v1, and updates disk."""
        new_text = "# Edited Title\n\nEdited by AI Agent."
        res = handle_write_document_content(
            document_id=self.doc_id,
            content=new_text,
            change_summary="AI edit 1",
            index=self.index
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["version"], 1)

        with open(self.doc_path, "r", encoding="utf-8") as f:
            disk_content = f.read()
        self.assertEqual(disk_content, new_text)

        # Verify history
        hist_res = handle_get_document_history(document_id=self.doc_id, index=self.index)
        self.assertEqual(hist_res["total_versions"], 2)  # v0 baseline + v1 AI edit
        self.assertEqual(hist_res["versions"][0]["version"], 1)
        self.assertEqual(hist_res["versions"][1]["version"], 0)

    def test_handle_rollback_document_success(self):
        """Tests rollback_document restores disk file to baseline version 0 and records audit trail."""
        # 1. First edit
        handle_write_document_content(
            document_id=self.doc_id,
            content="# Overwritten Content\n\nAI Overwrite.",
            index=self.index
        )

        # 2. Rollback to version 0
        roll_res = handle_rollback_document(
            document_id=self.doc_id,
            target_version=0,
            index=self.index
        )
        self.assertEqual(roll_res["status"], "success")
        self.assertEqual(roll_res["restored_version"], 0)
        self.assertEqual(roll_res["new_version"], 2)  # Audit trail appended as v2

        # Verify disk restored
        with open(self.doc_path, "r", encoding="utf-8") as f:
            restored_disk = f.read()
        self.assertEqual(restored_disk, self.initial_content)

    def test_handle_rollback_document_missing_file_restore(self):
        """Tests rollback restores a file that was physically deleted from disk."""
        # 1. Edit to create history
        handle_write_document_content(
            document_id=self.doc_id,
            content="# Temp Content",
            index=self.index
        )

        # 2. Delete physical file from disk
        os.remove(self.doc_path)
        self.assertFalse(os.path.exists(self.doc_path))

        # 3. Rollback should recreate file at stored_path
        roll_res = handle_rollback_document(
            document_id=self.doc_id,
            target_version=0,
            index=self.index
        )
        self.assertEqual(roll_res["status"], "success")
        self.assertTrue(os.path.exists(self.doc_path))

        with open(self.doc_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), self.initial_content)

    def test_handle_rollback_document_errors(self):
        """Tests rollback error discrimination: INVALID_UUID, DOCUMENT_NOT_FOUND, RESTORE_OUTSIDE_WORKSPACE, VERSION_NOT_FOUND."""
        # 1. Invalid UUID
        res1 = handle_rollback_document(document_id="not-a-uuid", target_version=0, index=self.index)
        self.assertEqual(res1["error"], "INVALID_UUID")

        # 2. Valid UUID but not found in index
        random_uuid = str(uuid.uuid4())
        res2 = handle_rollback_document(document_id=random_uuid, target_version=0, index=self.index)
        self.assertEqual(res2["error"], "DOCUMENT_NOT_FOUND")

        # 3. Target version does not exist
        res3 = handle_rollback_document(document_id=self.doc_id, target_version=99, index=self.index)
        self.assertEqual(res3["error"], "VERSION_NOT_FOUND")

        # 4. Document outside workspace
        outside_path = os.path.join(self.temp_dir.name, "outside", "out.md")
        os.makedirs(os.path.dirname(outside_path), exist_ok=True)
        with open(outside_path, "w", encoding="utf-8") as f:
            f.write("outside")
        outside_id = self.index.upsert_document(
            outside_path, "Outside", self.index.calculate_hash("outside")
        )

        res4 = handle_rollback_document(document_id=outside_id, target_version=0, index=self.index)
        self.assertEqual(res4["error"], "RESTORE_OUTSIDE_WORKSPACE")

    def test_write_document_graceful_when_append_version_fails(self):
        """EC-1: Verifies write_document succeeds on disk and returns warning if append_document_version throws."""
        new_text = "# Content Saved Without Audit"
        with patch.object(self.index, "append_document_version", side_effect=sqlite3.OperationalError("Simulated DB lock/disk full")):
            res = handle_write_document_content(
                document_id=self.doc_id,
                content=new_text,
                index=self.index
            )
            # Must remain status success because physical disk write succeeded
            self.assertEqual(res["status"], "success")
            self.assertIsNotNone(res["warning"])
            self.assertIn("Simulated DB lock/disk full", res["warning"])
            self.assertIsNone(res["version"])

            # Verify physical file on disk was indeed updated
            with open(self.doc_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), new_text)

    def test_write_document_graceful_when_index_fails(self):
        """EC-2: Verifies write_document succeeds and does not crash if post-write re-indexing fails."""
        new_text = "# Content Saved With Stale Index"
        with patch.object(self.index, "index_document", side_effect=Exception("Simulated index parser crash")):
            res = handle_write_document_content(
                document_id=self.doc_id,
                content=new_text,
                index=self.index
            )
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["version"], 1)

            # Verify physical file on disk was updated
            with open(self.doc_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), new_text)

    def test_concurrent_version_append_thread_safety(self):
        """Tests multithreaded concurrent append_document_version calls produce unique strictly monotonic versions."""
        self.index.ensure_baseline_version(self.doc_id)
        thread_count = 10
        results = []
        errors = []

        def worker(idx_num):
            try:
                ver = self.index.append_document_version(
                    self.doc_id,
                    f"Thread content {idx_num}",
                    f"Summary {idx_num}",
                    author="AI",
                    max_versions=50
                )
                results.append(ver)
            except Exception as ex:
                errors.append(ex)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), thread_count)
        # All version numbers must be unique and in range 1..thread_count
        self.assertEqual(len(set(results)), thread_count)
        self.assertEqual(set(results), set(range(1, thread_count + 1)))


if __name__ == "__main__":
    unittest.main()
