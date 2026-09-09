"""
Unit tests for DocConvert MCP Tools.
Verifies search_documents, read_document, convert_document, tag_document,
list_backlinks, and write_document_content handlers.
"""
import os
import unittest
import tempfile
import uuid
from src.mcp.tools import (
    handle_search_documents,
    handle_read_document,
    handle_convert_document,
    handle_tag_document,
    handle_list_backlinks,
    handle_write_document_content,
    MCP_TOOLS_MANIFEST,
)
from src.services.metadata_index import MetadataIndex


class TestMCPTools(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_tools_index.db")
        self.index = MetadataIndex(db_path=self.db_path)

        # File 1: Báo cáo tài chính
        self.doc1_path = os.path.join(self.temp_dir.name, "bao_cao_tai_chinh.md")
        with open(self.doc1_path, "w", encoding="utf-8") as f:
            f.write("# Báo Cáo Tài Chính 2026\n\nNội dung báo cáo kinh doanh.\n\n#finance #report")
        self.doc1_id = str(uuid.uuid4())
        self.index.upsert_document(self.doc1_path, "Báo Cáo Tài Chính 2026", "hash1", doc_id=self.doc1_id)
        self.index.set_document_tags(self.doc1_id, ["finance", "report", "tieng-viet"])

        # File 2: Kế hoạch nghiên cứu
        self.doc2_path = os.path.join(self.temp_dir.name, "ke_hoach_nghien_cuu.md")
        with open(self.doc2_path, "w", encoding="utf-8") as f:
            f.write("# Kế Hoạch Nghiên Cứu\n\nTham chiếu tới [[Báo Cáo Tài Chính 2026]]\n\n#research")
        self.doc2_id = str(uuid.uuid4())
        self.index.upsert_document(self.doc2_path, "Kế Hoạch Nghiên Cứu", "hash2", doc_id=self.doc2_id)
        self.index.set_document_tags(self.doc2_id, ["research"])

        # Add link in DB from doc2 to doc1
        with self.index.get_connection() as conn:
            conn.execute("""
                INSERT INTO wikilinks (source_id, target_id, target_title_raw, snippet, resolved)
                VALUES (?, ?, ?, ?, 1)
            """, (self.doc2_id, self.doc1_id, "Báo Cáo Tài Chính 2026", "Tham chiếu tới [[Báo Cáo Tài Chính 2026]]"))
            conn.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_manifest_schema(self):
        """Verifies tool manifest contains all 6 required tools and valid schemas."""
        self.assertEqual(len(MCP_TOOLS_MANIFEST), 6)
        names = {t["name"] for t in MCP_TOOLS_MANIFEST}
        expected = {
            "search_documents",
            "read_document",
            "convert_document",
            "tag_document",
            "list_backlinks",
            "write_document_content"
        }
        self.assertEqual(names, expected)
        for t in MCP_TOOLS_MANIFEST:
            self.assertIn("name", t)
            self.assertIn("description", t)
            self.assertIn("inputSchema", t)

    def test_search_documents_by_title_fuzzy(self):
        """Test searching documents with Vietnamese accents and fuzzy query."""
        res = handle_search_documents(query="tai chinh", index=self.index)
        self.assertGreaterEqual(res["total_matches"], 1)
        self.assertEqual(res["results"][0]["document_id"], self.doc1_id)
        self.assertIn("finance", res["results"][0]["tags"])

    def test_search_documents_by_tag_filter(self):
        """Test searching with tag filters (AND condition)."""
        res = handle_search_documents(tags=["finance"], index=self.index)
        self.assertEqual(res["total_matches"], 1)
        self.assertEqual(res["results"][0]["document_id"], self.doc1_id)

        # Non-matching tag
        res_none = handle_search_documents(tags=["nonexistent_tag"], index=self.index)
        self.assertEqual(res_none["total_matches"], 0)

    def test_read_document_valid(self):
        """Test reading a valid document by UUID."""
        res = handle_read_document(self.doc1_id, index=self.index)
        self.assertNotIn("error", res)
        self.assertEqual(res["document_id"], self.doc1_id)
        self.assertIn("# Báo Cáo Tài Chính 2026", res["content"])
        self.assertIn("finance", res["tags"])

    def test_read_document_invalid_id(self):
        """Test reading with an invalid UUID."""
        res = handle_read_document("invalid-uuid", index=self.index)
        self.assertIn("error", res)
        self.assertEqual(res["error"], "DOCUMENT_NOT_FOUND")

    def test_tag_document_add_and_remove(self):
        """Test adding and removing tags from document."""
        # Initial tags: ['finance', 'report', 'tieng-viet']
        res = handle_tag_document(
            document_id=self.doc1_id,
            add_tags=["urgent", "2026"],
            remove_tags=["report"],
            index=self.index
        )
        self.assertEqual(res["status"], "success")
        current_tags = res["current_tags"]
        self.assertIn("urgent", current_tags)
        self.assertIn("2026", current_tags)
        self.assertNotIn("report", current_tags)
        self.assertIn("finance", current_tags)

        # Verify DB directly
        db_tags = self.index.get_document_tags(self.doc1_id)
        self.assertEqual(sorted(db_tags), sorted(current_tags))

    def test_list_backlinks(self):
        """Test retrieving backlinks to doc1 from doc2."""
        res = handle_list_backlinks(self.doc1_id, index=self.index)
        self.assertNotIn("error", res)
        self.assertEqual(res["document_id"], self.doc1_id)
        self.assertEqual(res["linked_references_count"], 1)
        self.assertEqual(res["linked_references"][0]["source_id"], self.doc2_id)

    def test_convert_document_txt_and_html(self):
        """Test converting Markdown document to TXT and HTML format."""
        res_txt = handle_convert_document(self.doc1_id, target_format="txt", index=self.index)
        self.assertEqual(res_txt["status"], "success")
        self.assertTrue(os.path.exists(res_txt["output_path"]))
        self.assertTrue(res_txt["output_path"].endswith(".txt"))

        res_html = handle_convert_document(self.doc1_id, target_format="html", index=self.index)
        self.assertEqual(res_html["status"], "success")
        self.assertTrue(os.path.exists(res_html["output_path"]))
        self.assertTrue(res_html["output_path"].endswith(".html"))

    def test_write_document_content_and_reindex(self):
        """Test updating document content and ensuring DB sync."""
        new_content = "# Báo Cáo Mới Cập Nhật\n\nNội dung đã được AI chỉnh sửa.\n\n#ai #updated"
        res = handle_write_document_content(self.doc1_id, new_content, index=self.index)
        self.assertEqual(res["status"], "success")

        # Check physical file
        with open(self.doc1_path, "r", encoding="utf-8") as f:
            disk_content = f.read()
        self.assertEqual(disk_content, new_content)

        # Check index updated title and tags
        doc = self.index.get_document_by_id(self.doc1_id)
        self.assertEqual(doc["title"], "Báo Cáo Mới Cập Nhật")
        tags = self.index.get_document_tags(self.doc1_id)
        self.assertIn("ai", tags)
        self.assertIn("updated", tags)


if __name__ == "__main__":
    unittest.main()
