"""Heroku connection panel."""
from __future__ import annotations

from simplelog.core import i18n
from simplelog.sources import heroku_utils
from simplelog.ui.panels.form import Field, FormPanel


class HerokuPanel(FormPanel):
    provider_id = "heroku"
    help_key = "help_heroku"
    fields = (Field("token", "heroku_field_token", secret=True),)
    targets_title = "heroku_card_apps"
    show_interval = False       # a live stream: there is nothing to poll
    show_lookback = False

    def check(self, creds: dict) -> list[dict]:
        if not creds["token"]:
            raise RuntimeError(i18n.tr("form_missing_fields"))
        return [{"label": a["name"], "name": a["name"]} for a in heroku_utils.list_apps(creds["token"])]

    def make_cfg(self, creds: dict, target: dict | None, options: dict) -> dict:
        return {"type": "heroku", "token": creds["token"], "app_name": target["name"],
                "label": target["name"]}
