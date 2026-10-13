"""Loki connection panel."""

from __future__ import annotations

from PyQt6.QtCore import (
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import i18n
import loki_utils
from panels.base import FIELD_STYLE, LBL_STYLE, ProviderPanel
from ui_theme import C_BG, C_BORDER, C_CARD, C_ERR, C_INFO, C_MUTED, C_SEL_BG, C_TEXT
from ui_widgets import (
    NoScrollComboBox,
    OpenModeWidget,
    _ghost_btn,
    _lookback_combo,
    _primary_btn,
    _ProfileBar,
    make_card,
)
from ui_workers import BackgroundWorker

# ── LokiPanel ─────────────────────────────────────────────────────────────────

class _LokiConnectWorker(BackgroundWorker):
    success = pyqtSignal(list)   # label names

    def __init__(self, url: str, username: str, password: str, token: str) -> None:
        super().__init__()
        self._url      = url
        self._username = username
        self._password = password
        self._token    = token

    def _work(self) -> tuple:
        labels = loki_utils.verify_connection(
            self._url, self._username, self._password, self._token
        )
        return (labels,)


class LokiPanel(ProviderPanel):
    profile_type = "loki"
    _profile_bar_attr = "_loki_profile_bar"
    profile_required = ('url',)

    def default_profile_name(self) -> str:
        return self._url_input.text().split("//", 1)[-1].split("/")[0]
    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels: list[str] = []
        self._connect_worker: _LokiConnectWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        vlay = self._scaffold()


        # ── Saved configs card ────────────────────────────────────────
        saved_card_loki, saved_lay_loki, _ = make_card(i18n.tr("saved_configs"))
        self._loki_profile_bar = _ProfileBar("loki", wrapper=saved_card_loki)
        self._loki_profile_bar.profile_loaded.connect(self._load_loki_profile)
        saved_lay_loki.addWidget(self._loki_profile_bar)
        vlay.addWidget(saved_card_loki)

        # ── Card: Connection ─────────────────────────────────────────
        card_conn, lay_conn, _ = make_card(i18n.tr("new_config"), help_key="help_loki")

        lay_conn.addWidget(self._lbl(LBL_STYLE, i18n.tr("loki_field_url")))
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("http://localhost:3100")
        self._url_input.setStyleSheet(FIELD_STYLE)
        lay_conn.addWidget(self._url_input)

        self._auth_combo = NoScrollComboBox()
        self._auth_combo.addItems([
            i18n.tr("loki_auth_none"),
            i18n.tr("loki_auth_basic"),
            i18n.tr("loki_auth_token"),
        ])
        self._auth_combo.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )
        self._auth_combo.currentIndexChanged.connect(self._on_auth_mode_changed)
        lay_conn.addWidget(self._auth_combo)

        # Basic auth fields
        self._basic_widget = QWidget()
        basic_lay = QVBoxLayout(self._basic_widget)
        basic_lay.setContentsMargins(0, 4, 0, 0)
        basic_lay.setSpacing(4)
        self._user_input = QLineEdit()
        self._user_input.setPlaceholderText(i18n.tr("loki_field_username"))
        self._user_input.setStyleSheet(FIELD_STYLE)
        basic_lay.addWidget(self._user_input)
        self._pass_input = QLineEdit()
        self._pass_input.setPlaceholderText(i18n.tr("loki_field_password"))
        self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_input.setStyleSheet(FIELD_STYLE)
        basic_lay.addWidget(self._pass_input)
        self._basic_widget.setVisible(False)
        lay_conn.addWidget(self._basic_widget)

        # Token field
        self._token_widget = QWidget()
        token_lay = QVBoxLayout(self._token_widget)
        token_lay.setContentsMargins(0, 4, 0, 0)
        token_lay.setSpacing(0)
        self._token_input = QLineEdit()
        self._token_input.setPlaceholderText(i18n.tr("loki_field_token"))
        self._token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_input.setStyleSheet(FIELD_STYLE)
        token_lay.addWidget(self._token_input)
        self._token_widget.setVisible(False)
        lay_conn.addWidget(self._token_widget)

        self._save_profile_btn_loki = _ghost_btn(i18n.tr("profile_save_btn"))
        self._save_profile_btn_loki.clicked.connect(self._save_profile)
        self._save_profile_btn_loki.setEnabled(False)
        lay_conn.addWidget(self._save_profile_btn_loki)

        self._connect_btn_loki = _primary_btn(i18n.tr("loki_connect"))
        self._connect_btn_loki.clicked.connect(self._do_connect)
        lay_conn.addWidget(self._connect_btn_loki)

        self._conn_status = QLabel("")
        self._conn_status.setStyleSheet(LBL_STYLE)
        self._conn_status.setWordWrap(True)
        lay_conn.addWidget(self._conn_status)

        vlay.addWidget(card_conn)

        # ── Card: Query ──────────────────────────────────────────────
        card_query, lay_query, _ = make_card(i18n.tr("loki_card_query"))

        lay_query.addWidget(self._lbl(LBL_STYLE, i18n.tr("loki_field_query")))
        query_row = QHBoxLayout()
        self._query_input = QLineEdit()
        self._query_input.setPlaceholderText(i18n.tr("loki_query_hint"))
        self._query_input.setStyleSheet(FIELD_STYLE)
        self._labels_btn = _ghost_btn(i18n.tr("loki_list_labels"))
        self._labels_btn.clicked.connect(self._show_labels_menu)
        query_row.addWidget(self._query_input)
        query_row.addWidget(self._labels_btn)
        lay_query.addLayout(query_row)

        lb_row = QHBoxLayout()
        lb_row.addWidget(self._lbl(LBL_STYLE, i18n.tr("field_time_range")))
        lb_row.addStretch()
        self._lookback_combo_loki = _lookback_combo()
        lb_row.addWidget(self._lookback_combo_loki)
        lay_query.addLayout(lb_row)

        iv_row = QHBoxLayout()
        iv_row.addWidget(self._lbl(LBL_STYLE, i18n.tr("loki_field_interval")))
        iv_row.addStretch()
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 60)
        self._interval_spin.setValue(5)
        self._interval_spin.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px; font-size: 12px; max-width: 60px;"
        )
        iv_row.addWidget(self._interval_spin)
        lay_query.addLayout(iv_row)

        self._open_mode_loki = OpenModeWidget()
        lay_query.addWidget(self._open_mode_loki)

        self._open_btn_loki = _primary_btn(i18n.tr("loki_open"))
        self._open_btn_loki.clicked.connect(self._on_open)
        self._open_btn_loki.setEnabled(False)
        lay_query.addWidget(self._open_btn_loki)

        self._card_query = card_query
        card_query.setVisible(False)
        vlay.addWidget(card_query)
        vlay.addStretch()

    def _on_auth_mode_changed(self, idx: int) -> None:
        self._basic_widget.setVisible(idx == 1)
        self._token_widget.setVisible(idx == 2)

    def _do_connect(self) -> None:
        url = self._url_input.text().strip()
        if not url:
            self._conn_status.setText(i18n.tr("loki_field_url"))
            return
        auth = self._auth_combo.currentIndex()
        username = self._user_input.text().strip() if auth == 1 else ""
        password = self._pass_input.text() if auth == 1 else ""
        token = self._token_input.text().strip() if auth == 2 else ""
        self._connect_btn_loki.setEnabled(False)
        self._conn_status.setText(i18n.tr("loki_connecting"))
        self._conn_status.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        self._connect_worker = _LokiConnectWorker(url, username, password, token)
        self._connect_worker.success.connect(self._on_connected)
        self._connect_worker.failure.connect(self._on_connect_fail)
        self._connect_worker.start()

    def _on_connected(self, labels: list) -> None:
        self._labels = labels
        self._conn_status.setText(i18n.tr("loki_connected"))
        self._conn_status.setStyleSheet(f"color: {C_INFO}; font-size: 11px;")
        self._connect_btn_loki.setEnabled(True)
        self._open_btn_loki.setEnabled(True)
        self._save_profile_btn_loki.setEnabled(True)
        self._card_query.setVisible(True)

    def _on_connect_fail(self, msg: str) -> None:
        self._conn_status.setText(msg)
        self._conn_status.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
        self._connect_btn_loki.setEnabled(True)

    def _show_labels_menu(self) -> None:
        if not self._labels:
            self._conn_status.setText(i18n.tr("loki_no_labels"))
            return
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {C_CARD}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f" border-radius: 6px; padding: 4px; }}"
            f"QMenu::item {{ padding: 4px 16px; border-radius: 4px; }}"
            f"QMenu::item:selected {{ background: {C_SEL_BG}; }}"
        )
        for label in sorted(self._labels):
            act = menu.addAction(label)
            act.triggered.connect(lambda checked, lbl=label: self._insert_label(lbl))
        menu.exec(self._labels_btn.mapToGlobal(self._labels_btn.rect().bottomLeft()))

    def _insert_label(self, label: str) -> None:
        current = self._query_input.text().strip()
        if not current:
            self._query_input.setText(f'{{{label}="..."}}')
        else:
            self._query_input.setText(current + f', {label}=""')

    def _load_loki_profile(self, p: dict) -> None:
        self._url_input.setText(p.get("url", ""))
        auth_mode = p.get("auth_mode", 0)
        self._auth_combo.setCurrentIndex(auth_mode)
        self._user_input.setText(p.get("username", ""))
        self._pass_input.setText(p.get("password", ""))
        self._token_input.setText(p.get("token", ""))
        self._on_auth_mode_changed(auth_mode)

    def _on_open(self) -> None:
        url = self._url_input.text().strip()
        query = self._query_input.text().strip()
        if not url or not query:
            return
        auth_mode = self._auth_combo.currentIndex()
        label = url.split("//", 1)[-1].split("/")[0]
        cfg = {
            "type":          "loki",
            "url":           url,
            "query":         query,
            "auth_mode":     auth_mode,
            "username":      self._user_input.text().strip() if auth_mode == 1 else "",
            "password":      self._pass_input.text() if auth_mode == 1 else "",
            "token":         self._token_input.text().strip() if auth_mode == 2 else "",
            "lookback_s":    self._lookback_combo_loki.currentData(),
            "interval_s":    self._interval_spin.value(),
            "label":         label,
        }
        self.open_tab.emit(cfg, self._open_mode_loki.get_mode())

    # ── Embedding contract (see ProviderPanel) ────────────────────────────────

    restore_attrs = ("_query_input", "_lookback_combo_loki", "_interval_spin")

    def connect_now(self) -> None:
        self._do_connect()

    def is_connected(self) -> bool:
        return not self._card_query.isHidden()

    def load_profile(self, data: dict) -> None:
        self._load_loki_profile(data)

    def can_open(self) -> bool:
        return self._open_btn_loki.isEnabled()

    def open_selected(self) -> None:
        self._on_open()

    def profile_data(self) -> dict:
        mode = self._auth_combo.currentIndex()
        return {
            "url":       self._url_input.text().strip(),
            "auth_mode": mode,
            "username":  self._user_input.text().strip() if mode == 1 else "",
            "password":  self._pass_input.text() if mode == 1 else "",
            "token":     self._token_input.text().strip() if mode == 2 else "",
        }

    def _embedded_hidden(self) -> list:
        return [self._save_profile_btn_loki, self._open_btn_loki]
