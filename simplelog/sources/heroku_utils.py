"""heroku_utils.py — Heroku Platform API helpers (apps, log sessions, logplex lines)."""
from __future__ import annotations

import time
from datetime import datetime

from simplelog.core import http_utils

_API = "https://api.heroku.com"
_LABEL = "Heroku"


def _headers(token: str) -> dict:
    return {
        "Accept": "application/vnd.heroku+json; version=3",
        "Authorization": f"Bearer {token}",
    }


def list_apps(token: str) -> list[dict]:
    """``[{id, name}]`` of the apps the token can see. Raises RuntimeError on failure."""
    data = http_utils.get_json(f"{_API}/apps", headers=_headers(token), label=_LABEL)
    apps = data if isinstance(data, list) else []
    return sorted(
        ({"id": a.get("id", ""), "name": a["name"]} for a in apps if a.get("name")),
        key=lambda a: a["name"],
    )


def create_log_session(token: str, app: str, lines: int = 200, tail: bool = True) -> str:
    """Ask Heroku for a log session of *app* and return its ``logplex_url``.

    The URL needs no further authentication and is only valid for a short while, so
    it has to be opened right away.
    """
    body = {"lines": max(1, min(int(lines), 1500)), "tail": bool(tail), "source": "app"}
    data = http_utils.get_json(
        f"{_API}/apps/{app}/log-sessions", headers=_headers(token), data=body,
        method="POST", label=_LABEL,
    )
    url = data.get("logplex_url") if isinstance(data, dict) else None
    if not url:
        raise RuntimeError("Heroku: no log stream URL in the response")
    return url


def open_log_stream(url: str, timeout: int = 60):
    """Open a logplex URL; iterating the response yields raw log lines (bytes)."""
    return http_utils.request(url, timeout=timeout, label=_LABEL)


def parse_line(raw: str) -> tuple[int, str] | None:
    """``2024-05-01T12:00:00.123456+00:00 app[web.1]: text`` -> ``(ts_ms, "app[web.1]: text")``."""
    raw = raw.rstrip("\r\n")
    if not raw.strip():
        return None
    stamp, _, rest = raw.partition(" ")
    try:
        ts = int(datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return int(time.time() * 1000), raw
    return ts, rest or raw
