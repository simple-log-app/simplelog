"""splunk_utils.py — Splunk REST API helpers (connection test, streaming search export)."""
from __future__ import annotations

import base64
import json
import time
from datetime import datetime

import http_utils

_LABEL = "Splunk"


def _headers(token: str, username: str, password: str) -> dict:
    if token:
        return {"Authorization": f"Bearer {token}"}
    raw = f"{username}:{password}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


def _check_auth(token: str, username: str, password: str) -> None:
    if not token and not (username and password):
        raise RuntimeError("Splunk: give an authentication token, or a user name and password")


def server_name(url: str, token: str = "", username: str = "", password: str = "",
                verify_tls: bool = True) -> str:
    """Connect to the management port and return the server's name (raises on failure)."""
    _check_auth(token, username, password)
    base = http_utils.normalize_base_url(url)
    data = http_utils.get_json(
        f"{base}/services/server/info?output_mode=json",
        headers=_headers(token, username, password), label=_LABEL,
        context=http_utils.tls_context(verify_tls),
    )
    try:
        return str(data["entry"][0]["content"].get("serverName", ""))
    except (KeyError, IndexError, TypeError, AttributeError):
        return ""


def _search_string(query: str) -> str:
    query = query.strip() or "*"
    return query if query.startswith(("search ", "|")) else f"search {query}"


def _parse_time(value: str) -> int:
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except (ValueError, AttributeError):
        return int(time.time() * 1000)


def export_search(
    url: str, query: str, earliest_s: float, token: str = "", username: str = "",
    password: str = "", verify_tls: bool = True, limit: int = 500, timeout: int = 60,
) -> list[tuple[int, str]]:
    """Run *query* from *earliest_s* (epoch seconds) until now, oldest event first.

    Uses the streaming ``search/jobs/export`` endpoint: one JSON object per line, each
    holding an event whose ``_raw`` is the log line.
    """
    _check_auth(token, username, password)
    base = http_utils.normalize_base_url(url)
    form = {
        "search": _search_string(query),
        "output_mode": "json",
        "earliest_time": f"{earliest_s:.3f}",
        "latest_time": "now",
    }
    events: list[tuple[int, str]] = []
    with http_utils.request(
        f"{base}/services/search/jobs/export", form=form, method="POST", timeout=timeout,
        headers=_headers(token, username, password), label=_LABEL,
        context=http_utils.tls_context(verify_tls),
    ) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            result = obj.get("result") if isinstance(obj, dict) else None
            if not isinstance(result, dict):
                continue
            text = result.get("_raw") or json.dumps(result, ensure_ascii=False)
            events.append((_parse_time(str(result.get("_time", ""))), str(text).rstrip()))
            if len(events) >= limit:
                break
    return sorted(events, key=lambda e: e[0])
