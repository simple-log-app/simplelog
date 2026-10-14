"""betterstack_utils.py — Better Stack (Logtail) logs over the ClickHouse HTTP API."""
from __future__ import annotations

import base64
import json
import re
import time
from datetime import UTC, datetime

import http_utils

_LABEL = "Better Stack"
# The table name goes into the SQL text: only plain identifiers are accepted
_TABLE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")


def _auth(username: str, password: str) -> dict:
    raw = f"{username}:{password}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


def valid_table(table: str) -> bool:
    return bool(_TABLE_RE.match(table))


def _sql(host: str, username: str, password: str, sql: str, timeout: int = 30) -> list[dict]:
    base = http_utils.normalize_base_url(host)
    with http_utils.request(
        f"{base}/?output_format_pretty_row_numbers=0", data=sql.encode(), method="POST",
        headers={**_auth(username, password), "Content-Type": "text/plain"},
        timeout=timeout, label=_LABEL,
    ) as resp:
        rows = []
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError as e:
                    raise RuntimeError(f"{_LABEL}: unexpected answer: {line[:200]}") from e
        return rows


def check(host: str, username: str, password: str, table: str) -> None:
    """Raise RuntimeError unless the credentials work and the table can be read."""
    if not valid_table(table):
        raise RuntimeError(f"{_LABEL}: invalid table name “{table}”")
    _sql(host, username, password,
         f"SELECT dt FROM remote({table}) LIMIT 1 FORMAT JSONEachRow")


def _dt(value: str) -> int:
    try:
        return int(datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp() * 1000)
    except ValueError:
        return int(time.time() * 1000)


def _fmt(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def fetch_logs(
    host: str, username: str, password: str, table: str, since_ms: int, limit: int = 500,
) -> list[tuple[int, str]]:
    """Log events of *table* newer than *since_ms*, oldest first (``raw`` is kept as text)."""
    if not valid_table(table):
        raise RuntimeError(f"{_LABEL}: invalid table name “{table}”")
    limit = max(1, min(int(limit), 5000))
    sql = (
        f"SELECT dt, raw FROM remote({table}) "
        f"WHERE dt > toDateTime64('{_fmt(since_ms)}', 3, 'UTC') "
        f"ORDER BY dt ASC LIMIT {limit} FORMAT JSONEachRow"
    )
    events = []
    for row in _sql(host, username, password, sql, timeout=45):
        raw = row.get("raw")
        text = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
        events.append((_dt(str(row.get("dt", ""))), text.rstrip()))
    return events
