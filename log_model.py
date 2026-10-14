"""Filter terms, line classification and the log list model."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from PyQt6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    Qt,
    pyqtSignal,
)

# ── Filter / search data model ─────────────────────────────────────────────────

@dataclass
class TermRow:
    text: str
    operator: str  # "AND" | "OR" | "" — empty string for the first term (ignored)
    key: str = ""  # non-empty → JSON key=value match mode
    case: bool = False   # match case
    regex: bool = False  # *text* is a regular expression


@lru_cache(maxsize=256)
def _compile(text: str, case: bool, regex: bool) -> re.Pattern[str] | None:
    """The pattern of a term, or None when it is an invalid regular expression."""
    try:
        return re.compile(text if regex else re.escape(text), 0 if case else re.IGNORECASE)
    except re.error:
        return None


def term_pattern(term: TermRow) -> re.Pattern[str] | None:
    return _compile(term.text, term.case, term.regex)


def term_is_invalid(term: TermRow) -> bool:
    """True for a regular expression that does not compile (it matches nothing)."""
    return bool(term.regex and term.text and term_pattern(term) is None)


def _text_in(term: TermRow, haystack: str) -> bool:
    """Does *haystack* contain the term's text, honouring its case / regex options?"""
    if not term.regex and not term.case:
        return term.text.lower() in haystack.lower()      # the common, fast case
    pattern = term_pattern(term)
    return pattern is not None and pattern.search(haystack) is not None


def _line_matches(line: str, terms: list[TermRow], json_data: dict | None = None) -> bool:
    """Return True if *line* satisfies the AND/OR chain of *terms* (case-insensitive unless
    a term asks for case, and plain text unless a term is a regular expression).

    *json_data* is the already parsed line, when the caller has it (saves a parse per term).
    """
    if not terms:
        return True

    def _term_hit(term: TermRow) -> bool:
        if not term.key:
            # Plain text match
            return _text_in(term, line)
        # Key=value match: parse line as JSON, check data[key] contains text
        # Try the full line first, then search for an embedded JSON object
        data = json_data
        stripped = line.strip()
        try:
            parsed = json.loads(stripped) if data is None else None
            if isinstance(parsed, dict):
                data = parsed
        except (json.JSONDecodeError, ValueError):
            pass
        if data is None and json_data is None:
            # Try to find an embedded JSON object in the line
            start = line.find("{")
            if start != -1:
                try:
                    parsed = json.loads(line[start:])
                    if isinstance(parsed, dict):
                        data = parsed
                except (json.JSONDecodeError, ValueError):
                    pass
        if data is None or term.key not in data:
            return False
        if term.text == "":
            return True  # key presence check
        return _text_in(term, str(data[term.key]))

    result = _term_hit(terms[0])
    for term in terms[1:]:
        hit = _term_hit(term)
        result = (result and hit) if term.operator == "AND" else (result or hit)
    return result


# ── JSON parsing + line classification ─────────────────────────────────────────

def _try_parse_json(message: str) -> dict | None:
    """Try to parse message as a JSON object. Returns dict or None."""
    stripped = message.strip()
    if not stripped.startswith("{"):
        return None
    try:
        data = json.loads(stripped)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


_CLASSIFY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("error", re.compile(r"\b(CRITICAL|FATAL|ERROR|ERR)\b", re.IGNORECASE)),
    ("warn",  re.compile(r"\b(WARN(?:ING)?)\b",             re.IGNORECASE)),
    ("info",  re.compile(r"\bINFO\b",                       re.IGNORECASE)),
    ("debug", re.compile(r"\bDEBUG\b",                      re.IGNORECASE)),
    ("trace", re.compile(r"\bTRACE\b",                      re.IGNORECASE)),
]


def _classify_line(text: str) -> str:
    """Return severity level string for a log line."""
    for level, pattern in _CLASSIFY_PATTERNS:
        if pattern.search(text):
            return level
    return "plain"


LEVELS = ("error", "warn", "info", "debug", "trace")   # the levels that can be hidden


def level_of(item: LogItem) -> str:
    """Severity of a row (computed once, then cached on the row)."""
    if item.level is None:
        item.level = _classify_line(item.message)
    return item.level


_MAIN_KEYS = (
    "message", "msg", "error", "err", "data", "content", "text",
    "body", "log", "description", "details", "payload", "result", "output", "value",
)


def _resolve_main_key(data: dict) -> str | None:
    """Return the first priority key found in data, or None."""
    for k in _MAIN_KEYS:
        if k in data:
            return k
    return None


# ── LogItem + LogModel ─────────────────────────────────────────────────────────

@dataclass
class LogItem:
    ts_ms: int
    message: str
    is_json: bool
    json_data: dict | None
    main_key: str | None
    expanded: bool = False
    visible: bool = True
    is_break: bool = False
    bookmarked: bool = False
    source: str = ""     # which tab a line came from (merged views only)
    # Row-height cache owned by the delegate: (layout key, height)
    size_cache: tuple | None = None
    level: str | None = None   # severity, computed lazily by the delegate
    ts_text: str | None = None  # formatted HH:MM:SS, computed lazily by the delegate
    # Last search outcome for this row: (terms key, [(start, length), ...])
    search: tuple | None = None
    # Highlight-rule matches: (rules version, [(start, length, colour), ...])
    highlight: tuple | None = None


_ITEM_ROLE     = Qt.ItemDataRole.UserRole + 1
_EXPANDED_ROLE = Qt.ItemDataRole.UserRole + 2


class LogModel(QAbstractListModel):
    rows_appended     = pyqtSignal()
    json_keys_updated = pyqtSignal(set)
    filter_applied    = pyqtSignal()

    _MAX_LINES = 10_000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[LogItem] = []
        self._visible: list[LogItem] = []   # references into _items
        self._json_keys: set[str] = set()
        self._current_filter_terms: list[TermRow] = []
        self._hidden_levels: frozenset[str] = frozenset()

    def _passes_filter(self, item: LogItem) -> bool:
        """Does a row satisfy the filter terms and the level filter (breaks always do)?"""
        if item.is_break:
            return True
        if self._hidden_levels and level_of(item) in self._hidden_levels:
            return False
        return _line_matches(item.message, self._current_filter_terms, item.json_data)

    # ── QAbstractListModel interface ──────────────────────────────────────────

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._visible)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._visible):
            return None
        item = self._visible[index.row()]
        if role == _ITEM_ROLE:
            return item
        if role == Qt.ItemDataRole.DisplayRole:
            return item.message
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if role == _EXPANDED_ROLE and index.isValid():
            item = self._visible[index.row()]
            item.expanded = bool(value)
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    # ── Public API ────────────────────────────────────────────────────────────

    def all_events(self) -> list[tuple[int, str]]:
        """Every line held (shown or not), oldest first, without the section breaks."""
        return [(it.ts_ms, it.message) for it in self._items if not it.is_break]

    def append_events_sorted(self, events: list[tuple[int, str]], source: str = "") -> None:
        """Add lines that may be older than what is already here, keeping time order.

        Used by merged views, which receive lines from several logs at once.
        """
        if not events:
            return
        events = sorted(events, key=lambda e: e[0])
        newest = max((it.ts_ms for it in self._items), default=0)
        self.append_events(events, source)
        if events[0][0] >= newest:
            return                       # all newer: already in order
        self._items.sort(key=lambda it: it.ts_ms)     # stable: equal times keep their order
        self.beginResetModel()
        self._visible = [it for it in self._items if it.visible]
        self.endResetModel()
        self.rows_appended.emit()

    def append_events(self, events: list[tuple[int, str]], source: str = "") -> None:
        if not events:
            return
        new_keys: set[str] = set()
        appended: list[LogItem] = []

        for ts_ms, message in events:
            json_data = _try_parse_json(message)
            main_key  = _resolve_main_key(json_data) if json_data else None
            item = LogItem(
                ts_ms=ts_ms,
                message=message,
                is_json=json_data is not None,
                json_data=json_data,
                main_key=main_key,
                source=source,
            )
            item.visible = self._passes_filter(item)
            self._items.append(item)
            appended.append(item)
            if json_data:
                new_keys |= set(json_data.keys())

        excess = len(self._items) - self._MAX_LINES
        if excess >= len(self._items) - len(appended):
            # Everything that was there goes (the batch alone fills the buffer)
            self._items = self._items[-self._MAX_LINES:]
            self.beginResetModel()
            self._visible = [it for it in self._items if it.visible]
            self.endResetModel()
            self.rows_appended.emit()
        else:
            if excess > 0:
                self._drop_oldest(excess)
            newly_visible = [it for it in appended if it.visible]
            if newly_visible:
                first = len(self._visible)
                self.beginInsertRows(QModelIndex(), first, first + len(newly_visible) - 1)
                self._visible.extend(newly_visible)
                self.endInsertRows()
            if excess > 0 or newly_visible:
                self.rows_appended.emit()

        if new_keys - self._json_keys:
            self._json_keys |= new_keys
            self.json_keys_updated.emit(self._json_keys.copy())

    def _drop_oldest(self, count: int) -> None:
        """Remove the *count* oldest items, announcing only the rows that disappear.

        Removing rows (instead of resetting the model) keeps the selection and the
        scroll position of the remaining rows.
        """
        dropped_visible = sum(1 for it in self._items[:count] if it.visible)
        del self._items[:count]
        if dropped_visible:
            self.beginRemoveRows(QModelIndex(), 0, dropped_visible - 1)
            del self._visible[:dropped_visible]
            self.endRemoveRows()

    def insert_break(self) -> None:
        dt = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        label = f"══════════════  {dt}  ══════════════"
        item = LogItem(
            ts_ms=0, message=label, is_json=False, json_data=None,
            main_key=None, visible=True, is_break=True,
        )
        self._items.append(item)
        first = len(self._visible)
        self.beginInsertRows(QModelIndex(), first, first)
        self._visible.append(item)
        self.endInsertRows()
        self.rows_appended.emit()

    def apply_filter(self, terms: list[TermRow], hidden_levels=frozenset()) -> None:
        hidden_levels = frozenset(hidden_levels)
        if terms == self._current_filter_terms and hidden_levels == self._hidden_levels:
            # Same filter (e.g. switching back to this tab): nothing to rebuild
            self.filter_applied.emit()
            return
        self._current_filter_terms = terms
        self._hidden_levels = hidden_levels
        self.beginResetModel()
        self._visible = []
        for item in self._items:
            item.visible = self._passes_filter(item)
            if item.visible:
                self._visible.append(item)
        self.endResetModel()
        self.filter_applied.emit()

    def set_bookmarks(self, rows: list[int], on: bool) -> None:
        """Bookmark (or un-bookmark) the given visible rows; section breaks are skipped."""
        for row in rows:
            if 0 <= row < len(self._visible) and not self._visible[row].is_break:
                self._visible[row].bookmarked = on
                index = self.index(row)
                self.dataChanged.emit(index, index)

    def bookmark_rows(self) -> list[int]:
        """The visible rows that are bookmarked, top to bottom."""
        return [i for i, item in enumerate(self._visible) if item.bookmarked]

    def clear(self) -> None:
        self.beginResetModel()
        self._items.clear()
        self._visible.clear()
        self._json_keys.clear()
        self.endResetModel()

    def get_json_keys(self) -> set[str]:
        return self._json_keys.copy()

    def visible_items(self) -> list[LogItem]:
        """The rows currently shown, oldest first (not a copy: do not mutate)."""
        return self._visible

    def visible_count(self) -> int:
        return len(self._visible)
