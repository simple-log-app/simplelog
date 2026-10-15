"""Tests for the changelog dialog, the Help → What's New menu and the update dialog."""
import os
import sys
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QDialog, QDialogButtonBox


@pytest.fixture
def app():
    return QApplication.instance() or QApplication(sys.argv)


def test_changelog_dialog_renders_markdown_and_action(app):
    from simplelog.ui import facade as ui

    dlg = ui.ChangelogDialog(None, "Title", "## [1.0.0]\n- hello",
                             header="Update!", action_label="Install")
    assert "hello" in dlg.browser.toPlainText()
    box = dlg.findChild(QDialogButtonBox)
    labels = [b.text() for b in box.buttons()]
    assert "Install" in labels


def test_whats_new_menu_shows_local_changelog(app):
    from simplelog.ui import facade as ui

    shown = []
    with patch.object(ui.ChangelogDialog, "exec",
                      lambda self: shown.append(self.browser.toPlainText()) or 0):
        win = ui.MainWindow()
        win._action_changelog()
    assert shown and "1.0.8" in shown[0]


def test_update_available_with_notes_shows_changes(app):
    from simplelog.ui import facade as ui

    shown = []
    with patch.object(ui.ChangelogDialog, "exec",
                      lambda self: shown.append(self.browser.toPlainText())
                      or QDialog.DialogCode.Rejected):
        win = ui.MainWindow()
        with patch.object(win, "_install_update") as install:
            win._on_update_available("v9.0.0", "https://x", "## [9.0.0]\n- big change")
    assert shown and "big change" in shown[0]
    install.assert_not_called()
