import os
import tempfile
import unittest
from src.services.history_service import HistoryService


class TestHistoryService(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.storage_path = os.path.join(self.tmpdir.name, "recent_history.json")
        self.service = HistoryService(storage_path=self.storage_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_add_and_get_files(self):
        self.service.add_file("C:/fake/path/doc1.docx", mode="Word -> MD")
        self.service.add_file("C:/fake/path/doc2.md", mode="MD -> HTML")

        items = self.service.get_items("files")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["name"], "doc2.md")
        self.assertEqual(items[1]["name"], "doc1.docx")

    def test_add_and_get_folders(self):
        self.service.add_folder("C:/fake/workspace/project1")
        self.service.add_folder("C:/fake/workspace/project2")

        items = self.service.get_items("folders")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["name"], "project2")
        self.assertEqual(items[1]["name"], "project1")

    def test_lru_and_deduplication(self):
        self.service.add_file("C:/fake/doc1.md")
        self.service.add_file("C:/fake/doc2.md")
        # Re-add doc1
        self.service.add_file("C:/fake/doc1.md")

        items = self.service.get_items("files")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["name"], "doc1.md")
        self.assertEqual(items[1]["name"], "doc2.md")

    def test_pinning(self):
        self.service.add_file("C:/fake/doc1.md")
        self.service.add_file("C:/fake/doc2.md")

        # Pin doc1
        is_pinned = self.service.toggle_pin("C:/fake/doc1.md", "file")
        self.assertTrue(is_pinned)

        # Add doc3
        self.service.add_file("C:/fake/doc3.md")

        items = self.service.get_items("files")
        # doc1 is pinned so should remain at top
        self.assertEqual(items[0]["name"], "doc1.md")
        self.assertTrue(items[0]["pinned"])
        self.assertEqual(items[1]["name"], "doc3.md")
        self.assertEqual(items[2]["name"], "doc2.md")

        # Unpin doc1
        is_pinned_after = self.service.toggle_pin("C:/fake/doc1.md", "file")
        self.assertFalse(is_pinned_after)

    def test_remove_and_clear(self):
        self.service.add_file("C:/fake/doc1.md")
        self.service.add_folder("C:/fake/folder1")

        self.service.remove_item("C:/fake/doc1.md", "file")
        self.assertEqual(len(self.service.get_items("files")), 0)
        self.assertEqual(len(self.service.get_items("folders")), 1)

        self.service.clear_all("all")
        self.assertEqual(len(self.service.get_items("all")), 0)

    def test_search_query(self):
        self.service.add_file("C:/fake/financial_report.xlsx")
        self.service.add_file("C:/fake/readme.md")

        res = self.service.get_items("all", query="finan")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["name"], "financial_report.xlsx")

    def test_welcome_view_instantiation(self):
        from src.ui_flet.views.welcome_view import WelcomeView
        view = WelcomeView()
        self.assertIsNotNone(view.card_container)
        view.update_responsive_layout(1000)
        view.update_responsive_layout(600)
        view.update_responsive_layout(1200)
        view.update_locale()
        self.assertIsNotNone(view.content)


if __name__ == "__main__":
    unittest.main()
