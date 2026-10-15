"""systemd journal (local) panel."""
from __future__ import annotations

from PyQt6.QtWidgets import QLabel

from simplelog.core import i18n
from simplelog.sources import journald_utils
from simplelog.ui.panels.form import Field, FormPanel
from simplelog.ui.ui_theme import C_ERR


class JournaldPanel(FormPanel):
    provider_id = "journald"
    help_key = "help_journald"
    needs_connect = False            # local: no credentials, nothing to connect to
    show_interval = False
    option_fields = (
        Field("unit", "journald_field_unit", placeholder="journald_ph_unit"),
        Field("priority", "journald_field_priority", choices=(
            ("form_all", ""), ("journald_prio_err", "err"), ("journald_prio_warning", "warning"),
            ("journald_prio_notice", "notice"), ("journald_prio_info", "info"),
            ("journald_prio_debug", "debug"),
        )),
    )

    def _build_ui(self) -> None:
        super()._build_ui()
        if not journald_utils.is_available():
            warning = QLabel(i18n.tr("journald_missing"))
            warning.setWordWrap(True)
            warning.setStyleSheet(f"color: {C_ERR}; font-size: 11px;")
            self._options_card.layout().addWidget(warning)

    def can_open(self) -> bool:
        return journald_utils.is_available() and journald_utils.valid_unit(self._options()["unit"])

    def check(self, creds: dict) -> list[dict]:
        return []

    def make_cfg(self, creds: dict, target: dict | None, options: dict) -> dict:
        return {"type": "journald", "unit": options["unit"], "priority": options["priority"],
                "label": options["unit"] or "journald"}
