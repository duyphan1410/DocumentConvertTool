"""
Translator Engine for DocConvert i18n system.
Singleton-based, JSON locale files, flat dot-separated keys.
"""

import os
import json
from typing import Optional


_LOCALES_DIR = os.path.join(os.path.dirname(__file__), "locales")


class Translator:
    """Singleton translator with English fallback."""

    _instance: Optional["Translator"] = None

    def __new__(cls) -> "Translator":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._locale: str = "en"
        self._strings: dict[str, str] = {}
        self._fallback: dict[str, str] = {}
        # Load English as both active and fallback
        self._fallback = self._load_locale_file("en")
        self._strings = dict(self._fallback)

    def t(self, key: str, **kwargs) -> str:
        """Translate key with optional format kwargs. Falls back to English, then key itself."""
        text = self._strings.get(key) or self._fallback.get(key) or key
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                pass  # Return unformatted text rather than crash
        return text

    @property
    def locale(self) -> str:
        return self._locale

    def set_locale(self, locale: str) -> None:
        """Load a new locale. English fallback is always kept."""
        if locale == self._locale and self._strings:
            return
        self._locale = locale
        if locale == "en":
            self._strings = dict(self._fallback)
        else:
            loaded = self._load_locale_file(locale)
            self._strings = loaded if loaded else dict(self._fallback)

    def get_available_locales(self) -> list[dict]:
        """Scan locales/ directory and return list of available locales."""
        locales = []
        if not os.path.isdir(_LOCALES_DIR):
            return locales
        for fname in sorted(os.listdir(_LOCALES_DIR)):
            if fname.endswith(".json"):
                code = fname[:-5]  # strip .json
                meta = self._load_locale_meta(code)
                locales.append({
                    "code": code,
                    "name": meta.get("name", code),
                    "native_name": meta.get("native_name", code),
                })
        return locales

    @staticmethod
    def _load_locale_meta(locale: str) -> dict:
        """Load raw JSON and return _meta dict."""
        path = os.path.join(_LOCALES_DIR, f"{locale}.json")
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("_meta", {})
        except Exception:
            return {}

    @staticmethod
    def _load_locale_file(locale: str) -> dict[str, str]:
        """Load a single JSON locale file. Returns empty dict on failure."""
        path = os.path.join(_LOCALES_DIR, f"{locale}.json")
        if not os.path.isfile(path):
            print(f"[i18n] Locale file not found: {path}")
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Flatten: remove _meta from lookup, keep only string keys
            return {k: v for k, v in data.items() if isinstance(v, str)}
        except Exception as exc:
            print(f"[i18n] Failed to load locale '{locale}': {exc}")
            return {}
