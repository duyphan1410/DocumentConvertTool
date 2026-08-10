"""
DocConvert i18n Public API.

Usage:
    from src.i18n import t, set_locale, get_locale, get_available_locales

    label = t("welcome.title")
    label = t("status.file_loaded", filename="doc.md", duration="1.23")

    set_locale("vi")
    locales = get_available_locales()
"""

from src.i18n.translator import Translator

_translator = Translator()


def t(key: str, **kwargs) -> str:
    """Translate a key with optional format kwargs."""
    return _translator.t(key, **kwargs)


def set_locale(locale: str) -> None:
    """Switch active locale (e.g. 'en', 'vi')."""
    _translator.set_locale(locale)


def get_locale() -> str:
    """Return current active locale code."""
    return _translator.locale


def get_available_locales() -> list[dict]:
    """Return list of available locales: [{code, name, native_name}, ...]."""
    return _translator.get_available_locales()
