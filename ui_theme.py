"""Theme: SVG icons, colour constants and the global stylesheet."""

from __future__ import annotations

from PyQt6.QtCore import (
    Qt,
)
from PyQt6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPalette,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
)

try:
    from PyQt6.QtCore import QByteArray
    from PyQt6.QtSvg import QSvgRenderer
    _HAS_SVG = True
except ImportError:
    _HAS_SVG = False


_SVG_CLOUD = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M19.35 10.04A7.49 7.49 0 0 0 12 4'
    'C9.11 4 6.6 5.64 5.35 8.04A5.994 5.994 0 0 0 0 14'
    'c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5'
    ' 0-2.64-2.05-4.78-4.65-4.96z"/>'
    "</svg>"
)

_SVG_FOLDER = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M20 6h-8l-2-2H4c-1.1 0-1.99.9-1.99 2'
    'L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2z'
    'm0 12H4V8h16v10z"/>'
    "</svg>"
)

_SVG_SSH = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16'
    'c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zM4 18V8h16v10H4zm2-3h4v-2H6v2z'
    'm6 0h4v-2h-4v2zM6 11h2V9H6v2zm4 0h4V9h-4v2zm6 0h2V9h-2v2z"/>'
    "</svg>"
)

_SVG_DOCKER = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M13.98 8H10V6h3.98V8zm-5.98 0H4.02V6H8V8z'
    'm5.98 2.03H10V8.03h3.98v2zM8 10.03H4.02V8.03H8v2z'
    'm5.98 2H10v-2h3.98v2zM8 12.03H4.02v-2H8v2z'
    'm10 2.03h-4V12h4V14zm4 0h-3.98v2H18v-2z'
    'm3.18 2.5C20.76 6 20 4.53 20 4.53s-1 .47-1.82 1.97'
    'c-.56.99-.18 2.5-.18 2.5H23s.5-1.5-.82-2.5z'
    'M2 14c0 2.21 2.69 4 6 4h8c3.31 0 6-1.79 6-4H2z"/>'
    "</svg>"
)

_SVG_VERCEL = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M12 2L2 19.5h20L12 2z"/>'
    "</svg>"
)

_SVG_GCP = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z'
    'm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93z'
    'm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2'
    'c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>'
    "</svg>"
)

_SVG_AZURE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M13.05 4.24L6.56 18.05l14.36.02-1.52-1.46-9.1-1.84 5.2-4.62-3.45-5.91z'
    'M11.4 6.22l-7.88 12.1 2.57-.01 5.29-8.46-.34-1.24 .36-2.39z"/>'
    "</svg>"
)

_SVG_LOKI = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M4 5h2v14H4V5zM8 6h12v2H8V6zM8 11h9v2H8v-2zM8 16h12v2H8v-2z"/>'
    "</svg>"
)

_SVG_DATADOG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M12 2l8.5 4.9v10.2L12 22l-8.5-4.9V6.9L12 2z"/>'
    "</svg>"
)

_SVG_ELASTIC = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z'
    'm1 15H7v-2h6v2zm4-4H7V9h10v2z"/>'
    "</svg>"
)

_SVG_RAILWAY = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M4 16h16v2H4v-2zM4 6h16v2H4V6zm4 5h8v2H8v-2z'
    'M6 19l-2 3h2l1-1.5L8 22h2l-2-3H6zm10 0l-2 3h2l1-1.5 1 1.5h2l-2-3h-2z"/>'
    "</svg>"
)

_SVG_FLYIO = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M12 2C8.13 2 5 5.13 5 9c0 2.74 1.54 5.12 3.82 6.38'
    'L8 20h2l.5-3h3l.5 3h2l-.82-4.62C17.46 14.12 19 11.74 19 9c0-3.87-3.13-7-7-7z'
    'm0 2c2.76 0 5 2.24 5 5s-2.24 5-5 5-5-2.24-5-5 2.24-5 5-5z"/>'
    "</svg>"
)

_SVG_KUBERNETES = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M12 2l9 4.5v9L12 20l-9-4.5v-9L12 2zm0 2.18L5 7.64v8.72'
    'L12 19.82l7-3.46V7.64L12 4.18zm-1 3.32h2v5l-1 1-1-1V7.5zm0 7h2v2h-2v-2z"/>'
    "</svg>"
)

_SVG_CLOUDFLARE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M18.92 10.36c-.28-3-2.79-5.36-5.89-5.36'
    '-2.33 0-4.36 1.37-5.35 3.38-.44-.22-.93-.34-1.45-.34-1.79 0-3.23 1.45-3.23 3.24'
    ' 0 .18.02.36.05.53C1.84 12.51 1 13.72 1 15.15 1 17.01 2.49 18.5 4.35 18.5h14.3'
    'c1.86 0 3.35-1.49 3.35-3.35 0-1.77-1.38-3.22-3.13-3.33l.05-.46z"/>'
    "</svg>"
)

_SVG_REMOTE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2'
    'C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0z'
    'm-4-4 2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/>'
    "</svg>"
)

_SVG_TRASH = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12z'
    'M8 9h8v10H8V9zm7.5-5-1-1h-5l-1 1H5v2h14V4z"/>'
    "</svg>"
)

_SVG_STOP_SQ = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<rect fill="{color}" x="6" y="6" width="12" height="12" rx="2" ry="2"/>'
    "</svg>"
)

_SVG_CLOSE_X = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path stroke="{color}" stroke-width="2.5" stroke-linecap="round"'
    ' fill="none" d="M5 5L19 19M19 5L5 19"/>'
    "</svg>"
)

_SVG_CHEVRON_LEFT = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
    '<path fill="{color}" d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/>'
    "</svg>"
)

_SVG_CHEVRON_RIGHT = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
    '<path fill="{color}" d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/>'
    "</svg>"
)


def _svg_icon(svg_tmpl: str, color: str, size: int = 16) -> QIcon:
    """Render an SVG template (with {color} placeholder) to a QIcon."""
    if not _HAS_SVG:
        return QIcon()
    svg = svg_tmpl.replace("{color}", color)
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    return QIcon(pm)


# ── Colour constants ───────────────────────────────────────────────────────────

C_BG         = "#0d0d10"
C_RAIL       = "#080810"
C_SIDE       = "#111116"
C_PANEL      = "#14141a"
C_CARD       = "#1a1a24"
C_STATUS     = "#090910"
C_BORDER     = "rgba(255,255,255,18)"
C_ACCENT     = "#5b8fff"
C_ACCENT_DIM = "rgba(91,143,255,38)"
C_TEXT       = "#d4d4e0"
C_MUTED      = "#52526a"
C_SEL_BG     = "rgba(91,143,255,31)"
C_ERR        = "#f07878"
C_WARN       = "#f0c060"
C_INFO       = "#56cf80"
C_DEBUG      = "#5b8fff"
C_TRACE      = "#b07cf0"
C_TS         = "#50c8dc"

C_DIVIDER  = C_BORDER  # alias used in painter pens


# ── apply_style ────────────────────────────────────────────────────────────────

def apply_style(app: QApplication) -> None:
    """Apply Material Design dark palette and global stylesheet."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(C_BG))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(C_TEXT))
    palette.setColor(QPalette.ColorRole.Base,            QColor(C_CARD))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(C_BG))
    palette.setColor(QPalette.ColorRole.Text,            QColor(C_TEXT))
    palette.setColor(QPalette.ColorRole.Button,          QColor(C_CARD))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(C_TEXT))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(C_ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(C_MUTED))
    palette.setColor(QPalette.ColorRole.BrightText,      QColor(C_ERR))
    app.setPalette(palette)

    app.setStyleSheet(f"""
        QWidget {{
            background-color: {C_BG};
            color: {C_TEXT};
            font-family: "Inter", sans-serif;
            font-size: 12px;
        }}
        QLineEdit, QComboBox, QSpinBox {{
            background: {C_BG};
            border: 1px solid rgba(255,255,255,26);
            border-radius: 5px;
            padding: 6px 10px;
            color: {C_TEXT};
            min-height: 20px;
            font-size: 12px;
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
            border-color: {C_ACCENT};
            border-width: 1px;
        }}
        QPushButton {{
            background-color: transparent;
            border: 1px solid {C_BORDER};
            border-radius: 6px;
            padding: 7px 14px;
            color: {C_MUTED};
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: rgba(255,255,255,10);
            color: {C_TEXT};
        }}
        QPushButton#primary {{
            background-color: {C_ACCENT};
            color: #000000;
            border: none;
            font-weight: bold;
        }}
        QPushButton#primary:hover {{
            background-color: #7aa3ff;
        }}
        QPushButton#danger {{
            color: {C_ERR};
            border-color: rgba(240,120,120,77);
            background: transparent;
        }}
        QPushButton#danger:hover {{
            background: rgba(240,120,120,20);
        }}
        QPushButton:disabled {{
            background-color: rgba(91,143,255,38);
            color: {C_MUTED};
            border: none;
        }}
        QListWidget {{
            background: {C_BG};
            border: 1px solid {C_BORDER};
            border-radius: 6px;
            font-family: "JetBrains Mono", monospace;
            font-size: 11px;
        }}
        QListWidget::item {{
            padding: 6px 10px;
            border-radius: 4px;
        }}
        QListWidget::item:selected {{
            background: {C_SEL_BG};
            color: {C_ACCENT};
        }}
        QListWidget::item:hover {{
            background: rgba(255,255,255,10);
        }}
        QTabWidget::pane {{
            border: none;
        }}
        QTabBar::tab {{
            background: {C_PANEL};
            border: none;
            border-right: 1px solid {C_BORDER};
            padding: 0 14px;
            min-height: 38px;
            color: {C_MUTED};
            font-size: 12px;
        }}
        QTabBar::tab:selected {{
            background: {C_BG};
            color: {C_TEXT};
            border-top: 2px solid {C_ACCENT};
        }}
        QTabBar::tab:hover:!selected {{
            color: {C_TEXT};
            background: rgba(255,255,255,5);
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QComboBox QAbstractItemView {{
            background: {C_CARD};
            border: 1px solid {C_BORDER};
            selection-background-color: {C_SEL_BG};
            selection-color: {C_ACCENT};
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 6px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(255,255,255,31);
            border-radius: 3px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba(91,143,255,128);
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 6px;
        }}
        QScrollBar::handle:horizontal {{
            background: rgba(255,255,255,31);
            border-radius: 3px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: rgba(91,143,255,128);
        }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
        QCheckBox {{
            spacing: 6px;
            color: {C_MUTED};
            font-size: 11px;
        }}
        QCheckBox::indicator {{
            width: 14px;
            height: 14px;
            border: 1px solid {C_BORDER};
            border-radius: 3px;
            background: {C_BG};
        }}
        QCheckBox::indicator:checked {{
            background: {C_ACCENT};
            border-color: {C_ACCENT};
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QToolTip {{
            background: {C_CARD};
            color: {C_TEXT};
            border: 1px solid {C_BORDER};
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 11px;
        }}
        QStatusBar {{
            background: {C_STATUS};
            border-top: 1px solid {C_BORDER};
            color: {C_MUTED};
            font-family: "JetBrains Mono", monospace;
            font-size: 11px;
        }}
        QMenuBar {{
            background: {C_RAIL};
            color: {C_TEXT};
            border-bottom: 1px solid {C_BORDER};
            font-size: 12px;
            padding: 2px 4px;
        }}
        QMenuBar::item {{
            background: transparent;
            padding: 5px 12px;
            border-radius: 4px;
        }}
        QMenuBar::item:selected {{
            background: rgba(255,255,255,15);
            color: {C_ACCENT};
        }}
        QMenu {{
            background: {C_CARD};
            border: 1px solid {C_BORDER};
            border-radius: 8px;
            padding: 4px 0;
            font-size: 12px;
        }}
        QMenu::item {{
            padding: 8px 24px 8px 16px;
            color: {C_TEXT};
        }}
        QMenu::item:selected {{
            background: {C_SEL_BG};
            color: {C_ACCENT};
        }}
        QMenu::separator {{
            height: 1px;
            background: {C_BORDER};
            margin: 4px 8px;
        }}
    """)
