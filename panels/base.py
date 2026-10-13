"""Shared base class and styles for the provider connection panels."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from ui_theme import C_BG, C_BORDER, C_MUTED, C_PANEL, C_SEL_BG, C_TEXT

FIELD_STYLE = (
    f"background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
    f"border-radius: 4px; padding: 6px 8px; font-size: 12px;"
)
LBL_STYLE = f"color: {C_MUTED}; font-size: 11px;"
LIST_STYLE = (
    f"QListWidget {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
    f" border-radius: 4px; font-size: 12px; }}"
    f"QListWidget::item:selected {{ background: {C_SEL_BG}; }}"
)


class ProviderPanel(QWidget):
    """A connection panel that emits `open_tab(cfg, split_mode)` to open a log tab."""

    open_tab = pyqtSignal(dict, str)   # (cfg, split_mode)

    @staticmethod
    def _lbl(style: str, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(style)
        return lbl

    def _scaffold(self) -> QVBoxLayout:
        """Create the scrollable, padded content column and return its layout."""
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
        return vlay
