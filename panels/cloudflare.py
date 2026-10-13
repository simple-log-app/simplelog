"""Cloudflare connection panel."""

from __future__ import annotations

from PyQt6.QtCore import (
    QThread,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QFrame,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import cloudflare_utils
import i18n
import profiles_store
from ui_theme import C_BG, C_BORDER, C_ERR, C_INFO, C_MUTED, C_PANEL, C_SEL_BG, C_TEXT
from ui_widgets import OpenModeWidget, _ghost_btn, _primary_btn, _ProfileBar, make_card

# ── CloudflarePanel ───────────────────────────────────────────────────────────

class _CloudflareConnectWorker(QThread):
    success = pyqtSignal(list)   # list[str] — worker script names
    failure = pyqtSignal(str)

    def __init__(self, api_token: str, account_id: str) -> None:
        super().__init__()
        self._api_token  = api_token
        self._account_id = account_id

    def run(self) -> None:
        try:
            workers = cloudflare_utils.list_workers(self._api_token, self._account_id)
            self.success.emit(workers)
        except RuntimeError as e:
            self.failure.emit(str(e))


class CloudflarePanel(QWidget):
    open_tab = pyqtSignal(dict, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: list[str] = []
        self._connect_worker: _CloudflareConnectWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        root.addWidget(scroll)

        inner = QWidget()
        inner.setStyleSheet(f"background: {C_PANEL};")
        scroll.setWidget(inner)

        vlay = QVBoxLayout(inner)
        vlay.setContentsMargins(12, 12, 12, 12)
        vlay.setSpacing(10)

        field_style = (
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            "border-radius: 4px; padding: 6px 8px; font-size: 12px;"
        )
        lbl_style  = f"color: {C_MUTED}; font-size: 11px;"
        list_style = (
            f"QListWidget {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            " border-radius: 4px; font-size: 12px; }}"
            f"QListWidget::item:selected {{ background: {C_SEL_BG}; }}"
        )

        # ── Saved configs ─────────────────────────────────────────────
        saved_card, saved_lay, _ = make_card(i18n.tr("saved_configs"))
        self._cf_profile_bar = _ProfileBar("cloudflare", wrapper=saved_card)
        self._cf_profile_bar.profile_loaded.connect(self._load_cloudflare_profile)
        saved_lay.addWidget(self._cf_profile_bar)
        vlay.addWidget(saved_card)

        # ── Auth card ─────────────────────────────────────────────────
        card_auth, lay_auth, _ = make_card(i18n.tr("new_config"), help_key="help_cloudflare")

        lay_auth.addWidget(self._lbl(lbl_style, i18n.tr("cf_field_token")))
        self._cf_token_input = QLineEdit()
        self._cf_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._cf_token_input.setStyleSheet(field_style)
        self._cf_token_input.setPlaceholderText("API token with Workers:Read and Tail:Read")
        lay_auth.addWidget(self._cf_token_input)

        lay_auth.addWidget(self._lbl(lbl_style, i18n.tr("cf_field_account_id")))
        self._cf_account_input = QLineEdit()
        self._cf_account_input.setStyleSheet(field_style)
        self._cf_account_input.setPlaceholderText("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        lay_auth.addWidget(self._cf_account_input)

        self._save_profile_btn_cf = _ghost_btn("Save as profile…")
        self._save_profile_btn_cf.clicked.connect(self._on_save_cf_profile)
        self._save_profile_btn_cf.setEnabled(False)
        lay_auth.addWidget(self._save_profile_btn_cf)

        self._connect_btn_cf = _primary_btn(i18n.tr("cf_connect"))
        self._connect_btn_cf.clicked.connect(self._do_connect)
        lay_auth.addWidget(self._connect_btn_cf)

        self._conn_status_cf = QLabel("")
        self._conn_status_cf.setStyleSheet(lbl_style)
        self._conn_status_cf.setWordWrap(True)
        lay_auth.addWidget(self._conn_status_cf)

        vlay.addWidget(card_auth)

        # ── Workers card ──────────────────────────────────────────────
        card_wk, lay_wk, _ = make_card(i18n.tr("cf_card_workers"))

        self._cf_worker_list = QListWidget()
        self._cf_worker_list.setMaximumHeight(180)
        self._cf_worker_list.setStyleSheet(list_style)
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

    @staticmethod
    def _lbl(style: str, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(style)
        return lbl

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

    def _on_save_cf_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:", text="cloudflare")
        if not ok or not name.strip():
            return
        profiles_store.upsert("cloudflare", name.strip(), {
            "api_token":  self._cf_token_input.text().strip(),
            "account_id": self._cf_account_input.text().strip(),
        })
        self._cf_profile_bar.reload()

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
