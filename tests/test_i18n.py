"""Interface language: every English text the UI or the backend translates has an Italian entry."""
import ast
import re
from pathlib import Path

from clustersound import i18n

PKG = Path(__file__).resolve().parent.parent / "clustersound"
UI = PKG / "ui"

# t('…') / t("…") with a literal first argument, not obj.t( or foot(
_JS_CALL = re.compile(r"""(?<![\w.$])t\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")""")
_HTML_ATTR = re.compile(r'data-i18n(?:-html|-title|-placeholder|-label)?="([^"]*)"')
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _js_unescape(s: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), s)


def ui_texts() -> dict[str, str]:
    """English text -> first file that translates it."""
    out = {}
    for f in sorted(UI.glob("*.js")):
        for m in _JS_CALL.finditer(f.read_text(encoding="utf-8")):
            out.setdefault(_js_unescape(m.group(1) if m.group(1) is not None else m.group(2)), f.name)
    for m in _HTML_ATTR.finditer((UI / "index.html").read_text(encoding="utf-8")):
        out.setdefault(m.group(1).replace("&amp;", "&"), "index.html")
    return out


def backend_texts() -> dict[str, str]:
    out = {}
    for f in sorted(PKG.rglob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) in ("tr", "N_")
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                out.setdefault(node.args[0].value, f.name)
    return out


def test_every_ui_text_has_an_italian_translation():
    it = i18n.load_catalog("it")
    missing = {k: f for k, f in ui_texts().items() if k and k not in it}
    assert not missing, missing


def test_every_backend_text_has_an_italian_translation():
    it = i18n.load_catalog("it")
    missing = {k: f for k, f in backend_texts().items() if k not in it}
    assert not missing, missing


def test_translations_keep_the_placeholders():
    it = i18n.load_catalog("it")
    bad = {k: v for k, v in it.items() if set(_PLACEHOLDER.findall(k)) != set(_PLACEHOLDER.findall(v))}
    assert not bad, bad


def test_tr_follows_the_language():
    try:
        assert i18n.set_language("it") == "it"
        assert i18n.tr("file not found") == "file non trovato"
        assert i18n.tr("Saved to {path}.", path="/x") == "Salvato in /x."
        assert i18n.set_language("fr") == "en"  # unknown languages fall back to English
        assert i18n.tr("file not found") == "file not found"
    finally:
        i18n.set_language("en")
