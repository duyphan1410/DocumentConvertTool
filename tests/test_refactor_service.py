"""
Unit tests for RefactorService (PKB Phase 1.5 - Priority 3 / Items 5-7).
Verifies link renaming, alias preservation, heading preservation, transclusion updates, and graph integrity.
"""
import os
import tempfile
import unittest

from src.services.refactor_service import (
    refactor_markdown_links,
    refactor_document_rename_workspace,
)


class TestRefactorService(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_refactor_basic_wikilinks(self):
        content = "See [[Old Note]] and another [[Old Note]] here."
        res, count = refactor_markdown_links(content, "Old Note", "New Note")
        self.assertEqual(count, 2)
        self.assertEqual(res, "See [[New Note]] and another [[New Note]] here.")

    def test_refactor_wikilinks_with_alias_and_headings(self):
        content = """Check [[Old Note|Custom Alias]] for details.
Also see [[Old Note#Section 2]] and [[Old Note#Section 2|Aliased Section]].
Embedded: ![[Old Note]] and ![[Old Note#Architecture]].
"""
        res, count = refactor_markdown_links(content, "Old Note", "Renamed Doc")
        self.assertEqual(count, 5)
        self.assertIn("[[Renamed Doc|Custom Alias]]", res)
        self.assertIn("[[Renamed Doc#Section 2]]", res)
        self.assertIn("[[Renamed Doc#Section 2|Aliased Section]]", res)
        self.assertIn("![[Renamed Doc]]", res)
        self.assertIn("![[Renamed Doc#Architecture]]", res)

    def test_refactor_code_blocks_preserved(self):
        content = """```markdown
[[Old Note]] in code block should remain untouched
```
Inline code `[[Old Note]]` preserved.
Real link [[Old Note]] updated.
"""
        res, count = refactor_markdown_links(content, "Old Note", "Updated Note")
        self.assertEqual(count, 1)
        self.assertIn("[[Old Note]] in code block", res)
        self.assertIn("`[[Old Note]]`", res)
        self.assertIn("Real link [[Updated Note]]", res)

    def test_workspace_cascade_rename(self):
        # File A points to File B
        file_a = os.path.join(self.workspace, "Index.md")
        file_b = os.path.join(self.workspace, "Roadmap2026.md")
        new_file_b = os.path.join(self.workspace, "ProductRoadmap.md")

        with open(file_a, "w", encoding="utf-8") as f:
            f.write("# Index\n- Plan: [[Roadmap2026]]\n- Embedded: ![[Roadmap2026#Q1]]")

        with open(file_b, "w", encoding="utf-8") as f:
            f.write("# Roadmap 2026\n## Q1\nDeliverables...")

        # Rename File B on disk
        os.rename(file_b, new_file_b)

        result = refactor_document_rename_workspace(
            old_path=file_b,
            new_path=new_file_b,
            workspace_folder=self.workspace,
        )

        self.assertEqual(result["files_modified"], 1)
        self.assertEqual(result["links_updated"], 2)

        with open(file_a, "r", encoding="utf-8") as f:
            updated_index = f.read()

        self.assertIn("[[ProductRoadmap]]", updated_index)
        self.assertIn("![[ProductRoadmap#Q1]]", updated_index)
        self.assertNotIn("Roadmap2026", updated_index)

    def test_self_referencing_link_rename(self):
        # File has a self-reference: e.g. [[output]] inside output.md
        file_path = os.path.join(self.workspace, "output.md")
        new_file_path = os.path.join(self.workspace, "output2.md")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("# Output Doc\nSee my self link: [[output]] and section [[output#Details]]")

        os.rename(file_path, new_file_path)

        result = refactor_document_rename_workspace(
            old_path=file_path,
            new_path=new_file_path,
            workspace_folder=self.workspace,
        )

        self.assertEqual(result["files_modified"], 1)
        self.assertEqual(result["links_updated"], 2)

        with open(new_file_path, "r", encoding="utf-8") as f:
            updated_content = f.read()

        self.assertIn("[[output2]]", updated_content)
        self.assertIn("[[output2#Details]]", updated_content)
        self.assertNotIn("[[output]]", updated_content)


if __name__ == "__main__":
    unittest.main()

