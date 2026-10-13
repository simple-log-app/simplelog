"""Railway connection panel."""

from __future__ import annotations

from PyQt6.QtCore import (
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QSpinBox,
)

import i18n
import railway_utils
from panels.base import FIELD_STYLE, LBL_STYLE, LIST_STYLE, ProviderPanel
from ui_theme import C_BG, C_BORDER, C_ERR, C_INFO, C_MUTED, C_TEXT
from ui_widgets import (
    OpenModeWidget,
    _ghost_btn,
    _lookback_combo,
    _primary_btn,
    _ProfileBar,
    make_card,
)
from ui_workers import BackgroundWorker

# ── RailwayPanel ──────────────────────────────────────────────────────────────

class _RailwayConnectWorker(BackgroundWorker):
    success = pyqtSignal(list)   # list of project dicts

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token

    def _work(self) -> tuple:
        projects = railway_utils.list_projects(self._token)
        return (projects,)


class RailwayPanel(ProviderPanel):
    profile_type = "railway"
    _profile_bar_attr = "_railway_profile_bar"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._projects: list[dict] = []
        self._connect_worker: _RailwayConnectWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        vlay = self._scaffold()

        # ── Saved configs card ────────────────────────────────────────
        saved_card_rw, saved_lay_rw, _ = make_card(i18n.tr("saved_configs"))
        self._railway_profile_bar = _ProfileBar("railway", wrapper=saved_card_rw)
        self._railway_profile_bar.profile_loaded.connect(self._load_railway_profile)
        saved_lay_rw.addWidget(self._railway_profile_bar)
        vlay.addWidget(saved_card_rw)

        # ── Card: Auth ───────────────────────────────────────────────
        card_auth, lay_auth, _ = make_card(i18n.tr("new_config"), help_key="help_railway")

        lay_auth.addWidget(self._lbl(LBL_STYLE, i18n.tr("railway_field_token")))
        self._railway_token_input = QLineEdit()
        self._railway_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._railway_token_input.setStyleSheet(FIELD_STYLE)
        lay_auth.addWidget(self._railway_token_input)

        self._save_profile_btn_railway = _ghost_btn(i18n.tr("profile_save_btn"))
        self._save_profile_btn_railway.clicked.connect(self._save_profile)
        self._save_profile_btn_railway.setEnabled(False)
        lay_auth.addWidget(self._save_profile_btn_railway)

        self._connect_btn_railway = _primary_btn(i18n.tr("railway_connect"))
        self._connect_btn_railway.clicked.connect(self._do_connect)
        lay_auth.addWidget(self._connect_btn_railway)

        self._conn_status_railway = QLabel("")
        self._conn_status_railway.setStyleSheet(LBL_STYLE)
        self._conn_status_railway.setWordWrap(True)
        lay_auth.addWidget(self._conn_status_railway)

        vlay.addWidget(card_auth)

        # ── Card: Project ────────────────────────────────────────────
        card_proj, lay_proj, _ = make_card(i18n.tr("railway_card_project"))

        self._project_list = QListWidget()
        self._project_list.setMaximumHeight(140)
        self._project_list.setStyleSheet(LIST_STYLE)
        self._project_list.currentRowChanged.connect(self._on_project_selected)
        lay_proj.addWidget(self._project_list)

        self._card_proj = card_proj
        card_proj.setVisible(False)
        vlay.addWidget(card_proj)

        # ── Card: Service ────────────────────────────────────────────
        card_svc, lay_svc, _ = make_card(i18n.tr("railway_card_service"))

        self._service_list = QListWidget()
        self._service_list.setMaximumHeight(120)
        self._service_list.setStyleSheet(LIST_STYLE)
        self._service_list.itemSelectionChanged.connect(
            lambda: self._open_btn_railway.setEnabled(self._service_list.currentRow() >= 0)
        )
        lay_svc.addWidget(self._service_list)

        iv_row = QHBoxLayout()
        iv_row.addWidget(self._lbl(LBL_STYLE, i18n.tr("railway_field_interval")))
        iv_row.addStretch()
        self._interval_spin_railway = QSpinBox()
        self._interval_spin_railway.setRange(1, 60)
        self._interval_spin_railway.setValue(10)
        self._interval_spin_railway.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px; font-size: 12px; max-width: 60px;"
        )
        iv_row.addWidget(self._interval_spin_railway)
        lay_svc.addLayout(iv_row)

        lb_row = QHBoxLayout()
        lb_row.addWidget(self._lbl(LBL_STYLE, i18n.tr("field_time_range")))
        lb_row.addStretch()
        self._lookback_combo_railway = _lookback_combo()
        lb_row.addWidget(self._lookback_combo_railway)
        lay_svc.addLayout(lb_row)

        self._open_mode_railway = OpenModeWidget()
        lay_svc.addWidget(self._open_mode_railway)

        self._open_btn_railway = _primary_btn(i18n.tr("railway_open"))
        self._open_btn_railway.clicked.connect(self._on_open)
        self._open_btn_railway.setEnabled(False)
        lay_svc.addWidget(self._open_btn_railway)

        self._card_svc = card_svc
        card_svc.setVisible(False)
        vlay.addWidget(card_svc)
        vlay.addStretch()

    def _do_connect(self) -> None:
        token = self._railway_token_input.text().strip()
        if not token:
            return
        self._connect_btn_railway.setEnabled(False)
        self._conn_status_railway.setText(i18n.tr("railway_connecting"))
        self._conn_status_railway.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        self._connect_worker = _RailwayConnectWorker(token)
        self._connect_worker.success.connect(self._on_connected_railway)
        self._connect_worker.failure.connect(self._on_connect_fail_railway)
        self._connect_worker.start()

    def _on_connected_railway(self, projects: list) -> None:
        self._projects = projects
        self._conn_status_railway.setText(i18n.tr("railway_connected"))
        self._conn_status_railway.setStyleSheet(f"color: {C_INFO}; font-size: 11px;")
        self._connect_btn_railway.setEnabled(True)
        self._save_profile_btn_railway.setEnabled(True)
        self._project_list.clear()
        if projects:
            for p in projects:
                self._project_list.addItem(p["name"])
            self._card_proj.setVisible(True)
        else:
            self._conn_status_railway.setText(i18n.tr("railway_no_projects"))

    def _on_connect_fail_railway(self, msg: str) -> None:
        self._conn_status_railway.setText(msg)
        self._conn_status_railway.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
        self._connect_btn_railway.setEnabled(True)

    def _on_project_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._projects):
            return
        project = self._projects[row]
        services = project.get("services", [])
        self._service_list.clear()
        if services:
            for svc in services:
                self._service_list.addItem(svc["name"])
            self._card_svc.setVisible(True)
        else:
            self._card_svc.setVisible(False)
            self._conn_status_railway.setText(i18n.tr("railway_no_services"))

    def _load_railway_profile(self, p: dict) -> None:
        self._railway_token_input.setText(p.get("token", ""))

    def _on_open(self) -> None:
        token = self._railway_token_input.text().strip()
        proj_row = self._project_list.currentRow()
        svc_row  = self._service_list.currentRow()
        if proj_row < 0 or svc_row < 0:
            return
        project = self._projects[proj_row]
        service = project["services"][svc_row]
        cfg = {
            "type":         "railway",
            "token":        token,
            "project_name": project["name"],
            "service_name": service["name"],
            "service_id":   service["id"],
            "interval_s":   self._interval_spin_railway.value(),
            "lookback_s":   self._lookback_combo_railway.currentData(),
            "label":        f"{project['name']}/{service['name']}",
        }
        self.open_tab.emit(cfg, self._open_mode_railway.get_mode())

    # ── Embedding contract (see ProviderPanel) ────────────────────────────────

    restore_attrs = ("_interval_spin_railway", "_lookback_combo_railway",
                     "_project_list", "_service_list")

    def connect_now(self) -> None:
        self._do_connect()

    def is_connected(self) -> bool:
        return not self._card_proj.isHidden()

    def load_profile(self, data: dict) -> None:
        self._load_railway_profile(data)

    def can_open(self) -> bool:
        return self._open_btn_railway.isEnabled()

    def open_selected(self) -> None:
        self._on_open()

    def profile_data(self) -> dict:
        return {"token": self._railway_token_input.text().strip()}

    def _embedded_hidden(self) -> list:
        return [self._save_profile_btn_railway, self._open_btn_railway]
