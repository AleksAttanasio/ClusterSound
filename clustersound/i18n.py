"""Interface language for the messages the backend sends to the UI.

English is the source language and the English text is the key: tr("file not found") needs no entry
in English. Translations live in one catalog shared with the UI, ui/locales/<lang>.js (strict JSON
after "export default"), so the same sentence is translated once.
"""
import json
import re

from .paths import resource_path

LANGUAGES = ("en", "it")
DEFAULT = "en"

_lang = DEFAULT
_catalogs: dict[str, dict[str, str]] = {"en": {}}


def load_catalog(lang: str) -> dict[str, str]:
    """The catalog of a language, read from the UI's locales folder."""
    text = resource_path(f"ui/locales/{lang}.js").read_text(encoding="utf-8")
    body = re.sub(r"^\s*export\s+default\s*", "", text).rstrip().rstrip(";")
    return json.loads(body)


def normalize(lang) -> str:
    return lang if lang in LANGUAGES else DEFAULT


def set_language(lang) -> str:
    global _lang
    _lang = normalize(lang)
    if _lang not in _catalogs:
        try:
            _catalogs[_lang] = load_catalog(_lang)
        except (OSError, ValueError):
            _catalogs[_lang] = {}
    return _lang


def language() -> str:
    return _lang


def tr(text: str, **kw) -> str:
    """Translate English text into the current language; {name} placeholders are filled from kw."""
    s = _catalogs.get(_lang, {}).get(text, text)
    return s.format(**kw) if kw else s
