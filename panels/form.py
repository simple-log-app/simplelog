"""A declarative connection panel: credentials, a connect check, an optional target list.

Each source built on it only says which fields it needs and how to check them; the
layout, the background connection and the embedding contract (see ProviderPanel) are
shared.
"""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QWidget,
)

import i18n
from panels.base import FIELD_STYLE, LBL_STYLE, LIST_STYLE, ProviderPanel
from ui_theme import C_ERR, C_INFO, C_MUTED
from ui_widgets import NoScrollComboBox, _lookback_combo, _primary_btn, make_card
from ui_workers import CallWorker


@dataclass(frozen=True)
class Field:
    key: str                  # key in the profile and in the opened tab's config
    label: str                # i18n key of the caption
    secret: bool = False      # shown as dots
    default: str = ""
    placeholder: str = ""     # i18n key ("" = none)
    choices: tuple[tuple[str, str], ...] = ()    # (caption, value): a drop-down instead of text


class FormPanel(ProviderPanel):
    """Subclasses set the class attributes below and implement ``check`` / ``make_cfg``."""

    provider_id = ""
    help_key = ""
    #: credentials (saved with the connection)
    fields: tuple[Field, ...] = ()
    #: yes / no switches saved with the connection, e.g. "verify the certificate": (key, label key, default)
    switches: tuple[tuple[str, str, bool], ...] = ()
    #: free-text settings of this opening (query, filter…), shown with the options
    option_fields: tuple[Field, ...] = ()
    #: i18n key of the card listing the targets found by ``check`` ("" = nothing to pick)
    targets_title = ""
    #: False for sources that need no credentials (they open straight away)
    needs_connect = True
    show_interval = True
    default_interval = 5
    show_lookback = True

    # ── to implement ──────────────────────────────────────────────────────────

    def check(self, creds: dict) -> list[dict]:
        """Validate *creds* (runs off the UI thread). Return the targets
        ``[{"label": str, ...}]`` or raise RuntimeError."""
        raise NotImplementedError

    def make_cfg(self, creds: dict, target: dict | None, options: dict) -> dict:
        """The config of the tab to open (``type`` and the source's own keys)."""
        raise NotImplementedError

    # ── build ─────────────────────────────────────────────────────────────────

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.profile_type = self.provider_id
        self._inputs: dict[str, QLineEdit] = {}
        self._switches: dict[str, QCheckBox] = {}
        self._connected = not self.needs_connect
        self._targets: QListWidget | None = None
        self._connect_worker: CallWorker | None = None
        self._build_ui()

    def _line(self, field: Field):
        if field.choices:
            combo = NoScrollComboBox()
            for caption, value in field.choices:
                combo.addItem(i18n.tr(caption), value)
            combo.setStyleSheet(FIELD_STYLE)
            return combo
        edit = QLineEdit(field.default)
        if field.secret:
            edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setStyleSheet(FIELD_STYLE)
        if field.placeholder:
            edit.setPlaceholderText(i18n.tr(field.placeholder))
        return edit

    def _build_ui(self) -> None:
        vlay = self._scaffold()

        # ── credentials ───────────────────────────────────────────────────────
        card, lay, _ = make_card(i18n.tr("new_config"), help_key=self.help_key or None)
        for field in self.fields:
            lay.addWidget(self._lbl(LBL_STYLE, i18n.tr(field.label)))
            edit = self._line(field)
            self._inputs[field.key] = edit
            lay.addWidget(edit)
        for key, label, default in self.switches:
            box = QCheckBox(i18n.tr(label))
            box.setStyleSheet("background: transparent;")
            box.setChecked(default)
            self._switches[key] = box
            lay.addWidget(box)
        self._connect_btn = _primary_btn(i18n.tr("form_connect"))
        self._connect_btn.clicked.connect(self._do_connect)
        self._status = QLabel("")
        self._status.setStyleSheet(LBL_STYLE + " background: transparent; border: none;")
        self._status.setVisible(False)
        self._status.setWordWrap(True)
        if self.needs_connect:
            lay.addWidget(self._connect_btn)
            lay.addWidget(self._status)
        else:
            self._connect_btn.setVisible(False)
        self._cred_card = card
        card.setVisible(bool(self.fields or self.switches) or self.needs_connect)
        vlay.addWidget(card)

        # ── targets ───────────────────────────────────────────────────────────
        self._targets_card: QWidget | None = None
        if self.targets_title:
            tcard, tlay, _ = make_card(i18n.tr(self.targets_title))
            self._targets = QListWidget()
            self._targets.setMaximumHeight(170)
            self._targets.setStyleSheet(LIST_STYLE)
            tlay.addWidget(self._targets)
            tcard.setVisible(False)
            self._targets_card = tcard
            vlay.addWidget(tcard)

        # ── options ───────────────────────────────────────────────────────────
        ocard, olay, _ = make_card(i18n.tr("form_options"))
        for field in self.option_fields:
            olay.addWidget(self._lbl(LBL_STYLE, i18n.tr(field.label)))
            edit = self._line(field)
            self._inputs[field.key] = edit
            setattr(self, f"_opt_{field.key}", edit)
            olay.addWidget(edit)
        self._interval = QSpinBox()
        self._interval.setRange(1, 300)
        self._interval.setValue(self.default_interval)
        self._lookback = _lookback_combo()
        self._lookback.setStyleSheet(FIELD_STYLE)
        if self.show_interval:
            row = QHBoxLayout()
            row.addWidget(self._lbl(LBL_STYLE, i18n.tr("form_interval")))
            row.addStretch()
            self._interval.setStyleSheet(FIELD_STYLE + "max-width: 70px;")
            row.addWidget(self._interval)
            olay.addLayout(row)
        if self.show_lookback:
            row = QHBoxLayout()
            row.addWidget(self._lbl(LBL_STYLE, i18n.tr("field_time_range")))
            row.addStretch()
            row.addWidget(self._lookback)
            olay.addLayout(row)
        self._options_card = ocard
        ocard.setVisible(not self.needs_connect)
        vlay.addWidget(ocard)
        vlay.addStretch()

    # ── values ────────────────────────────────────────────────────────────────

    @staticmethod
    def _value(widget) -> str:
        return widget.currentData() if isinstance(widget, QComboBox) else widget.text().strip()

    def _creds(self) -> dict:
        creds = {f.key: self._value(self._inputs[f.key]) for f in self.fields}
        creds.update({k: box.isChecked() for k, box in self._switches.items()})
        return creds

    def _options(self) -> dict:
        return {f.key: self._value(self._inputs[f.key]) for f in self.option_fields}

    def _target(self) -> dict | None:
        if self._targets is None:
            return None
        item = self._targets.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ── connecting ────────────────────────────────────────────────────────────

    def _do_connect(self) -> None:
        creds = self._creds()
        self._connect_btn.setEnabled(False)
        self._set_status(i18n.tr("form_connecting"), C_MUTED)
        worker = CallWorker(self.check, creds)
        worker.success.connect(self._on_connected)
        worker.failure.connect(self._on_failed)
        self._connect_worker = worker
        worker.start()

    def _set_status(self, text: str, color: str) -> None:
        self._status.setText(text)
        self._status.setStyleSheet(
            f"color: {color}; font-size: 11px; background: transparent; border: none;")
        self._status.setVisible(bool(text))

    def _on_connected(self, targets) -> None:
        self._connect_btn.setEnabled(True)
        self._connect_btn.setText(i18n.tr("form_refresh"))
        if self._targets is not None:
            self._targets.clear()
            for target in targets or []:
                item = QListWidgetItem(target["label"])
                item.setData(Qt.ItemDataRole.UserRole, target)
                self._targets.addItem(item)
            if not targets:
                self._set_status(i18n.tr("form_no_targets"), C_ERR)
                return
            self._targets_card.setVisible(True)
        self._connected = True
        self._set_status(i18n.tr("form_connected"), C_INFO)
        self._options_card.setVisible(True)

    def _on_failed(self, msg: str) -> None:
        self._connect_btn.setEnabled(True)
        self._set_status(msg, C_ERR)

    # ── opening ───────────────────────────────────────────────────────────────

    def _on_open(self) -> None:
        if not self.can_open():
            return
        target = self._target()
        cfg = self.make_cfg(self._creds(), target, self._options())
        cfg["interval_s"] = self._interval.value()
        cfg["lookback_s"] = self._lookback.currentData()
        self.open_tab.emit(cfg, "tab")      # the dialog's "Open as" decides the mode

    # ── Embedding contract (see ProviderPanel) ────────────────────────────────

    @property
    def restore_attrs(self) -> tuple[str, ...]:  # type: ignore[override]
        attrs = [f"_opt_{f.key}" for f in self.option_fields]
        attrs += ["_interval", "_lookback"]
        if self._targets is not None:
            attrs.insert(0, "_targets")
        return tuple(attrs)

    @property
    def saveable(self) -> bool:  # type: ignore[override]
        return self.needs_connect

    def connect_now(self) -> None:
        if self.needs_connect:
            self._do_connect()

    def is_connected(self) -> bool:
        return self._connected

    def load_profile(self, data: dict) -> None:
        for field in self.fields:
            edit = self._inputs[field.key]
            if field.key in data and isinstance(edit, QLineEdit):
                edit.setText(str(data[field.key]))
        for key, box in self._switches.items():
            if key in data:
                box.setChecked(bool(data[key]))

    def profile_data(self) -> dict:
        return self._creds()

    def open_selected(self) -> None:
        self._on_open()

    def can_open(self) -> bool:
        if not self._connected:
            return False
        return self._targets is None or self._target() is not None
