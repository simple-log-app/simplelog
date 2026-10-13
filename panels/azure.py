"""Azure connection panel."""

from __future__ import annotations

from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import azure_utils
import i18n
import profiles_store
from panels.base import FIELD_STYLE, LBL_STYLE, ProviderPanel
from ui_theme import C_ACCENT, C_BG, C_BORDER, C_ERR, C_INFO, C_MUTED, C_PANEL, C_TEXT
from ui_widgets import (
    OpenModeWidget,
    _ghost_btn,
    _lookback_combo,
    _primary_btn,
    _ProfileBar,
    make_card,
)
from ui_workers import BackgroundWorker

# ── AzurePanel ─────────────────────────────────────────────────────────────────

class _AzureConnectWorker(BackgroundWorker):
    success = pyqtSignal(object, object)  # credential, logs_client

    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 workspace_id: str) -> None:
        super().__init__()
        self._tenant    = tenant_id
        self._client_id = client_id
        self._secret    = client_secret
        self._workspace = workspace_id

    def _work(self) -> tuple:
        cred   = azure_utils.make_credential(self._tenant, self._client_id, self._secret)
        client = azure_utils.make_logs_client(cred)
        azure_utils.verify_credential(cred, self._workspace)
        return (cred, client)


class AzurePanel(ProviderPanel):
    _ALL_TABLES: list[tuple[str, str]] = [
        (cat, tbl)
        for cat, tbls in azure_utils.TABLES.items()
        for tbl in tbls
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._credential = None
        self._logs_client = None
        self._workspace_id = ""
        self._connect_worker: _AzureConnectWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        vlay = self._scaffold()


        # ── Saved configs card ────────────────────────────────────────
        saved_card_az, saved_lay_az, _ = make_card(i18n.tr("saved_configs"))
        self._az_profile_bar = _ProfileBar("azure", wrapper=saved_card_az)
        self._az_profile_bar.profile_loaded.connect(self._load_az_profile)
        saved_lay_az.addWidget(self._az_profile_bar)
        vlay.addWidget(saved_card_az)

        # ── Card: Auth ───────────────────────────────────────────────
        card_auth, lay_auth, _ = make_card(i18n.tr("new_config"), help_key="help_azure")

        for attr, key, pw in [
            ("_tenant_input",    "azure_field_tenant",    False),
            ("_client_id_input", "azure_field_client",    False),
            ("_secret_input",    "azure_field_secret",    True),
            ("_workspace_input", "azure_field_workspace", False),
        ]:
            fld = QLineEdit()
            fld.setPlaceholderText(i18n.tr(key))
            fld.setStyleSheet(FIELD_STYLE)
            if pw:
                fld.setEchoMode(QLineEdit.EchoMode.Password)
            setattr(self, attr, fld)
            lay_auth.addWidget(fld)

        self._save_profile_btn_az = _ghost_btn("Save as profile…")
        self._save_profile_btn_az.clicked.connect(self._on_save_az_profile)
        self._save_profile_btn_az.setEnabled(False)
        lay_auth.addWidget(self._save_profile_btn_az)

        self._connect_btn_az = _primary_btn(i18n.tr("azure_connect"))
        self._connect_btn_az.clicked.connect(self._do_connect)
        lay_auth.addWidget(self._connect_btn_az)

        self._auth_status_az = QLabel("")
        self._auth_status_az.setStyleSheet(LBL_STYLE)
        self._auth_status_az.setWordWrap(True)
        lay_auth.addWidget(self._auth_status_az)

        vlay.addWidget(card_auth)

        # ── Tabs: Tables / KQL ───────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: none; background: {C_PANEL}; }}"
            f"QTabBar::tab {{ background: {C_PANEL}; color: {C_MUTED};"
            f" padding: 6px 12px; border: none; font-size: 11px; }}"
            f"QTabBar::tab:selected {{ color: {C_TEXT}; border-bottom: 2px solid {C_ACCENT}; }}"
        )
        self._tabs.setVisible(False)
        vlay.addWidget(self._tabs)

        # ── Tab 0: Tables ────────────────────────────────────────────
        tab_tables = QWidget()
        tt_lay = QVBoxLayout(tab_tables)
        tt_lay.setContentsMargins(0, 8, 0, 0)
        tt_lay.setSpacing(8)

        card_tbl, lay_tbl, _ = make_card(i18n.tr("azure_card_table"))

        self._table_search = QLineEdit()
        self._table_search.setPlaceholderText(i18n.tr("azure_search_table"))
        self._table_search.setStyleSheet(FIELD_STYLE)
        self._table_search.textChanged.connect(self._filter_tables)
        lay_tbl.addWidget(self._table_search)

        self._table_list = QListWidget()
        self._table_list.setFixedHeight(220)
        self._table_list.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; font-size: 12px;"
        )
        self._populate_table_list("")
        self._table_list.currentItemChanged.connect(self._on_table_selected)
        lay_tbl.addWidget(self._table_list)

        ts_row = QHBoxLayout()
        ts_row.addWidget(self._lbl(LBL_STYLE, i18n.tr("field_time_range")))
        ts_row.addStretch()
        self._timespan_combo = _lookback_combo()
        ts_row.addWidget(self._timespan_combo)
        lay_tbl.addLayout(ts_row)

        iv_row_t = QHBoxLayout()
        iv_row_t.addWidget(self._lbl(LBL_STYLE, i18n.tr("azure_field_interval")))
        iv_row_t.addStretch()
        self._interval_spin_az_t = QSpinBox()
        self._interval_spin_az_t.setRange(5, 300)
        self._interval_spin_az_t.setValue(10)
        self._interval_spin_az_t.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px; font-size: 12px; max-width: 60px;"
        )
        iv_row_t.addWidget(self._interval_spin_az_t)
        lay_tbl.addLayout(iv_row_t)

        self._open_mode_az_t = OpenModeWidget()
        lay_tbl.addWidget(self._open_mode_az_t)

        self._open_btn_az_t = _primary_btn(i18n.tr("azure_open_table"))
        self._open_btn_az_t.clicked.connect(self._on_open_table)
        self._open_btn_az_t.setEnabled(False)
        lay_tbl.addWidget(self._open_btn_az_t)

        tt_lay.addWidget(card_tbl)
        self._tabs.addTab(tab_tables, i18n.tr("azure_tab_tables"))

        # ── Tab 1: KQL ───────────────────────────────────────────────
        tab_kql = QWidget()
        kql_lay = QVBoxLayout(tab_kql)
        kql_lay.setContentsMargins(0, 8, 0, 0)
        kql_lay.setSpacing(8)

        card_kql, lay_kql, _ = make_card(i18n.tr("azure_card_kql"))

        self._kql_edit = QTextEdit()
        self._kql_edit.setPlaceholderText(
            "AppTraces\n| where TimeGenerated > ago(1h)\n| order by TimeGenerated asc"
        )
        self._kql_edit.setFixedHeight(160)
        self._kql_edit.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 6px 8px; font-size: 12px; font-family: monospace;"
        )
        lay_kql.addWidget(self._kql_edit)

        hint_kql = QLabel(i18n.tr("azure_kql_hint"))
        hint_kql.setStyleSheet(f"color: {C_MUTED}; font-size: 10px;")
        hint_kql.setWordWrap(True)
        lay_kql.addWidget(hint_kql)

        ts_row_k = QHBoxLayout()
        ts_row_k.addWidget(self._lbl(LBL_STYLE, i18n.tr("field_time_range")))
        ts_row_k.addStretch()
        self._timespan_combo_kql = _lookback_combo()
        ts_row_k.addWidget(self._timespan_combo_kql)
        lay_kql.addLayout(ts_row_k)

        iv_row_k = QHBoxLayout()
        iv_row_k.addWidget(self._lbl(LBL_STYLE, i18n.tr("azure_field_interval")))
        iv_row_k.addStretch()
        self._interval_spin_az_k = QSpinBox()
        self._interval_spin_az_k.setRange(5, 300)
        self._interval_spin_az_k.setValue(10)
        self._interval_spin_az_k.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px; font-size: 12px; max-width: 60px;"
        )
        iv_row_k.addWidget(self._interval_spin_az_k)
        lay_kql.addLayout(iv_row_k)

        self._open_mode_az_k = OpenModeWidget()
        lay_kql.addWidget(self._open_mode_az_k)

        self._open_btn_az_k = _primary_btn(i18n.tr("azure_open_kql"))
        self._open_btn_az_k.clicked.connect(self._on_open_kql)
        self._open_btn_az_k.setEnabled(False)
        lay_kql.addWidget(self._open_btn_az_k)

        kql_lay.addWidget(card_kql)
        self._tabs.addTab(tab_kql, i18n.tr("azure_tab_kql"))

        vlay.addStretch()

    def _populate_table_list(self, search: str) -> None:
        self._table_list.clear()
        search = search.lower()
        current_cat = None
        for cat, tbl in self._ALL_TABLES:
            if search and search not in tbl.lower() and search not in cat.lower():
                continue
            if cat != current_cat:
                hdr = QListWidgetItem(f"── {cat} ──")
                hdr.setFlags(Qt.ItemFlag.NoItemFlags)
                hdr.setForeground(QColor(C_MUTED))
                self._table_list.addItem(hdr)
                current_cat = cat
            item = QListWidgetItem(f"   {tbl}")
            item.setData(Qt.ItemDataRole.UserRole, tbl)
            self._table_list.addItem(item)

    def _filter_tables(self, text: str) -> None:
        self._populate_table_list(text)

    def _on_table_selected(self, current, _prev) -> None:
        if current and current.data(Qt.ItemDataRole.UserRole):
            self._open_btn_az_t.setEnabled(self._logs_client is not None)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _do_connect(self) -> None:
        tenant = self._tenant_input.text().strip()
        cid    = self._client_id_input.text().strip()
        secret = self._secret_input.text().strip()
        ws     = self._workspace_input.text().strip()
        if not all([tenant, cid, secret, ws]):
            self._auth_status_az.setText("All fields are required.")
            self._auth_status_az.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
            return
        self._workspace_id = ws
        self._connect_btn_az.setEnabled(False)
        self._auth_status_az.setText(i18n.tr("azure_connecting"))
        self._auth_status_az.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")

        self._connect_worker = _AzureConnectWorker(tenant, cid, secret, ws)
        self._connect_worker.success.connect(self._on_az_connected)
        self._connect_worker.failure.connect(self._on_az_connect_fail)
        self._connect_worker.start()

    def _on_az_connected(self, cred: object, client: object) -> None:
        self._credential  = cred
        self._logs_client = client
        self._auth_status_az.setText(i18n.tr("azure_connected"))
        self._auth_status_az.setStyleSheet(f"color: {C_INFO}; font-size: 11px;")
        self._connect_btn_az.setEnabled(True)
        self._tabs.setVisible(True)
        self._open_btn_az_k.setEnabled(True)
        self._save_profile_btn_az.setEnabled(True)

    def _load_az_profile(self, p: dict) -> None:
        self._tenant_input.setText(p.get("tenant_id", ""))
        self._client_id_input.setText(p.get("client_id", ""))
        self._secret_input.setText(p.get("client_secret", ""))
        self._workspace_input.setText(p.get("workspace_id", ""))

    def _on_save_az_profile(self) -> None:
        workspace_id = self._workspace_input.text().strip()
        tenant_id    = self._tenant_input.text().strip()
        if not workspace_id or not tenant_id:
            return
        default_name = f"{tenant_id[:8]}…"
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:", text=default_name)
        if not ok or not name.strip():
            return
        profiles_store.upsert("azure", name.strip(), {
            "tenant_id":     tenant_id,
            "client_id":     self._client_id_input.text().strip(),
            "client_secret": self._secret_input.text().strip(),
            "workspace_id":  workspace_id,
        })
        self._az_profile_bar.reload()

    def _on_az_connect_fail(self, msg: str) -> None:
        self._auth_status_az.setText(msg)
        self._auth_status_az.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
        self._connect_btn_az.setEnabled(True)

    # ── Open ──────────────────────────────────────────────────────────────────

    def _on_open_table(self) -> None:
        items = self._table_list.selectedItems()
        if not items:
            return
        tbl = items[0].data(Qt.ItemDataRole.UserRole)
        if not tbl:
            return
        query = azure_utils.build_table_query(tbl)
        cfg = {
            "type":          "azure",
            "workspace_id":  self._workspace_id,
            "query":         query,
            "label":         tbl,
            "lookback_s":    self._timespan_combo.currentData(),
            "interval_s":    self._interval_spin_az_t.value(),
            "_logs_client":  self._logs_client,
        }
        self.open_tab.emit(cfg, self._open_mode_az_t.get_mode())

    def _on_open_kql(self) -> None:
        query = self._kql_edit.toPlainText().strip()
        if not query:
            return
        cfg = {
            "type":          "azure",
            "workspace_id":  self._workspace_id,
            "query":         query,
            "label":         "KQL",
            "lookback_s":    self._timespan_combo_kql.currentData(),
            "interval_s":    self._interval_spin_az_k.value(),
            "_logs_client":  self._logs_client,
        }
        self.open_tab.emit(cfg, self._open_mode_az_k.get_mode())
