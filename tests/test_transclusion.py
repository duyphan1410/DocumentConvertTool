"""
Unit tests for Transclusion Engine & Embed Service (PKB Phase 1.5 - Priority 2).
"""
import os
import tempfile
import unittest

from src.services.transclusion_service import (
    strip_frontmatter,
    extract_heading_section,
    process_markdown_transclusions,
)


class TestTransclusionService(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_strip_frontmatter(self):
        content = "---\ntitle: My Note\ntags: [ai, pkb]\n---\n# Main Heading\nHello world"
        stripped = strip_frontmatter(content)
        self.assertEqual(stripped, "# Main Heading\nHello world")

        no_fm = "# Heading\nText"
        self.assertEqual(strip_frontmatter(no_fm), no_fm)

    def test_extract_heading_section(self):
        doc = """# Introduction
This is intro text.

## Section Alpha
Alpha line 1.
Alpha line 2.

### Sub Alpha
Sub detail.

## Section Beta
Beta line 1.

# Conclusion
Ending.
"""
        alpha_section = extract_heading_section(doc, "Section Alpha")
        self.assertIn("## Section Alpha", alpha_section)
        self.assertIn("Alpha line 1.", alpha_section)
        self.assertIn("### Sub Alpha", alpha_section)
        self.assertNotIn("## Section Beta", alpha_section)
        self.assertNotIn("# Conclusion", alpha_section)

        beta_section = extract_heading_section(doc, "Section Beta")
        self.assertIn("## Section Beta", beta_section)
        self.assertIn("Beta line 1.", beta_section)
        self.assertNotIn("Alpha line 1.", beta_section)
        self.assertNotIn("# Conclusion", beta_section)

        missing_section = extract_heading_section(doc, "NonExistent")
        self.assertIn("Không tìm thấy đề mục", missing_section)

    def test_image_embed_conversion(self):
        content = "Here is an image: ![[diagram.png]] and with size: ![[photo.jpg|400]] and with alt: ![[avatar.png|User Avatar]]"
        result = process_markdown_transclusions(content, base_dir=self.base_dir)

        self.assertIn("![diagram.png](diagram.png)", result)
        self.assertIn("![photo.jpg|400](photo.jpg)", result)
        self.assertIn("![User Avatar](avatar.png)", result)

    def test_attachment_embed(self):
        content = "Download here: ![[annual_report.pdf]]"
        result = process_markdown_transclusions(content, base_dir=self.base_dir)
        self.assertIn("📎", result)
        self.assertIn("annual_report.pdf", result)
        self.assertIn("PDF File", result)

    def test_note_transclusion_full(self):
        note_path = os.path.join(self.base_dir, "SummaryNote.md")
        with open(note_path, "w", encoding="utf-8") as f:
            f.write("# Executive Summary\nAll operations are smooth.\n- Task 1\n- Task 2")

        content = "Parent Note Header\n\n![[SummaryNote]]\n\nParent Note Footer"
        result = process_markdown_transclusions(content, base_dir=self.base_dir)

        self.assertIn("SummaryNote", result)
        self.assertIn("> # Executive Summary", result)
        self.assertIn("> All operations are smooth.", result)
        self.assertIn("> - Task 1", result)

    def test_note_transclusion_with_heading(self):
        note_path = os.path.join(self.base_dir, "ProjectPlan.md")
        with open(note_path, "w", encoding="utf-8") as f:
            f.write("# Main\nMain text.\n\n## Timeline\nQ1: Launch\nQ2: Scale\n\n## Budget\n$10,000")

        content = "Embedding timeline:\n![[ProjectPlan#Timeline]]"
        result = process_markdown_transclusions(content, base_dir=self.base_dir)

        self.assertIn("ProjectPlan > #Timeline", result)
        self.assertIn("> ## Timeline", result)
        self.assertIn("> Q1: Launch", result)
        self.assertNotIn("Budget", result)

    def test_circular_transclusion_prevention(self):
        # Note A embeds Note B, Note B embeds Note A
        path_a = os.path.join(self.base_dir, "NoteA.md")
        path_b = os.path.join(self.base_dir, "NoteB.md")

        with open(path_a, "w", encoding="utf-8") as f:
            f.write("Content A\n![[NoteB]]")

        with open(path_b, "w", encoding="utf-8") as f:
            f.write("Content B\n![[NoteA]]")

        content = "Root doc\n![[NoteA]]"
        result = process_markdown_transclusions(content, base_dir=self.base_dir)

        self.assertIn("Content A", result)
        self.assertIn("Content B", result)
        self.assertIn("Vòng lặp nhúng (Circular Embed)", result)

    def test_code_block_exclusion(self):
        content = """```markdown
Do not embed: ![[sample.png]]
Do not transclude: ![[MyNote]]
```
Inline code `![[not_this.png]]` should be preserved.
Real embed: ![[real.png]]
"""
        result = process_markdown_transclusions(content, base_dir=self.base_dir)
        self.assertIn("Do not embed: ![[sample.png]]", result)
        self.assertIn("`![[not_this.png]]`", result)
        self.assertIn("![real.png](real.png)", result)

    def test_get_document_excerpt(self):
        from src.services.transclusion_service import get_document_excerpt
        note_path = os.path.join(self.base_dir, "DocExcerptTest.md")
        with open(note_path, "w", encoding="utf-8") as f:
            f.write("---\ntags: [test]\n---\n# Title\nLine 1 of content\nLine 2 of content\nLine 3 of content\nLine 4 of content\nLine 5 of content\nLine 6 of content")

        excerpt = get_document_excerpt(note_path, max_lines=5)
        self.assertIn("Line 1 of content", excerpt)
        self.assertIn("Line 4 of content", excerpt)
        self.assertNotIn("Line 6 of content", excerpt)


if __name__ == "__main__":
    unittest.main()
