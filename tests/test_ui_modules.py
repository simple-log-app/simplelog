"""Tests that the UI split into modules stays consistent with the `ui` facade."""
import importlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

UI_MODULES = [
    "ui_theme", "ui_widgets", "log_model", "log_view", "sidebar", "remote_dialogs",
    "main_window",
    "panels.cloudwatch", "panels.file", "panels.ssh", "panels.docker", "panels.vercel",
    "panels.gcp", "panels.azure", "panels.loki", "panels.datadog", "panels.elastic",
    "panels.railway", "panels.flyio", "panels.kubernetes", "panels.cloudflare",
]

PANELS = {
    "panels.cloudwatch": "CloudWatchPanel", "panels.file": "FilePanel",
    "panels.ssh": "SSHPanel", "panels.docker": "DockerPanel",
    "panels.vercel": "VercelPanel", "panels.gcp": "GCPPanel",
    "panels.azure": "AzurePanel", "panels.loki": "LokiPanel",
    "panels.datadog": "DatadogPanel", "panels.elastic": "ElasticPanel",
    "panels.railway": "RailwayPanel", "panels.flyio": "FlyioPanel",
    "panels.kubernetes": "KubernetesPanel", "panels.cloudflare": "CloudflarePanel",
}


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("module", UI_MODULES)
def test_module_imports(module):
    importlib.import_module(module)


@pytest.mark.parametrize("module", UI_MODULES)
def test_facade_reexports_public_classes(module):
    import ui
    mod = importlib.import_module(module)
    for name, obj in vars(mod).items():
        if isinstance(obj, type) and obj.__module__ == module:
            assert getattr(ui, name) is obj, f"ui.{name} missing or different"


@pytest.mark.parametrize("module,cls", PANELS.items())
def test_panel_can_be_built(module, cls):
    panel = getattr(importlib.import_module(module), cls)()
    assert panel is not None
    panel.deleteLater()


def test_main_window_builds_and_applies_style():
    import ui
    ui.apply_style(QApplication.instance())
    win = ui.MainWindow()
    assert win is not None
    win.close()


def test_log_viewer_and_sidebar_build():
    import ui
    viewer = ui.LogViewer(source_type="file")
    sidebar = ui.FilterSearchSidebar()
    assert viewer is not None and sidebar is not None
