"""Unit tests for LogModel — no GUI required."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("DISPLAY", ":0")


def _make_model():
    # LogModel needs a QApplication to exist for signal/slot machinery
    from PyQt6.QtWidgets import QApplication

    from ui import LogModel
    app = QApplication.instance() or QApplication(sys.argv)
    return LogModel(), app


def test_empty_model():
    model, _ = _make_model()
    assert model.rowCount() == 0


def test_append_plain_events():
    model, _ = _make_model()
    model.append_events([(0, "hello"), (0, "world")])
    assert model.rowCount() == 2


def test_append_json_event():
    from ui import _ITEM_ROLE
    model, _ = _make_model()
    model.append_events([(0, '{"message": "hi", "level": "INFO"}')])
    assert model.rowCount() == 1
    item = model.data(model.index(0), _ITEM_ROLE)
    assert item.is_json is True
    assert item.main_key == "message"


def test_json_keys_emitted():
    results = []
    model, _ = _make_model()
    model.json_keys_updated.connect(results.append)
    model.append_events([(0, '{"skills": "toto", "version": "1.0"}')])
    assert len(results) == 1
    assert "skills" in results[0]
    assert "version" in results[0]


def test_apply_filter_hides_non_matching():
    from ui import TermRow
    model, _ = _make_model()
    model.append_events([(0, "ERROR: bad"), (0, "INFO: good"), (0, "ERROR: also bad")])
    assert model.rowCount() == 3
    model.apply_filter([TermRow(text="ERROR", operator="")])
    assert model.rowCount() == 2


def test_apply_filter_empty_shows_all():
    model, _ = _make_model()
    model.append_events([(0, "ERROR: bad"), (0, "INFO: good")])
    model.apply_filter([])
    assert model.rowCount() == 2


def test_clear():
    model, _ = _make_model()
    model.append_events([(0, "a"), (0, "b")])
    model.clear()
    assert model.rowCount() == 0


def test_max_lines_enforced():
    model, _ = _make_model()
    model._MAX_LINES = 5
    events = [(0, f"line {i}") for i in range(10)]
    model.append_events(events)
    assert model.rowCount() <= 5


def test_kv_filter():
    from ui import TermRow
    model, _ = _make_model()
    model.append_events([
        (0, '{"skills": "toto", "level": "INFO"}'),
        (0, '{"skills": "other", "level": "INFO"}'),
        (0, "plain line"),
    ])
    model.apply_filter([TermRow(text="toto", operator="", key="skills")])
    assert model.rowCount() == 1


def test_expand_toggle():
    from ui import _EXPANDED_ROLE, _ITEM_ROLE
    model, _ = _make_model()
    model.append_events([(0, '{"message": "hi"}')])
    idx = model.index(0)
    item = model.data(idx, _ITEM_ROLE)
    assert item.expanded is False
    model.setData(idx, True, _EXPANDED_ROLE)
    assert item.expanded is True


def test_insert_break_adds_row():
    from ui import _ITEM_ROLE
    model, _ = _make_model()
    model.append_events([(0, "line 1"), (0, "line 2")])
    model.insert_break()
    assert model.rowCount() == 3
    item = model.data(model.index(2), _ITEM_ROLE)
    assert item.is_break is True
    assert "══" in item.message


def test_break_survives_filter():
    from ui import _ITEM_ROLE, TermRow
    model, _ = _make_model()
    model.append_events([(0, "ERROR: bad"), (0, "INFO: good")])
    model.insert_break()
    model.apply_filter([TermRow(text="ERROR", operator="")])
    # 1 matching line + 1 break
    assert model.rowCount() == 2
    items = [model.data(model.index(i), _ITEM_ROLE) for i in range(model.rowCount())]
    assert any(it.is_break for it in items)


# ── level filter ─────────────────────────────────────────────────────────────

def _lvl_model():
    from log_model import LogModel
    m = LogModel()
    m.append_events([
        (1, "ERROR db down"), (2, "WARN slow query"), (3, "INFO started"),
        (4, "DEBUG cache miss"), (5, "no level here"),
    ])
    return m


def test_hiding_levels_removes_those_rows_only():
    m = _lvl_model()
    m.apply_filter([], {"debug", "info"})
    assert [i.message for i in m.visible_items()] == ["ERROR db down", "WARN slow query", "no level here"]
    m.apply_filter([], frozenset())
    assert m.visible_count() == 5


def test_level_filter_combines_with_the_terms():
    from log_model import TermRow
    m = _lvl_model()
    m.apply_filter([TermRow("db", "")], {"warn"})
    assert [i.message for i in m.visible_items()] == ["ERROR db down"]


def test_new_lines_respect_the_level_filter_and_breaks_stay():
    m = _lvl_model()
    m.apply_filter([], {"error"})
    m.append_events([(6, "ERROR again"), (7, "INFO ok")])
    m.insert_break()
    shown = [i.message for i in m.visible_items()]
    assert "ERROR again" not in shown and "INFO ok" in shown
    assert any(i.is_break for i in m.visible_items())
    m.apply_filter([], {"error", "info"})
    assert any(i.is_break for i in m.visible_items())


# ── case / regex options ─────────────────────────────────────────────────────

def test_case_option_changes_matching():
    from log_model import TermRow, _line_matches
    assert _line_matches("Error: Boom", [TermRow("error", "")])
    assert not _line_matches("Error: Boom", [TermRow("error", "", case=True)])
    assert _line_matches("Error: Boom", [TermRow("Error", "", case=True)])


def test_regex_option_matches_patterns_and_json_values():
    from log_model import TermRow, _line_matches
    assert _line_matches("took 245 ms", [TermRow(r"\d{3} ms", "", regex=True)])
    assert not _line_matches("took 245 ms", [TermRow(r"\d{3} ms", "")])      # literal text
    assert _line_matches('{"code": "E42"}', [TermRow(r"^E\d+$", "", key="code", regex=True)])
    assert _line_matches("Fatal", [TermRow(r"^FATAL$", "", regex=True)])     # still case-insensitive
    assert not _line_matches("Fatal", [TermRow(r"^FATAL$", "", case=True, regex=True)])


def test_invalid_regex_matches_nothing_and_is_reported():
    from log_model import TermRow, _line_matches, term_is_invalid
    bad = TermRow("(unclosed", "", regex=True)
    assert term_is_invalid(bad)
    assert not _line_matches("(unclosed", [bad])
    assert not term_is_invalid(TermRow("(unclosed", ""))      # fine as plain text
    assert not term_is_invalid(TermRow("", "", regex=True))


def test_terms_with_different_options_are_different_filters():
    from log_model import LogModel, TermRow
    m = LogModel()
    m.append_events([(1, "Error A"), (2, "error b")])
    m.apply_filter([TermRow("error", "")])
    assert m.visible_count() == 2
    m.apply_filter([TermRow("error", "", case=True)])
    assert m.visible_count() == 1


# ── bookmarks ────────────────────────────────────────────────────────────────

def test_bookmarks_are_set_listed_and_skip_breaks():
    from log_model import LogModel
    m = LogModel()
    m.append_events([(1, "a"), (2, "b"), (3, "c")])
    m.insert_break()
    m.set_bookmarks([0, 2, 3, 99], True)       # row 3 is the break, 99 does not exist
    assert m.bookmark_rows() == [0, 2]
    m.set_bookmarks([0], False)
    assert m.bookmark_rows() == [2]


def test_bookmarks_follow_their_rows_through_a_filter():
    from log_model import LogModel, TermRow
    m = LogModel()
    m.append_events([(1, "keep a"), (2, "drop"), (3, "keep b")])
    m.set_bookmarks([2], True)                 # "keep b"
    m.apply_filter([TermRow("keep", "")])
    assert m.bookmark_rows() == [1]
    m.apply_filter([TermRow("drop", "")])
    assert m.bookmark_rows() == []


# ── merged views ─────────────────────────────────────────────────────────────

def test_sorted_append_interleaves_sources_by_time():
    from log_model import LogModel
    m = LogModel()
    m.append_events_sorted([(10, "api 1"), (30, "api 3")], "api")
    m.append_events_sorted([(20, "db 2"), (40, "db 4")], "db")
    assert [(i.ts_ms, i.source) for i in m.visible_items()] == [
        (10, "api"), (20, "db"), (30, "api"), (40, "db")]
    m.append_events_sorted([(50, "api 5")], "api")                   # newer: plain append
    assert m.visible_items()[-1].message == "api 5"
    m.append_events_sorted([(5, "late")], "db")                      # older: re-sorted
    assert m.visible_items()[0].message == "late"


def test_sorted_append_keeps_the_filter_and_the_cap():
    from log_model import LogModel, TermRow
    m = LogModel()
    m._MAX_LINES = 4
    m.append_events_sorted([(1, "keep a"), (3, "drop")], "x")
    m.apply_filter([TermRow("keep", "")])
    m.append_events_sorted([(2, "keep b"), (4, "keep c")], "y")
    assert [i.message for i in m.visible_items()] == ["keep a", "keep b", "keep c"]
    m.append_events_sorted([(5, "keep d"), (6, "keep e")], "x")
    assert len(m._items) == 4


def test_all_events_lists_everything_but_breaks():
    from log_model import LogModel
    m = LogModel()
    m.append_events([(1, "a"), (2, "b")])
    m.insert_break()
    assert m.all_events() == [(1, "a"), (2, "b")]


def test_clear_bookmarks_removes_them_everywhere_even_on_filtered_rows():
    from log_model import LogModel, TermRow
    m = LogModel()
    m.append_events([(1, "keep a"), (2, "hidden"), (3, "keep b")])
    m.set_bookmarks([0, 1, 2], True)
    m.apply_filter([TermRow("keep", "")])            # "hidden" is no longer shown
    assert m.bookmark_rows() == [0, 1]
    assert m.clear_bookmarks() == 3                  # the hidden one counts too
    assert m.bookmark_rows() == []
    m.apply_filter([])
    assert m.bookmark_rows() == [] and m.clear_bookmarks() == 0
