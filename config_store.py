"""config_store.py — the one place SimpleLog writes its files under ~/.config/simplelog.

Every file holds credentials, hostnames or preferences, so they are all written the same
way: owner-only (0600) in an owner-only directory, replaced atomically.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "simplelog"


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass


def write_private(path: Path, text: str) -> None:
    """Write *text* to *path* readable by the owner only (0600)."""
    _ensure_dir(path)
    # Write a private temp file, then rename it over the target: a crash mid-write can
    # never leave a truncated file (which would read back as "no profiles").
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def append_private(path: Path, text: str) -> None:
    """Append *text* to *path* (created 0600 if absent)."""
    _ensure_dir(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(text)


def read_json(path: Path, default):
    """The JSON stored in *path*, or *default* when it is missing or unreadable."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, data) -> None:
    write_private(path, json.dumps(data, indent=2, ensure_ascii=False))


_PREFS_PATH = CONFIG_DIR / "prefs.json"


def get_pref(key: str, default):
    """A value of the shared preferences file (*default* when unset or unreadable)."""
    prefs = read_json(_PREFS_PATH, {})
    return prefs.get(key, default) if isinstance(prefs, dict) else default


def set_pref(key: str, value) -> None:
    """Store a value in the shared preferences file (read-modify-write)."""
    prefs = read_json(_PREFS_PATH, {})
    if not isinstance(prefs, dict):
        prefs = {}
    prefs[key] = value
    try:
        write_json(_PREFS_PATH, prefs)
    except OSError:
        pass
