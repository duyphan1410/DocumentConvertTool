import unittest
import os
import tempfile
import sys

sys.path.insert(0, os.path.abspath("."))

from src.core.registry import ModuleRegistry
from src.core.validator import validate_file_pipeline
from src.core.errors import DocumentError
from src.modules.json_module import JSONModule
from src.modules.yaml_module import YAMLModule


class TestJSONYAMLModules(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- JSON Module Tests ---
    def test_json_load_tabular(self):
        json_path = os.path.join(self.temp_dir.name, "sample.json")
        json_content = '[{"name": "Alice", "age": 25}, {"name": "Bob", "age": 30}]'
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(json_content)

        module = JSONModule()
        md_res = module.load_to_markdown(json_path)
        self.assertIn("| name | age |", md_res)
        self.assertIn("| Alice | 25 |", md_res)
        self.assertIn("| Bob | 30 |", md_res)

    def test_json_load_nested(self):
        json_path = os.path.join(self.temp_dir.name, "nested.json")
        json_content = '{"title": "DocConvert", "settings": {"theme": "dark", "fontSize": 14}}'
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(json_content)

        module = JSONModule()
        md_res = module.load_to_markdown(json_path)
        self.assertIn("- **title**: DocConvert", md_res)
        self.assertIn("# settings", md_res)
        self.assertIn("- **theme**: dark", md_res)

    def test_json_save_from_markdown_table(self):
        md_content = "| name | score |\n| --- | --- |\n| Charlie | 95 |\n| Dana | 88 |"
        out_json = os.path.join(self.temp_dir.name, "out.json")

        module = JSONModule()
        module.save_from_markdown(md_content, out_json)

        self.assertTrue(os.path.exists(out_json))
        with open(out_json, "r", encoding="utf-8") as f:
            import json
            data = json.load(f)

        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["name"], "Charlie")
        self.assertEqual(data[0]["score"], 95)
        self.assertEqual(data[1]["name"], "Dana")
        self.assertEqual(data[1]["score"], 88)

    def test_json_save_from_codeblock(self):
        md_content = "Here is the config:\n```json\n{\n  \"app\": \"DocConvert\",\n  \"version\": \"1.6.3\"\n}\n```"
        out_json = os.path.join(self.temp_dir.name, "config.json")

        module = JSONModule()
        module.save_from_markdown(md_content, out_json)

        with open(out_json, "r", encoding="utf-8") as f:
            import json
            data = json.load(f)

        self.assertEqual(data.get("app"), "DocConvert")
        self.assertEqual(data.get("version"), "1.6.3")

    def test_json_multiline_string_roundtrip(self):
        json_path = os.path.join(self.temp_dir.name, "multiline.json")
        desc = "Đây là block string nhiều dòng.\nDòng thứ hai giữ nguyên xuống dòng.\nTest xem load_to_markdown có giữ line break không."
        original_data = {
            "title": "Test Multiline",
            "description": desc
        }
        with open(json_path, "w", encoding="utf-8") as f:
            import json
            json.dump(original_data, f)

        module = JSONModule()
        md_res = module.load_to_markdown(json_path)
        self.assertIn("- **title**: Test Multiline", md_res)
        # Markdown contains natural line breaks (xuống dòng trực quan)
        self.assertIn("- **description**: Đây là block string nhiều dòng.\nDòng thứ hai giữ nguyên xuống dòng.\nTest xem load_to_markdown có giữ line break không.", md_res)

        out_json = os.path.join(self.temp_dir.name, "out_multiline.json")
        module.save_from_markdown(md_res, out_json)

        with open(out_json, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        self.assertEqual(saved_data["title"], "Test Multiline")
        self.assertEqual(saved_data["description"], desc)

    def test_json_tab_and_indent_preservation(self):
        json_path = os.path.join(self.temp_dir.name, "tabs.json")
        code_str = "function test() {\n\tconst x = 1;\n\t\treturn x;\n}"
        original_data = {
            "tab_separated": "col1\tcol2\tcol3",
            "indented_code": code_str
        }
        with open(json_path, "w", encoding="utf-8") as f:
            import json
            json.dump(original_data, f)

        module = JSONModule()
        md_res = module.load_to_markdown(json_path)
        self.assertIn("\tconst x = 1;", md_res)

        out_json = os.path.join(self.temp_dir.name, "out_tabs.json")
        module.save_from_markdown(md_res, out_json)

        with open(out_json, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        self.assertEqual(saved_data["tab_separated"], "col1\tcol2\tcol3")
        self.assertEqual(saved_data["indented_code"], code_str)

    # --- YAML Module Tests ---
    def test_yaml_load_and_save(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed in test environment")

        yaml_path = os.path.join(self.temp_dir.name, "sample.yaml")
        yaml_content = "server:\n  port: 8080\n  host: localhost\n"
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        module = YAMLModule()
        md_res = module.load_to_markdown(yaml_path)
        self.assertIn("# server", md_res)
        self.assertIn("- **port**: 8080", md_res)

        out_yaml = os.path.join(self.temp_dir.name, "out.yaml")
        module.save_from_markdown(md_res, out_yaml)
        self.assertTrue(os.path.exists(out_yaml))

        with open(out_yaml, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.assertEqual(data["server"]["port"], 8080)
        self.assertEqual(data["server"]["host"], "localhost")

    def test_yaml_multiline_string_roundtrip(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed in test environment")

        yaml_path = os.path.join(self.temp_dir.name, "multiline.yaml")
        desc = "Đây là block string nhiều dòng.\nDòng thứ hai giữ nguyên xuống dòng.\nTest xem load_to_markdown có giữ line break không.\n"
        yaml_content = f"description: |\n  Đây là block string nhiều dòng.\n  Dòng thứ hai giữ nguyên xuống dòng.\n  Test xem load_to_markdown có giữ line break không.\n"
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        module = YAMLModule()
        md_res = module.load_to_markdown(yaml_path)
        # Markdown contains natural line breaks (xuống dòng trực quan)
        self.assertIn("- **description**: Đây là block string nhiều dòng.\nDòng thứ hai giữ nguyên xuống dòng.\nTest xem load_to_markdown có giữ line break không.", md_res)

        out_yaml = os.path.join(self.temp_dir.name, "out_multiline.yaml")
        module.save_from_markdown(md_res, out_yaml)

        with open(out_yaml, "r", encoding="utf-8") as f:
            saved_data = yaml.safe_load(f)

        self.assertEqual(saved_data["description"].strip(), desc.strip())
        self.assertIn("Dòng thứ hai giữ nguyên xuống dòng.", saved_data["description"])
        self.assertIn("Test xem load_to_markdown có giữ line break không.", saved_data["description"])

    def test_yaml_tab_and_indent_preservation(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed in test environment")

        yaml_path = os.path.join(self.temp_dir.name, "tabs.yaml")
        original_data = {
            "tab_separated": "col1\tcol2\tcol3",
            "indented_block": "line 1\n  two spaces\n    four spaces"
        }
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(original_data, f, sort_keys=False)

        module = YAMLModule()
        md_res = module.load_to_markdown(yaml_path)

        out_yaml = os.path.join(self.temp_dir.name, "out_tabs.yaml")
        module.save_from_markdown(md_res, out_yaml)

        with open(out_yaml, "r", encoding="utf-8") as f:
            saved_data = yaml.safe_load(f)

        self.assertEqual(saved_data["tab_separated"], "col1\tcol2\tcol3")
        self.assertEqual(saved_data["indented_block"], original_data["indented_block"])

    # --- Registry & Dependencies Tests ---
    def test_module_registry(self):
        json_mod = ModuleRegistry.get_module_by_extension(".json")
        self.assertIsNotNone(json_mod)
        self.assertEqual(json_mod.name, "JSON")

        yaml_mod = ModuleRegistry.get_module_by_extension(".yaml")
        self.assertIsNotNone(yaml_mod)
        self.assertEqual(yaml_mod.name, "YAML")

        yml_mod = ModuleRegistry.get_module_by_extension(".yml")
        self.assertIsNotNone(yml_mod)
        self.assertEqual(yml_mod.name, "YAML")

    # --- Validator Tests ---
    def test_invalid_json_validation(self):
        bad_json = os.path.join(self.temp_dir.name, "invalid.json")
        with open(bad_json, "w", encoding="utf-8") as f:
            f.write("{invalid json format here")

        with self.assertRaises(DocumentError):
            validate_file_pipeline(bad_json)


if __name__ == "__main__":
    unittest.main()
