"""Gcp connection panel."""

from __future__ import annotations

from PyQt6.QtCore import (
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import gcp_utils
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

# ── GCPPanel ──────────────────────────────────────────────────────────────────

class _GCPConnectWorker(BackgroundWorker):
    success = pyqtSignal(object)  # gcp client

    def __init__(self, project_id: str, key_path: str | None) -> None:
        super().__init__()
        self._project_id = project_id
        self._key_path   = key_path or None

    def _work(self) -> tuple:
        client = gcp_utils.make_client(self._project_id, self._key_path)
        # cheap probe: fetch 0 entries to validate auth
        gcp_utils.fetch_entries(client,
            gcp_utils.build_filter(since=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            )),
            max_results=1,
        )
        return (client,)


class _GCPListProjectsWorker(BackgroundWorker):
    success = pyqtSignal(list)

    def __init__(self, key_path: str | None) -> None:
        super().__init__()
        self._key_path = key_path or None

    def _work(self) -> tuple:
        return (gcp_utils.list_projects(self._key_path),)


class GCPPanel(ProviderPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._client: object | None = None
        self._connect_worker:  _GCPConnectWorker | None = None
        self._projects_worker: _GCPListProjectsWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        vlay = self._scaffold()


        # ── Saved configs card ────────────────────────────────────────
        saved_card_gcp, saved_lay_gcp, _ = make_card(i18n.tr("saved_configs"))
        self._gcp_profile_bar = _ProfileBar("gcp", wrapper=saved_card_gcp)
        self._gcp_profile_bar.profile_loaded.connect(self._load_gcp_profile)
        saved_lay_gcp.addWidget(self._gcp_profile_bar)
        vlay.addWidget(saved_card_gcp)

        # ── Card: Auth ───────────────────────────────────────────────
        card_auth, lay_auth, _ = make_card(i18n.tr("new_config"), help_key="help_gcp")

        self._auth_combo = NoScrollComboBox()
        self._auth_combo.addItems([i18n.tr("gcp_auth_adc"), i18n.tr("gcp_auth_sa")])
        self._auth_combo.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )
        self._auth_combo.currentIndexChanged.connect(self._on_auth_mode_changed)
        lay_auth.addWidget(self._auth_combo)

        # Service account key row (shown only in SA mode)
        self._sa_widget = QWidget()
        sa_lay = QVBoxLayout(self._sa_widget)
        sa_lay.setContentsMargins(0, 4, 0, 0)
        sa_lay.setSpacing(4)
        key_row = QHBoxLayout()
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText(i18n.tr("gcp_field_keyfile"))
        self._key_input.setStyleSheet(FIELD_STYLE)
        self._key_browse = _ghost_btn(i18n.tr("gcp_browse_key"))
        self._key_browse.clicked.connect(self._browse_key)
        key_row.addWidget(self._key_input)
        key_row.addWidget(self._key_browse)
        sa_lay.addLayout(key_row)
        self._sa_widget.setVisible(False)
        lay_auth.addWidget(self._sa_widget)

        # Project ID row
        proj_row = QHBoxLayout()
        self._project_input = QLineEdit()
        self._project_input.setPlaceholderText(i18n.tr("gcp_field_project"))
        self._project_input.setStyleSheet(FIELD_STYLE)
        self._list_proj_btn = _ghost_btn(i18n.tr("gcp_list_projects"))
        self._list_proj_btn.clicked.connect(self._list_projects)
        proj_row.addWidget(self._project_input)
        proj_row.addWidget(self._list_proj_btn)
        lay_auth.addLayout(proj_row)

        self._proj_combo = NoScrollComboBox()
        self._proj_combo.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )
        self._proj_combo.setVisible(False)
        self._proj_combo.currentIndexChanged.connect(self._on_proj_combo_changed)
        lay_auth.addWidget(self._proj_combo)

        self._save_profile_btn_gcp = _ghost_btn("Save as profile…")
        self._save_profile_btn_gcp.clicked.connect(self._on_save_gcp_profile)
        self._save_profile_btn_gcp.setEnabled(False)
        lay_auth.addWidget(self._save_profile_btn_gcp)

        self._connect_btn_gcp = _primary_btn(i18n.tr("gcp_connect"))
        self._connect_btn_gcp.clicked.connect(self._do_connect)
        lay_auth.addWidget(self._connect_btn_gcp)

        self._auth_status = QLabel("")
        self._auth_status.setStyleSheet(LBL_STYLE)
        self._auth_status.setWordWrap(True)
        lay_auth.addWidget(self._auth_status)

        vlay.addWidget(card_auth)

        # ── Card: Filter ─────────────────────────────────────────────
        card_filt, lay_filt, _ = make_card(i18n.tr("gcp_card_filter"))

        lay_filt.addWidget(self._lbl(LBL_STYLE, i18n.tr("gcp_field_resource")))
        self._resource_combo = NoScrollComboBox()
        self._resource_combo.addItems(gcp_utils.RESOURCE_TYPES)
        self._resource_combo.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )
        lay_filt.addWidget(self._resource_combo)

        lay_filt.addWidget(self._lbl(LBL_STYLE, i18n.tr("gcp_field_severity")))
        self._severity_combo = NoScrollComboBox()
        self._severity_combo.addItems(gcp_utils.SEVERITIES)
        self._severity_combo.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )
        lay_filt.addWidget(self._severity_combo)

        lay_filt.addWidget(self._lbl(LBL_STYLE, i18n.tr("gcp_field_custom")))
        self._custom_input = QLineEdit()
        self._custom_input.setPlaceholderText(i18n.tr("gcp_custom_hint"))
        self._custom_input.setStyleSheet(FIELD_STYLE)
        lay_filt.addWidget(self._custom_input)

        lb_row = QHBoxLayout()
        lb_row.addWidget(self._lbl(LBL_STYLE, i18n.tr("field_time_range")))
        lb_row.addStretch()
        self._lookback_combo_gcp = _lookback_combo()
        lb_row.addWidget(self._lookback_combo_gcp)
        lay_filt.addLayout(lb_row)

        iv_row = QHBoxLayout()
        iv_row.addWidget(self._lbl(LBL_STYLE, i18n.tr("gcp_field_interval")))
        iv_row.addStretch()
        self._interval_spin_gcp = QSpinBox()
        self._interval_spin_gcp.setRange(1, 60)
        self._interval_spin_gcp.setValue(5)
        self._interval_spin_gcp.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px; font-size: 12px; max-width: 60px;"
        )
        iv_row.addWidget(self._interval_spin_gcp)
        lay_filt.addLayout(iv_row)

        self._open_mode_gcp = OpenModeWidget()
        lay_filt.addWidget(self._open_mode_gcp)

        self._open_btn_gcp = _primary_btn(i18n.tr("gcp_open"))
        self._open_btn_gcp.clicked.connect(self._on_open)
        self._open_btn_gcp.setEnabled(False)
        lay_filt.addWidget(self._open_btn_gcp)

        self._card_filt = card_filt
        card_filt.setVisible(False)
        vlay.addWidget(card_filt)
        vlay.addStretch()

    def _on_auth_mode_changed(self, idx: int) -> None:
        self._sa_widget.setVisible(idx == 1)

    def _browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Service Account Key", "", "JSON (*.json)")
        if path:
            self._key_input.setText(path)

    def _list_projects(self) -> None:
        self._list_proj_btn.setEnabled(False)
        key_path = self._key_input.text().strip() if self._auth_combo.currentIndex() == 1 else None
        self._projects_worker = _GCPListProjectsWorker(key_path)
        self._projects_worker.success.connect(self._on_projects_listed)
        self._projects_worker.failure.connect(lambda e: (
            self._auth_status.setText(e),
            self._list_proj_btn.setEnabled(True),
        ))
        self._projects_worker.start()

    def _on_projects_listed(self, projects: list) -> None:
        self._list_proj_btn.setEnabled(True)
        self._proj_combo.clear()
        if projects:
            for p in projects:
                self._proj_combo.addItem(f"{p['name']}  ({p['id']})", userData=p["id"])
            self._proj_combo.setVisible(True)
            self._project_input.setVisible(False)
        else:
            self._auth_status.setText(i18n.tr("gcp_no_projects"))

    def _on_proj_combo_changed(self, _idx: int) -> None:
        pid = self._proj_combo.currentData()
        if pid:
            self._project_input.setText(pid)

    def _do_connect(self) -> None:
        project_id = self._project_input.text().strip()
        if not project_id:
            self._auth_status.setText(i18n.tr("gcp_field_project"))
            return
        key_path = self._key_input.text().strip() if self._auth_combo.currentIndex() == 1 else None
        self._connect_btn_gcp.setEnabled(False)
        self._auth_status.setText(i18n.tr("gcp_connecting"))
        self._auth_status.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        self._connect_worker = _GCPConnectWorker(project_id, key_path)
        self._connect_worker.success.connect(self._on_connected)
        self._connect_worker.failure.connect(self._on_connect_fail_gcp)
        self._connect_worker.start()

    def _on_connected(self, client: object) -> None:
        self._client = client
        self._auth_status.setText(i18n.tr("gcp_connected"))
        self._auth_status.setStyleSheet(f"color: {C_INFO}; font-size: 11px;")
        self._connect_btn_gcp.setEnabled(True)
        self._open_btn_gcp.setEnabled(True)
        self._save_profile_btn_gcp.setEnabled(True)
        self._card_filt.setVisible(True)

    def _load_gcp_profile(self, p: dict) -> None:
        self._auth_combo.setCurrentIndex(p.get("auth_mode", 0))
        self._key_input.setText(p.get("key_path", ""))
        self._project_input.setText(p.get("project_id", ""))
        self._on_auth_mode_changed(self._auth_combo.currentIndex())

    def _on_save_gcp_profile(self) -> None:
        project_id = self._project_input.text().strip()
        if not project_id:
            return
        default_name = project_id
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:", text=default_name)
        if not ok or not name.strip():
            return
        profiles_store.upsert("gcp", name.strip(), {
            "auth_mode":  self._auth_combo.currentIndex(),
            "key_path":   self._key_input.text().strip() if self._auth_combo.currentIndex() == 1 else "",
            "project_id": project_id,
        })
        self._gcp_profile_bar.reload()

    def _on_connect_fail_gcp(self, msg: str) -> None:
        self._auth_status.setText(msg)
        self._auth_status.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
        self._connect_btn_gcp.setEnabled(True)

    def _on_open(self) -> None:
        if not self._client:
            return
        project_id = self._project_input.text().strip()
        cfg = {
            "type":          "gcp",
            "project_id":    project_id,
            "auth_mode":     self._auth_combo.currentIndex(),
            "key_path":      self._key_input.text().strip() if self._auth_combo.currentIndex() == 1 else "",
            "resource_type": self._resource_combo.currentText(),
            "severity":      self._severity_combo.currentText(),
            "custom_filter": self._custom_input.text().strip(),
            "lookback_s":    self._lookback_combo_gcp.currentData(),
            "interval_s":    self._interval_spin_gcp.value(),
            "_client":       self._client,
        }
        self.open_tab.emit(cfg, self._open_mode_gcp.get_mode())
