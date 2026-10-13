"""Remote connection dialogs and the remote home panel."""

from __future__ import annotations

from PyQt6.QtCore import (
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import i18n
import profiles_store
from panels.azure import AzurePanel
from panels.cloudflare import CloudflarePanel
from panels.cloudwatch import CloudWatchPanel
from panels.datadog import DatadogPanel
from panels.docker import DockerPanel
from panels.elastic import ElasticPanel
from panels.flyio import FlyioPanel
from panels.gcp import GCPPanel
from panels.kubernetes import KubernetesPanel
from panels.loki import LokiPanel
from panels.railway import RailwayPanel
from panels.ssh import SSHPanel
from panels.vercel import VercelPanel
from ui_theme import (
    _SVG_AZURE,
    _SVG_CHEVRON_LEFT,
    _SVG_CLOUD,
    _SVG_CLOUDFLARE,
    _SVG_DATADOG,
    _SVG_DOCKER,
    _SVG_ELASTIC,
    _SVG_FLYIO,
    _SVG_GCP,
    _SVG_KUBERNETES,
    _SVG_LOKI,
    _SVG_RAILWAY,
    _SVG_REMOTE,
    _SVG_SSH,
    _SVG_VERCEL,
    C_ACCENT,
    C_ACCENT_DIM,
    C_BG,
    C_BORDER,
    C_CARD,
    C_ERR,
    C_INFO,
    C_MUTED,
    C_PANEL,
    C_SIDE,
    C_TEXT,
    C_TRACE,
    C_TS,
    _svg_icon,
)
from ui_widgets import _ghost_btn, _primary_btn

# ── Remote redesign: providers + AddConnectionDialog + RemoteHomePanel ────────

RESULT_OPEN = 2  # custom dialog result: connect without saving

_REMOTE_PROVIDERS: list[tuple[str, str, str, str, str, str]] = [
    ("cloudwatch", "AWS CloudWatch", "☁",  "#ff9900", _SVG_CLOUD,  "AWS CloudWatch Logs"),
    ("gcp",        "Google Cloud",   "⬡",  "#4285f4", _SVG_GCP,    "Google Cloud Logging"),
    ("azure",      "Azure Monitor",  "△",  "#0078d4", _SVG_AZURE,  "Azure Monitor / Log Analytics"),
    ("ssh",        "SSH",            "⌥",  "#56cf80", _SVG_SSH,    "Remote log files over SSH"),
    ("docker",     "Docker",         "◈",  "#2496ed", _SVG_DOCKER, "Remote Docker container logs"),
    ("vercel",     "Vercel",         "▲",  "#e2e2e2", _SVG_VERCEL, "Vercel deployment & runtime logs"),
    ("loki",       "Grafana Loki",   "≡",  "#f46800", _SVG_LOKI,       "Grafana Loki log aggregation"),
    ("datadog",    "Datadog",        "⬡",  "#632ca6", _SVG_DATADOG,    "Datadog Logs"),
    ("elastic",    "Elasticsearch",  "⊙",  "#f04e98", _SVG_ELASTIC,    "Elasticsearch / OpenSearch"),
    ("railway",    "Railway",        "▣",  "#b975f2", _SVG_RAILWAY,    "Railway deployment logs"),
    ("flyio",      "Fly.io",         "⬥",  "#7b3fc4", _SVG_FLYIO,      "Fly.io app logs"),
    ("kubernetes",  "Kubernetes",     "⎈",  "#326ce5", _SVG_KUBERNETES,  "Kubernetes pod logs"),
    ("cloudflare",  "Cloudflare",     "⛅", "#f6821f", _SVG_CLOUDFLARE,  "Cloudflare Workers real-time logs"),
]

_PROVIDER_FIELDS: dict[str, list[tuple[str, str, str, bool]]] = {
    "cloudwatch": [
        ("name",       "Connection name", "prod-us-east-1",     False),
        ("region",     "AWS Region",      "us-east-1",          False),
        ("profile",    "AWS Profile",     "default",            False),
        ("access_key", "Access Key ID",   "AKIA… (optional)",   False),
        ("secret_key", "Secret Key",      "",                   True),
    ],
    "gcp": [
        ("name",        "Connection name",      "gcp-staging",               False),
        ("project",     "Project ID",           "my-project-123",            False),
        ("credentials", "Service account JSON", "~/.config/gcloud/key.json", False),
    ],
    "azure": [
        ("name",          "Connection name", "azure-prod",          False),
        ("workspace_id",  "Workspace ID",    "xxxx-xxxx-xxxx-xxxx", False),
        ("tenant_id",     "Tenant ID",       "xxxx-xxxx-xxxx-xxxx", False),
        ("client_id",     "Client ID",       "xxxx-xxxx-xxxx-xxxx", False),
        ("client_secret", "Client secret",   "",                    True),
    ],
    "ssh": [
        ("name",     "Connection name", "prod-server",   False),
        ("host",     "Host",            "192.168.1.10",  False),
        ("port",     "Port",            "22",            False),
        ("user",     "Username",        "ubuntu",        False),
        ("key_path", "SSH key path",    "~/.ssh/id_rsa", False),
    ],
    "docker": [
        ("name",      "Connection name", "docker-remote",       False),
        ("host",      "Docker host",     "tcp://10.0.0.1:2376", False),
        ("cert_path", "TLS cert path",   "/path/to/certs (opt.)", False),
    ],
    "vercel": [
        ("name",  "Connection name", "vercel-prod",      False),
        ("token", "API Token",       "",                 True),
        ("team",  "Team slug",       "acme-corp (opt.)", False),
    ],
    "loki": [
        ("name",     "Connection name", "loki-prod",            False),
        ("url",      "Loki URL",        "http://localhost:3100", False),
        ("username", "Username",        "(optional)",           False),
        ("password", "Password",        "",                     True),
        ("token",    "Bearer token",    "(optional)",           True),
    ],
    "datadog": [
        ("name",    "Connection name", "datadog-prod",          False),
        ("site",    "Site",            "US1 (datadoghq.com)",   False),
        ("api_key", "API Key",         "",                      True),
        ("app_key", "Application Key", "",                      True),
    ],
    "elastic": [
        ("name",     "Connection name", "elastic-prod",         False),
        ("url",      "Elasticsearch URL", "http://localhost:9200", False),
        ("api_key",  "API Key",          "(optional)",          True),
        ("username", "Username",         "(optional)",          False),
        ("password", "Password",         "",                    True),
    ],
    "railway": [
        ("name",  "Connection name", "railway-prod",            False),
        ("token", "API Token",       "",                        True),
    ],
    "flyio": [
        ("name",  "Connection name", "fly-prod",                False),
        ("token", "API Token",       "",                        True),
    ],
    "kubernetes": [
        ("name",      "Connection name", "k8s-prod",            False),
        ("context",   "kubectl context", "(default context)",   False),
        ("namespace", "Namespace",       "default",             False),
    ],
    "cloudflare": [
        ("name",       "Connection name", "cloudflare-prod",                 False),
        ("api_token",  "API Token",       "",                                True),
        ("account_id", "Account ID",      "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", False),
    ],
}


_RUNNING_WORKERS: set = set()   # workers of closed dialogs, kept alive until they finish


def _widget_state(w: QWidget):
    """Snapshot the user-visible value of an input widget."""
    if isinstance(w, QListWidget):
        item = w.currentItem()
        return item.text() if item else ""
    if isinstance(w, QComboBox):
        return w.currentText()
    if isinstance(w, QSpinBox):
        return w.value()
    if isinstance(w, QTabWidget):
        return w.currentIndex()
    if isinstance(w, QTextEdit):
        return w.toPlainText()
    return w.text()


def _restore_widget_state(w: QWidget, value) -> bool:
    """Apply a saved value. Returns False while the saved item is not (yet) listed."""
    if isinstance(w, QListWidget):
        if not value:
            return True
        # Compare names only: "pod-1  (Running)" must match "pod-1  (Pending)"
        key = value.strip().split("  ")[0]
        for i in range(w.count()):
            if w.item(i).text().strip().split("  ")[0] == key:
                w.setCurrentItem(w.item(i))
                return True
        return False
    if isinstance(w, QComboBox):
        if not value:
            return True
        idx = w.findText(value)
        if idx < 0:
            return False
        w.setCurrentIndex(idx)
    elif isinstance(w, QSpinBox):
        w.setValue(value)
    elif isinstance(w, QTabWidget):
        w.setCurrentIndex(value)
    elif isinstance(w, QTextEdit):
        w.setPlainText(value)
    else:
        w.setText(value)
    return True


class AddConnectionDialog(QDialog):
    """Two-step modal: step 1 = provider picker, step 2 = credential form."""

    tab_requested = pyqtSignal(dict, str)

    def __init__(self, parent=None, preselect: str | None = None, prefill_profile: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("remote_add_title"))
        self.setModal(True)
        self.setFixedWidth(500)
        self.setStyleSheet(
            f"QDialog {{ background: #13131a; color: {C_TEXT}; }}"
        )

        self._provider_id: str = ""
        self._fields: dict[str, QLineEdit] = {}
        self._open_btn: QPushButton | None = None
        self._save_open_btn: QPushButton | None = None
        self._cw_embedded_panel: CloudWatchPanel | None = None
        self._cw_save_pending: bool = False
        self._add_header_lbl: QLabel | None = None
        self._embedded_panel: QWidget | None = None
        self._embedded_save_pending: bool = False
        self._embedded_get_ready: object = None
        self._embedded_trigger: object = None
        self._embedded_get_save_data: object = None
        self._ready_timer: QTimer | None = None
        self._embedded_state_attrs: list[str] = []
        self._restore_queue: list = []
        self._restore_connected: object = None
        self._restore_ticks_left: int = 0
        self._prefill_profile: dict | None = prefill_profile
        self._is_existing: bool = prefill_profile is not None
        _key = id(self)
        i18n.register(_key, self._retranslate_dlg)
        self.finished.connect(lambda _=0, k=_key: self._release(k))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        root.addWidget(self._stack)

        self._stack.addWidget(self._build_step1())

        self._step2_widget = QWidget()
        self._step2_widget.setStyleSheet("background: transparent;")
        self._step2_layout = QVBoxLayout(self._step2_widget)
        self._step2_layout.setContentsMargins(0, 0, 0, 0)
        self._step2_layout.setSpacing(0)
        self._stack.addWidget(self._step2_widget)

        if preselect:
            self._go_step2(preselect)

    def _release(self, i18n_key: int) -> None:
        """Free what the dialog keeps alive once it is closed (timer, callbacks, SSH)."""
        i18n.unregister(i18n_key)
        if self._ready_timer:
            self._ready_timer.stop()
            self._ready_timer = None
        panel = self._embedded_panel or self._cw_embedded_panel
        if panel is None:
            return
        # The panel's own SSH connection is only used for browsing; the tab opened from
        # it gets a separate one.
        client = getattr(panel, "_client", None) if isinstance(panel, SSHPanel) else None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        # A connect/list worker may still be running: keep it referenced until it ends,
        # otherwise Qt aborts with "QThread destroyed while running".
        for value in list(vars(panel).values()):
            if isinstance(value, QThread) and value.isRunning():
                _RUNNING_WORKERS.add(value)
                value.finished.connect(lambda v=value: _RUNNING_WORKERS.discard(v))

    # ── Step 1 ────────────────────────────────────────────────────────────────

    def _retranslate_dlg(self) -> None:
        self.setWindowTitle(i18n.tr("remote_add_title"))
        if self._add_header_lbl is not None:
            self._add_header_lbl.setText(i18n.tr("remote_add_header"))

    def _build_step1(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        hdr = QWidget()
        hdr.setStyleSheet(
            "background: #1a1a24; border-bottom: 1px solid rgba(255,255,255,26);"
        )
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(20, 16, 20, 16)
        hdr_lay.setSpacing(8)

        titles = QVBoxLayout()
        titles.setSpacing(3)
        self._add_header_lbl = QLabel(i18n.tr("remote_add_header"))
        t1 = self._add_header_lbl
        t1.setStyleSheet(
            f"color: {C_TEXT}; font-size: 14px; font-weight: 700;"
            " border: none; background: transparent;"
        )
        t2 = QLabel(i18n.tr("remote_select_provider"))
        t2.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11.5px; border: none; background: transparent;"
        )
        titles.addWidget(t1)
        titles.addWidget(t2)
        hdr_lay.addLayout(titles, 1)

        close = QPushButton("✕")
        close.setFixedSize(28, 28)
        close.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_MUTED};"
            f" border: none; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {C_TEXT}; }}"
        )
        close.clicked.connect(self.reject)
        hdr_lay.addWidget(close)
        lay.addWidget(hdr)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        grid_lay = QGridLayout(body)
        grid_lay.setContentsMargins(20, 20, 20, 24)
        grid_lay.setSpacing(8)

        for i, (pid, name, icon_char, color, _svg, desc) in enumerate(_REMOTE_PROVIDERS):
            grid_lay.addWidget(
                self._make_provider_card(pid, name, icon_char, color, desc),
                i // 3, i % 3,
            )

        lay.addWidget(body)
        return page

    def _make_provider_card(
        self, pid: str, name: str, icon_char: str, color: str, desc: str
    ) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(140, 105)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: #17171f;
                border: 1px solid rgba(255,255,255,15);
                border-radius: 9px;
            }}
            QPushButton:hover {{
                background: #1e1e2c;
                border-color: {color};
            }}
        """)

        inner = QVBoxLayout(btn)
        inner.setContentsMargins(10, 12, 10, 12)
        inner.setSpacing(0)
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel(icon_char)
        icon_lbl.setFixedSize(30, 30)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        icon_lbl.setStyleSheet(
            f"background: {color}20; border: 1px solid {color}35;"
            f" border-radius: 6px; color: {color}; font-size: 15px;"
        )

        name_lbl = QLabel(name)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setWordWrap(True)
        name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        name_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-size: 11.5px; font-weight: 600;"
            " background: transparent; border: none;"
        )

        inner.addStretch()
        inner.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignHCenter)
        inner.addSpacing(8)
        inner.addWidget(name_lbl, 0, Qt.AlignmentFlag.AlignHCenter)
        inner.addStretch()

        btn.clicked.connect(lambda _c, p=pid: self._go_step2(p))
        return btn

    # ── Step 2 ────────────────────────────────────────────────────────────────

    def _go_step2(self, provider_id: str) -> None:
        self._provider_id = provider_id
        # Clear previous step2 content
        while self._step2_layout.count():
            item = self._step2_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        prov = next((p for p in _REMOTE_PROVIDERS if p[0] == provider_id), None)
        if not prov:
            return
        _, name, icon_char, color, _svg, _ = prov

        # Header
        hdr = QWidget()
        hdr.setStyleSheet(
            "background: #1a1a24; border-bottom: 1px solid rgba(255,255,255,26);"
        )
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(14, 12, 14, 12)
        hdr_lay.setSpacing(8)

        back_btn = QPushButton()
        back_btn.setFixedSize(28, 28)
        back_btn.setIcon(_svg_icon(_SVG_CHEVRON_LEFT, C_MUTED, 14))
        back_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { background: rgba(255,255,255,8); border-radius: 4px; }"
        )
        back_btn.clicked.connect(self._go_step1)
        hdr_lay.addWidget(back_btn)

        icon_lbl = QLabel(icon_char)
        icon_lbl.setFixedSize(24, 24)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            f"background: {color}20; border: 1px solid {color}35;"
            f" border-radius: 5px; color: {color}; font-size: 13px;"
        )
        hdr_lay.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-size: 13.5px; font-weight: 700;"
            " background: transparent; border: none;"
        )
        sub_lbl = QLabel(i18n.tr("remote_new_connection"))
        sub_lbl.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        title_col.addWidget(name_lbl)
        title_col.addWidget(sub_lbl)
        hdr_lay.addLayout(title_col, 1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_MUTED};"
            f" border: none; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {C_TEXT}; }}"
        )
        close_btn.clicked.connect(self.reject)
        hdr_lay.addWidget(close_btn)
        self._step2_layout.addWidget(hdr)

        if provider_id == "cloudwatch":
            self._build_cw_step2()
            self._stack.setCurrentIndex(1)
            return

        self._build_embedded_step2(provider_id)

    def _make_form_fields(
        self, provider_id: str, lay: QVBoxLayout
    ) -> dict[str, QLineEdit]:
        fields: dict[str, QLineEdit] = {}
        for key, label, placeholder, is_password in _PROVIDER_FIELDS.get(provider_id, []):
            wrap = QWidget()
            wrap.setStyleSheet("background: transparent;")
            wl = QVBoxLayout(wrap)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setSpacing(5)

            display_label = i18n.tr("remote_connection_name") if key == "name" else label
            lbl = QLabel(display_label.upper())
            lbl.setStyleSheet(
                f"color: {C_ACCENT}; font-size: 10px; font-weight: 700;"
                " letter-spacing: 0.8px; background: transparent; border: none;"
            )
            wl.addWidget(lbl)

            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            if is_password:
                edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.setStyleSheet(
                f"QLineEdit {{ background: {C_BG}; border: 1px solid rgba(255,255,255,26);"
                f" border-radius: 5px; padding: 6px 10px;"
                f" font-family: 'JetBrains Mono', monospace; font-size: 11.5px;"
                f" color: {C_TEXT}; }}"
                f"QLineEdit:focus {{ border-color: {C_ACCENT}88; }}"
            )
            wl.addWidget(edit)
            lay.addWidget(wrap)
            fields[key] = edit

        return fields

    # ── Navigation & actions ──────────────────────────────────────────────────

    def _go_step1(self) -> None:
        self._provider_id = ""
        self._fields = {}
        self._cw_embedded_panel = None
        if self._ready_timer:
            self._ready_timer.stop()
            self._ready_timer = None
        self._embedded_panel = None
        self._embedded_get_ready = None
        self._embedded_trigger = None
        self._embedded_get_save_data = None
        self._embedded_save_pending = False
        self._restore_queue = []
        self.setMaximumHeight(16777215)
        self.adjustSize()
        self._stack.setCurrentIndex(0)

    def _on_name_changed(self, text: str) -> None:
        enabled = bool(text.strip())
        if self._open_btn:
            self._open_btn.setEnabled(enabled)
        if self._save_open_btn:
            self._save_open_btn.setEnabled(enabled)

    def _on_open(self) -> None:
        if self._provider_id == "cloudwatch" and self._cw_embedded_panel:
            self._cw_save_pending = False
            self._cw_embedded_panel._on_open_clicked()
        elif self._embedded_panel and self._embedded_trigger:
            self._embedded_save_pending = False
            self._embedded_trigger()
        else:
            self.done(RESULT_OPEN)

    def _on_save_open(self) -> None:
        if self._provider_id == "cloudwatch" and self._cw_embedded_panel:
            self._cw_save_pending = True
            self._cw_embedded_panel._on_open_clicked()
        elif self._embedded_panel and self._embedded_trigger:
            self._embedded_save_pending = True
            self._embedded_trigger()
        else:
            data = self.get_form_data()
            name = data.get("name", "").strip()
            if name and self._provider_id:
                profiles_store.upsert(self._provider_id, name, data)
            self.done(QDialog.DialogCode.Accepted)

    def get_provider(self) -> str:
        return self._provider_id

    def get_form_data(self) -> dict:
        return {k: v.text() for k, v in self._fields.items()}

    # ── CloudWatch: embed CloudWatchPanel directly ───────────────────────────

    def _build_cw_step2(self) -> None:
        """Embed CloudWatchPanel directly — same proven code as AddRemoteDialog."""
        self.setFixedHeight(680)

        # ── Embed CloudWatchPanel ─────────────────────────────────────────────
        panel = CloudWatchPanel(parent=self)
        panel._title_lbl.setVisible(False)
        panel._save_profile_btn_cw.setVisible(False)
        panel.open_btn.setVisible(False)
        panel.open_tab.connect(self._cw_on_panel_tab)
        panel.group_list.currentTextChanged.connect(lambda _: self._cw_update_footer_btns())
        self._cw_embedded_panel = panel
        self._step2_layout.addWidget(panel, 1)

        # Saved connection: prefill credentials, then connect once the dialog is shown
        if self._prefill_profile is not None:
            prefill = self._prefill_profile
            panel._load_cw_profile(prefill)
            QTimer.singleShot(0, lambda: panel._restore_saved_target(
                prefill.get("group", ""), prefill.get("stream", "")
            ))

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet(
            "background: #17171f; border-top: 1px solid rgba(255,255,255,26);"
        )
        foot_lay = QVBoxLayout(footer)
        foot_lay.setContentsMargins(20, 14, 20, 14)
        foot_lay.setSpacing(8)

        # ── Connection name ───────────────────────────────────────────────────
        name_lbl = QLabel(i18n.tr("remote_connection_name").upper())
        name_lbl.setStyleSheet(
            f"color: {C_ACCENT}; font-size: 10px; font-weight: 700;"
            " letter-spacing: 0.8px; background: transparent; border: none;"
        )
        foot_lay.addWidget(name_lbl)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText(i18n.tr("remote_connection_name"))
        name_edit.setStyleSheet(
            f"QLineEdit {{ background: {C_BG}; border: 1px solid rgba(255,255,255,26);"
            f" border-radius: 5px; padding: 5px 10px;"
            f" font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: {C_TEXT}; }}"
            f"QLineEdit:focus {{ border-color: {C_ACCENT}88; }}"
        )
        name_edit.textChanged.connect(self._cw_update_footer_btns)
        self._fields["name"] = name_edit
        foot_lay.addWidget(name_edit)

        # Pre-fill name from prefill_profile if available
        if self._prefill_profile is not None:
            pname = self._prefill_profile.get("name", "")
            if pname:
                name_edit.setText(pname)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = _ghost_btn(i18n.tr("remote_cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()

        if self._is_existing:
            self._open_btn = _primary_btn(i18n.tr("remote_open"))
            self._save_open_btn = _ghost_btn(i18n.tr("remote_save_open"))
        else:
            self._open_btn = _ghost_btn(i18n.tr("remote_open"))
            self._save_open_btn = _primary_btn(i18n.tr("remote_save_open"))
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._on_open)
        btn_row.addWidget(self._open_btn)

        self._save_open_btn.setEnabled(False)
        self._save_open_btn.clicked.connect(self._on_save_open)
        btn_row.addWidget(self._save_open_btn)

        foot_lay.addLayout(btn_row)
        self._step2_layout.addWidget(footer)

    # ── Embedded panel step 2 (all non-CW providers) ─────────────────────────

    def _build_embedded_step2(self, provider_id: str) -> None:
        """Embed the provider's own panel, hide its internal buttons, add unified footer."""
        _configs = {
            "ssh": dict(
                factory=SSHPanel,
                connect=lambda p: p._on_connect() if p._auth_combo.currentIndex() == 0 else None,
                connected=lambda p: p._client is not None,
                state=["_tail_spin"],
                load=lambda p, d: p._load_ssh_profile(d),
                open_ready=lambda p: p._file_card_frame.isVisible() and bool(p._path_input.text().strip()),
                trigger=lambda p: p._on_open(),
                save_data=lambda p: {
                    "host": p._host_input.text().strip(),
                    "port": p._port_spin.value(),
                    "user": p._user_input.text().strip(),
                    "auth_mode": "key" if p._auth_combo.currentIndex() == 0 else "password",
                    "key_path": p._key_input.text().strip() if p._auth_combo.currentIndex() == 0 else "",
                    "remote_path": p._path_input.text().strip(),
                },
                hide_btns=lambda p: [p._save_profile_btn_ssh],
                hide_open=lambda p: [p._open_btn],
                hide_title=True,
                no_save=False,
            ),
            "docker": dict(
                factory=DockerPanel,
                load=lambda p, d: None,
                open_ready=lambda p: (
                    (not hasattr(p, '_tabs')) or
                    (p._tabs.currentIndex() == 0 and hasattr(p, '_open_btn_c') and p._open_btn_c.isEnabled()) or
                    (p._tabs.currentIndex() == 1 and hasattr(p, '_open_btn_s') and p._open_btn_s.isEnabled()) or
                    (p._tabs.currentIndex() == 2 and hasattr(p, '_open_btn_e') and p._open_btn_e.isEnabled())
                ),
                trigger=lambda p: (
                    p._on_open_container() if p._tabs.currentIndex() == 0 else
                    p._on_open_stack()     if p._tabs.currentIndex() == 1 else
                    p._on_open_exec()
                ) if hasattr(p, '_tabs') else None,
                save_data=lambda p: {},
                hide_btns=lambda p: [],
                hide_open=lambda p: [],
                hide_title=True,
                no_save=True,
            ),
            "vercel": dict(
                factory=VercelPanel,
                connect=lambda p: p._do_connect(),
                connected=lambda p: not p._card_proj.isHidden(),
                state=["_interval_spin", "_lookback_combo_vercel", "_target_combo", "_project_list"],
                load=lambda p, d: p._load_vercel_profile(d),
                open_ready=lambda p: p._open_btn.isEnabled(),
                trigger=lambda p: p._on_open(),
                save_data=lambda p: {"token": p._token_input.text().strip()},
                hide_btns=lambda p: [p._save_profile_btn_vercel],
                hide_open=lambda p: [p._open_btn],
                hide_title=False,
                no_save=False,
            ),
            "gcp": dict(
                factory=GCPPanel,
                connect=lambda p: p._do_connect(),
                connected=lambda p: not p._card_filt.isHidden(),
                state=["_resource_combo", "_severity_combo", "_custom_input", "_lookback_combo_gcp", "_interval_spin_gcp"],
                load=lambda p, d: p._load_gcp_profile(d),
                open_ready=lambda p: p._open_btn_gcp.isEnabled(),
                trigger=lambda p: p._on_open(),
                save_data=lambda p: {
                    "auth_mode":  p._auth_combo.currentIndex(),
                    "key_path":   p._key_input.text().strip() if p._auth_combo.currentIndex() == 1 else "",
                    "project_id": p._project_input.text().strip(),
                },
                hide_btns=lambda p: [p._save_profile_btn_gcp],
                hide_open=lambda p: [p._open_btn_gcp],
                hide_title=False,
                no_save=False,
            ),
            "azure": dict(
                factory=AzurePanel,
                connect=lambda p: p._do_connect(),
                connected=lambda p: p._logs_client is not None,
                state=["_tabs", "_timespan_combo", "_interval_spin_az_t", "_kql_edit", "_timespan_combo_kql", "_interval_spin_az_k", "_table_list"],
                load=lambda p, d: p._load_az_profile(d),
                open_ready=lambda p: p._open_btn_az_t.isEnabled() or p._open_btn_az_k.isEnabled(),
                trigger=lambda p: p._on_open_table() if p._tabs.currentIndex() == 0 else p._on_open_kql(),
                save_data=lambda p: {
                    "tenant_id":     p._tenant_input.text().strip(),
                    "client_id":     p._client_id_input.text().strip(),
                    "client_secret": p._secret_input.text().strip(),
                    "workspace_id":  p._workspace_input.text().strip(),
                },
                hide_btns=lambda p: [p._save_profile_btn_az],
                hide_open=lambda p: [p._open_btn_az_t, p._open_btn_az_k],
                hide_title=False,
                no_save=False,
            ),
            "loki": dict(
                factory=LokiPanel,
                connect=lambda p: p._do_connect(),
                connected=lambda p: not p._card_query.isHidden(),
                state=["_query_input", "_lookback_combo_loki", "_interval_spin"],
                load=lambda p, d: p._load_loki_profile(d),
                open_ready=lambda p: p._open_btn_loki.isEnabled(),
                trigger=lambda p: p._on_open(),
                save_data=lambda p: {
                    "url":       p._url_input.text().strip(),
                    "auth_mode": p._auth_combo.currentIndex(),
                    "username":  p._user_input.text().strip() if p._auth_combo.currentIndex() == 1 else "",
                    "password":  p._pass_input.text()         if p._auth_combo.currentIndex() == 1 else "",
                    "token":     p._token_input.text().strip() if p._auth_combo.currentIndex() == 2 else "",
                },
                hide_btns=lambda p: [p._save_profile_btn_loki],
                hide_open=lambda p: [p._open_btn_loki],
                hide_title=False,
                no_save=False,
            ),
            "datadog": dict(
                factory=DatadogPanel,
                connect=lambda p: p._do_connect(),
                connected=lambda p: p._connected,
                state=["_dd_query_input", "_lookback_combo_dd", "_interval_spin_dd"],
                load=lambda p, d: p._load_datadog_profile(d),
                open_ready=lambda p: p._open_btn_dd.isEnabled(),
                trigger=lambda p: p._on_open(),
                save_data=lambda p: {
                    "site":    p._site_combo.currentText(),
                    "api_key": p._api_key_input.text().strip(),
                    "app_key": p._app_key_input.text().strip(),
                },
                hide_btns=lambda p: [p._save_profile_btn_dd],
                hide_open=lambda p: [p._open_btn_dd],
                hide_title=False,
                no_save=False,
            ),
            "elastic": dict(
                factory=ElasticPanel,
                connect=lambda p: p._do_connect(),
                connected=lambda p: not p._card_query_es.isHidden(),
                state=["_es_index_input", "_es_ts_input", "_es_query_input", "_lookback_combo_es", "_interval_spin_es", "_es_index_combo"],
                load=lambda p, d: p._load_elastic_profile(d),
                open_ready=lambda p: p._open_btn_es.isEnabled(),
                trigger=lambda p: p._on_open(),
                save_data=lambda p: {
                    "url":       p._es_url_input.text().strip(),
                    "auth_mode": p._es_auth_combo.currentIndex(),
                    "api_key":   p._es_apikey_input.text().strip() if p._es_auth_combo.currentIndex() == 1 else "",
                    "username":  p._es_user_input.text().strip()   if p._es_auth_combo.currentIndex() == 2 else "",
                    "password":  p._es_pass_input.text()           if p._es_auth_combo.currentIndex() == 2 else "",
                },
                hide_btns=lambda p: [p._save_profile_btn_es],
                hide_open=lambda p: [p._open_btn_es],
                hide_title=False,
                no_save=False,
            ),
            "railway": dict(
                factory=RailwayPanel,
                connect=lambda p: p._do_connect(),
                connected=lambda p: not p._card_proj.isHidden(),
                state=["_interval_spin_railway", "_lookback_combo_railway", "_project_list", "_service_list"],
                load=lambda p, d: p._load_railway_profile(d),
                open_ready=lambda p: p._open_btn_railway.isEnabled(),
                trigger=lambda p: p._on_open(),
                save_data=lambda p: {"token": p._railway_token_input.text().strip()},
                hide_btns=lambda p: [p._save_profile_btn_railway],
                hide_open=lambda p: [p._open_btn_railway],
                hide_title=False,
                no_save=False,
            ),
            "flyio": dict(
                factory=FlyioPanel,
                connect=lambda p: p._do_connect(),
                connected=lambda p: not p._card_app_flyio.isHidden(),
                state=["_interval_spin_flyio", "_lookback_combo_flyio", "_flyio_app_list"],
                load=lambda p, d: p._load_flyio_profile(d),
                open_ready=lambda p: p._open_btn_flyio.isEnabled(),
                trigger=lambda p: p._on_open(),
                save_data=lambda p: {"token": p._flyio_token_input.text().strip()},
                hide_btns=lambda p: [p._save_profile_btn_flyio],
                hide_open=lambda p: [p._open_btn_flyio],
                hide_title=False,
                no_save=False,
            ),
            "kubernetes": dict(
                factory=KubernetesPanel,
                connect=lambda p: p._do_connect(),
                connected=lambda p: not p._card_pod.isHidden(),
                state=["_k8s_container_input", "_lookback_combo_k8s", "_k8s_ns_combo", "_k8s_pod_list"],
                load=lambda p, d: p._load_k8s_profile(d),
                open_ready=lambda p: p._open_btn_k8s.isEnabled() if hasattr(p, '_open_btn_k8s') else False,
                trigger=lambda p: p._on_open(),
                save_data=lambda p: {
                    "context": p._k8s_context_combo.currentText() if p._k8s_context_combo.currentText() != "(current context)" else ""
                } if hasattr(p, '_k8s_context_combo') else {},
                hide_btns=lambda p: [],
                hide_open=lambda p: [p._open_btn_k8s] if hasattr(p, '_open_btn_k8s') else [],
                hide_title=False,
                no_save=False,
            ),
            "cloudflare": dict(
                factory=CloudflarePanel,
                connect=lambda p: p._do_connect(),
                connected=lambda p: not p._card_wk.isHidden(),
                state=["_cf_worker_list"],
                load=lambda p, d: p._load_cloudflare_profile(d),
                open_ready=lambda p: p._open_btn_cf.isEnabled(),
                trigger=lambda p: p._on_open(),
                save_data=lambda p: {
                    "api_token":  p._cf_token_input.text().strip(),
                    "account_id": p._cf_account_input.text().strip(),
                },
                hide_btns=lambda p: [p._save_profile_btn_cf],
                hide_open=lambda p: [p._open_btn_cf],
                hide_title=False,
                no_save=False,
            ),
        }

        cfg = _configs.get(provider_id)
        if cfg is None:
            return

        # Create panel
        panel = cfg["factory"](parent=self)

        # Hide internal save-profile and open buttons
        for btn in cfg["hide_btns"](panel):
            btn.setVisible(False)
        for btn in cfg["hide_open"](panel):
            btn.setVisible(False)

        # Hide title label if present
        if cfg["hide_title"] and hasattr(panel, '_title_lbl'):
            panel._title_lbl.setVisible(False)

        # Store callables
        self._embedded_panel = panel
        self._embedded_get_ready = lambda: cfg["open_ready"](panel)
        self._embedded_trigger = lambda: cfg["trigger"](panel)
        self._embedded_get_save_data = lambda: cfg["save_data"](panel)

        # Connect open_tab signal
        panel.open_tab.connect(self._on_embedded_panel_tab)

        self._embedded_state_attrs = cfg.get("state", [])

        # Prefill if a profile was provided, then reconnect and restore the saved selection
        if self._prefill_profile is not None:
            cfg["load"](panel, self._prefill_profile)
            saved = self._prefill_profile.get("state", {})
            self._restore_queue = [
                (getattr(panel, a), saved[a]) for a in self._embedded_state_attrs if a in saved
            ]
            self._restore_connected = lambda: cfg["connected"](panel)
            self._restore_ticks_left = 150  # give up after ~30 s once connected
            if "connect" in cfg:
                cfg["connect"](panel)

        self.setFixedHeight(680)
        self._step2_layout.addWidget(panel, 1)

        no_save = cfg["no_save"]

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet(
            "background: #17171f; border-top: 1px solid rgba(255,255,255,26);"
        )
        foot_lay = QVBoxLayout(footer)
        foot_lay.setContentsMargins(20, 14, 20, 14)
        foot_lay.setSpacing(8)

        if not no_save:
            name_lbl = QLabel(i18n.tr("remote_connection_name").upper())
            name_lbl.setStyleSheet(
                f"color: {C_ACCENT}; font-size: 10px; font-weight: 700;"
                " letter-spacing: 0.8px; background: transparent; border: none;"
            )
            foot_lay.addWidget(name_lbl)

            name_edit = QLineEdit()
            name_edit.setPlaceholderText(i18n.tr("remote_connection_name"))
            name_edit.setStyleSheet(
                f"QLineEdit {{ background: {C_BG}; border: 1px solid rgba(255,255,255,26);"
                f" border-radius: 5px; padding: 5px 10px;"
                f" font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: {C_TEXT}; }}"
                f"QLineEdit:focus {{ border-color: {C_ACCENT}88; }}"
            )
            name_edit.textChanged.connect(self._sync_embedded_footer)
            self._fields["name"] = name_edit
            foot_lay.addWidget(name_edit)

            # Pre-fill name from prefill_profile if available
            if self._prefill_profile is not None:
                pname = self._prefill_profile.get("name", "")
                if pname:
                    name_edit.setText(pname)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = _ghost_btn(i18n.tr("remote_cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()

        if self._is_existing:
            self._open_btn = _primary_btn(i18n.tr("remote_open"))
        else:
            self._open_btn = _ghost_btn(i18n.tr("remote_open"))
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._on_open)
        btn_row.addWidget(self._open_btn)

        if not no_save:
            if self._is_existing:
                self._save_open_btn = _ghost_btn(i18n.tr("remote_save_open"))
            else:
                self._save_open_btn = _primary_btn(i18n.tr("remote_save_open"))
            self._save_open_btn.setEnabled(False)
            self._save_open_btn.clicked.connect(self._on_save_open)
            btn_row.addWidget(self._save_open_btn)
        else:
            self._save_open_btn = None

        foot_lay.addLayout(btn_row)
        self._step2_layout.addWidget(footer)

        # Start polling timer for button readiness
        self._ready_timer = QTimer(self)
        self._ready_timer.setInterval(200)
        self._ready_timer.timeout.connect(self._sync_embedded_footer)
        self._ready_timer.start()

        self._stack.setCurrentIndex(1)

    def _pump_restore(self) -> None:
        """Re-apply saved widget values in order, waiting for async lists to load."""
        if not self._restore_queue or not self._restore_connected():
            return
        self._restore_ticks_left -= 1
        if self._restore_ticks_left < 0:
            self._restore_queue = []
            return
        while self._restore_queue and _restore_widget_state(*self._restore_queue[0]):
            self._restore_queue.pop(0)

    def _sync_embedded_footer(self) -> None:
        if not self._embedded_get_ready:
            return
        self._pump_restore()
        ready = self._embedded_get_ready()
        name_ok = bool(self._fields.get("name") and self._fields["name"].text().strip())
        if self._open_btn:
            self._open_btn.setEnabled(ready)
        if self._save_open_btn:
            self._save_open_btn.setEnabled(not self._is_existing and ready and name_ok)

    def _on_embedded_panel_tab(self, cfg: dict, mode: str) -> None:
        if self._embedded_save_pending and self._embedded_get_save_data:
            name_edit = self._fields.get("name")
            name = name_edit.text().strip() if name_edit else ""
            if name and self._provider_id:
                data = self._embedded_get_save_data()
                data["state"] = {
                    a: _widget_state(getattr(self._embedded_panel, a))
                    for a in self._embedded_state_attrs
                }
                profiles_store.upsert(self._provider_id, name, data)
        self._embedded_save_pending = False
        self.tab_requested.emit(cfg, mode)
        self.done(QDialog.DialogCode.Accepted)

    def _cw_update_footer_btns(self) -> None:
        panel = self._cw_embedded_panel
        panel_ready = bool(panel and panel.open_btn.isEnabled())
        name_ok = bool(self._fields.get("name") and self._fields["name"].text().strip())
        if self._open_btn:
            self._open_btn.setEnabled(panel_ready)
        if self._save_open_btn:
            self._save_open_btn.setEnabled(not self._is_existing and panel_ready and name_ok)

    def _cw_on_panel_tab(self, cfg: dict, mode: str) -> None:
        if self._cw_save_pending:
            name_edit = self._fields.get("name")
            name = name_edit.text().strip() if name_edit else ""
            if name and self._cw_embedded_panel:
                p = self._cw_embedded_panel
                is_keys = p._auth_mode_combo.currentIndex() == 1
                creds: dict = {"region": p.region_combo.currentText()}
                if is_keys:
                    creds["access_key_id"] = p.access_key_input.text().strip()
                    creds["secret_key"]    = p.secret_key_input.text().strip()
                else:
                    creds["aws_profile"] = p.profile_combo.currentText()
                for key in ("group", "stream", "filter", "interval", "lookback"):
                    creds[key] = cfg[key]
                profiles_store.upsert("cloudwatch", name, creds)
            self.tab_requested.emit(cfg, mode)
            self.done(QDialog.DialogCode.Accepted)
        else:
            self.tab_requested.emit(cfg, mode)
            self.done(RESULT_OPEN)


    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self._stack.currentIndex() == 1:
                self._go_step1()
            else:
                self.reject()
        else:
            super().keyPressEvent(event)


# ── AddRemoteDialog ────────────────────────────────────────────────────────────

class AddRemoteDialog(QDialog):
    """Popin de configuration d'une source distante.

    Page 0  : grille de sélection du fournisseur.
    Pages 1+ : panneau de config existant embarqué.
    """

    tab_requested = pyqtSignal(dict, str)

    _PROVIDERS: list[tuple[str, str, str, str]] = [
        ("cloudwatch",  "CloudWatch",    _SVG_CLOUD,       C_ACCENT),
        ("ssh",         "SSH",           _SVG_SSH,         C_TRACE),
        ("docker",      "Docker",        _SVG_DOCKER,      C_TS),
        ("vercel",      "Vercel",        _SVG_VERCEL,      C_ERR),
        ("gcp",         "GCP",           _SVG_GCP,         C_INFO),
        ("azure",       "Azure",         _SVG_AZURE,       C_ACCENT_DIM),
        ("loki",        "Loki",          _SVG_LOKI,        "#f46800"),
        ("datadog",     "Datadog",       _SVG_DATADOG,     "#632ca6"),
        ("elastic",     "Elasticsearch", _SVG_ELASTIC,     "#f04e98"),
        ("railway",     "Railway",       _SVG_RAILWAY,     "#b975f2"),
        ("flyio",       "Fly.io",        _SVG_FLYIO,       "#7b3fc4"),
        ("kubernetes",  "Kubernetes",    _SVG_KUBERNETES,  "#326ce5"),
        ("cloudflare",  "Cloudflare",    _SVG_CLOUDFLARE,  "#f6821f"),
    ]

    def __init__(self, parent=None,
                 prefill_service: str | None = None,
                 prefill_profile: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("remote_dialog_title"))
        self.setModal(True)
        self.setFixedSize(560, 680)
        self.setStyleSheet(f"background: {C_PANEL}; color: {C_TEXT};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(
            f"background: {C_SIDE}; border-bottom: 1px solid {C_BORDER};"
        )
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(12, 0, 12, 0)
        h_lay.setSpacing(8)

        self._back_btn = QPushButton(i18n.tr("remote_back"))
        self._back_btn.setFixedHeight(28)
        self._back_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_MUTED};"
            f" border: none; font-size: 12px; padding: 0 8px; }}"
            f"QPushButton:hover {{ color: {C_TEXT}; }}"
        )
        self._back_btn.clicked.connect(self._on_back)
        self._back_btn.setVisible(False)
        h_lay.addWidget(self._back_btn)

        self._title_lbl = QLabel(i18n.tr("remote_dialog_header"))
        self._title_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-size: 14px; font-weight: 600;"
            " border: none; background: transparent;"
        )
        h_lay.addWidget(self._title_lbl, 1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_MUTED};"
            f" border: none; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {C_TEXT}; }}"
        )
        close_btn.clicked.connect(self.reject)
        h_lay.addWidget(close_btn)

        root.addWidget(header)

        # ── Stack ──────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        root.addWidget(self._stack, 1)

        # Page 0 — provider picker
        self._stack.addWidget(self._build_picker_page())

        # Pages 1-12 — existing panels
        self._cw_panel          = CloudWatchPanel()
        self._ssh_panel         = SSHPanel()
        self._docker_panel      = DockerPanel()
        self._vercel_panel      = VercelPanel()
        self._gcp_panel         = GCPPanel()
        self._azure_panel       = AzurePanel()
        self._loki_panel        = LokiPanel()
        self._datadog_panel     = DatadogPanel()
        self._elastic_panel     = ElasticPanel()
        self._railway_panel     = RailwayPanel()
        self._flyio_panel       = FlyioPanel()
        self._kubernetes_panel  = KubernetesPanel()
        self._cloudflare_panel  = CloudflarePanel()

        for panel in (self._cw_panel, self._ssh_panel, self._docker_panel,
                      self._vercel_panel, self._gcp_panel, self._azure_panel,
                      self._loki_panel, self._datadog_panel, self._elastic_panel,
                      self._railway_panel, self._flyio_panel, self._kubernetes_panel,
                      self._cloudflare_panel):
            panel.open_tab.connect(self._on_panel_open_tab)
            self._stack.addWidget(panel)

        self._provider_indices: dict[str, int] = {
            svc: i + 1 for i, (svc, *_) in enumerate(self._PROVIDERS)
        }
        self._load_fns: dict[str, object] = {
            "cloudwatch":  self._cw_panel._load_cw_profile,
            "ssh":         self._ssh_panel._load_ssh_profile,
            "vercel":      self._vercel_panel._load_vercel_profile,
            "gcp":         self._gcp_panel._load_gcp_profile,
            "azure":       self._azure_panel._load_az_profile,
            "loki":        self._loki_panel._load_loki_profile,
            "datadog":     self._datadog_panel._load_datadog_profile,
            "elastic":     self._elastic_panel._load_elastic_profile,
            "railway":     self._railway_panel._load_railway_profile,
            "flyio":       self._flyio_panel._load_flyio_profile,
            "kubernetes":  self._kubernetes_panel._load_k8s_profile,
            "cloudflare":  self._cloudflare_panel._load_cloudflare_profile,
        }

        if prefill_service:
            self._go_to_provider(prefill_service)
            if prefill_profile and prefill_service in self._load_fns:
                self._load_fns[prefill_service](prefill_profile)

    # ── Picker page ───────────────────────────────────────────────────────────

    def _build_picker_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background: {C_PANEL};")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(16)

        lbl = QLabel(i18n.tr("remote_choose"))
        lbl.setStyleSheet(
            f"color: {C_MUTED}; font-size: 12px; font-weight: 600;"
        )
        outer.addWidget(lbl)

        grid = QGridLayout()
        grid.setSpacing(12)

        for i, (svc, label, svg, color) in enumerate(self._PROVIDERS):
            btn = self._make_provider_btn(svc, label, svg, color)
            grid.addWidget(btn, i // 3, i % 3)

        outer.addLayout(grid)
        outer.addStretch()
        return page

    def _make_provider_btn(self, svc: str, label: str,
                           svg: str, color: str) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(148, 100)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_CARD};
                border: 1px solid {C_BORDER};
                border-radius: 10px;
            }}
            QPushButton:hover {{
                border-color: {color};
                background: rgba(255,255,255,6);
            }}
        """)

        inner = QVBoxLayout(btn)
        inner.setContentsMargins(0, 14, 0, 12)
        inner.setSpacing(6)
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(32, 32)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setPixmap(_svg_icon(svg, color, 28).pixmap(28, 28))
        icon_lbl.setStyleSheet("background: transparent; border: none;")

        text_lbl = QLabel(label)
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-size: 12px; font-weight: 600;"
            " background: transparent; border: none;"
        )

        inner.addStretch()
        inner.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignHCenter)
        inner.addWidget(text_lbl, 0, Qt.AlignmentFlag.AlignHCenter)
        inner.addStretch()

        btn.clicked.connect(lambda _checked, s=svc: self._go_to_provider(s))
        return btn

    # ── Navigation ────────────────────────────────────────────────────────────

    def _go_to_provider(self, svc: str) -> None:
        idx = self._provider_indices.get(svc, 0)
        self._stack.setCurrentIndex(idx)
        label = next((lbl for svc2, lbl, *_ in self._PROVIDERS if svc2 == svc), svc)
        self._title_lbl.setText(f"{i18n.tr('remote_dialog_header')}  ·  {label}")
        self._back_btn.setVisible(True)

    def _on_back(self) -> None:
        self._stack.setCurrentIndex(0)
        self._title_lbl.setText(i18n.tr("remote_dialog_header"))
        self._back_btn.setVisible(False)

    # ── Relay ─────────────────────────────────────────────────────────────────

    def _on_panel_open_tab(self, cfg: dict, split: str) -> None:
        self.tab_requested.emit(cfg, split)
        self.accept()


# ── RemoteHomePanel ────────────────────────────────────────────────────────────

class RemoteHomePanel(QWidget):
    """Sidebar panel: collapsible provider groups + new AddConnectionDialog."""

    tab_requested = pyqtSignal(dict, str)

    _PROVIDER_ORDER = [
        "cloudwatch", "gcp", "azure", "ssh", "docker", "vercel",
        "loki", "datadog", "elastic", "railway", "flyio", "kubernetes",
        "cloudflare",
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._expanded: dict[str, bool] = {}
        self._build_ui()
        self.reload()
        _key = id(self)
        i18n.register(_key, self.retranslate)

    def retranslate(self) -> None:
        self._remote_title_lbl.setText(i18n.tr("remote_title"))
        self._remote_add_btn.setText(i18n.tr("remote_add_btn"))

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(
            f"background: {C_SIDE}; border-bottom: 1px solid {C_BORDER};"
        )
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(14, 0, 14, 0)
        h_lay.setSpacing(10)

        self._remote_title_lbl = QLabel(i18n.tr("remote_title"))
        self._remote_title_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-size: 15px; font-weight: 700;"
        )
        h_lay.addWidget(self._remote_title_lbl, 1)

        self._remote_add_btn = _primary_btn(i18n.tr("remote_add_btn"))
        self._remote_add_btn.clicked.connect(self._on_add)
        h_lay.addWidget(self._remote_add_btn)
        root.addWidget(header)

        # Scrollable provider groups
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        self._groups_widget = QWidget()
        self._groups_widget.setStyleSheet(f"background: {C_PANEL};")
        self._groups_lay = QVBoxLayout(self._groups_widget)
        self._groups_lay.setContentsMargins(0, 0, 0, 0)
        self._groups_lay.setSpacing(0)
        self._groups_lay.addStretch()

        scroll.setWidget(self._groups_widget)
        root.addWidget(scroll, 1)

    # ── Reload ────────────────────────────────────────────────────────────────

    def reload(self) -> None:
        lay = self._groups_lay
        while lay.count() > 1:
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        any_conn = False
        for svc in self._PROVIDER_ORDER:
            profiles = profiles_store.load_all(svc)
            if profiles:
                any_conn = True
            lay.insertWidget(lay.count() - 1, self._make_provider_group(svc, profiles))

        if not any_conn:
            lay.insertWidget(lay.count() - 1, self._make_empty_state())

    # ── Empty state ───────────────────────────────────────────────────────────

    def _make_empty_state(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 40, 20, 40)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setPixmap(_svg_icon(_SVG_REMOTE, C_MUTED, 32).pixmap(32, 32))
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        lay.addWidget(icon_lbl)

        lbl1 = QLabel(i18n.tr("remote_no_connections"))
        lbl1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl1.setStyleSheet(
            f"color: {C_MUTED}; font-size: 12px; background: transparent; border: none;"
        )
        lay.addWidget(lbl1)

        lbl2 = QLabel(i18n.tr("remote_no_connections_sub"))
        lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl2.setStyleSheet(
            "color: #3a3a4a; font-size: 11px; background: transparent; border: none;"
        )
        lay.addWidget(lbl2)
        return w

    # ── Provider group ────────────────────────────────────────────────────────

    def _make_provider_group(self, svc: str, profiles: list[dict]) -> QWidget:
        prov = next((p for p in _REMOTE_PROVIDERS if p[0] == svc), None)
        if not prov:
            return QWidget()
        _, name, icon_char, color, _svg, _ = prov

        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        w_lay = QVBoxLayout(wrapper)
        w_lay.setContentsMargins(0, 0, 0, 0)
        w_lay.setSpacing(0)

        # Header button
        hdr_btn = QPushButton()
        hdr_btn.setFixedHeight(36)
        hdr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        hdr_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_CARD};
                border: none;
                border-bottom: 1px solid {C_BORDER};
                text-align: left;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,8); }}
        """)
        hdr_inner = QHBoxLayout(hdr_btn)
        hdr_inner.setContentsMargins(10, 0, 10, 0)
        hdr_inner.setSpacing(8)

        icon_box = QLabel(icon_char)
        icon_box.setFixedSize(20, 20)
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        icon_box.setStyleSheet(
            f"background: {color}18; border: 1px solid {color}30;"
            f" border-radius: 4px; color: {color}; font-size: 11px;"
        )
        hdr_inner.addWidget(icon_box)

        name_lbl = QLabel(name)
        name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        name_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-size: 12px; font-weight: 600;"
            " background: transparent; border: none;"
        )
        hdr_inner.addWidget(name_lbl, 1)

        if profiles:
            count_lbl = QLabel(str(len(profiles)))
            count_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            count_lbl.setStyleSheet(
                f"color: {C_MUTED}; font-size: 10px; background: transparent; border: none;"
            )
            hdr_inner.addWidget(count_lbl)

        is_expanded = self._expanded.get(svc, bool(profiles))
        chev = QLabel("▼" if is_expanded else "▶")
        chev.setFixedWidth(14)
        chev.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        chev.setStyleSheet(
            f"color: {C_MUTED}; font-size: 9px; background: transparent; border: none;"
        )
        hdr_inner.addWidget(chev)
        w_lay.addWidget(hdr_btn)

        # Expandable content
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content.setVisible(is_expanded)
        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(0)

        for profile in profiles:
            c_lay.addWidget(self._make_conn_row(svc, profile))

        c_lay.addWidget(self._make_add_inline_row(svc))
        w_lay.addWidget(content)

        def _toggle() -> None:
            exp = not content.isVisible()
            content.setVisible(exp)
            self._expanded[svc] = exp
            chev.setText("▼" if exp else "▶")

        hdr_btn.clicked.connect(_toggle)
        return wrapper

    # ── Connection row ────────────────────────────────────────────────────────

    def _make_conn_row(self, svc: str, profile: dict) -> QWidget:
        row = QFrame()
        row.setFixedHeight(32)
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet(
            "QFrame { background: rgba(17,17,22,150);"
            " border-top: 1px solid rgba(255,255,255,13); }"
            "QFrame:hover { background: rgba(255,255,255,8); }"
        )
        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(38, 0, 8, 0)
        row_lay.setSpacing(6)

        dot = QLabel()
        dot.setFixedSize(5, 5)
        dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        dot.setStyleSheet(
            f"background: {C_INFO}; border-radius: 3px; border: none;"
        )
        row_lay.addWidget(dot)

        conn_name = profile.get("name", "—")
        name_lbl = QLabel(conn_name)
        name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        name_lbl.setStyleSheet(
            "color: #b0b0c0; font-size: 11.5px;"
            " font-family: 'JetBrains Mono', monospace;"
            " background: transparent; border: none;"
        )
        row_lay.addWidget(name_lbl)

        subtitle = self._get_subtitle(svc, profile)
        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            sub_lbl.setStyleSheet(
                f"color: {C_MUTED}; font-size: 10px; background: transparent; border: none;"
            )
            row_lay.addWidget(sub_lbl)

        row_lay.addStretch()

        # Delete button with two-click confirm
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(22, 22)
        del_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_MUTED};"
            f" border: none; font-size: 11px; }}"
            f"QPushButton:hover {{ color: {C_ERR}; }}"
        )
        row_lay.addWidget(del_btn)

        _confirmed = [False]
        _timer: list[QTimer | None] = [None]

        def _reset_del() -> None:
            _confirmed[0] = False
            del_btn.setText("✕")
            del_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {C_MUTED};"
                f" border: none; font-size: 11px; }}"
                f"QPushButton:hover {{ color: {C_ERR}; }}"
            )

        def _on_del_clicked() -> None:
            if not _confirmed[0]:
                _confirmed[0] = True
                del_btn.setText("!")
                del_btn.setStyleSheet(
                    f"QPushButton {{ background: {C_ERR}20; color: {C_ERR};"
                    f" border: 1px solid {C_ERR}40; border-radius: 3px;"
                    f" font-size: 9px; font-weight: 700; }}"
                    f"QPushButton:hover {{ background: {C_ERR}30; }}"
                )
                t = QTimer()
                t.setSingleShot(True)
                t.timeout.connect(_reset_del)
                t.start(3000)
                _timer[0] = t
            else:
                if _timer[0]:
                    _timer[0].stop()
                profiles_store.delete(svc, conn_name)
                self.reload()

        del_btn.clicked.connect(_on_del_clicked)

        row.mousePressEvent = lambda e, s=svc, p=profile: (
            self._on_open_profile(s, p)
            if e.button() == Qt.MouseButton.LeftButton
            else None
        )
        return row

    # ── Inline "add connection" row ───────────────────────────────────────────

    def _make_add_inline_row(self, svc: str) -> QLabel:
        row = QLabel(i18n.tr("remote_add_connection"))
        row.setFixedHeight(28)
        row.setContentsMargins(38, 0, 10, 0)
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet(
            f"QLabel {{ color: {C_MUTED}; font-size: 11px;"
            f" background: transparent;"
            f" border-top: 1px solid rgba(255,255,255,8); }}"
            f"QLabel:hover {{ color: {C_ACCENT};"
            f" background: rgba(91,143,255,13); }}"
        )
        row.mousePressEvent = lambda _e, s=svc: self._on_add(preselect=s)
        return row

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _get_subtitle(svc: str, profile: dict) -> str:
        key = {
            "cloudwatch": "region",
            "gcp":        "project",
            "azure":      "workspace_id",
            "ssh":        "host",
            "docker":     "host",
            "vercel":     "team",
            "cloudflare": "account_id",
        }.get(svc, "")
        return profile.get(key, "")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_add(self, preselect: str | None = None) -> None:
        dlg = AddConnectionDialog(parent=self, preselect=preselect)
        dlg.tab_requested.connect(self.tab_requested)
        dlg.exec()
        dlg.deleteLater()
        self.reload()

    def _on_open_profile(self, svc: str, profile: dict) -> None:
        dlg = AddConnectionDialog(
            parent=self,
            preselect=svc,
            prefill_profile=profile,
        )
        dlg.tab_requested.connect(self.tab_requested)
        dlg.exec()
        dlg.deleteLater()
        self.reload()
