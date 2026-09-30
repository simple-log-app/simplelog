"""changelog.py — Read the CHANGELOG files and extract release notes."""
from __future__ import annotations

import re
import sys
from pathlib import Path

LOCALES = ("en", "fr", "de", "es", "zh")
ONLINE_URL = "https://github.com/simple-log-app/simplelog/blob/master/CHANGELOG.md"
_RAW_URL = "https://raw.githubusercontent.com/simple-log-app/simplelog/{tag}/{name}"
_BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def filename(locale: str) -> str:
    return "CHANGELOG.md" if locale == "en" else f"CHANGELOG.{locale}.md"


def raw_url(tag: str, locale: str) -> str:
    return _RAW_URL.format(tag=tag, name=filename(locale))


def _version_tuple(v: str) -> tuple:
    return tuple(int(x) for x in v.lstrip("v").split("."))


def sections(text: str) -> list[tuple[str, str]]:
    """Return (version, markdown) for each "## " section; version is "" when unreleased."""
    result = []
    for part in re.split(r"^(?=## )", text, flags=re.M)[1:]:
        m = re.match(r"## \[v?(\d+(?:\.\d+)*)\]", part)
        result.append((m.group(1) if m else "", part.strip()))
    return result


def notes_between(text: str, current: str, latest: str) -> str:
    """Markdown of the released sections newer than *current*, up to *latest* included."""
    lo, hi = _version_tuple(current), _version_tuple(latest)
    return "\n\n".join(
        md for v, md in sections(text) if v and lo < _version_tuple(v) <= hi
    )


def section_for(text: str, version: str) -> str:
    """Markdown of the section for *version*, or "" if absent."""
    version = version.lstrip("v")
    return next((md for v, md in sections(text) if v == version), "")


def local_text(locale: str) -> str:
    """Bundled changelog for *locale* (falls back to English), or "" if not bundled."""
    for name in (filename(locale), filename("en")):
        try:
            return (_BASE / name).read_text(encoding="utf-8")
        except OSError:
            pass
    return ""


if __name__ == "__main__":
    # Used by the release workflow: print the notes of the tag, fail if missing.
    notes = section_for((_BASE / filename("en")).read_text(encoding="utf-8"), sys.argv[1])
    if not notes:
        sys.exit(f"CHANGELOG.md has no section for {sys.argv[1]}")
    print(notes)
