"""Splunk connection panel."""
from __future__ import annotations

from simplelog.core import i18n
from simplelog.sources import splunk_utils
from simplelog.ui.panels.form import Field, FormPanel


class SplunkPanel(FormPanel):
    provider_id = "splunk"
    help_key = "help_splunk"
    fields = (
        Field("url", "splunk_field_url", placeholder="splunk_ph_url"),
        Field("token", "splunk_field_token", secret=True),
        Field("username", "splunk_field_user"),
        Field("password", "splunk_field_password", secret=True),
    )
    switches = (("verify_tls", "splunk_verify_tls", True),)
    option_fields = (Field("query", "splunk_field_query", default="*", placeholder="splunk_ph_query"),)
    default_interval = 10

    def check(self, creds: dict) -> list[dict]:
        if not creds["url"]:
            raise RuntimeError(i18n.tr("form_missing_fields"))
        splunk_utils.server_name(
            creds["url"], creds["token"], creds["username"], creds["password"],
            creds["verify_tls"])
        return []

    def make_cfg(self, creds: dict, target: dict | None, options: dict) -> dict:
        return {"type": "splunk", "url": creds["url"], "token": creds["token"],
                "username": creds["username"], "password": creds["password"],
                "verify_tls": creds["verify_tls"], "query": options["query"] or "*",
                "label": creds["url"].split("//", 1)[-1].split("/")[0]}
