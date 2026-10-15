"""Cloudflare connection panel."""

from __future__ import annotations

from PyQt6.QtCore import (
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
)

from simplelog.core import i18n
from simplelog.sources import cloudflare_utils
from simplelog.ui.panels.base import FIELD_STYLE, LIST_STYLE, ProviderPanel
from simplelog.ui.ui_theme import C_ERR, C_INFO, C_MUTED
from simplelog.ui.ui_widgets import OpenModeWidget, _ghost_btn, _primary_btn, _ProfileBar, make_card
from simplelog.ui.ui_workers import BackgroundWorker

# ── CloudflarePanel ───────────────────────────────────────────────────────────

class _CloudflareConnectWorker(BackgroundWorker):
    success = pyqtSignal(list)   # list[str] — worker script names

    def __init__(self, api_token: str, account_id: str) -> None:
        super().__init__()
        self._api_token  = api_token
        self._account_id = account_id

    def _work(self) -> tuple:
        workers = cloudflare_utils.list_workers(self._api_token, self._account_id)
        return (workers,)


class CloudflarePanel(ProviderPanel):
    profile_type = "cloudflare"
    _profile_bar_attr = "_cf_profile_bar"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: list[str] = []
        self._connect_worker: _CloudflareConnectWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        vlay = self._scaffold()

        LBL_STYLE  = f"color: {C_MUTED}; font-size: 11px;"
        # ── Saved configs ─────────────────────────────────────────────
        saved_card, saved_lay, _ = make_card(i18n.tr("saved_configs"))
        self._cf_profile_bar = _ProfileBar("cloudflare", wrapper=saved_card)
        self._cf_profile_bar.profile_loaded.connect(self._load_cloudflare_profile)
        saved_lay.addWidget(self._cf_profile_bar)
        vlay.addWidget(saved_card)

        # ── Auth card ─────────────────────────────────────────────────
        card_auth, lay_auth, _ = make_card(i18n.tr("new_config"), help_key="help_cloudflare")

        lay_auth.addWidget(self._lbl(LBL_STYLE, i18n.tr("cf_field_token")))
        self._cf_token_input = QLineEdit()
        self._cf_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._cf_token_input.setStyleSheet(FIELD_STYLE)
        self._cf_token_input.setPlaceholderText(i18n.tr("cf_token_placeholder"))
        lay_auth.addWidget(self._cf_token_input)

        lay_auth.addWidget(self._lbl(LBL_STYLE, i18n.tr("cf_field_account_id")))
        self._cf_account_input = QLineEdit()
        self._cf_account_input.setStyleSheet(FIELD_STYLE)
        self._cf_account_input.setPlaceholderText("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        lay_auth.addWidget(self._cf_account_input)

        self._save_profile_btn_cf = _ghost_btn(i18n.tr("profile_save_btn"))
        self._save_profile_btn_cf.clicked.connect(self._save_profile)
        self._save_profile_btn_cf.setEnabled(False)
        lay_auth.addWidget(self._save_profile_btn_cf)

        self._connect_btn_cf = _primary_btn(i18n.tr("cf_connect"))
        self._connect_btn_cf.clicked.connect(self._do_connect)
        lay_auth.addWidget(self._connect_btn_cf)

        self._conn_status_cf = QLabel("")
        self._conn_status_cf.setStyleSheet(LBL_STYLE)
        self._conn_status_cf.setWordWrap(True)
        lay_auth.addWidget(self._conn_status_cf)

        vlay.addWidget(card_auth)

        # ── Workers card ──────────────────────────────────────────────
        card_wk, lay_wk, _ = make_card(i18n.tr("cf_card_workers"))

        self._cf_worker_list = QListWidget()
        self._cf_worker_list.setMaximumHeight(180)
        self._cf_worker_list.setStyleSheet(LIST_STYLE)
        self._cf_worker_list.itemSelectionChanged.connect(
            lambda: self._open_btn_cf.setEnabled(self._cf_worker_list.currentRow() >= 0)
        )
        lay_wk.addWidget(self._cf_worker_list)

        self._open_mode_cf = OpenModeWidget()
        lay_wk.addWidget(self._open_mode_cf)

        self._open_btn_cf = _primary_btn(i18n.tr("cf_open"))
        self._open_btn_cf.clicked.connect(self._on_open)
        self._open_btn_cf.setEnabled(False)
        lay_wk.addWidget(self._open_btn_cf)

        self._card_wk = card_wk
        card_wk.setVisible(False)
        vlay.addWidget(card_wk)
        vlay.addStretch()

    def _do_connect(self) -> None:
        token      = self._cf_token_input.text().strip()
        account_id = self._cf_account_input.text().strip()
        if not token or not account_id:
            self._conn_status_cf.setText(i18n.tr("cf_missing_fields"))
            self._conn_status_cf.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
            return
        self._connect_btn_cf.setEnabled(False)
        self._conn_status_cf.setText(i18n.tr("cf_connecting"))
        self._conn_status_cf.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        self._connect_worker = _CloudflareConnectWorker(token, account_id)
        self._connect_worker.success.connect(self._on_connected_cf)
        self._connect_worker.failure.connect(self._on_connect_fail_cf)
        self._connect_worker.start()

    def _on_connected_cf(self, workers: list) -> None:
        self._workers = workers
        self._conn_status_cf.setText(i18n.tr("cf_connected"))
        self._conn_status_cf.setStyleSheet(f"color: {C_INFO}; font-size: 11px;")
        self._connect_btn_cf.setEnabled(True)
        self._save_profile_btn_cf.setEnabled(True)
        self._cf_worker_list.clear()
        if workers:
            for name in workers:
                self._cf_worker_list.addItem(name)
            self._card_wk.setVisible(True)
        else:
            self._conn_status_cf.setText(i18n.tr("cf_no_workers"))

    def _on_connect_fail_cf(self, msg: str) -> None:
        self._conn_status_cf.setText(msg)
        self._conn_status_cf.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
        self._connect_btn_cf.setEnabled(True)

    def _load_cloudflare_profile(self, p: dict) -> None:
        self._cf_token_input.setText(p.get("api_token", ""))
        self._cf_account_input.setText(p.get("account_id", ""))

    def _on_open(self) -> None:
        token      = self._cf_token_input.text().strip()
        account_id = self._cf_account_input.text().strip()
        item       = self._cf_worker_list.currentItem()
        if not item:
            return
        script_name = item.text()
        cfg = {
            "type":        "cloudflare",
            "api_token":   token,
            "account_id":  account_id,
            "script_name": script_name,
            "label":       script_name,
        }
        self.open_tab.emit(cfg, self._open_mode_cf.get_mode())

    # ── Embedding contract (see ProviderPanel) ────────────────────────────────

    restore_attrs = ("_cf_worker_list",)

    def connect_now(self) -> None:
        self._do_connect()

    def is_connected(self) -> bool:
        return not self._card_wk.isHidden()

    def load_profile(self, data: dict) -> None:
        self._load_cloudflare_profile(data)

    def can_open(self) -> bool:
        return self._open_btn_cf.isEnabled()

    def open_selected(self) -> None:
        self._on_open()

    def profile_data(self) -> dict:
        return {
            "api_token":  self._cf_token_input.text().strip(),
            "account_id": self._cf_account_input.text().strip(),
        }

    def _embedded_hidden(self) -> list:
        return [self._save_profile_btn_cf, self._open_btn_cf]
