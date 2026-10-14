"""Tests that the UI split into modules stays consistent with the `ui` facade."""
import importlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

UI_MODULES = [
    "ui_theme", "ui_widgets", "log_model", "log_view", "sidebar", "remote_dialogs",
    "main_window", "panels.base",
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


# ── BackgroundWorker ──────────────────────────────────────────────────────────

def _run_worker(worker):
    got = {}
    worker.success.connect(lambda *a: got.setdefault("success", a))
    worker.failure.connect(lambda m: got.setdefault("failure", m))
    worker.run()  # synchronous: no need to start a thread
    return got


def test_background_worker_emits_success_values():
    from PyQt6.QtCore import pyqtSignal

    from ui_workers import BackgroundWorker

    class W(BackgroundWorker):
        success = pyqtSignal(list, list)

        def _work(self):
            return (["a"], ["b"])

    assert _run_worker(W()) == {"success": (["a"], ["b"])}


def test_background_worker_emits_no_value():
    from PyQt6.QtCore import pyqtSignal

    from ui_workers import BackgroundWorker

    class W(BackgroundWorker):
        success = pyqtSignal()

        def _work(self):
            return ()

    assert _run_worker(W()) == {"success": ()}


def test_background_worker_turns_runtime_error_into_failure():
    from PyQt6.QtCore import pyqtSignal

    from ui_workers import BackgroundWorker

    class W(BackgroundWorker):
        success = pyqtSignal(list)

        def _work(self):
            raise RuntimeError("boom")

    assert _run_worker(W()) == {"failure": "boom"}


def test_provider_workers_report_errors_and_results(monkeypatch):
    import railway_utils
    from panels.railway import _RailwayConnectWorker

    monkeypatch.setattr(railway_utils, "list_projects", lambda token: [{"name": "p"}])
    assert _run_worker(_RailwayConnectWorker("t")) == {"success": ([{"name": "p"}],)}

    def fail(token):
        raise RuntimeError("bad token")

    monkeypatch.setattr(railway_utils, "list_projects", fail)
    assert _run_worker(_RailwayConnectWorker("t")) == {"failure": "bad token"}


def test_vercel_deploy_worker_without_deployment_fails(monkeypatch):
    import vercel_utils
    from panels.vercel import _VercelFetchDeployWorker

    monkeypatch.setattr(vercel_utils, "get_latest_deployment", lambda *a: None)
    got = _run_worker(_VercelFetchDeployWorker("t", "p", "production"))
    assert "failure" in got and "success" not in got


def test_provider_panels_share_the_base_class():
    from panels.base import ProviderPanel

    for module, cls in PANELS.items():
        if cls == "FilePanel":   # opens plain files: different open_tab signature
            continue
        assert issubclass(getattr(importlib.import_module(module), cls), ProviderPanel), cls


def test_provider_panel_scaffold_returns_content_layout():
    from PyQt6.QtWidgets import QScrollArea, QVBoxLayout

    from panels.base import ProviderPanel

    panel = ProviderPanel()
    lay = panel._scaffold()
    assert isinstance(lay, QVBoxLayout)
    assert panel.findChild(QScrollArea) is not None
    assert lay.contentsMargins().left() == 12


def test_cross_on_the_only_term_row_empties_it():
    import ui
    sidebar = ui.FilterSearchSidebar()
    row = sidebar._search_term_widgets[0]
    row._input.setText("error")
    row._rm_btn.click()
    assert row._input.text() == "" and len(sidebar._search_term_widgets) == 1
    frow = sidebar._filter_term_widgets[0]
    frow._input.setText("warn")
    frow._rm_btn.click()
    assert frow._input.text() == "" and len(sidebar._filter_term_widgets) == 1


def test_search_prev_next_have_f3_shortcuts_and_tooltips():
    from PyQt6.QtGui import QShortcut

    import ui
    sidebar = ui.FilterSearchSidebar()
    keys = {sc.key().toString() for sc in sidebar.findChildren(QShortcut)}
    assert {"F3", "Shift+F3"} <= keys
    assert "Shift+F3" in sidebar._btn_prev.toolTip()
    assert "F3" in sidebar._btn_next.toolTip() and "Shift" not in sidebar._btn_next.toolTip()


def test_and_or_toggle_follows_the_language_and_keeps_its_value():
    import i18n
    from sidebar import _TermRowWidget
    w = _TermRowWidget("AND")
    try:
        i18n.set_locale("fr")
        w.retranslate_op()
        assert w._op_btn.text() == "ET"
        w._op_btn.click()
        assert w._op_btn.text() == "OU" and w.to_term_row().operator == "OR"
        i18n.set_locale("en")
        w.retranslate_op()
        assert w._op_btn.text() == "OR"
    finally:
        i18n.set_locale("en")


@pytest.mark.parametrize("locale", ["en", "fr", "de", "es", "zh"])
def test_right_sidebar_fits_its_default_width_in_every_language(locale):
    from PyQt6.QtWidgets import QWidget

    import i18n
    import ui
    i18n.set_locale(locale)
    try:
        sidebar = ui.FilterSearchSidebar()
        sidebar.retranslate()
        sidebar.show()
        QApplication.processEvents()
        for i in range(3):
            page = sidebar._content_stack.widget(i)
            widest = max(w.minimumSizeHint().width() for w in page.findChildren(QWidget))
            assert widest <= 190, (locale, i, widest)   # the sidebar is 224 wide, 10px margins
    finally:
        i18n.set_locale("en")
