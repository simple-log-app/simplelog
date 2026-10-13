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
import providers
from ui_theme import (
    _SVG_CHEVRON_LEFT,
    _SVG_REMOTE,
    C_ACCENT,
    C_BG,
    C_BORDER,
    C_CARD,
    C_ERR,
    C_INFO,
    C_MUTED,
    C_PANEL,
    C_SIDE,
    C_TEXT,
    _svg_icon,
)
from ui_widgets import _ghost_btn, _primary_btn

# ── Remote redesign: providers + AddConnectionDialog + RemoteHomePanel ────────

_RUNNING_WORKERS: set = set()   # workers of closed dialogs, kept alive until they finish


def _reap_worker(worker: QThread) -> None:
    worker.wait()   # it just emitted finished(): returns at once
    _RUNNING_WORKERS.discard(worker)


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
        self._add_header_lbl: QLabel | None = None
        self._embedded_panel: QWidget | None = None
        self._save_pending: bool = False
        self._ready_timer: QTimer | None = None
        self._restore_queue: list = []
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
        panel = self._embedded_panel
        if panel is None:
            return
        panel.release()
        # A connect/list worker may still be running: keep it referenced until it ends,
        # otherwise Qt aborts with "QThread destroyed while running".
        for value in list(vars(panel).values()):
            if isinstance(value, QThread) and value.isRunning():
                _RUNNING_WORKERS.add(value)
                value.finished.connect(lambda v=value: _reap_worker(v))

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

        for i, provider in enumerate(providers.PROVIDERS):
            grid_lay.addWidget(self._make_provider_card(provider), i // 3, i % 3)

        lay.addWidget(body)
        return page

    def _make_provider_card(self, provider: providers.Provider) -> QPushButton:
        pid, name, icon_char, color = provider.id, provider.name, provider.icon, provider.color
        btn = QPushButton()
        btn.setToolTip(provider.describe())
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

        provider = providers.get(provider_id)
        if provider is None:
            return
        name, icon_char, color = provider.name, provider.icon, provider.color

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

        self._build_embedded_step2(provider)

    # ── Navigation & actions ──────────────────────────────────────────────────

    def _go_step1(self) -> None:
        self._provider_id = ""
        self._fields = {}
        if self._ready_timer:
            self._ready_timer.stop()
            self._ready_timer = None
        self._embedded_panel = None
        self._save_pending = False
        self._restore_queue = []
        self.setMaximumHeight(16777215)
        self.adjustSize()
        self._stack.setCurrentIndex(0)

    def _on_open(self) -> None:
        if self._embedded_panel:
            self._save_pending = False
            self._embedded_panel.open_selected()

    def _on_save_open(self) -> None:
        if self._embedded_panel:
            self._save_pending = True
            self._embedded_panel.open_selected()

    # ── Step 2: the provider's own panel + a footer shared by all providers ───

    def _build_embedded_step2(self, provider: providers.Provider) -> None:
        """Embed the provider's panel, hide its own buttons, add the unified footer."""
        panel = provider.panel_class()(parent=self)
        panel.embed()
        self._embedded_panel = panel
        panel.open_tab.connect(self._on_embedded_panel_tab)

        # Reopening a saved connection: fill the form, reconnect, then re-select the
        # saved targets as the (asynchronous) lists get populated
        if self._prefill_profile is not None:
            panel.load_profile(self._prefill_profile)
            saved = self._prefill_profile.get("state", {})
            self._restore_queue = [
                (getattr(panel, a), saved[a]) for a in panel.restore_attrs if a in saved
            ]
            self._restore_ticks_left = 150  # give up after ~30 s once connected
            panel.connect_now()

        self.setFixedHeight(680)
        self._step2_layout.addWidget(panel, 1)

        saveable = panel.saveable

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet(
            "background: #17171f; border-top: 1px solid rgba(255,255,255,26);"
        )
        foot_lay = QVBoxLayout(footer)
        foot_lay.setContentsMargins(20, 14, 20, 14)
        foot_lay.setSpacing(8)

        if saveable:
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

        if saveable:
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

        # Poll the panel to enable the buttons as soon as something can be opened
        self._ready_timer = QTimer(self)
        self._ready_timer.setInterval(200)
        self._ready_timer.timeout.connect(self._sync_embedded_footer)
        self._ready_timer.start()

        self._stack.setCurrentIndex(1)

    def _pump_restore(self) -> None:
        """Re-apply saved widget values in order, waiting for async lists to load."""
        panel = self._embedded_panel
        if not self._restore_queue or panel is None or not panel.is_connected():
            return
        self._restore_ticks_left -= 1
        if self._restore_ticks_left < 0:
            self._restore_queue = []
            return
        while self._restore_queue and _restore_widget_state(*self._restore_queue[0]):
            self._restore_queue.pop(0)

    def _sync_embedded_footer(self) -> None:
        panel = self._embedded_panel
        if panel is None:
            return
        self._pump_restore()
        ready = panel.can_open()
        name_ok = bool(self._fields.get("name") and self._fields["name"].text().strip())
        if self._open_btn:
            self._open_btn.setEnabled(ready)
        if self._save_open_btn:
            self._save_open_btn.setEnabled(not self._is_existing and ready and name_ok)

    def _on_embedded_panel_tab(self, cfg: dict, mode: str) -> None:
        panel = self._embedded_panel
        if self._save_pending and panel is not None:
            name_edit = self._fields.get("name")
            name = name_edit.text().strip() if name_edit else ""
            if name and self._provider_id:
                data = panel.profile_data()
                data.update(panel.profile_extra(cfg))
                if panel.restore_attrs:
                    data["state"] = {
                        a: _widget_state(getattr(panel, a)) for a in panel.restore_attrs
                    }
                profiles_store.upsert(self._provider_id, name, data)
        self._save_pending = False
        self.tab_requested.emit(cfg, mode)
        self.done(QDialog.DialogCode.Accepted)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self._stack.currentIndex() == 1:
                self._go_step1()
            else:
                self.reject()
        else:
            super().keyPressEvent(event)


# ── RemoteHomePanel ────────────────────────────────────────────────────────────

class RemoteHomePanel(QWidget):
    """Sidebar panel: collapsible provider groups + new AddConnectionDialog."""

    tab_requested = pyqtSignal(dict, str)

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
        for svc in (p.id for p in providers.PROVIDERS):
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
        prov = providers.get(svc)
        if prov is None:
            return QWidget()
        name, icon_char, color = prov.name, prov.icon, prov.color

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
        prov = providers.get(svc)
        return profile.get(prov.subtitle_key, "") if prov and prov.subtitle_key else ""

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
