"""Vercel connection panel."""

from __future__ import annotations

from PyQt6.QtCore import (
    Qt,
    QThread,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import i18n
import profiles_store
import vercel_utils
from ui_theme import C_BG, C_BORDER, C_ERR, C_INFO, C_MUTED, C_PANEL, C_TEXT
from ui_widgets import (
    NoScrollComboBox,
    OpenModeWidget,
    _ghost_btn,
    _lookback_combo,
    _primary_btn,
    _ProfileBar,
    make_card,
)

# ── VercelPanel ───────────────────────────────────────────────────────────────

class _VercelConnectWorker(QThread):
    """Verifies a Vercel token in a background thread."""
    success = pyqtSignal(str)   # username
    failure = pyqtSignal(str)   # error message

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token

    def run(self) -> None:
        try:
            data = vercel_utils.verify_token(self._token)
            name = data.get("user", {}).get("name") or data.get("user", {}).get("email") or "OK"
            self.success.emit(name)
        except RuntimeError as e:
            self.failure.emit(str(e))


class _VercelFetchProjectsWorker(QThread):
    """Fetches project list in background."""
    success = pyqtSignal(list)
    failure = pyqtSignal(str)

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token

    def run(self) -> None:
        try:
            projects = vercel_utils.list_projects(self._token)
            self.success.emit(projects)
        except RuntimeError as e:
            self.failure.emit(str(e))


class _VercelFetchDeployWorker(QThread):
    """Fetches latest deployment for a project in background."""
    success = pyqtSignal(dict)   # deployment dict
    failure = pyqtSignal(str)

    def __init__(self, token: str, project_id: str, target: str) -> None:
        super().__init__()
        self._token      = token
        self._project_id = project_id
        self._target     = target

    def run(self) -> None:
        try:
            deploy = vercel_utils.get_latest_deployment(self._token, self._project_id, self._target)
            if deploy:
                self.success.emit(deploy)
            else:
                self.failure.emit(i18n.tr("vercel_no_deploy"))
        except RuntimeError as e:
            self.failure.emit(str(e))


class VercelPanel(QWidget):
    open_tab = pyqtSignal(dict, str)   # (cfg, split_mode)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._token      = vercel_utils.load_token()
        self._projects:  list[dict] = []
        self._deployment: dict | None = None
        self._connect_worker: _VercelConnectWorker | None = None
        self._projects_worker: _VercelFetchProjectsWorker | None = None
        self._deploy_worker:  _VercelFetchDeployWorker | None = None
        self._build_ui()
        if self._token:
            self._token_input.setText(self._token)
            self._do_connect()

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

        # ── Saved configs card ────────────────────────────────────────
        saved_card_v, saved_lay_v, _ = make_card(i18n.tr("saved_configs"))
        self._vercel_profile_bar = _ProfileBar("vercel", wrapper=saved_card_v)
        self._vercel_profile_bar.profile_loaded.connect(self._load_vercel_profile)
        saved_lay_v.addWidget(self._vercel_profile_bar)
        vlay.addWidget(saved_card_v)

        # ── Card: API Token ──────────────────────────────────────────
        card_tok, lay_tok, _ = make_card(i18n.tr("new_config"), help_key="help_vercel")

        self._token_input = QLineEdit()
        self._token_input.setPlaceholderText(i18n.tr("vercel_field_token"))
        self._token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_input.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 6px 8px; font-size: 12px;"
        )
        lay_tok.addWidget(self._token_input)

        self._save_profile_btn_vercel = _ghost_btn("Save as profile…")
        self._save_profile_btn_vercel.clicked.connect(self._on_save_vercel_profile)
        self._save_profile_btn_vercel.setEnabled(False)
        lay_tok.addWidget(self._save_profile_btn_vercel)

        self._connect_btn = _primary_btn(i18n.tr("vercel_connect"))
        self._connect_btn.clicked.connect(self._do_connect)
        lay_tok.addWidget(self._connect_btn)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        self._status_lbl.setWordWrap(True)
        lay_tok.addWidget(self._status_lbl)

        vlay.addWidget(card_tok)

        # ── Card: Project ────────────────────────────────────────────
        card_proj, lay_proj, _ = make_card(i18n.tr("vercel_card_project"))

        refresh_row = QHBoxLayout()
        refresh_row.addStretch()
        self._refresh_btn = _ghost_btn(i18n.tr("vercel_refresh"))
        self._refresh_btn.clicked.connect(self._fetch_projects)
        self._refresh_btn.setEnabled(False)
        refresh_row.addWidget(self._refresh_btn)
        lay_proj.addLayout(refresh_row)

        self._project_list = QListWidget()
        self._project_list.setFixedHeight(160)
        self._project_list.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; font-size: 12px;"
        )
        self._project_list.currentItemChanged.connect(self._on_project_changed)
        lay_proj.addWidget(self._project_list)

        self._card_proj = card_proj
        card_proj.setVisible(False)
        vlay.addWidget(card_proj)

        # ── Card: Deployment ─────────────────────────────────────────
        card_dep, lay_dep, _ = make_card(i18n.tr("vercel_card_deploy"))

        self._target_combo = NoScrollComboBox()
        self._target_combo.addItems([
            i18n.tr("vercel_target_prod"),
            i18n.tr("vercel_target_preview"),
            i18n.tr("vercel_target_any"),
        ])
        self._target_combo.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )
        self._target_combo.currentIndexChanged.connect(self._on_target_changed)
        lay_dep.addWidget(self._target_combo)

        self._deploy_lbl = QLabel("—")
        self._deploy_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        self._deploy_lbl.setWordWrap(True)
        lay_dep.addWidget(self._deploy_lbl)

        interval_row = QHBoxLayout()
        interval_lbl = QLabel(i18n.tr("vercel_field_interval"))
        interval_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 60)
        self._interval_spin.setValue(3)
        self._interval_spin.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px; font-size: 12px; max-width: 60px;"
        )
        interval_row.addWidget(interval_lbl)
        interval_row.addStretch()
        interval_row.addWidget(self._interval_spin)
        lay_dep.addLayout(interval_row)

        lb_row = QHBoxLayout()
        lb_lbl = QLabel(i18n.tr("field_time_range"))
        lb_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        lb_row.addWidget(lb_lbl)
        lb_row.addStretch()
        self._lookback_combo_vercel = _lookback_combo()
        lb_row.addWidget(self._lookback_combo_vercel)
        lay_dep.addLayout(lb_row)

        self._open_mode = OpenModeWidget()
        lay_dep.addWidget(self._open_mode)

        self._open_btn = _primary_btn(i18n.tr("vercel_open"))
        self._open_btn.clicked.connect(self._on_open)
        self._open_btn.setEnabled(False)
        lay_dep.addWidget(self._open_btn)

        self._card_dep = card_dep
        card_dep.setVisible(False)
        vlay.addWidget(card_dep)
        vlay.addStretch()

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _do_connect(self) -> None:
        token = self._token_input.text().strip()
        if not token:
            return
        self._token = token
        self._connect_btn.setEnabled(False)
        self._status_lbl.setText(i18n.tr("vercel_connecting"))
        self._status_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")

        self._connect_worker = _VercelConnectWorker(token)
        self._connect_worker.success.connect(self._on_connect_ok)
        self._connect_worker.failure.connect(self._on_connect_fail)
        self._connect_worker.start()

    def _on_connect_ok(self, username: str) -> None:
        self._status_lbl.setText(f"{i18n.tr('vercel_connected')} ({username})")
        self._status_lbl.setStyleSheet(f"color: {C_INFO}; font-size: 11px;")
        self._connect_btn.setEnabled(True)
        self._refresh_btn.setEnabled(True)
        self._save_profile_btn_vercel.setEnabled(True)
        self._card_proj.setVisible(True)
        self._fetch_projects()

    def _load_vercel_profile(self, p: dict) -> None:
        self._token_input.setText(p.get("token", ""))

    def _on_save_vercel_profile(self) -> None:
        token = self._token_input.text().strip()
        if not token:
            return
        default_name = f"vercel-{token[:8]}…"
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:", text=default_name)
        if not ok or not name.strip():
            return
        profiles_store.upsert("vercel", name.strip(), {"token": token})
        self._vercel_profile_bar.reload()

    def _on_connect_fail(self, msg: str) -> None:
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
        self._connect_btn.setEnabled(True)

    # ── Projects ──────────────────────────────────────────────────────────────

    def _fetch_projects(self) -> None:
        self._project_list.clear()
        self._project_list.addItem("…")
        self._refresh_btn.setEnabled(False)

        self._projects_worker = _VercelFetchProjectsWorker(self._token)
        self._projects_worker.success.connect(self._on_projects_loaded)
        self._projects_worker.failure.connect(self._on_projects_fail)
        self._projects_worker.start()

    def _on_projects_loaded(self, projects: list) -> None:
        self._projects = projects
        self._project_list.clear()
        self._refresh_btn.setEnabled(True)
        if not projects:
            self._project_list.addItem(i18n.tr("vercel_no_projects"))
            return
        for p in projects:
            fw = f"  [{p['framework']}]" if p.get("framework") else ""
            item = QListWidgetItem(f"{p['name']}{fw}")
            item.setData(Qt.ItemDataRole.UserRole, p)
            self._project_list.addItem(item)

    def _on_projects_fail(self, msg: str) -> None:
        self._project_list.clear()
        self._project_list.addItem(msg)
        self._refresh_btn.setEnabled(True)

    def _on_project_changed(self, current, _prev) -> None:
        if not current:
            return
        p = current.data(Qt.ItemDataRole.UserRole)
        if not p:
            return
        self._open_btn.setEnabled(False)
        self._deployment = None
        self._deploy_lbl.setText("…")
        self._card_dep.setVisible(True)
        self._fetch_deployment(p["id"])

    def _on_target_changed(self, _idx: int) -> None:
        items = self._project_list.selectedItems()
        if not items:
            return
        p = items[0].data(Qt.ItemDataRole.UserRole)
        if not p:
            return
        self._open_btn.setEnabled(False)
        self._deployment = None
        self._deploy_lbl.setText("…")
        self._fetch_deployment(p["id"])

    # ── Deployment ────────────────────────────────────────────────────────────

    def _target_key(self) -> str:
        idx = self._target_combo.currentIndex()
        return ["production", "preview", "any"][idx]

    def _fetch_deployment(self, project_id: str) -> None:
        self._deploy_worker = _VercelFetchDeployWorker(self._token, project_id, self._target_key())
        self._deploy_worker.success.connect(self._on_deploy_loaded)
        self._deploy_worker.failure.connect(self._on_deploy_fail)
        self._deploy_worker.start()

    def _on_deploy_loaded(self, deploy: dict) -> None:
        self._deployment = deploy
        url  = deploy.get("url", "")
        state = deploy.get("state", "")
        self._deploy_lbl.setText(f"{url}  [{state}]")
        self._open_btn.setEnabled(True)

    def _on_deploy_fail(self, msg: str) -> None:
        self._deploy_lbl.setText(msg)
        self._deploy_lbl.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
        self._open_btn.setEnabled(False)

    # ── Open tab ──────────────────────────────────────────────────────────────

    def _on_open(self) -> None:
        items = self._project_list.selectedItems()
        if not items or not self._deployment:
            return
        p = items[0].data(Qt.ItemDataRole.UserRole)
        if not p:
            return
        cfg = {
            "type":          "vercel",
            "token":         self._token,
            "project_id":    p["id"],
            "project_name":  p["name"],
            "deployment_id": self._deployment["id"],
            "interval_s":    self._interval_spin.value(),
            "lookback_s":    self._lookback_combo_vercel.currentData(),
        }
        self.open_tab.emit(cfg, self._open_mode.get_mode())
