"""Tests for worker_base.py and for the concrete workers built on top of it."""
import os
import subprocess
import threading
import time
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QCoreApplication

import workers
from worker_base import (
    HISTORY_CAP,
    DockerStreamWorker,
    LogWorker,
    PollingWorker,
    ProcessStreamWorker,
    StreamWorker,
    clean_lines,
)


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


def _capture(worker):
    got = {"lines": [], "status": [], "error": [], "history": []}
    worker.new_lines.connect(lambda ev: got["lines"].append(ev))
    worker.status.connect(got["status"].append)
    worker.error.connect(got["error"].append)
    if hasattr(worker, "history_done"):
        worker.history_done.connect(got["history"].append)
    return got


# ── class hierarchy ──────────────────────────────────────────────────────────

POLLING = [workers.TailWorker, workers.VercelWorker, workers.GCPWorker, workers.AzureWorker,
           workers.LokiWorker, workers.DatadogWorker, workers.ElasticWorker,
           workers.RailwayWorker, workers.FlyioWorker]
PROCESS = [workers.DockerContainerWorker, workers.DockerComposeWorker,
           workers.DockerExecFileWorker, workers.KubernetesWorker]


@pytest.mark.parametrize("cls", POLLING)
def test_cloud_workers_are_polling_workers(cls):
    assert issubclass(cls, PollingWorker) and issubclass(cls, LogWorker)
    for sig in ("new_lines", "status", "error", "history_done"):
        assert hasattr(cls, sig)


@pytest.mark.parametrize("cls", PROCESS)
def test_process_workers_are_process_stream_workers(cls):
    assert issubclass(cls, ProcessStreamWorker) and issubclass(cls, StreamWorker)


def test_every_worker_can_be_stopped_the_same_way():
    for cls in (*POLLING, *PROCESS, workers.FileWorker, workers.StdinWorker,
                workers.SSHWorker, workers.CloudflareWorker):
        assert issubclass(cls, LogWorker), cls.__name__
        assert cls.stop is not None


def test_stop_sets_the_flag_and_wakes_sleepers():
    w = workers.StdinWorker()
    assert w._stop is False and not w._wakeup.is_set()
    w.stop()
    assert w._stop is True and w._wakeup.is_set()


# ── PollingWorker template ───────────────────────────────────────────────────

class _Scripted(PollingWorker):
    """History returns *history*; each poll returns the next item (an Exception is raised)."""

    _MSG_LOADING = "loading {who}"
    _MSG_LOADED = "loaded {n} for {who}"
    _MSG_NEW = "{n} new for {who}"
    _MSG_IDLE = "idle {who}"

    def __init__(self, history, polls, interval_s=0.001):
        super().__init__(interval_s)
        self._ctx = {"who": "w"}
        self._history = history
        self._polls = list(polls)

    def _fetch_history(self):
        if isinstance(self._history, Exception):
            raise self._history
        return self._history

    def _fetch_new(self):
        if not self._polls:
            self.stop()
            return []
        item = self._polls.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_polling_worker_runs_history_then_polls():
    w = _Scripted([(1, "a")], [[(2, "b")], [], []])
    got = _capture(w)
    order = []
    w.new_lines.connect(lambda ev: order.append("lines"))
    w.history_done.connect(lambda n: order.append("history"))
    w.status.connect(lambda s: order.append(s))
    w.run()
    assert got["lines"] == [[(1, "a")], [(2, "b")]]
    assert got["history"] == [1]
    assert got["status"] == ["loading w", "loaded 1 for w", "1 new for w", "idle w", "idle w", "idle w"]
    assert order[:4] == ["loading w", "lines", "history", "loaded 1 for w"]


def test_empty_history_still_reports_zero():
    w = _Scripted([], [])
    got = _capture(w)
    w.run()
    assert got["lines"] == [] and got["history"] == [0]


def test_history_error_stops_the_worker_at_once():
    w = _Scripted(RuntimeError("denied"), [[(1, "never")]])
    got = _capture(w)
    w.run()
    assert got["error"] == ["denied"] and got["lines"] == [] and got["history"] == []
    assert w._polls == [[(1, "never")]]                 # no poll was attempted


def test_failed_poll_is_retried_and_recovers():
    w = _Scripted([], [RuntimeError("blip"), [(5, "ok")], []])
    got = _capture(w)
    w.run()
    assert got["error"] == []
    assert got["lines"] == [[(5, "ok")]]
    assert any("retrying" in s and "blip" in s for s in got["status"])


def test_poll_gives_up_after_max_fails():
    w = _Scripted([], [RuntimeError("down")] * 10)
    got = _capture(w)
    w.run()
    assert got["error"] == ["down"]
    assert len(w._polls) == 10 - PollingWorker._MAX_FAILS


def test_unset_loaded_template_is_skipped():
    class Quiet(_Scripted):
        _MSG_LOADED = ""

    w = Quiet([(1, "a")], [])
    got = _capture(w)
    w.run()
    assert "loaded" not in " ".join(got["status"])


def test_polling_sleep_is_interrupted_by_stop():
    w = _Scripted([], [], interval_s=30)
    t0 = time.monotonic()
    th = threading.Thread(target=w._sleep)
    th.start()
    time.sleep(0.05)
    w.stop()
    th.join(2)
    assert time.monotonic() - t0 < 1.0


def test_polling_worker_requires_the_two_fetch_methods():
    w = PollingWorker()
    with pytest.raises(NotImplementedError):
        w._fetch_history()
    with pytest.raises(NotImplementedError):
        w._fetch_new()


# ── concrete polling workers: cursors and status lines ───────────────────────

def _run_to_end(worker):
    got = _capture(worker)
    worker.run()
    return got


def _stopper(worker, answers):
    """A fetch stub returning *answers* in turn, then stopping the worker."""
    answers = list(answers)

    def fetch(*a, **k):
        if not answers:
            worker.stop()
            return []
        r = answers.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    return fetch


def test_vercel_worker(monkeypatch):
    import vercel_utils
    w = workers.VercelWorker("t", "pid", "my-app", "dep", interval_s=0.001)
    monkeypatch.setattr(vercel_utils, "fetch_deployment_events",
                        _stopper(w, [[(10, "a")], [(20, "b")]]))
    got = _run_to_end(w)
    assert got["lines"] == [[(10, "a")], [(20, "b")]]
    assert got["status"][:3] == ["Loading logs for my-app…", "Tailing my-app — 1 events loaded",
                                 "my-app — 1 new events"]
    assert got["status"][3] == "Tailing my-app…"
    assert w._last_ts == 21


def test_cloudwatch_worker(monkeypatch):
    import cloudwatch
    w = workers.TailWorker(MagicMock(), "g", "s", "", 0.001, 3600)
    monkeypatch.setattr(cloudwatch, "fetch_events", _stopper(w, [[(5, "a")], [(9, "b")]]))
    got = _run_to_end(w)
    assert got["lines"] == [[(5, "a")], [(9, "b")]]
    assert got["status"][0] == "Loading history…"
    assert got["status"][1] == "Updated  —  1 new events"
    assert got["status"][2] == "Tailing…  no new events"
    assert w._last_ts == 10


def test_gcp_worker(monkeypatch):
    import gcp_utils
    w = workers.GCPWorker(MagicMock(), "proj", "(all)", "ALL", "", interval_s=0.001)
    monkeypatch.setattr(gcp_utils, "fetch_entries", _stopper(w, [[(1000, "a")], [(2000, "b")]]))
    got = _run_to_end(w)
    assert got["lines"] == [[(1000, "a")], [(2000, "b")]]
    assert got["status"][:3] == ["Loading GCP logs for proj…", "GCP proj — 1 entries loaded",
                                 "GCP proj — 1 new entries"]
    assert got["status"][3] == "GCP proj — tailing…"


def test_azure_worker(monkeypatch):
    import azure_utils
    w = workers.AzureWorker(MagicMock(), "workspace-id", "q", label="prod", interval_s=0.001)
    monkeypatch.setattr(azure_utils, "fetch_logs", _stopper(w, [[(1000, "a")]]))
    monkeypatch.setattr(azure_utils, "fetch_logs_since", _stopper(w, [[(2000, "b")]]))
    got = _run_to_end(w)
    assert got["lines"] == [[(1000, "a")], [(2000, "b")]]
    assert got["status"][:3] == ["Loading Azure logs — prod…", "Azure prod — 1 rows loaded",
                                 "Azure prod — 1 new rows"]


def test_azure_worker_label_defaults_to_the_workspace():
    w = workers.AzureWorker(MagicMock(), "abcdefghijkl", "q")
    assert w._ctx["label"] == "abcdefgh"


def test_loki_worker_status_names_the_host(monkeypatch):
    import loki_utils
    w = workers.LokiWorker("https://loki.example.com:3100/path", "q", interval_s=0.001)
    monkeypatch.setattr(loki_utils, "fetch_logs", _stopper(w, [[(1, "a")], [(2, "b")]]))
    got = _run_to_end(w)
    assert got["status"][0] == "Loading Loki logs from loki.example.com:3100…"
    assert got["status"][1] == "Loki loki.example.com:3100 — 1 entries loaded"
    assert got["status"][2] == "Loki loki.example.com:3100 — 1 new entries"


def test_datadog_worker_status_names_the_site(monkeypatch):
    import datadog_utils
    w = workers.DatadogWorker("https://api.datadoghq.eu", "*", "k", "a", interval_s=0.001)
    monkeypatch.setattr(datadog_utils, "fetch_logs", _stopper(w, [[(1000, "a")], [(2000, "b")]]))
    got = _run_to_end(w)
    assert got["status"][0] == "Loading Datadog logs from api.datadoghq.eu…"
    assert got["status"][2] == "Datadog api.datadoghq.eu — 1 new entries"
    assert w._last_iso.startswith("1970-01-01T00:00:02")


def test_elastic_worker_passes_its_options(monkeypatch):
    import elastic_utils
    calls = []
    w = workers.ElasticWorker("http://es:9200", "logs-*", "level:error", api_key="K",
                              ts_field="ts", interval_s=0.001)
    answers = [([(1000, "a")], []), ([(2000, "b")], [])]

    def fetch(url, index, query, **kw):
        calls.append((url, index, query, kw))
        if not answers:
            w.stop()
            return [], []
        return answers.pop(0)

    monkeypatch.setattr(elastic_utils, "fetch_logs", fetch)
    got = _run_to_end(w)
    assert got["status"][1] == "Elastic es:9200/logs-* — 1 hits loaded"
    assert got["status"][2] == "Elastic es:9200 — 1 new hits"
    assert all(c[3]["api_key"] == "K" and c[3]["ts_field"] == "ts" for c in calls)
    assert calls[0][3]["latest"] is True and calls[1][3]["inclusive"] is True


def test_railway_worker_without_a_deployment_reports_an_error(monkeypatch):
    import railway_utils
    monkeypatch.setattr(railway_utils, "get_latest_deployment", lambda *a: None)
    w = workers.RailwayWorker("t", "proj", "svc", "sid", interval_s=0.001)
    got = _run_to_end(w)
    assert got["error"] == ["No deployment found for proj/svc"]
    assert got["lines"] == [] and got["history"] == []


def test_railway_worker_follows_new_deployments(monkeypatch):
    import railway_utils
    now = int(time.time() * 1000)
    deploys = iter([{"id": "d1"}, {"id": "d1"}, {"id": "d2"}, {"id": "d2"}])
    logs = {"d1": [(now, "old")], "d2": [(now, "old"), (now + 1, "fresh")]}
    w = workers.RailwayWorker("t", "p", "s", "sid", interval_s=0.001, lookback_s=3600)
    seen_deploy = []

    def latest(*a):
        try:
            return next(deploys)
        except StopIteration:
            w.stop()
            return {"id": "d2"}

    def fetch(token, did):
        seen_deploy.append(did)
        return logs[did]

    monkeypatch.setattr(railway_utils, "get_latest_deployment", latest)
    monkeypatch.setattr(railway_utils, "fetch_deployment_logs", fetch)
    got = _run_to_end(w)
    flat = [e for batch in got["lines"] for e in batch]
    assert flat == [(now, "old"), (now, "old"), (now + 1, "fresh")]   # d2 starts with a clean slate
    assert got["status"][:2] == ["Loading Railway logs for p/s…", "Railway p/s — 1 lines loaded"]
    assert seen_deploy[0] == "d1" and "d2" in seen_deploy


def test_flyio_worker_only_shows_recent_history(monkeypatch):
    import flyio_utils
    now = int(time.time() * 1000)
    w = workers.FlyioWorker("t", "app", interval_s=0.001, lookback_s=60)
    monkeypatch.setattr(flyio_utils, "fetch_logs_sse",
                        _stopper(w, [[(now - 3_600_000, "ancient"), (now - 1000, "recent")]]))
    got = _run_to_end(w)
    assert got["lines"] == [[(now - 1000, "recent")]]
    assert got["history"] == [1]
    assert got["status"][:2] == ["Loading Fly.io logs for app…", "Fly.io app — 1 entries loaded"]


# ── streaming helpers ────────────────────────────────────────────────────────

def test_clean_lines_stamps_and_drops_empty_lines():
    out = clean_lines(["a  \n", "", "  \n", "b"])
    assert [m for _, m in out] == ["a", "b"]
    assert len({ts for ts, _ in out}) == 1 and out[0][0] > 1_600_000_000_000


def test_clean_lines_can_keep_trailing_spaces():
    assert [m for _, m in clean_lines(["a  \r\n"], "\n\r")] == ["a  "]


def test_pump_forwards_batches_and_stops():
    class W(StreamWorker):
        pass

    w = W()
    got = _capture(w)
    w._pump(iter(["x", "y"]), lambda batch: [(1, line) for line in batch])
    assert [m for ev in got["lines"] for _, m in ev] == ["x", "y"]


# ── process workers ──────────────────────────────────────────────────────────

class _Proc:
    def __init__(self, lines, code=0, stderr=""):
        self.stdout = iter(lines)
        self.stderr = MagicMock(read=lambda: stderr)
        self.returncode = code
        self.terminated = False

    def wait(self):
        pass

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True


def _popen(monkeypatch, proc):
    calls = []

    def fake(cmd, **kw):
        calls.append((cmd, kw))
        return proc

    monkeypatch.setattr(subprocess, "Popen", fake)
    return calls


DOCKER_CASES = [
    (lambda: workers.DockerContainerWorker("abcdef1234567890"),
     ["docker", "logs", "-f", "--timestamps", "--since=3600s", "abcdef1234567890"],
     "Streaming docker logs for abcdef123456…", "Docker log stream ended",
     "docker logs exited with code 3"),
    (lambda: workers.DockerComposeWorker("shop"),
     ["docker", "compose", "-p", "shop", "logs", "-f", "--timestamps", "--since=3600s"],
     "Streaming compose stack shop…", "Compose log stream ended",
     "docker compose logs exited 3"),
    (lambda: workers.DockerExecFileWorker("abcdef1234567890", "/var/log/x", 500_000),
     ["docker", "exec", "abcdef1234567890", "tail", f"-n{HISTORY_CAP}", "-f", "/var/log/x"],
     "Tailing /var/log/x in abcdef123456…", "Container file stream ended",
     "docker exec exited with code 3"),
]


@pytest.mark.parametrize("make,cmd,start,ended,failed", DOCKER_CASES)
def test_docker_workers_command_and_status(monkeypatch, make, cmd, start, ended, failed):
    calls = _popen(monkeypatch, _Proc(["2023-11-14T12:00:00.5Z hello\n", "\n"]))
    w = make()
    got = _capture(w)
    w.run()
    assert calls[0][0] == cmd
    assert calls[0][1]["stderr"] == subprocess.STDOUT         # errors appear in the log
    assert got["status"] == [start, ended]
    assert got["error"] == []
    assert [e for batch in got["lines"] for e in batch][0][1] in ("hello", "2023-11-14T12:00:00.5Z hello")


@pytest.mark.parametrize("make,cmd,start,ended,failed", DOCKER_CASES)
def test_docker_workers_report_a_failing_exit(monkeypatch, make, cmd, start, ended, failed):
    _popen(monkeypatch, _Proc(["x\n"], code=3))
    w = make()
    got = _capture(w)
    w.run()
    assert got["error"] == [failed] and ended not in got["status"]


@pytest.mark.parametrize("make,cmd,start,ended,failed", DOCKER_CASES)
def test_docker_workers_treat_sigterm_as_a_normal_end(monkeypatch, make, cmd, start, ended, failed):
    _popen(monkeypatch, _Proc(["x\n"], code=-15))
    w = make()
    got = _capture(w)
    w.run()
    assert got["error"] == [] and ended in got["status"]


@pytest.mark.parametrize("make,cmd,start,ended,failed", DOCKER_CASES)
def test_docker_workers_say_nothing_after_a_stop(monkeypatch, make, cmd, start, ended, failed):
    _popen(monkeypatch, _Proc(["x\n"], code=3))
    w = make()
    w._stop = True
    got = _capture(w)
    w.run()
    assert got["error"] == [] and got["status"] == [start]


def test_docker_timestamped_workers_parse_the_event_time(monkeypatch):
    _popen(monkeypatch, _Proc(["2023-11-14T12:00:00Z INFO started\n"]))
    w = workers.DockerContainerWorker("c")
    got = _capture(w)
    w.run()
    [(ts, msg)] = got["lines"][0]
    assert msg == "INFO started" and ts == 1_699_963_200_000


def test_docker_exec_worker_uses_receive_time(monkeypatch):
    _popen(monkeypatch, _Proc(["2023-11-14T12:00:00Z looks like a timestamp\n"]))
    w = workers.DockerExecFileWorker("c", "/x")
    got = _capture(w)
    w.run()
    assert got["lines"][0][0][1] == "2023-11-14T12:00:00Z looks like a timestamp"


def test_popen_failure_becomes_an_error(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("docker not found")

    monkeypatch.setattr(subprocess, "Popen", boom)
    w = workers.DockerContainerWorker("c")
    got = _capture(w)
    w.run()
    assert got["error"] == ["docker not found"]


def test_stop_terminates_a_running_process_only():
    class W(ProcessStreamWorker):
        pass

    w = W()
    w._proc = _Proc([], code=None)       # still running
    w.stop()
    assert w._proc.terminated
    w2 = W()
    w2._proc = _Proc([], code=0)         # already finished
    w2.stop()
    assert not w2._proc.terminated
    W().stop()                           # no process yet


def test_stop_ignores_a_process_that_refuses_to_terminate():
    class Bad(_Proc):
        def terminate(self):
            raise OSError("gone")

    class W(ProcessStreamWorker):
        pass

    w = W()
    w._proc = Bad([], code=None)
    w.stop()
    assert w._stop is True


def test_process_worker_requires_a_command():
    with pytest.raises(NotImplementedError):
        ProcessStreamWorker()._command()
    with pytest.raises(NotImplementedError):
        ProcessStreamWorker()._start_status()
    with pytest.raises(NotImplementedError):
        DockerStreamWorker()._exit_error(1)


def test_kubernetes_worker_command_and_stderr(monkeypatch):
    import kubernetes_utils
    monkeypatch.setattr(kubernetes_utils, "build_logs_cmd",
                        lambda pod, ns, ctx, container, since_s: ["kubectl", pod, ns, ctx, str(since_s)])
    calls = _popen(monkeypatch, _Proc(["2023-11-14T12:00:00Z one\n", "two\n"], code=1,
                                      stderr="Error from server (NotFound)"))
    w = workers.KubernetesWorker("web-1", "prod", context="c1", lookback_s=120)
    got = _capture(w)
    w.run()
    assert calls[0][0] == ["kubectl", "web-1", "prod", "c1", "120"]
    assert calls[0][1]["stderr"] == subprocess.PIPE
    assert got["status"][0] == "Streaming Kubernetes logs for prod/web-1…"
    assert got["status"][1] == "k8s prod/web-1 — streaming"
    assert got["history"] == [2]
    assert [m for ev in got["lines"] for _, m in ev] == ["one", "two"]
    assert got["error"] == ["Error from server (NotFound)"]


def test_kubernetes_worker_keeps_blank_lines_and_reports_history_once(monkeypatch):
    import kubernetes_utils
    monkeypatch.setattr(kubernetes_utils, "build_logs_cmd", lambda *a, **k: ["kubectl"])

    class SlowProc(_Proc):
        def __init__(self):
            super().__init__([])
            self.stdout = self._gen()

        def _gen(self):
            yield "a\n"
            yield "\n"
            time.sleep(0.4)
            yield "b\n"

    _popen(monkeypatch, SlowProc())
    w = workers.KubernetesWorker("p", "n")
    got = _capture(w)
    w.run()
    assert [m for ev in got["lines"] for _, m in ev] == ["a", "", "b"]
    assert got["history"] == [2]                        # only the first batch is "history"
    assert got["status"].count("k8s n/p — streaming") == 1
    assert got["error"] == []


def test_kubernetes_worker_clean_exit_has_no_error(monkeypatch):
    import kubernetes_utils
    monkeypatch.setattr(kubernetes_utils, "build_logs_cmd", lambda *a, **k: ["kubectl"])
    _popen(monkeypatch, _Proc(["x\n"], code=0, stderr="ignored"))
    w = workers.KubernetesWorker("p", "n")
    got = _capture(w)
    w.run()
    assert got["error"] == []


# ── SSH / stdin / file on the shared base ────────────────────────────────────

def test_ssh_worker_strips_only_line_endings():
    client = MagicMock()
    stdout = MagicMock()
    stdout.__iter__ = lambda s: iter(["keep  trailing  \r\n", "\n", "next\n"])
    stdout.channel.closed = False
    stderr = MagicMock(read=lambda: b"")
    client.exec_command.return_value = (None, stdout, stderr)
    w = workers.SSHWorker(client, "/var/log/x")
    got = _capture(w)
    w.run()
    assert [m for ev in got["lines"] for _, m in ev] == ["keep  trailing  ", "next"]
    assert got["status"] == ["Connecting to /var/log/x…", "Tailing /var/log/x", "SSH stream ended"]
    client.close.assert_called_once()


def test_ssh_worker_reports_stderr():
    client = MagicMock()
    stdout = MagicMock()
    stdout.__iter__ = lambda s: iter([])
    stdout.channel.closed = False
    client.exec_command.return_value = (None, stdout, MagicMock(read=lambda: b"No such file\n"))
    w = workers.SSHWorker(client, "/nope")
    got = _capture(w)
    w.run()
    assert got["error"] == ["No such file"]


def test_ssh_stop_closes_the_channel():
    w = workers.SSHWorker(MagicMock(), "/x")
    w._channel = MagicMock()
    w.stop()
    w._channel.close.assert_called_once()
    assert w._stop is True


def test_file_worker_stop_is_immediate_when_idle(tmp_path):
    p = tmp_path / "a.log"
    p.write_text("x\n")
    w = workers.FileWorker(str(p), interval_ms=60_000)    # would sleep a minute
    th = threading.Thread(target=w.run, daemon=True)
    th.start()
    time.sleep(0.3)
    t0 = time.monotonic()
    w.stop()
    th.join(3)
    assert not th.is_alive() and time.monotonic() - t0 < 1.5


def test_cloudflare_stop_closes_everything():
    w = workers.CloudflareWorker("t", "acc", "script")
    w._proc = MagicMock(poll=lambda: None)
    w._sock = MagicMock()
    w.stop()
    assert w._stop is True and w._wakeup.is_set()
    w._proc.terminate.assert_called_once()
    w._sock.close.assert_called_once()
