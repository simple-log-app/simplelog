"""Sentry connection panel."""
from __future__ import annotations

from simplelog.core import i18n
from simplelog.sources import sentry_utils
from simplelog.ui.panels.form import Field, FormPanel


class SentryPanel(FormPanel):
    provider_id = "sentry"
    help_key = "help_sentry"
    fields = (
        Field("url", "sentry_field_url", default=sentry_utils.DEFAULT_URL),
        Field("token", "sentry_field_token", secret=True),
    )
    targets_title = "sentry_card_projects"
    default_interval = 15

    def check(self, creds: dict) -> list[dict]:
        if not creds["token"]:
            raise RuntimeError(i18n.tr("form_missing_fields"))
        return [
            {"label": f"{p['org']}/{p['slug']}", **p}
            for p in sentry_utils.list_projects(creds["token"], creds["url"])
        ]

    def make_cfg(self, creds: dict, target: dict | None, options: dict) -> dict:
        return {"type": "sentry", "token": creds["token"], "url": creds["url"] or sentry_utils.DEFAULT_URL,
                "org": target["org"], "project": target["slug"],
                "label": f"{target['org']}/{target['slug']}"}
