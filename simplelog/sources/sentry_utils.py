"""sentry_utils.py — Sentry API helpers: projects and their error events."""
from __future__ import annotations

import re
import time
import urllib.parse
from datetime import UTC, datetime

from simplelog.core import http_utils

_LABEL = "Sentry"
DEFAULT_URL = "https://sentry.io"
_SLUG_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def list_projects(token: str, url: str = DEFAULT_URL) -> list[dict]:
    """``[{org, slug, name}]`` of the projects the token can read."""
    base = http_utils.normalize_base_url(url or DEFAULT_URL)
    data = http_utils.get_json(f"{base}/api/0/projects/", headers=_headers(token), label=_LABEL)
    projects = []
    for p in data if isinstance(data, list) else []:
        org = (p.get("organization") or {}).get("slug", "")
        if p.get("slug") and org:
            projects.append({"org": org, "slug": p["slug"], "name": p.get("name") or p["slug"]})
    return sorted(projects, key=lambda p: (p["org"], p["slug"]))


def _iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%S")


def _parse_ts(value: str) -> int:
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except (ValueError, AttributeError):
        return int(time.time() * 1000)


def format_event(event: dict) -> tuple[int, str]:
    """One Sentry event as a log line: ``[level] title  culprit``."""
    tags = {t.get("key"): t.get("value") for t in event.get("tags", []) if isinstance(t, dict)}
    level = tags.get("level") or ""
    title = str(event.get("title") or event.get("message") or "(no title)")
    culprit = event.get("culprit") or ""
    text = f"{title}  {culprit}".rstrip()
    if level:
        text = f"[{level}] {text}"
    return _parse_ts(str(event.get("dateCreated", ""))), text


def fetch_events(
    token: str, org: str, project: str, start_ms: int, url: str = DEFAULT_URL,
) -> list[tuple[int, str]]:
    """The error events of a project since *start_ms*, oldest first."""
    if not (_SLUG_RE.match(org) and _SLUG_RE.match(project)):
        raise RuntimeError(f"{_LABEL}: invalid organization or project name")
    base = http_utils.normalize_base_url(url or DEFAULT_URL)
    params = urllib.parse.urlencode({"start": _iso(start_ms), "end": _iso(int(time.time() * 1000) + 1000)})
    data = http_utils.get_json(
        f"{base}/api/0/projects/{org}/{project}/events/?{params}",
        headers=_headers(token), label=_LABEL,
    )
    events = [format_event(e) for e in data if isinstance(e, dict)] if isinstance(data, list) else []
    return sorted(events, key=lambda e: e[0])
