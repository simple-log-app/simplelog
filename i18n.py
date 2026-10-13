"""i18n.py — Minimal EN / FR translation support for SimpleLog."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from config_store import CONFIG_DIR, read_json, write_json

_locale: str = "en"
_PREFS_PATH = CONFIG_DIR / "prefs.json"

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


def available_locales() -> list[tuple[str, str]]:
    """``[(code, native name), ...]`` for every locales/<code>.json, English first."""
    return [(code, strings.get("lang_name", code)) for code, strings in _STRINGS.items()]


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
    prefs = read_json(_PREFS_PATH, {})
    if not isinstance(prefs, dict):
        prefs = {}
    prefs["locale"] = _locale
    try:
        write_json(_PREFS_PATH, prefs)
    except OSError:
        pass
