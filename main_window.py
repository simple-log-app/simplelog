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

from PyQt6.QtCore import (
    QPoint,
    Qt,
    QTimer,
    QUrl,
)
from PyQt6.QtGui import (
    QAction,
    QDesktopServices,
    QKeySequence,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import azure_utils
import changelog
import gcp_utils
import i18n
import ssh_utils
from log_view import LogViewer
from panels.file import FilePanel
from remote_dialogs import RemoteHomePanel
from sidebar import FilterSearchSidebar
from ui_theme import (
    _SVG_CHEVRON_LEFT,
    _SVG_CHEVRON_RIGHT,
    C_ACCENT,
    C_BG,
    C_BORDER,
    C_CARD,
    C_DIVIDER,
    C_MUTED,
    C_PANEL,
    C_SIDE,
    C_STATUS,
    C_TEXT,
)
from ui_widgets import NavRail, _SidebarEdgeBtn, _SLTabWidget
from workers import (
    AzureWorker,
    CloudflareWorker,
    DatadogWorker,
    DockerComposeWorker,
    DockerContainerWorker,
    DockerExecFileWorker,
    ElasticWorker,
    FileWorker,
    FlyioWorker,
    GCPWorker,
    KubernetesWorker,
    LokiWorker,
    RailwayWorker,
    SSHWorker,
    StdinWorker,
    TailWorker,
    VercelWorker,
)

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
        self._cur_viewer: LogViewer | None = None
        self._splitter_style: str = ""
        self._update_worker = None  # UpdateWorker instance (kept alive)
        self._left_sidebar_width: int = 326
        self._right_sidebar_width: int = 240
        self._build_ui()
        self._build_menubar()

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
        self._remote_panel.tab_requested.connect(self._dispatch_open_tab)
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
        self._top_tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: none; background: {C_BG}; border-top: 1px solid {C_BORDER}; }}"
            f"QTabBar::tab {{ background: {C_PANEL}; color: {C_MUTED};"
            f" padding: 0 16px 0 14px; min-height: 38px; border: none;"
            f" border-right: 1px solid {C_BORDER}; }}"
            f"QTabBar::tab:selected {{ background: {C_BG}; color: {C_TEXT};"
            f" border-top: 2px solid {C_ACCENT}; }}"
            f"QTabBar::tab:hover:!selected {{ color: {C_TEXT};"
            f" background: rgba(255,255,255,5); }}"
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
        self._outer_splitter.setSizes([10000, 240])
        self._outer_splitter.setStretchFactor(0, 1)
        self._outer_splitter.setStretchFactor(1, 0)
        self._outer_splitter.splitterMoved.connect(lambda *_: self._reposition_toggles())

        # Main splitter: left panel | content+right-sidebar
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setChildrenCollapsible(False)
        self._main_splitter.setStyleSheet(self._splitter_style)
        self._main_splitter.addWidget(self._side_stack)
        self._main_splitter.addWidget(self._outer_splitter)
        self._main_splitter.setSizes([326, 10000])
        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.splitterMoved.connect(lambda *_: self._reposition_toggles())
        root.addWidget(self._main_splitter, stretch=1)

        # Floating edge toggle buttons (overlaid on central widget)
        self._btn_left_toggle = _SidebarEdgeBtn("left", central)
        self._btn_left_toggle.set_svg(_SVG_CHEVRON_LEFT)
        self._btn_left_toggle.setToolTip("Toggle sidebar  (Ctrl+\\)")
        self._btn_left_toggle.clicked.connect(self._toggle_left_sidebar)
        self._btn_left_toggle.show()

        self._btn_right_toggle = _SidebarEdgeBtn("right", central)
        self._btn_right_toggle.set_svg(_SVG_CHEVRON_RIGHT)
        self._btn_right_toggle.setToolTip("Toggle search panel  (Ctrl+Shift+F)")
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

        self._act_close_all = QAction(self)
        self._act_close_all.setShortcut(QKeySequence("Ctrl+W"))
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

        # ── Language ──
        self._menu_lang = mb.addMenu("")
        ag = QButtonGroup(self)  # not actually needed but keeps logic tidy
        ag  # noqa: B018

        self._act_lang_en = QAction(self)
        self._act_lang_en.setCheckable(True)
        self._act_lang_en.triggered.connect(lambda: self._action_set_language("en"))
        self._menu_lang.addAction(self._act_lang_en)

        self._act_lang_fr = QAction(self)
        self._act_lang_fr.setCheckable(True)
        self._act_lang_fr.triggered.connect(lambda: self._action_set_language("fr"))
        self._menu_lang.addAction(self._act_lang_fr)

        self._act_lang_de = QAction(self)
        self._act_lang_de.setCheckable(True)
        self._act_lang_de.triggered.connect(lambda: self._action_set_language("de"))
        self._menu_lang.addAction(self._act_lang_de)

        self._act_lang_es = QAction(self)
        self._act_lang_es.setCheckable(True)
        self._act_lang_es.triggered.connect(lambda: self._action_set_language("es"))
        self._menu_lang.addAction(self._act_lang_es)

        self._act_lang_zh = QAction(self)
        self._act_lang_zh.setCheckable(True)
        self._act_lang_zh.triggered.connect(lambda: self._action_set_language("zh"))
        self._menu_lang.addAction(self._act_lang_zh)

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

        self._retranslate_menubar()

    def _retranslate_menubar(self) -> None:
        locale = i18n.get_locale()
        self._menu_file.setTitle(i18n.tr("menu_file"))
        self._act_open.setText(i18n.tr("action_open"))
        self._act_close_all.setText(i18n.tr("action_close_all"))
        self._act_update.setText(i18n.tr("action_update"))
        self._act_quit.setText(i18n.tr("action_quit"))
        self._menu_edit.setTitle(i18n.tr("menu_edit"))
        self._act_copy.setText(i18n.tr("action_copy"))
        self._act_break.setText(i18n.tr("action_break"))
        self._menu_lang.setTitle(i18n.tr("menu_language"))
        self._act_lang_en.setText(i18n.tr("lang_english"))
        self._act_lang_en.setChecked(locale == "en")
        self._act_lang_fr.setText(i18n.tr("lang_french"))
        self._act_lang_fr.setChecked(locale == "fr")
        self._act_lang_de.setText(i18n.tr("lang_german"))
        self._act_lang_de.setChecked(locale == "de")
        self._act_lang_es.setText(i18n.tr("lang_spanish"))
        self._act_lang_es.setChecked(locale == "es")
        self._act_lang_zh.setText(i18n.tr("lang_chinese"))
        self._act_lang_zh.setChecked(locale == "zh")
        self._menu_help.setTitle(i18n.tr("menu_help"))
        self._act_help_ref.setText(i18n.tr("action_help_ref"))
        self._act_about.setText(i18n.tr("action_about"))
        self._act_changelog.setText(i18n.tr("action_changelog"))

    # ── Menu action handlers ───────────────────────────────────────────────────

    def _action_open_file(self) -> None:
        """File → Open: browse and open a log file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            i18n.tr("action_open"),
            os.path.expanduser("~"),
            "Log files (*.log *.txt *.out *.err *.json);;All files (*)",
        )
        if path and os.path.isfile(path):
            self.open_file_tab(path)
            # Also update FilePanel's recent list
            self._file_panel._open_path(path)

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
            # Run pkexec without capture_output so polkit can show its
            # authentication dialog and communicate with the session agent.
            log_path = os.path.join(tempfile.gettempdir(), "simplelog-update.log")
            with open(log_path, "w") as log_f:
                result = subprocess.run(  # noqa: S603
                    ["pkexec", "dpkg", "-i", tmp_path],
                    stdout=log_f, stderr=log_f,
                )
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            if result.returncode != 0:
                try:
                    error_detail = open(log_path).read(500)  # noqa: SIM115
                except OSError:
                    error_detail = f"exit code {result.returncode}"
                QMessageBox.warning(
                    self, i18n.tr("update_title"),
                    i18n.tr("update_install_error", error=error_detail),
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
                f"setsid '{exe}' >/dev/null 2>&1 &\n"
                f"rm -- \"$0\"\n"
            )
            os.write(fd, script.encode())
            os.close(fd)
            os.chmod(script_path, stat.S_IRWXU)
            subprocess.Popen(["/bin/sh", script_path], close_fds=True)  # noqa: S603
            QApplication.quit()
            return

        QMessageBox.information(self, i18n.tr("update_title"), i18n.tr("update_restarting"))

        pid = os.getpid()
        if tmp_path.endswith(".AppImage"):
            old_path = os.environ["APPIMAGE"]
            script = (
                f"#!/bin/sh\n"
                f"while kill -0 {pid} 2>/dev/null; do sleep 0.2; done\n"
                f"cp -f '{tmp_path}' '{old_path}'\n"
                f"chmod +x '{old_path}'\n"
                f"rm -f '{tmp_path}'\n"
                f"setsid '{old_path}' >/dev/null 2>&1 &\n"
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

    def _dispatch_open_tab(self, cfg: dict, split: str = "tab") -> None:
        dispatch = {
            "cloudwatch":       self.open_cloudwatch_tab,
            "ssh":              self.open_ssh_tab,
            "docker_container": self.open_docker_tab,
            "docker_compose":   self.open_docker_tab,
            "docker_exec_file": self.open_docker_tab,
            "vercel":           self.open_vercel_tab,
            "gcp":              self.open_gcp_tab,
            "azure":            self.open_azure_tab,
            "loki":             self.open_loki_tab,
            "datadog":          self.open_datadog_tab,
            "elastic":          self.open_elastic_tab,
            "railway":          self.open_railway_tab,
            "flyio":            self.open_flyio_tab,
            "kubernetes":       self.open_kubernetes_tab,
            "cloudflare":       self.open_cloudflare_tab,
        }
        fn = dispatch.get(cfg.get("type", ""))
        if fn:
            fn(cfg, split)

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

    def open_cloudwatch_tab(self, cfg: dict, split: str = "tab"):
        worker = TailWorker(
            cfg["client"], cfg["group"], cfg["stream"],
            cfg["filter"], cfg["interval"], cfg["lookback"],
        )
        viewer = LogViewer(source_type="cloudwatch")
        stream_label = cfg["stream"] or "(all streams)"
        viewer.set_title(f"{cfg['group']}  ›  {stream_label}")
        tab_title = (cfg["stream"] or cfg["group"]).split("/")[-1]
        self._add_tab(tab_title, viewer, worker, split=split)

    def open_file_tab(self, path: str, tail_lines: int = 100, split: str = "tab"):
        worker = FileWorker(path, tail_lines=tail_lines)
        viewer = LogViewer(source_type="file")
        viewer.set_title(path)
        self._add_tab(os.path.basename(path), viewer, worker, split=split)

    def open_stdin_tab(self):
        worker = StdinWorker()
        viewer = LogViewer(source_type="stdin")
        viewer.set_title("stdin — piped input")
        self._add_tab("stdin", viewer, worker, split="tab")

    def open_ssh_tab(self, cfg: dict, split: str = "tab"):
        client = cfg.pop("_client", None)
        if client is None:
            try:
                client = ssh_utils.make_client(
                    cfg["host"], cfg["user"], cfg.get("port", 22),
                    key_path=cfg.get("key_path") or None,
                    password=cfg.get("password") or None,
                )
            except RuntimeError as e:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "SSH Error", str(e))
                return
        worker = SSHWorker(client, cfg["remote_path"], cfg.get("tail_lines", 100))
        viewer = LogViewer(source_type="ssh")
        viewer.set_title(f"{cfg['user']}@{cfg['host']}:{cfg['remote_path']}")
        tab_title = cfg["remote_path"].rsplit("/", 1)[-1] or cfg["host"]
        self._add_tab(tab_title, viewer, worker, split)

    def open_docker_tab(self, cfg: dict, split: str = "tab"):
        dtype = cfg["type"]
        if dtype == "docker_container":
            worker = DockerContainerWorker(cfg["container_id"], lookback_s=cfg.get("lookback_s", 3600))
            viewer = LogViewer(source_type="docker")
            viewer.set_title(f"docker  ›  {cfg.get('container_name', cfg['container_id'][:12])}")
            tab_title = cfg.get("container_name", cfg["container_id"][:12])
        elif dtype == "docker_compose":
            worker = DockerComposeWorker(cfg["project_name"], lookback_s=cfg.get("lookback_s", 3600))
            viewer = LogViewer(source_type="docker_compose")
            viewer.set_title(f"compose  ›  {cfg['project_name']}")
            tab_title = cfg["project_name"]
        else:  # docker_exec_file
            worker = DockerExecFileWorker(cfg["container_id"], cfg["remote_path"], cfg.get("tail_lines", 100))
            viewer = LogViewer(source_type="docker_exec_file")
            viewer.set_title(f"{cfg.get('container_name', '')}  ›  {cfg['remote_path']}")
            tab_title = cfg["remote_path"].rsplit("/", 1)[-1] or cfg.get("container_name", "docker")
        self._add_tab(tab_title, viewer, worker, split)

    def open_vercel_tab(self, cfg: dict, split: str = "tab"):
        worker = VercelWorker(
            cfg["token"], cfg["project_id"], cfg["project_name"],
            cfg["deployment_id"], interval_s=cfg.get("interval_s", 3),
            lookback_s=cfg.get("lookback_s", 3600),
        )
        viewer = LogViewer(source_type="vercel")
        viewer.set_title(f"vercel  ›  {cfg['project_name']}")
        self._add_tab(cfg["project_name"], viewer, worker, split)

    def open_gcp_tab(self, cfg: dict, split: str = "tab"):
        client = cfg.pop("_client", None)
        if client is None:
            try:
                client = gcp_utils.make_client(
                    cfg["project_id"],
                    cfg.get("key_path") or None,
                )
            except RuntimeError as e:
                QMessageBox.critical(self, "GCP Error", str(e))
                return
        worker = GCPWorker(
            client, cfg["project_id"],
            cfg.get("resource_type", "(all)"),
            cfg.get("severity", "ALL"),
            cfg.get("custom_filter", ""),
            lookback_s=cfg.get("lookback_s", 3600),
            interval_s=cfg.get("interval_s", 5),
        )
        viewer = LogViewer(source_type="gcp")
        viewer.set_title(f"gcp  ›  {cfg['project_id']}")
        self._add_tab(cfg["project_id"], viewer, worker, split)

    def open_azure_tab(self, cfg: dict, split: str = "tab"):
        logs_client = cfg.pop("_logs_client", None)
        if logs_client is None:
            try:
                cred = azure_utils.make_credential(
                    cfg["tenant_id"], cfg["client_id"], cfg["client_secret"]
                )
                logs_client = azure_utils.make_logs_client(cred)
            except RuntimeError as e:
                QMessageBox.critical(self, "Azure Error", str(e))
                return
        label = cfg.get("label", "azure")
        worker = AzureWorker(
            logs_client, cfg["workspace_id"], cfg["query"],
            label=label,
            lookback_s=cfg.get("lookback_s", 3600),
            interval_s=cfg.get("interval_s", 10),
        )
        viewer = LogViewer(source_type="azure")
        viewer.set_title(f"azure  ›  {label}")
        self._add_tab(label, viewer, worker, split)

    def open_loki_tab(self, cfg: dict, split: str = "tab"):
        url   = cfg["url"]
        query = cfg["query"]
        auth  = cfg.get("auth_mode", 0)
        label = cfg.get("label", url.split("//", 1)[-1].split("/")[0])
        worker = LokiWorker(
            url, query,
            username=cfg.get("username", "") if auth == 1 else "",
            password=cfg.get("password", "") if auth == 1 else "",
            token=cfg.get("token", "")    if auth == 2 else "",
            lookback_s=cfg.get("lookback_s", 3600),
            interval_s=cfg.get("interval_s", 5),
        )
        viewer = LogViewer(source_type="loki")
        viewer.set_title(f"loki  ›  {label}")
        self._add_tab(label, viewer, worker, split)

    def open_datadog_tab(self, cfg: dict, split: str = "tab"):
        label = cfg.get("label", cfg.get("base_url", "datadog"))
        worker = DatadogWorker(
            cfg["base_url"], cfg.get("query", "*"),
            cfg["api_key"], cfg["app_key"],
            lookback_s=cfg.get("lookback_s", 3600),
            interval_s=cfg.get("interval_s", 10),
        )
        viewer = LogViewer(source_type="datadog")
        viewer.set_title(f"datadog  ›  {label}")
        self._add_tab(label, viewer, worker, split)

    def open_elastic_tab(self, cfg: dict, split: str = "tab"):
        label = cfg.get("label", cfg.get("url", "elastic"))
        auth  = cfg.get("auth_mode", 0)
        worker = ElasticWorker(
            cfg["url"], cfg["index"], cfg.get("query", "*"),
            api_key=cfg.get("api_key", "")  if auth == 1 else "",
            username=cfg.get("username", "") if auth == 2 else "",
            password=cfg.get("password", "") if auth == 2 else "",
            ts_field=cfg.get("ts_field", "@timestamp"),
            lookback_s=cfg.get("lookback_s", 3600),
            interval_s=cfg.get("interval_s", 10),
        )
        viewer = LogViewer(source_type="elastic")
        viewer.set_title(f"elastic  ›  {label}")
        self._add_tab(label, viewer, worker, split)

    def open_railway_tab(self, cfg: dict, split: str = "tab"):
        label = cfg.get("label", cfg.get("service_name", "railway"))
        worker = RailwayWorker(
            cfg["token"], cfg["project_name"], cfg["service_name"],
            cfg["service_id"], interval_s=cfg.get("interval_s", 10),
            lookback_s=cfg.get("lookback_s", 3600),
        )
        viewer = LogViewer(source_type="railway")
        viewer.set_title(f"railway  ›  {label}")
        self._add_tab(label, viewer, worker, split)

    def open_flyio_tab(self, cfg: dict, split: str = "tab"):
        label = cfg.get("label", cfg.get("app_name", "fly.io"))
        worker = FlyioWorker(
            cfg["token"], cfg["app_name"],
            interval_s=cfg.get("interval_s", 5),
            lookback_s=cfg.get("lookback_s", 3600),
        )
        viewer = LogViewer(source_type="flyio")
        viewer.set_title(f"fly.io  ›  {label}")
        self._add_tab(label, viewer, worker, split)

    def open_kubernetes_tab(self, cfg: dict, split: str = "tab"):
        label = cfg.get("label", cfg.get("pod", "k8s"))
        worker = KubernetesWorker(
            cfg["pod"], cfg["namespace"],
            context=cfg.get("context", ""),
            container=cfg.get("container", ""),
            lookback_s=cfg.get("lookback_s", 3600),
        )
        viewer = LogViewer(source_type="kubernetes")
        viewer.set_title(f"k8s  ›  {label}")
        self._add_tab(label, viewer, worker, split)

    def open_cloudflare_tab(self, cfg: dict, split: str = "tab"):
        label = cfg.get("label", cfg.get("script_name", "worker"))
        worker = CloudflareWorker(
            cfg["api_token"], cfg["account_id"], cfg["script_name"],
        )
        viewer = LogViewer(source_type="cloudflare")
        viewer.set_title(f"cloudflare  ›  {label}")
        self._add_tab(label, viewer, worker, split)

    # ── Internal tab management ───────────────────────────────────────────────

    def _wire_viewer(self, viewer: LogViewer, worker) -> None:
        worker.new_lines.connect(viewer.append_events)
        worker.status.connect(self._status.showMessage)
        worker.error.connect(lambda msg, v=viewer: self._on_error(msg, v))
        if hasattr(worker, "history_done"):
            worker.history_done.connect(
                lambda n: self._status.showMessage(i18n.tr("history_loaded", n=n))
            )
        viewer.stop_requested.connect(lambda v=viewer: self._stop_viewer(v))
        viewer.pane_close_requested.connect(lambda v=viewer: self._close_pane(v))
        viewer.pane_activated.connect(lambda v=viewer: self._set_active_viewer(v))
        viewer.stop_btn.setEnabled(True)
        self._workers[id(viewer)] = worker

    def _discard(self, viewer: LogViewer, worker) -> None:
        """Throw away a viewer/worker pair that was never wired or started."""
        client = getattr(worker, "_client", None)
        if hasattr(client, "close"):
            try:
                client.close()
            except Exception:
                pass
        viewer.deleteLater()

    def _add_tab(self, title: str, viewer: LogViewer, worker, split: str = "tab"):
        if split in ("vertical", "horizontal"):
            spl = self._current_tab_splitter()
            if spl is not None and self._count_viewers_in(spl) >= self._MAX_PANES:
                self._status.showMessage(i18n.tr("err_max_panes", n=self._MAX_PANES))
                self._discard(viewer, worker)
                return
        self._wire_viewer(viewer, worker)

        if split == "vertical":
            self._add_viewer_to_current_tab(viewer, Qt.Orientation.Horizontal, title)
        elif split == "horizontal":
            self._add_viewer_to_current_tab(viewer, Qt.Orientation.Vertical, title)
        else:
            spl = self._make_tab_splitter()
            spl.addWidget(viewer)
            idx = self._top_tabs.addTab(spl, title)
            self._top_tabs.setCurrentIndex(idx)

        self._set_active_viewer(viewer)
        worker.start()

    def _action_close_all_logs(self):
        while self._top_tabs.count() > 0:
            self._close_tab_at(0)

    def _stop_viewer(self, viewer: LogViewer):
        worker = self._workers.pop(id(viewer), None)
        if worker and worker.isRunning():
            worker.stop()
            worker.wait(3000)
        if viewer:
            viewer.stop_btn.setEnabled(False)

    def _on_error(self, msg: str, viewer: LogViewer):
        self._stop_viewer(viewer)
        self._status.showMessage(i18n.tr("err_prefix", msg=msg))
        QMessageBox.critical(self, i18n.tr("err_worker"), msg)

    def closeEvent(self, event):  # noqa: N802
        for worker in list(self._workers.values()):
            if worker.isRunning():
                worker.stop()
                worker.wait(2000)
        event.accept()
