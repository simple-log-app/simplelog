"""Better Stack connection panel."""
from __future__ import annotations

from simplelog.core import i18n
from simplelog.sources import betterstack_utils
from simplelog.ui.panels.form import Field, FormPanel


class BetterStackPanel(FormPanel):
    provider_id = "betterstack"
    help_key = "help_betterstack"
    fields = (
        Field("host", "bs_field_host", placeholder="bs_ph_host"),
        Field("username", "bs_field_user"),
        Field("password", "bs_field_password", secret=True),
        Field("table", "bs_field_table", placeholder="bs_ph_table"),
    )

    def check(self, creds: dict) -> list[dict]:
        if not all(creds[k] for k in ("host", "username", "password", "table")):
            raise RuntimeError(i18n.tr("form_missing_fields"))
        betterstack_utils.check(creds["host"], creds["username"], creds["password"], creds["table"])
        return []

    def make_cfg(self, creds: dict, target: dict | None, options: dict) -> dict:
        return {"type": "betterstack", **{k: creds[k] for k in ("host", "username", "password", "table")},
                "label": creds["table"]}
