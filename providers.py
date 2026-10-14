"""providers.py — the one place that describes every remote log source.

A ``Provider`` carries everything the app needs to know about a source: how it is
presented (name, icon, colours), which panel configures it, and how a saved / entered
configuration becomes a running log tab (``session``). Adding a source means adding
one entry to ``PROVIDERS`` (plus its panel and worker) — nothing else lists providers.
"""
from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import azure_utils
import gcp_utils
import i18n
import ssh_utils
from ui_theme import (
    _SVG_AZURE,
    _SVG_CLOUD,
    _SVG_CLOUDFLARE,
    _SVG_DATADOG,
    _SVG_DOCKER,
    _SVG_ELASTIC,
    _SVG_FLYIO,
    _SVG_GCP,
    _SVG_KUBERNETES,
    _SVG_LOKI,
    _SVG_RAILWAY,
    _SVG_SSH,
    _SVG_VERCEL,
    C_ACCENT,
    C_ERR,
    C_INFO,
    C_TRACE,
    C_TS,
)
from workers import (
    AzureWorker,
    CloudflareWorker,
    DatadogWorker,
    DockerComposeWorker,
    DockerContainerWorker,
    DockerExecFileWorker,
    ElasticWorker,
    FlyioWorker,
    GCPWorker,
    KubernetesWorker,
    LokiWorker,
    RailwayWorker,
    SSHWorker,
    TailWorker,
    VercelWorker,
)


@dataclass
class Session:
    """What a log tab needs: its worker, and how it is labelled."""

    worker: Any            # a started-later LogWorker
    source: str            # LogViewer source type (badge text / colour)
    title: str             # shown in the viewer's toolbar
    tab: str               # tab title


@dataclass(frozen=True)
class Provider:
    id: str
    name: str                   # as shown on the provider card
    icon: str                   # glyph of the card
    color: str                  # accent of the card
    svg: str                    # navigation icon
    description: str
    panel: str                  # "module:Class" of the configuration panel (imported lazily)
    session: Callable[[dict, Any], Session] = field(repr=False)
    source_color: str = ""      # colour of the source badge in a log viewer
    subtitle_key: str = ""      # saved-connection field shown next to its name
    cfg_types: tuple[str, ...] = ()           # cfg["type"] values it opens (default: its id)
    extra_sources: tuple[str, ...] = ()       # more LogViewer source types it produces
    # Sources that need a connection of their own to open a tab (a restored session has
    # none yet): builds it from the cfg, which carries a ready one under *client_key*.
    connect: Callable[[dict], Any] | None = field(default=None, repr=False)
    client_key: str = "_client"
    logo: str = ""              # bundled asset of the brand logo, e.g. "assets/providers/docker.svg"

    def describe(self) -> str:
        return i18n.tr(f"provider_desc_{self.id}")

    def panel_class(self) -> type:
        module, _, name = self.panel.partition(":")
        return getattr(importlib.import_module(module), name)

    def types(self) -> tuple[str, ...]:
        return self.cfg_types or (self.id,)


# ── Sessions: one cfg dict -> one worker + labels ─────────────────────────────

def _cloudwatch(cfg: dict, _client) -> Session:
    worker = TailWorker(
        cfg["client"], cfg["group"], cfg["stream"],
        cfg["filter"], cfg["interval"], cfg["lookback"],
    )
    stream_label = cfg["stream"] or "(all streams)"
    return Session(worker, "cloudwatch", f"{cfg['group']}  ›  {stream_label}",
                   (cfg["stream"] or cfg["group"]).split("/")[-1])


def _ssh(cfg: dict, client) -> Session:
    worker = SSHWorker(client, cfg["remote_path"], cfg.get("tail_lines", 100))
    return Session(worker, "ssh", f"{cfg['user']}@{cfg['host']}:{cfg['remote_path']}",
                   cfg["remote_path"].rsplit("/", 1)[-1] or cfg["host"])


def _ssh_connect(cfg: dict):
    return ssh_utils.make_client(
        cfg["host"], cfg["user"], cfg.get("port", 22),
        key_path=cfg.get("key_path") or None,
        password=cfg.get("password") or None,
    )


def _docker(cfg: dict, _client) -> Session:
    kind = cfg["type"]
    if kind == "docker_container":
        name = cfg.get("container_name", cfg["container_id"][:12])
        worker = DockerContainerWorker(cfg["container_id"], lookback_s=cfg.get("lookback_s", 3600))
        return Session(worker, "docker", f"docker  ›  {name}", name)
    if kind == "docker_compose":
        worker = DockerComposeWorker(cfg["project_name"], lookback_s=cfg.get("lookback_s", 3600))
        return Session(worker, "docker_compose", f"compose  ›  {cfg['project_name']}",
                       cfg["project_name"])
    worker = DockerExecFileWorker(cfg["container_id"], cfg["remote_path"], cfg.get("tail_lines", 100))
    return Session(worker, "docker_exec_file",
                   f"{cfg.get('container_name', '')}  ›  {cfg['remote_path']}",
                   cfg["remote_path"].rsplit("/", 1)[-1] or cfg.get("container_name", "docker"))


def _vercel(cfg: dict, _client) -> Session:
    worker = VercelWorker(
        cfg["token"], cfg["project_id"], cfg["project_name"],
        cfg["deployment_id"], interval_s=cfg.get("interval_s", 3),
        lookback_s=cfg.get("lookback_s", 3600),
    )
    return Session(worker, "vercel", f"vercel  ›  {cfg['project_name']}", cfg["project_name"])


def _gcp(cfg: dict, client) -> Session:
    worker = GCPWorker(
        client, cfg["project_id"],
        cfg.get("resource_type", "(all)"),
        cfg.get("severity", "ALL"),
        cfg.get("custom_filter", ""),
        lookback_s=cfg.get("lookback_s", 3600),
        interval_s=cfg.get("interval_s", 5),
    )
    return Session(worker, "gcp", f"gcp  ›  {cfg['project_id']}", cfg["project_id"])


def _gcp_connect(cfg: dict):
    return gcp_utils.make_client(cfg["project_id"], cfg.get("key_path") or None)


def _azure(cfg: dict, logs_client) -> Session:
    label = cfg.get("label", "azure")
    worker = AzureWorker(
        logs_client, cfg["workspace_id"], cfg["query"],
        label=label,
        lookback_s=cfg.get("lookback_s", 3600),
        interval_s=cfg.get("interval_s", 10),
    )
    return Session(worker, "azure", f"azure  ›  {label}", label)


def _azure_connect(cfg: dict):
    cred = azure_utils.make_credential(cfg["tenant_id"], cfg["client_id"], cfg["client_secret"])
    return azure_utils.make_logs_client(cred)


def _loki(cfg: dict, _client) -> Session:
    url = cfg["url"]
    auth = cfg.get("auth_mode", 0)
    label = cfg.get("label", url.split("//", 1)[-1].split("/")[0])
    worker = LokiWorker(
        url, cfg["query"],
        username=cfg.get("username", "") if auth == 1 else "",
        password=cfg.get("password", "") if auth == 1 else "",
        token=cfg.get("token", "") if auth == 2 else "",
        lookback_s=cfg.get("lookback_s", 3600),
        interval_s=cfg.get("interval_s", 5),
    )
    return Session(worker, "loki", f"loki  ›  {label}", label)


def _datadog(cfg: dict, _client) -> Session:
    label = cfg.get("label", cfg.get("base_url", "datadog"))
    worker = DatadogWorker(
        cfg["base_url"], cfg.get("query", "*"),
        cfg["api_key"], cfg["app_key"],
        lookback_s=cfg.get("lookback_s", 3600),
        interval_s=cfg.get("interval_s", 10),
    )
    return Session(worker, "datadog", f"datadog  ›  {label}", label)


def _elastic(cfg: dict, _client) -> Session:
    label = cfg.get("label", cfg.get("url", "elastic"))
    auth = cfg.get("auth_mode", 0)
    worker = ElasticWorker(
        cfg["url"], cfg["index"], cfg.get("query", "*"),
        api_key=cfg.get("api_key", "") if auth == 1 else "",
        username=cfg.get("username", "") if auth == 2 else "",
        password=cfg.get("password", "") if auth == 2 else "",
        ts_field=cfg.get("ts_field", "@timestamp"),
        lookback_s=cfg.get("lookback_s", 3600),
        interval_s=cfg.get("interval_s", 10),
    )
    return Session(worker, "elastic", f"elastic  ›  {label}", label)


def _railway(cfg: dict, _client) -> Session:
    label = cfg.get("label", cfg.get("service_name", "railway"))
    worker = RailwayWorker(
        cfg["token"], cfg["project_name"], cfg["service_name"],
        cfg["service_id"], interval_s=cfg.get("interval_s", 10),
        lookback_s=cfg.get("lookback_s", 3600),
    )
    return Session(worker, "railway", f"railway  ›  {label}", label)


def _flyio(cfg: dict, _client) -> Session:
    label = cfg.get("label", cfg.get("app_name", "fly.io"))
    worker = FlyioWorker(
        cfg["token"], cfg["app_name"],
        interval_s=cfg.get("interval_s", 5),
        lookback_s=cfg.get("lookback_s", 3600),
    )
    return Session(worker, "flyio", f"fly.io  ›  {label}", label)


def _kubernetes(cfg: dict, _client) -> Session:
    label = cfg.get("label", cfg.get("pod", "k8s"))
    worker = KubernetesWorker(
        cfg["pod"], cfg["namespace"],
        context=cfg.get("context", ""),
        container=cfg.get("container", ""),
        lookback_s=cfg.get("lookback_s", 3600),
    )
    return Session(worker, "kubernetes", f"k8s  ›  {label}", label)


def _cloudflare(cfg: dict, _client) -> Session:
    label = cfg.get("label", cfg.get("script_name", "worker"))
    worker = CloudflareWorker(cfg["api_token"], cfg["account_id"], cfg["script_name"])
    return Session(worker, "cloudflare", f"cloudflare  ›  {label}", label)


# ── The registry (order = order on the provider picker and in the saved list) ──

PROVIDERS: tuple[Provider, ...] = (
    Provider("cloudwatch", "AWS CloudWatch", "☁", "#ff9900", _SVG_CLOUD,
             "AWS CloudWatch Logs", "panels.cloudwatch:CloudWatchPanel", _cloudwatch,
             source_color=C_ACCENT, subtitle_key="region",
             logo="assets/providers/amazoncloudwatch.svg"),
    Provider("gcp", "Google Cloud", "⬡", "#4285f4", _SVG_GCP,
             "Google Cloud Logging", "panels.gcp:GCPPanel", _gcp,
             source_color=C_INFO, subtitle_key="project_id",
             connect=_gcp_connect,
             logo="assets/providers/googlecloud.svg"),
    Provider("azure", "Azure Monitor", "△", "#0078d4", _SVG_AZURE,
             "Azure Monitor / Log Analytics", "panels.azure:AzurePanel", _azure,
             source_color=C_ACCENT, subtitle_key="workspace_id",
             connect=_azure_connect, client_key="_logs_client",
             logo="assets/providers/microsoftazure.svg"),
    Provider("ssh", "SSH", "⌥", "#56cf80", _SVG_SSH,
             "Remote log files over SSH", "panels.ssh:SSHPanel", _ssh,
             source_color=C_TRACE, subtitle_key="host",
             connect=_ssh_connect,
             logo="assets/providers/ssh.svg"),
    Provider("docker", "Docker", "◈", "#2496ed", _SVG_DOCKER,
             "Remote Docker container logs", "panels.docker:DockerPanel", _docker,
             source_color=C_TS, subtitle_key="host",
             cfg_types=("docker_container", "docker_compose", "docker_exec_file"),
             extra_sources=("docker_compose", "docker_exec_file"),
             logo="assets/providers/docker.svg"),
    Provider("vercel", "Vercel", "▲", "#e2e2e2", _SVG_VERCEL,
             "Vercel deployment & runtime logs", "panels.vercel:VercelPanel", _vercel,
             source_color=C_ERR, subtitle_key="team",
             logo="assets/providers/vercel.svg"),
    Provider("loki", "Grafana Loki", "≡", "#f46800", _SVG_LOKI,
             "Grafana Loki log aggregation", "panels.loki:LokiPanel", _loki,
             source_color="#f46800",
             logo="assets/providers/grafana.svg"),
    Provider("datadog", "Datadog", "⬡", "#632ca6", _SVG_DATADOG,
             "Datadog Logs", "panels.datadog:DatadogPanel", _datadog,
             source_color="#632ca6",
             logo="assets/providers/datadog.svg"),
    Provider("elastic", "Elasticsearch", "⊙", "#f04e98", _SVG_ELASTIC,
             "Elasticsearch / OpenSearch", "panels.elastic:ElasticPanel", _elastic,
             source_color="#f04e98",
             logo="assets/providers/elasticsearch.svg"),
    Provider("railway", "Railway", "▣", "#b975f2", _SVG_RAILWAY,
             "Railway deployment logs", "panels.railway:RailwayPanel", _railway,
             source_color="#b975f2",
             logo="assets/providers/railway.svg"),
    Provider("flyio", "Fly.io", "⬥", "#7b3fc4", _SVG_FLYIO,
             "Fly.io app logs", "panels.flyio:FlyioPanel", _flyio,
             source_color="#7b3fc4",
             logo="assets/providers/flydotio.svg"),
    Provider("kubernetes", "Kubernetes", "⎈", "#326ce5", _SVG_KUBERNETES,
             "Kubernetes pod logs", "panels.kubernetes:KubernetesPanel", _kubernetes,
             source_color="#326ce5",
             logo="assets/providers/kubernetes.svg"),
    Provider("cloudflare", "Cloudflare", "⛅", "#f6821f", _SVG_CLOUDFLARE,
             "Cloudflare Workers real-time logs", "panels.cloudflare:CloudflarePanel", _cloudflare,
             source_color="#f6821f", subtitle_key="account_id",
             logo="assets/providers/cloudflare.svg"),
)

_BY_ID = {p.id: p for p in PROVIDERS}
_BY_TYPE = {t: p for p in PROVIDERS for t in p.types()}


def get(provider_id: str) -> Provider | None:
    return _BY_ID.get(provider_id)


def for_type(cfg_type: str) -> Provider | None:
    """The provider that opens configurations of this ``cfg["type"]``."""
    return _BY_TYPE.get(cfg_type)


def source_colors() -> dict[str, str]:
    """LogViewer source type -> badge colour, for every remote source."""
    colors = {}
    for p in PROVIDERS:
        for source in (p.id, *p.extra_sources):
            colors[source] = p.source_color
    return colors
