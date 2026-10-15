"""Highlight rules: storage, matching, the editing dialog and the painting hook."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from simplelog.core import highlight_rules
from simplelog.core.highlight_rules import Rule


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def rules_file(tmp_path, monkeypatch):
    monkeypatch.setattr(highlight_rules, "_PATH", tmp_path / "rules.json")
    highlight_rules.set_rules([], persist=False)
    yield tmp_path / "rules.json"
    highlight_rules.set_rules([], persist=False)


def test_rules_round_trip_and_drop_blank_ones(rules_file):
    highlight_rules.set_rules([Rule("timeout", "#ef6b6b"), Rule("  "), Rule(r"\d+ms", "#6e9bff", regex=True)])
    assert [r.text for r in highlight_rules.get_rules()] == ["timeout", r"\d+ms"]
    highlight_rules.set_rules([], persist=False)
    highlight_rules.load()
    assert highlight_rules.get_rules() == [
        Rule("timeout", "#ef6b6b"), Rule(r"\d+ms", "#6e9bff", regex=True)]


def test_load_ignores_garbage(rules_file):
    rules_file.write_text('[{"text": 3}, "x", {"text": "ok", "color": "pink"}]')
    highlight_rules.load()
    assert highlight_rules.get_rules() == [Rule("ok", highlight_rules.PALETTE[0])]
    rules_file.write_text("not json")
    highlight_rules.load()
    assert highlight_rules.get_rules() == []


def test_spans_follow_case_and_regex_options():
    highlight_rules.set_rules([Rule("error", "#ef6b6b"), Rule("OK", "#5fc48a", case=True),
                               Rule(r"\d{3}", "#6e9bff", regex=True), Rule("(bad", "#fff", regex=True)])
    assert highlight_rules.spans("Error 404 ok OK") == [
        (0, 5, "#ef6b6b"), (13, 2, "#5fc48a"), (6, 3, "#6e9bff")]


def test_changing_rules_bumps_the_version():
    before = highlight_rules.version()
    highlight_rules.set_rules([Rule("x")], persist=False)
    assert highlight_rules.version() == before + 1


def test_rows_cache_their_matches_until_the_rules_change():
    from simplelog.ui import facade as ui
    viewer = ui.LogViewer(source_type="file")
    viewer.append_events([(1, "disk full on node-3")])
    item = viewer._model.visible_items()[0]
    delegate = viewer._delegate
    assert delegate._rule_spans(item) == []
    highlight_rules.set_rules([Rule("disk", "#e8b04a")], persist=False)
    assert delegate._rule_spans(item) == [(0, 4, "#e8b04a")]
    cached = item.highlight
    assert delegate._rule_spans(item) is cached[1]          # no second scan


def test_painting_rows_with_rules_works_for_plain_and_json_rows():
    from simplelog.ui import facade as ui
    viewer = ui.LogViewer(source_type="file")
    viewer.resize(600, 300)
    viewer.show()
    viewer.append_events([(1, "plain disk line"), (2, '{"msg": "disk json", "level": "warn"}')])
    highlight_rules.set_rules([Rule("disk", "#e8b04a")], persist=False)
    viewer.refresh_rules()
    QApplication.processEvents()
    img = viewer.grab().toImage()
    assert not img.isNull()


def test_dialog_edits_and_applies_the_rules(rules_file):
    from simplelog.ui import facade as ui
    highlight_rules.set_rules([Rule("one", "#5fc48a")], persist=False)
    dlg = ui.HighlightRulesDialog()
    assert [r.text for r in dlg.rules()] == ["one"]
    dlg._add_row(Rule(""))                                   # blank rows are ignored
    dlg._add_row(Rule("two", "#b08cf0", case=True))
    dlg._remove_row(dlg._rows[0])
    dlg._apply()
    assert highlight_rules.get_rules() == [Rule("two", "#b08cf0", case=True)]
    assert rules_file.exists()


def test_dialog_caps_the_number_of_rules():
    from simplelog.ui import facade as ui
    dlg = ui.HighlightRulesDialog()
    for i in range(30):
        dlg._add_row(Rule(f"r{i}"))
    assert len(dlg._rows) == highlight_rules._MAX_RULES
    assert not dlg._add_btn.isEnabled()
