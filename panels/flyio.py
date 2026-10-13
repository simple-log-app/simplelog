"""Flyio connection panel."""

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

import flyio_utils
import i18n
import profiles_store
from ui_theme import C_BG, C_BORDER, C_ERR, C_INFO, C_MUTED, C_PANEL, C_SEL_BG, C_TEXT
from ui_widgets import (
    OpenModeWidget,
    _ghost_btn,
    _lookback_combo,
    _primary_btn,
    _ProfileBar,
    make_card,
)

# ── FlyioPanel ────────────────────────────────────────────────────────────────

class _FlyioConnectWorker(QThread):
    success = pyqtSignal(list)   # app dicts
    failure = pyqtSignal(str)

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token

    def run(self) -> None:
        try:
            apps = flyio_utils.list_apps(self._token)
            self.success.emit(apps)
        except RuntimeError as e:
            self.failure.emit(str(e))


class FlyioPanel(QWidget):
    open_tab = pyqtSignal(dict, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._apps: list[dict] = []
        self._connect_worker: _FlyioConnectWorker | None = None
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
            f"border-radius: 4px; padding: 6px 8px; font-size: 12px;"
        )
        lbl_style = f"color: {C_MUTED}; font-size: 11px;"
        list_style = (
            f"QListWidget {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f" border-radius: 4px; font-size: 12px; }}"
            f"QListWidget::item:selected {{ background: {C_SEL_BG}; }}"
        )

        # ── Saved configs card ────────────────────────────────────────
        saved_card_fly, saved_lay_fly, _ = make_card(i18n.tr("saved_configs"))
        self._flyio_profile_bar = _ProfileBar("flyio", wrapper=saved_card_fly)
        self._flyio_profile_bar.profile_loaded.connect(self._load_flyio_profile)
        saved_lay_fly.addWidget(self._flyio_profile_bar)
        vlay.addWidget(saved_card_fly)

        # ── Card: Auth ───────────────────────────────────────────────
        card_auth, lay_auth, _ = make_card(i18n.tr("new_config"), help_key="help_flyio")

        lay_auth.addWidget(self._lbl(lbl_style, i18n.tr("flyio_field_token")))
        self._flyio_token_input = QLineEdit()
        self._flyio_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._flyio_token_input.setStyleSheet(field_style)
        lay_auth.addWidget(self._flyio_token_input)

        self._save_profile_btn_flyio = _ghost_btn("Save as profile…")
        self._save_profile_btn_flyio.clicked.connect(self._on_save_flyio_profile)
        self._save_profile_btn_flyio.setEnabled(False)
        lay_auth.addWidget(self._save_profile_btn_flyio)

        self._connect_btn_flyio = _primary_btn(i18n.tr("flyio_connect"))
        self._connect_btn_flyio.clicked.connect(self._do_connect)
        lay_auth.addWidget(self._connect_btn_flyio)

        self._conn_status_flyio = QLabel("")
        self._conn_status_flyio.setStyleSheet(lbl_style)
        self._conn_status_flyio.setWordWrap(True)
        lay_auth.addWidget(self._conn_status_flyio)

        vlay.addWidget(card_auth)

        # ── Card: Application ────────────────────────────────────────
        card_app, lay_app, _ = make_card(i18n.tr("flyio_card_app"))

        self._flyio_app_list = QListWidget()
        self._flyio_app_list.setMaximumHeight(160)
        self._flyio_app_list.setStyleSheet(list_style)
        self._flyio_app_list.itemSelectionChanged.connect(
            lambda: self._open_btn_flyio.setEnabled(self._flyio_app_list.currentRow() >= 0)
        )
        lay_app.addWidget(self._flyio_app_list)

        iv_row = QHBoxLayout()
        iv_row.addWidget(self._lbl(lbl_style, i18n.tr("flyio_field_interval")))
        iv_row.addStretch()
        self._interval_spin_flyio = QSpinBox()
        self._interval_spin_flyio.setRange(1, 60)
        self._interval_spin_flyio.setValue(5)
        self._interval_spin_flyio.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px; font-size: 12px; max-width: 60px;"
        )
        iv_row.addWidget(self._interval_spin_flyio)
        lay_app.addLayout(iv_row)

        lb_row = QHBoxLayout()
        lb_row.addWidget(self._lbl(lbl_style, i18n.tr("field_time_range")))
        lb_row.addStretch()
        self._lookback_combo_flyio = _lookback_combo()
        lb_row.addWidget(self._lookback_combo_flyio)
        lay_app.addLayout(lb_row)

        self._open_mode_flyio = OpenModeWidget()
        lay_app.addWidget(self._open_mode_flyio)

        self._open_btn_flyio = _primary_btn(i18n.tr("flyio_open"))
        self._open_btn_flyio.clicked.connect(self._on_open)
        self._open_btn_flyio.setEnabled(False)
        lay_app.addWidget(self._open_btn_flyio)

        self._card_app_flyio = card_app
        card_app.setVisible(False)
        vlay.addWidget(card_app)
        vlay.addStretch()

    @staticmethod
    def _lbl(style: str, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(style)
        return lbl

    def _do_connect(self) -> None:
        token = self._flyio_token_input.text().strip()
        if not token:
            return
        self._connect_btn_flyio.setEnabled(False)
        self._conn_status_flyio.setText(i18n.tr("flyio_connecting"))
        self._conn_status_flyio.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        self._connect_worker = _FlyioConnectWorker(token)
        self._connect_worker.success.connect(self._on_connected_flyio)
        self._connect_worker.failure.connect(self._on_connect_fail_flyio)
        self._connect_worker.start()

    def _on_connected_flyio(self, apps: list) -> None:
        self._apps = apps
        self._conn_status_flyio.setText(i18n.tr("flyio_connected"))
        self._conn_status_flyio.setStyleSheet(f"color: {C_INFO}; font-size: 11px;")
        self._connect_btn_flyio.setEnabled(True)
        self._save_profile_btn_flyio.setEnabled(True)
        self._flyio_app_list.clear()
        if apps:
            for a in apps:
                status = a.get("status", "")
                label = f"{a['name']}  ({status})" if status else a["name"]
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, a["name"])
                self._flyio_app_list.addItem(item)
            self._card_app_flyio.setVisible(True)
        else:
            self._conn_status_flyio.setText(i18n.tr("flyio_no_apps"))

    def _on_connect_fail_flyio(self, msg: str) -> None:
        self._conn_status_flyio.setText(msg)
        self._conn_status_flyio.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
        self._connect_btn_flyio.setEnabled(True)

    def _load_flyio_profile(self, p: dict) -> None:
        self._flyio_token_input.setText(p.get("token", ""))

    def _on_save_flyio_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:", text="flyio")
        if not ok or not name.strip():
            return
        profiles_store.upsert("flyio", name.strip(), {
            "token": self._flyio_token_input.text().strip(),
        })
        self._flyio_profile_bar.reload()

    def _on_open(self) -> None:
        token = self._flyio_token_input.text().strip()
        item  = self._flyio_app_list.currentItem()
        if not item:
            return
        app_name = item.data(Qt.ItemDataRole.UserRole) or item.text().split("  ")[0]
        cfg = {
            "type":       "flyio",
            "token":      token,
            "app_name":   app_name,
            "interval_s": self._interval_spin_flyio.value(),
            "lookback_s": self._lookback_combo_flyio.currentData(),
            "label":      app_name,
        }
        self.open_tab.emit(cfg, self._open_mode_flyio.get_mode())
