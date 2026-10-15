"""Shared widgets and helpers used by the panels and dialogs."""

from __future__ import annotations

from PyQt6.QtCore import (
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
)
from PyQt6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabBar,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from simplelog.core import i18n, profiles_store
from simplelog.ui.ui_theme import (
    _HAS_SVG,
    _SVG_CHEVRON_LEFT,
    _SVG_CLOSE_X,
    _SVG_FOLDER,
    _SVG_REMOTE,
    C_ACCENT,
    C_ACCENT_DIM,
    C_ACCENT_HOVER,
    C_ACCENT_PRESS,
    C_BG,
    C_BORDER,
    C_BORDER2,
    C_CARD,
    C_EL,
    C_ERR,
    C_HOVER,
    C_MUTED,
    C_MUTED2,
    C_ON_ACCENT,
    C_OVERLAY_SURFACE,
    C_PANEL,
    C_RAIL,
    C_TEXT,
    QByteArray,
    QSvgRenderer,
    _svg_icon,
    rgba,
)

# ── Combo box that ignores mouse wheel scrolling ──────────────────────────────

class NoScrollComboBox(QComboBox):
    """QComboBox that ignores wheel events so scrolling the page doesn't
    accidentally change the selected value when hovering over a closed combo."""

    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


# ── Tab bar with close-button-on-active-tab only ──────────────────────────────

class _TabCloseBtn(QPushButton):
    """14×14 × close button for tabs — turns red on hover."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setFlat(True)
        self.setStyleSheet(
            "QPushButton { background: transparent; border: none;"
            " border-radius: 3px; padding: 0; }"
            f"QPushButton:hover {{ background: {rgba(C_ERR, 25)}; }}"
        )
        self.retheme()

    def retheme(self) -> None:
        self.setIcon(_svg_icon(_SVG_CLOSE_X, C_MUTED, 10))
        self.setIconSize(QSize(10, 10))


class _SLTabBar(QTabBar):
    """QTabBar that shows the close button only on the active tab."""

    def tabInserted(self, index: int) -> None:  # noqa: N802
        super().tabInserted(index)
        tab_bar = self
        btn = _TabCloseBtn(self)

        def _req(_=False, _tb=tab_bar, _b=btn):
            for i in range(_tb.count()):
                if _tb.tabButton(i, QTabBar.ButtonPosition.RightSide) is _b:
                    _tb.tabCloseRequested.emit(i)
                    break

        btn.clicked.connect(_req)
        self.setTabButton(index, QTabBar.ButtonPosition.RightSide, btn)
        self._sync_close_buttons()

    def tabRemoved(self, index: int) -> None:  # noqa: N802
        super().tabRemoved(index)
        QTimer.singleShot(0, self._sync_close_buttons)

    def _sync_close_buttons(self) -> None:
        current = self.currentIndex()
        for i in range(self.count()):
            btn = self.tabButton(i, QTabBar.ButtonPosition.RightSide)
            if btn:
                btn.setVisible(i == current)


class _SLTabWidget(QTabWidget):
    """QTabWidget using _SLTabBar so the × only appears on the active tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sl_bar = _SLTabBar(self)
        self.setTabBar(self._sl_bar)
        self.currentChanged.connect(lambda _: self._sl_bar._sync_close_buttons())


# ── Sidebar edge toggle buttons ────────────────────────────────────────────────

class _SidebarEdgeBtn(QPushButton):
    """20×40 floating edge tab that collapses/expands a sidebar panel."""

    def __init__(self, side: str, parent=None):
        super().__init__(parent)
        self._side = side  # 'left' or 'right'
        self._svg = _SVG_CHEVRON_LEFT
        self._hovered = False
        self.setFixedSize(20, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def set_svg(self, svg: str) -> None:
        self._svg = svg
        self._apply_style()

    def _apply_style(self) -> None:
        bg = C_ACCENT_DIM if self._hovered else C_CARD
        color = C_ACCENT if self._hovered else C_MUTED
        if self._side == "left":
            border_r = (
                "border-top-left-radius: 0px; border-bottom-left-radius: 0px;"
                " border-top-right-radius: 6px; border-bottom-right-radius: 6px;"
            )
            border_css = f"border: 1px solid {C_BORDER}; border-left: none;"
        else:
            border_r = (
                "border-top-left-radius: 6px; border-bottom-left-radius: 6px;"
                " border-top-right-radius: 0px; border-bottom-right-radius: 0px;"
            )
            border_css = f"border: 1px solid {C_BORDER}; border-right: none;"
        self.setStyleSheet(
            f"QPushButton {{ background: {bg}; {border_css} {border_r} padding: 0; }}"
        )
        self.setIcon(_svg_icon(self._svg, color, 10))
        self.setIconSize(QSize(10, 10))

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._apply_style()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._apply_style()
        super().leaveEvent(event)


# ── NavButton ──────────────────────────────────────────────────────────────────

class NavButton(QAbstractButton):
    """Nav rail icon button: 34×34 tile centred in the 48px rail, accent bar when checked."""

    def __init__(self, svg_template: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(48, 34)
        self.setToolTip(tooltip)
        self._svg_template = svg_template
        self._renderer_checked: QSvgRenderer | None = None
        self._renderer_unchecked: QSvgRenderer | None = None
        self.retheme()

    def retheme(self) -> None:
        if _HAS_SVG:
            self._renderer_checked   = self._make_renderer(C_TEXT)
            self._renderer_unchecked = self._make_renderer(C_MUTED)
        self.update()

    def _make_renderer(self, color: str) -> QSvgRenderer:
        svg = self._svg_template.replace("{color}", color)
        renderer = QSvgRenderer()
        renderer.load(QByteArray(svg.encode()))
        return renderer

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        tile_x = (w - 34) // 2

        # Tile when checked / hovered, accent bar on the rail's left edge when checked
        if self.isChecked() or self.underMouse():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(C_EL)))
            path = QPainterPath()
            path.addRoundedRect(tile_x, 0, 34, h, 6, 6)
            p.drawPath(path)
        if self.isChecked():
            p.setBrush(QBrush(QColor(C_ACCENT)))
            p.drawRect(0, 8, 2, h - 16)

        # Icon
        icon_size = 17
        ix = (w - icon_size) // 2
        iy = (h - icon_size) // 2
        try:
            if _HAS_SVG:
                renderer = self._renderer_checked if self.isChecked() else self._renderer_unchecked
                if renderer and renderer.isValid():
                    renderer.render(p, QRectF(ix, iy, icon_size, icon_size))
                    return

            # Fallback: draw coloured square placeholder
            color = C_TEXT if self.isChecked() else C_MUTED
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(color)))
            p.drawRoundedRect(ix, iy, icon_size, icon_size, 4, 4)
        finally:
            p.end()

    def enterEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(event)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(48, 34)


# ── NavRail ────────────────────────────────────────────────────────────────────

class NavRail(QWidget):
    """48px left navigation rail."""

    index_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(48)
        self.setStyleSheet(
            f"background: {C_RAIL};"
            f"border-right: 1px solid {C_BORDER};"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(4)

        # Buttons
        self._buttons: list[NavButton] = []

        self._btn_remote = NavButton(_SVG_REMOTE, i18n.tr("remote_title"))
        self._btn_file   = NavButton(_SVG_FOLDER, i18n.tr("nav_open_file"))

        for btn in (self._btn_remote, self._btn_file):
            btn.clicked.connect(self._on_button_clicked)
            btn_row = QHBoxLayout()
            btn_row.setContentsMargins(0, 0, 0, 0)
            btn_row.addStretch()
            btn_row.addWidget(btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)
            self._buttons.append(btn)

        layout.addStretch()

        # Select first by default
        self._btn_remote.setChecked(True)

    def _on_button_clicked(self):
        sender = self.sender()
        for i, btn in enumerate(self._buttons):
            btn.setChecked(btn is sender)
        idx = self._buttons.index(sender)
        self.index_changed.emit(idx)


# ── make_card helper ───────────────────────────────────────────────────────────

def make_card(title: str | None = None, help_key: str | None = None) -> tuple[QFrame, QVBoxLayout, QLabel | None]:
    """Return (frame, layout, title_label | None) for a sidebar card."""
    frame = QFrame()
    frame.setObjectName("sl_card")
    # Scoped by name: a bare "QFrame {…}" would also box every label inside the card
    frame.setStyleSheet(
        f"QFrame#sl_card {{ background: {C_CARD}; border: 1px solid {C_BORDER};"
        f" border-radius: 6px; }}"
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(6)
    title_label: QLabel | None = None
    if title:
        title_label = QLabel(title.upper())
        title_label.setStyleSheet(
            f"color: {C_MUTED}; font-size: 10px; font-weight: 600;"
            " border: none; background: transparent; margin-bottom: 2px;"
        )
        _letter_spaced(title_label, 0.8)
        if help_key:
            hrow = QHBoxLayout()
            hrow.setContentsMargins(0, 0, 0, 0)
            hrow.setSpacing(4)
            hrow.addWidget(title_label)
            hrow.addStretch()
            help_btn = QPushButton("?")
            help_btn.setFixedSize(22, 22)
            help_btn.setToolTip(i18n.tr("help_dialog_title"))
            help_btn.setStyleSheet(
                f"QPushButton {{ background: {C_ACCENT}; color: {C_ON_ACCENT};"
                " border: none; border-radius: 11px;"
                " font-size: 13px; font-weight: bold; padding: 0; }"
                f"QPushButton:hover {{ background: {C_ACCENT_HOVER}; }}"
                f"QPushButton:pressed {{ background: {C_ACCENT_PRESS}; }}"
            )
            _key = help_key
            _frame = frame
            help_btn.clicked.connect(lambda _=False, k=_key, p=_frame: _HelpDialog(i18n.tr(k), p).exec())
            hrow.addWidget(help_btn)
            layout.addLayout(hrow)
        else:
            layout.addWidget(title_label)
    return frame, layout, title_label


# ── Primary button helper ─────────────────────────────────────────────────────

def _primary_btn(text: str = "", height: int = 28) -> QPushButton:
    """Create a styled primary (accent-coloured) button."""
    btn = QPushButton(text)
    btn.setObjectName("primary")
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {C_ACCENT};
            color: {C_ON_ACCENT};
            border: none;
            border-radius: 5px;
            min-height: {height}px;
            max-height: {height}px;
            padding: 0 12px;
            font-size: 12px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {C_ACCENT_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {C_ACCENT_PRESS};
        }}
        QPushButton:disabled {{
            background-color: {C_ACCENT_DIM};
            color: {C_MUTED};
        }}
    """)
    return btn


def _ghost_btn(text: str = "") -> QPushButton:
    """Create a ghost (outline) button."""
    btn = QPushButton(text)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            color: {C_TEXT};
            border: 1px solid {C_BORDER2};
            border-radius: 5px;
            min-height: 28px;
            max-height: 28px;
            padding: 0 12px;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background: {C_EL};
            border-color: {C_MUTED2};
        }}
        QPushButton:disabled {{
            color: {C_MUTED2};
            border-color: {C_BORDER};
        }}
    """)
    return btn


class _HelpDialog(QDialog):
    def __init__(self, html: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("help_dialog_title"))
        self.setMinimumSize(480, 440)
        self.setStyleSheet(f"background: {C_PANEL};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        browser = QTextBrowser()
        browser.setHtml(html)
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet(
            f"QTextBrowser {{ background: {C_CARD}; color: {C_TEXT};"
            f" border: 1px solid {C_BORDER}; border-radius: 8px;"
            f" padding: 12px; font-size: 12px; }}"
        )
        lay.addWidget(browser)

        close_btn = _primary_btn(i18n.tr("help_dialog_close"))
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close_btn)
        lay.addLayout(row)


class _ProfileBar(QWidget):
    """Compact saved-profile row: [combo ▾] [Load] [✕]
    Hidden automatically when no profiles are saved.
    Pass wrapper= to also show/hide an outer container."""

    profile_loaded = pyqtSignal(dict)

    def __init__(self, service: str, wrapper: QWidget | None = None, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._wrapper = wrapper
        self._suppressed = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._combo = NoScrollComboBox()
        self._combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._combo.setMinimumWidth(100)
        self._combo.setStyleSheet(
            f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f"border-radius: 4px; padding: 3px 6px; font-size: 11px;"
        )

        self._load_btn = QPushButton(i18n.tr("remote_open"))
        self._load_btn.setFixedWidth(48)
        self._load_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_ACCENT}; border: 1px solid {C_ACCENT};"
            f"border-radius: 4px; padding: 3px 6px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {rgba(C_ACCENT, 20)}; }}"
        )
        self._load_btn.clicked.connect(self._on_load)

        self._del_btn = QPushButton("✕")
        self._del_btn.setFixedWidth(28)
        self._del_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_ERR}; border: 1px solid {C_ERR};"
            f"border-radius: 4px; padding: 3px 4px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {rgba(C_ERR, 20)}; }}"
        )
        self._del_btn.clicked.connect(self._on_delete)

        lay.addWidget(self._combo, 1)
        lay.addWidget(self._load_btn)
        lay.addWidget(self._del_btn)

        self.reload()

    def reload(self) -> None:
        self._combo.clear()
        for p in profiles_store.load_all(self._service):
            self._combo.addItem(p["name"], userData=p)
        vis = self._combo.count() > 0 and not self._suppressed
        # A parentless widget told to show becomes a flashing top-level window: while the
        # panel is still being built, only hide (showing happens once it is parented).
        for w in (self, self._wrapper):
            if w is not None and (not vis or w.parent() is not None):
                w.setVisible(vis)

    def suppress(self) -> None:
        """Hide the bar for good (the dialog hosting the panel lists saved connections)."""
        self._suppressed = True
        self.reload()

    def _on_load(self) -> None:
        p = self._combo.currentData()
        if p:
            self.profile_loaded.emit(p)

    def _on_delete(self) -> None:
        p = self._combo.currentData()
        if not p:
            return
        profiles_store.delete(self._service, p["name"])
        self.reload()


# ── Open-mode segmented button widget ─────────────────────────────────────────

class OpenModeWidget(QWidget):
    """Horizontal segmented control: new tab / vertical split / horizontal split."""

    _MODES = ("tab", "vertical", "horizontal")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 4, 0, 0)
        vbox.setSpacing(6)

        self._lbl = QLabel()
        self._lbl.setStyleSheet(
            f"color: {C_MUTED}; font-size: 10px; font-weight: 500;"
            " background: transparent; border: none;"
        )
        _letter_spaced(self._lbl, 0.6)
        vbox.addWidget(self._lbl)

        # Segmented button container: 3 equal cells split by 1px separators
        seg = QFrame()
        seg.setFixedHeight(26)
        seg.setStyleSheet(
            f"QFrame {{ background: {C_BG}; border: 1px solid {C_BORDER2};"
            f" border-radius: 5px; }}"
        )
        seg_layout = QHBoxLayout(seg)
        seg_layout.setContentsMargins(0, 0, 0, 0)
        seg_layout.setSpacing(0)

        self._grp = QButtonGroup(self)
        self._btns: dict[str, QPushButton] = {}
        n = len(self._MODES)
        for idx, mode in enumerate(self._MODES):
            btn = QPushButton()
            btn.setCheckable(True)
            if idx == 0:
                r = "border-top-left-radius: 4px; border-bottom-left-radius: 4px;"
            elif idx == n - 1:
                r = "border-top-right-radius: 4px; border-bottom-right-radius: 4px;"
            else:
                r = ""
            sep = f"border-left: 1px solid {C_BORDER2};" if idx else ""
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    {sep}
                    color: {C_MUTED};
                    font-size: 11px;
                    padding: 0 6px;
                    min-height: 24px;
                    max-height: 24px;
                    border-radius: 0;
                    {r}
                }}
                QPushButton:checked {{
                    background: {C_ACCENT_DIM};
                    color: {C_ACCENT};
                    font-weight: 600;
                }}
                QPushButton:hover:!checked {{
                    background: {C_HOVER};
                    color: {C_TEXT};
                }}
                QPushButton:disabled {{
                    background: transparent;
                    color: {C_MUTED2};
                }}
            """)
            self._grp.addButton(btn, idx)
            seg_layout.addWidget(btn, 1)
            self._btns[mode] = btn

        self._btns["tab"].setChecked(True)
        vbox.addWidget(seg)

        _key = id(self)
        i18n.register(_key, self.retranslate)
        self.destroyed.connect(lambda _=None, k=_key: i18n.unregister(k))
        self.retranslate()

    def set_split_enabled(self, enabled: bool) -> None:
        """Splitting needs a log tab to split: without one only "New tab" is offered."""
        for mode in ("vertical", "horizontal"):
            self._btns[mode].setEnabled(enabled)
            self._btns[mode].setToolTip("" if enabled else i18n.tr("open_mode_no_split"))
        if not enabled:
            self._btns["tab"].setChecked(True)

    def get_mode(self) -> str:
        for mode, btn in self._btns.items():
            if btn.isChecked():
                return mode
        return "tab"

    def retranslate(self) -> None:
        self._lbl.setText(i18n.tr("open_as").upper())
        self._btns["tab"].setText(i18n.tr("open_mode_tab"))
        self._btns["vertical"].setText(i18n.tr("open_mode_vertical"))
        self._btns["horizontal"].setText(i18n.tr("open_mode_horizontal"))


# ── Tiny helpers ──────────────────────────────────────────────────────────────

def _letter_spaced(label: QLabel, px: float) -> None:
    """Add *px* of letter-spacing to *label* (not expressible in Qt stylesheets)."""
    font = label.font()
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, px)
    label.setFont(font)


class _FieldLabel(QLabel):
    """Caption shown in capitals whatever text it is given (retranslation included)."""

    def __init__(self, text: str = "") -> None:
        super().__init__(text.upper())

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(text.upper())


def _field_label(text: str) -> QLabel:
    """Small field caption label."""
    lbl = _FieldLabel(text)
    lbl.setStyleSheet(
        f"color: {C_MUTED}; font-size: 10px; font-weight: 500;"
        " background: transparent; border: none;"
    )
    _letter_spaced(lbl, 0.6)
    return lbl


def _lookback_combo(default_idx: int = 1) -> QComboBox:
    """Standardized time-range QComboBox (same options as CloudWatch)."""
    combo = NoScrollComboBox()
    for label, secs in [
        ("15 min", 900), ("1 h", 3600), ("3 h", 10800),
        ("6 h", 21600), ("12 h", 43200), ("1 day", 86400), ("7 days", 604800),
    ]:
        combo.addItem(label, secs)
    combo.setCurrentIndex(default_idx)
    return combo


class MergeTabsDialog(QDialog):
    """Pick (at least two) open logs to show together, interleaved by time."""

    def __init__(self, labels: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("merge_title"))
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setStyleSheet(
            f"QDialog {{ background: {C_OVERLAY_SURFACE}; color: {C_TEXT};"
            f" border: 1px solid {C_BORDER2}; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        hint = QLabel(i18n.tr("merge_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {C_MUTED}; font-size: 11px; background: transparent;")
        lay.addWidget(hint)

        self._list = QListWidget()
        for label in labels:
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._list.addItem(item)
        self._list.itemChanged.connect(self._sync)
        lay.addWidget(self._list)

        row = QHBoxLayout()
        row.addStretch()
        cancel = _ghost_btn(i18n.tr("remote_cancel"))
        cancel.clicked.connect(self.reject)
        self._ok = _primary_btn(i18n.tr("merge_action"))
        self._ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(self._ok)
        lay.addLayout(row)
        self._sync()

    def _sync(self, *_args) -> None:
        self._ok.setEnabled(len(self.chosen()) >= 2)

    def chosen(self) -> list[int]:
        """Indexes (into the labels given) of the logs ticked."""
        return [i for i in range(self._list.count())
                if self._list.item(i).checkState() == Qt.CheckState.Checked]
