"""Low-severity audit bugs: Azure filter injection, Railway/CloudWatch de-duplication."""
import os
from datetime import UTC, datetime
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import azure_utils
import workers

DT = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)


def _injected(query):
    client = MagicMock()
    client.query_workspace.return_value = MagicMock(tables=[], status=None)
    seen = {}
    orig = azure_utils._run_query
    azure_utils._run_query = lambda c, w, q, t: seen.setdefault("q", q) and []
    try:
        azure_utils.fetch_logs_since(client, "ws", query, DT)
    finally:
        azure_utils._run_query = orig
    return seen["q"]


def test_azure_filter_after_table_on_one_line_query():
    q = _injected("AppTraces | take 10")
    assert q.splitlines()[0] == "AppTraces"
    assert q.splitlines()[1].startswith("| where TimeGenerated > datetime(")
    assert q.splitlines()[2] == "| take 10"


def test_azure_filter_before_take_on_first_line():
    q = _injected("AppTraces | take 5\n| project Message")
    assert q.index("where TimeGenerated") < q.index("take 5")


def test_azure_filter_after_let_statements():
    q = _injected("let x = 1;\nAppTraces\n| project Message")
    assert q.startswith("let x = 1;")
    assert q.index("AppTraces") < q.index("where TimeGenerated") < q.index("project")


def test_azure_filter_table_only():
    q = _injected("AppTraces")
    assert q.splitlines() == [q.splitlines()[0], q.splitlines()[1]]
    assert q.splitlines()[0] == "AppTraces"


def test_azure_existing_filter_replaced():
    q = _injected("AppTraces\n| where TimeGenerated > ago(1h)\n| take 3")
    assert "ago(1h)" not in q and q.count("TimeGenerated") == 1


def test_railway_dedup_is_bounded_and_skips_known(monkeypatch):
    import railway_utils
    w = workers.RailwayWorker("t", "p", "s", "sid", interval_s=1)
    monkeypatch.setattr(railway_utils, "get_latest_deployment", lambda *a: {"id": "d1"})
    now = int(__import__("time").time() * 1000)
    batches = [[(now, "a"), (now + 1, "b")],
               [(now, "a"), (now + 1, "b"), (now + 200_000, "c")]]
    monkeypatch.setattr(railway_utils, "fetch_deployment_logs", lambda *a: batches.pop(0))
    assert w._fetch_history() == [(now, "a"), (now + 1, "b")]
    assert w._fetch_new() == [(now + 200_000, "c")]
    assert len(w._dedup._seen) == 1          # old entries were forgotten


def test_cloudwatch_late_event_is_not_lost(monkeypatch):
    import cloudwatch
    w = workers.TailWorker(MagicMock(), "g", "s", "", 1, 3600)
    calls = []
    results = [[(10_000, "a")], [(10_000, "a"), (8_000, "late"), (11_000, "b")]]

    def fetch(client, group, stream, start_ms=None, **kw):
        calls.append(start_ms)
        return results.pop(0)

    monkeypatch.setattr(cloudwatch, "fetch_events", fetch)
    w._fetch_history()
    new = w._fetch_new()
    assert calls[1] <= 8_000                 # the poll overlaps the previous one
    assert (8_000, "late") in new and (10_000, "a") not in new
