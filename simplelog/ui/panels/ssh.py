"""Ssh connection panel."""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import (
    Qt,
    QThread,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from simplelog.core import i18n
from simplelog.core.config_store import CONFIG_DIR, read_json, write_json
from simplelog.sources import ssh_utils
from simplelog.ui.panels.base import ProviderPanel
from simplelog.ui.ui_theme import C_ERR, C_INFO, C_MUTED, C_SIDE, C_TEXT
from simplelog.ui.ui_widgets import (
    MessageBox,
    NoScrollComboBox,
    OpenModeWidget,
    _ghost_btn,
    _primary_btn,
    _ProfileBar,
    make_card,
    make_frameless,
)
from simplelog.ui.ui_workers import CallWorker

# ── SSH recent connections manager ────────────────────────────────────────────

class SSHRecentManager:
    _path = CONFIG_DIR / "ssh_recents.json"
    _MAX  = 10

    @classmethod
    def load(cls) -> list[dict]:
        entries = read_json(cls._path, [])
        return entries if isinstance(entries, list) else []

    @classmethod
    def push(cls, entry: dict) -> None:
        entries = cls.load()
        # deduplicate by host+port+user+path
        key = (entry.get("host"), entry.get("port"), entry.get("user"), entry.get("remote_path"))
        entries = [e for e in entries
                   if (e.get("host"), e.get("port"), e.get("user"), e.get("remote_path")) != key]
        entries.insert(0, entry)
        entries = entries[:cls._MAX]
        try:
            write_json(cls._path, entries)
        except OSError:
            pass


# ── SFTP file browser dialog ──────────────────────────────────────────────────

class _SftpBrowserDialog(QDialog):
    """Simple SFTP directory browser. Double-click dirs to navigate, files to select."""

    def __init__(self, client, start_path: str = "/", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("ssh_browse_title"))
        self.resize(480, 400)
        self._client   = client
        self._selected : str | None = None
        self._nav_gen = 0        # answers to older listings are ignored
        self.finished.connect(lambda _=0: setattr(self, "_nav_gen", -1))

        layout = QVBoxLayout(self)

        self._path_lbl = QLabel()
        self._path_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-size: 12px; font-weight: 600;"
            " background: transparent; padding: 4px 0;"
        )
        layout.addWidget(self._path_lbl)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        make_frameless(self, layout)

        self._navigate(start_path)

    def _navigate(self, path: str) -> None:
        self._path_lbl.setText(path)
        self._list.clear()
        if path != "/":
            up_item = QListWidgetItem("📁  ..")
            up_item.setData(Qt.ItemDataRole.UserRole, ("dir", str(Path(path).parent)))
            self._list.addItem(up_item)
        # Listing a directory over a slow link can take seconds: do it in the background
        self._nav_gen += 1
        gen = self._nav_gen
        self._list.setEnabled(False)
        worker = CallWorker(ssh_utils.list_remote_dir_full, self._client, path)
        worker.success.connect(lambda entries: self._on_listed(gen, path, entries))
        worker.failure.connect(lambda msg: self._on_list_failed(gen, msg))
        self._list_worker = worker
        worker.start()

    def _on_list_failed(self, gen: int, msg: str) -> None:
        if gen != self._nav_gen:
            return
        self._list.setEnabled(True)
        MessageBox.warning(self, i18n.tr("err_title"), msg)

    def _on_listed(self, gen: int, path: str, entries: list) -> None:
        if gen != self._nav_gen:
            return   # another directory was requested meanwhile, or the dialog closed
        self._list.setEnabled(True)
        for name, is_dir in entries:
            prefix = "📁  " if is_dir else "📄  "
            item = QListWidgetItem(prefix + name)
            full = path.rstrip("/") + "/" + name
            item.setData(Qt.ItemDataRole.UserRole, ("dir" if is_dir else "file", full))
            self._list.addItem(item)

    def _on_double_click(self, item: QListWidgetItem) -> None:
        kind, full_path = item.data(Qt.ItemDataRole.UserRole)
        if kind == "dir":
            self._navigate(full_path)
        else:
            self._selected = full_path
            self.accept()

    def _on_ok(self) -> None:
        cur = self._list.currentItem()
        if cur:
            kind, full_path = cur.data(Qt.ItemDataRole.UserRole)
            if kind == "file":
                self._selected = full_path
        self.accept()

    def selected_path(self) -> str | None:
        return self._selected


# ── SSH connection worker (runs connect in background) ────────────────────────

class _SSHConnectWorker(QThread):
    success = pyqtSignal(object)   # paramiko.SSHClient
    failure = pyqtSignal(str)
    unknown_host = pyqtSignal(str, str, str)   # host, key type, fingerprint

    def __init__(self, host, user, port, key_path, password, trust_new_host=False) -> None:
        super().__init__()
        self._trust_new_host = trust_new_host
        self._host     = host
        self._user     = user
        self._port     = port
        self._key_path = key_path
        self._password = password

    def run(self) -> None:
        try:
            client = ssh_utils.make_client(
                self._host, self._user, self._port,
                key_path=self._key_path or None,
                password=self._password or None,
                trust_new_host=self._trust_new_host,
            )
            self.success.emit(client)
        except ssh_utils.UnknownHostKeyError as e:
            self.unknown_host.emit(e.host, e.key_type, e.fingerprint)
        except Exception as e:
            self.failure.emit(str(e))


# ── SSHPanel ──────────────────────────────────────────────────────────────────

class SSHPanel(ProviderPanel):
    profile_type = "ssh"
    _profile_bar_attr = "_ssh_profile_bar"

    def default_profile_name(self) -> str:
        return f"{self._user_input.text()}@{self._host_input.text()}"
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._client = None
        self._connect_worker: _SSHConnectWorker | None = None
        self._build_ui()
        _key = id(self)
        i18n.register(_key, self.retranslate)
        self.destroyed.connect(lambda _=None, k=_key: i18n.unregister(k))

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setStyleSheet(f"background: {C_SIDE};")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        outer.addWidget(scroll)

        content = QWidget()
        content.setStyleSheet(f"background: {C_SIDE};")
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(12, 16, 12, 16)
        vbox.setSpacing(12)
        scroll.setWidget(content)

        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-size: 15px; font-weight: 700;"
            " background: transparent; border: none; margin-bottom: 4px;"
        )
        vbox.addWidget(self._title_lbl)

        # ── Saved configs card ────────────────────────────────────────────────
        saved_card_ssh, saved_lay_ssh, _ = make_card(i18n.tr("saved_configs"))
        self._ssh_profile_bar = _ProfileBar("ssh", wrapper=saved_card_ssh)
        self._ssh_profile_bar.profile_loaded.connect(self._load_ssh_profile)
        saved_lay_ssh.addWidget(self._ssh_profile_bar)
        vbox.addWidget(saved_card_ssh)

        # ── CONNECTION card ───────────────────────────────────────────────────
        card, cl, self._lbl_conn = make_card(i18n.tr("new_config"), help_key="help_ssh")
        vbox.addWidget(card)

        # Host
        self._lbl_host = QLabel()
        self._lbl_host.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        self._host_input = QLineEdit()
        self._host_input.setPlaceholderText(i18n.tr("ssh_host_placeholder"))

        # Port
        self._lbl_port = QLabel()
        self._lbl_port.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        port_row = QHBoxLayout()
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setValue(22)
        port_row.addWidget(self._port_spin)
        port_row.addStretch()

        # User
        self._lbl_user = QLabel()
        self._lbl_user.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        self._user_input = QLineEdit()
        self._user_input.setPlaceholderText("ubuntu")

        # Auth mode
        self._lbl_auth = QLabel()
        self._lbl_auth.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        self._auth_combo = NoScrollComboBox()

        # Key widgets
        self._lbl_keypath = QLabel()
        self._lbl_keypath.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("~/.ssh/id_rsa")
        self._key_browse_btn = _ghost_btn()
        self._key_browse_btn.setMaximumWidth(90)
        self._key_browse_btn.clicked.connect(self._on_browse_key)
        key_row.addWidget(self._key_input)
        key_row.addWidget(self._key_browse_btn)
        self._key_widget = QWidget()
        kw_layout = QVBoxLayout(self._key_widget)
        kw_layout.setContentsMargins(0, 0, 0, 0)
        kw_layout.setSpacing(4)
        kw_layout.addWidget(self._lbl_keypath)
        kw_layout.addLayout(key_row)

        # Password widgets
        self._lbl_password = QLabel()
        self._lbl_password.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_widget = QWidget()
        pw_layout = QVBoxLayout(self._pass_widget)
        pw_layout.setContentsMargins(0, 0, 0, 0)
        pw_layout.setSpacing(4)
        pw_layout.addWidget(self._lbl_password)
        pw_layout.addWidget(self._password_input)

        self._auth_combo.currentIndexChanged.connect(self._on_auth_mode_changed)

        # Status badge
        self._status_lbl = QLabel()
        self._status_lbl.setStyleSheet(
            "color: transparent; font-size: 11px; background: transparent; border: none;"
        )

        self._connect_btn = _primary_btn()
        self._connect_btn.clicked.connect(lambda: self._on_connect())

        self._save_profile_btn_ssh = _ghost_btn(i18n.tr("profile_save_btn"))
        self._save_profile_btn_ssh.clicked.connect(self._save_profile)

        cl.addWidget(self._lbl_host)
        cl.addWidget(self._host_input)
        cl.addWidget(self._lbl_port)
        cl.addLayout(port_row)
        cl.addWidget(self._lbl_user)
        cl.addWidget(self._user_input)
        cl.addWidget(self._lbl_auth)
        cl.addWidget(self._auth_combo)
        cl.addWidget(self._key_widget)
        cl.addWidget(self._pass_widget)
        cl.addWidget(self._save_profile_btn_ssh)
        cl.addWidget(self._status_lbl)
        cl.addWidget(self._connect_btn)

        # ── REMOTE FILE card ──────────────────────────────────────────────────
        card2, fl, self._lbl_file_card = make_card()
        vbox.addWidget(card2)
        self._file_card_frame = card2
        self._file_card_frame.setVisible(False)

        self._lbl_path = QLabel()
        self._lbl_path.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("/var/log/app.log")
        self._browse_remote_btn = _ghost_btn()
        self._browse_remote_btn.setMaximumWidth(90)
        self._browse_remote_btn.clicked.connect(self._on_sftp_browse)
        path_row.addWidget(self._path_input)
        path_row.addWidget(self._browse_remote_btn)

        self._lbl_tail = QLabel()
        self._lbl_tail.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        tail_row2 = QHBoxLayout()
        self._tail_spin = QSpinBox()
        self._tail_spin.setRange(1, 500_000)
        self._tail_spin.setValue(100)
        self._tail_spin.setSingleStep(100)
        tail_row2.addWidget(self._tail_spin)
        tail_row2.addStretch()

        self._open_mode_w = OpenModeWidget()
        self._open_btn = _primary_btn()
        self._open_btn.clicked.connect(self._on_open)

        fl.addWidget(self._lbl_path)
        fl.addLayout(path_row)
        fl.addWidget(self._lbl_tail)
        fl.addLayout(tail_row2)
        fl.addWidget(self._open_mode_w)
        fl.addWidget(self._open_btn)

        # ── RECENT CONNECTIONS card ────────────────────────────────────────────
        card3, rl, self._lbl_recent_card = make_card()
        self._recent_card = card3
        self._recent_list = QListWidget()
        self._recent_list.setMinimumHeight(80)
        self._recent_list.itemDoubleClicked.connect(self._on_recent_double_click)
        self._recent_empty_lbl = QLabel()
        self._recent_empty_lbl.setStyleSheet(
            "color: #4c4c4c; font-size: 12px; background: transparent; border: none;"
        )
        self._recent_empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rl.addWidget(self._recent_list)
        rl.addWidget(self._recent_empty_lbl)
        card3.setVisible(False)
        vbox.addWidget(card3)

        vbox.addStretch()
        self.retranslate()
        self._on_auth_mode_changed(0)
        self._refresh_recents()

    def retranslate(self) -> None:
        self._title_lbl.setText(i18n.tr("ssh_title"))
        if self._lbl_conn:
            self._lbl_conn.setText(i18n.tr("ssh_card_connection").upper())
        if self._lbl_file_card:
            self._lbl_file_card.setText(i18n.tr("ssh_card_file").upper())
        if self._lbl_recent_card:
            self._lbl_recent_card.setText(i18n.tr("ssh_card_recent").upper())
        self._lbl_host.setText(i18n.tr("ssh_field_host"))
        self._lbl_port.setText(i18n.tr("ssh_field_port"))
        self._lbl_user.setText(i18n.tr("ssh_field_user"))
        self._lbl_auth.setText(i18n.tr("ssh_auth_mode"))
        self._lbl_keypath.setText(i18n.tr("ssh_field_keypath"))
        self._lbl_password.setText(i18n.tr("ssh_field_password"))
        self._key_browse_btn.setText(i18n.tr("ssh_browse_key"))
        self._browse_remote_btn.setText(i18n.tr("ssh_browse_remote"))
        self._lbl_path.setText(i18n.tr("ssh_field_path"))
        self._lbl_tail.setText(i18n.tr("ssh_field_tail"))
        self._open_btn.setText(i18n.tr("ssh_open"))
        self._recent_empty_lbl.setText(i18n.tr("ssh_no_recent"))
        cur = self._auth_combo.currentIndex()
        self._auth_combo.blockSignals(True)
        self._auth_combo.clear()
        self._auth_combo.addItem(i18n.tr("ssh_auth_key"))
        self._auth_combo.addItem(i18n.tr("ssh_auth_password"))
        self._auth_combo.setCurrentIndex(cur)
        self._auth_combo.blockSignals(False)
        if not self._connect_btn.isEnabled():
            pass  # keep "connecting" text
        elif self._client is not None:
            self._connect_btn.setText(i18n.tr("ssh_connected"))
        else:
            self._connect_btn.setText(i18n.tr("ssh_connect"))

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_auth_mode_changed(self, idx: int) -> None:
        self._key_widget.setVisible(idx == 0)
        self._pass_widget.setVisible(idx == 1)

    def _on_browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, i18n.tr("ssh_key_dialog_title"), os.path.expanduser("~/.ssh"),
            i18n.tr("filter_all_files")
        )
        if path:
            self._key_input.setText(path)

    def _on_connect(self, trust_new_host: bool = False) -> None:
        host = self._host_input.text().strip()
        user = self._user_input.text().strip()
        if not host or not user:
            MessageBox.warning(self, "SSH", i18n.tr("err_ssh_required"))
            return
        self._client = None
        self._file_card_frame.setVisible(False)
        self._recent_card.setVisible(False)
        self._connect_btn.setEnabled(False)
        self._connect_btn.setText(i18n.tr("ssh_connecting"))
        self._status_lbl.setText("")

        auth_mode = self._auth_combo.currentIndex()
        key_path  = self._key_input.text().strip() if auth_mode == 0 else ""
        password  = self._password_input.text() if auth_mode == 1 else ""

        self._connect_worker = _SSHConnectWorker(
            host, user, self._port_spin.value(), key_path, password, trust_new_host
        )
        self._connect_worker.success.connect(self._on_connect_success)
        self._connect_worker.failure.connect(self._on_connect_failure)
        self._connect_worker.unknown_host.connect(self._on_unknown_host)
        self._connect_worker.start()

    def _on_unknown_host(self, host: str, key_type: str, fingerprint: str) -> None:
        answer = MessageBox.question(
            self,
            i18n.tr("ssh_trust_host_title"),
            i18n.tr("ssh_trust_host_text", host=host, key_type=key_type,
                    fingerprint=fingerprint),
        )
        if answer == MessageBox.StandardButton.Yes:
            self._on_connect(trust_new_host=True)
        else:
            self._on_connect_failure(i18n.tr("ssh_trust_host_title"))

    def _on_connect_success(self, client) -> None:
        self._client = client
        self._connect_btn.setEnabled(True)
        self._connect_btn.setText(i18n.tr("ssh_connected"))
        self._status_lbl.setStyleSheet(
            f"color: {C_INFO}; font-size: 11px; background: transparent; border: none;"
        )
        self._status_lbl.setText("●  " + i18n.tr("ssh_connected"))
        self._file_card_frame.setVisible(True)
        self._recent_card.setVisible(True)

    def _on_connect_failure(self, msg: str) -> None:
        self._connect_btn.setEnabled(True)
        self._connect_btn.setText(i18n.tr("ssh_connect"))
        self._status_lbl.setStyleSheet(
            f"color: {C_ERR}; font-size: 11px; background: transparent; border: none;"
        )
        self._status_lbl.setText("●  " + msg)

    def _load_ssh_profile(self, p: dict) -> None:
        self._host_input.setText(p.get("host", ""))
        self._port_spin.setValue(p.get("port", 22))
        self._user_input.setText(p.get("user", ""))
        self._auth_combo.setCurrentIndex(0 if p.get("auth_mode", "key") == "key" else 1)
        self._key_input.setText(p.get("key_path", ""))
        self._path_input.setText(p.get("remote_path", ""))

    def _on_sftp_browse(self) -> None:
        if self._client is None:
            return
        start = self._path_input.text().strip()
        # start from the directory if path already set
        start_dir = str(Path(start).parent) if start else "/"
        dlg = _SftpBrowserDialog(self._client, start_dir, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_path():
            self._path_input.setText(dlg.selected_path())

    def _on_open(self) -> None:
        if self._client is None:
            return
        path = self._path_input.text().strip()
        if not path:
            return
        host     = self._host_input.text().strip()
        user     = self._user_input.text().strip()
        port     = self._port_spin.value()
        auth_idx = self._auth_combo.currentIndex()
        key_path = self._key_input.text().strip() if auth_idx == 0 else ""
        cfg = {
            "type":        "ssh",
            "host":        host,
            "port":        port,
            "user":        user,
            "auth_mode":   "key" if auth_idx == 0 else "password",
            "key_path":    key_path,
            "remote_path": path,
            "tail_lines":  self._tail_spin.value(),
        }
        # Push to recents (never store password)
        recent_entry = {k: v for k, v in cfg.items() if k != "password"}
        SSHRecentManager.push(recent_entry)
        self._refresh_recents()
        # Open a fresh connection for the worker (the panel keeps its own client).
        # Connecting can take seconds: do it in the background.
        self._open_btn.setEnabled(False)
        mode = self._open_mode_w.get_mode()
        worker = CallWorker(
            ssh_utils.make_client, host, user, port,
            key_path=key_path or None,
            password=self._password_input.text() if auth_idx == 1 else None,
        )
        worker.success.connect(lambda client: self._on_open_connected(cfg, client, mode))
        worker.failure.connect(self._on_open_failed)
        self._open_worker = worker
        worker.start()

    def _on_open_connected(self, cfg: dict, client, mode: str) -> None:
        self._open_btn.setEnabled(True)
        cfg["_client"] = client
        self.open_tab.emit(cfg, mode)

    def _on_open_failed(self, msg: str) -> None:
        self._open_btn.setEnabled(True)
        MessageBox.critical(self, i18n.tr("err_connection"), msg)

    def _on_recent_double_click(self, item: QListWidgetItem) -> None:
        entry = item.data(Qt.ItemDataRole.UserRole)
        if not entry:
            return
        self._host_input.setText(entry.get("host", ""))
        self._port_spin.setValue(entry.get("port", 22))
        self._user_input.setText(entry.get("user", ""))
        auth_mode = entry.get("auth_mode", "key")
        self._auth_combo.setCurrentIndex(0 if auth_mode == "key" else 1)
        self._key_input.setText(entry.get("key_path", ""))
        self._path_input.setText(entry.get("remote_path", ""))
        self._tail_spin.setValue(entry.get("tail_lines", 100))
        if auth_mode == "password":
            self._password_input.clear()
            self._password_input.setFocus()

    def _refresh_recents(self) -> None:
        entries = SSHRecentManager.load()
        self._recent_list.clear()
        if entries:
            self._recent_empty_lbl.hide()
            self._recent_list.show()
            for e in entries:
                label = f"{e.get('user','')}@{e.get('host','')}:{e.get('port',22)}  —  {e.get('remote_path','')}"
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, e)
                self._recent_list.addItem(item)
        else:
            self._recent_list.hide()
            self._recent_empty_lbl.show()

    # ── Embedding contract (see ProviderPanel) ────────────────────────────────

    restore_attrs = ("_tail_spin",)

    def connect_now(self) -> None:
        if self._auth_combo.currentIndex() == 0:        # key auth needs no password
            self._on_connect()

    def is_connected(self) -> bool:
        return self._client is not None

    def load_profile(self, data: dict) -> None:
        self._load_ssh_profile(data)

    def can_open(self) -> bool:
        return self._file_card_frame.isVisible() and bool(self._path_input.text().strip())

    def open_selected(self) -> None:
        self._on_open()

    def profile_data(self) -> dict:
        key_auth = self._auth_combo.currentIndex() == 0
        return {
            "host": self._host_input.text().strip(),
            "port": self._port_spin.value(),
            "user": self._user_input.text().strip(),
            "auth_mode": "key" if key_auth else "password",
            "key_path": self._key_input.text().strip() if key_auth else "",
            "remote_path": self._path_input.text().strip(),
        }

    def _embedded_hidden(self) -> list:
        return [self._save_profile_btn_ssh, self._open_btn, self._title_lbl]

    def release(self) -> None:
        # The panel's own connection only served browsing: the tab opened from it
        # got a separate one.
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
