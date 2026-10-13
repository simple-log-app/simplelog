"""Tests for the provider registry (providers.py) and the ProviderPanel embedding contract."""
import os
import threading
import time
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

import i18n
import providers
import workers
from panels.base import ProviderPanel


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


def _wait_for(cond, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QApplication.processEvents()
        if cond():
            return True
        time.sleep(0.005)
    return False


IDS = [p.id for p in providers.PROVIDERS]


# ── registry ─────────────────────────────────────────────────────────────────

def test_ids_are_unique_and_in_the_documented_order():
    assert IDS == ["cloudwatch", "gcp", "azure", "ssh", "docker", "vercel", "loki", "datadog",
                   "elastic", "railway", "flyio", "kubernetes", "cloudflare"]
    assert len(set(IDS)) == len(IDS)


def test_lookup_by_id_and_by_cfg_type():
    assert providers.get("ssh").name == "SSH"
    assert providers.get("nope") is None
    for t in ("docker_container", "docker_compose", "docker_exec_file"):
        assert providers.for_type(t).id == "docker"
    for pid in IDS:
        if pid != "docker":                 # docker opens its three cfg types instead
            assert providers.for_type(pid).id == pid
    assert providers.for_type("docker") is None
    assert providers.for_type("martian") is None


@pytest.mark.parametrize("provider", providers.PROVIDERS, ids=IDS)
def test_every_provider_is_fully_described(provider):
    assert provider.name and provider.icon and provider.description
    assert provider.color.startswith("#") and provider.svg.startswith("<svg")
    assert provider.source_color


@pytest.mark.parametrize("provider", providers.PROVIDERS, ids=IDS)
def test_every_panel_class_resolves_to_a_provider_panel(provider):
    cls = provider.panel_class()
    assert issubclass(cls, ProviderPanel)


def test_providers_that_need_their_own_connection():
    needing = {p.id: p.client_key for p in providers.PROVIDERS if p.connect}
    assert needing == {"gcp": "_client", "azure": "_logs_client", "ssh": "_client"}


def test_source_colors_cover_every_viewer_source():
    colors = providers.source_colors()
    assert set(IDS) <= set(colors)
    assert {"docker_compose", "docker_exec_file"} <= set(colors)
    import log_view
    assert log_view._SOURCE_COLORS["file"] and log_view._SOURCE_COLORS["stdin"]
    for source, color in colors.items():
        assert log_view._SOURCE_COLORS[source] == color


@pytest.mark.parametrize("source", [*providers.source_colors(), "file", "stdin"])
def test_viewer_badge_names_its_source(source):
    import ui
    viewer = ui.LogViewer(source_type=source)
    assert viewer._source_badge.text() == source.replace("_", " ").upper()
    i18n.set_locale("fr")
    try:
        viewer.retranslate()
        assert viewer._source_badge.text() == source.replace("_", " ").upper()
        assert not viewer._source_badge.text().lower().startswith("src_")
    finally:
        i18n.set_locale("en")


# ── sessions: cfg -> worker + labels ─────────────────────────────────────────

CLIENT = MagicMock()

SESSIONS = [
    ("cloudwatch", {"type": "cloudwatch", "client": CLIENT, "group": "/aws/lambda/fn",
                    "stream": "2024/01/01/s1", "filter": "", "interval": 5, "lookback": 3600},
     workers.TailWorker, "cloudwatch", "/aws/lambda/fn  ›  2024/01/01/s1", "s1"),
    ("cloudwatch", {"type": "cloudwatch", "client": CLIENT, "group": "/aws/lambda/fn",
                    "stream": "", "filter": "", "interval": 5, "lookback": 3600},
     workers.TailWorker, "cloudwatch", "/aws/lambda/fn  ›  (all streams)", "fn"),
    ("ssh", {"type": "ssh", "host": "srv", "user": "me", "remote_path": "/var/log/app.log"},
     workers.SSHWorker, "ssh", "me@srv:/var/log/app.log", "app.log"),
    ("ssh", {"type": "ssh", "host": "srv", "user": "me", "remote_path": "/var/log/"},
     workers.SSHWorker, "ssh", "me@srv:/var/log/", "srv"),
    ("docker", {"type": "docker_container", "container_id": "abcdef1234567890", "container_name": "web"},
     workers.DockerContainerWorker, "docker", "docker  ›  web", "web"),
    ("docker", {"type": "docker_container", "container_id": "abcdef1234567890"},
     workers.DockerContainerWorker, "docker", "docker  ›  abcdef123456", "abcdef123456"),
    ("docker", {"type": "docker_compose", "project_name": "shop"},
     workers.DockerComposeWorker, "docker_compose", "compose  ›  shop", "shop"),
    ("docker", {"type": "docker_exec_file", "container_id": "abc", "container_name": "web",
                "remote_path": "/var/log/x.log"},
     workers.DockerExecFileWorker, "docker_exec_file", "web  ›  /var/log/x.log", "x.log"),
    ("vercel", {"type": "vercel", "token": "t", "project_id": "p", "project_name": "site",
                "deployment_id": "d"},
     workers.VercelWorker, "vercel", "vercel  ›  site", "site"),
    ("gcp", {"type": "gcp", "project_id": "proj"},
     workers.GCPWorker, "gcp", "gcp  ›  proj", "proj"),
    ("azure", {"type": "azure", "workspace_id": "w", "query": "q", "label": "prod"},
     workers.AzureWorker, "azure", "azure  ›  prod", "prod"),
    ("azure", {"type": "azure", "workspace_id": "w", "query": "q"},
     workers.AzureWorker, "azure", "azure  ›  azure", "azure"),
    ("loki", {"type": "loki", "url": "https://loki.example.com:3100/x", "query": "{a=\"b\"}"},
     workers.LokiWorker, "loki", "loki  ›  loki.example.com:3100", "loki.example.com:3100"),
    ("datadog", {"type": "datadog", "base_url": "https://api.datadoghq.eu", "api_key": "k",
                 "app_key": "a"},
     workers.DatadogWorker, "datadog", "datadog  ›  https://api.datadoghq.eu",
     "https://api.datadoghq.eu"),
    ("elastic", {"type": "elastic", "url": "http://es:9200", "index": "logs-*", "label": "es"},
     workers.ElasticWorker, "elastic", "elastic  ›  es", "es"),
    ("railway", {"type": "railway", "token": "t", "project_name": "p", "service_name": "svc",
                 "service_id": "sid"},
     workers.RailwayWorker, "railway", "railway  ›  svc", "svc"),
    ("flyio", {"type": "flyio", "token": "t", "app_name": "myapp"},
     workers.FlyioWorker, "flyio", "fly.io  ›  myapp", "myapp"),
    ("kubernetes", {"type": "kubernetes", "pod": "web-1", "namespace": "prod", "label": "prod/web-1"},
     workers.KubernetesWorker, "kubernetes", "k8s  ›  prod/web-1", "prod/web-1"),
    ("cloudflare", {"type": "cloudflare", "api_token": "t", "account_id": "a", "script_name": "edge"},
     workers.CloudflareWorker, "cloudflare", "cloudflare  ›  edge", "edge"),
]


@pytest.mark.parametrize("pid,cfg,cls,source,title,tab", SESSIONS)
def test_session_labels_and_worker(pid, cfg, cls, source, title, tab):
    provider = providers.for_type(cfg["type"])
    assert provider.id == pid
    session = provider.session(cfg, CLIENT)
    assert isinstance(session.worker, cls)
    assert (session.source, session.title, session.tab) == (source, title, tab)


def test_every_provider_has_a_sample_session():
    assert {s[0] for s in SESSIONS} == set(IDS)


def test_loki_and_elastic_pass_only_the_credentials_of_the_chosen_auth_mode():
    loki = providers.get("loki").session(
        {"type": "loki", "url": "http://l", "query": "q", "auth_mode": 2,
         "username": "u", "password": "p", "token": "T"}, None).worker
    assert (loki._username, loki._password, loki._token) == ("", "", "T")
    es = providers.get("elastic").session(
        {"type": "elastic", "url": "http://e", "index": "i", "auth_mode": 2,
         "api_key": "K", "username": "u", "password": "p"}, None).worker
    assert (es._api_key, es._username, es._password) == ("", "u", "p")


def test_connect_functions_use_the_cfg():
    with patch("providers.ssh_utils.make_client", return_value="ssh-client") as ssh:
        assert providers.get("ssh").connect(
            {"host": "h", "user": "u", "port": 2200, "key_path": "/k", "password": ""}
        ) == "ssh-client"
    ssh.assert_called_once_with("h", "u", 2200, key_path="/k", password=None)
    with patch("providers.gcp_utils.make_client", return_value="gcp-client") as gcp:
        assert providers.get("gcp").connect({"project_id": "p", "key_path": ""}) == "gcp-client"
    gcp.assert_called_once_with("p", None)
    with patch("providers.azure_utils.make_credential", return_value="cred") as cred, \
         patch("providers.azure_utils.make_logs_client", return_value="logs") as logs:
        assert providers.get("azure").connect(
            {"tenant_id": "t", "client_id": "c", "client_secret": "s"}
        ) == "logs"
    cred.assert_called_once_with("t", "c", "s")
    logs.assert_called_once_with("cred")


# ── MainWindow.open_remote_tab ───────────────────────────────────────────────

class _FakeWorker(QObject):
    new_lines = pyqtSignal(list)
    status = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, *a, **k):
        super().__init__()

    def start(self):
        pass

    def isRunning(self):
        return False

    def stop(self):
        pass


@pytest.fixture
def window(qapp):
    import ui
    win = ui.MainWindow()
    win.show()
    qapp.processEvents()
    yield win
    win.close()


def test_unknown_type_is_ignored(window):
    window.open_remote_tab({"type": "martian"})
    window.open_remote_tab({})
    assert window._top_tabs.count() == 0


@pytest.mark.parametrize("pid,cfg,cls,source,title,tab", SESSIONS)
def test_open_remote_tab_opens_a_labelled_tab(window, pid, cfg, cls, source, title, tab):
    cfg = {**cfg, "_client": MagicMock(), "_logs_client": MagicMock()}
    with patch.object(workers.LogWorker, "start", lambda self, *a: None):
        window.open_remote_tab(cfg)
    assert window._top_tabs.count() == 1
    assert window._top_tabs.tabText(0) == tab
    viewer = window._cur_viewer
    assert viewer._source_type == source and viewer.title_label.text() == title


def test_the_ready_client_is_consumed_from_the_cfg(window):
    client = MagicMock()
    cfg = {"type": "azure", "workspace_id": "w", "query": "q", "_logs_client": client}
    with patch("providers.AzureWorker", _FakeWorker) as _:
        window.open_remote_tab(cfg)
    assert "_logs_client" not in cfg and window._top_tabs.count() == 1


def test_a_provider_without_connect_keeps_its_cfg_untouched(window):
    cfg = {"type": "loki", "url": "http://l", "query": "q", "_client": "keep"}
    with patch("providers.LokiWorker", _FakeWorker):
        window.open_remote_tab(cfg)
    assert cfg["_client"] == "keep"


def test_a_missing_connection_is_made_in_the_background_with_the_provider_title(window):
    release = threading.Event()

    def slow(cfg):
        release.wait(5)
        raise RuntimeError("unreachable")

    provider = providers.get("ssh")
    fake = providers.Provider(**{**provider.__dict__, "connect": slow})
    with patch.dict(providers._BY_TYPE, {"ssh": fake}), \
         patch("main_window.QMessageBox.critical") as crit:
        t0 = time.monotonic()
        window.open_remote_tab({"type": "ssh", "host": "h", "user": "u", "remote_path": "/x"})
        assert time.monotonic() - t0 < 0.5
        release.set()
        assert _wait_for(lambda: crit.called)
    assert crit.call_args[0][1] == "SSH Error" and "unreachable" in crit.call_args[0][2]


# ── saved-connection list uses the registry ──────────────────────────────────

def test_saved_connections_are_listed_for_every_provider(qapp, tmp_path, monkeypatch):
    import profiles_store
    import ui
    monkeypatch.setattr(profiles_store, "_DIR", tmp_path)
    for pid in IDS:
        profiles_store.upsert(pid, f"{pid}-conn", {})
    panel = ui.RemoteHomePanel()
    names = [lbl.text() for lbl in panel.findChildren(type(panel._remote_title_lbl))]
    for p in providers.PROVIDERS:
        assert p.name in names and f"{p.id}-conn" in names


@pytest.mark.parametrize("svc,profile,expected", [
    ("cloudwatch", {"region": "eu-west-1"}, "eu-west-1"),
    ("gcp", {"project_id": "proj-1"}, "proj-1"),
    ("azure", {"workspace_id": "ws"}, "ws"),
    ("ssh", {"host": "srv"}, "srv"),
    ("cloudflare", {"account_id": "acc"}, "acc"),
    ("loki", {"url": "http://l"}, ""),
    ("unknown", {"host": "x"}, ""),
])
def test_subtitle_comes_from_the_registry(svc, profile, expected):
    import ui
    assert ui.RemoteHomePanel._get_subtitle(svc, profile) == expected


# ── the ProviderPanel contract ───────────────────────────────────────────────

@pytest.fixture
def make_panel(monkeypatch):
    import cloudwatch
    import docker_utils
    import kubernetes_utils
    monkeypatch.setattr(cloudwatch, "list_profiles", lambda: [])
    monkeypatch.setattr(docker_utils, "is_docker_available", lambda: True)
    monkeypatch.setattr(docker_utils, "list_containers", lambda: [])
    monkeypatch.setattr(docker_utils, "list_compose_stacks", lambda: [])
    monkeypatch.setattr(kubernetes_utils, "is_available", lambda: True)
    monkeypatch.setattr(kubernetes_utils, "list_contexts", lambda: ["dev", "prod"])
    monkeypatch.setattr(kubernetes_utils, "current_context", lambda: "dev")

    def make(pid):
        return providers.get(pid).panel_class()()
    return make


def test_base_panel_defaults_and_abstract_members():
    p = ProviderPanel()
    assert p.restore_attrs == () and p.saveable is True
    assert p.is_connected() is True and p.profile_data() == {} and p.profile_extra({}) == {}
    p.connect_now()
    p.load_profile({})
    p.release()
    with pytest.raises(NotImplementedError):
        p.can_open()
    with pytest.raises(NotImplementedError):
        p.open_selected()


def test_base_embed_hides_what_the_subclass_lists():
    from PyQt6.QtWidgets import QPushButton

    class P(ProviderPanel):
        def __init__(self):
            super().__init__()
            self.a, self.b = QPushButton(self), QPushButton(self)

        def _embedded_hidden(self):
            return [self.a]

    p = P()
    p.embed()
    assert p.a.isHidden() and not p.b.isHidden()


@pytest.mark.parametrize("pid", IDS)
def test_panels_implement_the_whole_contract(make_panel, pid):
    p = make_panel(pid)
    assert isinstance(p.restore_attrs, tuple)
    assert isinstance(p.profile_data(), dict)
    assert isinstance(p.can_open(), bool)
    p.embed()
    for w in p._embedded_hidden():
        assert w.isHidden()
    for attr in p.restore_attrs:
        assert hasattr(p, attr), attr


@pytest.mark.parametrize("pid", IDS)
def test_only_docker_has_nothing_to_save(make_panel, pid):
    assert make_panel(pid).saveable is (pid != "docker")


@pytest.mark.parametrize("pid", [i for i in IDS if i != "docker"])
def test_nothing_is_openable_before_connecting(make_panel, pid):
    p = make_panel(pid)
    assert p.can_open() is False


def test_docker_panel_is_openable_only_with_a_selection(make_panel):
    p = make_panel("docker")
    assert p.can_open() is False
    p._open_btn_c.setEnabled(True)
    assert p.can_open() is True


def test_docker_without_docker_installed(monkeypatch):
    import docker_utils
    monkeypatch.setattr(docker_utils, "is_docker_available", lambda: False)
    from panels.docker import DockerPanel
    p = DockerPanel()
    assert p.can_open() is True        # nothing to wait for
    p.open_selected()                  # and nothing to open: must not raise
    p.embed()


def test_kubernetes_without_kubectl(monkeypatch):
    import kubernetes_utils
    monkeypatch.setattr(kubernetes_utils, "is_available", lambda: False)
    from panels.kubernetes import KubernetesPanel
    p = KubernetesPanel()
    assert p.can_open() is False and p.profile_data() == {}
    p.embed()


PROFILES = {
    "ssh": {"host": "h", "port": 2222, "user": "u", "auth_mode": "key", "key_path": "/k",
            "remote_path": "/var/log/x"},
    "gcp": {"auth_mode": 1, "key_path": "/k.json", "project_id": "proj"},
    "azure": {"tenant_id": "t", "client_id": "c", "client_secret": "s", "workspace_id": "w"},
    "vercel": {"token": "tok"},
    "loki": {"url": "http://l:3100", "auth_mode": 1, "username": "u", "password": "p", "token": ""},
    "elastic": {"url": "http://es:9200", "auth_mode": 2, "api_key": "", "username": "u",
                "password": "p"},
    "railway": {"token": "tok"},
    "flyio": {"token": "tok"},
    "cloudflare": {"api_token": "tok", "account_id": "acc"},
    "kubernetes": {"context": "prod"},
}


@pytest.mark.parametrize("pid", list(PROFILES))
def test_a_profile_survives_load_then_save(make_panel, pid):
    p = make_panel(pid)
    p.load_profile(PROFILES[pid])
    assert p.profile_data() == PROFILES[pid]


def test_datadog_profile_roundtrip(make_panel):
    p = make_panel("datadog")
    site = p._site_combo.itemText(p._site_combo.count() - 1)
    p.load_profile({"site": site, "api_key": "k", "app_key": "a"})
    assert p.profile_data() == {"site": site, "api_key": "k", "app_key": "a"}


def test_cloudwatch_profile_data_and_extras(make_panel):
    p = make_panel("cloudwatch")
    p._auth_mode_combo.setCurrentIndex(1)
    p.access_key_input.setText(" AKIA ")
    p.secret_key_input.setText("secret")
    assert p.profile_data() == {"region": p.region_combo.currentText(),
                                "access_key_id": "AKIA", "secret_key": "secret"}
    p._auth_mode_combo.setCurrentIndex(0)
    assert set(p.profile_data()) == {"region", "aws_profile"}
    cfg = {"group": "g", "stream": "s", "filter": "f", "interval": 5, "lookback": 60, "client": 1}
    assert p.profile_extra(cfg) == {"group": "g", "stream": "s", "filter": "f",
                                    "interval": 5, "lookback": 60}


def test_cloudwatch_load_profile_remembers_its_target_and_reconnects_later(make_panel):
    p = make_panel("cloudwatch")
    p.load_profile({"access_key_id": "AKIA", "secret_key": "s", "region": "eu-west-1",
                    "group": "/g", "stream": "s1"})
    assert p._saved_target == ("/g", "s1")
    with patch.object(p, "_restore_saved_target") as restore:
        p.connect_now()
        assert restore.call_count == 0          # deferred until the dialog is shown
        _wait_for(lambda: restore.called)
    restore.assert_called_once_with("/g", "s1")


def test_ssh_release_closes_its_own_connection(make_panel):
    p = make_panel("ssh")
    p.release()                                 # no connection: fine
    p._client = MagicMock()
    p.release()
    p._client.close.assert_called_once()


def test_ssh_release_survives_a_failing_close(make_panel):
    p = make_panel("ssh")
    p._client = MagicMock()
    p._client.close.side_effect = OSError("gone")
    p.release()


def test_ssh_connects_only_for_key_auth(make_panel):
    p = make_panel("ssh")
    with patch.object(p, "_on_connect") as connect:
        p._auth_combo.setCurrentIndex(1)       # password: the user has to type it first
        p.connect_now()
        assert not connect.called
        p._auth_combo.setCurrentIndex(0)
        p.connect_now()
        connect.assert_called_once()


# ── the dialog drives every panel through the contract ───────────────────────

@pytest.fixture
def dialog_env(tmp_path, monkeypatch, make_panel):
    import profiles_store
    monkeypatch.setattr(profiles_store, "_DIR", tmp_path)
    return tmp_path


@pytest.mark.parametrize("pid", IDS)
def test_dialog_embeds_every_provider(dialog_env, pid):
    import ui
    dlg = ui.AddConnectionDialog(preselect=pid)
    panel = dlg._embedded_panel
    assert isinstance(panel, providers.get(pid).panel_class())
    assert dlg._provider_id == pid
    assert ("name" in dlg._fields) is panel.saveable
    assert (dlg._save_open_btn is not None) is panel.saveable
    assert dlg._open_btn is not None and dlg._ready_timer.isActive()
    for w in panel._embedded_hidden():
        assert w.isHidden()
    dlg.reject()
    assert dlg._ready_timer is None


def test_dialog_footer_follows_the_panel(dialog_env):
    import ui
    dlg = ui.AddConnectionDialog(preselect="railway")
    p = dlg._embedded_panel
    dlg._sync_embedded_footer()
    assert not dlg._open_btn.isEnabled()
    p._open_btn_railway.setEnabled(True)
    dlg._sync_embedded_footer()
    assert dlg._open_btn.isEnabled() and not dlg._save_open_btn.isEnabled()   # needs a name
    dlg._fields["name"].setText("prod")
    assert dlg._save_open_btn.isEnabled()


def test_dialog_saves_credentials_extras_and_selection(dialog_env):
    import profiles_store
    import ui
    dlg = ui.AddConnectionDialog(preselect="railway")
    p = dlg._embedded_panel
    p._railway_token_input.setText("tok")
    p._interval_spin_railway.setValue(33)
    dlg._fields["name"].setText("prod")
    opened = []
    dlg.tab_requested.connect(lambda cfg, mode: opened.append((cfg, mode)))
    dlg._on_save_open()                       # nothing selected: the panel refuses to open
    assert opened == []
    p.open_tab.emit({"type": "railway"}, "tab")        # as if a service had been opened
    [saved] = profiles_store.load_all("railway")
    assert saved["name"] == "prod" and saved["token"] == "tok"
    assert saved["state"]["_interval_spin_railway"] == 33
    assert opened == [({"type": "railway"}, "tab")]


def test_dialog_open_without_saving_stores_nothing(dialog_env):
    import profiles_store
    import ui
    dlg = ui.AddConnectionDialog(preselect="railway")
    dlg._embedded_panel._railway_token_input.setText("tok")
    dlg._fields["name"].setText("prod")
    dlg._on_open()
    dlg._embedded_panel.open_tab.emit({"type": "railway"}, "tab")
    assert profiles_store.load_all("railway") == []


def test_dialog_adds_panel_extras_for_cloudwatch(dialog_env):
    import profiles_store
    import ui
    with patch("cloudwatch.list_profiles", return_value=[]):
        dlg = ui.AddConnectionDialog(preselect="cloudwatch")
    p = dlg._embedded_panel
    dlg._fields["name"].setText("aws")
    dlg._save_pending = True
    dlg._on_embedded_panel_tab(
        {"type": "cloudwatch", "group": "/g", "stream": "s", "filter": "F", "interval": 7,
         "lookback": 3600, "client": object()}, "tab")
    [saved] = profiles_store.load_all("cloudwatch")
    assert (saved["group"], saved["stream"], saved["filter"]) == ("/g", "s", "F")
    assert saved["region"] == p.region_combo.currentText()
    assert "state" not in saved            # CloudWatch restores group/stream, not widget state


def test_dialog_without_a_name_saves_nothing(dialog_env):
    import profiles_store
    import ui
    dlg = ui.AddConnectionDialog(preselect="railway")
    dlg._save_pending = True
    dlg._on_embedded_panel_tab({"type": "railway"}, "tab")
    assert profiles_store.load_all("railway") == []


def test_dialog_reopening_restores_the_selection_through_the_contract(dialog_env):
    import ui
    profile = {"name": "prod", "token": "tok",
               "state": {"_interval_spin_railway": 42}}
    with patch("panels.railway.RailwayPanel._do_connect", lambda self: None):
        dlg = ui.AddConnectionDialog(preselect="railway", prefill_profile=profile)
    p = dlg._embedded_panel
    assert p._railway_token_input.text() == "tok"
    assert dlg._restore_queue                      # waiting for the lists
    p._card_proj.setVisible(True)                  # "connected"
    dlg._pump_restore()
    assert p._interval_spin_railway.value() == 42 and dlg._restore_queue == []


def test_dialog_gives_up_restoring_after_the_deadline(dialog_env):
    import ui
    profile = {"name": "prod", "token": "t", "state": {"_project_list": "never-listed"}}
    with patch("panels.railway.RailwayPanel._do_connect", lambda self: None):
        dlg = ui.AddConnectionDialog(preselect="railway", prefill_profile=profile)
    dlg._embedded_panel._card_proj.setVisible(True)
    dlg._restore_ticks_left = 0
    dlg._pump_restore()
    dlg._pump_restore()
    assert dlg._restore_queue == []


def test_dialog_ignores_an_unknown_provider(dialog_env):
    import ui
    dlg = ui.AddConnectionDialog(preselect="martian")
    assert dlg._embedded_panel is None
    dlg._on_open()
    dlg._on_save_open()
    dlg._sync_embedded_footer()
    dlg.reject()


def test_provider_cards_come_from_the_registry(dialog_env):
    import ui
    dlg = ui.AddConnectionDialog()
    from PyQt6.QtWidgets import QLabel, QPushButton
    cards = [b for b in dlg.findChildren(QPushButton) if b.findChild(QLabel)]
    labels = {lbl.text() for b in cards for lbl in b.findChildren(QLabel)}
    assert {p.name for p in providers.PROVIDERS} <= labels
