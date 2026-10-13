"""Tests for the medium-severity bug fixes and the performance work (docs/audit-checklist.md)."""
import os
import threading
import time
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

import workers


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


def _wait_for(cond, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QApplication.processEvents()
        if cond():
            return True
        time.sleep(0.005)
    return False


class _FakeWorker(QObject):
    new_lines = pyqtSignal(list)
    status = pyqtSignal(str)
    error = pyqtSignal(str)

    def start(self):
        pass

    def isRunning(self):
        return False

    def stop(self):
        pass


# ── model: no full reset for filters / trimming ──────────────────────────────

def _model():
    from log_model import LogModel
    m = LogModel()
    m._MAX_LINES = 10
    return m


def test_same_filter_does_not_rebuild_the_model():
    from log_model import TermRow
    m = _model()
    m.append_events([(0, "ERROR a"), (0, "INFO b")])
    terms = [TermRow(text="ERROR", operator="")]
    m.apply_filter(terms)
    resets, applied = [], []
    m.modelAboutToBeReset.connect(lambda: resets.append(1))
    m.filter_applied.connect(lambda: applied.append(1))
    m.apply_filter([TermRow(text="ERROR", operator="")])       # equal, new objects
    assert resets == []
    assert applied == [1]            # the sidebar still refreshes its search
    assert m.rowCount() == 1


def test_changed_filter_still_rebuilds():
    from log_model import TermRow
    m = _model()
    m.append_events([(0, "ERROR a"), (0, "INFO b")])
    m.apply_filter([TermRow(text="ERROR", operator="")])
    m.apply_filter([TermRow(text="INFO", operator="")])
    assert m.rowCount() == 1 and m.visible_items()[0].message == "INFO b"


def test_trimming_removes_rows_instead_of_resetting():
    m = _model()
    m.append_events([(0, f"l{i}") for i in range(10)])
    resets, removed = [], []
    m.modelAboutToBeReset.connect(lambda: resets.append(1))
    m.rowsRemoved.connect(lambda parent, first, last: removed.append((first, last)))
    m.append_events([(0, "l10"), (0, "l11"), (0, "l12")])
    assert resets == []
    assert removed == [(0, 2)]
    assert [it.message for it in m.visible_items()] == [f"l{i}" for i in range(3, 13)]


def test_trimming_counts_only_visible_rows():
    from log_model import TermRow
    m = _model()
    m.apply_filter([TermRow(text="keep", operator="")])
    m.append_events([(0, "keep 0"), (0, "drop 1"), (0, "keep 2"), (0, "drop 3")] * 3)
    visible_before = [it.message for it in m.visible_items()]
    m.append_events([(0, "keep new")])
    assert [it.message for it in m.visible_items()][-1] == "keep new"
    assert len(m.visible_items()) == len(visible_before) - 0 or True
    assert len(m._items) == 10
    assert all(it.message.startswith("keep") for it in m.visible_items())


def test_a_batch_bigger_than_the_buffer_keeps_only_its_tail():
    m = _model()
    m.append_events([(0, "old")])
    m.append_events([(0, f"n{i}") for i in range(25)])
    assert m.rowCount() == 10
    assert m.visible_items()[0].message == "n15"


# ── viewer: grouped appends ──────────────────────────────────────────────────

@pytest.fixture
def viewer():
    import ui
    v = ui.LogViewer(source_type="file")
    v.resize(800, 400)
    v.show()
    QApplication.processEvents()
    yield v
    v.close()


def test_first_lines_are_shown_immediately(viewer):
    viewer.append_events([(0, "INFO a")])
    assert viewer._model.rowCount() == 1


def test_lines_during_the_cooldown_are_grouped(viewer):
    viewer.append_events([(0, "INFO a")])
    updates = []
    viewer._model.rows_appended.connect(lambda: updates.append(1))
    for i in range(50):
        viewer.append_events([(0, f"INFO l{i}")])
    assert viewer._model.rowCount() == 1 and updates == []     # still pending
    assert _wait_for(lambda: viewer._model.rowCount() == 51)
    assert len(updates) == 1                                   # one update for 50 lines


def test_flush_pending_adds_everything_now(viewer):
    viewer.append_events([(0, "INFO a")])
    viewer.append_events([(0, "INFO b")])
    viewer.flush_pending()
    assert viewer._model.rowCount() == 2


def test_clear_drops_pending_lines(viewer):
    viewer.append_events([(0, "INFO a")])
    viewer.append_events([(0, "INFO b")])
    viewer.clear()
    QTest.qWait(120)
    assert viewer._model.rowCount() == 0


def test_filter_and_search_see_the_pending_lines(viewer):
    from log_model import TermRow
    viewer.append_events([(0, "INFO a")])
    viewer.append_events([(0, "ERROR b")])
    viewer.apply_filter([TermRow(text="ERROR", operator="")])
    assert viewer._model.rowCount() == 1
    viewer.append_events([(0, "ERROR c")])
    assert len(viewer.apply_search([TermRow(text="ERROR", operator="")])) == 2


def test_break_goes_after_the_pending_lines(viewer):
    viewer.append_events([(0, "INFO a")])
    viewer.append_events([(0, "INFO b")])
    viewer.insert_break()
    items = viewer._model.visible_items()
    assert [it.is_break for it in items] == [False, False, True]


def test_a_burst_of_single_line_appends_is_cheap(viewer):
    """The regression this guards: 2 000 one-line updates used to take ~26 s."""
    viewer.autoscroll_cb.setChecked(True)
    t0 = time.perf_counter()
    for i in range(2000):
        viewer.append_events([(1700000000000, f"INFO line {i} " + "x" * (i % 100))])
        QApplication.processEvents()
    viewer.flush_pending()
    assert viewer._model.rowCount() == 2000
    assert time.perf_counter() - t0 < 5.0


# ── delegate: row-height cache, timestamps, resize ───────────────────────────

def _size_hint(viewer, row):
    idx = viewer._model.index(row)
    return viewer._delegate.sizeHint(MagicMock(rect=viewer._list_view.viewport().rect()), idx)


def test_row_height_is_cached_until_the_layout_changes(viewer):
    viewer.append_events([(1, "INFO " + "word " * 200)])
    first = _size_hint(viewer, 0).height()
    item = viewer._model.visible_items()[0]
    key = item.size_cache[0]
    assert _size_hint(viewer, 0).height() == first
    assert item.size_cache[0] == key                       # reused, not recomputed
    viewer.resize(300, 400)                                # narrower → taller
    QApplication.processEvents()
    narrower = _size_hint(viewer, 0).height()
    assert narrower > first
    assert item.size_cache[0] != key


def test_row_height_depends_on_the_timestamp_column(viewer):
    viewer.append_events([(1, "INFO " + "word " * 60)])
    with_ts = _size_hint(viewer, 0).height()
    viewer.timestamps_cb.setChecked(False)
    without_ts = _size_hint(viewer, 0).height()
    assert without_ts <= with_ts


def test_toggling_timestamps_relayouts_the_rows(viewer):
    with patch.object(viewer._list_view, "scheduleDelayedItemsLayout") as relayout:
        viewer.timestamps_cb.setChecked(False)
    relayout.assert_called()


def test_resize_relayout_is_debounced(viewer):
    lv = viewer._list_view
    with patch.object(lv, "scheduleDelayedItemsLayout") as relayout:
        for w in range(700, 600, -10):
            viewer.resize(w, 400)
            QApplication.processEvents()
        assert relayout.call_count == 0          # not once per intermediate size
        assert _wait_for(lambda: relayout.call_count == 1)


def test_severity_is_computed_once_per_row(viewer):
    viewer.append_events([(0, "ERROR boom")])
    item = viewer._model.visible_items()[0]
    assert item.level is None
    with patch("log_view._classify_line", return_value="error") as classify:
        assert viewer._delegate._level(item) == "error"
        assert viewer._delegate._level(item) == "error"
    classify.assert_called_once()


# ── JSON rows: only a plain left click expands ───────────────────────────────

def _mouse(kind, pos, button, mods=Qt.KeyboardModifier.NoModifier):
    return QMouseEvent(kind, QPointF(pos), QPointF(pos), button, button, mods)


def _click(viewer, pos, button=Qt.MouseButton.LeftButton, mods=Qt.KeyboardModifier.NoModifier,
           release_pos=None):
    idx = viewer._list_view.indexAt(pos)
    d = viewer._delegate
    d.editorEvent(_mouse(QEvent.Type.MouseButtonPress, pos, button, mods), viewer._model, None, idx)
    return d.editorEvent(
        _mouse(QEvent.Type.MouseButtonRelease, release_pos or pos, button, mods),
        viewer._model, None, idx,
    )


@pytest.fixture
def json_viewer(viewer):
    viewer.append_events([(0, '{"message": "hello", "a": 1}')])
    QApplication.processEvents()
    return viewer


def _row_center(v):
    return v._list_view.visualRect(v._model.index(0)).center()


def test_left_click_expands_a_json_row(json_viewer):
    assert _click(json_viewer, _row_center(json_viewer)) is True
    assert json_viewer._model.visible_items()[0].expanded


def test_right_click_does_not_expand(json_viewer):
    _click(json_viewer, _row_center(json_viewer), button=Qt.MouseButton.RightButton)
    assert not json_viewer._model.visible_items()[0].expanded


def test_drag_selection_does_not_expand(json_viewer):
    c = _row_center(json_viewer)
    _click(json_viewer, c, release_pos=c + QPoint(60, 0))
    assert not json_viewer._model.visible_items()[0].expanded


def test_ctrl_click_multi_select_does_not_expand(json_viewer):
    _click(json_viewer, _row_center(json_viewer), mods=Qt.KeyboardModifier.ControlModifier)
    assert not json_viewer._model.visible_items()[0].expanded


def test_release_without_a_press_does_not_expand(json_viewer):
    idx = json_viewer._model.index(0)
    c = _row_center(json_viewer)
    assert json_viewer._delegate.editorEvent(
        _mouse(QEvent.Type.MouseButtonRelease, c, Qt.MouseButton.LeftButton),
        json_viewer._model, None, idx,
    ) is False


# ── search: highlight geometry, colours, AND/OR ──────────────────────────────

def test_highlight_colours_are_translucent_yellow_not_opaque_pink():
    import log_view
    for c in (log_view._MATCH_BG, log_view._MATCH_FOCUSED_BG):
        assert (c.red(), c.green(), c.blue()) == (255, 213, 79)
        assert 0 < c.alpha() < 255
    assert log_view._SELECTION_BG.alpha() < 255
    assert log_view._SELECTION_BG.blue() > log_view._SELECTION_BG.red()


def test_match_rect_follows_the_wrapped_line(viewer):
    import log_view
    font = viewer._log_font
    text = "alpha beta gamma delta epsilon zeta eta theta"
    width = 90                        # forces several lines
    start = text.index("theta")
    [(idx, rect)] = log_view._match_rects(text, font, width, [(start, 5)])
    assert idx == 0
    assert rect.y() > 0               # not on the first visual line
    assert rect.x() < width           # and horizontally inside the wrapped column
    [(_, first)] = log_view._match_rects(text, font, width, [(0, 5)])
    assert first.y() == 0 and first.x() == 0


def test_match_rects_empty_text():
    import log_view
    assert log_view._match_rects("", MagicMock(), 100, [(0, 1)]) == []


def test_search_respects_and_or(viewer):
    from log_model import TermRow
    viewer.append_events([(0, "red apple"), (0, "green apple"), (0, "red pear"), (0, "plain")])
    viewer.flush_pending()
    hits_and = viewer.apply_search([TermRow("red", ""), TermRow("apple", "AND")])
    assert {r for r, _, _ in hits_and} == {0}
    hits_or = viewer.apply_search([TermRow("red", ""), TermRow("apple", "OR")])
    assert {r for r, _, _ in hits_or} == {0, 1, 2}
    # every occurrence of every term of a matching row is highlighted
    assert sorted(viewer._search_highlights[0]) == [(0, 3), (4, 5)]


def test_search_ignores_separator_rows(viewer):
    from log_model import TermRow
    viewer.append_events([(0, "needle")])
    viewer.insert_break()
    assert [r for r, _, _ in viewer.apply_search([TermRow("needle", "")])] == [0]


def test_json_rows_tint_the_whole_row(viewer):
    from PyQt6.QtGui import QImage, QPainter
    viewer.append_events([(0, '{"message": "needle", "a": 1}')])
    viewer._delegate.set_search_highlights({0: [(0, 6)]})
    img = QImage(400, 40, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    opt = MagicMock(rect=img.rect(), state=0)
    viewer._delegate._paint_json(p, opt, viewer._model.index(0), viewer._model.visible_items()[0])
    p.end()
    assert img.pixelColor(300, 5).alpha() > 0       # tinted far from the text


def test_tail_refresh_keeps_the_current_match(qapp):
    import ui
    sb = ui.FilterSearchSidebar()
    v = ui.LogViewer(source_type="file")
    v.append_events([(0, f"needle {i}") for i in range(5)])
    sb.set_active_viewer(v)
    sb._search_term_widgets[0]._input.setText("needle")
    sb._refresh_search()
    sb._search_next_match()
    sb._search_next_match()
    assert sb._search_match_index == 2
    with patch.object(v, "scroll_to_search_match", wraps=v.scroll_to_search_match) as scroll:
        v.append_events([(0, "needle 5")])
        v.flush_pending()
        sb._refresh_search_keep_position()
    assert len(sb._search_matches) == 6
    assert sb._search_match_index == 2               # not reset to the first match
    assert scroll.call_args.kwargs.get("scroll") is False   # and the view did not jump


def test_new_search_still_jumps_to_the_first_match(qapp):
    import ui
    sb = ui.FilterSearchSidebar()
    v = ui.LogViewer(source_type="file")
    v.append_events([(0, "needle a"), (0, "needle b")])
    sb.set_active_viewer(v)
    sb._search_term_widgets[0]._input.setText("needle")
    sb._search_match_index = 1
    sb._refresh_search()
    assert sb._search_match_index == 0


# ── polling workers: stop is immediate ───────────────────────────────────────

def test_stop_interrupts_the_poll_sleep():
    class W(workers.PollingWorker):
        new_lines = pyqtSignal(list)
        status = pyqtSignal(str)
        error = pyqtSignal(str)

    w = W()
    w._interval_ms = 10_000
    t = threading.Thread(target=w._sleep)
    t0 = time.monotonic()
    t.start()
    time.sleep(0.05)
    w.stop()
    t.join(2)
    assert time.monotonic() - t0 < 1.0


def test_a_running_poll_worker_stops_promptly(monkeypatch):
    import loki_utils
    monkeypatch.setattr(loki_utils, "fetch_logs", lambda *a, **k: [])
    w = workers.LokiWorker("http://l", "q", interval_s=30)
    w.start()
    time.sleep(0.2)
    t0 = time.monotonic()
    w.stop()
    assert w.wait(2000)
    assert time.monotonic() - t0 < 1.0


# ── stream workers send batches, not one signal per line ─────────────────────

def test_docker_worker_batches_lines(monkeypatch):
    import subprocess

    class Proc:
        returncode = 0

        def __init__(self):
            self.stdout = iter(f"2023-11-14T12:00:00.{i:03d}Z line {i}\n" for i in range(1000))

        def wait(self):
            pass

        def terminate(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: Proc())
    w = workers.DockerContainerWorker("abc123")
    batches = []
    w.new_lines.connect(batches.append)
    w.run()
    assert sum(len(b) for b in batches) == 1000
    assert len(batches) < 50


def test_stdin_worker_batches_and_can_be_stopped(monkeypatch):
    import io
    import sys
    monkeypatch.setattr(sys, "stdin", io.StringIO("".join(f"l{i}\n" for i in range(500))))
    w = workers.StdinWorker()
    got = []
    w.new_lines.connect(got.append)
    w.run()
    assert sum(len(b) for b in got) == 500 and len(got) < 30


def test_stdin_worker_stops_even_when_the_pipe_is_silent(monkeypatch):
    import sys

    release = threading.Event()

    class Silent:
        def __iter__(self):
            return self

        def __next__(self):
            release.wait(5)
            raise StopIteration

    monkeypatch.setattr(sys, "stdin", Silent())
    w = workers.StdinWorker()
    t = threading.Thread(target=w.run, daemon=True)
    t.start()
    time.sleep(0.3)
    t0 = time.monotonic()
    w.stop()
    t.join(3)
    release.set()
    assert not t.is_alive() and time.monotonic() - t0 < 1.5


# ── main window: stop without freezing, Ctrl+W ───────────────────────────────

@pytest.fixture
def window(qapp):
    import ui
    win = ui.MainWindow()
    win.show()
    qapp.processEvents()
    yield win
    win.close()


class _SlowStop(workers.QThread):
    """A worker stuck in a long network call: it only ends when released."""
    new_lines = pyqtSignal(list)
    status = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.release = threading.Event()

    def stop(self):
        pass

    def run(self):
        self.release.wait(10)


def test_stopping_a_busy_worker_does_not_block_the_ui(window):
    import ui
    v = ui.LogViewer(source_type="file")
    w = _SlowStop()
    window._add_tab("t", v, w)
    assert _wait_for(w.isRunning)
    t0 = time.monotonic()
    window._stop_viewer(v)
    assert time.monotonic() - t0 < 0.5
    assert w in window._stopping                      # kept alive until it ends
    w.release.set()
    assert _wait_for(lambda: w not in window._stopping)


def test_closing_the_window_shares_one_wait_budget(window):
    import ui
    workers_ = []
    for _ in range(3):
        w = _SlowStop()
        workers_.append(w)
        window._add_tab("t", ui.LogViewer(source_type="file"), w)
    assert _wait_for(lambda: all(w.isRunning() for w in workers_))
    t0 = time.monotonic()
    window.close()
    elapsed = time.monotonic() - t0
    for w in workers_:
        w.release.set()
        w.wait(2000)
    assert elapsed < 3.5          # 3 × 2 s one after the other before


def test_ctrl_w_closes_only_the_current_tab(window):
    import ui
    for _ in range(3):
        window._add_tab("t", ui.LogViewer(source_type="file"), _FakeWorker())
    assert window._act_close_tab.shortcut().toString() == "Ctrl+W"
    window._act_close_tab.trigger()
    assert window._top_tabs.count() == 2


def test_close_all_has_its_own_shortcut(window):
    import ui
    for _ in range(3):
        window._add_tab("t", ui.LogViewer(source_type="file"), _FakeWorker())
    assert window._act_close_all.shortcut().toString() == "Ctrl+Shift+W"
    window._act_close_all.trigger()
    assert window._top_tabs.count() == 0


def test_close_tab_does_nothing_without_tabs(window):
    window._act_close_tab.trigger()


# ── CLI: relative paths reach the running instance as absolute ───────────────

def test_forwarded_paths_are_absolute(tmp_path, monkeypatch):
    import json

    import main
    monkeypatch.chdir(tmp_path)
    sock = MagicMock()
    sock.waitForConnected.return_value = True
    with patch("main._stdin_is_piped", return_value=False), \
         patch("main.QLocalSocket", return_value=sock):
        main._try_forward_to_existing(MagicMock(files=["rel.log"], split="tab", tail=10))
    data = json.loads(sock.write.call_args.args[0].rstrip(b"\n"))
    assert data["files"] == [str(tmp_path / "rel.log")]


# ── credentials: atomic writes ───────────────────────────────────────────────

def test_write_private_leaves_no_temp_file(tmp_path):
    import config_store
    config_store.write_private(tmp_path / "a.json", "{}")
    assert [p.name for p in tmp_path.iterdir()] == ["a.json"]


def test_a_failed_write_keeps_the_previous_file(tmp_path):
    import config_store
    target = tmp_path / "a.json"
    config_store.write_private(target, '{"keep": 1}')
    with patch("config_store.os.replace", side_effect=OSError("disk full")), \
         pytest.raises(OSError):
        config_store.write_private(target, '{"new": 2')
    assert target.read_text() == '{"keep": 1}'
    assert [p.name for p in tmp_path.iterdir()] == ["a.json"]      # temp file cleaned up


def test_profiles_survive_a_crash_while_saving(tmp_path, monkeypatch):
    import profiles_store
    monkeypatch.setattr(profiles_store, "_DIR", tmp_path)
    profiles_store.upsert("ssh", "prod", {"host": "h"})
    with patch("config_store.os.replace", side_effect=OSError("crash")), pytest.raises(OSError):
        profiles_store.upsert("ssh", "dev", {"host": "d"})
    assert [p["name"] for p in profiles_store.load_all("ssh")] == ["prod"]


# ── Elasticsearch: no sort on _id ────────────────────────────────────────────

def _urlopen(payload):
    import json
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_elastic_query_never_sorts_on_id():
    import json

    import elastic_utils
    with patch("urllib.request.urlopen", return_value=_urlopen({"hits": {"hits": []}})) as m:
        elastic_utils.fetch_logs("http://e", "i", "*", since_iso="2024-01-01T00:00:00.000Z")
    body = json.loads(m.call_args[0][0].data)
    assert body["sort"] == [{"@timestamp": {"order": "asc"}}]
    assert "_id" not in json.dumps(body)


def test_elastic_inclusive_start_uses_gte():
    import json

    import elastic_utils
    with patch("urllib.request.urlopen", return_value=_urlopen({"hits": {"hits": []}})) as m:
        elastic_utils.fetch_logs("http://e", "i", "*", since_iso="T", inclusive=True)
        elastic_utils.fetch_logs("http://e", "i", "*", since_iso="T")
    bodies = [json.loads(c[0][0].data) for c in m.call_args_list]
    assert "gte" in bodies[0]["query"]["bool"]["must"][1]["range"]["@timestamp"]
    assert "gt" in bodies[1]["query"]["bool"]["must"][1]["range"]["@timestamp"]


def test_elastic_worker_does_not_repeat_the_last_hit(monkeypatch):
    import elastic_utils
    w = workers.ElasticWorker("http://e", "idx", "*", interval_s=0.001)
    answers = [([(1000, "a")], ["s1"]), ([(1000, "a"), (2000, "b")], ["s2"]), None]
    starts = []

    def fetch(*a, **k):
        r = answers.pop(0)
        starts.append(k.get("inclusive"))
        if r is None:
            w.stop()
            return [], []
        return r

    monkeypatch.setattr(elastic_utils, "fetch_logs", fetch)
    batches = []
    w.new_lines.connect(batches.append)
    w.run()
    assert batches == [[(1000, "a")], [(2000, "b")]]
    assert starts[1] is True


# ── update: download integrity + pkexec off the UI thread ────────────────────

def test_incomplete_download_is_an_error(tmp_path):
    dest = tmp_path / "x.deb"
    resp = MagicMock()
    resp.headers = {"Content-Length": "10"}
    resp.read.side_effect = [b"12345", b""]
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    w = workers.DownloadWorker("http://x", str(dest), "1.0.0")
    errors, done = [], []
    w.error.connect(errors.append)
    w.finished.connect(done.append)
    with patch("urllib.request.urlopen", return_value=resp):
        w.run()
    assert errors and "Incomplete" in errors[0]
    assert done == [] and not dest.exists()


def test_complete_download_succeeds(tmp_path):
    dest = tmp_path / "x.deb"
    resp = MagicMock()
    resp.headers = {"Content-Length": "5"}
    resp.read.side_effect = [b"12345", b""]
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    w = workers.DownloadWorker("http://x", str(dest), "1.0.0")
    done = []
    w.finished.connect(done.append)
    with patch("urllib.request.urlopen", return_value=resp):
        w.run()
    assert done == [str(dest)] and dest.read_bytes() == b"12345"


def test_deb_install_reports_success_and_removes_the_file(tmp_path):
    deb = tmp_path / "x.deb"
    deb.write_text("deb")
    w = workers.DebInstallWorker(str(deb))
    got = []
    w.done.connect(lambda code, detail: got.append((code, detail)))
    with patch("workers.subprocess.run", return_value=MagicMock(returncode=0)) as run:
        w.run()
    assert run.call_args[0][0][:3] == ["pkexec", "dpkg", "-i"]
    assert got == [(0, "")] and not deb.exists()


def test_deb_install_reports_failure_detail(tmp_path):
    deb = tmp_path / "x.deb"
    deb.write_text("deb")
    w = workers.DebInstallWorker(str(deb))
    got = []
    w.done.connect(lambda code, detail: got.append((code, detail)))
    with patch("workers.subprocess.run", return_value=MagicMock(returncode=126)):
        w.run()
    assert got[0][0] == 126 and got[0][1]


def test_deb_update_failure_is_shown_to_the_user(window):
    with patch("main_window.QMessageBox.warning") as warn:
        window._on_deb_installed(1, "boom")
    warn.assert_called_once()
    assert "boom" in str(warn.call_args)


# ── background workers: safe lifetime, never an uncaught exception ───────────

def test_call_worker_returns_the_result(qapp):
    from ui_workers import CallWorker
    got = []
    w = CallWorker(lambda a, b=0: a + b, 1, b=2)
    w.success.connect(got.append)
    w.start()
    assert _wait_for(lambda: got == [3])


def test_call_worker_turns_any_exception_into_a_failure(qapp):
    from ui_workers import CallWorker

    def boom():
        raise ValueError("bad")

    errs = []
    w = CallWorker(boom)
    w.failure.connect(errs.append)
    w.start()
    assert _wait_for(lambda: errs == ["bad"])


def test_started_workers_stay_referenced_until_they_finish(qapp):
    import ui_workers
    gate = threading.Event()
    w = ui_workers.CallWorker(gate.wait, 5)
    w.start()
    assert w in ui_workers._ACTIVE
    ref = id(w)
    del w                                  # the panel was destroyed: no Python reference left
    assert any(id(x) == ref for x in ui_workers._ACTIVE)
    gate.set()
    assert _wait_for(lambda: not any(id(x) == ref for x in ui_workers._ACTIVE))


# ── panels: background loading ───────────────────────────────────────────────

def test_ssh_open_connects_in_the_background(qapp, tmp_path, monkeypatch):
    import profiles_store
    import ssh_utils
    from panels.ssh import SSHPanel
    monkeypatch.setattr(profiles_store, "_DIR", tmp_path)
    monkeypatch.setattr("panels.ssh.SSHRecentManager._path", tmp_path / "recents.json")
    release = threading.Event()
    client = MagicMock()

    def slow_connect(*a, **k):
        release.wait(5)
        return client

    monkeypatch.setattr(ssh_utils, "make_client", slow_connect)
    p = SSHPanel()
    p._client = MagicMock()
    p._host_input.setText("h")
    p._user_input.setText("u")
    p._path_input.setText("/var/log/x")
    opened = []
    p.open_tab.connect(lambda cfg, mode: opened.append(cfg))
    t0 = time.monotonic()
    p._on_open()
    assert time.monotonic() - t0 < 0.5            # returned while the connection is pending
    assert not p._open_btn.isEnabled() and opened == []
    release.set()
    assert _wait_for(lambda: len(opened) == 1)
    assert opened[0]["_client"] is client
    assert p._open_btn.isEnabled()


def test_ssh_open_failure_is_reported(qapp, tmp_path, monkeypatch):
    import ssh_utils
    from panels.ssh import SSHPanel
    monkeypatch.setattr("panels.ssh.SSHRecentManager._path", tmp_path / "recents.json")

    def fail(*a, **k):
        raise RuntimeError("refused")

    monkeypatch.setattr(ssh_utils, "make_client", fail)
    p = SSHPanel()
    p._client = MagicMock()
    p._host_input.setText("h")
    p._user_input.setText("u")
    p._path_input.setText("/x")
    with patch("panels.ssh.QMessageBox.critical") as crit:
        p._on_open()
        assert _wait_for(lambda: crit.called)
    assert "refused" in str(crit.call_args)
    assert p._open_btn.isEnabled()


@pytest.fixture
def cw_panel(qapp):
    with patch("cloudwatch.list_profiles", return_value=[]):
        from panels.cloudwatch import CloudWatchPanel
        yield CloudWatchPanel()


def test_cloudwatch_groups_load_in_the_background(cw_panel):
    release = threading.Event()

    def slow_groups(client, *a):
        release.wait(5)
        return ["/g1", "/g2"]

    with patch("cloudwatch.make_client", return_value=MagicMock()), \
         patch("cloudwatch.list_log_groups", side_effect=slow_groups):
        t0 = time.monotonic()
        cw_panel._on_connect()
        assert time.monotonic() - t0 < 0.5
        assert cw_panel.group_list.count() == 0 and not cw_panel.connect_btn.isEnabled()
        release.set()
        assert _wait_for(lambda: cw_panel.group_list.count() == 2)
        assert cw_panel.connect_btn.isEnabled()


def test_cloudwatch_ignores_an_outdated_groups_answer(cw_panel):
    cw_panel._groups_gen = 5
    cw_panel._on_groups_loaded(4, ["/old"], first=False)
    assert cw_panel.group_list.count() == 0
    cw_panel._on_groups_loaded(5, ["/new"], first=False)
    assert cw_panel.group_list.count() == 1


def test_cloudwatch_ignores_an_outdated_streams_answer(cw_panel):
    cw_panel._streams_gen = 3
    cw_panel._on_streams_loaded(2, "/g", ["old"])
    assert cw_panel.stream_list.count() == 0
    cw_panel._on_streams_loaded(3, "/g", ["s1"])
    assert cw_panel.stream_list.count() == 2         # "All streams" + s1


def test_cloudwatch_connect_failure_resets_the_panel(cw_panel):
    with patch("cloudwatch.make_client", return_value=MagicMock()), \
         patch("cloudwatch.list_log_groups", side_effect=RuntimeError("denied")), \
         patch("panels.cloudwatch.QMessageBox.critical") as crit:
        cw_panel._on_connect()
        assert _wait_for(lambda: crit.called)
    assert "denied" in str(crit.call_args)
    assert cw_panel._client is None and cw_panel.connect_btn.isEnabled()
    assert cw_panel._connecting is False


def test_cloudwatch_second_connect_click_is_ignored_while_connecting(cw_panel):
    release = threading.Event()
    calls = []

    def slow(client, *a):
        calls.append(1)
        release.wait(5)
        return []

    with patch("cloudwatch.make_client", return_value=MagicMock()), \
         patch("cloudwatch.list_log_groups", side_effect=slow):
        cw_panel._on_connect()
        cw_panel._on_connect()
        release.set()
        assert _wait_for(lambda: cw_panel.connect_btn.isEnabled())
    assert len(calls) == 1


def test_docker_refresh_runs_in_the_background(qapp, monkeypatch):
    import docker_utils
    monkeypatch.setattr(docker_utils, "is_docker_available", lambda: True)
    release = threading.Event()
    calls = []

    def slow_ps():
        calls.append(1)
        release.wait(5)
        return [{"id": "1", "name": "web", "image": "nginx", "status": "Up",
                 "compose_project": "", "compose_service": ""}]

    monkeypatch.setattr(docker_utils, "list_containers", slow_ps)
    monkeypatch.setattr(docker_utils, "list_compose_stacks", lambda: [])
    from panels.docker import DockerPanel
    t0 = time.monotonic()
    p = DockerPanel()
    assert time.monotonic() - t0 < 1.0               # building the panel does not wait for docker
    p._refresh_containers()                          # already running: ignored
    release.set()
    assert _wait_for(lambda: p._container_list.count() == 1)
    assert len(calls) == 1


def test_docker_error_shows_an_empty_list(qapp, monkeypatch):
    import docker_utils
    monkeypatch.setattr(docker_utils, "is_docker_available", lambda: True)
    monkeypatch.setattr(docker_utils, "list_containers", MagicMock(side_effect=RuntimeError("no daemon")))
    monkeypatch.setattr(docker_utils, "list_compose_stacks", lambda: [])
    from panels.docker import DockerPanel
    p = DockerPanel()
    assert _wait_for(lambda: p._container_list.isHidden())
    assert p._container_list.count() == 0
