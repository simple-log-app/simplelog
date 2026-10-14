"""Docker connection panel."""

from __future__ import annotations

from PyQt6.QtCore import (
    Qt,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import docker_utils
import i18n
from panels.base import ProviderPanel
from ui_theme import (
    C_ACCENT,
    C_ACCENT_HOVER,
    C_ACCENT_PRESS,
    C_MUTED,
    C_ON_ACCENT,
    C_SIDE,
    C_TEXT,
)
from ui_widgets import (
    OpenModeWidget,
    _ghost_btn,
    _HelpDialog,
    _lookback_combo,
    _primary_btn,
    make_card,
)
from ui_workers import CallWorker

# ── DockerPanel ───────────────────────────────────────────────────────────────

class DockerPanel(ProviderPanel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        _key = id(self)
        i18n.register(_key, self.retranslate)
        self.destroyed.connect(lambda _=None, k=_key: i18n.unregister(k))

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setStyleSheet(f"background: {C_SIDE};")

        # ── Docker unavailable placeholder ────────────────────────────────────
        if not docker_utils.is_docker_available():
            lbl = QLabel(i18n.tr("docker_not_available"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f"color: {C_MUTED}; font-size: 13px; background: transparent; border: none; padding: 24px;"
            )
            outer.addWidget(lbl)
            return

        # Title bar
        title_bar = QWidget()
        title_bar.setStyleSheet(f"background: {C_SIDE};")
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(12, 16, 12, 8)
        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-size: 15px; font-weight: 700;"
            " background: transparent; border: none;"
        )
        tb_layout.addWidget(self._title_lbl)
        tb_layout.addStretch()
        _docker_help_btn = QPushButton("?")
        _docker_help_btn.setFixedSize(22, 22)
        _docker_help_btn.setToolTip(i18n.tr("help_dialog_title"))
        _docker_help_btn.setStyleSheet(
            f"QPushButton {{ background: {C_ACCENT}; color: {C_ON_ACCENT};"
            " border: none; border-radius: 11px;"
            " font-size: 13px; font-weight: bold; padding: 0; }"
            f"QPushButton:hover {{ background: {C_ACCENT_HOVER}; }}"
            f"QPushButton:pressed {{ background: {C_ACCENT_PRESS}; }}"
        )
        _docker_help_btn.clicked.connect(lambda: _HelpDialog(i18n.tr("help_docker"), self).exec())
        tb_layout.addWidget(_docker_help_btn)
        outer.addWidget(title_bar)

        # ── Inner QTabWidget ──────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {C_SIDE}; }}
            QTabBar::tab {{
                background: transparent; color: {C_MUTED};
                padding: 6px 14px; font-size: 11px; border: none;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {C_ACCENT}; border-bottom: 2px solid {C_ACCENT};
            }}
            QTabBar::tab:hover {{ color: {C_TEXT}; }}
        """)
        outer.addWidget(self._tabs)

        # ── Tab 0: Containers ─────────────────────────────────────────────────
        tab0 = QWidget()
        tab0.setStyleSheet(f"background: {C_SIDE};")
        t0 = QVBoxLayout(tab0)
        t0.setContentsMargins(12, 10, 12, 16)
        t0.setSpacing(12)
        self._tabs.addTab(tab0, "")

        card_c, cl_c, _ = make_card()
        # Refresh button header row
        hdr0 = QHBoxLayout()
        self._lbl_running = QLabel()
        self._lbl_running.setStyleSheet(
            f"color: {C_ACCENT}; font-size: 10px; font-weight: 700; background: transparent; border: none;"
        )
        self._refresh_btn0 = _ghost_btn()
        self._refresh_btn0.setMaximumWidth(100)
        self._refresh_btn0.clicked.connect(self._refresh_containers)
        hdr0.addWidget(self._lbl_running)
        hdr0.addStretch()
        hdr0.addWidget(self._refresh_btn0)
        self._container_list = QListWidget()
        self._container_list.setMinimumHeight(120)
        self._no_containers_lbl = QLabel()
        self._no_containers_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_containers_lbl.setStyleSheet(
            f"color: {C_MUTED}; font-size: 12px; background: transparent; border: none;"
        )
        cl_c.addLayout(hdr0)
        cl_c.addWidget(self._container_list)
        cl_c.addWidget(self._no_containers_lbl)
        t0.addWidget(card_c)

        card_co, ol_c, _ = make_card()
        t0.addWidget(card_co)
        self._open_mode_c = OpenModeWidget()
        self._open_btn_c = _primary_btn()
        self._open_btn_c.setEnabled(False)
        self._open_btn_c.clicked.connect(self._on_open_container)
        self._container_list.itemSelectionChanged.connect(
            lambda: self._open_btn_c.setEnabled(bool(self._container_list.selectedItems()))
        )
        lb_row_c = QHBoxLayout()
        self._lbl_tail_c = QLabel()
        self._lbl_tail_c.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        lb_row_c.addWidget(self._lbl_tail_c)
        lb_row_c.addStretch()
        self._lookback_combo_docker_c = _lookback_combo()
        lb_row_c.addWidget(self._lookback_combo_docker_c)
        ol_c.addLayout(lb_row_c)
        ol_c.addWidget(self._open_mode_c)
        ol_c.addWidget(self._open_btn_c)
        t0.addStretch()

        # ── Tab 1: Compose ────────────────────────────────────────────────────
        tab1 = QWidget()
        tab1.setStyleSheet(f"background: {C_SIDE};")
        t1 = QVBoxLayout(tab1)
        t1.setContentsMargins(12, 10, 12, 16)
        t1.setSpacing(12)
        self._tabs.addTab(tab1, "")

        card_s, sl, _ = make_card()
        hdr1 = QHBoxLayout()
        self._lbl_stacks = QLabel()
        self._lbl_stacks.setStyleSheet(
            f"color: {C_ACCENT}; font-size: 10px; font-weight: 700; background: transparent; border: none;"
        )
        self._refresh_btn1 = _ghost_btn()
        self._refresh_btn1.setMaximumWidth(100)
        self._refresh_btn1.clicked.connect(self._refresh_stacks)
        hdr1.addWidget(self._lbl_stacks)
        hdr1.addStretch()
        hdr1.addWidget(self._refresh_btn1)
        self._stack_list = QListWidget()
        self._stack_list.setMinimumHeight(120)
        self._no_stacks_lbl = QLabel()
        self._no_stacks_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_stacks_lbl.setStyleSheet(
            f"color: {C_MUTED}; font-size: 12px; background: transparent; border: none;"
        )
        sl.addLayout(hdr1)
        sl.addWidget(self._stack_list)
        sl.addWidget(self._no_stacks_lbl)
        t1.addWidget(card_s)

        card_so, ol_s, _ = make_card()
        t1.addWidget(card_so)
        self._open_mode_s = OpenModeWidget()
        self._open_btn_s = _primary_btn()
        self._open_btn_s.setEnabled(False)
        self._open_btn_s.clicked.connect(self._on_open_stack)
        self._stack_list.itemSelectionChanged.connect(
            lambda: self._open_btn_s.setEnabled(bool(self._stack_list.selectedItems()))
        )
        lb_row_s = QHBoxLayout()
        self._lbl_tail_s = QLabel()
        self._lbl_tail_s.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        lb_row_s.addWidget(self._lbl_tail_s)
        lb_row_s.addStretch()
        self._lookback_combo_docker_s = _lookback_combo()
        lb_row_s.addWidget(self._lookback_combo_docker_s)
        ol_s.addLayout(lb_row_s)
        ol_s.addWidget(self._open_mode_s)
        ol_s.addWidget(self._open_btn_s)
        t1.addStretch()

        # ── Tab 2: File in Container ──────────────────────────────────────────
        tab2 = QWidget()
        tab2.setStyleSheet(f"background: {C_SIDE};")
        t2 = QVBoxLayout(tab2)
        t2.setContentsMargins(12, 10, 12, 16)
        t2.setSpacing(12)
        self._tabs.addTab(tab2, "")

        card_ec, ecl, _ = make_card()
        hdr2 = QHBoxLayout()
        self._lbl_exec_c = QLabel()
        self._lbl_exec_c.setStyleSheet(
            f"color: {C_ACCENT}; font-size: 10px; font-weight: 700; background: transparent; border: none;"
        )
        self._refresh_btn2 = _ghost_btn()
        self._refresh_btn2.setMaximumWidth(100)
        self._refresh_btn2.clicked.connect(self._refresh_containers)
        hdr2.addWidget(self._lbl_exec_c)
        hdr2.addStretch()
        hdr2.addWidget(self._refresh_btn2)
        self._exec_container_list = QListWidget()
        self._exec_container_list.setMinimumHeight(100)
        self._no_exec_lbl = QLabel()
        self._no_exec_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_exec_lbl.setStyleSheet(
            f"color: {C_MUTED}; font-size: 12px; background: transparent; border: none;"
        )
        ecl.addLayout(hdr2)
        ecl.addWidget(self._exec_container_list)
        ecl.addWidget(self._no_exec_lbl)
        t2.addWidget(card_ec)

        card_ef, efl, _ = make_card()
        t2.addWidget(card_ef)
        self._lbl_exec_path = QLabel()
        self._lbl_exec_path.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        self._exec_path_input = QLineEdit()
        self._exec_path_input.setPlaceholderText("/var/log/app/service.log")
        self._tail_spin_e = QSpinBox()
        self._tail_spin_e.setRange(1, 500_000)
        self._tail_spin_e.setValue(100)
        self._tail_spin_e.setSingleStep(100)
        self._open_mode_e = OpenModeWidget()
        self._open_btn_e = _primary_btn()
        self._open_btn_e.setEnabled(False)
        self._open_btn_e.clicked.connect(self._on_open_exec)

        def _update_exec_btn():
            has_c = bool(self._exec_container_list.selectedItems())
            has_p = bool(self._exec_path_input.text().strip())
            self._open_btn_e.setEnabled(has_c and has_p)

        self._exec_container_list.itemSelectionChanged.connect(_update_exec_btn)
        self._exec_path_input.textChanged.connect(_update_exec_btn)

        tail_row_e = QHBoxLayout()
        self._lbl_tail_e = QLabel()
        self._lbl_tail_e.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11px; background: transparent; border: none;"
        )
        tail_row_e.addWidget(self._lbl_tail_e)
        tail_row_e.addWidget(self._tail_spin_e)
        tail_row_e.addStretch()
        efl.addWidget(self._lbl_exec_path)
        efl.addWidget(self._exec_path_input)
        efl.addLayout(tail_row_e)
        efl.addWidget(self._open_mode_e)
        efl.addWidget(self._open_btn_e)
        t2.addStretch()

        self.retranslate()
        self._refresh_containers()
        self._refresh_stacks()

    def retranslate(self) -> None:
        if not hasattr(self, "_title_lbl"):
            return
        self._title_lbl.setText(i18n.tr("docker_title"))
        self._tabs.setTabText(0, i18n.tr("docker_tab_containers"))
        self._tabs.setTabText(1, i18n.tr("docker_tab_compose"))
        self._tabs.setTabText(2, i18n.tr("docker_tab_exec"))
        self._lbl_running.setText(i18n.tr("docker_tab_containers").upper())
        self._lbl_stacks.setText(i18n.tr("docker_tab_compose").upper())
        self._lbl_exec_c.setText(i18n.tr("docker_tab_containers").upper())
        self._refresh_btn0.setText(i18n.tr("docker_refresh"))
        self._refresh_btn1.setText(i18n.tr("docker_refresh"))
        self._refresh_btn2.setText(i18n.tr("docker_refresh"))
        self._no_containers_lbl.setText(i18n.tr("docker_no_containers"))
        self._no_stacks_lbl.setText(i18n.tr("docker_no_stacks"))
        self._no_exec_lbl.setText(i18n.tr("docker_no_containers"))
        self._lbl_tail_c.setText(i18n.tr("field_time_range"))
        self._lbl_tail_s.setText(i18n.tr("field_time_range"))
        self._lbl_tail_e.setText(i18n.tr("docker_field_tail"))
        self._lbl_exec_path.setText(i18n.tr("docker_field_path"))
        self._open_btn_c.setText(i18n.tr("docker_open_container"))
        self._open_btn_s.setText(i18n.tr("docker_open_stack"))
        self._open_btn_e.setText(i18n.tr("docker_open_exec"))

    # ── Data refresh ──────────────────────────────────────────────────────────

    def _refresh_containers(self) -> None:
        self._fetch("_containers_worker", docker_utils.list_containers, self._show_containers)

    def _fetch(self, attr: str, fn, on_done) -> None:
        """Run a docker CLI query off the UI thread; an error shows an empty list."""
        running = getattr(self, attr, None)
        if running is not None and running.isRunning():
            return
        worker = CallWorker(fn)
        worker.success.connect(on_done)
        worker.failure.connect(lambda _msg: on_done([]))
        setattr(self, attr, worker)
        worker.start()

    def _show_containers(self, containers: list) -> None:
        self._container_list.clear()
        self._exec_container_list.clear()
        if containers:
            self._no_containers_lbl.hide()
            self._no_exec_lbl.hide()
            self._container_list.show()
            self._exec_container_list.show()
            for c in containers:
                label = f"{c['name']}   ({c['image']})"
                for lst in (self._container_list, self._exec_container_list):
                    item = QListWidgetItem(label)
                    item.setData(Qt.ItemDataRole.UserRole, c)
                    if c["compose_project"]:
                        item.setToolTip(i18n.tr("docker_compose_tip", project=c["compose_project"],
                                            service=c["compose_service"]))
                    lst.addItem(item)
        else:
            self._no_containers_lbl.show()
            self._no_exec_lbl.show()
            self._container_list.hide()
            self._exec_container_list.hide()

    def _refresh_stacks(self) -> None:
        self._fetch("_stacks_worker", docker_utils.list_compose_stacks, self._show_stacks)

    def _show_stacks(self, stacks: list) -> None:
        self._stack_list.clear()
        if stacks:
            self._no_stacks_lbl.hide()
            self._stack_list.show()
            for s in stacks:
                item = QListWidgetItem(f"{s['name']}   ({s['status']})")
                item.setData(Qt.ItemDataRole.UserRole, s)
                item.setToolTip(s.get("config_files", ""))
                self._stack_list.addItem(item)
        else:
            self._no_stacks_lbl.show()
            self._stack_list.hide()

    # ── Open actions ──────────────────────────────────────────────────────────

    def _on_open_container(self) -> None:
        items = self._container_list.selectedItems()
        if not items:
            return
        c = items[0].data(Qt.ItemDataRole.UserRole)
        cfg = {
            "type":           "docker_container",
            "container_id":   c["id"],
            "container_name": c["name"],
            "lookback_s":     self._lookback_combo_docker_c.currentData(),
        }
        self.open_tab.emit(cfg, self._open_mode_c.get_mode())

    def _on_open_stack(self) -> None:
        items = self._stack_list.selectedItems()
        if not items:
            return
        s = items[0].data(Qt.ItemDataRole.UserRole)
        cfg = {
            "type":         "docker_compose",
            "project_name": s["name"],
            "lookback_s":   self._lookback_combo_docker_s.currentData(),
        }
        self.open_tab.emit(cfg, self._open_mode_s.get_mode())

    def _on_open_exec(self) -> None:
        items = self._exec_container_list.selectedItems()
        path  = self._exec_path_input.text().strip()
        if not items or not path:
            return
        c = items[0].data(Qt.ItemDataRole.UserRole)
        cfg = {
            "type":           "docker_exec_file",
            "container_id":   c["id"],
            "container_name": c["name"],
            "remote_path":    path,
            "tail_lines":     self._tail_spin_e.value(),
        }
        self.open_tab.emit(cfg, self._open_mode_e.get_mode())

    # ── Embedding contract (see ProviderPanel) ────────────────────────────────

    saveable = False

    def can_open(self) -> bool:
        tabs = getattr(self, "_tabs", None)
        if tabs is None:                                  # docker is not installed
            return True
        button = (self._open_btn_c, self._open_btn_s, self._open_btn_e)[tabs.currentIndex()]
        return button.isEnabled()

    def open_selected(self) -> None:
        tabs = getattr(self, "_tabs", None)
        if tabs is None:
            return
        (self._on_open_container, self._on_open_stack, self._on_open_exec)[tabs.currentIndex()]()

    def _embedded_hidden(self) -> list:
        return [self._title_lbl] if hasattr(self, "_title_lbl") else []
