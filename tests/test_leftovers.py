"""Azure newest-first history, Railway incremental logs, update checksum verification."""
import hashlib
import io
import os
import urllib.error
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from simplelog.sources import azure_utils, railway_utils, workers

# ── Azure ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query,flipped", [
    ("AppTraces\n| order by TimeGenerated asc\n| limit 50", True),
    ("AppTraces | sort by TimeGenerated ASC | take 5", True),
    ("AppTraces\n| order by TimeGenerated asc", False),         # no cap: every row is loaded
    ("AppTraces\n| order by TimeGenerated desc\n| take 5", False),
])
def test_user_queries_that_cap_rows_load_the_newest_page(query, flipped):
    assert (" desc" in azure_utils._newest_first(query)) is (flipped or "desc" in query)


def test_default_table_query_is_newest_first_and_history_is_sorted(monkeypatch):
    assert "order by TimeGenerated desc" in azure_utils.build_table_query("AppTraces")
    monkeypatch.setattr(azure_utils, "_run_query", lambda *a: [(30, "c"), (10, "a"), (20, "b")])
    assert azure_utils.fetch_logs(None, "ws", "T") == [(10, "a"), (20, "b"), (30, "c")]


# ── Railway ──────────────────────────────────────────────────────────────────

def test_railway_polls_ask_only_for_new_logs(monkeypatch):
    seen = {}
    monkeypatch.setattr(railway_utils, "_gql",
                        lambda q, t, v=None, **k: seen.update(q=q, v=v) or {"deploymentLogs": []})
    railway_utils.fetch_deployment_logs("t", "d", since_ms=1_700_000_000_000)
    assert "startDate" in seen["q"] and seen["v"]["start"] == "2023-11-14T22:13:20.000Z"


def test_railway_falls_back_when_the_schema_has_no_start_date(monkeypatch):
    calls = []

    def gql(q, t, v=None, **k):
        calls.append(q)
        if "startDate" in q:
            raise RuntimeError('Unknown argument "startDate"')
        return {"deploymentLogs": [{"message": "x", "timestamp": "2024-01-01T00:00:00Z"}]}

    monkeypatch.setattr(railway_utils, "_gql", gql)
    assert railway_utils.fetch_deployment_logs("t", "d", since_ms=5)[0][1] == "x"
    assert len(calls) == 2


def test_railway_real_errors_are_not_swallowed(monkeypatch):
    monkeypatch.setattr(railway_utils, "_gql", MagicMock(side_effect=RuntimeError("Not Authorized")))
    with pytest.raises(RuntimeError, match="Not Authorized"):
        railway_utils.fetch_deployment_logs("t", "d", since_ms=5)


def test_railway_worker_passes_its_cursor(monkeypatch):
    w = workers.RailwayWorker("t", "p", "s", "sid")
    got = []
    monkeypatch.setattr(railway_utils, "get_latest_deployment", lambda *a: {"id": "d"})
    monkeypatch.setattr(railway_utils, "fetch_deployment_logs",
                        lambda tok, d, since=None: got.append(since) or [(1_000_000, "a")])
    now = int(datetime.now(UTC).timestamp() * 1000)
    monkeypatch.setattr(railway_utils, "fetch_deployment_logs",
                        lambda tok, d, since=None: got.append(since) or [(now, "a")])
    w._fetch_history()
    w._fetch_new()
    assert got[0] is None and got[1] == now - 60_000


# ── Update checksum ──────────────────────────────────────────────────────────

class _Resp(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _download(tmp_path, payload, sums):
    url = "https://github.com/o/r/releases/download/v1/app.deb"

    def opener(req, timeout=0):
        if req.full_url.endswith("SHA256SUMS"):
            if isinstance(sums, Exception):
                raise sums
            return _Resp(sums.encode())
        return _Resp(payload)

    w = workers.DownloadWorker(url, str(tmp_path / "app.deb"), "1.0")
    done, errors = [], []
    w.finished.connect(done.append)
    w.error.connect(errors.append)
    with patch("simplelog.sources.workers.urllib.request.urlopen", opener):
        w.run()
    return done, errors


def test_matching_checksum_is_accepted(tmp_path):
    data = b"payload"
    sums = f"{hashlib.sha256(data).hexdigest()}  app.deb\nffff  other\n"
    done, errors = _download(tmp_path, data, sums)
    assert done and not errors


def test_wrong_checksum_discards_the_download(tmp_path):
    done, errors = _download(tmp_path, b"payload", f"{'0' * 64}  app.deb\n")
    assert not done and len(errors) == 1
    assert not (tmp_path / "app.deb").exists()


def test_releases_without_checksums_still_install(tmp_path):
    err = urllib.error.HTTPError("u", 404, "nf", {}, None)
    done, errors = _download(tmp_path, b"payload", err)
    assert done and not errors


def test_other_http_errors_stop_the_update(tmp_path):
    err = urllib.error.HTTPError("u", 500, "boom", {}, None)
    done, errors = _download(tmp_path, b"payload", err)
    assert not done and errors
