"""creds_store.py — Simple credential persistence for SimpleLog panels."""
from __future__ import annotations

import json
import os
from pathlib import Path

_DIR = Path.home() / ".config" / "simplelog"


def load(name: str) -> dict:
    """Load saved credentials for *name*. Returns {} if none saved."""
    try:
        return json.loads((_DIR / f"creds_{name}.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def write_private(path: Path, text: str) -> None:
    """Write *text* to *path* readable by the owner only (0600)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    # Write a private temp file, then rename it over the target: a crash mid-write can
    # never leave a truncated file (which would read back as "no profiles").
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
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
