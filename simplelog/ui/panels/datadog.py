"""Datadog connection panel."""

from __future__ import annotations

from PyQt6.QtCore import (
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
)

from simplelog.core import i18n
from simplelog.sources import datadog_utils
from simplelog.ui.panels.base import FIELD_STYLE, LBL_STYLE, ProviderPanel
from simplelog.ui.ui_theme import C_BG, C_BORDER, C_ERR, C_INFO, C_MUTED, C_TEXT
from simplelog.ui.ui_widgets import (
    NoScrollComboBox,
    OpenModeWidget,
    _ghost_btn,
    _lookback_combo,
    _primary_btn,
    _ProfileBar,
    make_card,
)
from simplelog.ui.ui_workers import BackgroundWorker

# ── DatadogPanel ──────────────────────────────────────────────────────────────

class _DatadogConnectWorker(BackgroundWorker):
    success = pyqtSignal()

    def __init__(self, base_url: str, api_key: str, app_key: str) -> None:
        super().__init__()
        self._base_url = base_url
        self._api_key  = api_key
        self._app_key  = app_key

    def _work(self) -> tuple:
        datadog_utils.verify_connection(self._base_url, self._api_key, self._app_key)
        return ()


class DatadogPanel(ProviderPanel):
    profile_type = "datadog"
    _profile_bar_attr = "_dd_profile_bar"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        self._connect_worker: _DatadogConnectWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        vlay = self._scaffold()


        # ── Saved configs card ────────────────────────────────────────
        saved_card_dd, saved_lay_dd, _ = make_card(i18n.tr("saved_configs"))
        self._dd_profile_bar = _ProfileBar("datadog", wrapper=saved_card_dd)
        self._dd_profile_bar.profile_loaded.connect(self._load_datadog_profile)
        saved_lay_dd.addWidget(self._dd_profile_bar)
        vlay.addWidget(saved_card_dd)

        # ── Card: Auth ───────────────────────────────────────────────
        card_auth, lay_auth, _ = make_card(i18n.tr("new_config"), help_key="help_datadog")

        lay_auth.addWidget(self._lbl(LBL_STYLE, i18n.tr("datadog_field_site")))
        self._site_combo = NoScrollComboBox()
        self._site_combo.addItems(list(datadog_utils.DD_SITES.keys()))
        self._site_combo.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )
        lay_auth.addWidget(self._site_combo)

        lay_auth.addWidget(self._lbl(LBL_STYLE, i18n.tr("datadog_field_api_key")))
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setStyleSheet(FIELD_STYLE)
        lay_auth.addWidget(self._api_key_input)

        lay_auth.addWidget(self._lbl(LBL_STYLE, i18n.tr("datadog_field_app_key")))
        self._app_key_input = QLineEdit()
        self._app_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._app_key_input.setStyleSheet(FIELD_STYLE)
        lay_auth.addWidget(self._app_key_input)

        self._save_profile_btn_dd = _ghost_btn(i18n.tr("profile_save_btn"))
        self._save_profile_btn_dd.clicked.connect(self._save_profile)
        self._save_profile_btn_dd.setEnabled(False)
        lay_auth.addWidget(self._save_profile_btn_dd)

        self._connect_btn_dd = _primary_btn(i18n.tr("datadog_connect"))
        self._connect_btn_dd.clicked.connect(self._do_connect)
        lay_auth.addWidget(self._connect_btn_dd)

        self._auth_status_dd = QLabel("")
        self._auth_status_dd.setStyleSheet(LBL_STYLE)
        self._auth_status_dd.setWordWrap(True)
        lay_auth.addWidget(self._auth_status_dd)

        vlay.addWidget(card_auth)

        # ── Card: Query ──────────────────────────────────────────────
        card_query, lay_query, _ = make_card(i18n.tr("datadog_card_query"))

        lay_query.addWidget(self._lbl(LBL_STYLE, i18n.tr("datadog_field_query")))
        self._dd_query_input = QLineEdit()
        self._dd_query_input.setPlaceholderText(i18n.tr("datadog_query_hint"))
        self._dd_query_input.setStyleSheet(FIELD_STYLE)
        self._dd_query_input.textChanged.connect(self._update_open_btn)
        lay_query.addWidget(self._dd_query_input)

        lb_row = QHBoxLayout()
        lb_row.addWidget(self._lbl(LBL_STYLE, i18n.tr("field_time_range")))
        lb_row.addStretch()
        self._lookback_combo_dd = _lookback_combo()
        lb_row.addWidget(self._lookback_combo_dd)
        lay_query.addLayout(lb_row)

        iv_row = QHBoxLayout()
        iv_row.addWidget(self._lbl(LBL_STYLE, i18n.tr("datadog_field_interval")))
        iv_row.addStretch()
        self._interval_spin_dd = QSpinBox()
        self._interval_spin_dd.setRange(1, 60)
        self._interval_spin_dd.setValue(10)
        self._interval_spin_dd.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px; font-size: 12px; max-width: 60px;"
        )
        iv_row.addWidget(self._interval_spin_dd)
        lay_query.addLayout(iv_row)

        self._open_mode_dd = OpenModeWidget()
        lay_query.addWidget(self._open_mode_dd)

        self._open_btn_dd = _primary_btn(i18n.tr("datadog_open"))
        self._open_btn_dd.clicked.connect(self._on_open)
        self._open_btn_dd.setEnabled(False)
        lay_query.addWidget(self._open_btn_dd)

        self._card_query_dd = card_query
        card_query.setVisible(False)
        vlay.addWidget(card_query)
        vlay.addStretch()

    def _update_open_btn(self) -> None:
        self._open_btn_dd.setEnabled(
            bool(self._dd_query_input.text().strip()) and self._connected
        )

    def _do_connect(self) -> None:
        site_name = self._site_combo.currentText()
        base_url  = datadog_utils.DD_SITES.get(site_name, "https://api.datadoghq.com")
        api_key   = self._api_key_input.text().strip()
        app_key   = self._app_key_input.text().strip()
        if not api_key or not app_key:
            self._auth_status_dd.setText(i18n.tr("err_dd_keys_required"))
            self._auth_status_dd.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
            return
        self._connect_btn_dd.setEnabled(False)
        self._auth_status_dd.setText(i18n.tr("datadog_connecting"))
        self._auth_status_dd.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        self._connect_worker = _DatadogConnectWorker(base_url, api_key, app_key)
        self._connect_worker.success.connect(self._on_connected)
        self._connect_worker.failure.connect(self._on_connect_fail_dd)
        self._connect_worker.start()

    def _on_connected(self) -> None:
        self._connected = True
        self._auth_status_dd.setText(i18n.tr("datadog_connected"))
        self._auth_status_dd.setStyleSheet(f"color: {C_INFO}; font-size: 11px;")
        self._connect_btn_dd.setEnabled(True)
        self._save_profile_btn_dd.setEnabled(True)
        self._card_query_dd.setVisible(True)
        self._update_open_btn()

    def _on_connect_fail_dd(self, msg: str) -> None:
        self._auth_status_dd.setText(msg)
        self._auth_status_dd.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
        self._connect_btn_dd.setEnabled(True)

    def _load_datadog_profile(self, p: dict) -> None:
        site_name = p.get("site", "US1 (datadoghq.com)")
        idx = self._site_combo.findText(site_name)
        if idx >= 0:
            self._site_combo.setCurrentIndex(idx)
        self._api_key_input.setText(p.get("api_key", ""))
        self._app_key_input.setText(p.get("app_key", ""))

    def _on_open(self) -> None:
        site_name = self._site_combo.currentText()
        base_url  = datadog_utils.DD_SITES.get(site_name, "https://api.datadoghq.com")
        query = self._dd_query_input.text().strip() or "*"
        cfg = {
            "type":          "datadog",
            "base_url":      base_url,
            "query":         query,
            "api_key":       self._api_key_input.text().strip(),
            "app_key":       self._app_key_input.text().strip(),
            "lookback_s":    self._lookback_combo_dd.currentData(),
            "interval_s":    self._interval_spin_dd.value(),
            "label":         site_name.split(" ")[0],
        }
        self.open_tab.emit(cfg, self._open_mode_dd.get_mode())

    # ── Embedding contract (see ProviderPanel) ────────────────────────────────

    restore_attrs = ("_dd_query_input", "_lookback_combo_dd", "_interval_spin_dd")

    def connect_now(self) -> None:
        self._do_connect()

    def is_connected(self) -> bool:
        return self._connected

    def load_profile(self, data: dict) -> None:
        self._load_datadog_profile(data)

    def can_open(self) -> bool:
        return self._open_btn_dd.isEnabled()

    def open_selected(self) -> None:
        self._on_open()

    def profile_data(self) -> dict:
        return {
            "site":    self._site_combo.currentText(),
            "api_key": self._api_key_input.text().strip(),
            "app_key": self._app_key_input.text().strip(),
        }

    def _embedded_hidden(self) -> list:
        return [self._save_profile_btn_dd, self._open_btn_dd]
