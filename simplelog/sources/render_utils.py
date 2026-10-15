"""render_utils.py — Render API helpers (services, logs)."""
from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime

from simplelog.core import http_utils

_API = "https://api.render.com/v1"
_LABEL = "Render"
_MAX_PAGES = 5


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


def _iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_ts(value: str) -> int:
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except (ValueError, AttributeError):
        return 0


def list_services(api_key: str) -> list[dict]:
    """``[{id, name, type, owner_id}]`` of the services of the account."""
    data = http_utils.get_json(
        f"{_API}/services?limit=100", headers=_headers(api_key), label=_LABEL)
    services = []
    for entry in data if isinstance(data, list) else []:
        svc = entry.get("service", entry) if isinstance(entry, dict) else {}
        if svc.get("id") and svc.get("name"):
            services.append({
                "id": svc["id"], "name": svc["name"],
                "type": svc.get("type", ""), "owner_id": svc.get("ownerId", ""),
            })
    return sorted(services, key=lambda s: s["name"])


def fetch_logs(
    api_key: str, owner_id: str, resource_id: str, start_ms: int, end_ms: int | None = None,
    limit: int = 100,
) -> list[tuple[int, str]]:
    """The log lines of a service between *start_ms* and now, oldest first."""
    start = _iso(start_ms)
    end = _iso(end_ms) if end_ms else None
    events: list[tuple[int, str]] = []
    for _ in range(_MAX_PAGES):
        params = {"ownerId": owner_id, "resource": resource_id, "direction": "forward",
                  "limit": max(1, min(limit, 100)), "startTime": start}
        if end:
            params["endTime"] = end
        data = http_utils.get_json(
            f"{_API}/logs?{urllib.parse.urlencode(params)}",
            headers=_headers(api_key), label=_LABEL,
        )
        if not isinstance(data, dict):
            break
        for log in data.get("logs", []):
            message = str(log.get("message", ""))
            if not message:
                continue
            labels = {lb.get("name"): lb.get("value") for lb in log.get("labels", [])
                      if isinstance(lb, dict)}
            level = labels.get("level")
            if level:
                message = f"[{level}] {message}"
            events.append((_parse_ts(log.get("timestamp", "")), message.rstrip()))
        next_start = data.get("nextStartTime")
        if not data.get("hasMore") or not next_start or next_start == start:
            break
        start = next_start
        end = data.get("nextEndTime") or end
    return sorted(events, key=lambda e: e[0])
