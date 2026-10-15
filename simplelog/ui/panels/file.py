"""File connection panel."""

from __future__ import annotations

import os

from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from simplelog.core import i18n
from simplelog.ui.ui_theme import C_MUTED, C_SIDE, C_TEXT
from simplelog.ui.ui_widgets import MessageBox, OpenModeWidget, _primary_btn, make_card

# ── FilePanel ──────────────────────────────────────────────────────────────────

class FilePanel(QWidget):
    open_tab = pyqtSignal(str, int, str)  # (path, tail_lines, split_mode)

    _MAX_RECENT = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recent: list[str] = []
        self._build_ui()
        _key = id(self)
        i18n.register(_key, self.retranslate)
        self.destroyed.connect(lambda _=None, k=_key: i18n.unregister(k))

    def _build_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(12, 16, 12, 16)
        vbox.setSpacing(12)
        self.setMinimumWidth(200)
        self.setStyleSheet(f"background: {C_SIDE};")

        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-size: 15px; font-weight: 700;"
            "background: transparent; border: none; margin-bottom: 4px;"
        )
        vbox.addWidget(self._title_lbl)

        # ── OPEN FILE card ──
        card, cl, self._lbl_card_open = make_card(i18n.tr("file_card_open"))
        self._desc_lbl = QLabel()
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setStyleSheet(
            f"color: {C_MUTED}; font-size: 12px; background: transparent; border: none;"
        )

        # Tail lines selector
        tail_row = QHBoxLayout()
        tail_row.setSpacing(8)
        self._tail_lbl = QLabel()
        self._tail_lbl.setStyleSheet(
            f"color: {C_MUTED}; font-size: 12px; background: transparent; border: none;"
        )
        self._tail_spin = QSpinBox()
        self._tail_spin.setRange(1, 500_000)
        self._tail_spin.setValue(100)
        self._tail_spin.setSingleStep(100)
        tail_row.addWidget(self._tail_lbl)
        tail_row.addWidget(self._tail_spin)
        tail_row.addStretch()

        self._open_mode_w = OpenModeWidget()
        self._get_open_mode = self._open_mode_w.get_mode

        self._browse_btn = _primary_btn()
        self._browse_btn.clicked.connect(self._on_browse)

        cl.addWidget(self._desc_lbl)
        cl.addLayout(tail_row)
        cl.addWidget(self._open_mode_w)
        cl.addWidget(self._browse_btn)
        vbox.addWidget(card)

        # ── RECENT FILES card ──
        card2, rl, self._lbl_card_recent = make_card(i18n.tr("file_card_recent"))
        self.recent_list = QListWidget()
        self.recent_list.setMinimumHeight(120)
        self.recent_list.itemDoubleClicked.connect(self._on_recent_double_click)

        self.empty_label = QLabel()
        self.empty_label.setStyleSheet(
            "color: #4c4c4c; font-size: 12px; background: transparent; border: none;"
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        rl.addWidget(self.recent_list)
        rl.addWidget(self.empty_label)
        vbox.addWidget(card2)

        vbox.addStretch()
        self.retranslate()
        self._refresh_recent_ui()

    def retranslate(self) -> None:
        self._title_lbl.setText(i18n.tr("file_title"))
        if self._lbl_card_open:
            self._lbl_card_open.setText(i18n.tr("file_card_open").upper())
        if self._lbl_card_recent:
            self._lbl_card_recent.setText(i18n.tr("file_card_recent").upper())
        self._desc_lbl.setText(i18n.tr("file_desc"))
        self._tail_lbl.setText(i18n.tr("file_last_lines"))
        self._browse_btn.setText(i18n.tr("file_browse"))
        self.empty_label.setText(i18n.tr("file_no_recent"))

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            i18n.tr("nav_open_file"),
            os.path.expanduser("~"),
            i18n.tr("filter_log_files"),
        )
        if path:
            self._open_path(path)

    def _on_recent_double_click(self, item: QListWidgetItem):
        path = item.toolTip()
        if os.path.isfile(path):
            self._open_path(path)
        else:
            MessageBox.warning(
                self,
                i18n.tr("err_file_not_found"),
                i18n.tr("err_cannot_open", path=path),
            )

    def _open_path(self, path: str):
        if path in self._recent:
            self._recent.remove(path)
        self._recent.insert(0, path)
        self._recent = self._recent[: self._MAX_RECENT]
        self._refresh_recent_ui()
        self.open_tab.emit(path, self._tail_spin.value(), self._get_open_mode())

    def _refresh_recent_ui(self):
        self.recent_list.clear()
        if self._recent:
            self.recent_list.show()
            self.empty_label.hide()
            for p in self._recent:
                item = QListWidgetItem(os.path.basename(p))
                item.setToolTip(p)
                self.recent_list.addItem(item)
        else:
            self.recent_list.hide()
            self.empty_label.show()
