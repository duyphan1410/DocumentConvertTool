"""
Configuration constants for DocumentConvertTool Flet UI.
"""
import os

appdata_dir = os.getenv('APPDATA')
if not appdata_dir:
    appdata_dir = os.path.join(os.path.expanduser("~"), ".config")

DRAFT_PATH = os.path.join(appdata_dir, "DocConvert", "draft_autosave.md")
DRAFT_META_PATH = os.path.join(appdata_dir, "DocConvert", "draft_autosave_meta.json")
EDITOR_DISPLAY_LIMIT = 500_000

MODES = {
    "MD -> Excel":  {"in_ext": ".md",   "out_ext": ".xlsx", "in_label": "File .md",   "out_label": "Save .xlsx"},
    "MD -> Word":   {"in_ext": ".md",   "out_ext": ".docx", "in_label": "File .md",   "out_label": "Save .docx"},
    "MD -> CSV":    {"in_ext": ".md",   "out_ext": ".csv",  "in_label": "File .md",   "out_label": "Save .csv"},
    "MD -> PDF":    {"in_ext": ".md",   "out_ext": ".pdf",  "in_label": "File .md",   "out_label": "Save .pdf"},
    "MD -> HTML":   {"in_ext": ".md",   "out_ext": ".html", "in_label": "File .md",   "out_label": "Save .html"},
    "Excel -> MD":  {"in_ext": ".xlsx", "out_ext": ".md",   "in_label": "File .xlsx", "out_label": "Save .md"},
    "Word -> MD":   {"in_ext": ".docx", "out_ext": ".md",   "in_label": "File .docx", "out_label": "Save .md"},
    "CSV -> MD":    {"in_ext": ".csv",  "out_ext": ".md",   "in_label": "File .csv",  "out_label": "Save .md"},
    "PDF -> MD":    {"in_ext": ".pdf",  "out_ext": ".md",   "in_label": "File .pdf",  "out_label": "Save .md"},
    "HTML -> MD":   {"in_ext": ".html", "out_ext": ".md",   "in_label": "File .html", "out_label": "Save .md"},
}

# i18n display labels for mode dropdown — maps internal key → locale key
MODE_DISPLAY_KEYS = {
    "MD -> Excel":  "mode.md_to_excel",
    "MD -> Word":   "mode.md_to_word",
    "MD -> CSV":    "mode.md_to_csv",
    "MD -> PDF":    "mode.md_to_pdf",
    "MD -> HTML":   "mode.md_to_html",
    "Excel -> MD":  "mode.excel_to_md",
    "Word -> MD":   "mode.word_to_md",
    "CSV -> MD":    "mode.csv_to_md",
    "PDF -> MD":    "mode.pdf_to_md",
    "HTML -> MD":   "mode.html_to_md",
}

IN_FILETYPES = {
    ".md":   ["md"],
    ".xlsx": ["xlsx", "xls"],
    ".docx": ["docx"],
    ".csv":  ["csv"],
    ".pdf":  ["pdf"],
    ".html": ["html", "htm"],
}

OUT_FILETYPES = {
    ".xlsx": ["xlsx"],
    ".docx": ["docx"],
    ".md":   ["md"],
    ".csv":  ["csv"],
    ".pdf":  ["pdf"],
    ".html": ["html", "htm"],
}
