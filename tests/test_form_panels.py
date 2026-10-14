"""The declarative panels of the newer sources, and their place in the connection dialog."""
from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

import betterstack_utils
import heroku_utils
import journald_utils
import profiles_store
import render_utils
import sentry_utils
import splunk_utils


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles_store, "_DIR", tmp_path)


def _wait(cond, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QApplication.processEvents()
        if cond():
            return True
        time.sleep(0.005)
    return False


def _panel(pid):
    import providers
    return providers.get(pid).panel_class()()


def _opened(panel):
    got = []
    panel.open_tab.connect(lambda cfg, mode: got.append((cfg, mode)))
    return got


# ── target lists: Heroku, Render, Sentry ─────────────────────────────────────

def test_heroku_panel_connect_pick_open(monkeypatch):
    monkeypatch.setattr(heroku_utils, "list_apps",
                        lambda token: [{"id": "1", "name": "shop"}, {"id": "2", "name": "blog"}])
    p = _panel("heroku")
    got = _opened(p)
    assert not p.can_open() and not p.is_connected()
    p._inputs["token"].setText("tok")
    p._do_connect()
    assert _wait(p.is_connected)
    assert p._targets.count() == 2 and not p.can_open()          # still nothing picked
    p._targets.setCurrentRow(0)
    assert p.can_open()
    p._on_open()
    cfg, mode = got[0]
    assert cfg == {"type": "heroku", "token": "tok", "app_name": "shop", "label": "shop",
                   "interval_s": p._interval.value(), "lookback_s": p._lookback.currentData()}
    assert mode == "tab"
    assert p.profile_data() == {"token": "tok"}


def test_render_panel_cfg_carries_the_owner(monkeypatch):
    monkeypatch.setattr(render_utils, "list_services", lambda key: [
        {"id": "srv-1", "name": "api", "type": "web_service", "owner_id": "own-1"}])
    p = _panel("render")
    got = _opened(p)
    p._inputs["api_key"].setText("key")
    p._do_connect()
    assert _wait(p.is_connected)
    assert p._targets.item(0).text() == "api  (web_service)"
    p._targets.setCurrentRow(0)
    p._on_open()
    cfg = got[0][0]
    assert (cfg["type"], cfg["owner_id"], cfg["resource_id"], cfg["name"]) == (
        "render", "own-1", "srv-1", "api")


def test_sentry_panel_lists_org_slash_project(monkeypatch):
    seen = {}

    def projects(token, url):
        seen.update(token=token, url=url)
        return [{"org": "acme", "slug": "web", "name": "Web"}]

    monkeypatch.setattr(sentry_utils, "list_projects", projects)
    p = _panel("sentry")
    got = _opened(p)
    assert p._inputs["url"].text() == "https://sentry.io"           # sensible default
    p._inputs["token"].setText("tok")
    p._do_connect()
    assert _wait(p.is_connected)
    assert seen == {"token": "tok", "url": "https://sentry.io"}
    p._targets.setCurrentRow(0)
    p._on_open()
    assert (got[0][0]["org"], got[0][0]["project"], got[0][0]["label"]) == ("acme", "web", "acme/web")


def test_no_targets_found_keeps_open_disabled(monkeypatch):
    monkeypatch.setattr(heroku_utils, "list_apps", lambda token: [])
    p = _panel("heroku")
    p._inputs["token"].setText("tok")
    p._do_connect()
    assert _wait(lambda: "Nothing found" in p._status.text())
    assert not p.is_connected() and not p.can_open()


# ── no target list: Splunk, Better Stack ─────────────────────────────────────

def test_splunk_panel_needs_a_successful_check_then_opens_with_the_query(monkeypatch):
    calls = []
    monkeypatch.setattr(splunk_utils, "server_name", lambda *a: calls.append(a) or "splunk-1")
    p = _panel("splunk")
    got = _opened(p)
    assert not p.can_open()
    for key, value in (("url", "https://s.example.com:8089"), ("token", "T")):
        p._inputs[key].setText(value)
    p._switches["verify_tls"].setChecked(False)
    p._do_connect()
    assert _wait(p.is_connected)
    assert calls == [("https://s.example.com:8089", "T", "", "", False)]
    assert p.can_open()
    p._inputs["query"].setText("index=main error")
    p._on_open()
    cfg = got[0][0]
    assert cfg["type"] == "splunk" and cfg["query"] == "index=main error"
    assert cfg["verify_tls"] is False and cfg["label"] == "s.example.com:8089"
    assert "query" not in p.profile_data()                      # the query is not a credential
    assert p.profile_data()["verify_tls"] is False


def test_failed_connection_shows_the_error_and_stays_closed(monkeypatch):
    def boom(*a):
        raise RuntimeError("Splunk 401: bad credentials")

    monkeypatch.setattr(splunk_utils, "server_name", boom)
    p = _panel("splunk")
    p._inputs["url"].setText("https://s:8089")
    p._do_connect()
    assert _wait(lambda: "401" in p._status.text())
    assert not p.can_open() and p._connect_btn.isEnabled()


def test_missing_fields_are_reported_without_any_network_call(monkeypatch):
    called = []
    monkeypatch.setattr(betterstack_utils, "check", lambda *a: called.append(a))
    p = _panel("betterstack")
    p._inputs["host"].setText("h")
    p._do_connect()
    assert _wait(lambda: "required fields" in p._status.text())
    assert called == [] and not p.can_open()


def test_betterstack_panel_roundtrip_and_cfg(monkeypatch):
    monkeypatch.setattr(betterstack_utils, "check", lambda *a: None)
    p = _panel("betterstack")
    got = _opened(p)
    profile = {"host": "h.example.com", "username": "u", "password": "p", "table": "t1_x_logs"}
    p.load_profile(profile)
    assert p.profile_data() == profile
    p._do_connect()
    assert _wait(p.is_connected)
    p._on_open()
    assert got[0][0]["table"] == "t1_x_logs" and got[0][0]["label"] == "t1_x_logs"


# ── journald: local, nothing to connect ──────────────────────────────────────

def test_journald_panel_opens_straight_away_when_journalctl_exists(monkeypatch):
    monkeypatch.setattr(journald_utils, "is_available", lambda: True)
    p = _panel("journald")
    got = _opened(p)
    assert p.saveable is False and p.is_connected() and p.can_open()
    p._inputs["unit"].setText("nginx.service")
    p._inputs["priority"].setCurrentIndex(1)
    p._on_open()
    cfg = got[0][0]
    assert (cfg["unit"], cfg["priority"], cfg["label"]) == ("nginx.service", "err", "nginx.service")


def test_journald_panel_refuses_without_journalctl_or_with_a_bad_unit(monkeypatch):
    monkeypatch.setattr(journald_utils, "is_available", lambda: False)
    p = _panel("journald")
    assert not p.can_open()
    monkeypatch.setattr(journald_utils, "is_available", lambda: True)
    p._inputs["unit"].setText("--vacuum-size=1")
    assert not p.can_open()


# ── inside the dialog: saving, reopening and restoring the choice ────────────

def test_dialog_saves_a_new_connection_and_restores_its_selection(monkeypatch):
    import ui
    monkeypatch.setattr(heroku_utils, "list_apps",
                        lambda token: [{"id": "1", "name": "shop"}, {"id": "2", "name": "blog"}])
    dlg = ui.AddConnectionDialog(preselect="heroku")
    panel = dlg._embedded_panel
    emitted = []
    dlg.tab_requested.connect(lambda cfg, mode: emitted.append((cfg, mode)))
    panel._inputs["token"].setText("tok")
    panel._do_connect()
    assert _wait(panel.is_connected)
    panel._targets.setCurrentRow(1)                       # "blog"
    dlg._fields["name"].setText("my heroku")
    dlg._sync_embedded_footer()
    assert dlg._save_open_btn.isEnabled()
    dlg._open_mode_w._btns["vertical"].setChecked(True)
    dlg._on_save_open()
    assert emitted[0][1] == "vertical" and emitted[0][0]["app_name"] == "blog"
    saved = profiles_store.load_all("heroku")[0]
    assert saved["name"] == "my heroku" and saved["token"] == "tok"
    assert saved["state"]["_targets"].startswith("blog")

    again = ui.AddConnectionDialog(preselect="heroku", prefill_profile=saved)
    assert _wait(lambda: again._embedded_panel.can_open(), 5)     # reconnects, re-selects "blog"
    assert again._embedded_panel._target()["name"] == "blog"


def test_dialog_for_journald_has_no_name_field_and_no_save(monkeypatch):
    import ui
    monkeypatch.setattr(journald_utils, "is_available", lambda: True)
    dlg = ui.AddConnectionDialog(preselect="journald")
    assert "name" not in dlg._fields and dlg._save_open_btn is None
    dlg._sync_embedded_footer()
    assert dlg._open_btn.isEnabled()


def test_the_picker_lists_every_source_and_filters_the_new_ones():
    import providers
    import ui
    dlg = ui.AddConnectionDialog()
    assert len(dlg._cards) == len(providers.PROVIDERS) >= 19
    dlg.show()
    dlg._filter_edit.setText("splunk")
    assert [p.id for p, card in dlg._cards if card.isVisible()] == ["splunk"]
    dlg._filter_edit.setText("journal")
    assert [p.id for p, card in dlg._cards if card.isVisible()] == ["journald"]
