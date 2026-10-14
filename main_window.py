"""Main window and changelog dialog."""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time

from PyQt6.QtCore import (
    QPoint,
    QSize,
    Qt,
    QTimer,
    QUrl,
)
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QDesktopServices,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import changelog
import config_store
import connection_state as cs
import i18n
import providers
import ui_theme
from highlight_dialog import HighlightRulesDialog
from log_view import LogViewer
from panels.file import FilePanel
from remote_dialogs import RemoteHomePanel
from sidebar import FilterSearchSidebar
from ui_theme import (
    _SVG_CHEVRON_LEFT,
    _SVG_CHEVRON_RIGHT,
    _SVG_MOON,
    _SVG_SUN,
    C_ACCENT,
    C_BG,
    C_BORDER,
    C_CARD,
    C_DIVIDER,
    C_ERR,
    C_HOVER,
    C_INFO,
    C_MUTED,
    C_PANEL,
    C_SIDE,
    C_STATUS,
    C_TEXT,
    C_WARN,
    _svg_icon,
    provider_logo,
    with_status_dot,
)
from ui_widgets import MergeTabsDialog, NavRail, _SidebarEdgeBtn, _SLTabWidget, _TabCloseBtn
from ui_workers import CallWorker
from workers import DebInstallWorker, FileWorker, StdinWorker

# ── macOS in-place update helpers ─────────────────────────────────────────────

def macos_app_bundle(executable: str) -> str | None:
    """Return the `.app` bundle that contains *executable*, or None if it isn't in one.

    A PyInstaller bundle runs `X.app/Contents/MacOS/<exe>`; anything else must never
    be treated as replaceable (the update script deletes the returned path).
    """
    bundle = os.path.abspath(os.path.join(os.path.dirname(executable), "..", ".."))
    if bundle.endswith(".app") and os.path.basename(os.path.dirname(executable)) == "MacOS":
        return bundle
    return None


def macos_update_script(pid: int, dmg_path: str, app_bundle: str) -> str:
    """Shell script that swaps *app_bundle* for the app in *dmg_path* once *pid* exits.

    The new app is copied next to the old one first; the old one is only removed once
    the swap succeeded, and is put back if it did not.
    """
    q = shlex.quote
    app_dir = os.path.dirname(app_bundle)
    new = os.path.join(app_dir, ".SimpleLog.new.app")
    old = os.path.join(app_dir, ".SimpleLog.old.app")
    return (
        "#!/bin/sh\n"
        f"while kill -0 {int(pid)} 2>/dev/null; do sleep 0.1; done\n"
        'MP=$(mktemp -d /tmp/simplelog-mnt.XXXXXX)\n'
        f'hdiutil attach {q(dmg_path)} -nobrowse -quiet -mountpoint "$MP" || exit 1\n'
        f"rm -rf {q(new)} {q(old)}\n"
        f'if cp -R "$MP/SimpleLog.app" {q(new)} && mv {q(app_bundle)} {q(old)} '
        f"&& mv {q(new)} {q(app_bundle)}; then\n"
        f"  rm -rf {q(old)}\n"
        "else\n"
        f"  if [ -d {q(old)} ] && [ ! -d {q(app_bundle)} ]; then mv {q(old)} {q(app_bundle)}; fi\n"
        f"  rm -rf {q(new)}\n"
        "fi\n"
        'hdiutil detach "$MP" -quiet\n'
        'rmdir "$MP"\n'
        f"rm {q(dmg_path)}\n"
        f"open {q(app_bundle)}\n"
        'rm -- "$0"\n'
    )


# ── SideStack ─────────────────────────────────────────────────────────────────

class SideStack(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(160)
        self.setMaximumWidth(480)
        self.setStyleSheet(
            f"background: {C_SIDE};"
            f"border-right: 1px solid {C_BORDER};"
        )


# ── MainWindow ────────────────────────────────────────────────────────────────

class ChangelogDialog(QDialog):
    """Shows changelog markdown, optionally under a header and with an action button."""

    def __init__(self, parent, title: str, markdown: str,
                 header: str = "", action_label: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 500)
        lay = QVBoxLayout(self)
        if header:
            header_lbl = QLabel(header)
            header_lbl.setWordWrap(True)
            lay.addWidget(header_lbl)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setMarkdown(markdown)
        lay.addWidget(self.browser, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        if action_label:
            buttons.addButton(action_label, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SimpleLog")
        self.resize(1380, 860)
        self._workers: dict[int, object] = {}
        self._stopping: set = set()   # stopped workers that are still winding down
        self._connectors: set = set()  # background connections for tabs being opened
        self._cur_viewer: LogViewer | None = None
        self._links: dict[int, cs.Link] = {}     # remote tabs: how to bring them back
        self._auto_reconnect = bool(config_store.get_pref("auto_reconnect", True))
        self._splitter_style: str = ""
        self._update_worker = None  # UpdateWorker instance (kept alive)
        self._left_sidebar_width: int = 300
        self._right_sidebar_width: int = 224
        self._build_ui()
        self._build_menubar()
        ui_theme.on_theme_changed(id(self), self._on_theme_changed)
        self.destroyed.connect(lambda _=None, k=id(self): ui_theme.off_theme_changed(k))

    def _build_ui(self):
        # Central container
        central = QWidget()
        central.setStyleSheet(f"background: {C_BG};")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Nav rail
        self._nav = NavRail()
        self._nav.index_changed.connect(self._on_nav_index_changed)
        root.addWidget(self._nav)

        # Side stack
        self._side_stack = SideStack()

        self._remote_panel = RemoteHomePanel()
        self._remote_panel.tab_requested.connect(self.open_remote_tab)
        self._remote_panel.split_available = lambda: self._top_tabs.count() > 0
        self._side_stack.addWidget(self._remote_panel)  # index 0

        self._file_panel = FilePanel()
        self._file_panel.open_tab.connect(self.open_file_tab)
        self._side_stack.addWidget(self._file_panel)    # index 1

        self._splitter_style = (
            f"QSplitter::handle {{ background: {C_BORDER}; }}"
            f"QSplitter::handle:horizontal {{ width: 4px; }}"
            f"QSplitter::handle:vertical {{ height: 4px; }}"
            f"QSplitter::handle:hover {{ background: {C_ACCENT}; }}"
        )

        # Top-level browser-style tab widget: each tab takes the full space
        self._top_tabs = _SLTabWidget()
        self._top_tabs.setTabsClosable(True)
        self._top_tabs.setDocumentMode(True)
        self._top_tabs.setIconSize(QSize(14, 14))
        self._top_tabs.tabBar().setDrawBase(False)
        self._top_tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: none; background: {C_BG}; border-top: 1px solid {C_BORDER}; }}"
            f"QTabBar::tab {{ background: {C_PANEL}; color: {C_MUTED};"
            f" padding: 0 16px 0 14px; min-height: 34px; border: none;"
            f" border-right: 1px solid {C_BORDER}; }}"
            f"QTabBar::tab:selected {{ background: {C_BG}; color: {C_TEXT};"
            f" border-bottom: 2px solid {C_ACCENT}; }}"
            f"QTabBar::tab:hover:!selected {{ color: {C_TEXT};"
            f" background: {C_HOVER}; }}"
        )
        self._top_tabs.tabCloseRequested.connect(self._close_tab_at)
        self._top_tabs.currentChanged.connect(self._on_top_tab_changed)

        self._sidebar = FilterSearchSidebar(self)

        # Outer splitter: content area | sidebar
        self._outer_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._outer_splitter.setChildrenCollapsible(False)
        self._outer_splitter.setStyleSheet(self._splitter_style)
        self._outer_splitter.addWidget(self._top_tabs)
        self._outer_splitter.addWidget(self._sidebar)
        self._outer_splitter.setSizes([10000, 224])
        self._outer_splitter.setStretchFactor(0, 1)
        self._outer_splitter.setStretchFactor(1, 0)
        self._outer_splitter.splitterMoved.connect(lambda *_: self._reposition_toggles())

        # Main splitter: left panel | content+right-sidebar
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setChildrenCollapsible(False)
        self._main_splitter.setStyleSheet(self._splitter_style)
        self._main_splitter.addWidget(self._side_stack)
        self._main_splitter.addWidget(self._outer_splitter)
        self._main_splitter.setSizes([300, 10000])
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.splitterMoved.connect(lambda *_: self._reposition_toggles())
        root.addWidget(self._main_splitter, stretch=1)

        # Floating edge toggle buttons (overlaid on central widget)
        self._btn_left_toggle = _SidebarEdgeBtn("left", central)
        self._btn_left_toggle.set_svg(_SVG_CHEVRON_LEFT)
        self._btn_left_toggle.setToolTip(i18n.tr("tip_toggle_sidebar"))
        self._btn_left_toggle.clicked.connect(self._toggle_left_sidebar)
        self._btn_left_toggle.show()

        self._btn_right_toggle = _SidebarEdgeBtn("right", central)
        self._btn_right_toggle.set_svg(_SVG_CHEVRON_RIGHT)
        self._btn_right_toggle.setToolTip(i18n.tr("tip_toggle_search"))
        self._btn_right_toggle.clicked.connect(self._toggle_right_sidebar)
        self._btn_right_toggle.show()

        sc_toggle = QShortcut(QKeySequence("Ctrl+Shift+F"), self)
        sc_toggle.activated.connect(self._toggle_right_sidebar)

        sc_left = QShortcut(QKeySequence("Ctrl+\\"), self)
        sc_left.activated.connect(self._toggle_left_sidebar)

        # Status bar
        self._status = QStatusBar()
        self._status.setFixedHeight(26)
        self._status.setStyleSheet(
            f"QStatusBar {{ background: {C_STATUS}; border-top: 1px solid {C_BORDER};"
            f" color: {C_MUTED}; font-family: 'JetBrains Mono', monospace; font-size: 11px; }}"
        )
        self.setStatusBar(self._status)
        self._status.showMessage(i18n.tr("status_ready"))

    # ── Menu bar ──────────────────────────────────────────────────────────────

    def _build_menubar(self) -> None:
        mb = self.menuBar()

        # ── File ──
        self._menu_file = mb.addMenu("")
        self._act_open = QAction(self)
        self._act_open.setShortcut(QKeySequence("Ctrl+O"))
        self._act_open.triggered.connect(self._action_open_file)
        self._menu_file.addAction(self._act_open)

        self._act_export = QAction(self)
        self._act_export.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self._act_export.triggered.connect(lambda: self._action_export(False))
        self._menu_file.addAction(self._act_export)

        self._act_reconnect = QAction(self, checkable=True)
        self._act_reconnect.setChecked(self._auto_reconnect)
        self._act_reconnect.toggled.connect(self._set_auto_reconnect)
        self._menu_file.addAction(self._act_reconnect)

        self._act_close_tab = QAction(self)
        self._act_close_tab.setShortcut(QKeySequence("Ctrl+W"))
        self._act_close_tab.triggered.connect(self._action_close_current_tab)
        self._menu_file.addAction(self._act_close_tab)

        self._act_close_all = QAction(self)
        self._act_close_all.setShortcut(QKeySequence("Ctrl+Shift+W"))
        self._act_close_all.triggered.connect(self._action_close_all_logs)
        self._menu_file.addAction(self._act_close_all)

        self._menu_file.addSeparator()

        self._act_update = QAction(self)
        self._act_update.triggered.connect(self._action_check_update)
        self._menu_file.addAction(self._act_update)

        self._menu_file.addSeparator()

        self._act_quit = QAction(self)
        self._act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self._act_quit.triggered.connect(self.close)
        self._menu_file.addAction(self._act_quit)

        # ── Edit ──
        self._menu_edit = mb.addMenu("")
        self._act_copy = QAction(self)
        self._act_copy.setShortcut(QKeySequence("Ctrl+C"))
        self._act_copy.triggered.connect(self._action_copy)
        self._menu_edit.addAction(self._act_copy)

        self._menu_edit.addSeparator()

        # No "Return" shortcut here: a window-wide shortcut fired from every text field.
        # The log list inserts the break itself when it has the focus (_LogListView).
        self._act_break = QAction(self)
        self._act_break.triggered.connect(self._action_break)
        self._menu_edit.addAction(self._act_break)

        self._menu_edit.addSeparator()
        self._act_bookmark = QAction(self)
        self._act_bookmark.setShortcut(QKeySequence("Ctrl+B"))
        self._act_bookmark.triggered.connect(self._action_toggle_bookmark)
        self._menu_edit.addAction(self._act_bookmark)
        self._act_next_bookmark = QAction(self)
        self._act_next_bookmark.setShortcut(QKeySequence("F2"))
        self._act_next_bookmark.triggered.connect(lambda: self._action_goto_bookmark(1))
        self._menu_edit.addAction(self._act_next_bookmark)
        self._act_prev_bookmark = QAction(self)
        self._act_prev_bookmark.setShortcut(QKeySequence("Shift+F2"))
        self._act_prev_bookmark.triggered.connect(lambda: self._action_goto_bookmark(-1))
        self._menu_edit.addAction(self._act_prev_bookmark)
        self._act_clear_bookmarks = QAction(self)
        self._act_clear_bookmarks.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self._act_clear_bookmarks.triggered.connect(self._action_clear_bookmarks)
        self._menu_edit.addAction(self._act_clear_bookmarks)

        self._menu_edit.addSeparator()
        self._act_highlight = QAction(self)
        self._act_highlight.triggered.connect(self._action_highlight_rules)
        self._menu_edit.addAction(self._act_highlight)

        self._act_merge = QAction(self)
        self._act_merge.triggered.connect(self._action_merge_tabs)
        self._menu_edit.addAction(self._act_merge)

        # ── Language ──
        self._menu_lang = mb.addMenu("")

        self._lang_actions: dict[str, QAction] = {}
        for code, name in i18n.available_locales():
            action = QAction(name, self)
            action.setCheckable(True)
            action.triggered.connect(lambda _=False, c=code: self._action_set_language(c))
            self._menu_lang.addAction(action)
            self._lang_actions[code] = action

        # ── Help ──
        self._menu_help = mb.addMenu("")
        self._act_help_ref = QAction(self)
        self._act_help_ref.triggered.connect(self._action_help)
        self._menu_help.addAction(self._act_help_ref)

        self._act_changelog = QAction(self)
        self._act_changelog.triggered.connect(self._action_changelog)
        self._menu_help.addAction(self._act_changelog)

        self._menu_help.addSeparator()

        self._act_about = QAction(self)
        self._act_about.triggered.connect(self._action_about)
        self._menu_help.addAction(self._act_about)

        # ── Day / night switch, at the right end of the menu bar ──
        self._theme_btn = QToolButton()
        self._theme_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.setMinimumWidth(84)
        self._theme_btn.setStyleSheet(
            f"QToolButton {{ background: transparent; color: {C_MUTED}; border: none;"
            f" border-radius: 5px; padding: 3px 10px; font-size: 12px; }}"
            f"QToolButton:hover {{ color: {C_TEXT}; background: {C_HOVER}; }}"
            f"QToolButton::menu-button {{ border: none; width: 14px; background: transparent; }}"
            f"QToolButton::menu-button:hover {{ background: {C_HOVER}; border-radius: 5px; }}"
        )
        self._theme_btn.clicked.connect(self._toggle_theme)
        # The arrow next to the button picks the mode: follow the system, or force one
        self._theme_menu = QMenu(self._theme_btn)
        self._theme_actions: dict[str, QAction] = {}
        group = QActionGroup(self)
        for mode in ui_theme.MODES:
            action = QAction(self, checkable=True)
            action.triggered.connect(lambda _=False, m=mode: self._set_theme_mode(m))
            group.addAction(action)
            self._theme_menu.addAction(action)
            self._theme_actions[mode] = action
        self._theme_btn.setMenu(self._theme_menu)
        self._theme_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        hints = QGuiApplication.styleHints()
        if hints is not None:
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)
        corner = QWidget()
        corner.setStyleSheet("background: transparent;")
        corner_lay = QHBoxLayout(corner)
        corner_lay.setContentsMargins(0, 0, 12, 0)   # keep the button off the window edge
        corner_lay.addWidget(self._theme_btn)
        mb.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        self._act_theme = QShortcut(QKeySequence("Ctrl+Shift+L"), self)
        self._act_theme.activated.connect(self._toggle_theme)

        self._retranslate_menubar()

    def _toggle_theme(self) -> None:
        """Day <-> night (an explicit choice: it leaves the "follow the system" mode)."""
        self._set_theme_mode("light" if ui_theme.current_theme() == "dark" else "dark")

    def _set_theme_mode(self, mode: str) -> None:
        ui_theme.apply_mode(QApplication.instance(), mode)
        ui_theme.save_theme()
        self._refresh_theme_btn()

    def _on_system_scheme_changed(self, *_args) -> None:
        if ui_theme.theme_mode() == "auto":
            ui_theme.apply_style(QApplication.instance(), ui_theme.system_theme())

    def _refresh_theme_btn(self) -> None:
        # Shows the mode a click switches to: "Day" (sun) while dark, "Night" (moon) while light
        to_light = ui_theme.current_theme() == "dark"
        self._theme_btn.setIcon(_svg_icon(_SVG_SUN if to_light else _SVG_MOON, C_MUTED, 15))
        self._theme_btn.setText(i18n.tr("theme_day" if to_light else "theme_night"))
        labels = {"auto": i18n.tr("theme_auto"), "light": i18n.tr("theme_day"),
                  "dark": i18n.tr("theme_night")}
        for mode, action in self._theme_actions.items():
            action.setText(labels[mode])
            action.setChecked(mode == ui_theme.theme_mode())

    def _on_theme_changed(self, theme: str) -> None:
        """Re-colour what stylesheets cannot reach: icons, painted widgets, saved styles."""
        self._splitter_style = ui_theme.convert_qss(self._splitter_style, theme)
        for btn in self._nav._buttons:
            btn.retheme()
        self._btn_left_toggle._apply_style()
        self._btn_right_toggle._apply_style()
        for btn in self._top_tabs.tabBar().findChildren(_TabCloseBtn):
            btn.retheme()
        self._sidebar.retheme()
        for viewer in self.findChildren(LogViewer):
            viewer.retheme()
        self._remote_panel.reload()
        self._refresh_theme_btn()
        self.update()

    def _retranslate_menubar(self) -> None:
        locale = i18n.get_locale()
        self._refresh_theme_btn()
        self._menu_file.setTitle(i18n.tr("menu_file"))
        self._act_open.setText(i18n.tr("action_open"))
        self._act_close_tab.setText(i18n.tr("action_close_tab"))
        self._act_export.setText(i18n.tr("action_export"))
        self._act_merge.setText(i18n.tr("action_merge"))
        self._act_reconnect.setText(i18n.tr("action_auto_reconnect"))
        self._act_close_all.setText(i18n.tr("action_close_all"))
        self._act_update.setText(i18n.tr("action_update"))
        self._act_quit.setText(i18n.tr("action_quit"))
        self._menu_edit.setTitle(i18n.tr("menu_edit"))
        self._act_copy.setText(i18n.tr("action_copy"))
        self._act_break.setText(i18n.tr("action_break"))
        self._act_highlight.setText(i18n.tr("action_highlight_rules"))
        self._act_bookmark.setText(i18n.tr("action_toggle_bookmark"))
        self._act_next_bookmark.setText(i18n.tr("action_next_bookmark"))
        self._act_prev_bookmark.setText(i18n.tr("action_prev_bookmark"))
        self._act_clear_bookmarks.setText(i18n.tr("action_clear_bookmarks"))
        self._menu_lang.setTitle(i18n.tr("menu_language"))
        for code, action in self._lang_actions.items():
            action.setChecked(code == locale)
        self._menu_help.setTitle(i18n.tr("menu_help"))
        self._act_help_ref.setText(i18n.tr("action_help_ref"))
        self._act_about.setText(i18n.tr("action_about"))
        self._act_changelog.setText(i18n.tr("action_changelog"))

    # ── Menu action handlers ───────────────────────────────────────────────────

    def _action_toggle_bookmark(self) -> None:
        """Edit → Toggle bookmark: mark the selected lines so F2 / Shift+F2 can come back."""
        viewer = self._active_viewer()
        if viewer:
            viewer.toggle_bookmark()

    def _action_clear_bookmarks(self) -> None:
        """Edit → Remove all bookmarks of the active log."""
        viewer = self._active_viewer()
        if viewer and not viewer.clear_bookmarks():
            self._status.showMessage(i18n.tr("status_no_bookmarks"), 3000)

    def _action_goto_bookmark(self, step: int) -> None:
        viewer = self._active_viewer()
        if viewer and not viewer.goto_bookmark(step):
            self._status.showMessage(i18n.tr("status_no_bookmarks"), 3000)

    def _action_highlight_rules(self) -> None:
        """Edit → Highlight rules: colour the lines that contain chosen words."""
        if HighlightRulesDialog(self).exec() == QDialog.DialogCode.Accepted:
            for viewer in self.findChildren(LogViewer):
                viewer.refresh_rules()

    def _action_open_file(self) -> None:
        """File → Open: browse and open a log file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            i18n.tr("action_open"),
            os.path.expanduser("~"),
            i18n.tr("filter_log_files"),
        )
        if path and os.path.isfile(path):
            # Updates FilePanel's recent list and opens the tab (open_tab signal)
            self._file_panel._open_path(path)

    def _set_auto_reconnect(self, on: bool) -> None:
        self._auto_reconnect = on
        config_store.set_pref("auto_reconnect", on)
        if not on:                      # cancel the countdowns already running
            for link in self._links.values():
                if link.state == cs.RECONNECTING:
                    link.cancel()
                    link.state = cs.FAILED
            for viewer in self.findChildren(LogViewer):
                self._refresh_tab_state(viewer)

    def _action_merge_tabs(self) -> None:
        """Edit → Merge logs: one tab that shows several logs interleaved by time."""
        sources: list[tuple[str, LogViewer]] = []
        for i in range(self._top_tabs.count()):
            spl = self._top_tabs.widget(i)
            if isinstance(spl, QSplitter):
                for viewer in spl.findChildren(LogViewer):
                    if not viewer.merged:
                        sources.append((self._top_tabs.tabText(i), viewer))
        if len(sources) < 2:
            self._status.showMessage(i18n.tr("status_merge_needs_two"), 4000)
            return
        dlg = MergeTabsDialog([f"{title}   {viewer.title_label.text()}" for title, viewer in sources], self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.merge_viewers([sources[i] for i in dlg.chosen()])

    def merge_viewers(self, sources: list[tuple[str, LogViewer]]) -> LogViewer:
        """Open a tab that shows *sources* (label, viewer) together, in time order."""
        merged = LogViewer(source_type="merged")
        labels = list(dict.fromkeys(label for label, _ in sources))
        merged.set_title(" + ".join(labels))
        for label, viewer in sources:
            merged.append_merged(label, viewer._model.all_events())
            # New lines of a source flow in as long as both stay open
            def feed(events, lb=label):
                merged.append_merged(lb, events)

            viewer.events_added.connect(feed)
            merged.destroyed.connect(
                lambda _=None, v=viewer, f=feed: self._unfeed(v, f))
        merged.stop_btn.setEnabled(False)
        merged.pane_close_requested.connect(lambda v=merged: self._close_pane(v))
        merged.pane_activated.connect(lambda v=merged: self._set_active_viewer(v))
        merged.export_requested.connect(
            lambda selection, v=merged: (self._set_active_viewer(v), self._action_export(selection))
        )
        spl = self._make_tab_splitter()
        spl.addWidget(merged)
        idx = self._top_tabs.addTab(spl, i18n.tr("merge_tab", n=len(sources)))
        self._top_tabs.setCurrentIndex(idx)
        self._set_active_viewer(merged)
        return merged

    @staticmethod
    def _unfeed(viewer: LogViewer, feed) -> None:
        try:
            viewer.events_added.disconnect(feed)
        except (RuntimeError, TypeError):
            pass      # the source is gone already

    def _action_export(self, selection_only: bool = False) -> None:
        """File → Export: save the lines shown in the active log (or its selection)."""
        viewer = self._active_viewer()
        if viewer is None:
            self._status.showMessage(i18n.tr("status_nothing_to_export"), 3000)
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            i18n.tr("action_export"),
            os.path.join(os.path.expanduser("~"), "simplelog-export.log"),
            i18n.tr("filter_export_files"),
        )
        if not path:
            return
        try:
            count = viewer.export_lines(path, selection_only)
        except OSError as exc:
            QMessageBox.warning(self, i18n.tr("action_export"), i18n.tr("err_export", error=exc))
            return
        self._status.showMessage(i18n.tr("status_exported", n=count, path=path), 5000)

    def _action_check_update(self) -> None:
        """File → Check for Updates: async GitHub release check."""
        from version import __version__
        from workers import UpdateWorker

        self._update_worker = UpdateWorker(__version__, i18n.get_locale())
        self._update_worker.up_to_date.connect(self._on_up_to_date)
        self._update_worker.update_available.connect(self._on_update_available)
        self._update_worker.error.connect(
            lambda msg: QMessageBox.warning(
                self, i18n.tr("update_title"), i18n.tr("update_error", error=msg)
            )
        )
        self._act_update.setEnabled(False)
        self._update_worker.finished.connect(lambda: self._act_update.setEnabled(True))
        self._update_worker.start()

    def _action_changelog(self) -> None:
        """Help → What's New: show the bundled changelog (online one if not bundled)."""
        text = changelog.local_text(i18n.get_locale())
        if not text:
            QDesktopServices.openUrl(QUrl(changelog.ONLINE_URL))
            return
        ChangelogDialog(self, i18n.tr("action_changelog"), text).exec()

    def _action_about(self) -> None:
        from version import __version__
        QMessageBox.about(
            self,
            i18n.tr("action_about"),
            f"<b>SimpleLog</b> v{__version__}<br><br>"
            f"Fast multi-source log viewer",
        )

    def _on_up_to_date(self, version: str) -> None:
        QMessageBox.information(
            self,
            i18n.tr("update_title"),
            i18n.tr("update_up_to_date", version=version),
        )

    def _on_update_available(self, latest: str, url: str, notes: str = "") -> None:
        from version import __version__
        header = i18n.tr("update_available", latest=latest, current=__version__)
        can_auto = self._auto_update_asset_url(latest) is not None
        action_label = i18n.tr("update_install") if can_auto else i18n.tr("update_download")

        if notes:
            dlg = ChangelogDialog(self, i18n.tr("update_title"), notes,
                                  header=header, action_label=action_label)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
        else:
            box = QMessageBox(self)
            box.setWindowTitle(i18n.tr("update_title"))
            box.setText(header)
            action_btn = box.addButton(action_label, QMessageBox.ButtonRole.AcceptRole)
            box.addButton(QMessageBox.StandardButton.Close)
            box.exec()
            if box.clickedButton() is not action_btn:
                return
        if can_auto:
            self._install_update(latest)
        else:
            QDesktopServices.openUrl(QUrl(url))

    def _auto_update_asset_url(self, tag: str) -> str | None:
        """Return the direct download URL for this platform+tag, or None if auto-update is unsupported."""
        base = f"https://github.com/simple-log-app/simplelog/releases/download/{tag}"
        if os.environ.get("APPIMAGE"):
            return f"{base}/simplelog-x86_64.AppImage"
        if (getattr(sys, "frozen", False) and platform.system() == "Darwin"
                and macos_app_bundle(sys.executable) is not None):
            return f"{base}/SimpleLog-macOS-universal.dmg"
        if getattr(sys, "frozen", False) and platform.system() == "Linux" and shutil.which("pkexec"):
            return f"{base}/simplelog_amd64.deb"
        return None

    def _install_update(self, tag: str) -> None:
        from version import __version__
        from workers import DownloadWorker

        asset_url = self._auto_update_asset_url(tag)
        if asset_url is None:
            return

        if asset_url.endswith(".AppImage"):
            suffix = ".AppImage"
        elif asset_url.endswith(".deb"):
            suffix = ".deb"
        else:
            suffix = ".dmg"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)

        progress = QProgressDialog(i18n.tr("update_downloading"), None, 0, 100, self)
        progress.setWindowTitle(i18n.tr("update_title"))
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        self._dl_worker = DownloadWorker(asset_url, tmp_path, __version__)
        self._dl_worker.progress.connect(progress.setValue)
        self._dl_worker.error.connect(lambda msg: (
            progress.close(),
            QMessageBox.warning(self, i18n.tr("update_title"), i18n.tr("update_install_error", error=msg)),
        ))
        self._dl_worker.finished.connect(lambda path: self._apply_update(path, progress))
        self._dl_worker.start()

    def _apply_update(self, tmp_path: str, progress: QProgressDialog) -> None:
        progress.close()

        if tmp_path.endswith(".deb"):
            # pkexec waits for the user to authenticate: keep the UI alive meanwhile
            self._deb_worker = DebInstallWorker(tmp_path)
            self._deb_worker.done.connect(self._on_deb_installed)
            self._deb_worker.start()
            return

        QMessageBox.information(self, i18n.tr("update_title"), i18n.tr("update_restarting"))

        pid = os.getpid()
        if tmp_path.endswith(".AppImage"):
            old_path = os.environ["APPIMAGE"]
            script = (
                f"#!/bin/sh\n"
                f"while kill -0 {pid} 2>/dev/null; do sleep 0.2; done\n"
                f"cp -f {shlex.quote(tmp_path)} {shlex.quote(old_path)}\n"
                f"chmod +x {shlex.quote(old_path)}\n"
                f"rm -f {shlex.quote(tmp_path)}\n"
                f"setsid {shlex.quote(old_path)} >/dev/null 2>&1 &\n"
                f"rm -- \"$0\"\n"
            )
        else:
            # macOS: replace .app bundle from mounted DMG
            app_bundle = macos_app_bundle(sys.executable)
            if app_bundle is None:
                QMessageBox.warning(
                    self, i18n.tr("update_title"),
                    i18n.tr("update_install_error", error=sys.executable),
                )
                return
            script = macos_update_script(pid, tmp_path, app_bundle)

        fd, script_path = tempfile.mkstemp(suffix=".sh")
        os.write(fd, script.encode())
        os.close(fd)
        os.chmod(script_path, stat.S_IRWXU)
        subprocess.Popen(["/bin/sh", script_path], close_fds=True)  # noqa: S603
        QApplication.quit()

    def _on_deb_installed(self, code: int, detail: str) -> None:
        if code != 0:
            QMessageBox.warning(
                self, i18n.tr("update_title"),
                i18n.tr("update_install_error", error=detail),
            )
            return
        QMessageBox.information(self, i18n.tr("update_title"), i18n.tr("update_restarting"))
        # Use a background script so the new binary starts after we exit
        pid = os.getpid()
        exe = sys.executable
        fd, script_path = tempfile.mkstemp(suffix=".sh")
        script = (
            f"#!/bin/sh\n"
            f"while kill -0 {pid} 2>/dev/null; do sleep 0.1; done\n"
            f"setsid {shlex.quote(exe)} >/dev/null 2>&1 &\n"
            f"rm -- \"$0\"\n"
        )
        os.write(fd, script.encode())
        os.close(fd)
        os.chmod(script_path, stat.S_IRWXU)
        subprocess.Popen(["/bin/sh", script_path], close_fds=True)  # noqa: S603
        QApplication.quit()

    def _action_copy(self) -> None:
        """Edit → Copy: copy selected text from active viewer."""
        viewer = self._active_viewer()
        if viewer:
            viewer.copy()

    def _action_break(self) -> None:
        viewer = self._active_viewer()
        if viewer:
            viewer.insert_break()

    def _action_help(self) -> None:
        """Help → CLI Reference: show documentation dialog."""
        dlg = QDialog(self)
        dlg.setWindowTitle(i18n.tr("help_title"))
        dlg.resize(560, 480)
        dlg.setStyleSheet(f"background: {C_BG}; color: {C_TEXT};")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(i18n.tr("help_content"))
        text.setStyleSheet(
            f"background: {C_CARD}; border: 1px solid {C_DIVIDER}; border-radius: 8px;"
            "font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 13px;"
            f"color: {C_TEXT}; padding: 12px;"
        )
        layout.addWidget(text)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(dlg.accept)
        btns.setStyleSheet(f"color: {C_TEXT};")
        layout.addWidget(btns)

        dlg.exec()

    def _action_set_language(self, locale: str) -> None:
        i18n.set_locale(locale)
        i18n.save_locale()
        i18n.retranslate_all()
        self._retranslate_menubar()
        self._status.showMessage(i18n.tr("status_ready"))

    def _active_viewer(self) -> LogViewer | None:
        return self._cur_viewer

    # ── Tab / pane management ─────────────────────────────────────────────────

    _MAX_PANES = 9

    def _make_tab_splitter(self, orient: Qt.Orientation = Qt.Orientation.Horizontal) -> QSplitter:
        s = QSplitter(orient)
        s.setChildrenCollapsible(False)
        s.setStyleSheet(self._splitter_style)
        return s

    def _current_tab_splitter(self) -> QSplitter | None:
        w = self._top_tabs.currentWidget()
        return w if isinstance(w, QSplitter) else None

    def _first_viewer_in(self, spl: QSplitter) -> LogViewer | None:
        for i in range(spl.count()):
            w = spl.widget(i)
            if isinstance(w, LogViewer):
                return w
            if isinstance(w, QSplitter):
                v = self._first_viewer_in(w)
                if v:
                    return v
        return None

    def _count_viewers_in(self, spl: QSplitter) -> int:
        total = 0
        for i in range(spl.count()):
            w = spl.widget(i)
            if isinstance(w, LogViewer):
                total += 1
            elif isinstance(w, QSplitter):
                total += self._count_viewers_in(w)
        return total

    def _stop_all_in_splitter(self, spl: QSplitter) -> None:
        for i in range(spl.count()):
            w = spl.widget(i)
            if isinstance(w, LogViewer):
                self._stop_viewer(w)
            elif isinstance(w, QSplitter):
                self._stop_all_in_splitter(w)

    def _set_active_viewer(self, viewer: LogViewer | None) -> None:
        self._cur_viewer = viewer
        self._sidebar.set_active_viewer(viewer)
        if viewer:
            viewer.focus_list()

    def _on_top_tab_changed(self, _idx: int) -> None:
        spl = self._current_tab_splitter()
        viewer = self._first_viewer_in(spl) if spl else None
        self._set_active_viewer(viewer)

    def _add_viewer_to_current_tab(
        self, viewer: LogViewer, orientation: Qt.Orientation, title: str
    ) -> None:
        spl = self._current_tab_splitter()
        if spl is None:
            spl = self._make_tab_splitter(orientation)
            idx = self._top_tabs.addTab(spl, title)
            self._top_tabs.setCurrentIndex(idx)
            spl.addWidget(viewer)
            return

        if self._count_viewers_in(spl) >= self._MAX_PANES:
            return

        active = self._cur_viewer
        parent_spl = active.parent() if active else None

        if isinstance(parent_spl, QSplitter) and parent_spl.orientation() == orientation:
            # Capture total before inserting so the window doesn't grow
            old_sizes = parent_spl.sizes()
            total = sum(old_sizes)
            idx = parent_spl.indexOf(active)
            parent_spl.insertWidget(idx + 1, viewer)
            n = parent_spl.count()
            if total > 0:
                share = total // n
                new_sizes = [share] * n
                new_sizes[-1] += total - sum(new_sizes)  # give remainder to last
                parent_spl.setSizes(new_sizes)
        elif isinstance(parent_spl, QSplitter):
            idx = parent_spl.indexOf(active)
            parent_sizes = parent_spl.sizes()
            sub = self._make_tab_splitter(orientation)
            active.setParent(None)
            sub.addWidget(active)
            sub.addWidget(viewer)
            sub.setStretchFactor(0, 1)
            sub.setStretchFactor(1, 1)
            parent_spl.insertWidget(idx, sub)
            parent_spl.setSizes(parent_sizes)
        else:
            spl.addWidget(viewer)

    def _close_tab_at(self, idx: int) -> None:
        spl = self._top_tabs.widget(idx)
        if isinstance(spl, QSplitter):
            self._stop_all_in_splitter(spl)
        self._top_tabs.removeTab(idx)
        if spl:
            spl.deleteLater()
        spl2 = self._current_tab_splitter()
        viewer = self._first_viewer_in(spl2) if spl2 else None
        self._set_active_viewer(viewer)

    def _close_pane(self, viewer: LogViewer) -> None:
        self._stop_viewer(viewer)
        parent = viewer.parent()
        viewer.setParent(None)
        viewer.deleteLater()
        if isinstance(parent, QSplitter):
            self._cleanup_empty_splitters(parent)
        spl = self._current_tab_splitter()
        self._set_active_viewer(self._first_viewer_in(spl) if spl else None)

    def _cleanup_empty_splitters(self, spl: QSplitter) -> None:
        if spl.count() > 0:
            return
        tab_idx = self._top_tabs.indexOf(spl)
        if tab_idx >= 0:
            self._top_tabs.removeTab(tab_idx)
            spl.deleteLater()
            return
        parent = spl.parent()
        spl.setParent(None)
        spl.deleteLater()
        if isinstance(parent, QSplitter):
            self._cleanup_empty_splitters(parent)

    # ── Nav ───────────────────────────────────────────────────────────────────

    def _on_nav_index_changed(self, idx: int):
        self._side_stack.setCurrentIndex(idx)
        if not self._side_stack.isVisible():
            self._toggle_left_sidebar()

    def _toggle_left_sidebar(self) -> None:
        visible = self._side_stack.isVisible()
        if visible:
            sizes = self._main_splitter.sizes()
            if sizes[0] > 0:
                self._left_sidebar_width = sizes[0]
            self._side_stack.setVisible(False)
        else:
            self._side_stack.setVisible(True)
            total = sum(self._main_splitter.sizes())
            self._main_splitter.setSizes([
                self._left_sidebar_width,
                max(1, total - self._left_sidebar_width),
            ])
        now_visible = not visible
        self._btn_left_toggle.set_svg(_SVG_CHEVRON_LEFT if now_visible else _SVG_CHEVRON_RIGHT)
        QTimer.singleShot(0, self._reposition_toggles)

    def _toggle_right_sidebar(self) -> None:
        visible = self._sidebar.isVisible()
        if visible:
            sizes = self._outer_splitter.sizes()
            if sizes[1] > 0:
                self._right_sidebar_width = sizes[1]
            self._sidebar.setVisible(False)
        else:
            self._sidebar.setVisible(True)
            total = sum(self._outer_splitter.sizes())
            self._outer_splitter.setSizes([
                max(1, total - self._right_sidebar_width),
                self._right_sidebar_width,
            ])
        now_visible = not visible
        self._btn_right_toggle.set_svg(_SVG_CHEVRON_RIGHT if now_visible else _SVG_CHEVRON_LEFT)
        QTimer.singleShot(0, self._reposition_toggles)

    def _reposition_toggles(self) -> None:
        central = self.centralWidget()
        if central is None:
            return
        btn_h = 40
        cy = (central.height() - btn_h) // 2

        # Left toggle: on the right edge of the side stack (or nav rail when hidden)
        anchor = self._side_stack if self._side_stack.isVisible() else self._nav
        pt = anchor.mapTo(central, QPoint(anchor.width(), 0))
        self._btn_left_toggle.move(pt.x() - 10, cy)
        self._btn_left_toggle.raise_()

        # Right toggle: on the left edge of the sidebar (or content-area right edge when hidden)
        if self._sidebar.isVisible():
            pt2 = self._sidebar.mapTo(central, QPoint(0, 0))
            rx = pt2.x() - 10
        else:
            rx = central.width() - 20
        self._btn_right_toggle.move(rx, cy)
        self._btn_right_toggle.raise_()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._reposition_toggles)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_btn_left_toggle"):
            self._reposition_toggles()

    # ── Tab factories ─────────────────────────────────────────────────────────

    def open_file_tab(self, path: str, tail_lines: int = 100, split: str = "tab"):
        worker = FileWorker(path, tail_lines=tail_lines)
        viewer = LogViewer(source_type="file")
        viewer.set_title(path)
        self._add_tab(os.path.basename(path), viewer, worker, split=split)

    def open_stdin_tab(self):
        worker = StdinWorker()
        viewer = LogViewer(source_type="stdin")
        viewer.set_title(i18n.tr("tab_stdin"))
        self._add_tab("stdin", viewer, worker, split="tab")

    def _connect_then(self, title: str, connect, done) -> None:
        """Run a blocking *connect()* in the background, then call done(result).

        Used when a tab has to open its own connection (e.g. a restored session):
        the network wait must not freeze the window.
        """
        self._status.showMessage(i18n.tr("ssh_connecting"))
        worker = CallWorker(connect)

        def _ok(result) -> None:
            self._status.showMessage(i18n.tr("status_ready"))
            done(result)

        def _failed(msg: str) -> None:
            self._status.showMessage(i18n.tr("status_ready"))
            QMessageBox.critical(self, title, msg)

        worker.success.connect(_ok)
        worker.failure.connect(_failed)
        self._connectors.add(worker)
        worker.finished.connect(lambda w=worker: self._connectors.discard(w))
        worker.start()

    def open_remote_tab(self, cfg: dict, split: str = "tab") -> None:
        """Open the log tab described by *cfg* (``cfg["type"]`` picks the provider)."""
        provider = providers.for_type(cfg.get("type", ""))
        if provider is None:
            return
        client = cfg.pop(provider.client_key, None) if provider.connect else None
        if provider.connect is not None and client is None:
            # No connection yet (e.g. a restored session): make it without freezing the UI
            self._connect_then(
                i18n.tr("err_provider_title", name=provider.name),
                lambda: provider.connect(cfg),
                lambda c: self._open_session(provider, cfg, c, split),
            )
            return
        self._open_session(provider, cfg, client, split)

    def _open_session(self, provider: providers.Provider, cfg: dict, client, split: str) -> None:
        session = provider.session(cfg, client)
        viewer = LogViewer(source_type=session.source)
        viewer.set_title(session.title)
        link = cs.Link(provider, dict(cfg))
        self._links[id(viewer)] = link
        viewer.destroyed.connect(lambda _=None, k=id(viewer): self._links.pop(k, None))
        self._add_tab(session.tab, viewer, session.worker, split, provider)

    # ── Internal tab management ───────────────────────────────────────────────

    def _attach_worker(self, viewer: LogViewer, worker) -> None:
        """Connect a (new) worker to the viewer that shows its lines."""
        worker.new_lines.connect(viewer.append_events)
        worker.status.connect(self._status.showMessage)
        worker.error.connect(lambda msg, v=viewer: self._on_error(msg, v))
        worker.new_lines.connect(lambda _events, v=viewer, w=worker: self._mark_live(v, w))
        if hasattr(worker, "history_done"):
            worker.history_done.connect(
                lambda n: self._status.showMessage(i18n.tr("history_loaded", n=n))
            )
            worker.history_done.connect(
                lambda _n, v=viewer, w=worker: (self._mark_live(v, w), v.end_resync()))
        if hasattr(worker, "finished"):
            worker.finished.connect(lambda v=viewer, w=worker: self._worker_finished(v, w))
        # A quiet stream sends no line to prove it is up: running a moment is enough
        self._after(viewer, 2500, lambda v=viewer, w=worker: self._mark_live(v, w))
        viewer.stop_btn.setEnabled(True)
        self._workers[id(viewer)] = worker
        self._set_state(viewer, cs.CONNECTING)

    def _wire_viewer(self, viewer: LogViewer, worker) -> None:
        self._attach_worker(viewer, worker)
        viewer.stop_requested.connect(lambda v=viewer: self._stop_viewer(v))
        viewer.pane_close_requested.connect(lambda v=viewer: self._close_pane(v))
        viewer.pane_activated.connect(lambda v=viewer: self._set_active_viewer(v))
        viewer.export_requested.connect(
            lambda selection, v=viewer: (self._set_active_viewer(v), self._action_export(selection))
        )

    def _discard(self, viewer: LogViewer, worker) -> None:
        """Throw away a viewer/worker pair that was never wired or started."""
        client = getattr(worker, "_client", None)
        if hasattr(client, "close"):
            try:
                client.close()
            except Exception:
                pass
        viewer.deleteLater()

    def _add_tab(self, title: str, viewer: LogViewer, worker, split: str = "tab",
                 provider: providers.Provider | None = None):
        if split in ("vertical", "horizontal"):
            spl = self._current_tab_splitter()
            if spl is not None and self._count_viewers_in(spl) >= self._MAX_PANES:
                self._status.showMessage(i18n.tr("err_max_panes", n=self._MAX_PANES))
                self._discard(viewer, worker)
                return
        self._wire_viewer(viewer, worker)

        tabs_before = self._top_tabs.count()
        if split == "vertical":
            self._add_viewer_to_current_tab(viewer, Qt.Orientation.Horizontal, title)
        elif split == "horizontal":
            self._add_viewer_to_current_tab(viewer, Qt.Orientation.Vertical, title)
        else:
            spl = self._make_tab_splitter()
            spl.addWidget(viewer)
            idx = self._top_tabs.addTab(spl, title)
            self._top_tabs.setCurrentIndex(idx)

        if provider is not None and self._top_tabs.count() > tabs_before:
            self._top_tabs.setTabIcon(
                self._top_tabs.count() - 1,
                QIcon(provider_logo(provider.logo, provider.icon, provider.color, 14, tile=False)),
            )
        self._refresh_tab_state(viewer)

        self._set_active_viewer(viewer)
        worker.start()

    def _action_close_current_tab(self) -> None:
        if self._top_tabs.count() > 0:
            self._close_tab_at(self._top_tabs.currentIndex())

    def _action_close_all_logs(self):
        while self._top_tabs.count() > 0:
            self._close_tab_at(0)

    def _stop_viewer(self, viewer: LogViewer, by_user: bool = True):
        """Ask the viewer's worker to stop; it winds down in the background."""
        worker = self._workers.pop(id(viewer), None)
        if worker is not None and worker.isRunning():
            worker.stop()
            self._stopping.add(worker)
            worker.finished.connect(lambda w=worker: self._reap(w))
        if viewer:
            viewer.stop_btn.setEnabled(False)
            link = self._links.get(id(viewer))
            if by_user and link is not None:
                link.cancel()                       # no reconnection behind the user's back
                self._set_state(viewer, cs.STOPPED)

    def _reap(self, worker) -> None:
        worker.wait()   # already finishing: returns at once
        self._stopping.discard(worker)

    def _on_error(self, msg: str, viewer: LogViewer):
        if id(viewer) not in self._workers:
            return   # tab closed or worker stopped: its late error is of no interest
        self._stop_viewer(viewer, by_user=False)
        self._lost(viewer, msg)

    # ── Connection state and automatic reconnection ───────────────────────────

    def _after(self, viewer: LogViewer, ms: int, fn) -> None:
        """Run *fn* later, unless the viewer is gone by then (the timer dies with it)."""
        timer = QTimer(viewer)
        timer.setSingleShot(True)
        timer.timeout.connect(fn)
        timer.start(ms)

    def _lost(self, viewer: LogViewer, msg: str) -> None:
        """A remote log stopped with an error: retry later, or tell the user we gave up."""
        link = self._links.get(id(viewer))
        if link is not None and self._auto_reconnect and link.can_retry():
            delay = link.next_delay()
            gen = link.generation
            link.detail = i18n.tr("conn_reconnecting", s=delay, n=link.attempts,
                                  max=len(cs.RECONNECT_DELAYS))
            self._set_state(viewer, cs.RECONNECTING)
            self._status.showMessage(f"{link.detail} — {msg}")
            self._after(viewer, delay * 1000, lambda v=viewer, g=gen: self._reconnect(v, g))
            return
        if link is not None:
            self._set_state(viewer, cs.FAILED)
        self._status.showMessage(i18n.tr("err_prefix", msg=msg))
        QMessageBox.critical(self, i18n.tr("err_worker"), msg)

    def _reconnect(self, viewer: LogViewer, generation: int) -> None:
        link = self._links.get(id(viewer))
        if link is None or link.generation != generation or id(viewer) in self._workers:
            return        # stopped / closed / already running again
        provider = link.provider
        newest = viewer.newest_ts()
        gap = max(0.0, time.time() - (newest / 1000 if newest else link.last_ok))
        cfg = link.reconnect_cfg(gap)
        self._set_state(viewer, cs.CONNECTING)

        def start(client) -> None:
            if link.generation != generation:
                return
            try:
                session = provider.session(dict(cfg), client)
            except Exception as exc:       # a broken config cannot be fixed by waiting
                self._lost(viewer, str(exc))
                return
            viewer.begin_resync()
            self._after(viewer, 20000, viewer.end_resync)    # streams send no end-of-history mark
            viewer.insert_break()
            self._attach_worker(viewer, session.worker)
            session.worker.start()

        if provider.connect is None:
            start(None)
            return
        worker = CallWorker(lambda: provider.connect(dict(cfg)))
        worker.success.connect(start)
        worker.failure.connect(lambda msg: link.generation == generation and self._lost(viewer, msg))
        self._connectors.add(worker)
        worker.finished.connect(lambda w=worker: self._connectors.discard(w))
        worker.start()

    def _mark_live(self, viewer: LogViewer, worker) -> None:
        link = self._links.get(id(viewer))
        if link is None or self._workers.get(id(viewer)) is not worker:
            return
        if link.state != cs.LIVE:
            was_reconnect = link.attempts > 0
            link.connected()
            link.detail = ""
            self._set_state(viewer, cs.LIVE)
            if was_reconnect:
                self._status.showMessage(i18n.tr("status_reconnected"), 5000)

    def _worker_finished(self, viewer: LogViewer, worker) -> None:
        """A stream that simply ends (not stopped, no error) is shown as ended."""
        link = self._links.get(id(viewer))
        if link is not None and self._workers.get(id(viewer)) is worker \
                and link.state in (cs.CONNECTING, cs.LIVE):
            self._set_state(viewer, cs.ENDED)

    def _set_state(self, viewer: LogViewer, state: str) -> None:
        link = self._links.get(id(viewer))
        if link is None:
            return
        link.state = state
        if state != cs.RECONNECTING:
            link.detail = ""                   # the countdown text only belongs to its state
        self._refresh_tab_state(viewer)

    def _tab_of(self, viewer: LogViewer) -> int:
        widget = viewer
        while widget is not None:
            idx = self._top_tabs.indexOf(widget)
            if idx >= 0:
                return idx
            widget = widget.parentWidget()
        return -1

    def _refresh_tab_state(self, viewer: LogViewer) -> None:
        """Show the worst connection state of the tab's logs as a dot on its logo."""
        idx = self._tab_of(viewer)
        if idx < 0:
            return
        spl = self._top_tabs.widget(idx)
        links = [self._links[id(v)] for v in spl.findChildren(LogViewer) if id(v) in self._links]
        state = cs.worst([lk.state for lk in links])
        if state is None:
            return
        lead = links[0].provider
        colors = {cs.LIVE: C_INFO, cs.CONNECTING: C_WARN, cs.RECONNECTING: C_WARN,
                  cs.FAILED: C_ERR, cs.STOPPED: C_MUTED, cs.ENDED: C_MUTED}
        pixmap = provider_logo(lead.logo, lead.icon, lead.color, 14, tile=False)
        self._top_tabs.setTabIcon(idx, QIcon(with_status_dot(pixmap, colors[state])))
        detail = next((lk.detail for lk in links if lk.state == state and lk.detail), "")
        self._top_tabs.setTabToolTip(idx, detail or i18n.tr(f"conn_{state}"))

    def closeEvent(self, event):  # noqa: N802
        running = [w for w in (*self._workers.values(), *self._stopping) if w.isRunning()]
        for worker in running:
            worker.stop()
        # One shared budget: a worker stuck in a network call must not delay quitting
        deadline = time.monotonic() + 2.0
        for worker in running:
            worker.wait(max(0, int((deadline - time.monotonic()) * 1000)))
        event.accept()
