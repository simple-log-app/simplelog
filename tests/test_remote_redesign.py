"""Remote redesign: connection list, provider picker, dialog steps, logos."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QLineEdit, QPushButton

import profiles_store
import providers
import remote_dialogs
import ui_theme


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles_store, "_DIR", tmp_path)
    return tmp_path


def _group_names(panel):
    names = set()
    for frame in panel.findChildren(QFrame):
        if frame.objectName() == "group":
            names |= {lbl.text() for lbl in frame.findChildren(QLabel)}
    return names


def test_list_only_shows_providers_with_a_connection(store):
    profiles_store.upsert("ssh", "prod", {"host": "10.0.0.1"})
    panel = remote_dialogs.RemoteHomePanel()
    names = _group_names(panel)
    assert "SSH" in names
    assert "Docker" not in names and "AWS CloudWatch" not in names


def test_list_shows_the_empty_state_without_connections(store):
    panel = remote_dialogs.RemoteHomePanel()
    assert not _group_names(panel)
    texts = {lbl.text() for lbl in panel.findChildren(QLabel)}
    assert "No remote connections" in texts


def test_delete_needs_two_clicks(store):
    profiles_store.upsert("ssh", "prod", {"host": "10.0.0.1"})
    panel = remote_dialogs.RemoteHomePanel()
    row = panel.findChildren(remote_dialogs._ConnRow)[0]
    btn = row.findChild(QPushButton)
    assert btn.isHidden()
    row.hovered.emit(True)
    assert not btn.isHidden()
    btn.click()
    assert btn.text() == "Delete?"
    assert profiles_store.load_all("ssh")          # still there after one click
    row.hovered.emit(False)                        # leaving the row resets it
    assert btn.text() == ""
    row.hovered.emit(True)
    btn.click()
    btn.click()
    assert profiles_store.load_all("ssh") == []


def test_picker_filter_hides_non_matching_providers(store):
    dlg = remote_dialogs.AddConnectionDialog()
    dlg.show()
    dlg._filter_edit.setText("kube")
    visible = [p.id for p, card in dlg._cards if card.isVisible()]
    assert visible == ["kubernetes"]
    dlg._filter_edit.setText("")
    assert len([1 for _, card in dlg._cards if card.isVisible()]) == len(providers.PROVIDERS)
    dlg.reject()


def test_picker_grid_has_four_columns(store):
    dlg = remote_dialogs.AddConnectionDialog()
    cols = {dlg._grid.getItemPosition(i)[1] for i in range(dlg._grid.count())}
    assert cols == {0, 1, 2, 3}
    assert dlg.width() == remote_dialogs._STEP1_WIDTH
    dlg.reject()


def test_step2_is_narrower_and_back_button_depends_on_origin(store):
    dlg = remote_dialogs.AddConnectionDialog(preselect="railway")
    assert dlg.width() == remote_dialogs._STEP2_WIDTH
    assert dlg._can_go_back is False            # preselected: nothing to go back to
    dlg.reject()

    dlg = remote_dialogs.AddConnectionDialog()
    dlg._go_step2("railway")
    assert dlg._can_go_back is True
    dlg._go_step1()
    assert dlg._stack.currentIndex() == 0
    dlg.reject()

    dlg = remote_dialogs.AddConnectionDialog(preselect="railway", prefill_profile={"name": "x"})
    assert dlg._can_go_back is False            # an existing connection
    labels = {lbl.text() for lbl in dlg.findChildren(QLabel)}
    assert "Saved connection" in labels
    dlg.reject()


def test_embedded_panels_hide_their_saved_profile_bar(store):
    profiles_store.upsert("cloudwatch", "x", {"region": "us-east-1"})
    dlg = remote_dialogs.AddConnectionDialog(preselect="cloudwatch")
    bar = dlg._embedded_panel._cw_profile_bar
    assert bar.isHidden()
    dlg.reject()


def test_every_provider_has_a_bundled_logo():
    for p in providers.PROVIDERS:
        if p.id == "heroku":
            continue          # no brand logo is published for it: the glyph is used instead
        assert p.logo and ui_theme._logo_svg(p.logo, "#ffffff"), p.id


def test_provider_logo_renders_with_and_without_tile():
    p = providers.get("docker")
    tile = ui_theme.provider_logo(p.logo, p.icon, p.color, 26)
    bare = ui_theme.provider_logo(p.logo, p.icon, p.color, 14, tile=False)
    assert tile.width() == 52 and bare.width() == 28      # rendered at 2x


def test_provider_logo_falls_back_to_the_glyph():
    pm = ui_theme.provider_logo("assets/providers/nope.svg", "☁", "#ff9900", 20)
    assert not pm.isNull()


def test_provider_card_filter_field_exists(store):
    dlg = remote_dialogs.AddConnectionDialog()
    assert isinstance(dlg._filter_edit, QLineEdit)
    assert dlg._filter_edit.placeholderText() == "Filter sources…"
    dlg.reject()


def test_escape_closes_when_there_is_no_picker_to_return_to(store):
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QKeyEvent
    dlg = remote_dialogs.AddConnectionDialog(preselect="railway")
    dlg.show()
    dlg.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
    assert not dlg.isVisible()


def test_open_as_lives_in_the_dialog_footer_and_decides_the_mode(store):
    from ui_widgets import OpenModeWidget
    dlg = remote_dialogs.AddConnectionDialog(preselect="railway")
    panel = dlg._embedded_panel
    assert dlg._open_mode_w.get_mode() == "tab"                    # new tab by default
    assert all(w.isHidden() for w in panel.findChildren(OpenModeWidget))
    got = []
    dlg.tab_requested.connect(lambda cfg, mode: got.append(mode))
    dlg._open_mode_w._btns["vertical"].setChecked(True)
    dlg._on_embedded_panel_tab({"type": "railway"}, "tab")         # panel's own value is ignored
    assert got == ["vertical"]


def test_split_choices_are_greyed_out_when_no_log_is_open(store):
    dlg = remote_dialogs.AddConnectionDialog(preselect="railway", split_enabled=False)
    w = dlg._open_mode_w
    assert not w._btns["vertical"].isEnabled() and not w._btns["horizontal"].isEnabled()
    assert w._btns["tab"].isEnabled() and w.get_mode() == "tab"
    assert "log first" in w._btns["vertical"].toolTip()
    dlg.reject()

    dlg = remote_dialogs.AddConnectionDialog(preselect="railway")          # default: all offered
    assert dlg._open_mode_w._btns["vertical"].isEnabled()
    assert dlg._open_mode_w._btns["vertical"].toolTip() == ""
    dlg.reject()


def test_disabling_split_falls_back_to_a_new_tab_and_can_be_undone():
    from ui_widgets import OpenModeWidget
    w = OpenModeWidget()
    w._btns["horizontal"].setChecked(True)
    w.set_split_enabled(False)
    assert w.get_mode() == "tab"
    w.set_split_enabled(True)
    assert w._btns["horizontal"].isEnabled() and w.get_mode() == "tab"


def test_main_window_tells_the_dialog_whether_a_tab_exists(store):
    import main_window
    import ui
    win = main_window.MainWindow()
    try:
        assert win._remote_panel.split_available() is False
        v = ui.LogViewer(source_type="file")
        spl = win._make_tab_splitter()
        spl.addWidget(v)
        win._top_tabs.addTab(spl, "t")
        assert win._remote_panel.split_available() is True
        assert remote_dialogs.RemoteHomePanel().split_available() is True      # alone: no restriction
    finally:
        win.close()
