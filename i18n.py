"""i18n.py — Minimal EN / FR translation support for SimpleLog."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_locale: str = "en"
_PREFS_PATH = Path.home() / ".config" / "simplelog" / "prefs.json"

# id(fn) -> callable — registered retranslate callbacks
_callbacks: dict[int, object] = {}


def register(key: int, fn: object) -> None:
    _callbacks[key] = fn


def unregister(key: int) -> None:
    _callbacks.pop(key, None)


def retranslate_all() -> None:
    for fn in list(_callbacks.values()):
        try:
            fn()  # type: ignore[operator]
        except Exception:
            pass


_BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
_LOCALES_DIR = _BASE / "locales"


def _load_strings() -> dict[str, dict[str, str]]:
    """Load every locales/<lang>.json catalog (English first, it is the fallback)."""
    files = sorted(_LOCALES_DIR.glob("*.json"), key=lambda p: (p.stem != "en", p.stem))
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in files}


_STRINGS: dict[str, dict[str, str]] = _load_strings()


def tr(key: str, **kwargs: object) -> str:
    """Return translated string for *key* in the current locale."""
    lang = _STRINGS.get(_locale, _STRINGS["en"])
    text = lang.get(key) or _STRINGS["en"].get(key) or key
    return text.format(**kwargs) if kwargs else text


def set_locale(locale: str) -> None:
    global _locale
    _locale = locale if locale in _STRINGS else "en"


def get_locale() -> str:
    return _locale


def load_locale() -> None:
    """Load persisted locale preference on startup."""
    global _locale
    try:
        prefs = json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
        candidate = prefs.get("locale", "en")
        if candidate in _STRINGS:
            _locale = candidate
    except Exception:
        pass


def save_locale() -> None:
    """Persist current locale to prefs file."""
    try:
        _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            prefs = json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
        except Exception:
            prefs = {}
        prefs["locale"] = _locale
        tmp = _PREFS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(prefs, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_PREFS_PATH)
    except Exception:
        pass
