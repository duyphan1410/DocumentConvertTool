import os
import re
import base64
import mimetypes
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
        return ["markdown2", "beautifulsoup4", "Pygments"]

    def load_to_markdown(self, file_path: str) -> str:
        """Loads physical HTML file and extracts it to Markdown text using BeautifulSoup structure parsing."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            try:
                from markitdown import MarkItDown
                md = MarkItDown()
                result = md.convert(file_path)
                if result and result.text_content and result.text_content.strip():
                    return result.text_content
            except Exception:
                pass

            try:
                from bs4 import BeautifulSoup, NavigableString, Tag
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    soup = BeautifulSoup(f.read(), "html.parser")

                # Decompose non-content elements
                for elem in soup(["script", "style", "head", "title"]):
                    elem.decompose()

                container = soup.find(class_="markdown-body") or soup.find("body") or soup

                def parse_node(node, depth=0):
                    if isinstance(node, NavigableString):
                        return str(node)
                    if not isinstance(node, Tag):
                        return ""

                    tag = node.name.lower()

                    if tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                        level = int(tag[1])
                        text = "".join(parse_node(child, depth) for child in node.children).strip()
                        return f"\n\n{'#' * level} {text}\n\n"

                    elif tag == "p":
                        text = "".join(parse_node(child, depth) for child in node.children).strip()
                        return f"\n\n{text}\n\n"

                    elif tag == "pre":
                        code_tag = node.find("code")
                        lang = ""
                        if code_tag and code_tag.get("class"):
                            for c in code_tag["class"]:
                                if c.startswith("language-"):
                                    lang = c.replace("language-", "")
                                elif c != "codehilite":
                                    lang = c
                        code_text = (code_tag or node).get_text()
                        return f"\n\n```{lang}\n{code_text.strip()}\n```\n\n"

                    elif tag == "code":
                        if node.parent and node.parent.name == "pre":
                            return "".join(parse_node(child, depth) for child in node.children)
                        return f"`{node.get_text()}`"

                    elif tag in ["strong", "b"]:
                        inner = "".join(parse_node(child, depth) for child in node.children).strip()
                        return f"**{inner}**" if inner else ""

                    elif tag in ["em", "i"]:
                        inner = "".join(parse_node(child, depth) for child in node.children).strip()
                        return f"*{inner}*" if inner else ""

                    elif tag in ["del", "strike", "s"]:
                        inner = "".join(parse_node(child, depth) for child in node.children).strip()
                        return f"~~{inner}~~" if inner else ""

                    elif tag == "a":
                        href = node.get("href", "")
                        text = "".join(parse_node(child, depth) for child in node.children).strip()
                        return f"[{text}]({href})" if href else text

                    elif tag == "img":
                        src = node.get("src", "")
                        alt = node.get("alt", "")
                        return f"![{alt}]({src})"

                    elif tag == "blockquote":
                        inner = "".join(parse_node(child, depth) for child in node.children).strip()
                        lines = inner.split("\n")
                        quoted = "\n".join(f"> {l}" for l in lines)
                        return f"\n\n{quoted}\n\n"

                    elif tag == "hr":
                        return "\n\n---\n\n"

                    elif tag == "table":
                        tr_elements = []
                        for sec in node.find_all(["thead", "tbody", "tfoot"], recursive=False):
                            tr_elements.extend(sec.find_all("tr", recursive=False))
                        if not tr_elements:
                            tr_elements = node.find_all("tr", recursive=False)

                        rows = []
                        for tr in tr_elements:
                            cells = [td.get_text().strip().replace("\n", "<br>").replace("|", "\\|") for td in tr.find_all(["th", "td"], recursive=False)]
                            if cells:
                                rows.append(cells)
                        if not rows:
                            return ""
                        headers = rows[0]
                        md_lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
                        for r in rows[1:]:
                            if len(r) < len(headers):
                                r.extend([""] * (len(headers) - len(r)))
                            md_lines.append("| " + " | ".join(r[:len(headers)]) + " |")
                        return "\n\n" + "\n".join(md_lines) + "\n\n"

                    elif tag in ["ul", "ol"]:
                        items = []
                        indent = "  " * depth
                        for idx, li in enumerate(node.find_all("li", recursive=False)):
                            inline_parts = []
                            nested_lists = []
                            for child in li.children:
                                if isinstance(child, Tag) and child.name.lower() in ["ul", "ol"]:
                                    nested_lists.append(child)
                                else:
                                    inline_parts.append(parse_node(child, depth + 1))

                            item_text = "".join(inline_parts).strip()
                            prefix = f"{idx + 1}." if tag == "ol" else "-"
                            item_str = f"{indent}{prefix} {item_text}"

                            if nested_lists:
                                sub_str = "\n".join(parse_node(nl, depth + 1).strip() for nl in nested_lists)
                                item_str += f"\n{sub_str}"

                            items.append(item_str)
                        return "\n\n" + "\n".join(items) + "\n\n"

                    else:
                        return "".join(parse_node(child, depth) for child in node.children)

                result = parse_node(container)
                result = re.sub(r"\n{3,}", "\n\n", result).strip()
                if result:
                    return result
                return soup.get_text()
            except Exception as bs_err:
                print(f"[DEBUG] HTMLModule: Structured BS4 parse failed: {bs_err}")
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
        except Exception as e:
            raise RuntimeError(f"HTML Ingestion Error: Failed to extract text from HTML. Detail: {str(e)}")

    def save_from_markdown(self, markdown_content: str, out_path: str) -> str:
        """Converts Markdown text and saves it to a styled HTML document."""
        try:
            from src.services.media_asset_manager import MediaAssetManager
            asset_mgr = MediaAssetManager()

            def resolve_to_base64(src: str) -> str:
                """Resolve @media/ URI or local path to an inline base64 data URI.
                Remote URLs (http/https) and existing data URIs are passed through unchanged.
                Falls back to the original src string if the file cannot be found.
                """
                if not src or src.startswith(("http://", "https://", "data:")):
                    return src
                resolved = asset_mgr.resolve_uri(src)
                if os.path.isfile(resolved):
                    mime, _ = mimetypes.guess_type(resolved)
                    if not mime:
                        mime = "image/png"
                    with open(resolved, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                    return f"data:{mime};base64,{b64}"
                print(f"[DEBUG] HTMLModule: Image not found, keeping original src: {src}")
                return src

            def replace_md_image(match):
                alt, src = match.group(1), match.group(2)
                return f"![{alt}]({resolve_to_base64(src)})"

            # Resolve @media/ URIs on raw markdown BEFORE converting to HTML.
            processed_md = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_md_image, markdown_content)

            # Auto-repair malformed code blocks safely:
            # 1. Insert missing newline after ```lang if at start of line and NOT ending with ``` on same line
            def fix_fence(match):
                prefix = match.group(1)
                lang = match.group(2)
                rest = match.group(3)
                if rest.rstrip().endswith("```"):
                    return match.group(0)  # Keep inline triple backticks unchanged
                return f"{prefix}```{lang}\n{rest}"

            processed_md = re.sub(r'(^|\n)```([a-zA-Z0-9_\-+]+)[ \t]+([^\n]+)', fix_fence, processed_md)
            # 2. Insert missing blank line before ``` if preceded directly by text
            processed_md = re.sub(r'([^\n])\n```', r'\1\n\n```', processed_md)

            try:
                import markdown2
                html_body = markdown2.markdown(
                    processed_md,
                    extras=["fenced-code-blocks", "tables", "strike", "underline"]
                )
            except ImportError:
                try:
                    import markdown
                    html_body = markdown.markdown(processed_md, extensions=["fenced_code", "tables"])
                except ImportError:
                    # Simple fallback when external markdown libraries are not installed
                    lines = processed_md.split("\n")
                    html_body = "\n".join(f"<p>{l}</p>" if l.strip() else "<br/>" for l in lines)

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
            --syntax-keyword: #d73a49;
            --syntax-func: #6f42c1;
            --syntax-string: #032f62;
            --syntax-comment: #6a737d;
            --syntax-builtin: #005cc5;
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
                --syntax-keyword: #ff79c6;
                --syntax-func: #d2a8ff;
                --syntax-string: #a5d6ff;
                --syntax-comment: #8b949e;
                --syntax-builtin: #79c0ff;
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

        .markdown-body {{
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

        .codehilite {{
            background-color: var(--code-bg);
            border-radius: 6px;
            margin-top: 0;
            margin-bottom: 16px;
            border: 1px solid var(--border-color);
        }}

        .codehilite pre {{
            margin: 0;
            padding: 16px;
            overflow: auto;
            font-size: 85%;
            line-height: 1.45;
            background: transparent;
            border: 0;
        }}

        .codehilite .k, .codehilite .kd, .codehilite .kn {{ color: var(--syntax-keyword); font-weight: bold; }}
        .codehilite .nf, .codehilite .fm {{ color: var(--syntax-func); }}
        .codehilite .s, .codehilite .s1, .codehilite .s2 {{ color: var(--syntax-string); }}
        .codehilite .c, .codehilite .c1 {{ color: var(--syntax-comment); font-style: italic; }}
        .codehilite .nb {{ color: var(--syntax-builtin); }}

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

        img {{
            max-width: 100%;
            height: auto;
        }}
    </style>
</head>
<body>
    <div class="markdown-body">
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
