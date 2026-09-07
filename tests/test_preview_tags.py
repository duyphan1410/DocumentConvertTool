"""
Unit tests for process_markdown_tags in Markdown Live Preview (PKB Phase 1.5).
Verifies that inline #tags become clickable links while excluding headings, code blocks, URLs, and inline code.
"""
import unittest
from src.ui_flet.views.preview_view import process_markdown_tags


class TestPreviewTags(unittest.TestCase):
    def test_basic_tag_conversion(self):
        text = "This note has #ai and #deep_learning tags."
        res = process_markdown_tags(text)
        self.assertIn("[🏷️ #ai](tag://ai)", res)
        self.assertIn("[🏷️ #deep_learning](tag://deep_learning)", res)

    def test_nested_tags(self):
        text = "Learning #dev/python/flet is fun."
        res = process_markdown_tags(text)
        self.assertIn("[🏷️ #dev/python/flet](tag://dev/python/flet)", res)

    def test_headings_not_converted(self):
        text = "# Heading 1\n## Heading 2\n### Heading 3\nContent #real_tag here."
        res = process_markdown_tags(text)
        self.assertIn("# Heading 1", res)
        self.assertIn("## Heading 2", res)
        self.assertIn("### Heading 3", res)
        self.assertIn("[🏷️ #real_tag](tag://real_tag)", res)

    def test_code_blocks_and_inline_code_not_converted(self):
        text = """Here is `#inline_code` and a block:
```python
# This is a python comment, not a tag
import os
```
And outside is #actual_tag."""
        res = process_markdown_tags(text)
        self.assertIn("`#inline_code`", res)
        self.assertIn("# This is a python comment", res)
        self.assertIn("[🏷️ #actual_tag](tag://actual_tag)", res)

    def test_urls_with_anchor_not_converted(self):
        text = "Visit https://example.com/page#section for info or see [Link](https://abc.com#anchor). Also #valid_tag."
        res = process_markdown_tags(text)
        self.assertIn("https://example.com/page#section", res)
        self.assertIn("[Link](https://abc.com#anchor)", res)
        self.assertIn("[🏷️ #valid_tag](tag://valid_tag)", res)


if __name__ == "__main__":
    unittest.main()
