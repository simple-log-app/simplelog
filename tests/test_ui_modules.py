"""Tests that the UI split into modules stays consistent with the `ui` facade."""
import importlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

UI_MODULES = [
    "simplelog.ui.ui_theme", "simplelog.ui.ui_widgets", "simplelog.core.log_model", "simplelog.ui.log_view", "simplelog.ui.sidebar", "simplelog.ui.remote_dialogs",
    "simplelog.ui.main_window", "simplelog.ui.highlight_dialog", "simplelog.ui.panels.base",
    "simplelog.ui.panels.cloudwatch", "simplelog.ui.panels.file", "simplelog.ui.panels.ssh", "simplelog.ui.panels.docker", "simplelog.ui.panels.vercel",
    "simplelog.ui.panels.gcp", "simplelog.ui.panels.azure", "simplelog.ui.panels.loki", "simplelog.ui.panels.datadog", "simplelog.ui.panels.elastic",
    "simplelog.ui.panels.railway", "simplelog.ui.panels.flyio", "simplelog.ui.panels.kubernetes", "simplelog.ui.panels.cloudflare",
    "simplelog.ui.panels.form", "simplelog.ui.panels.heroku", "simplelog.ui.panels.render", "simplelog.ui.panels.splunk", "simplelog.ui.panels.betterstack",
    "simplelog.ui.panels.sentry", "simplelog.ui.panels.journald",
]

PANELS = {
    "simplelog.ui.panels.cloudwatch": "CloudWatchPanel", "simplelog.ui.panels.file": "FilePanel",
    "simplelog.ui.panels.ssh": "SSHPanel", "simplelog.ui.panels.docker": "DockerPanel",
    "simplelog.ui.panels.vercel": "VercelPanel", "simplelog.ui.panels.gcp": "GCPPanel",
    "simplelog.ui.panels.azure": "AzurePanel", "simplelog.ui.panels.loki": "LokiPanel",
    "simplelog.ui.panels.datadog": "DatadogPanel", "simplelog.ui.panels.elastic": "ElasticPanel",
    "simplelog.ui.panels.railway": "RailwayPanel", "simplelog.ui.panels.flyio": "FlyioPanel",
    "simplelog.ui.panels.kubernetes": "KubernetesPanel", "simplelog.ui.panels.cloudflare": "CloudflarePanel",
    "simplelog.ui.panels.heroku": "HerokuPanel", "simplelog.ui.panels.render": "RenderPanel",
    "simplelog.ui.panels.splunk": "SplunkPanel", "simplelog.ui.panels.betterstack": "BetterStackPanel",
    "simplelog.ui.panels.sentry": "SentryPanel", "simplelog.ui.panels.journald": "JournaldPanel",
}


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("module", UI_MODULES)
def test_module_imports(module):
    importlib.import_module(module)


@pytest.mark.parametrize("module", UI_MODULES)
def test_facade_reexports_public_classes(module):
    from simplelog.ui import facade as ui
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
    from simplelog.ui import facade as ui
    ui.apply_style(QApplication.instance())
    win = ui.MainWindow()
    assert win is not None
    win.close()


def test_log_viewer_and_sidebar_build():
    from simplelog.ui import facade as ui
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

    from simplelog.ui.ui_workers import BackgroundWorker

    class W(BackgroundWorker):
        success = pyqtSignal(list, list)

        def _work(self):
            return (["a"], ["b"])

    assert _run_worker(W()) == {"success": (["a"], ["b"])}


def test_background_worker_emits_no_value():
    from PyQt6.QtCore import pyqtSignal

    from simplelog.ui.ui_workers import BackgroundWorker

    class W(BackgroundWorker):
        success = pyqtSignal()

        def _work(self):
            return ()

    assert _run_worker(W()) == {"success": ()}


def test_background_worker_turns_runtime_error_into_failure():
    from PyQt6.QtCore import pyqtSignal

    from simplelog.ui.ui_workers import BackgroundWorker

    class W(BackgroundWorker):
        success = pyqtSignal(list)

        def _work(self):
            raise RuntimeError("boom")

    assert _run_worker(W()) == {"failure": "boom"}


def test_provider_workers_report_errors_and_results(monkeypatch):
    from simplelog.sources import railway_utils
    from simplelog.ui.panels.railway import _RailwayConnectWorker

    monkeypatch.setattr(railway_utils, "list_projects", lambda token: [{"name": "p"}])
    assert _run_worker(_RailwayConnectWorker("t")) == {"success": ([{"name": "p"}],)}

    def fail(token):
        raise RuntimeError("bad token")

    monkeypatch.setattr(railway_utils, "list_projects", fail)
    assert _run_worker(_RailwayConnectWorker("t")) == {"failure": "bad token"}


def test_vercel_deploy_worker_without_deployment_fails(monkeypatch):
    from simplelog.sources import vercel_utils
    from simplelog.ui.panels.vercel import _VercelFetchDeployWorker

    monkeypatch.setattr(vercel_utils, "get_latest_deployment", lambda *a: None)
    got = _run_worker(_VercelFetchDeployWorker("t", "p", "production"))
    assert "failure" in got and "success" not in got


def test_provider_panels_share_the_base_class():
    from simplelog.ui.panels.base import ProviderPanel

    for module, cls in PANELS.items():
        if cls == "FilePanel":   # opens plain files: different open_tab signature
            continue
        assert issubclass(getattr(importlib.import_module(module), cls), ProviderPanel), cls


def test_provider_panel_scaffold_returns_content_layout():
    from PyQt6.QtWidgets import QScrollArea, QVBoxLayout

    from simplelog.ui.panels.base import ProviderPanel

    panel = ProviderPanel()
    lay = panel._scaffold()
    assert isinstance(lay, QVBoxLayout)
    assert panel.findChild(QScrollArea) is not None
    assert lay.contentsMargins().left() == 12


def test_cross_on_the_only_term_row_empties_it():
    from simplelog.ui import facade as ui
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

    from simplelog.ui import facade as ui
    sidebar = ui.FilterSearchSidebar()
    keys = {sc.key().toString() for sc in sidebar.findChildren(QShortcut)}
    assert {"F3", "Shift+F3"} <= keys
    assert "Shift+F3" in sidebar._btn_prev.toolTip()
    assert "F3" in sidebar._btn_next.toolTip() and "Shift" not in sidebar._btn_next.toolTip()


def test_and_or_toggle_follows_the_language_and_keeps_its_value():
    from simplelog.core import i18n
    from simplelog.ui.sidebar import _TermRowWidget
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

    from simplelog.core import i18n
    from simplelog.ui import facade as ui
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


def test_level_chips_filter_the_active_viewer():
    from simplelog.ui import facade as ui
    viewer = ui.LogViewer(source_type="file")
    sidebar = ui.FilterSearchSidebar()
    sidebar.set_active_viewer(viewer)
    viewer.append_events([(1, "ERROR boom"), (2, "INFO fine"), (3, "WARN hmm")])
    viewer.flush_pending()
    assert viewer._model.visible_count() == 3
    sidebar._level_btns["info"].click()          # hide INFO
    assert [i.message for i in viewer._model.visible_items()] == ["ERROR boom", "WARN hmm"]
    sidebar._level_btns["info"].click()          # show it again
    assert viewer._model.visible_count() == 3
    sidebar._level_btns["error"].click()
    other = ui.LogViewer(source_type="file")
    other.append_events([(1, "ERROR x"), (2, "INFO y")])
    other.flush_pending()
    sidebar.set_active_viewer(other)             # the chips follow the user across tabs
    assert [i.message for i in other._model.visible_items()] == ["INFO y"]


@pytest.fixture
def history_file(tmp_path, monkeypatch):
    from simplelog.ui import sidebar
    monkeypatch.setattr(sidebar, "_HISTORY_PATH", tmp_path / "history.json")
    return tmp_path / "history.json"


def test_search_options_reach_the_viewer(history_file):
    from simplelog.ui import facade as ui
    viewer = ui.LogViewer(source_type="file")
    sidebar = ui.FilterSearchSidebar()
    sidebar.set_active_viewer(viewer)
    viewer.append_events([(1, "Error 404 here"), (2, "error 500 there")])
    viewer.flush_pending()
    row = sidebar._search_term_widgets[0]
    row._input.setText(r"error \d+")
    assert sidebar._refresh_search() is None and sidebar._search_matches == []   # plain text
    sidebar._search_regex_btn.setChecked(True)
    sidebar._refresh_search()
    assert len(sidebar._search_matches) == 2
    sidebar._search_case_btn.setChecked(True)
    sidebar._refresh_search()
    assert len(sidebar._search_matches) == 1                                     # only "error 500"


def test_invalid_regex_turns_the_term_red(history_file):
    from simplelog.ui import facade as ui
    sidebar = ui.FilterSearchSidebar()
    sidebar.set_active_viewer(ui.LogViewer(source_type="file"))
    row = sidebar._search_term_widgets[0]
    row._input.setText("(oops")
    sidebar._search_regex_btn.setChecked(True)
    sidebar._current_search_terms()
    assert "color:" in row._input.styleSheet() and row._input.styleSheet().endswith(";")
    assert row._input.styleSheet() != row._input_style
    sidebar._search_regex_btn.setChecked(False)
    sidebar._current_search_terms()
    assert row._input.styleSheet() == row._input_style


def test_term_history_is_kept_deduplicated_and_persisted(history_file):
    import json

    from simplelog.ui import facade as ui
    sidebar = ui.FilterSearchSidebar()
    for term in ("alpha", "beta", "alpha", "  ", "gamma"):
        sidebar._remember(term)
    assert sidebar._history == ["gamma", "alpha", "beta"]
    assert json.loads(history_file.read_text()) == ["gamma", "alpha", "beta"]
    again = ui.FilterSearchSidebar()                         # a new session sees it
    assert again._history == ["gamma", "alpha", "beta"]
    row = again._search_term_widgets[0]
    assert row._input.completer() is again._completer


def test_history_is_capped(history_file):
    from simplelog.ui import facade as ui
    sidebar = ui.FilterSearchSidebar()
    for i in range(50):
        sidebar._remember(f"term{i}")
    assert len(sidebar._history) == 30 and sidebar._history[0] == "term49"


def test_editing_finished_remembers_the_term(history_file):
    from simplelog.ui import facade as ui
    sidebar = ui.FilterSearchSidebar()
    row = sidebar._search_term_widgets[0]
    row._input.setText("needle")
    row._input.editingFinished.emit()
    assert sidebar._history[0] == "needle"


def _viewer_with_lines(n=6):
    from simplelog.ui import facade as ui
    v = ui.LogViewer(source_type="file")
    v.resize(500, 300)
    v.show()
    v.append_events([(i, f"line {i}") for i in range(n)])
    v.flush_pending()
    QApplication.processEvents()
    return v


def test_toggle_bookmark_on_the_selection_and_back():
    v = _viewer_with_lines()
    seen = []
    v.bookmarks_changed.connect(lambda: seen.append(1))
    v._list_view.setCurrentIndex(v._model.index(2))
    v.toggle_bookmark()
    assert v._model.bookmark_rows() == [2] and v.bookmark_count() == 1 and seen
    v.toggle_bookmark()
    assert v._model.bookmark_rows() == []


def test_goto_bookmark_wraps_in_both_directions():
    v = _viewer_with_lines()
    assert v.goto_bookmark(1) is False                       # nothing bookmarked yet
    v._model.set_bookmarks([1, 4], True)
    v._list_view.setCurrentIndex(v._model.index(0))
    assert v.goto_bookmark(1) and v._list_view.currentIndex().row() == 1
    assert v.goto_bookmark(1) and v._list_view.currentIndex().row() == 4
    assert v.goto_bookmark(1) and v._list_view.currentIndex().row() == 1      # wraps
    assert v.goto_bookmark(-1) and v._list_view.currentIndex().row() == 4     # wraps back
    assert v.goto_bookmark(-1) and v._list_view.currentIndex().row() == 1


def test_main_window_bookmark_actions_use_the_active_viewer(tmp_path):
    from simplelog.ui import main_window
    win = main_window.MainWindow()
    try:
        win._action_goto_bookmark(1)                          # no viewer: nothing happens
        v = _viewer_with_lines()
        win._cur_viewer = v
        v._list_view.setCurrentIndex(v._model.index(3))
        win._action_toggle_bookmark()
        assert v._model.bookmark_rows() == [3]
        win._action_goto_bookmark(1)
        assert v._list_view.currentIndex().row() == 3
        v._model.set_bookmarks([3], False)
        win._action_goto_bookmark(1)
        assert "bookmark" in win._status.currentMessage().lower()
        assert win._act_bookmark.shortcut().toString() == "Ctrl+B"
        assert win._act_next_bookmark.shortcut().toString() == "F2"
        assert win._act_prev_bookmark.shortcut().toString() == "Shift+F2"
    finally:
        win.close()


def test_bookmarked_rows_paint_a_marker():
    from PyQt6.QtGui import QColor
    v = _viewer_with_lines(3)
    v._model.set_bookmarks([1], True)
    QApplication.processEvents()
    img = v._list_view.viewport().grab().toImage()
    rect = v._list_view.visualRect(v._model.index(1))
    marker = QColor(img.pixel(1, rect.center().y()))
    plain = QColor(img.pixel(1, v._list_view.visualRect(v._model.index(0)).center().y()))
    assert marker != plain


def test_export_writes_the_filtered_lines(tmp_path):
    from simplelog.core.log_model import TermRow
    v = _viewer_with_lines(5)
    v.append_events([(10, "ERROR special")])
    v.flush_pending()
    out = tmp_path / "all.log"
    assert v.export_lines(str(out)) == 6
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0].endswith("line 0") and lines[-1].endswith("ERROR special")
    assert lines[1][:4].isdigit() and lines[1].endswith("line 1")  # timestamps are on
    v.timestamps_cb.setChecked(False)
    v.apply_filter([TermRow("special", "")])
    out2 = tmp_path / "filtered.log"
    assert v.export_lines(str(out2)) == 1
    assert out2.read_text(encoding="utf-8") == "ERROR special\n"


def test_export_of_the_selection_only(tmp_path):
    v = _viewer_with_lines(5)
    v.timestamps_cb.setChecked(False)
    v._list_view.selectionModel().select(
        v._model.index(1), v._list_view.selectionModel().SelectionFlag.Select)
    v._list_view.selectionModel().select(
        v._model.index(3), v._list_view.selectionModel().SelectionFlag.Select)
    assert v.export_text(selection_only=True) == "line 1\nline 3\n"
    assert v.export_text().count("\n") == 5


def test_export_with_nothing_to_show_gives_an_empty_file(tmp_path):
    from simplelog.ui import facade as ui
    v = ui.LogViewer(source_type="file")
    out = tmp_path / "empty.log"
    assert v.export_lines(str(out)) == 0 and out.read_text() == ""


def test_main_window_export_action(tmp_path, monkeypatch):
    from simplelog.ui import main_window
    win = main_window.MainWindow()
    try:
        win._action_export()
        assert "nothing" in win._status.currentMessage().lower()
        v = _viewer_with_lines(3)
        v.timestamps_cb.setChecked(False)
        win._cur_viewer = v
        target = tmp_path / "out.log"
        monkeypatch.setattr(main_window.QFileDialog, "getSaveFileName",
                            staticmethod(lambda *a, **k: (str(target), "")))
        win._action_export()
        assert target.read_text() == "line 0\nline 1\nline 2\n"
        assert "3" in win._status.currentMessage()
        warned = []
        monkeypatch.setattr(main_window.QMessageBox, "warning",
                            staticmethod(lambda *a, **k: warned.append(a)))
        monkeypatch.setattr(main_window.QFileDialog, "getSaveFileName",
                            staticmethod(lambda *a, **k: (str(tmp_path / "no" / "dir.log"), "")))
        win._action_export()
        assert warned
    finally:
        win.close()


def test_merge_viewers_shows_both_logs_in_time_order_and_follows_new_lines():
    from simplelog.ui import facade as ui
    from simplelog.ui import main_window
    win = main_window.MainWindow()
    try:
        a = ui.LogViewer(source_type="file")
        b = ui.LogViewer(source_type="file")
        a.append_events([(10, "a1"), (30, "a3")])
        b.append_events([(20, "b2")])
        merged = win.merge_viewers([("api", a), ("db", b)])
        assert merged.merged
        rows = [(i.source, i.message) for i in merged._model.visible_items()]
        assert rows == [("api", "a1"), ("db", "b2"), ("api", "a3")]
        b.append_events([(25, "b2.5"), (40, "b4")])                # live lines arrive in order
        assert [i.message for i in merged._model.visible_items()] == ["a1", "b2", "b2.5", "a3", "b4"]
        assert win._top_tabs.tabText(win._top_tabs.currentIndex()) == "Merged (2)"
        assert win._cur_viewer is merged and not merged.stop_btn.isEnabled()
        merged.timestamps_cb.setChecked(False)
        assert merged.export_text().splitlines()[0] == "[api] a1"
        merged.resize(600, 200)
        merged.show()
        QApplication.processEvents()
        assert not merged.grab().toImage().isNull()                # painting the source column works
        win._close_tab_at(win._top_tabs.currentIndex())
        QApplication.processEvents()
        a.append_events([(50, "after close")])                     # a closed merge must not crash
    finally:
        win.close()


def test_merge_action_needs_two_logs_and_the_dialog_lists_them():
    from PyQt6.QtCore import Qt

    from simplelog.ui import facade as ui
    from simplelog.ui import main_window
    win = main_window.MainWindow()
    try:
        win._action_merge_tabs()
        assert "two" in win._status.currentMessage()
        dlg = ui.MergeTabsDialog(["one", "two", "three"])
        assert not dlg._ok.isEnabled()
        dlg._list.item(0).setCheckState(Qt.CheckState.Checked)
        assert not dlg._ok.isEnabled()
        dlg._list.item(2).setCheckState(Qt.CheckState.Checked)
        assert dlg._ok.isEnabled() and dlg.chosen() == [0, 2]
    finally:
        win.close()


def test_remove_all_bookmarks_from_the_menu_and_the_viewer():
    from simplelog.ui import main_window
    win = main_window.MainWindow()
    try:
        v = _viewer_with_lines(5)
        win._cur_viewer = v
        v._model.set_bookmarks([0, 2, 4], True)
        seen = []
        v.bookmarks_changed.connect(lambda: seen.append(1))
        win._action_clear_bookmarks()
        assert v.bookmark_count() == 0 and seen
        win._action_clear_bookmarks()                      # none left: a hint, no crash
        assert "bookmark" in win._status.currentMessage().lower()
        assert win._act_clear_bookmarks.shortcut().toString() == "Ctrl+Shift+B"
    finally:
        win.close()


def test_bookmark_entries_of_the_edit_menu_are_in_reading_order():
    from simplelog.ui import main_window
    win = main_window.MainWindow()
    try:
        order = [a for a in win._menu_edit.actions()]
        names = [win._act_bookmark, win._act_next_bookmark, win._act_prev_bookmark,
                 win._act_clear_bookmarks]
        assert [order.index(a) for a in names] == sorted(order.index(a) for a in names)
    finally:
        win.close()


def test_merge_logs_lives_in_the_edit_menu_not_the_file_menu():
    from simplelog.ui import main_window
    win = main_window.MainWindow()
    try:
        assert win._act_merge in win._menu_edit.actions()
        assert win._act_merge not in win._menu_file.actions()
    finally:
        win.close()


class _Worker:
    """Just enough of a worker for the window: signals, and what closing it asks."""

    def __init__(self):
        from PyQt6.QtCore import QObject, pyqtSignal

        class _Sig(QObject):
            new_lines = pyqtSignal(list)
            status = pyqtSignal(str)
            error = pyqtSignal(str)

        self._sig = _Sig()
        self.new_lines, self.status, self.error = (
            self._sig.new_lines, self._sig.status, self._sig.error)

    def isRunning(self):  # noqa: N802
        return False

    def stop(self):
        pass


def test_merge_logs_is_in_the_context_menu_of_a_log_and_a_merged_view(monkeypatch):
    from PyQt6.QtWidgets import QMenu

    from simplelog.ui import facade as ui
    from simplelog.ui import main_window
    win = main_window.MainWindow()
    try:
        asked = []
        monkeypatch.setattr(win, "_action_merge_tabs", lambda: asked.append(1))
        a, b = ui.LogViewer(source_type="file"), ui.LogViewer(source_type="file")
        a.append_events([(1, "a")])
        win._wire_viewer(a, _Worker())                             # as a real log tab is
        merged = win.merge_viewers([("a", a), ("b", b)])
        for viewer in (a, merged):
            captured = []
            monkeypatch.setattr(QMenu, "exec", lambda self, *args, c=captured: c.append(
                [act.text() for act in self.actions()]) or None)
            viewer._show_context_menu(viewer._list_view.rect().center())
            assert "Merge logs…" in captured[0]
        viewer.merge_requested.emit()
        a.merge_requested.emit()
        assert len(asked) == 2                          # both viewers reach the window's action
    finally:
        win.close()


def test_merge_logs_is_greyed_out_with_fewer_than_two_logs(monkeypatch):
    from PyQt6.QtWidgets import QMenu

    from simplelog.ui import facade as ui
    from simplelog.ui import main_window
    win = main_window.MainWindow()
    try:
        viewer = ui.LogViewer(source_type="file")
        win._wire_viewer(viewer, _Worker())
        states = {}

        def grab(self, *args):
            states["ctx"] = [a.isEnabled() for a in self.actions() if a.text() == "Merge logs…"]

        monkeypatch.setattr(QMenu, "exec", grab)
        for count in (1, 2):
            monkeypatch.setattr(win, "_merge_sources", lambda n=count: [("t", viewer)] * n)
            win._menu_edit.aboutToShow.emit()
            viewer._show_context_menu(viewer._list_view.rect().center())
            assert win._act_merge.isEnabled() == (count == 2)
            assert states["ctx"] == [count == 2]
    finally:
        win.close()


def test_remote_home_panel_never_shows_a_top_level_window_while_building():
    from PyQt6.QtCore import QEvent, QObject
    from PyQt6.QtWidgets import QApplication

    from simplelog.ui import facade as ui

    class Spy(QObject):
        shown: list = []

        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.Show and obj.isWidgetType() and obj.isWindow():
                self.shown.append(type(obj).__name__)
            return False

    spy = Spy()
    app = QApplication.instance()
    app.installEventFilter(spy)
    try:
        panel = ui.RemoteHomePanel()      # a flashing parentless widget makes GNOME show a busy cursor
        assert spy.shown == []
        panel.deleteLater()
    finally:
        app.removeEventFilter(spy)


def test_add_connection_dialog_never_shows_a_top_level_window_while_building():
    from PyQt6.QtCore import QEvent, QObject
    from PyQt6.QtWidgets import QApplication, QWidget

    from simplelog.sources import providers
    from simplelog.ui import remote_dialogs

    class Spy(QObject):
        shown: list = []

        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.Show and obj.isWidgetType() and obj.isWindow():
                self.shown.append(type(obj).__name__)
            return False

    spy = Spy()
    app = QApplication.instance()
    app.installEventFilter(spy)
    try:
        host = QWidget()
        remote_dialogs.AddConnectionDialog(parent=host)
        for provider in providers.PROVIDERS:
            remote_dialogs.AddConnectionDialog(parent=host, preselect=provider.id)
        assert spy.shown == []
    finally:
        app.removeEventFilter(spy)


def test_pyinstaller_spec_lists_every_panel_without_the_package_being_installed():
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    spec = (root / "simplelog.spec").read_text()
    snippet = re.search(r"^APP_MODULES = \[.*?^\]$", spec, re.S | re.M).group(0)
    cwd = os.getcwd()
    os.chdir(root)          # the spec is evaluated from the repository root
    try:
        scope = {"Path": Path}
        exec(snippet, scope)
    finally:
        os.chdir(cwd)
    listed = set(scope["APP_MODULES"])
    assert set(PANELS) <= listed
    assert {"simplelog.sources.docker_utils", "simplelog.ui.facade"} <= listed


def test_theme_menu_follows_the_day_night_switch(monkeypatch, tmp_path):
    import simplelog.ui.ui_theme as ui_theme
    from simplelog.ui import facade as ui

    monkeypatch.setattr(ui_theme, "_PREFS_PATH", tmp_path / "prefs.json")
    win = ui.MainWindow()
    try:
        win._set_theme_mode("light")
        assert ui_theme.LIGHT["card"] in win._theme_menu.styleSheet()
        win._set_theme_mode("dark")
        assert ui_theme.DARK["card"] in win._theme_menu.styleSheet()
    finally:
        win.close()


def test_dialogs_have_no_system_title_bar():
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QPushButton, QWidget

    from simplelog.ui.highlight_dialog import HighlightRulesDialog
    from simplelog.ui.main_window import ChangelogDialog
    from simplelog.ui.remote_dialogs import AddConnectionDialog
    from simplelog.ui.ui_widgets import MergeTabsDialog, _HelpDialog

    host = QWidget()
    dialogs = [
        _HelpDialog("<p>x</p>", host), MergeTabsDialog(["a", "b"], host),
        HighlightRulesDialog(host), ChangelogDialog(host, "T", "# x"),
        AddConnectionDialog(parent=host),
    ]
    for dlg in dialogs:
        assert dlg.windowFlags() & Qt.WindowType.FramelessWindowHint, type(dlg).__name__
        assert any(b.text() == "✕" for b in dlg.findChildren(QPushButton)), type(dlg).__name__
