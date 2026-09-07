"""
Unit Tests for MetadataIndex SQLite Service (PKB Phase 1).
Using standard library unittest.
Verifies WAL mode, Thread Safety, Atomic Rename with Wikilink preservation,
Re-resolve broken links on creation, and 3-Way Synchronization.
"""
import os
import shutil
import tempfile
import threading
import unittest
from src.services.metadata_index import MetadataIndex
from src.services.link_parser import WikilinkToken


class TestMetadataIndex(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_index.db")
        self.index = MetadataIndex(db_path=self.db_path)

    def tearDown(self):
        try:
            shutil.rmtree(self.tmp_dir)
        except Exception:
            pass

    def test_db_initialization_and_wal_mode(self):
        with self.index.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]
            self.assertEqual(journal_mode.upper(), "WAL")

            cursor.execute("PRAGMA foreign_keys;")
            fk_enabled = cursor.fetchone()[0]
            self.assertEqual(fk_enabled, 1)

    def test_upsert_and_retrieve_document(self):
        doc_path = os.path.join(self.tmp_dir, "test_doc.md")
        content = "# Test Title\nSome content"
        content_hash = self.index.calculate_hash(content)

        doc_id = self.index.upsert_document(doc_path, "Test Title", content_hash)
        self.assertIsNotNone(doc_id)

        doc_by_id = self.index.get_document_by_id(doc_id)
        self.assertIsNotNone(doc_by_id)
        self.assertEqual(doc_by_id["title"], "Test Title")
        self.assertEqual(doc_by_id["content_hash"], content_hash)

        doc_by_path = self.index.get_document_by_path(doc_path)
        self.assertIsNotNone(doc_by_path)
        self.assertEqual(doc_by_path["id"], doc_id)

    def test_atomic_rename_preserves_id_and_wikilinks(self):
        """
        CRITICAL TEST: Verifies that renaming a file does NOT change doc_id,
        and all incoming wikilinks to this file remain valid and do NOT become NULL.
        """
        # Doc A (target)
        path_a = os.path.join(self.tmp_dir, "TargetDoc.md")
        id_a = self.index.upsert_document(path_a, "TargetDoc", self.index.calculate_hash("TargetDoc"))

        # Doc B (source, has wikilink to TargetDoc)
        path_b = os.path.join(self.tmp_dir, "SourceDoc.md")
        id_b = self.index.upsert_document(path_b, "SourceDoc", self.index.calculate_hash("SourceDoc"))
        
        # Set wikilink from B -> A
        token = WikilinkToken(raw_target="TargetDoc", display_text=None, snippet="See [[TargetDoc]]", start_pos=4, end_pos=17)
        self.index.set_document_wikilinks(id_b, [token], source_path=path_b)

        # Verify link is resolved to id_a
        linked_refs = self.index.get_linked_references(id_a)
        self.assertEqual(len(linked_refs), 1)
        self.assertEqual(linked_refs[0]["source_id"], id_b)

        # Atomic Rename Doc A -> TargetDocRenamed.md
        new_path_a = os.path.join(self.tmp_dir, "TargetDocRenamed.md")
        rename_success = self.index.rename_document(path_a, new_path_a, "TargetDocRenamed")
        self.assertTrue(rename_success)

        # Verify ID is preserved
        doc_a_after = self.index.get_document_by_id(id_a)
        self.assertIsNotNone(doc_a_after)
        self.assertEqual(doc_a_after["title"], "TargetDocRenamed")
        self.assertEqual(doc_a_after["path"], os.path.normpath(new_path_a))

        # Verify incoming wikilink is STILL valid and target_id is STILL id_a (NOT NULL!)
        linked_refs_after = self.index.get_linked_references(id_a)
        self.assertEqual(len(linked_refs_after), 1)
        self.assertEqual(linked_refs_after[0]["source_id"], id_b)

    def test_re_resolve_broken_wikilinks_on_creation(self):
        """
        Verifies that when a broken link exists in Note X and Note Y,
        creating the new note automatically resolves the links across all notes.
        """
        # Doc X has broken link to [[NewFeature]]
        path_x = os.path.join(self.tmp_dir, "NoteX.md")
        id_x = self.index.upsert_document(path_x, "NoteX", "hash_x")
        token_x = WikilinkToken(raw_target="NewFeature", display_text=None, snippet="[[NewFeature]] in X", start_pos=0, end_pos=14)
        self.index.set_document_wikilinks(id_x, [token_x], source_path=path_x)

        # Verify initially unresolved (target_id is NULL)
        with self.index.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT resolved, target_id FROM wikilinks WHERE source_id = ?", (id_x,))
            row = cursor.fetchone()
            self.assertEqual(row["resolved"], 0)
            self.assertIsNone(row["target_id"])

        # Now create the new document [[NewFeature]]
        path_new = os.path.join(self.tmp_dir, "NewFeature.md")
        id_new = self.index.upsert_document(path_new, "NewFeature", "hash_new")
        
        # Trigger re-resolution
        affected = self.index.re_resolve_broken_wikilinks(id_new, "NewFeature")
        self.assertEqual(affected, 1)

        # Verify link in Note X is now resolved
        with self.index.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT resolved, target_id FROM wikilinks WHERE source_id = ?", (id_x,))
            row = cursor.fetchone()
            self.assertEqual(row["resolved"], 1)
            self.assertEqual(row["target_id"], id_new)

    def test_3_way_sync_incremental_and_orphan_purge(self):
        """
        Verifies 3-Way Sync:
        1. Discovers new files.
        2. Updates modified files (hash changed).
        3. Purges deleted files (orphans).
        """
        ws_folder = os.path.join(self.tmp_dir, "my_workspace")
        os.makedirs(ws_folder, exist_ok=True)

        file1 = os.path.join(ws_folder, "note1.md")
        file2 = os.path.join(ws_folder, "note2.md")

        with open(file1, "w", encoding="utf-8") as f:
            f.write("# Note One\nContent for note 1 #tag1")
        with open(file2, "w", encoding="utf-8") as f:
            f.write("# Note Two\nLinks to [[Note One]] #tag2")

        # 1. Initial Sync
        stats1 = self.index.sync_workspace_incremental(ws_folder)
        self.assertEqual(stats1["added"], 2)
        self.assertEqual(stats1["deleted"], 0)

        # Verify in DB
        all_tags = self.index.get_all_tags()
        tag_names = {t["name"] for t in all_tags}
        self.assertIn("tag1", tag_names)
        self.assertIn("tag2", tag_names)

        # 2. Modify note1 without touching note2
        with open(file1, "w", encoding="utf-8") as f:
            f.write("# Note One Updated\nNew content #tag1 #tag_new")

        stats2 = self.index.sync_workspace_incremental(ws_folder)
        self.assertEqual(stats2["added"], 0)
        self.assertEqual(stats2["updated"], 1)
        self.assertEqual(stats2["deleted"], 0)

        # 3. Delete note2 from disk (orphan purge test)
        os.remove(file2)

        stats3 = self.index.sync_workspace_incremental(ws_folder)
        self.assertEqual(stats3["deleted"], 1)

        # Verify note2 is gone from DB
        doc2 = self.index.get_document_by_path(file2)
        self.assertIsNone(doc2)

    def test_thread_safety_concurrent_access(self):
        """
        Verifies that multiple concurrent reader and writer threads
        can query and update the database without locking crashes.
        """
        errors = []

        def writer_task(thread_id: int):
            try:
                for i in range(15):
                    p = os.path.join(self.tmp_dir, f"doc_{thread_id}_{i}.md")
                    doc_id = self.index.upsert_document(p, f"Doc {thread_id} {i}", f"hash_{thread_id}_{i}")
                    self.index.set_document_tags(doc_id, [f"tag_{thread_id}", "shared_tag"])
            except Exception as ex:
                errors.append(f"Writer {thread_id} failed: {ex}")

        def reader_task(thread_id: int):
            try:
                for _ in range(25):
                    self.index.get_all_tags()
                    self.index.search_documents_by_tag("shared_tag")
            except Exception as ex:
                errors.append(f"Reader {thread_id} failed: {ex}")

        threads = []
        for t_id in range(4):
            threads.append(threading.Thread(target=writer_task, args=(t_id,)))
            threads.append(threading.Thread(target=reader_task, args=(t_id,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def test_extract_wikilinks_ignores_code_blocks_and_placeholders(self):
        """
        Verifies that extract_wikilinks ignores:
        1. Fenced code blocks ```...```
        2. Inline code `...`
        3. Placeholder targets like '...', '---', empty
        4. Frontmatter
        """
        from src.services.link_parser import extract_wikilinks, extract_tags

        doc_content = """---
tags: [architecture, pkb]
---
# Document Title

This is a real wikilink to [[Real Target|Real Alias]].

Here is documentation explaining syntax:
- Example: `[[Sample Inline Code]]`
- Syntax placeholder: `[[...]]`

```markdown
Here is a fenced block:
- [[Target In Fenced Code]]
- [[...]]
```

And another real link [[Second Real Target]].
"""
        tokens = extract_wikilinks(doc_content)
        targets = [t.raw_target for t in tokens]
        self.assertEqual(targets, ["Real Target", "Second Real Target"])
        self.assertEqual(tokens[0].display_text, "Real Alias")


if __name__ == "__main__":
    unittest.main()

