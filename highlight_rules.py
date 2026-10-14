"""User-defined highlight rules: a keyword (or regular expression) and the colour it gets."""
from __future__ import annotations

from dataclasses import dataclass

from config_store import CONFIG_DIR, read_json, write_json
from log_model import TermRow, term_pattern

_PATH = CONFIG_DIR / "highlight_rules.json"
_MAX_RULES = 20

#: Colours offered for a rule (they read on both the dark and the light theme)
PALETTE = ("#e8b04a", "#5fc48a", "#6e9bff", "#b08cf0", "#ef6b6b", "#5cc0d0", "#f08cc0")


@dataclass(frozen=True)
class Rule:
    text: str
    color: str = PALETTE[0]
    case: bool = False
    regex: bool = False


_rules: list[Rule] = []
_version = 0     # bumped on every change: rows cache their matches against it


def version() -> int:
    return _version


def get_rules() -> list[Rule]:
    return list(_rules)


def set_rules(rules: list[Rule], persist: bool = True) -> None:
    """Replace the rules (blank ones are dropped) and save them."""
    global _version
    _rules[:] = [r for r in rules if r.text.strip()][:_MAX_RULES]
    _version += 1
    if persist:
        try:
            write_json(_PATH, [vars(r) for r in _rules])
        except OSError:
            pass


def load() -> None:
    """Read the saved rules (ignoring anything malformed)."""
    rules = []
    data = read_json(_PATH, [])
    for entry in data if isinstance(data, list) else []:
        if isinstance(entry, dict) and isinstance(entry.get("text"), str):
            color = entry.get("color")
            rules.append(Rule(
                entry["text"],
                color if color in PALETTE else PALETTE[0],
                bool(entry.get("case")),
                bool(entry.get("regex")),
            ))
    set_rules(rules, persist=False)


def spans(message: str) -> list[tuple[int, int, str]]:
    """``(start, length, colour)`` of every rule match in *message*, in rule order."""
    found: list[tuple[int, int, str]] = []
    for rule in _rules:
        pattern = term_pattern(TermRow(rule.text, "", case=rule.case, regex=rule.regex))
        if pattern is None:
            continue
        found.extend(
            (m.start(), m.end() - m.start(), rule.color)
            for m in pattern.finditer(message) if m.end() > m.start()
        )
    return found
