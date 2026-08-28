"""
Configuration constants for DocumentConvertTool Flet UI.
"""
import os

appdata_dir = os.getenv('APPDATA')
if not appdata_dir:
    appdata_dir = os.path.join(os.path.expanduser("~"), ".config")

DRAFT_PATH = os.path.join(appdata_dir, "DocConvert", "draft_autosave.md")
DRAFT_META_PATH = os.path.join(appdata_dir, "DocConvert", "draft_autosave_meta.json")
DRAFTS_DIR = os.path.join(appdata_dir, "DocConvert", "drafts")
TAB_SESSION_PATH = os.path.join(appdata_dir, "DocConvert", "tab_session.json")
EDITOR_DISPLAY_LIMIT = 500_000


def get_default_output_dir() -> str:
    """Returns standard user Documents output directory for untitled drafts."""
    user_docs = os.path.join(os.path.expanduser("~"), "Documents")
    out_dir = os.path.join(user_docs, "DocConvert_Output")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


MODES = {
    "MD -> Markdown": {"in_ext": ".md",   "out_ext": ".md",   "in_label": "File .md",   "out_label": "Save .md"},
    "MD -> Word":   {"in_ext": ".md",   "out_ext": ".docx", "in_label": "File .md",   "out_label": "Save .docx"},
    "MD -> PDF":    {"in_ext": ".md",   "out_ext": ".pdf",  "in_label": "File .md",   "out_label": "Save .pdf"},
    "MD -> Excel":  {"in_ext": ".md",   "out_ext": ".xlsx", "in_label": "File .md",   "out_label": "Save .xlsx"},
    "MD -> CSV":    {"in_ext": ".md",   "out_ext": ".csv",  "in_label": "File .md",   "out_label": "Save .csv"},
    "MD -> HTML":   {"in_ext": ".md",   "out_ext": ".html", "in_label": "File .md",   "out_label": "Save .html"},
    "MD -> JSON":   {"in_ext": ".md",   "out_ext": ".json", "in_label": "File .md",   "out_label": "Save .json"},
    "MD -> YAML":   {"in_ext": ".md",   "out_ext": ".yaml", "in_label": "File .md",   "out_label": "Save .yaml"},
    "MD -> PowerPoint": {"in_ext": ".md",   "out_ext": ".pptx", "in_label": "File .md",   "out_label": "Save .pptx"},
    "Excel -> MD":  {"in_ext": ".xlsx", "out_ext": ".md",   "in_label": "File .xlsx", "out_label": "Save .md"},
    "Word -> MD":   {"in_ext": ".docx", "out_ext": ".md",   "in_label": "File .docx", "out_label": "Save .md"},
    "CSV -> MD":    {"in_ext": ".csv",  "out_ext": ".md",   "in_label": "File .csv",  "out_label": "Save .md"},
    "PDF -> MD":    {"in_ext": ".pdf",  "out_ext": ".md",   "in_label": "File .pdf",  "out_label": "Save .md"},
    "HTML -> MD":   {"in_ext": ".html", "out_ext": ".md",   "in_label": "File .html", "out_label": "Save .md"},
    "JSON -> MD":   {"in_ext": ".json", "out_ext": ".md",   "in_label": "File .json", "out_label": "Save .md"},
    "YAML -> MD":   {"in_ext": ".yaml", "out_ext": ".md",   "in_label": "File .yaml", "out_label": "Save .md"},
    "PowerPoint -> MD": {"in_ext": ".pptx", "out_ext": ".md",   "in_label": "File .pptx", "out_label": "Save .md"},
}

# i18n display labels for mode dropdown — maps internal key → locale key
MODE_DISPLAY_KEYS = {
    "MD -> Markdown": "mode.md_to_md",
    "MD -> Word":   "mode.md_to_word",
    "MD -> PDF":    "mode.md_to_pdf",
    "MD -> Excel":  "mode.md_to_excel",
    "MD -> CSV":    "mode.md_to_csv",
    "MD -> HTML":   "mode.md_to_html",
    "MD -> JSON":   "mode.md_to_json",
    "MD -> YAML":   "mode.md_to_yaml",
    "MD -> PowerPoint": "mode.md_to_pptx",
    "Excel -> MD":  "mode.excel_to_md",
    "Word -> MD":   "mode.word_to_md",
    "CSV -> MD":    "mode.csv_to_md",
    "PDF -> MD":    "mode.pdf_to_md",
    "HTML -> MD":   "mode.html_to_md",
    "JSON -> MD":   "mode.json_to_md",
    "YAML -> MD":   "mode.yaml_to_md",
    "PowerPoint -> MD": "mode.pptx_to_md",
}

IN_FILETYPES = {
    ".md":   ["md"],
    ".xlsx": ["xlsx", "xls"],
    ".docx": ["docx"],
    ".csv":  ["csv"],
    ".pdf":  ["pdf"],
    ".html": ["html", "htm"],
    ".pptx": ["pptx"],
    ".json": ["json"],
    ".yaml": ["yaml", "yml"],
    ".yml":  ["yaml", "yml"],
}

OUT_FILETYPES = {
    ".xlsx": ["xlsx"],
    ".docx": ["docx"],
    ".md":   ["md"],
    ".csv":  ["csv"],
    ".pdf":  ["pdf"],
    ".html": ["html", "htm"],
    ".pptx": ["pptx"],
    ".json": ["json"],
    ".yaml": ["yaml", "yml"],
    ".yml":  ["yaml", "yml"],
}
