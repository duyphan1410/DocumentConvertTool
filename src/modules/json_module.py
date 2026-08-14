import os
import json
import re
from typing import Any, Dict, List, Union

from src.core.base_module import BaseDocumentModule
from src.core.registry import ModuleRegistry
from src.core.converters import parse_md_tables, strip_markdown_styles


class JSONModule(BaseDocumentModule):
    @property
    def name(self) -> str:
        return "JSON"

    @property
    def file_extensions(self) -> list[str]:
        return [".json"]

    @property
    def required_dependencies(self) -> list[str]:
        return []

    def load_to_markdown(self, file_path: str) -> str:
        """Loads a JSON file and formats it into clean, structured Markdown."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read().strip()

        if not content:
            return "*(Empty JSON)*"

        try:
            data = json.loads(content)
        except Exception as e:
            raise ValueError(f"Invalid JSON format in file '{os.path.basename(file_path)}': {str(e)}")

        return self._data_to_markdown(data)

    def _data_to_markdown(self, data: Any, level: int = 1) -> str:
        """Recursively formats Python data structures (dicts, lists, primitives) into Markdown."""
        if data is None:
            return ""

        if isinstance(data, list):
            if not data:
                return "*(Empty List)*"
            # Check if list of dicts (tabular data)
            if all(isinstance(item, dict) for item in data):
                return self._list_of_dicts_to_md_table(data)
            # List of primitives or mixed items
            lines = []
            for item in data:
                if isinstance(item, (dict, list)):
                    lines.append(self._data_to_markdown(item, level=level))
                else:
                    lines.append(f"- {item}")
            return "\n".join(lines)

        elif isinstance(data, dict):
            if not data:
                return "*(Empty Object)*"
            
            # If all dictionary values are primitive, render as simple bullet key-values
            if all(not isinstance(v, (dict, list)) for v in data.values()):
                lines = [f"- **{k}**: {v}" if v is not None else f"- **{k}**:" for k, v in data.items()]
                return "\n".join(lines)

            # Complex dictionary with nested sections
            parts = []
            header_prefix = "#" * min(level, 6)
            for k, v in data.items():
                if isinstance(v, list) and all(isinstance(item, dict) for item in v):
                    parts.append(f"{header_prefix} {k}\n")
                    parts.append(self._list_of_dicts_to_md_table(v))
                    parts.append("")
                elif isinstance(v, dict):
                    parts.append(f"{header_prefix} {k}\n")
                    parts.append(self._data_to_markdown(v, level=level + 1))
                    parts.append("")
                elif isinstance(v, list):
                    parts.append(f"{header_prefix} {k}\n")
                    for item in v:
                        if isinstance(item, (dict, list)):
                            parts.append(self._data_to_markdown(item, level=level + 1))
                        else:
                            parts.append(f"- {item}")
                    parts.append("")
                else:
                    val_str = str(v) if v is not None else ""
                    parts.append(f"- **{k}**: {val_str}")
            return "\n".join(parts).strip()

        else:
            return str(data)

    def _list_of_dicts_to_md_table(self, data: List[Dict[str, Any]]) -> str:
        """Converts a list of dicts into a Markdown pipe table."""
        if not data:
            return "*(Empty Table)*"

        # Collect all unique keys preserving order
        headers = []
        for d in data:
            for k in d.keys():
                if k not in headers:
                    headers.append(str(k))

        if not headers:
            return "*(Empty Table)*"

        header_str = "| " + " | ".join(headers) + " |"
        sep_str = "| " + " | ".join("---" for _ in headers) + " |"
        
        rows = [header_str, sep_str]
        for item in data:
            row_cells = []
            for h in headers:
                val = item.get(h, "")
                if isinstance(val, (dict, list)):
                    val_str = json.dumps(val, ensure_ascii=False).replace("\n", " ")
                else:
                    val_str = str(val).replace("\n", " ") if val is not None else ""
                # Escape vertical pipes in cell content
                val_str = val_str.replace("|", "\\|")
                row_cells.append(val_str)
            rows.append("| " + " | ".join(row_cells) + " |")

        return "\n".join(rows)

    def save_from_markdown(self, markdown_content: str, out_path: str) -> str:
        """Converts Markdown text back into a formatted JSON file."""
        parsed_data = self._markdown_to_data(markdown_content)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(parsed_data, f, indent=2, ensure_ascii=False)

        return f"Exported successfully to JSON -> {os.path.basename(out_path)}"

    def _markdown_to_data(self, content: str) -> Any:
        """Parses Markdown content into a Python data structure (dict, list, etc.)."""
        stripped_content = content.strip()
        if not stripped_content:
            return {}

        # 1. Check for fenced JSON code block: ```json ... ```
        code_block_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", stripped_content, re.DOTALL | re.IGNORECASE)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1).strip())
            except Exception:
                pass

        # 2. Try direct JSON parse if whole content is JSON
        if (stripped_content.startswith("{") and stripped_content.endswith("}")) or \
           (stripped_content.startswith("[") and stripped_content.endswith("]")):
            try:
                return json.loads(stripped_content)
            except Exception:
                pass

        # 3. Check for Markdown tables via core converters
        tables = parse_md_tables(content)
        if tables:
            parsed_tables = {}
            for name, rows in tables:
                if not rows or len(rows) < 2:
                    continue
                headers = [strip_markdown_styles(c) for c in rows[0]]
                table_dicts = []
                for row in rows[1:]:
                    d = {}
                    for idx, cell in enumerate(row):
                        if idx < len(headers):
                            val = strip_markdown_styles(cell)
                            # Attempt type coercion for numbers/booleans
                            d[headers[idx]] = self._coerce_value(val)
                    table_dicts.append(d)
                parsed_tables[name] = table_dicts

            if len(parsed_tables) == 1 and list(parsed_tables.keys())[0].startswith("Sheet"):
                # Single anonymous table -> return list of dicts directly
                return list(parsed_tables.values())[0]
            elif parsed_tables:
                return parsed_tables

        # 4. Parse key-value bullet points and headers
        result_dict = {}
        current_section = None
        lines = content.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str or re.match(r"^[\|\s\-:]+$", line_str):
                continue

            # Header check: # Section Name
            header_match = re.match(r"^(#{1,6})\s+(.*)", line_str)
            if header_match:
                current_section = strip_markdown_styles(header_match.group(2))
                if current_section not in result_dict:
                    result_dict[current_section] = {}
                continue

            # Bullet key-value check: - **Key**: Value or - Key: Value
            kv_match = re.match(r"^[-*+]\s+(?:\*\*(.*?)\*\*|(.*?)):\s*(.*)", line_str)
            if kv_match:
                key = kv_match.group(1) or kv_match.group(2)
                key = strip_markdown_styles(key.strip()) if key else ""
                val = strip_markdown_styles(kv_match.group(3).strip())
                coerced_val = self._coerce_value(val)

                if current_section:
                    if not isinstance(result_dict[current_section], dict):
                        result_dict[current_section] = {}
                    result_dict[current_section][key] = coerced_val
                else:
                    result_dict[key] = coerced_val
                continue

            # Simple bullet list item check: - Value
            bullet_match = re.match(r"^[-*+]\s+(.*)", line_str)
            if bullet_match:
                val = strip_markdown_styles(bullet_match.group(1).strip())
                coerced_val = self._coerce_value(val)
                if current_section:
                    if not isinstance(result_dict[current_section], list):
                        result_dict[current_section] = []
                    result_dict[current_section].append(coerced_val)
                else:
                    if "_items" not in result_dict:
                        result_dict["_items"] = []
                    result_dict["_items"].append(coerced_val)

        if result_dict:
            if list(result_dict.keys()) == ["_items"]:
                return result_dict["_items"]
            return result_dict

        # Fallback: line array or raw text
        non_empty = [line.strip() for line in lines if line.strip()]
        return {"content": non_empty} if len(non_empty) > 1 else (non_empty[0] if non_empty else {})

    def _coerce_value(self, val: str) -> Any:
        """Coerces string values to primitive types (int, float, bool, null, or JSON object)."""
        if not val:
            return ""
        val_lower = val.lower()
        if val_lower == "true":
            return True
        if val_lower == "false":
            return False
        if val_lower in ("null", "none", "~"):
            return None

        # Check integer / float
        if re.match(r"^-?\d+$", val):
            try:
                return int(val)
            except ValueError:
                pass
        if re.match(r"^-?\d+\.\d+$", val):
            try:
                return float(val)
            except ValueError:
                pass

        # Check JSON nested object string
        if (val.startswith("{") and val.endswith("}")) or (val.startswith("[") and val.endswith("]")):
            try:
                return json.loads(val)
            except Exception:
                pass

        return val


ModuleRegistry.register(JSONModule())
