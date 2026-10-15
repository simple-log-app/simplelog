"""Heroku, Render, Splunk, Better Stack, Sentry and journald: clients, workers, panels."""
from __future__ import annotations

import json
import os
import time
import urllib.error
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from simplelog.core import http_utils
from simplelog.sources import (
    betterstack_utils,
    heroku_utils,
    journald_utils,
    render_utils,
    sentry_utils,
    splunk_utils,
    workers,
)


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


def _resp(payload=None, lines=None):
    """A fake urlopen() result: ``.read()`` gives JSON, iterating gives *lines*."""
    r = MagicMock()
    if payload is not None:
        r.read.return_value = json.dumps(payload).encode()
    if lines is not None:
        r.__iter__ = lambda s: iter(lines)
    r.__enter__ = lambda s: s
    r.__exit__ = MagicMock(return_value=False)
    return r


def _http_error(code, body):
    err = urllib.error.HTTPError(url="", code=code, msg="x", hdrs={}, fp=MagicMock())
    err.read = lambda: body.encode()
    return err


def _sent(mock_urlopen):
    """The Request given to the patched urlopen."""
    return mock_urlopen.call_args[0][0]


# ── http_utils ───────────────────────────────────────────────────────────────

def test_normalize_base_url():
    assert http_utils.normalize_base_url("splunk.example.com:8089/") == "https://splunk.example.com:8089"
    assert http_utils.normalize_base_url("http://h:1/path/") == "http://h:1/path"
    for bad in ("", "ftp://h", "https://"):
        with pytest.raises(RuntimeError):
            http_utils.normalize_base_url(bad)


def test_errors_carry_the_status_and_the_servers_message():
    with patch("urllib.request.urlopen", side_effect=_http_error(401, '{"message": "bad token"}')):
        with pytest.raises(RuntimeError, match="Acme 401: bad token"):
            http_utils.get_json("https://x", label="Acme")
    with patch("urllib.request.urlopen", side_effect=_http_error(500, "plain text")):
        with pytest.raises(RuntimeError, match="500: plain text"):
            http_utils.get_json("https://x", label="Acme")
    with patch("urllib.request.urlopen", side_effect=OSError("no route")):
        with pytest.raises(RuntimeError, match="Acme: no route"):
            http_utils.get_json("https://x", label="Acme")


def test_request_encodes_json_and_form_bodies():
    with patch("urllib.request.urlopen", return_value=_resp({})) as op:
        http_utils.get_json("https://x", data={"a": 1}, method="POST")
        req = _sent(op)
        assert json.loads(req.data) == {"a": 1} and req.get_header("Content-type") == "application/json"
        http_utils.get_json("https://x", form={"q": "a b"}, method="POST")
        assert _sent(op).data == b"q=a+b"


def test_tls_verification_can_be_switched_off():
    import ssl
    assert http_utils.tls_context(True) is None
    ctx = http_utils.tls_context(False)
    assert ctx.verify_mode == ssl.CERT_NONE and ctx.check_hostname is False


# ── Heroku ───────────────────────────────────────────────────────────────────

def test_heroku_lists_apps_sorted_and_sends_the_v3_headers():
    payload = [{"id": "2", "name": "zeta"}, {"id": "1", "name": "alpha"}, {"id": "3"}]
    with patch("urllib.request.urlopen", return_value=_resp(payload)) as op:
        assert [a["name"] for a in heroku_utils.list_apps("tok")] == ["alpha", "zeta"]
    req = _sent(op)
    assert req.get_header("Authorization") == "Bearer tok"
    assert "version=3" in req.get_header("Accept")


def test_heroku_log_session_requests_a_tail_and_returns_the_stream_url():
    with patch("urllib.request.urlopen",
               return_value=_resp({"logplex_url": "https://logplex/x"})) as op:
        assert heroku_utils.create_log_session("tok", "shop", lines=5000) == "https://logplex/x"
    req = _sent(op)
    assert req.full_url.endswith("/apps/shop/log-sessions") and req.get_method() == "POST"
    body = json.loads(req.data)
    assert body["tail"] is True and body["lines"] == 1500          # capped
    with patch("urllib.request.urlopen", return_value=_resp({})):
        with pytest.raises(RuntimeError, match="no log stream"):
            heroku_utils.create_log_session("tok", "shop")


def test_heroku_parse_line():
    assert heroku_utils.parse_line("2024-05-01T12:00:00.123456+00:00 app[web.1]: hi") == (
        1714564800123, "app[web.1]: hi")
    ts, msg = heroku_utils.parse_line("not a stamped line")
    assert msg == "not a stamped line" and ts > 0
    assert heroku_utils.parse_line("  \n") is None


def test_heroku_worker_streams_then_reports_a_closed_stream():
    stream = [b"2024-05-01T12:00:00+00:00 app[web.1]: one\n", b"2024-05-01T12:00:01+00:00 app[web.1]: two\n"]
    got, errors = [], []
    w = workers.HerokuWorker("tok", "shop")
    w.new_lines.connect(lambda ev: got.extend(ev))
    w.error.connect(errors.append)
    with patch("simplelog.sources.heroku_utils.create_log_session", return_value="https://logplex/x") as sess, \
            patch("simplelog.sources.heroku_utils.open_log_stream", return_value=iter(stream)):
        w.run()
    assert [m for _, m in got] == ["app[web.1]: one", "app[web.1]: two"]
    assert sess.call_args.kwargs["tail"] is True
    assert errors and "closed" in errors[0].lower()        # lets the tab reconnect


def test_heroku_worker_stays_quiet_when_stopped():
    w = workers.HerokuWorker("tok", "shop")
    errors = []
    w.error.connect(errors.append)
    w.stop()
    with patch("simplelog.sources.heroku_utils.create_log_session", return_value="u"), \
            patch("simplelog.sources.heroku_utils.open_log_stream", return_value=iter([])):
        w.run()
    assert errors == []


# ── Render ───────────────────────────────────────────────────────────────────

def test_render_lists_services_in_both_shapes():
    payload = [{"service": {"id": "srv-1", "name": "web", "type": "web_service", "ownerId": "o1"},
                "cursor": "c"},
               {"id": "srv-2", "name": "api", "type": "", "ownerId": "o1"},
               {"service": {"id": "srv-3"}}]
    with patch("urllib.request.urlopen", return_value=_resp(payload)):
        services = render_utils.list_services("key")
    assert [(s["name"], s["owner_id"]) for s in services] == [("api", "o1"), ("web", "o1")]


def test_render_logs_are_paged_sorted_and_carry_the_level():
    page1 = {"hasMore": True, "nextStartTime": "2024-05-01T12:00:02Z", "nextEndTime": "2024-05-01T13:00:00Z",
             "logs": [{"message": "second", "timestamp": "2024-05-01T12:00:01Z",
                       "labels": [{"name": "level", "value": "error"}]}]}
    page2 = {"hasMore": False,
             "logs": [{"message": "first", "timestamp": "2024-05-01T12:00:00Z", "labels": []},
                      {"message": "", "timestamp": "2024-05-01T12:00:00Z"}]}
    with patch("urllib.request.urlopen", side_effect=[_resp(page1), _resp(page2)]) as op:
        events = render_utils.fetch_logs("key", "own", "srv-1", 1714564700000)
    assert events == [(1714564800000, "first"), (1714564801000, "[error] second")]
    first_url = op.call_args_list[0][0][0].full_url
    assert "ownerId=own" in first_url and "resource=srv-1" in first_url and "direction=forward" in first_url
    assert "startTime=2024-05-01T12%3A00%3A02" in op.call_args_list[1][0][0].full_url


def test_render_worker_fetches_a_window_then_only_what_is_new(monkeypatch):
    calls = []

    def fetch(key, owner, resource, start_ms, *a, **k):
        calls.append(start_ms)
        return [(5000, "a"), (6000, "b")] if len(calls) == 1 else [(6000, "b"), (7000, "c")]

    monkeypatch.setattr(render_utils, "fetch_logs", fetch)
    w = workers.RenderWorker("k", "o", "r", "api", lookback_s=60)
    assert [m for _, m in w._fetch_history()] == ["a", "b"]
    assert [m for _, m in w._fetch_new()] == ["c"]                    # "b" is not repeated
    assert calls[1] == 6000 - 2000


# ── Splunk ───────────────────────────────────────────────────────────────────

def test_splunk_server_name_and_auth_headers():
    info = {"entry": [{"content": {"serverName": "splunk-1"}}]}
    with patch("urllib.request.urlopen", return_value=_resp(info)) as op:
        assert splunk_utils.server_name("splunk:8089", token="T") == "splunk-1"
    assert _sent(op).get_header("Authorization") == "Bearer T"
    with patch("urllib.request.urlopen", return_value=_resp(info)) as op:
        splunk_utils.server_name("https://splunk:8089", username="u", password="p")
    assert _sent(op).get_header("Authorization").startswith("Basic ")
    with pytest.raises(RuntimeError, match="authentication token"):
        splunk_utils.server_name("https://splunk:8089")


def test_splunk_export_parses_events_and_adds_the_search_prefix():
    lines = [
        json.dumps({"preview": False, "result": {"_time": "2024-05-01T12:00:02.000+00:00", "_raw": "later"}}).encode(),
        json.dumps({"preview": False, "result": {"_time": "2024-05-01T12:00:01.000+00:00", "_raw": "earlier"}}).encode(),
        b"", b"not json", json.dumps({"lastrow": True}).encode(),
    ]
    with patch("urllib.request.urlopen", return_value=_resp(lines=lines)) as op:
        events = splunk_utils.export_search("https://s:8089", "index=main error", 1714564700.0, token="T")
    assert [m for _, m in events] == ["earlier", "later"]
    form = _sent(op).data.decode()
    assert "search=search+index%3Dmain+error" in form and "output_mode=json" in form
    assert "earliest_time=1714564700.000" in form
    with patch("urllib.request.urlopen", return_value=_resp(lines=[])) as op:
        splunk_utils.export_search("https://s:8089", "| tstats count", 0, token="T")
    assert "search=%7C+tstats" in _sent(op).data.decode()            # pipelines are left alone


def test_splunk_export_honours_the_limit():
    lines = [json.dumps({"result": {"_time": "2024-05-01T12:00:00Z", "_raw": f"l{i}"}}).encode()
             for i in range(10)]
    with patch("urllib.request.urlopen", return_value=_resp(lines=lines)):
        assert len(splunk_utils.export_search("https://s", "*", 0, token="T", limit=3)) == 3


def test_splunk_can_skip_certificate_verification():
    with patch("urllib.request.urlopen", return_value=_resp(lines=[])) as op:
        splunk_utils.export_search("https://s", "*", 0, token="T", verify_tls=False)
    assert op.call_args.kwargs["context"] is not None
    with patch("urllib.request.urlopen", return_value=_resp(lines=[])) as op:
        splunk_utils.export_search("https://s", "*", 0, token="T")
    assert op.call_args.kwargs["context"] is None


# ── Better Stack ─────────────────────────────────────────────────────────────

def test_betterstack_table_names_are_checked_before_reaching_the_sql():
    assert betterstack_utils.valid_table("t123456_my_source_logs")
    for bad in ("", "x; DROP TABLE y", "a b", "1abc", "a-b", "a'b"):
        assert not betterstack_utils.valid_table(bad)
        with pytest.raises(RuntimeError, match="invalid table"):
            betterstack_utils.fetch_logs("h", "u", "p", bad, 0)


def test_betterstack_fetch_builds_the_query_and_reads_json_rows():
    rows = [json.dumps({"dt": "2024-05-01 12:00:00.250", "raw": '{"message": "hi"}'}).encode(),
            json.dumps({"dt": "2024-05-01 12:00:01.000", "raw": {"nested": 1}}).encode()]
    with patch("urllib.request.urlopen", return_value=_resp(lines=rows)) as op:
        events = betterstack_utils.fetch_logs(
            "eu-nbg-2-connect.betterstackdata.com", "u", "p", "t1_src_logs", 1714564700000, limit=50)
    assert events == [(1714564800250, '{"message": "hi"}'), (1714564801000, '{"nested": 1}')]
    req = _sent(op)
    sql = req.data.decode()
    assert urlparse(req.full_url).hostname == "eu-nbg-2-connect.betterstackdata.com"
    assert "FROM remote(t1_src_logs)" in sql and "dt > toDateTime64('2024-05-01 11:58:20.000'" in sql
    assert "LIMIT 50" in sql and sql.endswith("FORMAT JSONEachRow")
    assert req.get_header("Authorization").startswith("Basic ")


def test_betterstack_garbage_answer_is_an_error():
    with patch("urllib.request.urlopen", return_value=_resp(lines=[b"Code: 516 Authentication failed"])):
        with pytest.raises(RuntimeError, match="unexpected answer"):
            betterstack_utils.check("h", "u", "p", "t1_src_logs")


# ── Sentry ───────────────────────────────────────────────────────────────────

def test_sentry_projects_and_event_formatting():
    projects = [{"slug": "web", "name": "Web", "organization": {"slug": "acme"}},
                {"slug": "api", "organization": {"slug": "acme"}}, {"slug": "orphan"}]
    with patch("urllib.request.urlopen", return_value=_resp(projects)) as op:
        listed = sentry_utils.list_projects("tok", "https://sentry.example.com/")
    assert [(p["org"], p["slug"]) for p in listed] == [("acme", "api"), ("acme", "web")]
    assert _sent(op).full_url == "https://sentry.example.com/api/0/projects/"
    ts, text = sentry_utils.format_event({
        "title": "ValueError: x", "culprit": "app.views", "dateCreated": "2024-05-01T12:00:00Z",
        "tags": [{"key": "level", "value": "error"}]})
    assert (ts, text) == (1714564800000, "[error] ValueError: x  app.views")
    assert sentry_utils.format_event({"message": "m"})[1] == "m"


def test_sentry_events_request_and_slug_validation():
    events = [{"title": "b", "dateCreated": "2024-05-01T12:00:01Z"},
              {"title": "a", "dateCreated": "2024-05-01T12:00:00Z"}]
    with patch("urllib.request.urlopen", return_value=_resp(events)) as op:
        got = sentry_utils.fetch_events("tok", "acme", "web", 1714564700000)
    assert [m for _, m in got] == ["a", "b"]
    assert "/api/0/projects/acme/web/events/?start=2024-05-01T11%3A58%3A20" in _sent(op).full_url
    with pytest.raises(RuntimeError, match="invalid"):
        sentry_utils.fetch_events("tok", "../evil", "web", 0)


# ── journald ─────────────────────────────────────────────────────────────────

def test_journald_command_and_validation():
    cmd = journald_utils.command("nginx.service", "err", 120)
    assert cmd[:3] == ["journalctl", "--no-pager", "--follow"]
    assert "--since=-120s" in cmd and "--unit=nginx.service" in cmd and "--priority=err" in cmd
    assert not any(a.startswith("--unit") for a in journald_utils.command())
    for bad_unit in ("--vacuum-size=1", "a b", "x;y"):
        with pytest.raises(RuntimeError):
            journald_utils.command(bad_unit)
    with pytest.raises(RuntimeError):
        journald_utils.command("", "loud")


def test_journald_parse_line():
    assert journald_utils.parse_line("2024-05-01T12:00:00.123456+00:00 host nginx[1]: hi") == (
        1714564800123, "host nginx[1]: hi")
    assert journald_utils.parse_line("-- Journal begins at Mon --") is None
    assert journald_utils.parse_line("") is None
    assert journald_utils.parse_line("odd line")[1] == "odd line"


def test_journald_worker_command_and_parsing():
    w = workers.JournaldWorker("sshd.service", "warning", 300)
    assert "--unit=sshd.service" in w._command() and "--since=-300s" in w._command()
    events = w._parse(["2024-05-01T12:00:00+00:00 h sshd[1]: x", "", "-- header --"])
    assert [m for _, m in events] == ["h sshd[1]: x"]
    assert "sshd.service" in w._start_status()


# ── polling workers share the same dedupe logic ──────────────────────────────

def test_splunk_and_betterstack_and_sentry_workers_only_emit_new_events(monkeypatch):
    seq = [[(1000, "a"), (2000, "b")], [(2000, "b"), (3000, "c")]]
    monkeypatch.setattr(splunk_utils, "export_search", lambda *a, **k: seq.pop(0))
    sp = workers.SplunkWorker("https://s", "*", token="t", lookback_s=60)
    assert [m for _, m in sp._fetch_history()] == ["a", "b"]
    assert [m for _, m in sp._fetch_new()] == ["c"]

    seq2 = [[(1000, "a")], [(1000, "a"), (1500, "b")]]
    monkeypatch.setattr(betterstack_utils, "fetch_logs", lambda *a, **k: seq2.pop(0))
    bs = workers.BetterStackWorker("h", "u", "p", "t1_x_logs", lookback_s=60)
    assert [m for _, m in bs._fetch_history()] == ["a"]
    assert [m for _, m in bs._fetch_new()] == ["b"]

    seq3 = [[(1000, "e1")], [(1000, "e1"), (9000, "e2")]]
    monkeypatch.setattr(sentry_utils, "fetch_events", lambda *a, **k: seq3.pop(0))
    se = workers.SentryWorker("t", "o", "p", lookback_s=60)
    assert [m for _, m in se._fetch_history()] == ["e1"]
    assert [m for _, m in se._fetch_new()] == ["e2"]


def test_a_failing_poll_is_retried_not_fatal(monkeypatch):
    w = workers.SentryWorker("t", "o", "p", interval_s=0.001)
    w._MAX_FAILS = 3
    errors, statuses = [], []
    w.error.connect(errors.append)
    w.status.connect(statuses.append)
    state = {"n": 0}

    def fetch(*a, **k):
        state["n"] += 1
        if state["n"] == 1:
            return []                       # history
        raise RuntimeError("boom")

    monkeypatch.setattr(sentry_utils, "fetch_events", fetch)
    w.run()
    assert errors == ["boom"] and any("retrying" in s for s in statuses)
