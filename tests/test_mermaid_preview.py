"""
Unit tests for Mermaid Diagram Live Preview Interceptor in Flet UI.
"""
import unittest
import json
import base64
import collections
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from src.ui_flet.views.preview_view import (
    encode_mermaid_payload,
    render_mermaid_diagram,
    process_markdown_mermaid,
    process_markdown_media,
    MarkdownPreview,
    _MERMAID_CACHE,
    MAX_MERMAID_CACHE_SIZE,
)


class TestMermaidPreview(unittest.TestCase):
    def setUp(self):
        _MERMAID_CACHE.clear()

    def test_encode_mermaid_payload_light_and_dark(self):
        code = "graph TD\nA-->B"
        
        # Test Light Theme
        payload_light = encode_mermaid_payload(code, is_dark=False, palette_name="Violet Cyberpunk")
        decoded_json_light = json.loads(base64.b64decode(payload_light).decode("utf-8"))
        self.assertEqual(decoded_json_light["code"], code)
        self.assertEqual(decoded_json_light["mermaid"]["theme"], "base")
        self.assertFalse(decoded_json_light["mermaid"]["themeVariables"]["darkMode"])
        self.assertIn("primaryTextColor", decoded_json_light["mermaid"]["themeVariables"])

        # Test Dark Theme
        payload_dark = encode_mermaid_payload(code, is_dark=True, palette_name="Violet Cyberpunk")
        decoded_json_dark = json.loads(base64.b64decode(payload_dark).decode("utf-8"))
        self.assertEqual(decoded_json_dark["code"], code)
        self.assertEqual(decoded_json_dark["mermaid"]["theme"], "base")
        self.assertTrue(decoded_json_dark["mermaid"]["themeVariables"]["darkMode"])
        self.assertIn("lineColor", decoded_json_dark["mermaid"]["themeVariables"])
        self.assertEqual(decoded_json_dark["mermaid"]["themeVariables"]["primaryTextColor"], "#f8fafc")

    def test_process_markdown_mermaid_basic(self):
        md = "# Architecture\n```mermaid\ngraph TD\n    A[Client] --> B[Server]\n```\nEnd of doc."
        result = process_markdown_mermaid(md, is_dark=False, enable_cloud=True)
        self.assertNotIn("```mermaid", result)
        self.assertIn("![Mermaid Diagram](", result)
        self.assertIn("End of doc.", result)

    def test_non_mermaid_code_blocks_preserved(self):
        md = (
            "# Code Example\n"
            "```python\ndef hello():\n    return 'world'\n```\n\n"
            "```json\n{\"status\": \"ok\"}\n```\n"
        )
        result = process_markdown_mermaid(md, is_dark=False)
        self.assertEqual(result, md)

    def test_multiple_mermaid_blocks(self):
        md = (
            "# Workflow\n"
            "```mermaid\ngraph LR\n    A --> B\n```\n"
            "Some intermediate text.\n"
            "```mermaid\nsequenceDiagram\n    Alice->>Bob: Hello\n```\n"
        )
        result = process_markdown_mermaid(md, is_dark=True)
        self.assertNotIn("```mermaid", result)
        self.assertEqual(result.count("![Mermaid Diagram]("), 2)
        self.assertIn("Some intermediate text.", result)

    def test_empty_or_whitespace_mermaid_fallback(self):
        md = "```mermaid\n   \n```"
        result = process_markdown_mermaid(md, is_dark=False)
        self.assertIn("```mermaid", result)

    def test_cloud_disabled_fallback_when_no_local_cli(self):
        code = "graph TD\nA-->B"
        md = f"```mermaid\n{code}\n```"
        # When cloud is disabled and assuming no mmdc, it should safely return code block
        import unittest.mock as mock
        with mock.patch("shutil.which", return_value=None):
            result = process_markdown_mermaid(md, is_dark=False, enable_cloud=False)
            self.assertIn("```mermaid", result)

    def test_lru_cache_size_limit(self):
        self.assertEqual(len(_MERMAID_CACHE), 0)
        import unittest.mock as mock
        mock_response = mock.MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"\x89PNG\r\n\x1a\n"

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            for i in range(MAX_MERMAID_CACHE_SIZE + 20):
                diagram = f"graph TD\nA{i}-->B{i}"
                render_mermaid_diagram(diagram, is_dark=False, enable_cloud=True)

        self.assertLessEqual(len(_MERMAID_CACHE), MAX_MERMAID_CACHE_SIZE)

    def test_markdown_preview_theme_synchronization(self):
        preview = MarkdownPreview()
        md = "# Diagram\n```mermaid\ngraph TD\n    A-->B\n```"
        preview.set_content(md)
        self.assertIn("![Mermaid Diagram](", preview.markdown.value)

        # Toggle palette / theme to dark
        palette = {"text_accent_primary": "#60a5fa", "border_color": "#374151", "bg_component": "#1f2937", "bg_header": "#111827"}
        preview.apply_palette(palette, is_dark=True)
        self.assertTrue(preview._is_dark)
        self.assertIn("![Mermaid Diagram](", preview.markdown.value)

    def test_export_pipeline_renders_mermaid_as_image(self):
        from src.core.converters import prepare_markdown_for_export
        from src.modules.word_module import WordModule
        import tempfile
        import os

        md = "# Export Test\n```mermaid\ngraph TD\n    A[Step 1] --> B[Step 2]\n```\nDone."
        prepared = prepare_markdown_for_export(md)
        self.assertNotIn("```mermaid", prepared)
        self.assertIn("![Mermaid Diagram](", prepared)

        # Test actual DOCX generation
        wm = WordModule()
        out_docx = os.path.join(tempfile.gettempdir(), "test_mermaid_export.docx")
        try:
            wm.save_from_markdown(md, out_docx)
            self.assertTrue(os.path.exists(out_docx))
            self.assertGreater(os.path.getsize(out_docx), 0)
        finally:
            if os.path.exists(out_docx):
                try:
                    os.remove(out_docx)
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
