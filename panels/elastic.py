"""Elastic connection panel."""

from __future__ import annotations

from PyQt6.QtCore import (
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import elastic_utils
import i18n
import profiles_store
from panels.base import FIELD_STYLE, LBL_STYLE, ProviderPanel
from ui_theme import C_BG, C_BORDER, C_ERR, C_INFO, C_MUTED, C_TEXT
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

# ── ElasticPanel ──────────────────────────────────────────────────────────────

class _ElasticConnectWorker(BackgroundWorker):
    success = pyqtSignal(list)   # index names

    def __init__(self, url: str, api_key: str, username: str, password: str) -> None:
        super().__init__()
        self._url      = url
        self._api_key  = api_key
        self._username = username
        self._password = password

    def _work(self) -> tuple:
        elastic_utils.verify_connection(self._url, self._api_key, self._username, self._password)
        indices = elastic_utils.list_indices(self._url, self._api_key, self._username, self._password)
        return (indices,)


class ElasticPanel(ProviderPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._connect_worker: _ElasticConnectWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        vlay = self._scaffold()


        # ── Saved configs card ────────────────────────────────────────
        saved_card_es, saved_lay_es, _ = make_card(i18n.tr("saved_configs"))
        self._elastic_profile_bar = _ProfileBar("elastic", wrapper=saved_card_es)
        self._elastic_profile_bar.profile_loaded.connect(self._load_elastic_profile)
        saved_lay_es.addWidget(self._elastic_profile_bar)
        vlay.addWidget(saved_card_es)

        # ── Card: Connection ─────────────────────────────────────────
        card_conn, lay_conn, _ = make_card(i18n.tr("new_config"), help_key="help_elastic")

        lay_conn.addWidget(self._lbl(LBL_STYLE, i18n.tr("elastic_field_url")))
        self._es_url_input = QLineEdit()
        self._es_url_input.setPlaceholderText("http://localhost:9200")
        self._es_url_input.setStyleSheet(FIELD_STYLE)
        lay_conn.addWidget(self._es_url_input)

        self._es_auth_combo = NoScrollComboBox()
        self._es_auth_combo.addItems([
            i18n.tr("elastic_auth_none"),
            i18n.tr("elastic_auth_apikey"),
            i18n.tr("elastic_auth_basic"),
        ])
        self._es_auth_combo.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )
        self._es_auth_combo.currentIndexChanged.connect(self._on_auth_mode_changed_es)
        lay_conn.addWidget(self._es_auth_combo)

        self._es_apikey_widget = QWidget()
        ak_lay = QVBoxLayout(self._es_apikey_widget)
        ak_lay.setContentsMargins(0, 4, 0, 0)
        ak_lay.setSpacing(0)
        self._es_apikey_input = QLineEdit()
        self._es_apikey_input.setPlaceholderText(i18n.tr("elastic_field_apikey"))
        self._es_apikey_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._es_apikey_input.setStyleSheet(FIELD_STYLE)
        ak_lay.addWidget(self._es_apikey_input)
        self._es_apikey_widget.setVisible(False)
        lay_conn.addWidget(self._es_apikey_widget)

        self._es_basic_widget = QWidget()
        bas_lay = QVBoxLayout(self._es_basic_widget)
        bas_lay.setContentsMargins(0, 4, 0, 0)
        bas_lay.setSpacing(4)
        self._es_user_input = QLineEdit()
        self._es_user_input.setPlaceholderText(i18n.tr("elastic_field_username"))
        self._es_user_input.setStyleSheet(FIELD_STYLE)
        bas_lay.addWidget(self._es_user_input)
        self._es_pass_input = QLineEdit()
        self._es_pass_input.setPlaceholderText(i18n.tr("elastic_field_password"))
        self._es_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._es_pass_input.setStyleSheet(FIELD_STYLE)
        bas_lay.addWidget(self._es_pass_input)
        self._es_basic_widget.setVisible(False)
        lay_conn.addWidget(self._es_basic_widget)

        self._save_profile_btn_es = _ghost_btn("Save as profile…")
        self._save_profile_btn_es.clicked.connect(self._on_save_elastic_profile)
        self._save_profile_btn_es.setEnabled(False)
        lay_conn.addWidget(self._save_profile_btn_es)

        self._connect_btn_es = _primary_btn(i18n.tr("elastic_connect"))
        self._connect_btn_es.clicked.connect(self._do_connect)
        lay_conn.addWidget(self._connect_btn_es)

        self._conn_status_es = QLabel("")
        self._conn_status_es.setStyleSheet(LBL_STYLE)
        self._conn_status_es.setWordWrap(True)
        lay_conn.addWidget(self._conn_status_es)

        vlay.addWidget(card_conn)

        # ── Card: Query ──────────────────────────────────────────────
        card_query, lay_query, _ = make_card(i18n.tr("elastic_card_query"))

        lay_query.addWidget(self._lbl(LBL_STYLE, i18n.tr("elastic_field_index")))
        idx_row = QHBoxLayout()
        self._es_index_input = QLineEdit()
        self._es_index_input.setPlaceholderText("logs-*")
        self._es_index_input.setStyleSheet(FIELD_STYLE)
        self._es_index_combo = NoScrollComboBox()
        self._es_index_combo.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )
        self._es_index_combo.setVisible(False)
        self._es_index_combo.currentTextChanged.connect(
            lambda t: self._es_index_input.setText(t)
        )
        idx_row.addWidget(self._es_index_input)
        idx_row.addWidget(self._es_index_combo)
        lay_query.addLayout(idx_row)

        lay_query.addWidget(self._lbl(LBL_STYLE, i18n.tr("elastic_field_ts")))
        self._es_ts_input = QLineEdit()
        self._es_ts_input.setPlaceholderText("@timestamp")
        self._es_ts_input.setText("@timestamp")
        self._es_ts_input.setStyleSheet(FIELD_STYLE)
        lay_query.addWidget(self._es_ts_input)

        lay_query.addWidget(self._lbl(LBL_STYLE, i18n.tr("elastic_field_query")))
        self._es_query_input = QLineEdit()
        self._es_query_input.setPlaceholderText(i18n.tr("elastic_query_hint"))
        self._es_query_input.setStyleSheet(FIELD_STYLE)
        lay_query.addWidget(self._es_query_input)

        lb_row = QHBoxLayout()
        lb_row.addWidget(self._lbl(LBL_STYLE, i18n.tr("field_time_range")))
        lb_row.addStretch()
        self._lookback_combo_es = _lookback_combo()
        lb_row.addWidget(self._lookback_combo_es)
        lay_query.addLayout(lb_row)

        iv_row = QHBoxLayout()
        iv_row.addWidget(self._lbl(LBL_STYLE, i18n.tr("elastic_field_interval")))
        iv_row.addStretch()
        self._interval_spin_es = QSpinBox()
        self._interval_spin_es.setRange(1, 60)
        self._interval_spin_es.setValue(10)
        self._interval_spin_es.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px; font-size: 12px; max-width: 60px;"
        )
        iv_row.addWidget(self._interval_spin_es)
        lay_query.addLayout(iv_row)

        self._open_mode_es = OpenModeWidget()
        lay_query.addWidget(self._open_mode_es)

        self._open_btn_es = _primary_btn(i18n.tr("elastic_open"))
        self._open_btn_es.clicked.connect(self._on_open)
        self._open_btn_es.setEnabled(False)
        lay_query.addWidget(self._open_btn_es)

        self._card_query_es = card_query
        card_query.setVisible(False)
        vlay.addWidget(card_query)
        vlay.addStretch()

    def _on_auth_mode_changed_es(self, idx: int) -> None:
        self._es_apikey_widget.setVisible(idx == 1)
        self._es_basic_widget.setVisible(idx == 2)

    def _do_connect(self) -> None:
        url = self._es_url_input.text().strip()
        if not url:
            return
        auth = self._es_auth_combo.currentIndex()
        api_key  = self._es_apikey_input.text().strip() if auth == 1 else ""
        username = self._es_user_input.text().strip()   if auth == 2 else ""
        password = self._es_pass_input.text()           if auth == 2 else ""
        self._connect_btn_es.setEnabled(False)
        self._conn_status_es.setText(i18n.tr("elastic_connecting"))
        self._conn_status_es.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        self._connect_worker = _ElasticConnectWorker(url, api_key, username, password)
        self._connect_worker.success.connect(self._on_connected_es)
        self._connect_worker.failure.connect(self._on_connect_fail_es)
        self._connect_worker.start()

    def _on_connected_es(self, indices: list) -> None:
        self._conn_status_es.setText(i18n.tr("elastic_connected"))
        self._conn_status_es.setStyleSheet(f"color: {C_INFO}; font-size: 11px;")
        self._connect_btn_es.setEnabled(True)
        self._save_profile_btn_es.setEnabled(True)
        self._card_query_es.setVisible(True)
        self._open_btn_es.setEnabled(True)
        if indices:
            self._es_index_combo.clear()
            self._es_index_combo.addItems(indices)
            self._es_index_combo.setVisible(True)
            self._es_index_input.setVisible(False)
        else:
            self._conn_status_es.setText(i18n.tr("elastic_no_indices"))

    def _on_connect_fail_es(self, msg: str) -> None:
        self._conn_status_es.setText(msg)
        self._conn_status_es.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
        self._connect_btn_es.setEnabled(True)

    def _load_elastic_profile(self, p: dict) -> None:
        self._es_url_input.setText(p.get("url", ""))
        auth = p.get("auth_mode", 0)
        self._es_auth_combo.setCurrentIndex(auth)
        self._es_apikey_input.setText(p.get("api_key", ""))
        self._es_user_input.setText(p.get("username", ""))
        self._es_pass_input.setText(p.get("password", ""))
        self._on_auth_mode_changed_es(auth)

    def _on_save_elastic_profile(self) -> None:
        url = self._es_url_input.text().strip()
        if not url:
            return
        default_name = url.split("//", 1)[-1].split("/")[0]
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:", text=default_name)
        if not ok or not name.strip():
            return
        auth = self._es_auth_combo.currentIndex()
        profiles_store.upsert("elastic", name.strip(), {
            "url":      url,
            "auth_mode": auth,
            "api_key":  self._es_apikey_input.text().strip() if auth == 1 else "",
            "username": self._es_user_input.text().strip()   if auth == 2 else "",
            "password": self._es_pass_input.text()           if auth == 2 else "",
        })
        self._elastic_profile_bar.reload()

    def _on_open(self) -> None:
        url   = self._es_url_input.text().strip()
        index = self._es_index_input.text().strip() or self._es_index_combo.currentText()
        if not url or not index:
            return
        auth = self._es_auth_combo.currentIndex()
        label = f"{url.split('//')[-1].split('/')[0]}/{index}"
        cfg = {
            "type":          "elastic",
            "url":           url,
            "index":         index,
            "query":         self._es_query_input.text().strip() or "*",
            "auth_mode":     auth,
            "api_key":       self._es_apikey_input.text().strip() if auth == 1 else "",
            "username":      self._es_user_input.text().strip()   if auth == 2 else "",
            "password":      self._es_pass_input.text()           if auth == 2 else "",
            "ts_field":      self._es_ts_input.text().strip() or "@timestamp",
            "lookback_s":    self._lookback_combo_es.currentData(),
            "interval_s":    self._interval_spin_es.value(),
            "label":         label,
        }
        self.open_tab.emit(cfg, self._open_mode_es.get_mode())

    # ── Embedding contract (see ProviderPanel) ────────────────────────────────

    restore_attrs = ("_es_index_input", "_es_ts_input", "_es_query_input",
                     "_lookback_combo_es", "_interval_spin_es", "_es_index_combo")

    def connect_now(self) -> None:
        self._do_connect()

    def is_connected(self) -> bool:
        return not self._card_query_es.isHidden()

    def load_profile(self, data: dict) -> None:
        self._load_elastic_profile(data)

    def can_open(self) -> bool:
        return self._open_btn_es.isEnabled()

    def open_selected(self) -> None:
        self._on_open()

    def profile_data(self) -> dict:
        mode = self._es_auth_combo.currentIndex()
        return {
            "url":       self._es_url_input.text().strip(),
            "auth_mode": mode,
            "api_key":   self._es_apikey_input.text().strip() if mode == 1 else "",
            "username":  self._es_user_input.text().strip() if mode == 2 else "",
            "password":  self._es_pass_input.text() if mode == 2 else "",
        }

    def _embedded_hidden(self) -> list:
        return [self._save_profile_btn_es, self._open_btn_es]
