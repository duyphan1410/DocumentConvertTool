import os
from src.core.base_module import BaseDocumentModule
from src.core.registry import ModuleRegistry

class HTMLModule(BaseDocumentModule):
    @property
    def name(self) -> str:
        return "HTML"

    @property
    def file_extensions(self) -> list[str]:
        return [".html", ".htm"]

    @property
    def required_dependencies(self) -> list[str]:
        return ["markdown2", "markitdown"]

    def load_to_markdown(self, file_path: str) -> str:
        """Loads physical HTML file and extracts it to Markdown text using markitdown."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            from markitdown import MarkItDown
            md = MarkItDown()
            result = md.convert(file_path)
            if not result or not result.text_content:
                return "*(Empty HTML)*"
            return result.text_content
        except Exception as e:
            raise RuntimeError(f"HTML Ingestion Error: Failed to extract text from HTML. Detail: {str(e)}")

    def save_from_markdown(self, markdown_content: str, out_path: str) -> str:
        """Converts Markdown text and saves it to a styled HTML document."""
        try:
            import markdown2
            # Convert Markdown to HTML using markdown2 with extras
            # - "fenced-code-blocks" enables GitHub-like code formatting blocks
            # - "tables" enables rendering markdown tables
            # - "strike" enables strikethroughs with ~~text~~
            # - "underline" allows parsing <u> tags
            html_body = markdown2.markdown(
                markdown_content,
                extras=["fenced-code-blocks", "tables", "strike", "underline"]
            )

            # HTML Template with beautiful modern CSS styles supporting both Light and Dark themes
            # using system preference (prefers-color-scheme)
            html_document = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Exported Document</title>
    <style>
        :root {{
            --bg-color: #ffffff;
            --text-color: #24292e;
            --container-bg: #ffffff;
            --border-color: #e1e4e8;
            --heading-border: #eaecef;
            --code-bg: #f6f8fa;
            --table-header-bg: #f6f8fa;
            --table-zebra-bg: #f8f9fa;
            --link-color: #0366d6;
            --blockquote-color: #6a737d;
            --blockquote-border: #dfe2e5;
        }}

        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg-color: #0d1117;
                --text-color: #c9d1d9;
                --container-bg: #0d1117;
                --border-color: #30363d;
                --heading-border: #21262d;
                --code-bg: #161b22;
                --table-header-bg: #161b22;
                --table-zebra-bg: #161b22;
                --link-color: #58a6ff;
                --blockquote-color: #8b949e;
                --blockquote-border: #30363d;
            }}
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            word-wrap: break-word;
            margin: 0;
            padding: 2rem 1.5rem;
        }}

        .container {{
            max-width: 850px;
            margin: 0 auto;
            background-color: var(--container-bg);
        }}

        h1, h2, h3, h4, h5, h6 {{
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
            line-height: 1.25;
        }}

        h1 {{
            font-size: 2em;
            padding-bottom: 0.3em;
            border-bottom: 1px solid var(--heading-border);
        }}

        h2 {{
            font-size: 1.5em;
            padding-bottom: 0.3em;
            border-bottom: 1px solid var(--heading-border);
        }}

        h3 {{
            font-size: 1.25em;
        }}

        p {{
            margin-top: 0;
            margin-bottom: 16px;
        }}

        a {{
            color: var(--link-color);
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        code {{
            padding: 0.2em 0.4em;
            margin: 0;
            font-size: 85%;
            background-color: var(--code-bg);
            border-radius: 3px;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        }}

        pre {{
            padding: 16px;
            overflow: auto;
            font-size: 85%;
            line-height: 1.45;
            background-color: var(--code-bg);
            border-radius: 6px;
            margin-top: 0;
            margin-bottom: 16px;
        }}

        pre code {{
            padding: 0;
            margin: 0;
            font-size: 100%;
            background-color: transparent;
            border: 0;
            word-break: normal;
            white-space: pre;
        }}

        blockquote {{
            padding: 0 1em;
            color: var(--blockquote-color);
            border-left: 0.25em solid var(--blockquote-border);
            margin: 0 0 16px 0;
        }}

        ul, ol {{
            padding-left: 2em;
            margin-top: 0;
            margin-bottom: 16px;
        }}

        table {{
            border-spacing: 0;
            border-collapse: collapse;
            width: 100%;
            margin-top: 0;
            margin-bottom: 16px;
            overflow-x: auto;
            display: block;
        }}

        table th, table td {{
            padding: 6px 13px;
            border: 1px solid var(--border-color);
        }}

        table th {{
            font-weight: 600;
            background-color: var(--table-header-bg);
        }}

        table tr:nth-child(even) {{
            background-color: var(--table-zebra-bg);
        }}

        hr {{
            height: 0.25em;
            padding: 0;
            margin: 24px 0;
            background-color: var(--border-color);
            border: 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        {html_body}
    </div>
</body>
</html>
"""
            # Ensure output directory exists
            out_dir = os.path.dirname(out_path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html_document)

            return f"Exported successfully to HTML -> {os.path.basename(out_path)}"
        except Exception as e:
            raise RuntimeError(f"HTML Export Error: Failed to generate HTML document. Detail: {str(e)}")

ModuleRegistry.register(HTMLModule())
