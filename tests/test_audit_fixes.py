# ruff: noqa: E402, I001
"""Regression tests for the second audit: crashes, lost lines, wrong queries."""
import os
import subprocess
import sys
import time
import urllib.error
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication



@pytest.fixture(autouse=True)
def app():
    """Created per test, like the other UI tests (not at import: it changes their behaviour)."""
    return QApplication.instance() or QApplication([])


import azure_utils
import cloudwatch
import flyio_utils
import main_window
from log_model import LogModel, TermRow, _line_matches
from worker_base import DockerStreamWorker, LogWorker, PollingWorker, ProcessStreamWorker


def _wait(cond, timeout=8.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        QApplication.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


# ── Error from a worker whose tab is already closed ─────────────────────────

def test_error_of_a_closed_tab_is_ignored(monkeypatch):
    monkeypatch.setattr(main_window.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    w = main_window.MainWindow()
    viewer = main_window.LogViewer(source_type="file")
    worker = _Idle()
    w._add_tab("t", viewer, worker)
    w._close_tab_at(0)
    QApplication.processEvents()
    w._on_error("late failure", viewer)   # must not touch the deleted widgets
    assert _wait(worker.isFinished)
    worker.wait()


class _Idle(LogWorker):
    def run(self):
        self._wakeup.wait(5)   # until stop()


def test_polling_worker_does_not_report_a_history_error_after_stop():
    class P(PollingWorker):
        def _fetch_history(self):
            raise RuntimeError("boom")

    p = P(1)
    p._ctx = {"label": "x"}
    errors = []
    p.error.connect(errors.append)
    p.stop()
    p.run()
    assert errors == []


# ── Process streams ─────────────────────────────────────────────────────────

class _Sh(DockerStreamWorker):
    _ENDED_STATUS = "msg_docker_ended"

    def __init__(self, script):
        super().__init__()
        self._script = script

    def _start_status(self):
        return "s"

    def _command(self):
        return ["sh", "-c", self._script]

    def _exit_error(self, code):
        return str(code)


def test_invalid_utf8_does_not_end_the_stream():
    got = []
    w = _Sh(r"printf 'one\ncaf\351\nthree\n'")
    w.new_lines.connect(lambda ev: got.extend(m for _, m in ev))
    w.run()   # synchronous: no thread to leak into the other tests
    assert got[0] == "one" and got[-1] == "three" and len(got) == 3


def test_stop_before_the_process_exists_kills_it():
    w = _Sh("sleep 30")
    w.stop()
    t0 = time.monotonic()
    w.run()
    assert time.monotonic() - t0 < 5


def test_stderr_is_drained_while_streaming():
    class K(ProcessStreamWorker):
        _MERGE_STDERR = False

        def _start_status(self):
            return "k"

        def _command(self):
            # 200 KB on stderr would fill the pipe and block the process
            return ["sh", "-c", "head -c 200000 /dev/zero | tr '\\0' 'e' >&2; echo ok"]

    got = []
    w = K()
    w.new_lines.connect(lambda ev: got.extend(m for _, m in ev))
    w.run()
    assert got == ["ok"]
    assert len(w._stderr_output()) == 200000


# ── Log model ───────────────────────────────────────────────────────────────

def test_batch_larger_than_the_buffer_on_a_non_empty_model():
    m = LogModel()
    m.append_events([(i, f"old {i}") for i in range(5000)])
    m.append_events([(i, f"new {i}") for i in range(12000)])
    assert len(m._items) == LogModel._MAX_LINES
    assert m.rowCount() == len(m._items)
    assert all(it.message.startswith("new") for it in m.visible_items())


def test_kv_filter_uses_the_parsed_json():
    line = '{"service": "api", "duration": 42}'
    terms = [TermRow("api", "", key="service"), TermRow("42", "AND", key="duration")]
    assert _line_matches(line, terms, {"service": "api", "duration": 42})
    assert _line_matches(line, terms)
    assert not _line_matches(line, [TermRow("web", "", key="service")], {"service": "api"})


# ── Cloud helpers ───────────────────────────────────────────────────────────

def test_flyio_http_error_is_reported():
    err = urllib.error.HTTPError("u", 401, "Unauthorized", {}, None)
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RuntimeError, match="401"):
            flyio_utils.fetch_logs_sse("bad", "app")


def test_azure_since_keeps_the_other_conditions_of_the_line():
    seen = {}
    with patch.object(azure_utils, "_run_query",
                      lambda c, w, q, t: seen.setdefault("q", q) and []):
        azure_utils.fetch_logs_since(
            None, "ws",
            "AppTraces\n| where TimeGenerated > ago(1h) and SeverityLevel >= 3\n| order by TimeGenerated asc",
            datetime(2026, 1, 1, tzinfo=UTC),
        )
    q = seen["q"]
    assert "SeverityLevel >= 3" in q and "datetime(2026-01-01T00:00:00.000Z)" in q
    assert "ago(1h)" not in q


def test_azure_worker_overlaps_late_rows():
    import workers
    calls = []
    with patch.object(azure_utils, "fetch_logs_since", lambda *a: calls.append(a[3]) or []):
        w = workers.AzureWorker(None, "ws", "T")
        w._last_dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        w._fetch_new()
    assert calls[0] == datetime(2026, 1, 1, 11, 59, 0, tzinfo=UTC)


def test_duplicated_aws_profile_does_not_raise(tmp_path, monkeypatch):
    (tmp_path / ".aws").mkdir()
    (tmp_path / ".aws" / "config").write_text(
        "[profile dev]\nregion=a\n[profile dev]\nregion=b\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cloudwatch.list_profiles() == ["dev"]


# ── Update script / checksum ────────────────────────────────────────────────

def test_appimage_update_script_survives_a_quote_in_the_path(tmp_path, monkeypatch):
    scripts = []
    w = main_window.MainWindow()
    monkeypatch.setenv("APPIMAGE", "/home/u/Bob's apps/simplelog.AppImage")
    monkeypatch.setattr(main_window.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(main_window.QApplication, "quit", staticmethod(lambda: None))
    with monkeypatch.context() as mp:
        mp.setattr(subprocess, "Popen", lambda cmd, **k: scripts.append(cmd[1]))
        w._apply_update("/tmp/it's.AppImage", type("P", (), {"close": lambda s: None})())
    body = open(scripts[0]).read()
    os.unlink(scripts[0])
    subprocess.run(["sh", "-n"], input=body.encode(), check=True)


def test_checksum_list_without_the_asset_is_refused():
    import workers
    w = workers.DownloadWorker("https://x/rel/app.deb", "/tmp/none", "1.0.0")

    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"abc  other.file\n"

    with patch("urllib.request.urlopen", return_value=R()):
        with pytest.raises(OSError):
            w._expected_sha256()
