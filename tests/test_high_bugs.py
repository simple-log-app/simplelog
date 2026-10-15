"""Regression tests for the high-severity bugs of the audit (docs/audit-checklist.md)."""
import json
import os
import threading
import time
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from simplelog.sources import workers
from simplelog.sources.worker_base import _batched


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


# ── 2. duplicates: _Dedup ─────────────────────────────────────────────────────

def test_dedup_first_batch_is_returned_whole():
    d = workers.Dedup()
    assert d.new([(1, "a"), (2, "b")]) == [(1, "a"), (2, "b")]


def test_dedup_drops_the_boundary_event_that_comes_back():
    d = workers.Dedup()
    d.new([(1, "a"), (2, "b")])
    assert d.new([(2, "b"), (3, "c")]) == [(3, "c")]


def test_dedup_keeps_a_different_event_in_the_same_millisecond():
    d = workers.Dedup()
    d.new([(2, "b")])
    assert d.new([(2, "b"), (2, "b2")]) == [(2, "b2")]


def test_dedup_window_absorbs_truncated_timestamps():
    d = workers.Dedup(window_ms=1000)
    d.new([(5200, "x"), (5900, "y")])
    # the next query restarts at second 5 → x and y are returned again
    assert d.new([(5200, "x"), (5900, "y"), (6100, "z")]) == [(6100, "z")]


def test_dedup_ignores_events_older_than_the_window():
    d = workers.Dedup(window_ms=1000)
    d.new([(10_000, "x")])
    assert d.new([(2_000, "old")]) == []


def test_dedup_forgets_old_events_to_stay_small():
    d = workers.Dedup(window_ms=10)
    for i in range(1000):
        d.new([(i * 100, f"m{i}")])
    assert len(d._seen) <= 2


# ── 4. transient errors do not stop the tail ──────────────────────────────────

class _Probe(workers.PollingWorker):
    new_lines = pyqtSignal(list)
    status = pyqtSignal(str)
    error = pyqtSignal(str)


def test_poll_failures_are_retried_then_reported():
    w = _Probe()
    errors, statuses = [], []
    w.error.connect(errors.append)
    w.status.connect(statuses.append)
    for i in range(workers.PollingWorker._MAX_FAILS - 1):
        assert w._poll_failed(RuntimeError("net")) is False
    assert errors == [] and len(statuses) == workers.PollingWorker._MAX_FAILS - 1
    assert w._poll_failed(RuntimeError("net")) is True
    assert errors == ["net"]


def test_a_successful_poll_resets_the_failure_count():
    w = _Probe()
    errors = []
    w.error.connect(errors.append)
    for _ in range(workers.PollingWorker._MAX_FAILS - 1):
        w._poll_failed(RuntimeError("net"))
    w._poll_ok()
    for _ in range(workers.PollingWorker._MAX_FAILS - 1):
        w._poll_failed(RuntimeError("net"))
    assert errors == []


def _run_polling(worker, polls):
    """Run worker.run() synchronously, stopping it after *polls* fetches."""
    batches, errors = [], []
    worker.new_lines.connect(batches.append)
    worker.error.connect(errors.append)
    worker.run()
    return batches, errors


def test_loki_survives_one_failed_poll(monkeypatch):
    from simplelog.sources import loki_utils
    calls = {"n": 0}
    w = workers.LokiWorker("http://l", "{a=\"b\"}", interval_s=0.001)

    def fetch(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return [(1000, "first")]
        if calls["n"] == 2:
            raise RuntimeError("blip")
        if calls["n"] == 3:
            return [(2000, "second")]
        w.stop()
        return []

    monkeypatch.setattr(loki_utils, "fetch_logs", fetch)
    batches, errors = _run_polling(w, 4)
    assert errors == []
    assert batches == [[(1000, "first")], [(2000, "second")]]


def test_worker_gives_up_after_repeated_failures(monkeypatch):
    from simplelog.sources import loki_utils
    calls = {"n": 0}

    def fetch(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return []
        raise RuntimeError("down")

    monkeypatch.setattr(loki_utils, "fetch_logs", fetch)
    w = workers.LokiWorker("http://l", "q", interval_s=0.001)
    _, errors = _run_polling(w, 0)
    assert errors == ["down"]
    assert calls["n"] == 1 + workers.PollingWorker._MAX_FAILS


# ── 2. duplicates through the workers ─────────────────────────────────────────

def test_loki_does_not_repeat_the_last_entry(monkeypatch):
    from simplelog.sources import loki_utils
    seen_starts = []
    w = workers.LokiWorker("http://l", "q", interval_s=0.001)
    answers = [[(5, "a"), (6, "b")], [(6, "b"), (7, "c")], None]

    def fetch(url, query, start_ns, end_ns, *a, **k):
        seen_starts.append(start_ns)
        r = answers.pop(0)
        if r is None:
            w.stop()
            return []
        return r

    monkeypatch.setattr(loki_utils, "fetch_logs", fetch)
    batches, _ = _run_polling(w, 3)
    assert batches == [[(5, "a"), (6, "b")], [(7, "c")]]
    assert seen_starts[1] == 6 * 1_000_000      # inclusive, millisecond precision


def test_flyio_does_not_replay_its_history(monkeypatch):
    from simplelog.sources import flyio_utils
    now = int(time.time() * 1000)
    hist = [(now - 2000, "a"), (now - 1000, "b")]
    answers = [hist, hist + [(now, "c")], None]
    w = workers.FlyioWorker("t", "app", interval_s=0.001, lookback_s=3600)

    def fetch(*a, **k):
        r = answers.pop(0)
        if r is None:
            w.stop()
            return []
        return r

    monkeypatch.setattr(flyio_utils, "fetch_logs_sse", fetch)
    batches, _ = _run_polling(w, 3)
    assert batches == [hist, [(now, "c")]]


def test_datadog_does_not_repeat_the_last_entry(monkeypatch):
    from simplelog.sources import datadog_utils
    w = workers.DatadogWorker("https://api.x", "*", "k", "a", interval_s=0.001)
    answers = [[(1000, "a")], [(1000, "a"), (2000, "b")], None]

    def fetch(*args, **kw):
        r = answers.pop(0)
        if r is None:
            w.stop()
            return []
        return r

    monkeypatch.setattr(datadog_utils, "fetch_logs", fetch)
    batches, _ = _run_polling(w, 3)
    assert batches == [[(1000, "a")], [(2000, "b")]]


# ── 3. history = newest events; no skipped entries ────────────────────────────

def _urlopen(payload):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_loki_latest_asks_for_the_newest_entries():
    from simplelog.sources import loki_utils
    with patch("urllib.request.urlopen", return_value=_urlopen({"data": {"result": []}})) as m:
        loki_utils.fetch_logs("http://l", "q", 0, 9, latest=True)
        loki_utils.fetch_logs("http://l", "q", 0, 9)
    urls = [c[0][0].full_url for c in m.call_args_list]
    assert "direction=backward" in urls[0] and "direction=forward" in urls[1]


def test_datadog_latest_sorts_newest_first_but_returns_oldest_first():
    from simplelog.sources import datadog_utils
    payload = {"data": [
        {"attributes": {"timestamp": "2023-11-14T12:00:02Z", "message": "new"}},
        {"attributes": {"timestamp": "2023-11-14T12:00:01Z", "message": "old"}},
    ]}
    with patch("urllib.request.urlopen", return_value=_urlopen(payload)) as m:
        res = datadog_utils.fetch_logs("https://x", "*", "f", "t", "k", "a", latest=True)
    assert json.loads(m.call_args[0][0].data)["sort"] == "-timestamp"
    assert [r[1] for r in res] == ["old", "new"]


def test_elastic_latest_returns_oldest_first_with_the_newest_sort_key():
    from simplelog.sources import elastic_utils
    hits = [
        {"_source": {"@timestamp": "2023-11-14T12:00:02Z", "message": "new"}, "sort": ["N"]},
        {"_source": {"@timestamp": "2023-11-14T12:00:01Z", "message": "old"}, "sort": ["O"]},
    ]
    with patch("urllib.request.urlopen",
               return_value=_urlopen({"hits": {"hits": hits}})) as m:
        events, last_sort = elastic_utils.fetch_logs("http://e", "i", "*", latest=True)
    body = json.loads(m.call_args[0][0].data)
    assert body["sort"][0]["@timestamp"]["order"] == "desc"
    assert [e[1] for e in events] == ["old", "new"]
    assert last_sort == ["N"]


def test_gcp_ascending_tail_does_not_skip_the_oldest_entries():
    import sys

    from simplelog.sources import gcp_utils
    fake = MagicMock()
    fake.ASCENDING, fake.DESCENDING = "ASC", "DESC"
    entries = []
    for i in range(3):
        e = MagicMock()
        e.timestamp.timestamp.return_value = i
        e.severity = None
        e.resource = None
        e.payload = f"m{i}"
        entries.append(e)
    client = MagicMock()
    client.list_entries.return_value = entries
    with patch.dict(sys.modules, {"google.cloud.logging": fake,
                                  "google.cloud": MagicMock(logging=fake)}):
        asc = gcp_utils.fetch_entries(client, "f", ascending=True)
        assert client.list_entries.call_args.kwargs["order_by"] == "ASC"
        desc = gcp_utils.fetch_entries(client, "f")
        assert client.list_entries.call_args.kwargs["order_by"] == "DESC"
    assert [m for _, m in asc] == ["m0", "m1", "m2"]
    assert [m for _, m in desc] == ["m2", "m1", "m0"]    # DESC results get re-ordered


# ── 1. Kubernetes: lines show up without waiting for 200 ──────────────────────

def test_batched_flushes_a_slow_stream_quickly():
    def slow():
        yield "a"
        yield "b"
        time.sleep(1.0)
        yield "c"

    t0 = time.monotonic()
    it = _batched(slow(), lambda: False, max_batch=200, max_wait=0.05)
    first = next(it)
    assert first == ["a", "b"]
    assert time.monotonic() - t0 < 0.6
    assert next(it) == ["c"]


def test_batched_caps_the_batch_size():
    out = list(_batched(iter(range(10)), lambda: False, max_batch=4, max_wait=5))
    assert [len(b) for b in out] == [4, 4, 2]
    assert sum(out, []) == list(range(10))


def test_batched_stops_when_asked():
    stop = {"v": False}

    def never_ending():
        while True:
            time.sleep(0.05)
            yield "x"

    it = _batched(never_ending(), lambda: stop["v"], max_wait=0.01)
    next(it)
    stop["v"] = True
    with pytest.raises(StopIteration):
        for _ in range(100):
            next(it)


def test_kubernetes_worker_emits_before_200_lines(monkeypatch):
    import subprocess

    from simplelog.sources import kubernetes_utils
    monkeypatch.setattr(kubernetes_utils, "build_logs_cmd", lambda *a, **k: ["x"])

    class Proc:
        def __init__(self):
            self.stdout = self._lines()
            self.stderr = MagicMock(read=lambda: "")

        def _lines(self):
            yield "2023-11-14T12:00:00Z one\n"
            yield "2023-11-14T12:00:01Z two\n"
            time.sleep(0.8)          # the pod goes quiet: nothing more for a while
            yield "2023-11-14T12:00:02Z three\n"

        def poll(self):
            return 0

        def terminate(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: Proc())
    w = workers.KubernetesWorker("pod", "ns")
    got = []
    hist = []
    w.new_lines.connect(lambda ev: got.append((time.monotonic(), ev)))
    w.history_done.connect(hist.append)
    t0 = time.monotonic()
    w.run()
    assert [m for _, ev in got for _, m in ev] == ["one", "two", "three"]
    assert got[0][0] - t0 < 0.5            # first batch arrived long before the stream ended
    assert hist == [2]


# ── 8. file tailing ───────────────────────────────────────────────────────────

def _tail(path, **kw):
    """Start a FileWorker in a thread; return (worker, thread, collected lines)."""
    w = workers.FileWorker(str(path), interval_ms=10, **kw)
    lines = []
    w.new_lines.connect(lambda ev: lines.extend(m for _, m in ev), Qt.ConnectionType.DirectConnection)
    t = threading.Thread(target=w.run, daemon=True)
    t.start()
    return w, t, lines


def _wait(cond, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def _stop(w, t):
    w.stop()
    t.join(3)


def test_file_tail_follows_appended_lines(tmp_path):
    p = tmp_path / "a.log"
    p.write_text("one\ntwo\n")
    w, t, lines = _tail(p)
    assert _wait(lambda: lines == ["one", "two"])
    with open(p, "a") as f:
        f.write("three\n")
    assert _wait(lambda: lines[-1:] == ["three"])
    _stop(w, t)


def test_file_tail_follows_a_truncated_file(tmp_path):
    p = tmp_path / "a.log"
    p.write_text("one\ntwo\nthree\n")
    w, t, lines = _tail(p)
    assert _wait(lambda: len(lines) == 3)
    p.write_text("fresh\n")              # same inode, smaller size
    assert _wait(lambda: lines[-1:] == ["fresh"])
    _stop(w, t)


def test_file_tail_follows_a_rotated_file(tmp_path):
    p = tmp_path / "a.log"
    p.write_text("old1\nold2\n")
    w, t, lines = _tail(p)
    assert _wait(lambda: len(lines) == 2)
    os.rename(p, tmp_path / "a.log.1")   # logrotate: the old file is moved away…
    p.write_text("new1\nnew2\nnew3\nnew4\n")   # …and a new one is created
    assert _wait(lambda: lines[2:] == ["new1", "new2", "new3", "new4"])
    _stop(w, t)


def test_file_tail_joins_a_line_written_in_two_parts(tmp_path):
    p = tmp_path / "a.log"
    p.write_text("start\n")
    w, t, lines = _tail(p)
    assert _wait(lambda: lines == ["start"])
    with open(p, "a") as f:
        f.write("hello ")
        f.flush()
        time.sleep(0.15)
        f.write("world\n")
    assert _wait(lambda: "hello world" in lines)
    assert "hello " not in lines and "world" not in lines
    _stop(w, t)


def test_file_tail_does_not_split_a_multibyte_character(tmp_path):
    p = tmp_path / "a.log"
    p.write_text("start\n")
    w, t, lines = _tail(p)
    assert _wait(lambda: lines == ["start"])
    data = "café ☕\n".encode()
    with open(p, "ab") as f:
        f.write(data[:5])                 # cuts the 'é' in half
        f.flush()
        time.sleep(0.15)
        f.write(data[5:])
    assert _wait(lambda: "café ☕" in lines)
    assert not any("�" in line for line in lines)
    _stop(w, t)


def test_file_tail_shows_an_unterminated_last_line_after_a_pause(tmp_path, monkeypatch):
    monkeypatch.setattr(workers.FileWorker, "_PARTIAL_LINE_MS", 100)
    p = tmp_path / "a.log"
    p.write_bytes(b"done\nno newline at the end")
    w, t, lines = _tail(p)
    assert _wait(lambda: lines == ["done", "no newline at the end"])
    _stop(w, t)


def test_file_tail_reports_a_missing_file(tmp_path):
    w = workers.FileWorker(str(tmp_path / "nope.log"))
    errors = []
    w.error.connect(errors.append)
    w.run()
    assert errors


# ── 5. Return in a text field must not insert a break ─────────────────────────

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


@pytest.fixture
def window(qapp):
    from simplelog.ui import facade as ui
    win = ui.MainWindow()
    win.show()
    qapp.processEvents()
    yield win
    win.close()


def test_return_in_the_search_box_does_not_insert_a_break(window, qapp):
    from simplelog.ui import facade as ui
    v = ui.LogViewer(source_type="file")
    window._add_tab("t", v, _FakeWorker())
    v.append_events([(0, "INFO a")])
    box = window._sidebar._search_term_widgets[0]._input
    box.setFocus()
    qapp.processEvents()
    before = v._model.rowCount()
    QTest.keyClick(box, Qt.Key.Key_Return)
    qapp.processEvents()
    assert v._model.rowCount() == before


def test_return_in_the_log_list_still_inserts_a_break(window, qapp):
    from simplelog.ui import facade as ui
    v = ui.LogViewer(source_type="file")
    window._add_tab("t", v, _FakeWorker())
    v.append_events([(0, "INFO a")])
    before = v._model.rowCount()
    QTest.keyClick(v._list_view, Qt.Key.Key_Return)
    assert v._model.rowCount() == before + 1


def test_break_menu_action_still_works(window):
    from simplelog.ui import facade as ui
    v = ui.LogViewer(source_type="file")
    window._add_tab("t", v, _FakeWorker())
    n = v._model.rowCount()
    window._act_break.trigger()
    assert v._model.rowCount() == n + 1


# ── 6. pane limit ─────────────────────────────────────────────────────────────

def test_pane_beyond_the_limit_is_not_started(window, qapp):
    from simplelog.ui import facade as ui
    started = []

    class W(_FakeWorker):
        def start(self):
            started.append(self)

    for _ in range(window._MAX_PANES):
        window._add_tab("p", ui.LogViewer(source_type="file"), W(), split="vertical")
    assert len(started) == window._MAX_PANES
    extra_viewer, extra_worker = ui.LogViewer(source_type="file"), W()
    window._add_tab("p", extra_viewer, extra_worker, split="vertical")
    assert len(started) == window._MAX_PANES          # never started
    assert id(extra_viewer) not in window._workers    # nor tracked (would never be stopped)
    assert "9" in window._status.currentMessage()


def test_discarded_worker_closes_its_ssh_client(window):
    from simplelog.ui import facade as ui
    client = MagicMock()
    w = _FakeWorker()
    w._client = client
    for _ in range(window._MAX_PANES):
        window._add_tab("p", ui.LogViewer(source_type="file"), _FakeWorker(), split="vertical")
    window._add_tab("p", ui.LogViewer(source_type="file"), w, split="vertical")
    client.close.assert_called_once()


# ── 7. closed connection dialogs are released ─────────────────────────────────

def test_closing_a_dialog_stops_its_timer_and_callbacks(qapp, tmp_path, monkeypatch):
    from simplelog.core import i18n, profiles_store
    from simplelog.ui import facade as ui
    monkeypatch.setattr(profiles_store, "_DIR", tmp_path)
    with patch("simplelog.ui.panels.railway.RailwayPanel._do_connect", lambda self: None):
        dlg = ui.AddConnectionDialog(preselect="railway")
    assert dlg._ready_timer.isActive()
    key = id(dlg)
    assert key in i18n._callbacks
    dlg.reject()
    assert dlg._ready_timer is None
    assert key not in i18n._callbacks


def test_remote_panel_deletes_dialogs_after_use(qapp, tmp_path, monkeypatch):
    from simplelog.core import profiles_store
    from simplelog.ui import facade as ui
    from simplelog.ui.remote_dialogs import AddConnectionDialog
    monkeypatch.setattr(profiles_store, "_DIR", tmp_path)
    panel = ui.RemoteHomePanel()
    deleted = []
    orig = AddConnectionDialog.deleteLater

    def spy(self):
        deleted.append(self)
        orig(self)

    with patch.object(AddConnectionDialog, "exec", lambda self: self.reject()), \
         patch.object(AddConnectionDialog, "deleteLater", spy), \
         patch("simplelog.ui.panels.railway.RailwayPanel._do_connect", lambda self: None):
        panel._on_add(preselect="railway")
        panel._on_open_profile("railway", {"name": "x", "token": "t"})
    assert len(deleted) == 2


def test_closing_a_dialog_closes_the_panel_ssh_client(qapp, tmp_path, monkeypatch):
    from simplelog.core import profiles_store
    from simplelog.ui import facade as ui
    monkeypatch.setattr(profiles_store, "_DIR", tmp_path)
    dlg = ui.AddConnectionDialog(preselect="ssh")
    client = MagicMock()
    dlg._embedded_panel._client = client
    dlg.reject()
    client.close.assert_called_once()


def test_running_workers_of_a_closed_dialog_stay_referenced(qapp, tmp_path, monkeypatch):
    from simplelog.core import profiles_store
    from simplelog.ui import facade as ui
    from simplelog.ui import remote_dialogs
    monkeypatch.setattr(profiles_store, "_DIR", tmp_path)
    dlg = ui.AddConnectionDialog(preselect="railway")
    gate = threading.Event()

    class Slow(workers.QThread):
        def run(self):
            gate.wait(5)

    th = Slow()
    th.start()
    dlg._embedded_panel._connect_worker = th
    dlg.reject()
    assert th in remote_dialogs._RUNNING_WORKERS
    gate.set()
    th.wait(3000)
    qapp.processEvents()
    assert th not in remote_dialogs._RUNNING_WORKERS
