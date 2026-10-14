"""journald_utils.py — the local systemd journal, read through ``journalctl``."""
from __future__ import annotations

import re
import shutil
import time
from datetime import datetime

PRIORITIES = ("", "err", "warning", "notice", "info", "debug")     # "" = all
_UNIT_RE = re.compile(r"^[A-Za-z0-9:_.@\\-]+$")


def is_available() -> bool:
    return shutil.which("journalctl") is not None


def valid_unit(unit: str) -> bool:
    """A systemd unit name (an empty one means "everything")."""
    return not unit or bool(_UNIT_RE.match(unit) and not unit.startswith("-"))


def command(unit: str = "", priority: str = "", lookback_s: int = 3600) -> list[str]:
    """The ``journalctl`` command line that follows the journal."""
    if not valid_unit(unit):
        raise RuntimeError(f"journald: invalid unit name “{unit}”")
    if priority not in PRIORITIES:
        raise RuntimeError(f"journald: invalid priority “{priority}”")
    cmd = ["journalctl", "--no-pager", "--follow", "--output=short-iso-precise",
           f"--since=-{max(1, int(lookback_s))}s"]
    if unit:
        cmd.append(f"--unit={unit}")
    if priority:
        cmd.append(f"--priority={priority}")
    return cmd


def parse_line(raw: str) -> tuple[int, str] | None:
    """``2024-05-01T12:00:00.123456+0200 host unit[1]: text`` -> ``(ts_ms, "host unit[1]: text")``."""
    raw = raw.rstrip("\r\n")
    if not raw.strip() or raw.startswith("-- "):       # "-- Journal begins at …" banners
        return None
    stamp, _, rest = raw.partition(" ")
    try:
        ts = int(datetime.fromisoformat(stamp).timestamp() * 1000)
    except ValueError:
        return int(time.time() * 1000), raw
    return ts, rest or raw
