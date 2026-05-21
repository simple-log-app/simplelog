"""Unit tests for gcp_utils.py - google-cloud-* clients are mocked."""
import sys
from datetime import UTC, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import gcp_utils

# -- module-level constants ----------------------------------------------------

def test_resource_types_contains_common():
    assert "(all)" in gcp_utils.RESOURCE_TYPES
    assert "cloud_run_revision" in gcp_utils.RESOURCE_TYPES


def test_severities_lookup():
    assert gcp_utils.SEVERITIES[0] == "ALL"
    assert "ERROR" in gcp_utils.SEVERITIES


# -- build_filter --------------------------------------------------------------

def test_build_filter_all_defaults_empty():
    assert gcp_utils.build_filter() == ""


def test_build_filter_resource_type_only():
    f = gcp_utils.build_filter(resource_type="cloud_run_revision")
    assert f == 'resource.type="cloud_run_revision"'


def test_build_filter_skips_all_marker():
    assert gcp_utils.build_filter(resource_type="(all)") == ""


def test_build_filter_severity():
    assert gcp_utils.build_filter(severity="ERROR") == "severity>=ERROR"


def test_build_filter_severity_all_skipped():
    assert gcp_utils.build_filter(severity="ALL") == ""


def test_build_filter_since_iso_format():
    dt = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    f = gcp_utils.build_filter(since=dt)
    assert f == 'timestamp>="2025-01-02T03:04:05Z"'


def test_build_filter_custom_wrapped_in_parens():
    f = gcp_utils.build_filter(custom='textPayload:"hello"')
    assert f == '(textPayload:"hello")'


def test_build_filter_custom_whitespace_only_skipped():
    assert gcp_utils.build_filter(custom="   ") == ""


def test_build_filter_combined_with_AND():
    dt = datetime(2025, 1, 1, tzinfo=UTC)
    f = gcp_utils.build_filter(
        resource_type="gce_instance",
        severity="WARNING",
        custom="jsonPayload.user=admin",
        since=dt,
    )
    parts = f.split(" AND ")
    assert 'resource.type="gce_instance"' in parts
    assert "severity>=WARNING" in parts
    assert any("2025-01-01" in p for p in parts)
    assert "(jsonPayload.user=admin)" in parts


# -- _entry_to_text ------------------------------------------------------------

def _entry(payload, severity_name=None, resource_type=None):
    e = MagicMock()
    e.payload = payload
    if severity_name:
        sev = MagicMock()
        sev.name = severity_name
        e.severity = sev
    else:
        e.severity = None
    if resource_type:
        e.resource = SimpleNamespace(type=resource_type)
    else:
        e.resource = None
    return e


def test_entry_to_text_string_payload_no_meta():
    assert gcp_utils._entry_to_text(_entry("hello")) == "hello"


def test_entry_to_text_with_severity_and_resource():
    e = _entry("boom", severity_name="ERROR", resource_type="cloud_run_revision")
    assert gcp_utils._entry_to_text(e) == "[ERROR] cloud_run_revision: boom"


def test_entry_to_text_dict_payload_message_key():
    e = _entry({"message": "msg-value", "other": "x"})
    assert gcp_utils._entry_to_text(e) == "msg-value"


def test_entry_to_text_dict_payload_msg_key():
    e = _entry({"msg": "from-msg"})
    assert gcp_utils._entry_to_text(e) == "from-msg"


def test_entry_to_text_dict_payload_no_known_keys():
    e = _entry({"foo": "bar"})
    assert "foo" in gcp_utils._entry_to_text(e)


def test_entry_to_text_non_str_non_dict_payload():
    e = _entry(42)
    assert gcp_utils._entry_to_text(e) == "42"


def test_entry_to_text_resource_with_falsy_type():
    e = _entry("x", resource_type="")
    assert gcp_utils._entry_to_text(e) == "x"


# -- make_client ---------------------------------------------------------------

def _install_fake_gcp_logging(client_mock):
    """Install a fake google.cloud.logging module into sys.modules."""
    fake = MagicMock()
    fake.Client = MagicMock(return_value=client_mock)
    fake.DESCENDING = "DESCENDING"
    sys.modules["google.cloud.logging"] = fake
    sys.modules["google.cloud"] = MagicMock(logging=fake)
    return fake


def _install_fake_service_account():
    fake = MagicMock()
    fake.Credentials.from_service_account_file = MagicMock(return_value="CREDS")
    sys.modules["google.oauth2"] = MagicMock(service_account=fake)
    sys.modules["google.oauth2.service_account"] = fake
    return fake


def test_make_client_with_key_path(monkeypatch):
    client = MagicMock()
    log_mod = _install_fake_gcp_logging(client)
    sa = _install_fake_service_account()
    result = gcp_utils.make_client("proj", key_path="/k.json")
    assert result is client
    sa.Credentials.from_service_account_file.assert_called_once()
    log_mod.Client.assert_called_once_with(project="proj", credentials="CREDS")


def test_make_client_no_key_path():
    client = MagicMock()
    log_mod = _install_fake_gcp_logging(client)
    result = gcp_utils.make_client("proj")
    log_mod.Client.assert_called_once_with(project="proj")
    assert result is client


def test_make_client_wraps_exceptions():
    sys.modules.pop("google.cloud.logging", None)
    sys.modules.pop("google.cloud", None)
    sys.modules["google.cloud"] = MagicMock()
    sys.modules["google.cloud"].logging = MagicMock()
    sys.modules["google.cloud"].logging.Client = MagicMock(side_effect=Exception("boom"))
    sys.modules["google.cloud.logging"] = sys.modules["google.cloud"].logging
    with pytest.raises(RuntimeError, match="boom"):
        gcp_utils.make_client("proj")


# -- list_projects -------------------------------------------------------------

def _install_fake_resourcemanager(projects):
    """projects: list of (id, display_name)."""
    rm_client = MagicMock()
    rm_client.search_projects.return_value = [
        SimpleNamespace(project_id=pid, display_name=name) for pid, name in projects
    ]
    fake = MagicMock()
    fake.ProjectsClient = MagicMock(return_value=rm_client)
    sys.modules["google.cloud.resourcemanager_v3"] = fake
    sys.modules["google.cloud"] = MagicMock(resourcemanager_v3=fake)
    return fake, rm_client


def test_list_projects_sorted_by_name_case_insensitive():
    _install_fake_resourcemanager([("p1", "beta"), ("p2", "Alpha")])
    result = gcp_utils.list_projects()
    assert [p["name"] for p in result] == ["Alpha", "beta"]


def test_list_projects_falls_back_to_id_when_no_display_name():
    _install_fake_resourcemanager([("only-id", "")])
    result = gcp_utils.list_projects()
    assert result == [{"id": "only-id", "name": "only-id"}]


def test_list_projects_with_key_path():
    _install_fake_resourcemanager([("p", "P")])
    _install_fake_service_account()
    result = gcp_utils.list_projects(key_path="/k.json")
    assert len(result) == 1


def test_list_projects_wraps_exceptions():
    fake = MagicMock()
    fake.ProjectsClient = MagicMock(side_effect=Exception("denied"))
    sys.modules["google.cloud.resourcemanager_v3"] = fake
    sys.modules["google.cloud"] = MagicMock(resourcemanager_v3=fake)
    with pytest.raises(RuntimeError, match="denied"):
        gcp_utils.list_projects()


# -- fetch_entries -------------------------------------------------------------

def test_fetch_entries_returns_ascending_order():
    log_mod = _install_fake_gcp_logging(MagicMock())
    log_mod.DESCENDING = "DESCENDING"

    e1 = _entry("first")
    e1.timestamp = datetime(2025, 1, 1, 0, 0, 1, tzinfo=UTC)
    e2 = _entry("second")
    e2.timestamp = datetime(2025, 1, 1, 0, 0, 2, tzinfo=UTC)
    e3 = _entry("third")
    e3.timestamp = datetime(2025, 1, 1, 0, 0, 3, tzinfo=UTC)

    client = MagicMock()
    # API returns descending; fetch_entries reverses to ascending
    client.list_entries.return_value = [e3, e2, e1]

    result = gcp_utils.fetch_entries(client, "filter")
    msgs = [m for _, m in result]
    assert msgs == ["first", "second", "third"]


def test_fetch_entries_handles_missing_timestamp():
    log_mod = _install_fake_gcp_logging(MagicMock())
    log_mod.DESCENDING = "DESCENDING"

    e = _entry("no-ts")
    e.timestamp = None
    client = MagicMock()
    client.list_entries.return_value = [e]
    result = gcp_utils.fetch_entries(client, "f")
    assert result == [(0, "no-ts")]


def test_fetch_entries_wraps_exceptions():
    _install_fake_gcp_logging(MagicMock())
    client = MagicMock()
    client.list_entries.side_effect = Exception("api fail")
    with pytest.raises(RuntimeError, match="api fail"):
        gcp_utils.fetch_entries(client, "f")


def test_fetch_entries_passes_max_results_and_filter():
    log_mod = _install_fake_gcp_logging(MagicMock())
    log_mod.DESCENDING = "DESCENDING"
    client = MagicMock()
    client.list_entries.return_value = []
    gcp_utils.fetch_entries(client, "my-filter", max_results=50)
    kwargs = client.list_entries.call_args.kwargs
    assert kwargs["filter_"] == "my-filter"
    assert kwargs["max_results"] == 50
    assert kwargs["page_size"] == 50
