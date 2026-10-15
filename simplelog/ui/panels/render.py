"""Render connection panel."""
from __future__ import annotations

from simplelog.core import i18n
from simplelog.sources import render_utils
from simplelog.ui.panels.form import Field, FormPanel


class RenderPanel(FormPanel):
    provider_id = "render"
    help_key = "help_render"
    fields = (Field("api_key", "render_field_key", secret=True),)
    targets_title = "render_card_services"

    def check(self, creds: dict) -> list[dict]:
        if not creds["api_key"]:
            raise RuntimeError(i18n.tr("form_missing_fields"))
        return [
            {"label": f"{s['name']}  ({s['type']})" if s["type"] else s["name"], **s}
            for s in render_utils.list_services(creds["api_key"])
        ]

    def make_cfg(self, creds: dict, target: dict | None, options: dict) -> dict:
        return {"type": "render", "api_key": creds["api_key"], "owner_id": target["owner_id"],
                "resource_id": target["id"], "name": target["name"], "label": target["name"]}
