import os
import json

SETTINGS_KEYS = [
    "current_palette",
    "current_theme_mode",
    "default_mode",
    "autosave_enabled",
    "autosave_interval_sec",
    "editor_font_size",
    "show_line_numbers",
    "word_wrap",
]

_appdata = os.getenv("APPDATA", os.path.expanduser("~"))
SETTINGS_PATH = os.path.join(_appdata, "DocConvert", "settings.json")


def save_settings(state) -> None:
    """Persist AppState settings fields to settings.json."""
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        data = {k: getattr(state, k) for k in SETTINGS_KEYS if hasattr(state, k)}
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        print(f"[SettingsStore] save failed: {exc}")


def load_settings_into(state) -> None:
    """Read settings.json and populate AppState. Silent on missing file."""
    if not os.path.isfile(SETTINGS_PATH):
        return
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in SETTINGS_KEYS:
            if key in data and hasattr(state, key):
                setattr(state, key, data[key])
    except Exception as exc:
        print(f"[SettingsStore] load failed: {exc}")
