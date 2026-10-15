"""Kubernetes connection panel."""

from __future__ import annotations

from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from simplelog.core import i18n
from simplelog.sources import kubernetes_utils
from simplelog.ui.panels.base import FIELD_STYLE, LBL_STYLE, LIST_STYLE, ProviderPanel
from simplelog.ui.ui_theme import C_BG, C_BORDER, C_ERR, C_INFO, C_MUTED, C_PANEL, C_TEXT
from simplelog.ui.ui_widgets import (
    NoScrollComboBox,
    OpenModeWidget,
    _lookback_combo,
    _primary_btn,
    make_card,
)
from simplelog.ui.ui_workers import BackgroundWorker, CallWorker

# ── KubernetesPanel ───────────────────────────────────────────────────────────

class _K8sConnectWorker(BackgroundWorker):
    success = pyqtSignal(list, list)  # namespaces, contexts

    def __init__(self, context: str) -> None:
        super().__init__()
        self._context = context

    def _work(self) -> tuple:
        namespaces = kubernetes_utils.list_namespaces(self._context)
        contexts   = kubernetes_utils.list_contexts()
        return (namespaces, contexts)


class _K8sListPodsWorker(BackgroundWorker):
    success = pyqtSignal(list)

    def __init__(self, namespace: str, context: str) -> None:
        super().__init__()
        self._namespace = namespace
        self._context   = context

    def _work(self) -> tuple:
        pods = kubernetes_utils.list_pods(self._namespace, self._context)
        return (pods,)


class KubernetesPanel(ProviderPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._context = ""
        self._connect_worker: _K8sConnectWorker | None = None
        self._pods_worker: _K8sListPodsWorker | None = None
        self._build_ui()

    def _on_contexts_loaded(self, result) -> None:
        contexts, current = result
        combo = self._k8s_context_combo
        selected = combo.currentText()          # may be a saved context chosen before this arrived
        for ctx in contexts:
            if combo.findText(ctx) < 0:
                combo.addItem(ctx)
        if selected != "(current context)":
            combo.setCurrentIndex(max(0, combo.findText(selected)))
        elif current:
            idx = combo.findText(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        if not kubernetes_utils.is_available():
            lbl = QLabel(i18n.tr("kubernetes_not_available"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f"color: {C_MUTED}; font-size: 13px; background: transparent; border: none; padding: 24px;"
            )
            root.addWidget(lbl)
            return

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

        # ── Card: Cluster ────────────────────────────────────────────
        card_cluster, lay_cluster, _ = make_card(i18n.tr("kubernetes_card_cluster"), help_key="help_kubernetes")

        lay_cluster.addWidget(self._lbl(LBL_STYLE, i18n.tr("kubernetes_field_context")))
        self._k8s_context_combo = NoScrollComboBox()
        self._k8s_context_combo.addItem("(current context)")
        # kubectl is spawned to list the contexts: do it in the background
        self._contexts_worker = CallWorker(
            lambda: (kubernetes_utils.list_contexts(), kubernetes_utils.current_context())
        )
        self._contexts_worker.success.connect(self._on_contexts_loaded)
        self._contexts_worker.start()
        self._k8s_context_combo.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )
        lay_cluster.addWidget(self._k8s_context_combo)

        self._connect_btn_k8s = _primary_btn(i18n.tr("kubernetes_connect"))
        self._connect_btn_k8s.clicked.connect(self._do_connect)
        lay_cluster.addWidget(self._connect_btn_k8s)

        self._conn_status_k8s = QLabel("")
        self._conn_status_k8s.setStyleSheet(LBL_STYLE)
        self._conn_status_k8s.setWordWrap(True)
        lay_cluster.addWidget(self._conn_status_k8s)

        vlay.addWidget(card_cluster)

        # ── Card: Namespace / Pod ────────────────────────────────────
        card_pod, lay_pod, _ = make_card(i18n.tr("kubernetes_card_pod"))

        lay_pod.addWidget(self._lbl(LBL_STYLE, i18n.tr("kubernetes_field_ns")))
        self._k8s_ns_combo = NoScrollComboBox()
        self._k8s_ns_combo.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )
        self._k8s_ns_combo.currentTextChanged.connect(self._on_ns_changed)
        lay_pod.addWidget(self._k8s_ns_combo)

        self._k8s_pod_list = QListWidget()
        self._k8s_pod_list.setMaximumHeight(150)
        self._k8s_pod_list.setStyleSheet(LIST_STYLE)
        self._k8s_pod_list.itemSelectionChanged.connect(
            lambda: self._open_btn_k8s.setEnabled(self._k8s_pod_list.currentRow() >= 0)
        )
        lay_pod.addWidget(self._k8s_pod_list)

        lay_pod.addWidget(self._lbl(LBL_STYLE, i18n.tr("kubernetes_field_container")))
        self._k8s_container_input = QLineEdit()
        self._k8s_container_input.setPlaceholderText("(auto)")
        self._k8s_container_input.setStyleSheet(FIELD_STYLE)
        lay_pod.addWidget(self._k8s_container_input)

        lb_row = QHBoxLayout()
        lb_row.addWidget(self._lbl(LBL_STYLE, i18n.tr("field_time_range")))
        lb_row.addStretch()
        self._lookback_combo_k8s = _lookback_combo()
        lb_row.addWidget(self._lookback_combo_k8s)
        lay_pod.addLayout(lb_row)

        self._open_mode_k8s = OpenModeWidget()
        lay_pod.addWidget(self._open_mode_k8s)

        self._open_btn_k8s = _primary_btn(i18n.tr("kubernetes_open"))
        self._open_btn_k8s.clicked.connect(self._on_open)
        self._open_btn_k8s.setEnabled(False)
        lay_pod.addWidget(self._open_btn_k8s)

        self._card_pod = card_pod
        card_pod.setVisible(False)
        vlay.addWidget(card_pod)
        vlay.addStretch()

    def _do_connect(self) -> None:
        ctx_text = self._k8s_context_combo.currentText()
        context  = "" if ctx_text == "(current context)" else ctx_text
        self._context = context
        self._connect_btn_k8s.setEnabled(False)
        self._conn_status_k8s.setText(i18n.tr("kubernetes_connecting"))
        self._conn_status_k8s.setStyleSheet(f"color: {C_MUTED}; font-size: 11px;")
        self._connect_worker = _K8sConnectWorker(context)
        self._connect_worker.success.connect(self._on_connected_k8s)
        self._connect_worker.failure.connect(self._on_connect_fail_k8s)
        self._connect_worker.start()

    def _on_connected_k8s(self, namespaces: list, _contexts: list) -> None:
        self._conn_status_k8s.setText(i18n.tr("kubernetes_connected"))
        self._conn_status_k8s.setStyleSheet(f"color: {C_INFO}; font-size: 11px;")
        self._connect_btn_k8s.setEnabled(True)
        self._k8s_ns_combo.blockSignals(True)
        self._k8s_ns_combo.clear()
        if namespaces:
            self._k8s_ns_combo.addItems(namespaces)
            self._card_pod.setVisible(True)
        else:
            self._conn_status_k8s.setText(i18n.tr("kubernetes_no_ns"))
        self._k8s_ns_combo.blockSignals(False)
        if namespaces:
            self._on_ns_changed(self._k8s_ns_combo.currentText())

    def _on_connect_fail_k8s(self, msg: str) -> None:
        self._conn_status_k8s.setText(msg)
        self._conn_status_k8s.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
        self._connect_btn_k8s.setEnabled(True)

    def _on_ns_changed(self, ns: str) -> None:
        if not ns:
            return
        self._k8s_pod_list.clear()
        self._open_btn_k8s.setEnabled(False)
        self._pods_worker = _K8sListPodsWorker(ns, self._context)
        self._pods_worker.success.connect(self._on_pods_listed)
        self._pods_worker.failure.connect(
            lambda e: self._conn_status_k8s.setText(e)
        )
        self._pods_worker.start()

    def _on_pods_listed(self, pods: list) -> None:
        self._k8s_pod_list.clear()
        if pods:
            for pod in pods:
                status = pod.get("status", "")
                label  = f"{pod['name']}  ({status})" if status else pod["name"]
                item   = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, pod["name"])
                self._k8s_pod_list.addItem(item)
        else:
            self._conn_status_k8s.setText(i18n.tr("kubernetes_no_pods"))

    def _load_k8s_profile(self, p: dict) -> None:
        ctx = p.get("context", "")
        if ctx and self._k8s_context_combo.findText(ctx) < 0:
            # The contexts may still be loading: keep the saved one selectable now
            self._k8s_context_combo.addItem(ctx)
        idx = self._k8s_context_combo.findText(ctx) if ctx else 0
        self._k8s_context_combo.setCurrentIndex(max(0, idx))

    def _on_open(self) -> None:
        ns   = self._k8s_ns_combo.currentText()
        item = self._k8s_pod_list.currentItem()
        if not ns or not item:
            return
        pod       = item.data(Qt.ItemDataRole.UserRole) or item.text().split("  ")[0]
        container = self._k8s_container_input.text().strip()
        ctx_text  = self._k8s_context_combo.currentText()
        context   = "" if ctx_text == "(current context)" else ctx_text
        cfg = {
            "type":      "kubernetes",
            "pod":       pod,
            "namespace": ns,
            "context":   context,
            "container": container,
            "lookback_s": self._lookback_combo_k8s.currentData(),
            "label":     f"{ns}/{pod}",
        }
        self.open_tab.emit(cfg, self._open_mode_k8s.get_mode())

    # ── Embedding contract (see ProviderPanel) ────────────────────────────────

    restore_attrs = ("_k8s_container_input", "_lookback_combo_k8s", "_k8s_ns_combo", "_k8s_pod_list")

    def connect_now(self) -> None:
        self._do_connect()

    def is_connected(self) -> bool:
        return not self._card_pod.isHidden()

    def load_profile(self, data: dict) -> None:
        self._load_k8s_profile(data)

    def can_open(self) -> bool:
        button = getattr(self, "_open_btn_k8s", None)       # absent when kubectl is missing
        return button.isEnabled() if button is not None else False

    def open_selected(self) -> None:
        self._on_open()

    def profile_data(self) -> dict:
        combo = getattr(self, "_k8s_context_combo", None)
        if combo is None:
            return {}
        context = combo.currentText()
        return {"context": "" if context == "(current context)" else context}

    def _embedded_hidden(self) -> list:
        button = getattr(self, "_open_btn_k8s", None)
        return [button] if button is not None else []
