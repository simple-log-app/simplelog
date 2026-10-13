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
    QPushButton,
    QTabBar,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import i18n
import profiles_store
from ui_theme import (
    _SVG_CHEVRON_LEFT,
    _SVG_CLOSE_X,
    _SVG_FOLDER,
    _SVG_REMOTE,
    C_ACCENT,
    C_ACCENT_DIM,
    C_BG,
    C_BORDER,
    C_CARD,
    C_ERR,
    C_MUTED,
    C_PANEL,
    C_RAIL,
    C_TEXT,
    _svg_icon,
)

# ── Combo box that ignores mouse wheel scrolling ──────────────────────────────

class NoScrollComboBox(QComboBox):
    """QComboBox that ignores wheel events so scrolling the page doesn't
    accidentally change the selected value when hovering over a closed combo."""

    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()

try:
    from PyQt6.QtCore import QByteArray
    from PyQt6.QtSvg import QSvgRenderer
    _HAS_SVG = True
except ImportError:
    _HAS_SVG = False


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
            "QPushButton:hover { background: rgba(240,120,120,25); }"
        )
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
    """40×40 nav rail icon button with rounded-rect highlight when checked."""

    def __init__(self, svg_template: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(40, 40)
        self.setToolTip(tooltip)
        self._svg_template = svg_template
        self._renderer_checked: QSvgRenderer | None = None
        self._renderer_unchecked: QSvgRenderer | None = None
        if _HAS_SVG:
            self._renderer_checked   = self._make_renderer(C_ACCENT)
            self._renderer_unchecked = self._make_renderer(C_MUTED)

    def _make_renderer(self, color: str) -> QSvgRenderer:
        svg = self._svg_template.replace("{color}", color)
        renderer = QSvgRenderer()
        renderer.load(QByteArray(svg.encode()))
        return renderer

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # Rounded-rect background when checked
        if self.isChecked():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(91, 143, 255, 38)))  # C_ACCENT_DIM
            path = QPainterPath()
            path.addRoundedRect(0, 0, w, h, 8, 8)
            p.drawPath(path)
        elif self.underMouse():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(255, 255, 255, 12)))
            path = QPainterPath()
            path.addRoundedRect(0, 0, w, h, 8, 8)
            p.drawPath(path)

        # Icon
        icon_size = 18
        ix = (w - icon_size) // 2
        iy = (h - icon_size) // 2
        try:
            if _HAS_SVG:
                renderer = self._renderer_checked if self.isChecked() else self._renderer_unchecked
                if renderer and renderer.isValid():
                    renderer.render(p, QRectF(ix, iy, icon_size, icon_size))
                    return

            # Fallback: draw coloured square placeholder
            color = C_ACCENT if self.isChecked() else C_MUTED
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
        return QSize(40, 40)


# ── NavRail ────────────────────────────────────────────────────────────────────

# ── NavRail ────────────────────────────────────────────────────────────────────

class NavRail(QWidget):
    """52px left navigation rail."""

    index_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(52)
        self.setStyleSheet(
            f"background: {C_RAIL};"
            f"border-right: 1px solid {C_BORDER};"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(2)

        # Logo
        logo = QLabel("SL")
        logo.setFixedSize(32, 32)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            f"background: {C_ACCENT}; color: #000; font-weight: 800;"
            "font-size: 12px; border-radius: 8px;"
        )
        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(0, 0, 0, 0)
        logo_row.addStretch()
        logo_row.addWidget(logo)
        logo_row.addStretch()
        layout.addLayout(logo_row)
        layout.addSpacing(10)

        # Divider
        div = QFrame()
        div.setFixedSize(28, 1)
        div.setStyleSheet(f"background: {C_BORDER}; border: none;")
        div_row = QHBoxLayout()
        div_row.setContentsMargins(0, 0, 0, 0)
        div_row.addStretch()
        div_row.addWidget(div)
        div_row.addStretch()
        layout.addLayout(div_row)
        layout.addSpacing(6)

        # Buttons
        self._buttons: list[NavButton] = []

        self._btn_remote = NavButton(_SVG_REMOTE, i18n.tr("remote_title"))
        self._btn_file   = NavButton(_SVG_FOLDER, "Open log file")

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
    frame.setStyleSheet(
        f"QFrame {{ background: {C_CARD}; border: 1px solid rgba(255,255,255,18);"
        f" border-radius: 10px; }}"
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(6)
    title_label: QLabel | None = None
    if title:
        title_label = QLabel(title.upper())
        title_label.setStyleSheet(
            f"color: {C_ACCENT}; font-size: 10px; font-weight: 700;"
            " border: none; background: transparent; margin-bottom: 2px;"
        )
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
                "QPushButton { background: #5b8fff; color: #ffffff;"
                " border: none; border-radius: 11px;"
                " font-size: 13px; font-weight: bold; padding: 0; }"
                "QPushButton:hover { background: #7aa3ff; }"
                "QPushButton:pressed { background: #4a7aee; }"
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

def _primary_btn(text: str = "") -> QPushButton:
    """Create a styled primary (accent-coloured) button."""
    btn = QPushButton(text)
    btn.setObjectName("primary")
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {C_ACCENT};
            color: #000000;
            border: none;
            border-radius: 6px;
            padding: 7px 14px;
            font-size: 12px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: #7aa3ff;
        }}
        QPushButton:pressed {{
            background-color: #4a7aee;
        }}
        QPushButton:disabled {{
            background-color: rgba(91,143,255,38);
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
            border: 1px solid rgba(255,255,255,35);
            border-radius: 6px;
            padding: 7px 14px;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background: rgba(255,255,255,10);
            border-color: rgba(255,255,255,60);
        }}
        QPushButton:disabled {{
            color: {C_MUTED};
            border-color: rgba(255,255,255,15);
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
            f"QPushButton:hover {{ background: rgba(91,143,255,20); }}"
        )
        self._load_btn.clicked.connect(self._on_load)

        self._del_btn = QPushButton("✕")
        self._del_btn.setFixedWidth(28)
        self._del_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_ERR}; border: 1px solid {C_ERR};"
            f"border-radius: 4px; padding: 3px 4px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: rgba(240,120,120,20); }}"
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
        vis = self._combo.count() > 0
        self.setVisible(vis)
        if self._wrapper is not None:
            self._wrapper.setVisible(vis)

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
    """Segmented button group: new tab / vertical split / horizontal split."""

    _MODES = ("tab", "vertical", "horizontal")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 4, 0, 0)
        vbox.setSpacing(6)

        self._lbl = QLabel()
        self._lbl.setStyleSheet(
            f"color: {C_MUTED}; font-size: 11px; font-weight: 600;"
            " background: transparent; border: none;"
        )
        vbox.addWidget(self._lbl)

        # Segmented button container
        seg = QFrame()
        seg.setStyleSheet(
            f"QFrame {{ background: {C_BG}; border: 1px solid rgba(255,255,255,18);"
            f" border-radius: 6px; }}"
        )
        seg_layout = QVBoxLayout(seg)
        seg_layout.setContentsMargins(0, 0, 0, 0)
        seg_layout.setSpacing(0)

        self._grp = QButtonGroup(self)
        self._btns: dict[str, QPushButton] = {}
        n = len(self._MODES)
        for idx, mode in enumerate(self._MODES):
            btn = QPushButton()
            btn.setCheckable(True)
            if idx == 0:
                r = ("border-top-left-radius: 5px; border-top-right-radius: 5px;"
                     " border-bottom-left-radius: 3px; border-bottom-right-radius: 3px;")
            elif idx == n - 1:
                r = ("border-top-left-radius: 3px; border-top-right-radius: 3px;"
                     " border-bottom-left-radius: 5px; border-bottom-right-radius: 5px;")
            else:
                r = "border-radius: 3px;"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    color: {C_MUTED};
                    font-size: 12px;
                    padding: 6px 10px;
                    text-align: left;
                    {r}
                }}
                QPushButton:checked {{
                    background: rgba(91,143,255,38);
                    color: {C_ACCENT};
                    font-weight: 600;
                }}
                QPushButton:hover:!checked {{
                    background: rgba(255,255,255,10);
                    color: {C_TEXT};
                }}
            """)
            self._grp.addButton(btn, idx)
            seg_layout.addWidget(btn)
            self._btns[mode] = btn

        self._btns["tab"].setChecked(True)
        vbox.addWidget(seg)

        _key = id(self)
        i18n.register(_key, self.retranslate)
        self.destroyed.connect(lambda _=None, k=_key: i18n.unregister(k))
        self.retranslate()

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

def _field_label(text: str) -> QLabel:
    """Small field caption label."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {C_MUTED}; font-size: 11px; background: transparent; border: none;"
    )
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
