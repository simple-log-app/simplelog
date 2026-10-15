"""profiles_store.py — Named credential profiles for SimpleLog panels."""
from __future__ import annotations

from simplelog.core.config_store import CONFIG_DIR, read_json, write_json

_DIR = CONFIG_DIR


def load_all(service: str) -> list[dict]:
    """Return all saved profiles for *service*, newest first."""
    return read_json(_DIR / f"profiles_{service}.json", [])


def save_all(service: str, profiles: list[dict]) -> None:
    write_json(_DIR / f"profiles_{service}.json", profiles)


def upsert(service: str, name: str, data: dict) -> None:
    """Add or update a profile named *name* with *data*."""
    profiles = load_all(service)
    for i, p in enumerate(profiles):
        if p.get("name") == name:
            profiles[i] = {"name": name, **{k: v for k, v in data.items() if k != "name"}}
            save_all(service, profiles)
            return
    profiles.insert(0, {"name": name, **{k: v for k, v in data.items() if k != "name"}})
    save_all(service, profiles)


def delete(service: str, name: str) -> None:
    """Delete the profile named *name*."""
    save_all(service, [p for p in load_all(service) if p.get("name") != name])
