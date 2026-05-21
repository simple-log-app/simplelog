"""Unit tests for azure_utils.py - azure SDK is mocked."""
import sys
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import azure_utils

# -- constants -----------------------------------------------------------------

def test_tables_grouped():
    assert "Application" in azure_utils.TABLES
    assert "Security" in azure_utils.TABLES
    assert "AppTraces" in azure_utils.TABLES["Application"]


# -- build_table_query ---------------------------------------------------------

def test_build_table_query_without_since():
    q = azure_utils.build_table_query("AppTraces")
    assert "AppTraces" in q
    assert "ago(1h)" in q
    assert "limit 500" in q


def test_build_table_query_with_since():
    dt = datetime(2025, 1, 2, 3, 4, 5, 123000, tzinfo=UTC)
    q = azure_utils.build_table_query("AppRequests", since_dt=dt, limit=100)
    assert "AppRequests" in q
    assert "datetime(2025-01-02T03:04:05.123Z)" in q
    assert "limit 100" in q
    assert "ago(1h)" not in q


def test_build_table_query_custom_limit():
    q = azure_utils.build_table_query("Heartbeat", limit=42)
    assert "limit 42" in q


# -- make_credential / make_logs_client (mock the azure modules) ---------------

def _install_fake_identity():
    fake_id = MagicMock()
    fake_id.ClientSecretCredential = MagicMock(return_value="CRED")
    sys.modules["azure.identity"] = fake_id
    return fake_id


def _install_fake_query(query_client=None, status_constants=None):
    fake = MagicMock()
    fake.LogsQueryClient = MagicMock(return_value=query_client or MagicMock())
    if status_constants:
        fake.LogsQueryStatus = status_constants
    else:
        sentinel = SimpleNamespace(PARTIAL="PARTIAL", SUCCESS="SUCCESS")
        fake.LogsQueryStatus = sentinel
    sys.modules["azure.monitor.query"] = fake
    return fake


def test_make_credential_success():
    fake = _install_fake_identity()
    result = azure_utils.make_credential("tenant", "client", "secret")
    assert result == "CRED"
    fake.ClientSecretCredential.assert_called_once_with(
        tenant_id="tenant", client_id="client", client_secret="secret"
    )


def test_make_credential_wraps_exceptions():
    fake = MagicMock()
    fake.ClientSecretCredential = MagicMock(side_effect=Exception("boom"))
    sys.modules["azure.identity"] = fake
    with pytest.raises(RuntimeError, match="boom"):
        azure_utils.make_credential("t", "c", "s")


def test_make_logs_client_success():
    qc = MagicMock()
    fake = _install_fake_query(query_client=qc)
    result = azure_utils.make_logs_client("CRED")
    assert result is qc
    fake.LogsQueryClient.assert_called_once_with("CRED")


def test_make_logs_client_wraps_exceptions():
    fake = MagicMock()
    fake.LogsQueryClient = MagicMock(side_effect=Exception("oops"))
    sys.modules["azure.monitor.query"] = fake
    with pytest.raises(RuntimeError, match="oops"):
        azure_utils.make_logs_client("c")


# -- _run_query / fetch_logs ---------------------------------------------------

def _make_table(col_names, rows):
    cols = [SimpleNamespace(name=n) for n in col_names]
    return SimpleNamespace(columns=cols, rows=rows)


def _make_response(status, tables=None, partial_data=None, partial_error=None):
    r = SimpleNamespace(
        status=status,
        tables=tables or [],
        partial_data=partial_data or [],
        partial_error=partial_error,
    )
    return r


def test_run_query_success_with_message_col():
    fake = _install_fake_query()
    client = MagicMock()
    table = _make_table(
        ["TimeGenerated", "Message"],
        [
            [datetime(2025, 1, 1, 0, 0, 1, tzinfo=UTC), "hello"],
            [datetime(2025, 1, 1, 0, 0, 2, tzinfo=UTC), "world"],
        ],
    )
    client.query_workspace.return_value = _make_response(
        fake.LogsQueryStatus.SUCCESS, tables=[table]
    )
    result = azure_utils._run_query(client, "ws", "Q", timedelta(hours=1))
    assert len(result) == 2
    assert result[0][1] == "hello"
    assert result[1][1] == "world"
    assert result[0][0] > 0


def test_run_query_partial_uses_partial_data():
    fake = _install_fake_query()
    client = MagicMock()
    table = _make_table(["TimeGenerated", "Message"], [[None, "partial"]])
    client.query_workspace.return_value = _make_response(
        fake.LogsQueryStatus.PARTIAL, partial_data=[table]
    )
    result = azure_utils._run_query(client, "ws", "Q", timedelta(hours=1))
    assert result == [(0, "partial")]


def test_run_query_failure_status_raises():
    _install_fake_query()
    client = MagicMock()
    client.query_workspace.return_value = SimpleNamespace(
        status="FAIL", tables=[], partial_data=[], partial_error="bad"
    )
    with pytest.raises(RuntimeError, match="Azure query failed"):
        azure_utils._run_query(client, "ws", "Q", timedelta(hours=1))


def test_run_query_wraps_client_exception():
    _install_fake_query()
    client = MagicMock()
    client.query_workspace.side_effect = Exception("net")
    with pytest.raises(RuntimeError, match="net"):
        azure_utils._run_query(client, "ws", "Q", timedelta(hours=1))


def test_run_query_no_tables_returns_empty():
    fake = _install_fake_query()
    client = MagicMock()
    client.query_workspace.return_value = _make_response(fake.LogsQueryStatus.SUCCESS, tables=[])
    assert azure_utils._run_query(client, "ws", "Q", timedelta(hours=1)) == []


def test_run_query_falls_back_to_pairs_when_no_message_col():
    fake = _install_fake_query()
    client = MagicMock()
    table = _make_table(
        ["TimeGenerated", "TenantId", "Foo", "Bar"],
        [[datetime(2025, 1, 1, tzinfo=UTC), "tid", "f1", "b1"]],
    )
    client.query_workspace.return_value = _make_response(
        fake.LogsQueryStatus.SUCCESS, tables=[table]
    )
    result = azure_utils._run_query(client, "ws", "Q", timedelta(hours=1))
    assert len(result) == 1
    msg = result[0][1]
    assert "Foo=f1" in msg
    assert "Bar=b1" in msg
    # TimeGenerated and TenantId are filtered out
    assert "TimeGenerated=" not in msg
    assert "TenantId=" not in msg


def test_run_query_iso_string_timestamp():
    fake = _install_fake_query()
    client = MagicMock()
    table = _make_table(
        ["TimeGenerated", "Message"],
        [["2025-01-01T00:00:00Z", "iso"]],
    )
    client.query_workspace.return_value = _make_response(
        fake.LogsQueryStatus.SUCCESS, tables=[table]
    )
    result = azure_utils._run_query(client, "ws", "Q", timedelta(hours=1))
    assert result[0][0] > 0
    assert result[0][1] == "iso"


def test_run_query_invalid_iso_string_gives_zero_ts():
    fake = _install_fake_query()
    client = MagicMock()
    table = _make_table(["TimeGenerated", "Message"], [["not-a-date", "msg"]])
    client.query_workspace.return_value = _make_response(
        fake.LogsQueryStatus.SUCCESS, tables=[table]
    )
    result = azure_utils._run_query(client, "ws", "Q", timedelta(hours=1))
    assert result == [(0, "msg")]


def test_run_query_skips_empty_messages():
    fake = _install_fake_query()
    client = MagicMock()
    table = _make_table(
        ["TimeGenerated", "Message"],
        [[datetime(2025, 1, 1, tzinfo=UTC), ""]],
    )
    client.query_workspace.return_value = _make_response(
        fake.LogsQueryStatus.SUCCESS, tables=[table]
    )
    assert azure_utils._run_query(client, "ws", "Q", timedelta(hours=1)) == []


# -- fetch_logs / fetch_logs_since / verify_credential -------------------------

def test_fetch_logs_delegates_to_run_query():
    fake = _install_fake_query()
    client = MagicMock()
    table = _make_table(
        ["TimeGenerated", "Message"],
        [[datetime(2025, 1, 1, tzinfo=UTC), "x"]],
    )
    client.query_workspace.return_value = _make_response(
        fake.LogsQueryStatus.SUCCESS, tables=[table]
    )
    result = azure_utils.fetch_logs(client, "ws", "Heartbeat", timespan_hours=2.0)
    assert result == [(result[0][0], "x")]
    timespan = client.query_workspace.call_args.kwargs["timespan"]
    assert timespan == timedelta(hours=2.0)


def test_fetch_logs_since_replaces_existing_where():
    fake = _install_fake_query()
    client = MagicMock()
    client.query_workspace.return_value = _make_response(
        fake.LogsQueryStatus.SUCCESS, tables=[]
    )
    dt = datetime(2025, 5, 10, 12, 0, 0, 0, tzinfo=UTC)
    azure_utils.fetch_logs_since(
        client,
        "ws",
        "Heartbeat\n| where TimeGenerated > ago(1h)\n| limit 10",
        dt,
    )
    query = client.query_workspace.call_args.kwargs["query"]
    assert "2025-05-10T12:00:00.000Z" in query
    # original "ago(1h)" line was replaced
    assert "ago(1h)" not in query


def test_fetch_logs_since_injects_when_missing():
    fake = _install_fake_query()
    client = MagicMock()
    client.query_workspace.return_value = _make_response(
        fake.LogsQueryStatus.SUCCESS, tables=[]
    )
    dt = datetime(2025, 5, 10, 12, 0, 0, 0, tzinfo=UTC)
    azure_utils.fetch_logs_since(client, "ws", "AppTraces\n| limit 10", dt)
    query = client.query_workspace.call_args.kwargs["query"]
    lines = query.splitlines()
    assert lines[0] == "AppTraces"
    assert "TimeGenerated > datetime(" in lines[1]


def test_verify_credential_runs_a_query():
    fake = _install_fake_query()
    client = MagicMock()
    client.query_workspace.return_value = _make_response(
        fake.LogsQueryStatus.SUCCESS, tables=[]
    )
    fake.LogsQueryClient = MagicMock(return_value=client)
    azure_utils.verify_credential("CRED", "ws-id")
    client.query_workspace.assert_called_once()
    query = client.query_workspace.call_args.kwargs["query"]
    assert "Heartbeat" in query
