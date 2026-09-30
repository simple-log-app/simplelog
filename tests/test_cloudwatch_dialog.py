"""Tests for saving / reopening a CloudWatch connection in AddConnectionDialog."""
import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

import profiles_store


@pytest.fixture
def cw_env(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841 — keep alive
    monkeypatch.setattr(profiles_store, "_DIR", tmp_path)
    with patch("cloudwatch.list_profiles", return_value=[]), \
         patch("cloudwatch.make_client", return_value=MagicMock()), \
         patch("cloudwatch.list_log_groups", return_value=["/app/a", "/app/b"]), \
         patch("cloudwatch.list_log_streams", return_value=["s1", "s2"]):
        yield


def test_save_and_open_stores_full_cloudwatch_config(cw_env):
    import ui

    dlg = ui.AddConnectionDialog(preselect="cloudwatch")
    p = dlg._cw_embedded_panel
    p._auth_mode_combo.setCurrentIndex(1)
    p.access_key_input.setText("AKIA")
    p.secret_key_input.setText("secret")
    p._on_connect()
    p.group_list.setCurrentRow(1)
    p.stream_list.setCurrentRow(2)
    p.filter_input.setText("ERROR")
    dlg._fields["name"].setText("prod")

    dlg._on_save_open()

    [saved] = profiles_store.load_all("cloudwatch")
    assert saved["name"] == "prod"
    assert saved["access_key_id"] == "AKIA"
    assert saved["secret_key"] == "secret"
    assert saved["group"] == "/app/b"
    assert saved["stream"] == "s2"
    assert saved["filter"] == "ERROR"


def test_reopen_saved_cloudwatch_connection_is_ready_to_open(cw_env):
    import ui

    profile = {
        "name": "prod", "region": "eu-west-1",
        "access_key_id": "AKIA", "secret_key": "secret",
        "group": "/app/b", "stream": "s2", "filter": "ERROR",
        "interval": 7, "lookback": 21600,
    }
    dlg = ui.AddConnectionDialog(preselect="cloudwatch", prefill_profile=profile)
    p = dlg._cw_embedded_panel

    assert p._auth_mode_combo.currentIndex() == 1
    assert p.access_key_input.text() == "AKIA"
    assert p.secret_key_input.text() == "secret"
    assert p.region_combo.currentText() == "eu-west-1"
    assert p.filter_input.text() == "ERROR"
    assert p.interval_spin.value() == 7
    assert p.lookback_combo.currentData() == 21600

    QApplication.processEvents()  # runs the deferred auto-connect

    assert p.group_list.currentItem().text() == "/app/b"
    assert p.stream_list.currentItem().text() == "s2"
    assert dlg._open_btn.isEnabled()
