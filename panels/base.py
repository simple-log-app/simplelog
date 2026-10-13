"""Shared base class and styles for the provider connection panels."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QInputDialog, QLabel, QScrollArea, QVBoxLayout, QWidget

import i18n
import profiles_store
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

    #: profiles_store service this panel saves to ("" when it has no saved profiles)
    profile_type = ""
    #: name of the ``_ProfileBar`` attribute refreshed after a save
    _profile_bar_attr = ""
    #: ``profile_data()`` keys that must be filled in before a profile can be saved
    profile_required: tuple = ()

    def default_profile_name(self) -> str:
        return self.profile_type

    def _save_profile(self) -> None:
        """Ask for a name, then store ``profile_data()`` under it."""
        data = self.profile_data()
        if any(not data.get(key) for key in self.profile_required):
            return
        name, ok = QInputDialog.getText(
            self, i18n.tr("profile_save_title"), i18n.tr("profile_name_prompt"),
            text=self.default_profile_name())
        if not ok or not name.strip():
            return
        profiles_store.upsert(self.profile_type, name.strip(), data)
        bar = getattr(self, self._profile_bar_attr, None)
        if bar is not None:
            bar.reload()

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


    # ── Embedding contract ────────────────────────────────────────────────────
    # AddConnectionDialog hosts a panel inside its own footer (name field, Open /
    # Save & Open buttons) and drives it only through these members, so a panel needs
    # no knowledge of the dialog and the dialog none of the panel's widgets.

    #: names of the widgets whose selection is saved with a connection and restored
    #: (once connected) when it is reopened
    restore_attrs: tuple[str, ...] = ()
    #: False when there is nothing to save (e.g. Docker talks to the local daemon)
    saveable: bool = True

    def connect_now(self) -> None:
        """Start connecting with the credentials currently entered."""

    def is_connected(self) -> bool:
        """True once the connection is up and its targets (projects, pods…) are listed."""
        return True

    def load_profile(self, data: dict) -> None:
        """Fill the form from a saved connection."""

    def profile_data(self) -> dict:
        """The credentials / settings to store for this connection."""
        return {}

    def can_open(self) -> bool:
        """True when a target is selected, so that Open can be used."""
        raise NotImplementedError

    def open_selected(self) -> None:
        """Open the selected target (emits ``open_tab``)."""
        raise NotImplementedError

    def profile_extra(self, cfg: dict) -> dict:
        """More settings to store when saving, taken from the tab config being opened."""
        return {}

    def release(self) -> None:
        """Free what the panel holds once its dialog is closed (e.g. a connection)."""

    def _embedded_hidden(self) -> list[QWidget]:
        """Widgets made redundant by the dialog's footer (own Save / Open buttons, title)."""
        return []

    def embed(self) -> None:
        """Prepare the panel to live inside the dialog."""
        for widget in self._embedded_hidden():
            widget.setVisible(False)
