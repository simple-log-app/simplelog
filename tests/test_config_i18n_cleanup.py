"""R6 (profile saving in ProviderPanel), R7 (config_store), R8 (language menu), new i18n keys."""
import os
import stat
import sys
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

import config_store
import i18n
import profiles_store
import providers


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(sys.argv)


# ── R7: config_store ─────────────────────────────────────────────────────────

def test_write_json_is_private_and_atomic(tmp_path):
    target = tmp_path / "cfg" / "a.json"
    config_store.write_json(target, {"é": 1})
    assert config_store.read_json(target, None) == {"é": 1}
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700
    assert [p.name for p in target.parent.iterdir()] == ["a.json"]


def test_read_json_falls_back_on_missing_or_corrupt(tmp_path):
    assert config_store.read_json(tmp_path / "none.json", []) == []
    bad = tmp_path / "bad.json"
    bad.write_text("{oops")
    assert config_store.read_json(bad, {}) == {}


def test_append_private_creates_0600_and_appends(tmp_path):
    f = tmp_path / "known_hosts"
    config_store.append_private(f, "a\n")
    config_store.append_private(f, "b\n")
    assert f.read_text() == "a\nb\n"
    assert stat.S_IMODE(f.stat().st_mode) == 0o600


def test_every_config_file_goes_through_config_store(tmp_path, monkeypatch):
    import ssh_utils
    from panels.ssh import SSHRecentManager
    monkeypatch.setattr(SSHRecentManager, "_path", tmp_path / "recents.json")
    SSHRecentManager.push({"host": "h", "port": 22, "user": "u", "remote_path": "/x"})
    assert stat.S_IMODE((tmp_path / "recents.json").stat().st_mode) == 0o600
    assert SSHRecentManager.load()[0]["host"] == "h"

    monkeypatch.setattr(i18n, "_PREFS_PATH", tmp_path / "prefs.json")
    monkeypatch.setattr(i18n, "_locale", "fr")
    i18n.save_locale()
    assert stat.S_IMODE((tmp_path / "prefs.json").stat().st_mode) == 0o600
    assert ssh_utils.append_private is config_store.append_private


# ── R6: one _save_profile for every panel ────────────────────────────────────

SAVEABLE = [p for p in providers.PROVIDERS if p.id not in ("docker", "kubernetes")]


def test_no_panel_keeps_its_own_save_handler():
    import glob
    import re
    for path in glob.glob(os.path.join(os.path.dirname(__file__), "..", "panels", "*.py")):
        text = open(path, encoding="utf-8").read()
        assert not re.search(r"def _on_save_\w*profile", text), path
        assert "Profile name:" not in text and "Save as profile" not in text, path


@pytest.mark.parametrize("provider", SAVEABLE, ids=lambda p: p.id)
def test_save_profile_stores_profile_data(app, tmp_path, monkeypatch, provider):
    monkeypatch.setattr(profiles_store, "_DIR", tmp_path)
    with patch("cloudwatch.list_profiles", return_value=[]):
        panel = provider.panel_class()()
    assert panel.profile_type == provider.id
    fake = {k: "v" for k in panel.profile_required} | {"extra": 1}
    with patch.object(type(panel), "profile_data", return_value=fake), \
         patch("panels.base.QInputDialog.getText", return_value=("  mine ", True)) as ask:
        panel._save_profile()
    assert ask.call_args.args[1:3] == (i18n.tr("profile_save_title"), i18n.tr("profile_name_prompt"))
    assert [p["name"] for p in profiles_store.load_all(provider.id)] == ["mine"]


def test_save_profile_ignores_cancel_and_missing_fields(app, tmp_path, monkeypatch):
    monkeypatch.setattr(profiles_store, "_DIR", tmp_path)
    from panels.loki import LokiPanel
    panel = LokiPanel()
    with patch("panels.base.QInputDialog.getText") as ask:
        panel._save_profile()                 # no URL yet: nothing to save, no prompt
    ask.assert_not_called()
    panel._url_input.setText("http://loki:3100")
    with patch("panels.base.QInputDialog.getText", return_value=("x", False)) as ask:
        panel._save_profile()
    assert ask.call_args.kwargs["text"] == "loki:3100"       # default name from the URL
    assert profiles_store.load_all("loki") == []


# ── R8: language menu follows locales/*.json ─────────────────────────────────

def test_language_menu_lists_every_catalog(app):
    import ui
    codes = [c for c, _ in i18n.available_locales()]
    assert codes[0] == "en" and set(codes) >= {"en", "fr", "de", "es", "zh"}
    win = ui.MainWindow()
    try:
        assert list(win._lang_actions) == codes
        assert [a.text() for a in win._lang_actions.values()] == [n for _, n in i18n.available_locales()]
        assert [c for c, a in win._lang_actions.items() if a.isChecked()] == [i18n.get_locale()]
    finally:
        win.close()


def test_every_catalog_has_a_native_name_and_all_keys():
    # the long help pages may fall back to English; every other text must be translated
    en = {k for k in i18n._STRINGS["en"] if not k.startswith("help_")}
    for code, catalog in i18n._STRINGS.items():
        assert catalog.get("lang_name"), code
        assert en <= set(catalog), (code, sorted(en - set(catalog))[:5])


# ── #24: texts that used to be hard-coded ────────────────────────────────────

@pytest.fixture
def french():
    i18n.set_locale("fr")
    yield
    i18n.set_locale("en")


def test_worker_status_and_errors_follow_the_language(french):
    import workers
    w = workers.GCPWorker(None, "proj", "(all)", "ALL", "", interval_s=1)
    got = []
    w.status.connect(got.append)
    w._say(w._MSG_LOADING)
    w._say(w._MSG_NEW, 3)
    assert got == ["Chargement des logs GCP pour proj…", "GCP proj — 3 nouvelles entrées"]
    assert i18n.tr("err_cmd_exit", cmd="docker", code=2) == "docker s'est terminé avec le code 2"


def test_ssh_and_cloudflare_errors_are_translated(french):
    import ssh_utils
    assert "inconnue" in str(ssh_utils.UnknownHostKeyError("h", "ssh-rsa", "SHA256:x"))
    import cloudflare_utils
    assert i18n.tr("err_ws_closed") == "Connexion WebSocket fermée"
    assert cloudflare_utils.i18n is i18n


def test_provider_descriptions_are_translated(french):
    assert providers.get("ssh").describe() == "Fichiers de log distants via SSH"
    assert all(not p.describe().startswith("provider_desc_") for p in providers.PROVIDERS)
