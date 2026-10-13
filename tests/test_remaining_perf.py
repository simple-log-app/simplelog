"""Tests for the second round of perf work and the last blocking-UI fixes."""
import os
import subprocess
import sys
import threading
import time
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QObject, Qt, pyqtSignal
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

    def __init__(self, *a, **k):
        super().__init__()

    def start(self):
        pass

    def isRunning(self):
        return False

    def stop(self):
        pass


# ── P14: heavy SDKs are imported on demand ───────────────────────────────────

def test_paramiko_and_boto3_are_not_imported_at_startup():
    code = (
        "import sys, ui\n"
        "print('paramiko' in sys.modules, 'boto3' in sys.modules)\n"
        "import ssh_utils, cloudwatch\n"
        "ssh_utils.paramiko; cloudwatch.boto3\n"
        "print('paramiko' in sys.modules, 'boto3' in sys.modules)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    ).stdout.split("\n")
    assert out[0] == "False False"
    assert out[1] == "True True"


def test_lazy_module_attribute_errors_stay_attribute_errors():
    import cloudwatch
    import ssh_utils
    with pytest.raises(AttributeError):
        ssh_utils.nope
    with pytest.raises(AttributeError):
        cloudwatch.nope


def test_trust_policy_is_built_once():
    import ssh_utils
    assert ssh_utils._TrustPolicy is ssh_utils._TrustPolicy


# ── P11: bounded history ─────────────────────────────────────────────────────

def test_last_lines_of_a_big_file_are_read_fast(tmp_path):
    p = tmp_path / "big.log"
    p.write_text("".join(f"2024-01-01 INFO request {i} handled path=/api/{i}\n" for i in range(200_000)))
    t0 = time.perf_counter()
    lines, size = workers._read_last_n_lines(str(p), 150_000)
    assert time.perf_counter() - t0 < 2.0           # was ~10 s with the quadratic version
    assert len(lines) == 150_000
    assert lines[-1].endswith("/api/199999") and lines[0].endswith("/api/50000")
    assert size == p.stat().st_size


def test_last_lines_match_a_naive_read(tmp_path):
    p = tmp_path / "a.log"
    text = "".join(f"line {i} é\n" for i in range(5000))
    p.write_text(text)
    for n in (1, 7, 4999, 5000, 9999):
        lines, _ = workers._read_last_n_lines(str(p), n)
        assert lines == text.splitlines()[-n:]


def test_file_worker_never_loads_more_than_the_viewer_keeps(tmp_path):
    p = tmp_path / "a.log"
    p.write_text("".join(f"l{i}\n" for i in range(workers.HISTORY_CAP + 5000)))
    w = workers.FileWorker(str(p), tail_lines=500_000, interval_ms=10)
    got = []
    w.new_lines.connect(lambda ev: got.extend(ev), Qt.ConnectionType.DirectConnection)
    t = threading.Thread(target=w.run, daemon=True)
    t.start()
    end = time.monotonic() + 5
    while time.monotonic() < end and len(got) < workers.HISTORY_CAP:
        time.sleep(0.02)
    w.stop()
    t.join(3)
    assert len(got) == workers.HISTORY_CAP
    assert got[-1][1] == f"l{workers.HISTORY_CAP + 4999}"


def test_cloudwatch_keep_last_bounds_memory():
    import cloudwatch
    pages = [{"events": [{"timestamp": i * 10 + j, "message": f"m{i * 10 + j}"} for j in range(10)]}
             for i in range(100)]
    client = MagicMock()
    client.get_paginator.return_value.paginate.return_value = iter(pages)
    out = cloudwatch.fetch_events(client, "g", max_events=None, keep_last=25)
    assert len(out) == 25
    assert out[-1] == (999, "m999") and out[0] == (975, "m975")


def test_cloudwatch_without_keep_last_returns_everything():
    import cloudwatch
    client = MagicMock()
    client.get_paginator.return_value.paginate.return_value = iter(
        [{"events": [{"timestamp": i, "message": f"m{i}"} for i in range(50)]}]
    )
    assert len(cloudwatch.fetch_events(client, "g", max_events=None)) == 50


def test_cloudwatch_tail_worker_asks_for_a_bounded_history(monkeypatch):
    import cloudwatch
    seen = {}

    def fake(client, group, stream, **kw):
        seen.update(kw)
        w.stop()
        return []

    monkeypatch.setattr(cloudwatch, "fetch_events", fake)
    w = workers.TailWorker(MagicMock(), "g", "", "", 0.001, 3600)
    w.run()
    assert seen["keep_last"] == workers.HISTORY_CAP and seen["max_events"] is None


def test_ssh_tail_command_is_capped():
    client = MagicMock()
    stdout = MagicMock()
    stdout.__iter__ = lambda s: iter([])
    stdout.channel.closed = True
    client.exec_command.return_value = (None, stdout, MagicMock(read=lambda: b""))
    w = workers.SSHWorker(client, "/var/log/x", tail_lines=500_000)
    w.run()
    assert f"tail -n {workers.HISTORY_CAP} -f" in client.exec_command.call_args[0][0]


# ── P8: painting caches ──────────────────────────────────────────────────────

@pytest.fixture
def viewer():
    import ui
    v = ui.LogViewer(source_type="file")
    v.resize(800, 400)
    v.show()
    QApplication.processEvents()
    yield v
    v.close()


def test_color_strings_are_parsed_once():
    import log_view
    assert log_view._qcolor("#abcdef") is log_view._qcolor("#abcdef")
    assert log_view._qcolor("#abcdef").name() == "#abcdef"


def test_timestamp_text_is_formatted_once_per_row(viewer):
    viewer.append_events([(1_700_000_000_000, "INFO a")])
    item = viewer._model.visible_items()[0]
    assert item.ts_text is None
    with patch("log_view.datetime") as dt:
        dt.fromtimestamp.return_value.strftime.return_value = "12:00:00"
        assert viewer._delegate._ts_text(item) == "12:00:00"
        assert viewer._delegate._ts_text(item) == "12:00:00"
    dt.fromtimestamp.assert_called_once()


def test_level_badges_are_laid_out_once_per_font_and_level(viewer):
    from PyQt6.QtGui import QImage, QPainter
    viewer.append_events([(0, "ERROR a"), (0, "ERROR b"), (0, "WARN c")])
    img = QImage(300, 30, QImage.Format.Format_ARGB32)
    p = QPainter(img)
    p.setFont(viewer._log_font)
    rect = img.rect()
    for _ in range(3):
        viewer._delegate._paint_level_badge(p, rect, "error")
    viewer._delegate._paint_level_badge(p, rect, "warn")
    p.end()
    assert len(viewer._delegate._badge_cache) == 2


def test_badge_painting_restores_the_painter_font(viewer):
    from PyQt6.QtGui import QImage, QPainter
    img = QImage(300, 30, QImage.Format.Format_ARGB32)
    p = QPainter(img)
    p.setFont(viewer._log_font)
    before = (p.font().pointSize(), p.font().bold())
    viewer._delegate._paint_level_badge(p, img.rect(), "info")
    assert (p.font().pointSize(), p.font().bold()) == before
    p.end()


# ── P9: search only scans rows it has not seen ───────────────────────────────

def test_search_rescans_only_new_rows(viewer):
    from log_model import TermRow
    viewer.append_events([(0, f"needle {i}") for i in range(50)])
    viewer.flush_pending()
    terms = [TermRow("needle", "")]
    calls = []
    import log_view
    real = log_view._line_matches

    def counting(line, ts):
        calls.append(line)
        return real(line, ts)

    with patch.object(log_view, "_line_matches", counting):
        first = viewer.apply_search(terms)
        assert len(calls) == 50
        calls.clear()
        again = viewer.apply_search(terms)
        assert calls == [] and again == first
        viewer.append_events([(0, "needle new"), (0, "other")])
        viewer.flush_pending()
        viewer.apply_search(terms)
        assert sorted(calls) == ["needle new", "other"]       # only the new rows
        calls.clear()
        viewer.apply_search([TermRow("other", "")])           # new terms: everything again
        assert len(calls) == 52


def test_cached_search_gives_the_same_matches_as_a_fresh_one(viewer):
    from log_model import TermRow
    viewer.append_events([(0, "red apple"), (0, "green apple"), (0, "red pear"), (0, "x")])
    viewer.flush_pending()
    terms = [TermRow("red", ""), TermRow("apple", "OR")]
    first = viewer.apply_search(terms)
    viewer.append_events([(0, "red again")])
    viewer.flush_pending()
    second = viewer.apply_search(terms)
    assert second[:len(first)] == first
    assert second[-1][0] == 4
    for item in viewer._model.visible_items():       # forget the cache: same answer
        item.search = None
    assert viewer.apply_search(terms) == second


def test_search_cache_follows_a_changed_filter(viewer):
    from log_model import TermRow
    viewer.append_events([(0, "a needle"), (0, "b needle"), (0, "c")])
    viewer.flush_pending()
    search = [TermRow("needle", "")]
    assert [r for r, _, _ in viewer.apply_search(search)] == [0, 1]
    viewer.apply_filter([TermRow("b", "")])
    assert [r for r, _, _ in viewer.apply_search(search)] == [0]     # row index shifted


# ── P7: wrapping can be switched off ─────────────────────────────────────────

LONG = "INFO " + "word " * 120


def _hint(v, row=0):
    return v._delegate.sizeHint(MagicMock(rect=v._list_view.viewport().rect()), v._model.index(row))


def test_wrapping_is_on_by_default(viewer):
    assert viewer.wrap_lines and viewer.wrap_cb.isChecked()
    assert viewer._list_view.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_without_wrapping_every_row_is_one_line_wide_enough_for_its_text(viewer):
    viewer.append_events([(1, LONG), (1, "INFO short")])
    viewer.flush_pending()
    wrapped = _hint(viewer, 0)
    short_wrapped = _hint(viewer, 1)
    viewer.wrap_cb.setChecked(False)
    long_row, short_row = _hint(viewer, 0), _hint(viewer, 1)
    assert long_row.height() == short_row.height() == short_wrapped.height() < wrapped.height()
    assert long_row.width() > viewer._list_view.viewport().width()     # scrolls sideways
    assert short_row.width() == viewer._list_view.viewport().width()


def test_unwrapped_view_gets_a_horizontal_scrollbar_and_back(viewer):
    viewer.wrap_cb.setChecked(False)
    assert viewer._list_view.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    viewer.wrap_cb.setChecked(True)
    assert viewer._list_view.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_toggling_wrap_relayouts(viewer):
    with patch.object(viewer._list_view, "scheduleDelayedItemsLayout") as relayout:
        viewer.wrap_cb.setChecked(False)
    relayout.assert_called()


def test_row_size_cache_distinguishes_wrap_modes(viewer):
    viewer.append_events([(1, LONG)])
    viewer.flush_pending()
    h_wrapped = _hint(viewer).height()
    viewer.wrap_cb.setChecked(False)
    h_single = _hint(viewer).height()
    viewer.wrap_cb.setChecked(True)
    assert _hint(viewer).height() == h_wrapped != h_single


def test_unwrapped_rows_paint_without_error(viewer):
    from PyQt6.QtGui import QImage, QPainter
    viewer.append_events([(1, LONG)])
    viewer.flush_pending()
    viewer.wrap_cb.setChecked(False)
    img = QImage(1200, 40, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setFont(viewer._log_font)
    from PyQt6.QtWidgets import QStyle
    opt = MagicMock(rect=img.rect(), state=QStyle.StateFlag.State_None)
    viewer._delegate.paint(p, opt, viewer._model.index(0))
    p.end()


def test_wrap_label_is_translated():
    import i18n
    for lang in ("en", "fr", "de", "es", "zh"):
        assert i18n._STRINGS[lang]["viewer_wrap"]


# ── 14: SFTP browser lists directories in the background ─────────────────────

def test_sftp_dialog_does_not_block_while_listing(qapp):
    import ssh_utils
    from panels.ssh import _SftpBrowserDialog
    release = threading.Event()

    def slow(client, path):
        release.wait(5)
        return [("etc", True), ("app.log", False)]

    with patch.object(ssh_utils, "list_remote_dir_full", slow):
        t0 = time.monotonic()
        dlg = _SftpBrowserDialog(MagicMock(), "/var/log")
        assert time.monotonic() - t0 < 0.5
        assert not dlg._list.isEnabled()
        release.set()
        assert _wait_for(lambda: dlg._list.isEnabled())
    texts = [dlg._list.item(i).text() for i in range(dlg._list.count())]
    assert texts == ["📁  ..", "📁  etc", "📄  app.log"]
    assert dlg._list.item(2).data(Qt.ItemDataRole.UserRole) == ("file", "/var/log/app.log")


def test_sftp_dialog_ignores_an_outdated_listing(qapp):
    import ssh_utils
    from panels.ssh import _SftpBrowserDialog
    with patch.object(ssh_utils, "list_remote_dir_full", lambda c, p: []):
        dlg = _SftpBrowserDialog(MagicMock(), "/")
        assert _wait_for(lambda: dlg._list.isEnabled())
    dlg._nav_gen = 10
    dlg._on_listed(9, "/old", [("stale", False)])
    assert dlg._list.count() == 0


def test_sftp_dialog_reports_a_listing_error(qapp):
    import ssh_utils
    from panels.ssh import _SftpBrowserDialog

    def fail(c, p):
        raise RuntimeError("permission denied")

    with patch.object(ssh_utils, "list_remote_dir_full", fail), \
         patch("panels.ssh.QMessageBox.warning") as warn:
        dlg = _SftpBrowserDialog(MagicMock(), "/root")
        assert _wait_for(lambda: warn.called)
    assert "permission denied" in str(warn.call_args)
    assert dlg._list.isEnabled()


def test_sftp_dialog_closed_while_listing_is_harmless(qapp):
    import ssh_utils
    from panels.ssh import _SftpBrowserDialog
    release = threading.Event()
    with patch.object(ssh_utils, "list_remote_dir_full",
                      lambda c, p: (release.wait(5), [("x", False)])[1]):
        dlg = _SftpBrowserDialog(MagicMock(), "/")
        dlg.reject()
        release.set()
        QApplication.processEvents()
        time.sleep(0.2)
        QApplication.processEvents()
    assert dlg._nav_gen == -1


def test_sftp_navigation_into_a_folder_keeps_working(qapp):
    import ssh_utils
    from panels.ssh import _SftpBrowserDialog
    listing = {"/": [("var", True)], "/var": [("syslog", False)]}
    with patch.object(ssh_utils, "list_remote_dir_full", lambda c, p: listing[p]):
        dlg = _SftpBrowserDialog(MagicMock(), "/")
        assert _wait_for(lambda: dlg._list.count() == 1)
        dlg._on_double_click(dlg._list.item(0))
        assert _wait_for(lambda: dlg._list.count() == 2)
    assert dlg._list.item(1).text() == "📄  syslog"


# ── 14: restored tabs connect in the background ──────────────────────────────

@pytest.fixture
def window(qapp):
    import ui
    win = ui.MainWindow()
    win.show()
    qapp.processEvents()
    yield win
    win.close()


def test_ssh_tab_restore_does_not_block_and_then_opens(window):
    import ssh_utils
    release = threading.Event()
    client = MagicMock()

    def slow(*a, **k):
        release.wait(5)
        return client

    cfg = {"host": "h", "user": "u", "remote_path": "/var/log/x.log"}
    with patch.object(ssh_utils, "make_client", slow), \
         patch("main_window.SSHWorker", _FakeWorker):
        t0 = time.monotonic()
        window.open_ssh_tab(cfg)
        assert time.monotonic() - t0 < 0.5
        assert window._top_tabs.count() == 0
        release.set()
        assert _wait_for(lambda: window._top_tabs.count() == 1)
    assert window._top_tabs.tabText(0) == "x.log"


def test_ssh_tab_restore_failure_is_reported(window):
    import ssh_utils

    def fail(*a, **k):
        raise RuntimeError("no route")

    with patch.object(ssh_utils, "make_client", fail), \
         patch("main_window.QMessageBox.critical") as crit:
        window.open_ssh_tab({"host": "h", "user": "u", "remote_path": "/x"})
        assert _wait_for(lambda: crit.called)
    assert "no route" in str(crit.call_args) and window._top_tabs.count() == 0


def test_gcp_tab_restore_connects_in_the_background(window):
    import gcp_utils
    release = threading.Event()

    def slow(project, key_path=None):
        release.wait(5)
        return MagicMock()

    with patch.object(gcp_utils, "make_client", slow), patch("main_window.GCPWorker", _FakeWorker):
        t0 = time.monotonic()
        window.open_gcp_tab({"project_id": "proj"})
        assert time.monotonic() - t0 < 0.5
        release.set()
        assert _wait_for(lambda: window._top_tabs.count() == 1)
    assert window._top_tabs.tabText(0) == "proj"


def test_azure_tab_restore_connects_in_the_background(window):
    import azure_utils
    release = threading.Event()

    def slow_cred(*a):
        release.wait(5)
        return "cred"

    cfg = {"tenant_id": "t", "client_id": "c", "client_secret": "s", "workspace_id": "w",
           "query": "q", "label": "prod"}
    with patch.object(azure_utils, "make_credential", slow_cred), \
         patch.object(azure_utils, "make_logs_client", lambda cred: MagicMock()), \
         patch("main_window.AzureWorker", _FakeWorker):
        t0 = time.monotonic()
        window.open_azure_tab(cfg)
        assert time.monotonic() - t0 < 0.5
        release.set()
        assert _wait_for(lambda: window._top_tabs.count() == 1)
    assert window._top_tabs.tabText(0) == "prod"


def test_gcp_and_azure_restore_failures_are_reported(window):
    import azure_utils
    import gcp_utils
    with patch.object(gcp_utils, "make_client", MagicMock(side_effect=RuntimeError("gcp down"))), \
         patch.object(azure_utils, "make_credential", MagicMock(side_effect=RuntimeError("az down"))), \
         patch("main_window.QMessageBox.critical") as crit:
        window.open_gcp_tab({"project_id": "p"})
        window.open_azure_tab({"tenant_id": "t", "client_id": "c", "client_secret": "s",
                               "workspace_id": "w", "query": "q"})
        assert _wait_for(lambda: crit.call_count == 2)
    messages = " ".join(str(c) for c in crit.call_args_list)
    assert "gcp down" in messages and "az down" in messages


def test_tabs_opened_with_a_ready_client_are_still_synchronous(window):
    with patch("main_window.SSHWorker", _FakeWorker):
        window.open_ssh_tab({"host": "h", "user": "u", "remote_path": "/x", "_client": MagicMock()})
    assert window._top_tabs.count() == 1


# ── 12: Kubernetes contexts load in the background ───────────────────────────

@pytest.fixture
def k8s(monkeypatch):
    import kubernetes_utils
    monkeypatch.setattr(kubernetes_utils, "is_available", lambda: True)
    return kubernetes_utils


def test_kubernetes_panel_builds_without_waiting_for_kubectl(qapp, k8s, monkeypatch):
    release = threading.Event()

    def slow_contexts():
        release.wait(5)
        return ["dev", "prod"]

    monkeypatch.setattr(k8s, "list_contexts", slow_contexts)
    monkeypatch.setattr(k8s, "current_context", lambda: "prod")
    from panels.kubernetes import KubernetesPanel
    t0 = time.monotonic()
    p = KubernetesPanel()
    assert time.monotonic() - t0 < 0.5
    assert p._k8s_context_combo.count() == 1
    release.set()
    assert _wait_for(lambda: p._k8s_context_combo.count() == 3)
    assert p._k8s_context_combo.currentText() == "prod"       # the current context is preselected


def test_kubernetes_saved_context_survives_the_late_listing(qapp, k8s, monkeypatch):
    release = threading.Event()

    def slow_contexts():
        release.wait(5)
        return ["dev", "prod", "staging"]

    monkeypatch.setattr(k8s, "list_contexts", slow_contexts)
    monkeypatch.setattr(k8s, "current_context", lambda: "prod")
    from panels.kubernetes import KubernetesPanel
    p = KubernetesPanel()
    p._load_k8s_profile({"context": "staging"})     # reopened before kubectl answered
    assert p._k8s_context_combo.currentText() == "staging"
    release.set()
    assert _wait_for(lambda: p._k8s_context_combo.count() == 4)
    assert p._k8s_context_combo.currentText() == "staging"
    assert [p._k8s_context_combo.itemText(i) for i in range(4)].count("staging") == 1


def test_kubernetes_survives_kubectl_failure(qapp, k8s, monkeypatch):
    def boom():
        raise RuntimeError("no kubeconfig")

    monkeypatch.setattr(k8s, "list_contexts", boom)
    monkeypatch.setattr(k8s, "current_context", lambda: "")
    from panels.kubernetes import KubernetesPanel
    p = KubernetesPanel()
    QApplication.processEvents()
    time.sleep(0.1)
    QApplication.processEvents()
    assert p._k8s_context_combo.count() == 1
