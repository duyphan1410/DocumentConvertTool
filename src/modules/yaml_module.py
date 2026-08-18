import os
import re
from typing import Any, Dict, List

from src.core.base_module import BaseDocumentModule
from src.core.registry import ModuleRegistry
from src.core.converters import parse_md_tables, strip_markdown_styles


class YAMLModule(BaseDocumentModule):
    @property
    def name(self) -> str:
        return "YAML"

    @property
    def file_extensions(self) -> list[str]:
        return [".yaml", ".yml"]

    @property
    def required_dependencies(self) -> list[str]:
        return ["pyyaml"]

    def load_to_markdown(self, file_path: str) -> str:
        """Loads a YAML file and formats it into clean Markdown text."""
        # CRITICAL: Lazy import rule to prevent app startup crashes
        import yaml

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read().strip()

        if not content:
            return "*(Empty YAML)*"

        try:
            data = yaml.safe_load(content)
        except Exception as e:
            raise ValueError(f"Invalid YAML format in file '{os.path.basename(file_path)}': {str(e)}")

        return self._data_to_markdown(data)

    def _data_to_markdown(self, data: Any, level: int = 1) -> str:
        """Recursively formats Python data structures into Markdown."""
        if data is None:
            return ""

        if isinstance(data, list):
            if not data:
                return "*(Empty List)*"
            if all(isinstance(item, dict) for item in data):
                return self._list_of_dicts_to_md_table(data)
            lines = []
            for item in data:
                if isinstance(item, list):
                    if not item:
                        lines.append("- *(Empty List)*")
                    else:
                        lines.append(f"- - {item[0]}")
                        for sub in item[1:]:
                            lines.append(f"  - {sub}")
                elif isinstance(item, dict):
                    if not item:
                        lines.append("- *(Empty Object)*")
                    else:
                        sub_md = self._data_to_markdown(item, level=level + 1)
                        sub_lines = sub_md.splitlines()
                        for sl in sub_lines:
                            lines.append(f"  {sl}")
                else:
                    lines.append(f"- {item}")
            return "\n".join(lines)

        elif isinstance(data, dict):
            if not data:
                return "*(Empty Object)*"

            if all(not isinstance(v, (dict, list)) for v in data.values()):
                lines = [f"- **{k}**: {v}" if v is not None else f"- **{k}**: null" for k, v in data.items()]
                return "\n".join(lines)

            parts = []
            header_prefix = "#" * min(level, 6)

            # 1. Primitives first
            for k, v in data.items():
                if not isinstance(v, (dict, list)):
                    val_str = "null" if v is None else str(v)
                    parts.append(f"- **{k}**: {val_str}")

            # 2. Containers next
            for k, v in data.items():
                if isinstance(v, list):
                    if not v:
                        parts.append(f"{header_prefix} {k}\n*(Empty List)*\n")
                    elif all(isinstance(item, dict) for item in v):
                        parts.append(f"{header_prefix} {k}\n")
                        parts.append(self._list_of_dicts_to_md_table(v))
                        parts.append("")
                    else:
                        parts.append(f"{header_prefix} {k}\n")
                        for item in v:
                            if isinstance(item, list):
                                if not item:
                                    parts.append("- *(Empty List)*")
                                else:
                                    parts.append(f"- - {item[0]}")
                                    for sub in item[1:]:
                                        parts.append(f"  - {sub}")
                            elif isinstance(item, dict):
                                if not item:
                                    parts.append("- *(Empty Object)*")
                                else:
                                    parts.append(self._data_to_markdown(item, level=level + 1))
                            else:
                                parts.append(f"- {item}")
                        parts.append("")
                elif isinstance(v, dict):
                    if not v:
                        parts.append(f"{header_prefix} {k}\n*(Empty Object)*\n")
                    else:
                        parts.append(f"{header_prefix} {k}\n")
                        parts.append(self._data_to_markdown(v, level=level + 1))
                        parts.append("")

            return "\n".join(parts).strip()

        else:
            return str(data)

    def _list_of_dicts_to_md_table(self, data: List[Dict[str, Any]]) -> str:
        """Converts a list of dicts into a Markdown pipe table."""
        if not data:
            return "*(Empty Table)*"

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
                val_str = str(val).replace("\n", " ") if val is not None else ""
                val_str = val_str.replace("|", "\\|")
                row_cells.append(val_str)
            rows.append("| " + " | ".join(row_cells) + " |")

        return "\n".join(rows)

    def save_from_markdown(self, markdown_content: str, out_path: str) -> str:
        """Converts Markdown text back into a YAML file."""
        # CRITICAL: Lazy import rule to prevent app startup crashes
        import yaml

        parsed_data = self._markdown_to_data(markdown_content, yaml_module=yaml)

        with open(out_path, "w", encoding="utf-8") as f:
            yaml.dump(parsed_data, f, allow_unicode=True, sort_keys=False)

        return f"Exported successfully to YAML -> {os.path.basename(out_path)}"

    def _markdown_to_data(self, content: str, yaml_module=None) -> Any:
        """Parses Markdown content into a Python data structure."""
        stripped_content = content.strip()
        if not stripped_content:
            return {}

        # 1. Check for fenced YAML code block: ```yaml ... ```
        code_block_match = re.search(r"```(?:yaml|yml)?\s*\n(.*?)\n```", stripped_content, re.DOTALL | re.IGNORECASE)
        if code_block_match and yaml_module:
            try:
                res = yaml_module.safe_load(code_block_match.group(1).strip())
                if res is not None:
                    return res
            except Exception:
                pass

        # 2. Check for top-level empty markers
        if stripped_content in ("*(Empty List)*", "*(Empty Table)*"):
            return []
        if stripped_content in ("*(Empty Object)*", "*(Empty JSON)*", "*(Empty YAML)*"):
            return {}

        # 3. Sequential Markdown parser with Header Level Stack
        # Stack elements: [level, container, section_key, parent_container]
        root_container = {}
        stack = [[0, root_container, None, None]]
        last_target = None
        lines = content.splitlines()
        i = 0

        while i < len(lines):
            line = lines[i]
            line_str = line.strip()

            if not line_str:
                i += 1
                continue

            # A. Markdown Table check
            if line_str.startswith("|") and "|" in line_str[1:]:
                last_target = None
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1

                from src.core.converters import parse_table_rows
                rows = parse_table_rows(table_lines)
                if len(rows) >= 2:
                    headers = [c.replace(r"\|", "|").strip() for c in rows[0]]
                    table_dicts = []
                    for row in rows[1:]:
                        d = {}
                        for idx, cell in enumerate(row):
                            if idx < len(headers):
                                val = cell.replace(r"\|", "|").strip()
                                d[headers[idx]] = self._coerce_value(val)
                        table_dicts.append(d)

                    curr_level, curr_container, curr_key, curr_parent = stack[-1]
                    if curr_parent is not None and curr_key is not None:
                        if isinstance(curr_container, dict) and not curr_container:
                            curr_parent[curr_key] = table_dicts
                            stack[-1][1] = table_dicts
                        elif isinstance(curr_container, list):
                            curr_container.extend(table_dicts)
                        elif isinstance(curr_container, dict):
                            curr_container["_table"] = table_dicts
                    else:
                        if not root_container:
                            root_container = table_dicts
                            stack[0][1] = root_container
                        elif isinstance(root_container, list):
                            root_container.extend(table_dicts)
                        elif isinstance(root_container, dict):
                            root_container["_table"] = table_dicts
                continue

            # B. Header check: # Section Name
            header_match = re.match(r"^(#{1,6})\s+(.*)", line_str)
            if header_match:
                last_target = None
                h_level = len(header_match.group(1))
                section_name = header_match.group(2).strip()
                if section_name.startswith("**") and section_name.endswith("**") and len(section_name) >= 4:
                    section_name = section_name[2:-2].strip()

                while len(stack) > 1 and stack[-1][0] >= h_level:
                    stack.pop()

                parent_level, parent_container, _, _ = stack[-1]
                if isinstance(parent_container, dict):
                    new_container = {}
                    parent_container[section_name] = new_container
                    stack.append([h_level, new_container, section_name, parent_container])
                i += 1
                continue

            # C. Empty Section Markers inside content
            if line_str in ("*(Empty List)*", "*(Empty Table)*"):
                last_target = None
                curr_level, curr_container, curr_key, curr_parent = stack[-1]
                if curr_parent is not None and curr_key is not None:
                    curr_parent[curr_key] = []
                    stack[-1][1] = []
                elif not root_container:
                    root_container = []
                    stack[0][1] = []
                i += 1
                continue

            if line_str in ("*(Empty Object)*", "*(Empty JSON)*", "*(Empty YAML)*"):
                last_target = None
                curr_level, curr_container, curr_key, curr_parent = stack[-1]
                if curr_parent is not None and curr_key is not None:
                    curr_parent[curr_key] = {}
                    stack[-1][1] = {}
                i += 1
                continue

            # D. Bullet Key-Value check: - **Key**: Value or - Key: Value
            kv_match = re.match(r"^[-*+]\s+(?:\*\*(.*?)\*\*|`(.*?)`|(.*?)):\s*(.*)", line_str)
            if kv_match:
                key = kv_match.group(1) or kv_match.group(2) or kv_match.group(3)
                key = key.strip() if key else ""
                val_raw = kv_match.group(4).strip().replace(r"\|", "|")
                coerced_val = self._coerce_value(val_raw)

                curr_level, curr_container, curr_key, curr_parent = stack[-1]
                if isinstance(curr_container, dict):
                    curr_container[key] = coerced_val
                    last_target = ('kv', curr_container, key)
                elif isinstance(curr_container, list):
                    new_dict = {key: coerced_val}
                    if len(curr_container) == 0:
                        if curr_parent is not None and curr_key is not None:
                            curr_parent[curr_key] = new_dict
                        else:
                            root_container = new_dict
                        stack[-1][1] = new_dict
                    else:
                        curr_container.append(new_dict)
                    last_target = ('kv', new_dict, key)
                i += 1
                continue

            # E. Simple Bullet List item check: - Value or indented bullets
            bullet_match = re.match(r"^(\s*)[-*+]\s+(.*)", line)
            if bullet_match:
                indent_len = len(bullet_match.group(1))
                val_raw = bullet_match.group(2).strip()

                curr_level, curr_container, curr_key, curr_parent = stack[-1]

                # Check if this line starts a sub-list: "- - val"
                if val_raw.startswith("- ") or val_raw.startswith("* "):
                    sub_val_raw = val_raw[2:].strip().replace(r"\|", "|")
                    sub_val = self._coerce_value(sub_val_raw)
                    new_sub_list = [sub_val]
                    if isinstance(curr_container, dict):
                        if not curr_container:
                            new_list = [new_sub_list]
                            if curr_parent is not None and curr_key is not None:
                                curr_parent[curr_key] = new_list
                            else:
                                root_container = new_list
                            stack[-1][1] = new_list
                        else:
                            if "_items" not in curr_container:
                                curr_container["_items"] = []
                            curr_container["_items"].append(new_sub_list)
                    elif isinstance(curr_container, list):
                        curr_container.append(new_sub_list)
                    last_target = ('list_item', new_sub_list)
                    i += 1
                    continue

                # Check if indented sub-item: "  - val"
                if indent_len >= 2 and isinstance(curr_container, list) and len(curr_container) > 0 and isinstance(curr_container[-1], list):
                    sub_val = self._coerce_value(val_raw.replace(r"\|", "|"))
                    curr_container[-1].append(sub_val)
                    last_target = ('list_item', curr_container[-1])
                    i += 1
                    continue

                # Normal bullet item
                if val_raw in ("*(Empty List)*", "*(Empty Table)*"):
                    coerced_val = []
                elif val_raw in ("*(Empty Object)*", "*(Empty JSON)*", "*(Empty YAML)*"):
                    coerced_val = {}
                else:
                    coerced_val = self._coerce_value(val_raw.replace(r"\|", "|"))

                if isinstance(curr_container, dict):
                    if not curr_container:
                        new_list = [coerced_val]
                        if curr_parent is not None and curr_key is not None:
                            curr_parent[curr_key] = new_list
                        else:
                            root_container = new_list
                        stack[-1][1] = new_list
                        last_target = ('list_item', new_list)
                    else:
                        if "_items" not in curr_container:
                            curr_container["_items"] = []
                        curr_container["_items"].append(coerced_val)
                        last_target = ('list_item', curr_container["_items"])
                elif isinstance(curr_container, list):
                    curr_container.append(coerced_val)
                    last_target = ('list_item', curr_container)
                i += 1
                continue

            # Unmatched line: treat as multi-line continuation for previous key or list item
            if last_target is not None:
                cont_line = line.rstrip("\r\n")
                target_type = last_target[0]
                if target_type == 'kv':
                    target_dict, target_key = last_target[1], last_target[2]
                    if target_key in target_dict:
                        target_dict[target_key] = str(target_dict[target_key]) + "\n" + cont_line
                elif target_type == 'list_item':
                    target_list = last_target[1]
                    if len(target_list) > 0:
                        target_list[-1] = str(target_list[-1]) + "\n" + cont_line

            i += 1

        if isinstance(root_container, dict):
            if list(root_container.keys()) == ["_items"]:
                return root_container["_items"]
            if len(root_container) == 1 and list(root_container.keys())[0].startswith("Sheet") and isinstance(list(root_container.values())[0], list):
                return list(root_container.values())[0]
            if root_container:
                return root_container
        elif isinstance(root_container, list):
            return root_container

        # Direct safe load fallback if yaml_module provided
        if yaml_module:
            try:
                res = yaml_module.safe_load(stripped_content)
                if res is not None:
                    return res
            except Exception:
                pass

        non_empty = [l.strip() for l in lines if l.strip()]
        return {"content": non_empty} if len(non_empty) > 1 else (non_empty[0] if non_empty else {})

    def _coerce_value(self, val: str) -> Any:
        """Coerces string values to primitive types."""
        if val == "":
            return ""
        val_lower = val.lower()
        if val_lower == "true":
            return True
        if val_lower == "false":
            return False
        if val_lower in ("null", "none", "~"):
            return None
        if val in ("*(Empty List)*", "*(Empty Table)*", "[]"):
            return []
        if val in ("*(Empty Object)*", "*(Empty JSON)*", "*(Empty YAML)*", "{}"):
            return {}

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

        if "\\n" in val or "\\r" in val or "\\t" in val:
            val = val.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n").replace("\\t", "\t")

        return val


ModuleRegistry.register(YAMLModule())
