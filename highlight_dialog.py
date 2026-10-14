"""Dialog to edit the highlight rules (see highlight_rules.py)."""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import highlight_rules
import i18n
from highlight_rules import Rule
from ui_theme import (
    C_ACCENT,
    C_BORDER,
    C_BORDER2,
    C_ERR,
    C_MUTED,
    C_OVERLAY_SURFACE,
    C_TEXT,
    rgba,
)
from ui_widgets import _ghost_btn, _primary_btn


def _swatch(color: str) -> QIcon:
    pm = QPixmap(14, 14)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(1, 1, 12, 12, 3, 3)
    p.end()
    return QIcon(pm)


class _RuleRow(QWidget):
    """[text] [Aa] [.*] [colour] [×]"""

    def __init__(self, rule: Rule, on_remove, parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.text_edit = QLineEdit(rule.text)
        self.text_edit.setPlaceholderText(i18n.tr("highlight_placeholder"))
        lay.addWidget(self.text_edit, 1)

        self.case_btn = self._toggle("Aa", rule.case, i18n.tr("tip_match_case"))
        self.regex_btn = self._toggle(".*", rule.regex, i18n.tr("tip_regex"))
        lay.addWidget(self.case_btn)
        lay.addWidget(self.regex_btn)

        self.color_combo = QComboBox()
        self.color_combo.setIconSize(QSize(14, 14))
        self.color_combo.setFixedWidth(52)
        for color in highlight_rules.PALETTE:
            self.color_combo.addItem(_swatch(color), "", color)
        idx = self.color_combo.findData(rule.color)
        self.color_combo.setCurrentIndex(max(0, idx))
        lay.addWidget(self.color_combo)

        remove = QPushButton("×")
        remove.setFixedSize(24, 24)
        remove.setCursor(Qt.CursorShape.PointingHandCursor)
        remove.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_MUTED}; border: none;"
            f" font-size: 15px; padding: 0; min-height: 24px; }}"
            f"QPushButton:hover {{ color: {C_ERR}; background: {rgba(C_ERR, 20)};"
            f" border-radius: 4px; }}"
        )
        remove.clicked.connect(lambda: on_remove(self))
        lay.addWidget(remove)

    @staticmethod
    def _toggle(text: str, checked: bool, tip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setToolTip(tip)
        btn.setFixedSize(28, 28)
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_MUTED}; padding: 0;"
            f" border: 1px solid {C_BORDER2}; border-radius: 5px; font-size: 10px;"
            f" font-weight: 700; font-family: 'JetBrains Mono', monospace; }}"
            f"QPushButton:checked {{ background: {rgba(C_ACCENT, 31)}; color: {C_ACCENT};"
            f" border: 1px solid {rgba(C_ACCENT, 90)}; }}"
        )
        return btn

    def rule(self) -> Rule:
        return Rule(
            self.text_edit.text().strip(),
            self.color_combo.currentData(),
            self.case_btn.isChecked(),
            self.regex_btn.isChecked(),
        )


class HighlightRulesDialog(QDialog):
    """Edit the list of rules; **Apply** stores them (and they show at once in every log)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("highlight_title"))
        self.setModal(True)
        self.setFixedSize(460, 420)
        self.setStyleSheet(
            f"QDialog {{ background: {C_OVERLAY_SURFACE}; color: {C_TEXT};"
            f" border: 1px solid {C_BORDER2}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        hint = QLabel(i18n.tr("highlight_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {C_MUTED}; font-size: 11px; background: transparent;")
        root.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {C_BORDER}; border-radius: 5px; }}"
        )
        host = QWidget()
        self._rows_lay = QVBoxLayout(host)
        self._rows_lay.setContentsMargins(8, 8, 8, 8)
        self._rows_lay.setSpacing(6)
        self._rows_lay.addStretch()
        scroll.setWidget(host)
        root.addWidget(scroll, 1)

        self._rows: list[_RuleRow] = []

        self._add_btn = _ghost_btn(i18n.tr("highlight_add"))
        self._add_btn.clicked.connect(lambda: self._add_row(Rule("")))
        add_row = QHBoxLayout()
        add_row.addWidget(self._add_btn)
        add_row.addStretch()
        root.addLayout(add_row)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = _ghost_btn(i18n.tr("remote_cancel"))
        cancel.clicked.connect(self.reject)
        apply_btn = _primary_btn(i18n.tr("highlight_apply"))
        apply_btn.clicked.connect(self._apply)
        buttons.addWidget(cancel)
        buttons.addWidget(apply_btn)
        root.addLayout(buttons)
        for rule in highlight_rules.get_rules():
            self._add_row(rule)

    def _add_row(self, rule: Rule) -> None:
        if len(self._rows) >= highlight_rules._MAX_RULES:
            return
        row = _RuleRow(rule, self._remove_row)
        self._rows.append(row)
        self._rows_lay.insertWidget(self._rows_lay.count() - 1, row)
        self._sync_add_button()
        if not rule.text:
            row.text_edit.setFocus()

    def _remove_row(self, row: _RuleRow) -> None:
        self._rows.remove(row)
        self._rows_lay.removeWidget(row)
        row.deleteLater()
        self._sync_add_button()

    def _sync_add_button(self) -> None:
        self._add_btn.setEnabled(len(self._rows) < highlight_rules._MAX_RULES)

    def rules(self) -> list[Rule]:
        return [r.rule() for r in self._rows if r.text_edit.text().strip()]

    def _apply(self) -> None:
        highlight_rules.set_rules(self.rules())
        self.accept()
