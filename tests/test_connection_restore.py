"""Tests for saving / restoring the full selection of embedded providers in AddConnectionDialog."""
import os
import sys
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QListWidget, QSpinBox

import profiles_store

PROVIDERS = [
    "ssh", "vercel", "gcp", "azure", "loki", "datadog",
    "elastic", "railway", "flyio", "kubernetes", "cloudflare",
]

RAILWAY_PROJECTS = [
    {"name": "shop", "services": [{"name": "api", "id": "s1"}, {"name": "web", "id": "s2"}]},
    {"name": "blog", "services": [{"name": "front", "id": "s3"}, {"name": "worker", "id": "s4"}]},
]


@pytest.fixture
def env(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841 — keep alive
    monkeypatch.setattr(profiles_store, "_DIR", tmp_path)
    # kubectl may be absent on the test machine: simulate it
    with patch("kubernetes_utils.is_available", return_value=True), \
         patch("kubernetes_utils.list_contexts", return_value=[]), \
         patch("kubernetes_utils.current_context", return_value=""):
        yield


# ── Helpers ───────────────────────────────────────────────────────────────────

def test_list_state_matches_on_name_and_ignores_status(env):
    import ui

    lst = QListWidget()
    lst.addItems(["pod-a  (Running)", "pod-b  (Pending)"])
    assert ui._restore_widget_state(lst, "pod-b  (Running)")
    assert ui._widget_state(lst) == "pod-b  (Pending)"


def test_list_state_waits_until_item_is_listed(env):
    import ui

    lst = QListWidget()
    assert not ui._restore_widget_state(lst, "api")
    lst.addItem("api")
    assert ui._restore_widget_state(lst, "api")


def test_spinbox_state_roundtrip(env):
    import ui

    spin = QSpinBox()
    spin.setRange(1, 60)
    assert ui._restore_widget_state(spin, 12)
    assert ui._widget_state(spin) == 12


@pytest.mark.parametrize("provider", PROVIDERS)
def test_every_saved_state_attr_exists(env, provider):
    import ui

    dlg = ui.AddConnectionDialog(preselect=provider)
    assert dlg._embedded_state_attrs, f"{provider} saves no selection"
    for attr in dlg._embedded_state_attrs:
        ui._widget_state(getattr(dlg._embedded_panel, attr))


# ── Save → reopen ─────────────────────────────────────────────────────────────

def test_railway_save_then_reopen_restores_project_and_service(env):
    import ui

    with patch.object(ui.RailwayPanel, "_do_connect",
                      lambda self: self._on_connected_railway(RAILWAY_PROJECTS)):
        dlg = ui.AddConnectionDialog(preselect="railway")
        p = dlg._embedded_panel
        p._railway_token_input.setText("tok")
        p._do_connect()
        p._project_list.setCurrentRow(1)
        p._service_list.setCurrentRow(1)
        p._interval_spin_railway.setValue(9)
        dlg._fields["name"].setText("blog")
        dlg._on_save_open()

        [saved] = profiles_store.load_all("railway")
        assert saved["token"] == "tok"
        assert saved["state"]["_project_list"] == "blog"
        assert saved["state"]["_service_list"] == "worker"

        dlg2 = ui.AddConnectionDialog(preselect="railway", prefill_profile=saved)
        dlg2._sync_embedded_footer()
        p2 = dlg2._embedded_panel
        assert p2._project_list.currentItem().text() == "blog"
        assert p2._service_list.currentItem().text() == "worker"
        assert p2._interval_spin_railway.value() == 9
        assert dlg2._open_btn.isEnabled()


def test_kubernetes_reopen_restores_namespace_and_pod(env):
    import ui

    profile = {
        "name": "prod", "context": "",
        "state": {"_k8s_ns_combo": "prod", "_k8s_pod_list": "prod-pod  (Running)",
                  "_k8s_container_input": "app"},
    }
    with patch.object(ui.KubernetesPanel, "_do_connect",
                      lambda self: self._on_connected_k8s(["default", "prod"], [])), \
         patch.object(ui.KubernetesPanel, "_on_ns_changed",
                      lambda self, ns: self._on_pods_listed(
                          [{"name": f"{ns}-pod", "status": "Pending"}])):
        dlg = ui.AddConnectionDialog(preselect="kubernetes", prefill_profile=profile)
        dlg._sync_embedded_footer()
        p = dlg._embedded_panel
        assert p._k8s_ns_combo.currentText() == "prod"
        assert p._k8s_pod_list.currentItem().text() == "prod-pod  (Pending)"
        assert p._k8s_container_input.text() == "app"
        assert dlg._open_btn.isEnabled()


def test_azure_reopen_waits_for_connection_before_selecting_table(env):
    import ui

    profile = {
        "name": "az", "tenant_id": "t", "client_id": "c",
        "client_secret": "s", "workspace_id": "w",
        "state": {"_tabs": 0, "_table_list": "   AppTraces"},
    }
    with patch.object(ui.AzurePanel, "_do_connect", lambda self: None):
        dlg = ui.AddConnectionDialog(preselect="azure", prefill_profile=profile)
        p = dlg._embedded_panel
        dlg._sync_embedded_footer()
        assert p._table_list.currentItem() is None  # not connected yet

        p._on_az_connected(object(), object())
        dlg._sync_embedded_footer()
        assert p._table_list.currentItem().text().strip() == "AppTraces"
        assert dlg._open_btn.isEnabled()


def test_ssh_password_profile_does_not_auto_connect(env):
    import ui

    profile = {"name": "srv", "host": "h", "user": "u", "auth_mode": "password",
               "remote_path": "/var/log/app.log"}
    with patch.object(ui.SSHPanel, "_on_connect") as connect:
        ui.AddConnectionDialog(preselect="ssh", prefill_profile=profile)
    connect.assert_not_called()


def test_restore_gives_up_when_saved_item_is_gone(env):
    import ui

    profile = {"name": "blog", "token": "tok", "state": {"_project_list": "deleted"}}
    with patch.object(ui.RailwayPanel, "_do_connect",
                      lambda self: self._on_connected_railway(RAILWAY_PROJECTS)):
        dlg = ui.AddConnectionDialog(preselect="railway", prefill_profile=profile)
        for _ in range(200):
            dlg._sync_embedded_footer()
        assert dlg._restore_queue == []
        assert dlg._embedded_panel._project_list.currentItem() is None
