"""creds_store.py — Simple credential persistence for SimpleLog panels."""
from __future__ import annotations

import json

from config_store import CONFIG_DIR, read_json, write_private

_DIR = CONFIG_DIR


def load(name: str) -> dict:
    """Load saved credentials for *name*. Returns {} if none saved."""
    return read_json(_DIR / f"creds_{name}.json", {})


def save(name: str, data: dict) -> None:
    """Persist *data* as credentials for *name*."""
    write_private(_DIR / f"creds_{name}.json", json.dumps(data, indent=2))


def clear(name: str) -> None:
    """Delete saved credentials for *name* (no-op if absent)."""
    try:
        (_DIR / f"creds_{name}.json").unlink()
    except OSError:
        pass


def exists(name: str) -> bool:
    return (_DIR / f"creds_{name}.json").exists()
