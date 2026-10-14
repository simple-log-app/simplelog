"""Connection state of remote tabs and their automatic reconnection."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

import connection_state as cs
import providers
from worker_base import LogWorker


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


# ── the pure logic ───────────────────────────────────────────────────────────

def test_backoff_grows_then_gives_up():
    link = cs.Link(provider=None, cfg={})
    delays = []
    while link.can_retry():
        delays.append(link.next_delay())
    assert delays == list(cs.RECONNECT_DELAYS) and not link.can_retry()
    link.connected()
    assert link.can_retry() and link.attempts == 0


def test_cancel_invalidates_scheduled_reconnections():
    link = cs.Link(provider=None, cfg={})
    gen = link.generation
    link.cancel()
    assert link.generation != gen


def test_reconnect_cfg_only_asks_for_what_was_missed():
    link = cs.Link(provider=None, cfg={"lookback_s": 3600, "group": "g", "lookback": 86400})
    cfg = link.reconnect_cfg(gap_s=20)
    assert cfg["lookback_s"] == 60 and cfg["lookback"] == 60 and cfg["group"] == "g"
    assert link.reconnect_cfg(gap_s=500)["lookback_s"] == 530
    assert link.reconnect_cfg(gap_s=10_000_000)["lookback_s"] == 3600       # never more than asked
    assert link.cfg["lookback_s"] == 3600                                   # the original is intact
    assert cs.Link(provider=None, cfg={"x": 1}).reconnect_cfg(5) == {"x": 1}


def test_worst_state_wins():
    assert cs.worst([cs.LIVE, cs.RECONNECTING, cs.STOPPED]) == cs.RECONNECTING
    assert cs.worst([cs.LIVE, cs.FAILED]) == cs.FAILED
    assert cs.worst([cs.STOPPED, cs.LIVE]) == cs.LIVE
    assert cs.worst([]) is None


# ── the window drives it ─────────────────────────────────────────────────────

class FakeWorker(LogWorker):
    """Stays 'running' until stopped, like a stream; tests emit its signals by hand."""

    def run(self) -> None:
        self._wakeup.wait(10)


@pytest.fixture
def env(tmp_path, monkeypatch):
    import config_store
    import main_window
    monkeypatch.setattr(config_store, "_PREFS_PATH", tmp_path / "prefs.json")
    made: list[FakeWorker] = []

    def session(cfg, _client):
        worker = FakeWorker()
        made.append(worker)
        cfg_seen.append(dict(cfg))
        return providers.Session(worker, "ssh", "fake › log", "fake")

    cfg_seen: list[dict] = []
    provider = providers.Provider(
        "fake", "Fake", "F", "#ffffff", "<svg/>", "fake", "panels.railway:RailwayPanel", session)
    dialogs: list = []
    monkeypatch.setattr(main_window.QMessageBox, "critical",
                        staticmethod(lambda *a, **k: dialogs.append(a[2])))
    win = main_window.MainWindow()
    win._open_session(provider, {"lookback_s": 3600, "id": 1}, None, "tab")
    viewer = win._first_viewer_in(win._top_tabs.widget(0))
    yield win, viewer, made, dialogs, cfg_seen
    win.close()
    for w in made:
        w.stop()
        w.wait(2000)


def _link(win, viewer):
    return win._links[id(viewer)]


def test_state_goes_connecting_then_live_with_the_first_line(env):
    win, viewer, made, _, _ = env
    assert _link(win, viewer).state == cs.CONNECTING
    made[0].new_lines.emit([(1000, "first")])
    assert _link(win, viewer).state == cs.LIVE
    assert win._top_tabs.tabToolTip(0) == "Connected"
    assert not win._top_tabs.tabIcon(0).isNull()


def test_a_dropped_stream_reconnects_instead_of_popping_a_dialog(env):
    win, viewer, made, dialogs, _ = env
    made[0].new_lines.emit([(1000, "before")])
    made[0].error.emit("connection reset")
    link = _link(win, viewer)
    assert link.state == cs.RECONNECTING and not dialogs
    assert "reconnecting in 3 s" in win._top_tabs.tabToolTip(0)
    assert id(viewer) not in win._workers          # the dead worker is gone, none is running
    assert viewer._model.visible_count() == 1      # the lines already shown stay


def test_reconnecting_resumes_without_duplicating_lines(env):
    win, viewer, made, _, cfg_seen = env
    made[0].new_lines.emit([(1000, "a"), (2000, "b")])
    made[0].error.emit("reset")
    link = _link(win, viewer)
    win._reconnect(viewer, link.generation)
    assert len(made) == 2 and win._workers[id(viewer)] is made[1]
    assert cfg_seen[1]["lookback_s"] <= 3600 and cfg_seen[1]["id"] == 1
    made[1].history_done.emit(2) if hasattr(made[1], "history_done") else None
    made[1].new_lines.emit([(1000, "a"), (2000, "b"), (3000, "c")])    # history re-sent + news
    viewer.flush_pending()
    messages = [i.message for i in viewer._model.visible_items()]
    assert [m for m in messages if not m.startswith("═")] == ["a", "b", "c"]
    assert any(i.is_break for i in viewer._model.visible_items())      # a marker shows the gap
    assert link.state == cs.LIVE and link.attempts == 0


def test_user_stop_cancels_a_pending_reconnection(env):
    win, viewer, made, _, _ = env
    made[0].error.emit("reset")
    link = _link(win, viewer)
    gen = link.generation
    win._stop_viewer(viewer)
    assert link.state == cs.STOPPED and link.generation != gen
    win._reconnect(viewer, gen)                       # the old timer fires: nothing happens
    assert len(made) == 1


def test_gives_up_after_the_last_attempt_and_then_tells_the_user(env):
    win, viewer, made, dialogs, _ = env
    link = _link(win, viewer)
    for i in range(len(cs.RECONNECT_DELAYS)):
        made[-1].error.emit(f"down {i}")
        assert link.state == cs.RECONNECTING and not dialogs
        win._reconnect(viewer, link.generation)
    made[-1].error.emit("still down")
    assert link.state == cs.FAILED and dialogs == ["still down"]
    assert win._top_tabs.tabToolTip(0) == "Connection lost"


def test_turning_auto_reconnect_off_restores_the_old_behaviour(env):
    import config_store
    win, viewer, made, dialogs, _ = env
    win._act_reconnect.setChecked(False)
    assert config_store.get_pref("auto_reconnect", True) is False
    made[0].error.emit("reset")
    assert _link(win, viewer).state == cs.FAILED and dialogs == ["reset"]


def test_countdown_is_cancelled_when_auto_reconnect_is_turned_off(env):
    win, viewer, made, _, _ = env
    made[0].error.emit("reset")
    assert _link(win, viewer).state == cs.RECONNECTING
    win._act_reconnect.setChecked(False)
    assert _link(win, viewer).state == cs.FAILED
    win._reconnect(viewer, 0)
    assert len(made) == 1


def test_a_stream_that_ends_quietly_is_shown_as_ended(env):
    win, viewer, made, dialogs, _ = env
    made[0].new_lines.emit([(1000, "x")])
    made[0].stop()                       # the thread leaves its run(), nobody asked for it
    made[0].wait(3000)
    QApplication.processEvents()
    assert _link(win, viewer).state == cs.ENDED and not dialogs


def test_resync_filter_ignores_only_lines_already_shown():
    import ui
    v = ui.LogViewer(source_type="file")
    v.append_events([(1000, "a"), (2000, "b")])
    v.begin_resync()
    v.append_events([(2000, "b"), (2500, "new")])
    v.flush_pending()
    assert [i.message for i in v._model.visible_items()] == ["a", "b", "new"]
    v.end_resync()
    v.append_events([(2000, "b")])
    v.flush_pending()
    assert v._model.visible_count() == 4          # no longer filtered


def test_with_status_dot_changes_only_a_corner():
    from PyQt6.QtGui import QColor, QPixmap

    import ui_theme
    base = QPixmap(14, 14)
    base.fill(QColor("#000000"))
    out = ui_theme.with_status_dot(base, "#5fc48a")
    img, ref = out.toImage(), base.toImage()
    assert img.pixelColor(1, 1) == ref.pixelColor(1, 1)
    assert img.pixelColor(11, 11) != ref.pixelColor(11, 11)
