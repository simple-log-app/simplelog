"""i18n.py — Minimal EN / FR translation support for SimpleLog."""
from __future__ import annotations

import json
from pathlib import Path

_locale: str = "en"
_PREFS_PATH = Path.home() / ".config" / "simplelog" / "prefs.json"

# id(fn) -> callable — registered retranslate callbacks
_callbacks: dict[int, object] = {}


def register(key: int, fn: object) -> None:
    _callbacks[key] = fn


def unregister(key: int) -> None:
    _callbacks.pop(key, None)


def retranslate_all() -> None:
    for fn in list(_callbacks.values()):
        try:
            fn()  # type: ignore[operator]
        except Exception:
            pass


_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # ── Menu bar ──────────────────────────────────────────────────
        "menu_file":             "File",
        "menu_edit":             "Edit",
        "menu_language":         "Language",
        "menu_help":             "Help",
        "action_open":           "Open…",
        "action_close_all":      "Close All Logs",
        "action_update":         "Check for Updates",
        "action_quit":           "Quit",
        "action_copy":           "Copy",
        "action_break":          "Break",
        "lang_english":          "English",
        "lang_french":           "Français",
        "lang_german":           "Deutsch",
        "lang_spanish":          "Español",
        "lang_chinese":          "中文",
        "action_help_ref":       "CLI Reference",
        "action_about":          "About SimpleLog",
        # ── Help dialog ───────────────────────────────────────────────
        "help_title":            "CLI Reference — SimpleLog",
        "help_content": (
            "USAGE\n"
            "  simplelog [OPTIONS] [FILE ...]\n"
            "  command | simplelog [OPTIONS]\n"
            "\n"
            "ARGUMENTS\n"
            "  FILE ...          One or more log file paths.\n"
            "\n"
            "OPTIONS\n"
            "  --split MODE      How to open logs on startup.\n"
            "                    tab (default) | vertical | horizontal\n"
            "  --tail N          Lines to load from the end of each file (default: 100).\n"
            "\n"
            "KEYBOARD SHORTCUTS\n"
            "  Ctrl+F            Focus sidebar search\n"
            "  Ctrl+Shift+F      Toggle sidebar\n"
            "\n"
            "EXAMPLES\n"
            "  simplelog\n"
            "  simplelog /var/log/syslog\n"
            "  simplelog --tail 500 /var/log/nginx/access.log\n"
            "  simplelog --split vertical app.log error.log\n"
            "  journalctl -f | simplelog\n"
            "  kubectl logs -f my-pod | simplelog\n"
            "  docker logs -f my-container | simplelog\n"
        ),
        # ── Update dialog ─────────────────────────────────────────────
        "update_title":          "Check for Updates",
        "update_up_to_date":     "You are up to date  ({version}).",
        "update_available":      "Update available: {latest}\n\nCurrent version: {current}",
        "update_download":       "Download",
        "update_install":        "Install Update",
        "update_downloading":    "Downloading update…",
        "update_restarting":     "Update downloaded. The app will restart now.",
        "update_error":          "Could not check for updates:\n{error}",
        "update_install_error":  "Update failed:\n{error}",
        # ── Status bar ────────────────────────────────────────────────
        "status_ready":          "Ready",
        "history_loaded":        "History loaded: {n:,} events — tailing…",
        # ── Open-mode widget ──────────────────────────────────────────
        "open_as":               "Open as",
        "open_mode_tab":         "New tab",
        "open_mode_vertical":    "Split ↔  side by side",
        "open_mode_horizontal":  "Split ↕  top / bottom",
        # ── CloudWatch panel ──────────────────────────────────────────
        "cw_title":              "CloudWatch",
        "cw_card_connection":    "Connection",
        "cw_auth_mode":          "Auth mode",
        "cw_auth_profile":       "AWS Profile",
        "cw_auth_keys":          "Access Keys",
        "cw_field_profile":      "Profile",
        "cw_field_access_key":   "Access Key ID",
        "cw_field_secret_key":   "Secret Access Key",
        "cw_field_region":       "Region",
        "cw_connect":            "Connect",
        "cw_connecting":         "Connecting…",
        "cw_refresh":            "Refresh",
        "cw_card_groups":        "Log Groups",
        "cw_search_groups":      "Search groups…",
        "cw_card_streams":       "Log Streams",
        "cw_card_options":       "Options",
        "cw_field_lookback":     "Load history",
        "cw_field_poll":         "Poll interval",
        "field_time_range":      "Time range",
        "cw_field_filter":       "Filter pattern",
        "cw_filter_ph":          "CloudWatch filter pattern…",
        "cw_open":               "Open ↗",
        # ── File panel ────────────────────────────────────────────────
        "file_title":            "Log Files",
        "file_card_open":        "Open File",
        "file_desc":             "Browse your filesystem to open any log file.",
        "file_last_lines":       "Last lines:",
        "file_browse":           "Browse & Open ↗",
        "file_card_recent":      "Recent Files",
        "file_no_recent":        "No recent files",
        # ── LogViewer toolbar ─────────────────────────────────────────
        "viewer_autoscroll":     "Auto-scroll",
        "viewer_timestamps":     "Timestamps",
        "viewer_clear":          "Clear",
        "viewer_stop":           "Stop",
        "viewer_lines":          "{n:,} lines",
        # ── Sidebar ───────────────────────────────────────────────────────
        "sidebar_add_and":       "+ AND",
        "sidebar_add_or":        "+ OR",
        "sidebar_hits":          "{n:,} hits",
        "sidebar_no_hits":       "No results",
        "sidebar_term_ph":       "Term…",
        "sidebar_live_filter":   "Live",
        "sidebar_json_ph":       "Detected keys…",
        # ── Error / dialog messages ───────────────────────────────────
        "err_file_not_found":    "File not found",
        "err_cannot_open":       "Cannot open: {path}",
        "err_worker":            "Worker error",
        "err_connection":        "Connection error",
        "err_streams":           "Error loading streams",
        "err_prefix":            "Error: {msg}",
        # ── SSH panel ─────────────────────────────────────────────────
        "ssh_title":             "SSH Remote Logs",
        "ssh_card_connection":   "Connection",
        "ssh_field_host":        "Host",
        "ssh_field_port":        "Port",
        "ssh_field_user":        "Username",
        "ssh_auth_mode":         "Authentication",
        "ssh_auth_key":          "SSH Key",
        "ssh_auth_password":     "Password",
        "ssh_field_keypath":     "Key file",
        "ssh_field_password":    "Password",
        "ssh_browse_key":        "Browse…",
        "ssh_connect":           "Connect",
        "ssh_connecting":        "Connecting…",
        "ssh_connected":         "Connected ✓",
        "ssh_card_file":         "Remote File",
        "ssh_field_path":        "File path",
        "ssh_field_tail":        "Last lines",
        "ssh_browse_remote":     "Browse…",
        "ssh_open":              "Open ↗",
        "ssh_card_recent":       "Recent Connections",
        "ssh_no_recent":         "No recent connections",
        # ── Docker panel ──────────────────────────────────────────────
        "docker_title":          "Docker Logs",
        "docker_tab_containers": "Containers",
        "docker_tab_compose":    "Compose",
        "docker_tab_exec":       "File in Container",
        "docker_refresh":        "Refresh ↻",
        "docker_no_containers":  "No running containers",
        "docker_no_stacks":      "No compose projects found",
        "docker_not_available":  "Docker CLI not found in PATH.\nInstall Docker to use this feature.",
        "docker_field_tail":     "Last lines",
        "docker_field_path":     "File path in container",
        "docker_open_container": "Stream Logs ↗",
        "docker_open_stack":     "Stream Stack ↗",
        "docker_open_exec":      "Tail File ↗",
        # ── Vercel panel ──────────────────────────────────────────────
        "vercel_field_token":    "Paste your Vercel token",
        "vercel_connect":        "Connect",
        "vercel_connecting":     "Connecting…",
        "vercel_connected":      "Connected ✓",
        "vercel_card_project":   "Project",
        "vercel_refresh":        "Refresh ↻",
        "vercel_no_projects":    "No projects found",
        "vercel_card_deploy":    "Deployment",
        "vercel_target_prod":    "Production",
        "vercel_target_preview": "Preview",
        "vercel_target_any":     "Latest (any)",
        "vercel_field_interval": "Poll interval (s)",
        "vercel_open":           "Open Logs ↗",
        "vercel_no_deploy":      "No deployment found for this project",
        # ── GCP panel ─────────────────────────────────────────────────
        "gcp_auth_adc":          "Application Default Credentials",
        "gcp_auth_sa":           "Service Account Key",
        "gcp_field_keyfile":     "Key file (.json)",
        "gcp_browse_key":        "Browse…",
        "gcp_field_project":     "Project ID",
        "gcp_list_projects":     "List Projects ↻",
        "gcp_connect":           "Connect",
        "gcp_connecting":        "Connecting…",
        "gcp_connected":         "Connected ✓",
        "gcp_card_filter":       "Log Filter",
        "gcp_field_resource":    "Resource type",
        "gcp_field_severity":    "Min severity",
        "gcp_field_custom":      "Custom filter (optional)",
        "gcp_custom_hint":       "GCP filter syntax, e.g.  labels.app=\"my-service\"",
        "gcp_field_interval":    "Poll interval (s)",
        "gcp_open":              "Open Logs ↗",
        "gcp_no_projects":       "No projects found",
        # ── Azure panel ───────────────────────────────────────────────
        "azure_connect":         "Connect",
        "azure_connecting":      "Connecting…",
        "azure_connected":       "Connected ✓",
        "azure_tab_tables":      "Tables",
        "azure_tab_kql":         "KQL Query",
        "azure_card_table":      "Log Table",
        "azure_search_table":    "Search tables…",
        "azure_field_interval":  "Poll interval (s)",
        "azure_open_table":      "Open Table ↗",
        "azure_card_kql":        "KQL Query",
        "azure_kql_hint":        "Enter a KQL query. TimeGenerated filter is added automatically when polling.",
        "azure_open_kql":        "Run Query ↗",
        # ── Grafana Loki ──────────────────────────────────────────────
        "loki_auth_none":        "No authentication",
        "loki_auth_basic":       "Basic auth",
        "loki_auth_token":       "Bearer token",
        "loki_field_url":        "Loki URL",
        "loki_field_username":   "Username",
        "loki_field_password":   "Password",
        "loki_field_token":      "Bearer token",
        "loki_connect":          "Connect",
        "loki_connecting":       "Connecting…",
        "loki_connected":        "Connected ✓",
        "loki_card_query":       "Query",
        "loki_field_query":      "LogQL query",
        "loki_query_hint":       "{app=\"myapp\"} |= \"error\"",
        "loki_list_labels":      "Labels ↻",
        "loki_field_interval":   "Poll interval (s)",
        "loki_open":             "Open Logs ↗",
        "loki_no_labels":        "No labels found",
        # ── Datadog ───────────────────────────────────────────────────
        "datadog_field_site":    "Site",
        "datadog_field_api_key": "API Key",
        "datadog_field_app_key": "Application Key",
        "datadog_connect":       "Connect",
        "datadog_connecting":    "Connecting…",
        "datadog_connected":     "Connected ✓",
        "datadog_card_query":    "Query",
        "datadog_field_query":   "Log query",
        "datadog_query_hint":    "service:myapp status:error",
        "datadog_field_interval":"Poll interval (s)",
        "datadog_open":          "Open Logs ↗",
        # ── Elasticsearch ─────────────────────────────────────────────
        "elastic_auth_none":     "No authentication",
        "elastic_auth_apikey":   "API Key",
        "elastic_auth_basic":    "Basic auth",
        "elastic_field_url":     "Elasticsearch URL",
        "elastic_field_apikey":  "API Key",
        "elastic_field_username":"Username",
        "elastic_field_password":"Password",
        "elastic_connect":       "Connect",
        "elastic_connecting":    "Connecting…",
        "elastic_connected":     "Connected ✓",
        "elastic_card_query":    "Query",
        "elastic_field_index":   "Index",
        "elastic_field_ts":      "Timestamp field",
        "elastic_field_query":   "Query string",
        "elastic_query_hint":    "level:ERROR AND service:myapp",
        "elastic_field_interval":"Poll interval (s)",
        "elastic_open":          "Open Logs ↗",
        "elastic_no_indices":    "No indices found",
        # ── Railway ───────────────────────────────────────────────────
        "railway_field_token":   "API Token",
        "railway_connect":       "Connect",
        "railway_connecting":    "Connecting…",
        "railway_connected":     "Connected ✓",
        "railway_card_project":  "Project",
        "railway_no_projects":   "No projects found",
        "railway_card_service":  "Service",
        "railway_no_services":   "No services found",
        "railway_field_interval":"Poll interval (s)",
        "railway_open":          "Open Logs ↗",
        # ── Fly.io ────────────────────────────────────────────────────
        "flyio_field_token":     "API Token",
        "flyio_connect":         "Connect",
        "flyio_connecting":      "Connecting…",
        "flyio_connected":       "Connected ✓",
        "flyio_card_app":        "Application",
        "flyio_no_apps":         "No apps found",
        "flyio_field_interval":  "Poll interval (s)",
        "flyio_open":            "Open Logs ↗",
        # ── Kubernetes ────────────────────────────────────────────────
        "kubernetes_not_available": "kubectl not found. Install kubectl and ensure it is in PATH.",
        "kubernetes_card_cluster":"Cluster",
        "kubernetes_field_context":"Context",
        "kubernetes_field_ns":   "Namespace",
        "kubernetes_connect":    "Connect",
        "kubernetes_connecting": "Connecting…",
        "kubernetes_connected":  "Connected ✓",
        "kubernetes_card_pod":   "Pod",
        "kubernetes_no_ns":      "No namespaces found",
        "kubernetes_no_pods":    "No pods found",
        "kubernetes_field_container": "Container (optional)",
        "kubernetes_open":       "Stream Logs ↗",
        # ── Cloudflare Workers ────────────────────────────────────────
        "cf_field_token":        "API Token",
        "cf_field_account_id":   "Account ID",
        "cf_connect":            "Connect",
        "cf_connecting":         "Connecting…",
        "cf_connected":          "Connected ✓",
        "cf_card_workers":       "Workers",
        "cf_no_workers":         "No workers found in this account",
        "cf_missing_fields":     "API token and Account ID are required",
        "cf_open":               "Tail Logs ↗",
        # ── Credential storage ────────────────────────────────────────
        # ── Remote panel ─────────────────────────────────────────────
        "remote_title":          "Remote Sources",
        "remote_dialog_title":   "Add Remote Source",
        "remote_dialog_header":  "Add Remote",
        "remote_back":               "← Back",
        "remote_choose":             "Choose a provider",
        "remote_open":               "Open",
        "remote_add_connection":     "+ Add connection",
        "remote_no_connections":     "No remote connections",
        "remote_no_connections_sub": "Click Add to connect a provider",
        "remote_save_open":          "Save && Open",
        "remote_cancel":             "Cancel",
        "remote_select_provider":    "Select a provider to configure",
        "remote_new_connection":     "New connection",
        "remote_connection_name":    "Connection name",
        "remote_add_btn":            "+ Add",
        "remote_add_title":          "Add Connection",
        "remote_add_header":         "Add remote connection",
        "saved_configs":             "Saved configurations",
        "new_config":                "New configuration",
        "help_dialog_title":         "Configuration guide",
        "help_dialog_close":         "Close",
        # ── Provider help content ──────────────────────────────────────
        "help_cloudwatch": (
            "<h3>AWS CloudWatch</h3>"
            "<p><b>Option 1 — AWS Profile (recommended)</b><br>"
            "Select <em>AWS Profile</em> and choose a profile from <code>~/.aws/credentials</code>.</p>"
            "<p><b>Option 2 — Manual keys</b></p>"
            "<ol><li>AWS Console → <b>IAM → Users → your user → Security credentials</b></li>"
            "<li>Click <b>Create access key</b></li>"
            "<li>Copy <b>Access Key ID</b> and <b>Secret Access Key</b>, choose your <b>Region</b></li></ol>"
            "<p>Required permissions: <code>logs:DescribeLogGroups</code>, <code>logs:FilterLogEvents</code></p>"
        ),
        "help_ssh": (
            "<h3>SSH — Remote file</h3>"
            "<p>Fill in the connection fields:</p>"
            "<ul><li><b>Host</b>: server IP or hostname</li>"
            "<li><b>Port</b>: usually <code>22</code></li>"
            "<li><b>User</b>: your SSH username</li>"
            "<li><b>SSH Key</b>: path to your private key (e.g. <code>~/.ssh/id_rsa</code>)</li>"
            "<li><b>Remote path</b>: full path to the log file (e.g. <code>/var/log/app.log</code>)</li></ul>"
            "<p>To allow key auth on a server: <code>ssh-copy-id -i ~/.ssh/id_rsa.pub user@host</code></p>"
        ),
        "help_docker": (
            "<h3>Docker</h3>"
            "<p>Docker must be running on this machine. No credentials needed.</p>"
            "<p><b>Containers tab</b>: select a running container to stream its logs (like <code>docker logs -f</code>).</p>"
            "<p><b>Compose tab</b>: select a Docker Compose project to stream logs from all its services.</p>"
            "<p><b>Exec tab</b>: pick a container and a file path inside it to tail.</p>"
        ),
        "help_vercel": (
            "<h3>Vercel</h3>"
            "<p><b>Get your API token:</b></p>"
            "<ol><li>Go to <b>vercel.com → Account Settings → Tokens</b></li>"
            "<li>Click <b>Create Token</b>, give it a name</li>"
            "<li>Paste the token in SimpleLog and click <b>Connect</b></li></ol>"
            "<p>Then select your <b>project</b> and a <b>deployment</b> to stream its runtime logs.</p>"
        ),
        "help_gcp": (
            "<h3>GCP Cloud Logging</h3>"
            "<p><b>Create a Service Account key:</b></p>"
            "<ol><li>GCP Console → <b>IAM &amp; Admin → Service Accounts</b></li>"
            "<li>Select or create a service account with role <b>Logging → Logs Viewer</b></li>"
            "<li>Tab <b>Keys → Add Key → JSON</b> → download the file</li></ol>"
            "<p>In SimpleLog:</p>"
            "<ul><li><b>Credentials file</b>: path to the downloaded JSON file</li>"
            "<li><b>Project ID</b>: visible in the GCP console header (e.g. <code>my-project-123</code>)</li></ul>"
        ),
        "help_azure": (
            "<h3>Azure Monitor</h3>"
            "<p><b>1. Get your Workspace ID:</b><br>"
            "Log Analytics Workspace → <b>Settings → Agents</b> → copy <b>Workspace ID</b></p>"
            "<p><b>2. Create an App Registration:</b></p>"
            "<ol><li>Azure Active Directory → <b>App registrations → New registration</b></li>"
            "<li>Copy <b>Application (client) ID</b> and <b>Directory (tenant) ID</b></li>"
            "<li><b>Certificates &amp; secrets → New client secret</b> → copy the <b>Value</b></li>"
            "<li>In your workspace: <b>Access control (IAM) → Add role → Log Analytics Reader</b>, assign to this app</li></ol>"
            "<p><b>In SimpleLog:</b> fill Workspace ID, Tenant ID, Client ID, Client Secret, then enter a KQL query.</p>"
        ),
        "help_loki": (
            "<h3>Grafana Loki</h3>"
            "<p><b>Self-hosted / local:</b> just enter the URL (e.g. <code>http://localhost:3100</code>). No credentials needed.</p>"
            "<p><b>Grafana Cloud:</b></p>"
            "<ol><li>Go to your Grafana Cloud stack → <b>Connections → Data sources → Loki</b></li>"
            "<li>Copy the <b>URL</b>, <b>User</b> and generate a token under <b>Access Policies</b></li></ol>"
            "<p><b>Query (LogQL):</b> e.g. <code>{app=\"my-app\"}</code> or leave empty to see all streams.</p>"
        ),
        "help_datadog": (
            "<h3>Datadog</h3>"
            "<p><b>Get your API key:</b><br>"
            "Organization Settings → <b>API Keys → New Key</b> → copy it</p>"
            "<p><b>Get your Application key:</b><br>"
            "Organization Settings → <b>Application Keys → New Key</b> → copy it</p>"
            "<p><b>In SimpleLog:</b> select your site (e.g. US1), paste both keys, optionally add a query filter (e.g. <code>service:api</code>).</p>"
        ),
        "help_elastic": (
            "<h3>Elasticsearch</h3>"
            "<p><b>Self-hosted / local:</b> enter URL (e.g. <code>http://localhost:9200</code>) and index name. No credentials needed if security is disabled.</p>"
            "<p><b>Elastic Cloud:</b></p>"
            "<ol><li>Go to your deployment → <b>Security → API Keys → Create API key</b></li>"
            "<li>Or use username/password</li></ol>"
            "<p><b>In SimpleLog:</b> fill URL, Index (e.g. <code>logs-*</code>), and credentials if required.</p>"
        ),
        "help_railway": (
            "<h3>Railway</h3>"
            "<p><b>Get your token:</b></p>"
            "<ol><li>Railway dashboard → <b>Account Settings → Tokens → Create Token</b></li>"
            "<li>Paste the token in SimpleLog and click <b>Connect</b></li></ol>"
            "<p>Then select your <b>project</b> and <b>service</b> to stream its logs.</p>"
        ),
        "help_flyio": (
            "<h3>Fly.io</h3>"
            "<p><b>Get your token:</b></p>"
            "<ol><li>Install the CLI: <code>curl -L https://fly.io/install.sh | sh</code></li>"
            "<li>Log in: <code>fly auth login</code></li>"
            "<li>Get your token: <code>fly auth token</code></li>"
            "<li>Paste the output in SimpleLog and click <b>Connect</b></li></ol>"
            "<p>Then select your <b>app</b> to stream its logs.</p>"
        ),
        "help_kubernetes": (
            "<h3>Kubernetes</h3>"
            "<p>SimpleLog reads your existing <code>~/.kube/config</code>. No credentials to enter.</p>"
            "<p><b>Steps:</b></p>"
            "<ol><li>Select a <b>context</b> (cluster)</li>"
            "<li>Select a <b>namespace</b></li>"
            "<li>Click <b>Connect</b> to load the pod list</li>"
            "<li>Select a <b>pod</b> to stream its logs</li></ol>"
        ),
        "help_cloudflare": (
            "<h3>Cloudflare Workers</h3>"
            "<p><b>Get your Account ID:</b><br>"
            "Log in to <b>dash.cloudflare.com</b> → select any domain → the Account ID is shown in the right sidebar (32 hex chars).</p>"
            "<p><b>Create an API Token:</b></p>"
            "<ol><li><b>My Profile → API Tokens → Create Token → Custom Token</b></li>"
            "<li>Add these permissions:<br>"
            "— Account → <b>Workers Scripts : Read</b><br>"
            "— Account → <b>Workers Tail : Read</b><br>"
            "— User → <b>User Details : Read</b></li>"
            "<li>Copy the generated token</li></ol>"
            "<p>Paste both the Account ID and token in SimpleLog, then click <b>Connect</b> and select a Worker.</p>"
        ),
    },
    "fr": {
        # ── Menu bar ──────────────────────────────────────────────────
        "menu_file":             "Fichier",
        "menu_edit":             "Édition",
        "menu_language":         "Langage",
        "menu_help":             "Aide",
        "action_open":           "Ouvrir…",
        "action_close_all":      "Fermer tous les logs",
        "action_update":         "Mettre à jour",
        "action_quit":           "Quitter",
        "action_copy":           "Copier",
        "action_break":          "Break",
        "lang_english":          "English",
        "lang_french":           "Français",
        "lang_german":           "Deutsch",
        "lang_spanish":          "Español",
        "lang_chinese":          "中文",
        "action_help_ref":       "Référence CLI",
        "action_about":          "À propos de SimpleLog",
        # ── Help dialog ───────────────────────────────────────────────
        "help_title":            "Référence CLI — SimpleLog",
        "help_content": (
            "UTILISATION\n"
            "  simplelog [OPTIONS] [FICHIER ...]\n"
            "  commande | simplelog [OPTIONS]\n"
            "\n"
            "ARGUMENTS\n"
            "  FICHIER ...       Un ou plusieurs chemins de fichiers de log.\n"
            "\n"
            "OPTIONS\n"
            "  --split MODE      Disposition à l'ouverture.\n"
            "                    tab (défaut) | vertical | horizontal\n"
            "  --tail N          Lignes à charger depuis la fin du fichier (défaut : 100).\n"
            "\n"
            "RACCOURCIS CLAVIER\n"
            "  Ctrl+F            Activer la recherche dans la sidebar\n"
            "  Ctrl+Shift+F      Afficher / masquer la sidebar\n"
            "\n"
            "EXEMPLES\n"
            "  simplelog\n"
            "  simplelog /var/log/syslog\n"
            "  simplelog --tail 500 /var/log/nginx/access.log\n"
            "  simplelog --split vertical app.log error.log\n"
            "  journalctl -f | simplelog\n"
            "  kubectl logs -f my-pod | simplelog\n"
            "  docker logs -f my-container | simplelog\n"
        ),
        # ── Update dialog ─────────────────────────────────────────────
        "update_title":          "Mise à jour",
        "update_up_to_date":     "L'application est à jour  ({version}).",
        "update_available":      "Mise à jour disponible : {latest}\n\nVersion actuelle : {current}",
        "update_download":       "Télécharger",
        "update_install":        "Installer la mise à jour",
        "update_downloading":    "Téléchargement de la mise à jour…",
        "update_restarting":     "Mise à jour téléchargée. L'application va redémarrer.",
        "update_error":          "Impossible de vérifier les mises à jour :\n{error}",
        "update_install_error":  "Échec de la mise à jour :\n{error}",
        # ── Status bar ────────────────────────────────────────────────
        "status_ready":          "Prêt",
        "history_loaded":        "Historique chargé : {n:,} événements — surveillance…",
        # ── Open-mode widget ──────────────────────────────────────────
        "open_as":               "Ouvrir comme",
        "open_mode_tab":         "Nouvel onglet",
        "open_mode_vertical":    "Split ↔  côte à côte",
        "open_mode_horizontal":  "Split ↕  haut / bas",
        # ── CloudWatch panel ──────────────────────────────────────────
        "cw_title":              "CloudWatch",
        "cw_card_connection":    "Connexion",
        "cw_auth_mode":          "Mode d'auth",
        "cw_auth_profile":       "Profil AWS",
        "cw_auth_keys":          "Clés d'accès",
        "cw_field_profile":      "Profil",
        "cw_field_access_key":   "Access Key ID",
        "cw_field_secret_key":   "Secret Access Key",
        "cw_field_region":       "Région",
        "cw_connect":            "Connecter",
        "cw_connecting":         "Connexion…",
        "cw_refresh":            "Actualiser",
        "cw_card_groups":        "Groupes de logs",
        "cw_search_groups":      "Rechercher…",
        "cw_card_streams":       "Flux de logs",
        "cw_card_options":       "Options",
        "cw_field_lookback":     "Historique",
        "cw_field_poll":         "Intervalle",
        "field_time_range":      "Plage de temps",
        "cw_field_filter":       "Filtre",
        "cw_filter_ph":          "Filtre CloudWatch…",
        "cw_open":               "Ouvrir ↗",
        # ── File panel ────────────────────────────────────────────────
        "file_title":            "Fichiers de logs",
        "file_card_open":        "Ouvrir un fichier",
        "file_desc":             "Parcourez votre système de fichiers pour ouvrir un fichier de log.",
        "file_last_lines":       "Dernières lignes :",
        "file_browse":           "Parcourir & Ouvrir ↗",
        "file_card_recent":      "Fichiers récents",
        "file_no_recent":        "Aucun fichier récent",
        # ── LogViewer toolbar ─────────────────────────────────────────
        "viewer_autoscroll":     "Défilement auto",
        "viewer_timestamps":     "Timestamps",
        "viewer_clear":          "Effacer",
        "viewer_stop":           "Arrêter",
        "viewer_lines":          "{n:,} lignes",
        # ── Sidebar ───────────────────────────────────────────────────────
        "sidebar_add_and":       "+ ET",
        "sidebar_add_or":        "+ OU",
        "sidebar_hits":          "{n:,} résultats",
        "sidebar_no_hits":       "Aucun résultat",
        "sidebar_term_ph":       "Terme…",
        "sidebar_live_filter":   "En direct",
        "sidebar_json_ph":       "Clés détectées…",
        # ── Error / dialog messages ───────────────────────────────────
        "err_file_not_found":    "Fichier introuvable",
        "err_cannot_open":       "Impossible d'ouvrir : {path}",
        "err_worker":            "Erreur worker",
        "err_connection":        "Erreur de connexion",
        "err_streams":           "Erreur lors du chargement des flux",
        "err_prefix":            "Erreur : {msg}",
        # ── SSH panel ─────────────────────────────────────────────────
        "ssh_title":             "Logs SSH distants",
        "ssh_card_connection":   "Connexion",
        "ssh_field_host":        "Hôte",
        "ssh_field_port":        "Port",
        "ssh_field_user":        "Utilisateur",
        "ssh_auth_mode":         "Authentification",
        "ssh_auth_key":          "Clé SSH",
        "ssh_auth_password":     "Mot de passe",
        "ssh_field_keypath":     "Fichier de clé",
        "ssh_field_password":    "Mot de passe",
        "ssh_browse_key":        "Parcourir…",
        "ssh_connect":           "Connecter",
        "ssh_connecting":        "Connexion…",
        "ssh_connected":         "Connecté ✓",
        "ssh_card_file":         "Fichier distant",
        "ssh_field_path":        "Chemin du fichier",
        "ssh_field_tail":        "Dernières lignes",
        "ssh_browse_remote":     "Parcourir…",
        "ssh_open":              "Ouvrir ↗",
        "ssh_card_recent":       "Connexions récentes",
        "ssh_no_recent":         "Aucune connexion récente",
        # ── Docker panel ──────────────────────────────────────────────
        "docker_title":          "Logs Docker",
        "docker_tab_containers": "Conteneurs",
        "docker_tab_compose":    "Compose",
        "docker_tab_exec":       "Fichier dans conteneur",
        "docker_refresh":        "Actualiser ↻",
        "docker_no_containers":  "Aucun conteneur en cours",
        "docker_no_stacks":      "Aucun projet Compose trouvé",
        "docker_not_available":  "Docker CLI introuvable dans le PATH.\nInstallez Docker pour utiliser cette fonctionnalité.",
        "docker_field_tail":     "Dernières lignes",
        "docker_field_path":     "Chemin du fichier dans le conteneur",
        "docker_open_container": "Streamer les logs ↗",
        "docker_open_stack":     "Streamer la stack ↗",
        "docker_open_exec":      "Suivre le fichier ↗",
        # ── Vercel panel ──────────────────────────────────────────────
        "vercel_field_token":    "Collez votre jeton Vercel",
        "vercel_connect":        "Connexion",
        "vercel_connecting":     "Connexion…",
        "vercel_connected":      "Connecté ✓",
        "vercel_card_project":   "Projet",
        "vercel_refresh":        "Actualiser ↻",
        "vercel_no_projects":    "Aucun projet trouvé",
        "vercel_card_deploy":    "Déploiement",
        "vercel_target_prod":    "Production",
        "vercel_target_preview": "Aperçu",
        "vercel_target_any":     "Dernier (tous)",
        "vercel_field_interval": "Intervalle de sondage (s)",
        "vercel_open":           "Ouvrir les logs ↗",
        "vercel_no_deploy":      "Aucun déploiement trouvé pour ce projet",
        # ── GCP panel ─────────────────────────────────────────────────
        "gcp_auth_adc":          "Identifiants par défaut (ADC)",
        "gcp_auth_sa":           "Clé de compte de service",
        "gcp_field_keyfile":     "Fichier de clé (.json)",
        "gcp_browse_key":        "Parcourir…",
        "gcp_field_project":     "ID du projet",
        "gcp_list_projects":     "Lister les projets ↻",
        "gcp_connect":           "Connexion",
        "gcp_connecting":        "Connexion…",
        "gcp_connected":         "Connecté ✓",
        "gcp_card_filter":       "Filtre de logs",
        "gcp_field_resource":    "Type de ressource",
        "gcp_field_severity":    "Sévérité minimale",
        "gcp_field_custom":      "Filtre personnalisé (optionnel)",
        "gcp_custom_hint":       "Syntaxe GCP, ex. labels.app=\"mon-service\"",
        "gcp_field_interval":    "Intervalle de sondage (s)",
        "gcp_open":              "Ouvrir les logs ↗",
        "gcp_no_projects":       "Aucun projet trouvé",
        # ── Azure panel ───────────────────────────────────────────────
        "azure_connect":         "Connexion",
        "azure_connecting":      "Connexion…",
        "azure_connected":       "Connecté ✓",
        "azure_tab_tables":      "Tables",
        "azure_tab_kql":         "Requête KQL",
        "azure_card_table":      "Table de logs",
        "azure_search_table":    "Rechercher une table…",
        "azure_field_interval":  "Intervalle de sondage (s)",
        "azure_open_table":      "Ouvrir la table ↗",
        "azure_card_kql":        "Requête KQL",
        "azure_kql_hint":        "Entrez une requête KQL. Le filtre TimeGenerated est ajouté automatiquement.",
        "azure_open_kql":        "Exécuter ↗",
        # ── Grafana Loki ──────────────────────────────────────────────
        "loki_auth_none":        "Sans authentification",
        "loki_auth_basic":       "Auth basique",
        "loki_auth_token":       "Token Bearer",
        "loki_field_url":        "URL Loki",
        "loki_field_username":   "Nom d'utilisateur",
        "loki_field_password":   "Mot de passe",
        "loki_field_token":      "Token Bearer",
        "loki_connect":          "Connexion",
        "loki_connecting":       "Connexion…",
        "loki_connected":        "Connecté ✓",
        "loki_card_query":       "Requête",
        "loki_field_query":      "Requête LogQL",
        "loki_query_hint":       "{app=\"myapp\"} |= \"error\"",
        "loki_list_labels":      "Labels ↻",
        "loki_field_interval":   "Intervalle (s)",
        "loki_open":             "Ouvrir les logs ↗",
        "loki_no_labels":        "Aucun label trouvé",
        # ── Datadog ───────────────────────────────────────────────────
        "datadog_field_site":    "Site",
        "datadog_field_api_key": "Clé API",
        "datadog_field_app_key": "Clé Application",
        "datadog_connect":       "Connexion",
        "datadog_connecting":    "Connexion…",
        "datadog_connected":     "Connecté ✓",
        "datadog_card_query":    "Requête",
        "datadog_field_query":   "Requête de logs",
        "datadog_query_hint":    "service:myapp status:error",
        "datadog_field_interval":"Intervalle (s)",
        "datadog_open":          "Ouvrir les logs ↗",
        # ── Elasticsearch ─────────────────────────────────────────────
        "elastic_auth_none":     "Sans authentification",
        "elastic_auth_apikey":   "Clé API",
        "elastic_auth_basic":    "Auth basique",
        "elastic_field_url":     "URL Elasticsearch",
        "elastic_field_apikey":  "Clé API",
        "elastic_field_username":"Nom d'utilisateur",
        "elastic_field_password":"Mot de passe",
        "elastic_connect":       "Connexion",
        "elastic_connecting":    "Connexion…",
        "elastic_connected":     "Connecté ✓",
        "elastic_card_query":    "Requête",
        "elastic_field_index":   "Index",
        "elastic_field_ts":      "Champ timestamp",
        "elastic_field_query":   "Requête",
        "elastic_query_hint":    "level:ERROR AND service:myapp",
        "elastic_field_interval":"Intervalle (s)",
        "elastic_open":          "Ouvrir les logs ↗",
        "elastic_no_indices":    "Aucun index trouvé",
        # ── Railway ───────────────────────────────────────────────────
        "railway_field_token":   "Token API",
        "railway_connect":       "Connexion",
        "railway_connecting":    "Connexion…",
        "railway_connected":     "Connecté ✓",
        "railway_card_project":  "Projet",
        "railway_no_projects":   "Aucun projet trouvé",
        "railway_card_service":  "Service",
        "railway_no_services":   "Aucun service trouvé",
        "railway_field_interval":"Intervalle (s)",
        "railway_open":          "Ouvrir les logs ↗",
        # ── Fly.io ────────────────────────────────────────────────────
        "flyio_field_token":     "Token API",
        "flyio_connect":         "Connexion",
        "flyio_connecting":      "Connexion…",
        "flyio_connected":       "Connecté ✓",
        "flyio_card_app":        "Application",
        "flyio_no_apps":         "Aucune app trouvée",
        "flyio_field_interval":  "Intervalle (s)",
        "flyio_open":            "Ouvrir les logs ↗",
        # ── Kubernetes ────────────────────────────────────────────────
        "kubernetes_not_available": "kubectl introuvable. Installez kubectl et vérifiez le PATH.",
        "kubernetes_card_cluster":"Cluster",
        "kubernetes_field_context":"Contexte",
        "kubernetes_field_ns":   "Namespace",
        "kubernetes_connect":    "Connexion",
        "kubernetes_connecting": "Connexion…",
        "kubernetes_connected":  "Connecté ✓",
        "kubernetes_card_pod":   "Pod",
        "kubernetes_no_ns":      "Aucun namespace trouvé",
        "kubernetes_no_pods":    "Aucun pod trouvé",
        "kubernetes_field_container": "Conteneur (optionnel)",
        "kubernetes_open":       "Diffuser les logs ↗",
        # ── Cloudflare Workers ────────────────────────────────────────
        "cf_field_token":        "Token API",
        "cf_field_account_id":   "ID de compte",
        "cf_connect":            "Connexion",
        "cf_connecting":         "Connexion…",
        "cf_connected":          "Connecté ✓",
        "cf_card_workers":       "Workers",
        "cf_no_workers":         "Aucun worker trouvé dans ce compte",
        "cf_missing_fields":     "Le token API et l'ID de compte sont requis",
        "cf_open":               "Suivre les logs ↗",
        # ── Credential storage ────────────────────────────────────────
        # ── Remote panel ─────────────────────────────────────────────
        "remote_title":          "Sources distantes",
        "remote_dialog_title":   "Ajouter une source distante",
        "remote_dialog_header":  "Ajouter une source",
        "remote_back":               "← Retour",
        "remote_choose":             "Choisir un fournisseur",
        "remote_open":               "Ouvrir",
        "remote_add_connection":     "+ Ajouter une connexion",
        "remote_no_connections":     "Aucune connexion distante",
        "remote_no_connections_sub": "Cliquez sur Ajouter pour connecter un fournisseur",
        "remote_save_open":          "Enregistrer && Ouvrir",
        "remote_cancel":             "Annuler",
        "remote_select_provider":    "Sélectionnez un fournisseur",
        "remote_new_connection":     "Nouvelle connexion",
        "remote_connection_name":    "Nom de la connexion",
        "remote_add_btn":            "+ Ajouter",
        "remote_add_title":          "Ajouter une connexion",
        "remote_add_header":         "Ajouter une connexion distante",
        "saved_configs":             "Configurations enregistrées",
        "new_config":                "Nouvelle configuration",
        "help_dialog_title":         "Guide de configuration",
        "help_dialog_close":         "Fermer",
        # ── Aide providers ────────────────────────────────────────────
        "help_cloudwatch": (
            "<h3>AWS CloudWatch</h3>"
            "<p><b>Option 1 — Profil AWS (recommandé)</b><br>"
            "Sélectionnez <em>Profil AWS</em> et choisissez un profil configuré dans <code>~/.aws/credentials</code>.</p>"
            "<p><b>Option 2 — Clés manuelles</b></p>"
            "<ol><li>Console AWS → <b>IAM → Users → votre utilisateur → Security credentials</b></li>"
            "<li>Cliquez <b>Create access key</b></li>"
            "<li>Copiez l'<b>Access Key ID</b> et le <b>Secret Access Key</b>, choisissez votre <b>Région</b></li></ol>"
            "<p>Permissions requises : <code>logs:DescribeLogGroups</code>, <code>logs:FilterLogEvents</code></p>"
        ),
        "help_ssh": (
            "<h3>SSH — Fichier distant</h3>"
            "<p>Remplissez les champs de connexion :</p>"
            "<ul><li><b>Host</b> : IP ou hostname du serveur</li>"
            "<li><b>Port</b> : généralement <code>22</code></li>"
            "<li><b>User</b> : votre nom d'utilisateur SSH</li>"
            "<li><b>SSH Key</b> : chemin vers votre clé privée (ex. <code>~/.ssh/id_rsa</code>)</li>"
            "<li><b>Remote path</b> : chemin complet vers le fichier de log (ex. <code>/var/log/app.log</code>)</li></ul>"
            "<p>Pour autoriser la clé sur le serveur : <code>ssh-copy-id -i ~/.ssh/id_rsa.pub user@host</code></p>"
        ),
        "help_docker": (
            "<h3>Docker</h3>"
            "<p>Docker doit être en cours d'exécution. Aucun identifiant requis.</p>"
            "<p><b>Onglet Containers</b> : sélectionnez un container pour voir ses logs en temps réel (équivalent de <code>docker logs -f</code>).</p>"
            "<p><b>Onglet Compose</b> : sélectionnez un projet Docker Compose pour voir les logs de tous ses services.</p>"
            "<p><b>Onglet Exec</b> : choisissez un container et un chemin de fichier à l'intérieur pour le surveiller.</p>"
        ),
        "help_vercel": (
            "<h3>Vercel</h3>"
            "<p><b>Obtenir votre token API :</b></p>"
            "<ol><li>Allez sur <b>vercel.com → Account Settings → Tokens</b></li>"
            "<li>Cliquez <b>Create Token</b> et donnez-lui un nom</li>"
            "<li>Collez le token dans SimpleLog et cliquez <b>Connecter</b></li></ol>"
            "<p>Sélectionnez ensuite votre <b>projet</b> et un <b>déploiement</b> pour voir ses logs en temps réel.</p>"
        ),
        "help_gcp": (
            "<h3>GCP Cloud Logging</h3>"
            "<p><b>Créer une clé de Service Account :</b></p>"
            "<ol><li>Console GCP → <b>IAM &amp; Admin → Service Accounts</b></li>"
            "<li>Sélectionnez ou créez un compte avec le rôle <b>Logging → Logs Viewer</b></li>"
            "<li>Onglet <b>Keys → Add Key → JSON</b> → téléchargez le fichier</li></ol>"
            "<p>Dans SimpleLog :</p>"
            "<ul><li><b>Credentials file</b> : chemin vers le fichier JSON téléchargé</li>"
            "<li><b>Project ID</b> : visible dans l'en-tête de la console GCP (ex. <code>mon-projet-123</code>)</li></ul>"
        ),
        "help_azure": (
            "<h3>Azure Monitor</h3>"
            "<p><b>1. Obtenir le Workspace ID :</b><br>"
            "Log Analytics Workspace → <b>Settings → Agents</b> → copiez le <b>Workspace ID</b></p>"
            "<p><b>2. Créer une App Registration :</b></p>"
            "<ol><li>Azure Active Directory → <b>App registrations → New registration</b></li>"
            "<li>Copiez l'<b>Application (client) ID</b> et le <b>Directory (tenant) ID</b></li>"
            "<li><b>Certificates &amp; secrets → New client secret</b> → copiez la <b>Value</b></li>"
            "<li>Dans votre workspace : <b>Access control (IAM) → Add role → Log Analytics Reader</b>, assignez à cette app</li></ol>"
            "<p><b>Dans SimpleLog :</b> remplissez Workspace ID, Tenant ID, Client ID, Client Secret, puis entrez une requête KQL.</p>"
        ),
        "help_loki": (
            "<h3>Grafana Loki</h3>"
            "<p><b>Auto-hébergé / local :</b> entrez simplement l'URL (ex. <code>http://localhost:3100</code>). Aucun identifiant requis.</p>"
            "<p><b>Grafana Cloud :</b></p>"
            "<ol><li>Allez sur votre stack Grafana Cloud → <b>Connections → Data sources → Loki</b></li>"
            "<li>Copiez l'<b>URL</b>, le <b>User</b> et générez un token dans <b>Access Policies</b></li></ol>"
            "<p><b>Query (LogQL) :</b> ex. <code>{app=\"mon-app\"}</code> ou laissez vide pour tout voir.</p>"
        ),
        "help_datadog": (
            "<h3>Datadog</h3>"
            "<p><b>Clé API :</b><br>"
            "Organization Settings → <b>API Keys → New Key</b> → copiez-la</p>"
            "<p><b>Clé Application :</b><br>"
            "Organization Settings → <b>Application Keys → New Key</b> → copiez-la</p>"
            "<p><b>Dans SimpleLog :</b> sélectionnez votre site (ex. US1), collez les deux clés, ajoutez un filtre si besoin (ex. <code>service:api</code>).</p>"
        ),
        "help_elastic": (
            "<h3>Elasticsearch</h3>"
            "<p><b>Auto-hébergé / local :</b> entrez l'URL (ex. <code>http://localhost:9200</code>) et le nom de l'index. Aucun identifiant si la sécurité est désactivée.</p>"
            "<p><b>Elastic Cloud :</b></p>"
            "<ol><li>Allez sur votre déploiement → <b>Security → API Keys → Create API key</b></li>"
            "<li>Ou utilisez le username/password de votre cluster</li></ol>"
            "<p><b>Dans SimpleLog :</b> remplissez l'URL, l'Index (ex. <code>logs-*</code>) et les identifiants si requis.</p>"
        ),
        "help_railway": (
            "<h3>Railway</h3>"
            "<p><b>Obtenir votre token :</b></p>"
            "<ol><li>Dashboard Railway → <b>Account Settings → Tokens → Create Token</b></li>"
            "<li>Collez le token dans SimpleLog et cliquez <b>Connecter</b></li></ol>"
            "<p>Sélectionnez ensuite votre <b>projet</b> et <b>service</b> pour voir ses logs.</p>"
        ),
        "help_flyio": (
            "<h3>Fly.io</h3>"
            "<p><b>Obtenir votre token :</b></p>"
            "<ol><li>Installez la CLI : <code>curl -L https://fly.io/install.sh | sh</code></li>"
            "<li>Connectez-vous : <code>fly auth login</code></li>"
            "<li>Obtenez le token : <code>fly auth token</code></li>"
            "<li>Collez le résultat dans SimpleLog et cliquez <b>Connecter</b></li></ol>"
            "<p>Sélectionnez ensuite votre <b>app</b> pour voir ses logs.</p>"
        ),
        "help_kubernetes": (
            "<h3>Kubernetes</h3>"
            "<p>SimpleLog lit votre <code>~/.kube/config</code> existant. Aucun identifiant à saisir.</p>"
            "<p><b>Étapes :</b></p>"
            "<ol><li>Sélectionnez un <b>contexte</b> (cluster)</li>"
            "<li>Sélectionnez un <b>namespace</b></li>"
            "<li>Cliquez <b>Connecter</b> pour charger la liste des pods</li>"
            "<li>Sélectionnez un <b>pod</b> pour voir ses logs</li></ol>"
        ),
        "help_cloudflare": (
            "<h3>Cloudflare Workers</h3>"
            "<p><b>Obtenir votre Account ID :</b><br>"
            "Connectez-vous sur <b>dash.cloudflare.com</b> → sélectionnez un domaine → l'Account ID est dans la barre latérale droite (32 caractères).</p>"
            "<p><b>Créer un API Token :</b></p>"
            "<ol><li><b>My Profile → API Tokens → Create Token → Custom Token</b></li>"
            "<li>Ajoutez ces permissions :<br>"
            "— Account → <b>Workers Scripts : Read</b><br>"
            "— Account → <b>Workers Tail : Read</b><br>"
            "— User → <b>User Details : Read</b></li>"
            "<li>Copiez le token généré</li></ol>"
            "<p>Collez l'Account ID et le token dans SimpleLog, cliquez <b>Connecter</b>, puis sélectionnez un Worker.</p>"
        ),
    },
    "de": {
        # ── Menu bar ──────────────────────────────────────────────────
        "menu_file":             "Datei",
        "menu_edit":             "Bearbeiten",
        "menu_language":         "Sprache",
        "menu_help":             "Hilfe",
        "action_open":           "Öffnen…",
        "action_close_all":      "Alle Logs schließen",
        "action_update":         "Auf Updates prüfen",
        "action_quit":           "Beenden",
        "action_copy":           "Kopieren",
        "action_break":          "Break",
        "lang_english":          "English",
        "lang_french":           "Français",
        "lang_german":           "Deutsch",
        "lang_spanish":          "Español",
        "lang_chinese":          "中文",
        "action_help_ref":       "CLI-Referenz",
        "action_about":          "Über SimpleLog",
        # ── Help dialog ───────────────────────────────────────────────
        "help_title":            "CLI-Referenz — SimpleLog",
        "help_content": (
            "VERWENDUNG\n"
            "  simplelog [OPTIONEN] [DATEI ...]\n"
            "  befehl | simplelog [OPTIONEN]\n"
            "\n"
            "ARGUMENTE\n"
            "  DATEI ...         Ein oder mehrere Log-Dateipfade.\n"
            "\n"
            "OPTIONEN\n"
            "  --split MODUS     Ansicht beim Start.\n"
            "                    tab (Standard) | vertical | horizontal\n"
            "  --tail N          Zeilen vom Dateiende (Standard: 100).\n"
            "\n"
            "TASTENKÜRZEL\n"
            "  Ctrl+F            Sidebar-Suche fokussieren\n"
            "  Ctrl+Shift+F      Sidebar umschalten\n"
            "\n"
            "BEISPIELE\n"
            "  simplelog\n"
            "  simplelog /var/log/syslog\n"
            "  simplelog --tail 500 /var/log/nginx/access.log\n"
            "  simplelog --split vertical app.log error.log\n"
            "  journalctl -f | simplelog\n"
            "  kubectl logs -f my-pod | simplelog\n"
            "  docker logs -f my-container | simplelog\n"
        ),
        # ── Update dialog ─────────────────────────────────────────────
        "update_title":          "Auf Updates prüfen",
        "update_up_to_date":     "Sie sind auf dem neuesten Stand  ({version}).",
        "update_available":      "Update verfügbar: {latest}\n\nAktuelle Version: {current}",
        "update_download":       "Herunterladen",
        "update_install":        "Update installieren",
        "update_downloading":    "Update wird heruntergeladen…",
        "update_restarting":     "Update heruntergeladen. Die App wird jetzt neu gestartet.",
        "update_error":          "Updates konnten nicht geprüft werden:\n{error}",
        "update_install_error":  "Update fehlgeschlagen:\n{error}",
        # ── Status bar ────────────────────────────────────────────────
        "status_ready":          "Bereit",
        "history_loaded":        "Verlauf geladen: {n:,} Ereignisse — läuft…",
        # ── Open-mode widget ──────────────────────────────────────────
        "open_as":               "Öffnen als",
        "open_mode_tab":         "Neuer Tab",
        "open_mode_vertical":    "Split ↔  nebeneinander",
        "open_mode_horizontal":  "Split ↕  oben / unten",
        # ── CloudWatch panel ──────────────────────────────────────────
        "cw_title":              "CloudWatch",
        "cw_card_connection":    "Verbindung",
        "cw_auth_mode":          "Auth-Modus",
        "cw_auth_profile":       "AWS-Profil",
        "cw_auth_keys":          "Zugriffsschlüssel",
        "cw_field_profile":      "Profil",
        "cw_field_access_key":   "Access Key ID",
        "cw_field_secret_key":   "Secret Access Key",
        "cw_field_region":       "Region",
        "cw_connect":            "Verbinden",
        "cw_connecting":         "Verbinde…",
        "cw_refresh":            "Aktualisieren",
        "cw_card_groups":        "Log-Gruppen",
        "cw_search_groups":      "Gruppen suchen…",
        "cw_card_streams":       "Log-Streams",
        "cw_card_options":       "Optionen",
        "cw_field_lookback":     "Verlauf laden",
        "cw_field_poll":         "Abfrageintervall",
        "field_time_range":      "Zeitraum",
        "cw_field_filter":       "Filtermuster",
        "cw_filter_ph":          "CloudWatch-Filtermuster…",
        "cw_open":               "Öffnen ↗",
        # ── File panel ────────────────────────────────────────────────
        "file_title":            "Log-Dateien",
        "file_card_open":        "Datei öffnen",
        "file_desc":             "Durchsuchen Sie Ihr Dateisystem, um eine Log-Datei zu öffnen.",
        "file_last_lines":       "Letzte Zeilen:",
        "file_browse":           "Durchsuchen & Öffnen ↗",
        "file_card_recent":      "Zuletzt geöffnet",
        "file_no_recent":        "Keine zuletzt geöffneten Dateien",
        # ── LogViewer toolbar ─────────────────────────────────────────
        "viewer_autoscroll":     "Auto-Scrollen",
        "viewer_timestamps":     "Zeitstempel",
        "viewer_clear":          "Löschen",
        "viewer_stop":           "Stoppen",
        "viewer_lines":          "{n:,} Zeilen",
        # ── Sidebar ───────────────────────────────────────────────────────
        "sidebar_add_and":       "+ UND",
        "sidebar_add_or":        "+ ODER",
        "sidebar_hits":          "{n:,} Treffer",
        "sidebar_no_hits":       "Keine Ergebnisse",
        "sidebar_term_ph":       "Begriff…",
        "sidebar_live_filter":   "Live",
        "sidebar_json_ph":       "Erkannte Schlüssel…",
        # ── Error / dialog messages ───────────────────────────────────
        "err_file_not_found":    "Datei nicht gefunden",
        "err_cannot_open":       "Kann nicht geöffnet werden: {path}",
        "err_worker":            "Worker-Fehler",
        "err_connection":        "Verbindungsfehler",
        "err_streams":           "Fehler beim Laden der Streams",
        "err_prefix":            "Fehler: {msg}",
        # ── SSH panel ─────────────────────────────────────────────────
        "ssh_title":             "SSH-Fernzugriff",
        "ssh_card_connection":   "Verbindung",
        "ssh_field_host":        "Host",
        "ssh_field_port":        "Port",
        "ssh_field_user":        "Benutzer",
        "ssh_auth_mode":         "Authentifizierung",
        "ssh_auth_key":          "SSH-Schlüssel",
        "ssh_auth_password":     "Passwort",
        "ssh_field_keypath":     "Schlüsseldatei",
        "ssh_field_password":    "Passwort",
        "ssh_browse_key":        "Durchsuchen…",
        "ssh_connect":           "Verbinden",
        "ssh_connecting":        "Verbinde…",
        "ssh_connected":         "Verbunden ✓",
        "ssh_card_file":         "Remote-Datei",
        "ssh_field_path":        "Dateipfad",
        "ssh_field_tail":        "Letzte Zeilen",
        "ssh_browse_remote":     "Durchsuchen…",
        "ssh_open":              "Öffnen ↗",
        "ssh_card_recent":       "Letzte Verbindungen",
        "ssh_no_recent":         "Keine letzten Verbindungen",
        # ── Docker panel ──────────────────────────────────────────────
        "docker_title":          "Docker-Logs",
        "docker_tab_containers": "Container",
        "docker_tab_compose":    "Compose",
        "docker_tab_exec":       "Datei im Container",
        "docker_refresh":        "Aktualisieren ↻",
        "docker_no_containers":  "Keine laufenden Container",
        "docker_no_stacks":      "Keine Compose-Projekte gefunden",
        "docker_not_available":  "Docker CLI nicht im PATH gefunden.\nInstallieren Sie Docker, um diese Funktion zu nutzen.",
        "docker_field_tail":     "Letzte Zeilen",
        "docker_field_path":     "Dateipfad im Container",
        "docker_open_container": "Logs streamen ↗",
        "docker_open_stack":     "Stack streamen ↗",
        "docker_open_exec":      "Datei verfolgen ↗",
        # ── Vercel panel ──────────────────────────────────────────────
        "vercel_field_token":    "Vercel-Token einfügen",
        "vercel_connect":        "Verbinden",
        "vercel_connecting":     "Verbinde…",
        "vercel_connected":      "Verbunden ✓",
        "vercel_card_project":   "Projekt",
        "vercel_refresh":        "Aktualisieren ↻",
        "vercel_no_projects":    "Keine Projekte gefunden",
        "vercel_card_deploy":    "Deployment",
        "vercel_target_prod":    "Produktion",
        "vercel_target_preview": "Vorschau",
        "vercel_target_any":     "Letztes (beliebig)",
        "vercel_field_interval": "Abfrageintervall (s)",
        "vercel_open":           "Logs öffnen ↗",
        "vercel_no_deploy":      "Kein Deployment für dieses Projekt gefunden",
        # ── GCP panel ─────────────────────────────────────────────────
        "gcp_auth_adc":          "Standard-Anmeldedaten (ADC)",
        "gcp_auth_sa":           "Service-Account-Schlüssel",
        "gcp_field_keyfile":     "Schlüsseldatei (.json)",
        "gcp_browse_key":        "Durchsuchen…",
        "gcp_field_project":     "Projekt-ID",
        "gcp_list_projects":     "Projekte auflisten ↻",
        "gcp_connect":           "Verbinden",
        "gcp_connecting":        "Verbinde…",
        "gcp_connected":         "Verbunden ✓",
        "gcp_card_filter":       "Log-Filter",
        "gcp_field_resource":    "Ressourcentyp",
        "gcp_field_severity":    "Mindest-Schweregrad",
        "gcp_field_custom":      "Benutzerdefinierter Filter (optional)",
        "gcp_custom_hint":       "GCP-Filtersyntax, z.B. labels.app=\"mein-service\"",
        "gcp_field_interval":    "Abfrageintervall (s)",
        "gcp_open":              "Logs öffnen ↗",
        "gcp_no_projects":       "Keine Projekte gefunden",
        # ── Azure panel ───────────────────────────────────────────────
        "azure_connect":         "Verbinden",
        "azure_connecting":      "Verbinde…",
        "azure_connected":       "Verbunden ✓",
        "azure_tab_tables":      "Tabellen",
        "azure_tab_kql":         "KQL-Abfrage",
        "azure_card_table":      "Log-Tabelle",
        "azure_search_table":    "Tabellen suchen…",
        "azure_field_interval":  "Abfrageintervall (s)",
        "azure_open_table":      "Tabelle öffnen ↗",
        "azure_card_kql":        "KQL-Abfrage",
        "azure_kql_hint":        "KQL-Abfrage eingeben. TimeGenerated-Filter wird automatisch hinzugefügt.",
        "azure_open_kql":        "Ausführen ↗",
        # ── Grafana Loki ──────────────────────────────────────────────
        "loki_auth_none":        "Keine Authentifizierung",
        "loki_auth_basic":       "Basis-Auth",
        "loki_auth_token":       "Bearer-Token",
        "loki_field_url":        "Loki-URL",
        "loki_field_username":   "Benutzername",
        "loki_field_password":   "Passwort",
        "loki_field_token":      "Bearer-Token",
        "loki_connect":          "Verbinden",
        "loki_connecting":       "Verbinde…",
        "loki_connected":        "Verbunden ✓",
        "loki_card_query":       "Abfrage",
        "loki_field_query":      "LogQL-Abfrage",
        "loki_query_hint":       "{app=\"myapp\"} |= \"error\"",
        "loki_list_labels":      "Labels ↻",
        "loki_field_interval":   "Abfrageintervall (s)",
        "loki_open":             "Logs öffnen ↗",
        "loki_no_labels":        "Keine Labels gefunden",
        # ── Datadog ───────────────────────────────────────────────────
        "datadog_field_site":    "Site",
        "datadog_field_api_key": "API-Schlüssel",
        "datadog_field_app_key": "Application-Schlüssel",
        "datadog_connect":       "Verbinden",
        "datadog_connecting":    "Verbinde…",
        "datadog_connected":     "Verbunden ✓",
        "datadog_card_query":    "Abfrage",
        "datadog_field_query":   "Log-Abfrage",
        "datadog_query_hint":    "service:myapp status:error",
        "datadog_field_interval":"Abfrageintervall (s)",
        "datadog_open":          "Logs öffnen ↗",
        # ── Elasticsearch ─────────────────────────────────────────────
        "elastic_auth_none":     "Keine Authentifizierung",
        "elastic_auth_apikey":   "API-Schlüssel",
        "elastic_auth_basic":    "Basis-Auth",
        "elastic_field_url":     "Elasticsearch-URL",
        "elastic_field_apikey":  "API-Schlüssel",
        "elastic_field_username":"Benutzername",
        "elastic_field_password":"Passwort",
        "elastic_connect":       "Verbinden",
        "elastic_connecting":    "Verbinde…",
        "elastic_connected":     "Verbunden ✓",
        "elastic_card_query":    "Abfrage",
        "elastic_field_index":   "Index",
        "elastic_field_ts":      "Timestamp-Feld",
        "elastic_field_query":   "Abfrage",
        "elastic_query_hint":    "level:ERROR AND service:myapp",
        "elastic_field_interval":"Abfrageintervall (s)",
        "elastic_open":          "Logs öffnen ↗",
        "elastic_no_indices":    "Keine Indizes gefunden",
        # ── Railway ───────────────────────────────────────────────────
        "railway_field_token":   "API-Token",
        "railway_connect":       "Verbinden",
        "railway_connecting":    "Verbinde…",
        "railway_connected":     "Verbunden ✓",
        "railway_card_project":  "Projekt",
        "railway_no_projects":   "Keine Projekte gefunden",
        "railway_card_service":  "Service",
        "railway_no_services":   "Keine Services gefunden",
        "railway_field_interval":"Abfrageintervall (s)",
        "railway_open":          "Logs öffnen ↗",
        # ── Fly.io ────────────────────────────────────────────────────
        "flyio_field_token":     "API-Token",
        "flyio_connect":         "Verbinden",
        "flyio_connecting":      "Verbinde…",
        "flyio_connected":       "Verbunden ✓",
        "flyio_card_app":        "Anwendung",
        "flyio_no_apps":         "Keine Apps gefunden",
        "flyio_field_interval":  "Abfrageintervall (s)",
        "flyio_open":            "Logs öffnen ↗",
        # ── Kubernetes ────────────────────────────────────────────────
        "kubernetes_not_available": "kubectl nicht gefunden. Installieren Sie kubectl und prüfen Sie den PATH.",
        "kubernetes_card_cluster":"Cluster",
        "kubernetes_field_context":"Kontext",
        "kubernetes_field_ns":   "Namespace",
        "kubernetes_connect":    "Verbinden",
        "kubernetes_connecting": "Verbinde…",
        "kubernetes_connected":  "Verbunden ✓",
        "kubernetes_card_pod":   "Pod",
        "kubernetes_no_ns":      "Keine Namespaces gefunden",
        "kubernetes_no_pods":    "Keine Pods gefunden",
        "kubernetes_field_container": "Container (optional)",
        "kubernetes_open":       "Logs streamen ↗",
        # ── Cloudflare Workers ────────────────────────────────────────
        "cf_field_token":        "API-Token",
        "cf_field_account_id":   "Konto-ID",
        "cf_connect":            "Verbinden",
        "cf_connecting":         "Verbinde…",
        "cf_connected":          "Verbunden ✓",
        "cf_card_workers":       "Workers",
        "cf_no_workers":         "Keine Workers in diesem Konto gefunden",
        "cf_missing_fields":     "API-Token und Konto-ID sind erforderlich",
        "cf_open":               "Logs streamen ↗",
        # ── Credential storage ────────────────────────────────────────
        # ── Remote panel ─────────────────────────────────────────────
        "remote_title":          "Remote-Quellen",
        "remote_dialog_title":   "Remote-Quelle hinzufügen",
        "remote_dialog_header":  "Quelle hinzufügen",
        "remote_back":               "← Zurück",
        "remote_choose":             "Anbieter auswählen",
        "remote_open":               "Öffnen",
        "remote_add_connection":     "+ Verbindung hinzufügen",
        "remote_no_connections":     "Keine Remote-Verbindungen",
        "remote_no_connections_sub": "Klicken Sie auf Hinzufügen, um einen Anbieter zu verbinden",
        "remote_save_open":          "Speichern && Öffnen",
        "remote_cancel":             "Abbrechen",
        "remote_select_provider":    "Anbieter auswählen",
        "remote_new_connection":     "Neue Verbindung",
        "remote_connection_name":    "Verbindungsname",
        "remote_add_btn":            "+ Hinzufügen",
        "remote_add_title":          "Verbindung hinzufügen",
        "remote_add_header":         "Remote-Verbindung hinzufügen",
        "saved_configs":             "Gespeicherte Konfigurationen",
        "new_config":                "Neue Konfiguration",
        "help_dialog_title":         "Konfigurationsanleitung",
        "help_dialog_close":         "Schließen",
    },
    "es": {
        # ── Menu bar ──────────────────────────────────────────────────
        "menu_file":             "Archivo",
        "menu_edit":             "Editar",
        "menu_language":         "Idioma",
        "menu_help":             "Ayuda",
        "action_open":           "Abrir…",
        "action_close_all":      "Cerrar todos los logs",
        "action_update":         "Buscar actualizaciones",
        "action_quit":           "Salir",
        "action_copy":           "Copiar",
        "action_break":          "Break",
        "lang_english":          "English",
        "lang_french":           "Français",
        "lang_german":           "Deutsch",
        "lang_spanish":          "Español",
        "lang_chinese":          "中文",
        "action_help_ref":       "Referencia CLI",
        "action_about":          "Acerca de SimpleLog",
        # ── Help dialog ───────────────────────────────────────────────
        "help_title":            "Referencia CLI — SimpleLog",
        "help_content": (
            "USO\n"
            "  simplelog [OPCIONES] [ARCHIVO ...]\n"
            "  comando | simplelog [OPCIONES]\n"
            "\n"
            "ARGUMENTOS\n"
            "  ARCHIVO ...       Una o más rutas de archivos de log.\n"
            "\n"
            "OPCIONES\n"
            "  --split MODO      Disposición al iniciar.\n"
            "                    tab (predeterminado) | vertical | horizontal\n"
            "  --tail N          Líneas desde el final del archivo (predeterminado: 100).\n"
            "\n"
            "ATAJOS DE TECLADO\n"
            "  Ctrl+F            Enfocar la búsqueda de la barra lateral\n"
            "  Ctrl+Shift+F      Alternar barra lateral\n"
            "\n"
            "EJEMPLOS\n"
            "  simplelog\n"
            "  simplelog /var/log/syslog\n"
            "  simplelog --tail 500 /var/log/nginx/access.log\n"
            "  simplelog --split vertical app.log error.log\n"
            "  journalctl -f | simplelog\n"
            "  kubectl logs -f my-pod | simplelog\n"
            "  docker logs -f my-container | simplelog\n"
        ),
        # ── Update dialog ─────────────────────────────────────────────
        "update_title":          "Buscar actualizaciones",
        "update_up_to_date":     "Estás al día  ({version}).",
        "update_available":      "Actualización disponible: {latest}\n\nVersión actual: {current}",
        "update_download":       "Descargar",
        "update_install":        "Instalar actualización",
        "update_downloading":    "Descargando actualización…",
        "update_restarting":     "Actualización descargada. La app se reiniciará ahora.",
        "update_error":          "No se pudieron buscar actualizaciones:\n{error}",
        "update_install_error":  "Error en la actualización:\n{error}",
        # ── Status bar ────────────────────────────────────────────────
        "status_ready":          "Listo",
        "history_loaded":        "Historial cargado: {n:,} eventos — siguiendo…",
        # ── Open-mode widget ──────────────────────────────────────────
        "open_as":               "Abrir como",
        "open_mode_tab":         "Nueva pestaña",
        "open_mode_vertical":    "Split ↔  lado a lado",
        "open_mode_horizontal":  "Split ↕  arriba / abajo",
        # ── CloudWatch panel ──────────────────────────────────────────
        "cw_title":              "CloudWatch",
        "cw_card_connection":    "Conexión",
        "cw_auth_mode":          "Modo auth",
        "cw_auth_profile":       "Perfil AWS",
        "cw_auth_keys":          "Claves de acceso",
        "cw_field_profile":      "Perfil",
        "cw_field_access_key":   "Access Key ID",
        "cw_field_secret_key":   "Secret Access Key",
        "cw_field_region":       "Región",
        "cw_connect":            "Conectar",
        "cw_connecting":         "Conectando…",
        "cw_refresh":            "Actualizar",
        "cw_card_groups":        "Grupos de logs",
        "cw_search_groups":      "Buscar grupos…",
        "cw_card_streams":       "Flujos de logs",
        "cw_card_options":       "Opciones",
        "cw_field_lookback":     "Cargar historial",
        "cw_field_poll":         "Intervalo",
        "field_time_range":      "Rango de tiempo",
        "cw_field_filter":       "Patrón de filtro",
        "cw_filter_ph":          "Patrón de filtro CloudWatch…",
        "cw_open":               "Abrir ↗",
        # ── File panel ────────────────────────────────────────────────
        "file_title":            "Archivos de logs",
        "file_card_open":        "Abrir archivo",
        "file_desc":             "Navega por tu sistema de archivos para abrir un archivo de log.",
        "file_last_lines":       "Últimas líneas:",
        "file_browse":           "Explorar & Abrir ↗",
        "file_card_recent":      "Archivos recientes",
        "file_no_recent":        "Sin archivos recientes",
        # ── LogViewer toolbar ─────────────────────────────────────────
        "viewer_autoscroll":     "Auto-scroll",
        "viewer_timestamps":     "Marcas de tiempo",
        "viewer_clear":          "Limpiar",
        "viewer_stop":           "Detener",
        "viewer_lines":          "{n:,} líneas",
        # ── Sidebar ───────────────────────────────────────────────────────
        "sidebar_add_and":       "+ Y",
        "sidebar_add_or":        "+ O",
        "sidebar_hits":          "{n:,} resultados",
        "sidebar_no_hits":       "Sin resultados",
        "sidebar_term_ph":       "Término…",
        "sidebar_live_filter":   "En vivo",
        "sidebar_json_ph":       "Claves detectadas…",
        # ── Error / dialog messages ───────────────────────────────────
        "err_file_not_found":    "Archivo no encontrado",
        "err_cannot_open":       "No se puede abrir: {path}",
        "err_worker":            "Error del worker",
        "err_connection":        "Error de conexión",
        "err_streams":           "Error al cargar los flujos",
        "err_prefix":            "Error: {msg}",
        # ── SSH panel ─────────────────────────────────────────────────
        "ssh_title":             "Logs SSH Remotos",
        "ssh_card_connection":   "Conexión",
        "ssh_field_host":        "Host",
        "ssh_field_port":        "Puerto",
        "ssh_field_user":        "Usuario",
        "ssh_auth_mode":         "Autenticación",
        "ssh_auth_key":          "Clave SSH",
        "ssh_auth_password":     "Contraseña",
        "ssh_field_keypath":     "Archivo de clave",
        "ssh_field_password":    "Contraseña",
        "ssh_browse_key":        "Examinar…",
        "ssh_connect":           "Conectar",
        "ssh_connecting":        "Conectando…",
        "ssh_connected":         "Conectado ✓",
        "ssh_card_file":         "Archivo remoto",
        "ssh_field_path":        "Ruta del archivo",
        "ssh_field_tail":        "Últimas líneas",
        "ssh_browse_remote":     "Examinar…",
        "ssh_open":              "Abrir ↗",
        "ssh_card_recent":       "Conexiones recientes",
        "ssh_no_recent":         "Sin conexiones recientes",
        # ── Docker panel ──────────────────────────────────────────────
        "docker_title":          "Logs de Docker",
        "docker_tab_containers": "Contenedores",
        "docker_tab_compose":    "Compose",
        "docker_tab_exec":       "Archivo en contenedor",
        "docker_refresh":        "Actualizar ↻",
        "docker_no_containers":  "No hay contenedores en ejecución",
        "docker_no_stacks":      "No se encontraron proyectos Compose",
        "docker_not_available":  "Docker CLI no encontrado en PATH.\nInstala Docker para usar esta función.",
        "docker_field_tail":     "Últimas líneas",
        "docker_field_path":     "Ruta del archivo en el contenedor",
        "docker_open_container": "Stream de logs ↗",
        "docker_open_stack":     "Stream del stack ↗",
        "docker_open_exec":      "Seguir archivo ↗",
        # ── Vercel panel ──────────────────────────────────────────────
        "vercel_field_token":    "Pegue su token de Vercel",
        "vercel_connect":        "Conectar",
        "vercel_connecting":     "Conectando…",
        "vercel_connected":      "Conectado ✓",
        "vercel_card_project":   "Proyecto",
        "vercel_refresh":        "Actualizar ↻",
        "vercel_no_projects":    "No se encontraron proyectos",
        "vercel_card_deploy":    "Despliegue",
        "vercel_target_prod":    "Producción",
        "vercel_target_preview": "Vista previa",
        "vercel_target_any":     "Último (cualquiera)",
        "vercel_field_interval": "Intervalo de sondeo (s)",
        "vercel_open":           "Abrir logs ↗",
        "vercel_no_deploy":      "No se encontró despliegue para este proyecto",
        # ── GCP panel ─────────────────────────────────────────────────
        "gcp_auth_adc":          "Credenciales predeterminadas (ADC)",
        "gcp_auth_sa":           "Clave de cuenta de servicio",
        "gcp_field_keyfile":     "Archivo de clave (.json)",
        "gcp_browse_key":        "Examinar…",
        "gcp_field_project":     "ID del proyecto",
        "gcp_list_projects":     "Listar proyectos ↻",
        "gcp_connect":           "Conectar",
        "gcp_connecting":        "Conectando…",
        "gcp_connected":         "Conectado ✓",
        "gcp_card_filter":       "Filtro de logs",
        "gcp_field_resource":    "Tipo de recurso",
        "gcp_field_severity":    "Severidad mínima",
        "gcp_field_custom":      "Filtro personalizado (opcional)",
        "gcp_custom_hint":       "Sintaxis GCP, ej. labels.app=\"mi-servicio\"",
        "gcp_field_interval":    "Intervalo de sondeo (s)",
        "gcp_open":              "Abrir logs ↗",
        "gcp_no_projects":       "No se encontraron proyectos",
        # ── Azure panel ───────────────────────────────────────────────
        "azure_connect":         "Conectar",
        "azure_connecting":      "Conectando…",
        "azure_connected":       "Conectado ✓",
        "azure_tab_tables":      "Tablas",
        "azure_tab_kql":         "Consulta KQL",
        "azure_card_table":      "Tabla de logs",
        "azure_search_table":    "Buscar tabla…",
        "azure_field_interval":  "Intervalo de sondeo (s)",
        "azure_open_table":      "Abrir tabla ↗",
        "azure_card_kql":        "Consulta KQL",
        "azure_kql_hint":        "Ingrese una consulta KQL. El filtro TimeGenerated se agrega automáticamente.",
        "azure_open_kql":        "Ejecutar ↗",
        # ── Grafana Loki ──────────────────────────────────────────────
        "loki_auth_none":        "Sin autenticación",
        "loki_auth_basic":       "Auth básica",
        "loki_auth_token":       "Token Bearer",
        "loki_field_url":        "URL de Loki",
        "loki_field_username":   "Nombre de usuario",
        "loki_field_password":   "Contraseña",
        "loki_field_token":      "Token Bearer",
        "loki_connect":          "Conectar",
        "loki_connecting":       "Conectando…",
        "loki_connected":        "Conectado ✓",
        "loki_card_query":       "Consulta",
        "loki_field_query":      "Consulta LogQL",
        "loki_query_hint":       "{app=\"myapp\"} |= \"error\"",
        "loki_list_labels":      "Labels ↻",
        "loki_field_interval":   "Intervalo (s)",
        "loki_open":             "Abrir logs ↗",
        "loki_no_labels":        "No se encontraron labels",
        # ── Datadog ───────────────────────────────────────────────────
        "datadog_field_site":    "Sitio",
        "datadog_field_api_key": "API Key",
        "datadog_field_app_key": "Application Key",
        "datadog_connect":       "Conectar",
        "datadog_connecting":    "Conectando…",
        "datadog_connected":     "Conectado ✓",
        "datadog_card_query":    "Consulta",
        "datadog_field_query":   "Consulta de logs",
        "datadog_query_hint":    "service:myapp status:error",
        "datadog_field_interval":"Intervalo (s)",
        "datadog_open":          "Abrir logs ↗",
        # ── Elasticsearch ─────────────────────────────────────────────
        "elastic_auth_none":     "Sin autenticación",
        "elastic_auth_apikey":   "API Key",
        "elastic_auth_basic":    "Auth básica",
        "elastic_field_url":     "URL de Elasticsearch",
        "elastic_field_apikey":  "API Key",
        "elastic_field_username":"Nombre de usuario",
        "elastic_field_password":"Contraseña",
        "elastic_connect":       "Conectar",
        "elastic_connecting":    "Conectando…",
        "elastic_connected":     "Conectado ✓",
        "elastic_card_query":    "Consulta",
        "elastic_field_index":   "Índice",
        "elastic_field_ts":      "Campo timestamp",
        "elastic_field_query":   "Consulta",
        "elastic_query_hint":    "level:ERROR AND service:myapp",
        "elastic_field_interval":"Intervalo (s)",
        "elastic_open":          "Abrir logs ↗",
        "elastic_no_indices":    "No se encontraron índices",
        # ── Railway ───────────────────────────────────────────────────
        "railway_field_token":   "Token API",
        "railway_connect":       "Conectar",
        "railway_connecting":    "Conectando…",
        "railway_connected":     "Conectado ✓",
        "railway_card_project":  "Proyecto",
        "railway_no_projects":   "No se encontraron proyectos",
        "railway_card_service":  "Servicio",
        "railway_no_services":   "No se encontraron servicios",
        "railway_field_interval":"Intervalo (s)",
        "railway_open":          "Abrir logs ↗",
        # ── Fly.io ────────────────────────────────────────────────────
        "flyio_field_token":     "Token API",
        "flyio_connect":         "Conectar",
        "flyio_connecting":      "Conectando…",
        "flyio_connected":       "Conectado ✓",
        "flyio_card_app":        "Aplicación",
        "flyio_no_apps":         "No se encontraron apps",
        "flyio_field_interval":  "Intervalo (s)",
        "flyio_open":            "Abrir logs ↗",
        # ── Kubernetes ────────────────────────────────────────────────
        "kubernetes_not_available": "kubectl no encontrado. Instale kubectl y verifique el PATH.",
        "kubernetes_card_cluster":"Cluster",
        "kubernetes_field_context":"Contexto",
        "kubernetes_field_ns":   "Namespace",
        "kubernetes_connect":    "Conectar",
        "kubernetes_connecting": "Conectando…",
        "kubernetes_connected":  "Conectado ✓",
        "kubernetes_card_pod":   "Pod",
        "kubernetes_no_ns":      "No se encontraron namespaces",
        "kubernetes_no_pods":    "No se encontraron pods",
        "kubernetes_field_container": "Contenedor (opcional)",
        "kubernetes_open":       "Transmitir logs ↗",
        # ── Cloudflare Workers ────────────────────────────────────────
        "cf_field_token":        "Token de API",
        "cf_field_account_id":   "ID de cuenta",
        "cf_connect":            "Conectar",
        "cf_connecting":         "Conectando…",
        "cf_connected":          "Conectado ✓",
        "cf_card_workers":       "Workers",
        "cf_no_workers":         "No se encontraron workers en esta cuenta",
        "cf_missing_fields":     "El token API y el ID de cuenta son obligatorios",
        "cf_open":               "Ver logs en tiempo real ↗",
        # ── Credential storage ────────────────────────────────────────
        # ── Remote panel ─────────────────────────────────────────────
        "remote_title":          "Fuentes remotas",
        "remote_dialog_title":   "Añadir fuente remota",
        "remote_dialog_header":  "Añadir fuente",
        "remote_back":               "← Volver",
        "remote_choose":             "Elegir proveedor",
        "remote_open":               "Abrir",
        "remote_add_connection":     "+ Añadir conexión",
        "remote_no_connections":     "Sin conexiones remotas",
        "remote_no_connections_sub": "Haz clic en Añadir para conectar un proveedor",
        "remote_save_open":          "Guardar && Abrir",
        "remote_cancel":             "Cancelar",
        "remote_select_provider":    "Seleccionar un proveedor",
        "remote_new_connection":     "Nueva conexión",
        "remote_connection_name":    "Nombre de conexión",
        "remote_add_btn":            "+ Añadir",
        "remote_add_title":          "Añadir conexión",
        "remote_add_header":         "Añadir conexión remota",
        "saved_configs":             "Configuraciones guardadas",
        "new_config":                "Nueva configuración",
        "help_dialog_title":         "Guía de configuración",
        "help_dialog_close":         "Cerrar",
    },
    "zh": {
        # ── Menu bar ──────────────────────────────────────────────────
        "menu_file":             "文件",
        "menu_edit":             "编辑",
        "menu_language":         "语言",
        "menu_help":             "帮助",
        "action_open":           "打开…",
        "action_close_all":      "关闭所有日志",
        "action_update":         "检查更新",
        "action_quit":           "退出",
        "action_copy":           "复制",
        "action_break":          "中断",
        "lang_english":          "English",
        "lang_french":           "Français",
        "lang_german":           "Deutsch",
        "lang_spanish":          "Español",
        "lang_chinese":          "中文",
        "action_help_ref":       "CLI 参考",
        "action_about":          "关于 SimpleLog",
        # ── Help dialog ───────────────────────────────────────────────
        "help_title":            "CLI 参考 — SimpleLog",
        "help_content": (
            "用法\n"
            "  simplelog [选项] [文件 ...]\n"
            "  命令 | simplelog [选项]\n"
            "\n"
            "参数\n"
            "  文件 ...          一个或多个日志文件路径。\n"
            "\n"
            "选项\n"
            "  --split 模式      启动时的布局方式。\n"
            "                    tab（默认）| vertical | horizontal\n"
            "  --tail N          从文件末尾加载的行数（默认：100）。\n"
            "\n"
            "键盘快捷键\n"
            "  Ctrl+F            聚焦侧边栏搜索\n"
            "  Ctrl+Shift+F      切换侧边栏\n"
            "\n"
            "示例\n"
            "  simplelog\n"
            "  simplelog /var/log/syslog\n"
            "  simplelog --tail 500 /var/log/nginx/access.log\n"
            "  simplelog --split vertical app.log error.log\n"
            "  journalctl -f | simplelog\n"
            "  kubectl logs -f my-pod | simplelog\n"
            "  docker logs -f my-container | simplelog\n"
        ),
        # ── Update dialog ─────────────────────────────────────────────
        "update_title":          "检查更新",
        "update_up_to_date":     "已是最新版本  ({version})。",
        "update_available":      "发现新版本：{latest}\n\n当前版本：{current}",
        "update_download":       "下载",
        "update_install":        "安装更新",
        "update_downloading":    "正在下载更新…",
        "update_restarting":     "更新已下载，应用即将重启。",
        "update_error":          "无法检查更新：\n{error}",
        "update_install_error":  "更新失败：\n{error}",
        # ── Status bar ────────────────────────────────────────────────
        "status_ready":          "就绪",
        "history_loaded":        "历史记录已加载：{n:,} 条事件 — 正在追踪…",
        # ── Open-mode widget ──────────────────────────────────────────
        "open_as":               "打开方式",
        "open_mode_tab":         "新标签页",
        "open_mode_vertical":    "Split ↔  左右分割",
        "open_mode_horizontal":  "Split ↕  上下分割",
        # ── CloudWatch panel ──────────────────────────────────────────
        "cw_title":              "CloudWatch",
        "cw_card_connection":    "连接",
        "cw_auth_mode":          "认证方式",
        "cw_auth_profile":       "AWS 配置文件",
        "cw_auth_keys":          "访问密钥",
        "cw_field_profile":      "配置文件",
        "cw_field_access_key":   "Access Key ID",
        "cw_field_secret_key":   "Secret Access Key",
        "cw_field_region":       "区域",
        "cw_connect":            "连接",
        "cw_connecting":         "连接中…",
        "cw_refresh":            "刷新",
        "cw_card_groups":        "日志组",
        "cw_search_groups":      "搜索日志组…",
        "cw_card_streams":       "日志流",
        "cw_card_options":       "选项",
        "cw_field_lookback":     "加载历史",
        "cw_field_poll":         "轮询间隔",
        "field_time_range":      "时间范围",
        "cw_field_filter":       "过滤模式",
        "cw_filter_ph":          "CloudWatch 过滤模式…",
        "cw_open":               "打开 ↗",
        # ── File panel ────────────────────────────────────────────────
        "file_title":            "日志文件",
        "file_card_open":        "打开文件",
        "file_desc":             "浏览文件系统以打开日志文件。",
        "file_last_lines":       "最后几行：",
        "file_browse":           "浏览并打开 ↗",
        "file_card_recent":      "最近文件",
        "file_no_recent":        "无最近文件",
        # ── LogViewer toolbar ─────────────────────────────────────────
        "viewer_autoscroll":     "自动滚动",
        "viewer_timestamps":     "时间戳",
        "viewer_clear":          "清除",
        "viewer_stop":           "停止",
        "viewer_lines":          "{n:,} 行",
        # ── Sidebar ───────────────────────────────────────────────────────
        "sidebar_add_and":       "+ 与",
        "sidebar_add_or":        "+ 或",
        "sidebar_hits":          "{n:,} 个结果",
        "sidebar_no_hits":       "无结果",
        "sidebar_term_ph":       "关键词…",
        "sidebar_live_filter":   "实时",
        "sidebar_json_ph":       "已检测到的键…",
        # ── Error / dialog messages ───────────────────────────────────
        "err_file_not_found":    "文件未找到",
        "err_cannot_open":       "无法打开：{path}",
        "err_worker":            "Worker 错误",
        "err_connection":        "连接错误",
        "err_streams":           "加载流时出错",
        "err_prefix":            "错误：{msg}",
        # ── SSH panel ─────────────────────────────────────────────────
        "ssh_title":             "SSH 远程日志",
        "ssh_card_connection":   "连接",
        "ssh_field_host":        "主机",
        "ssh_field_port":        "端口",
        "ssh_field_user":        "用户名",
        "ssh_auth_mode":         "认证方式",
        "ssh_auth_key":          "SSH 密钥",
        "ssh_auth_password":     "密码",
        "ssh_field_keypath":     "密钥文件",
        "ssh_field_password":    "密码",
        "ssh_browse_key":        "浏览…",
        "ssh_connect":           "连接",
        "ssh_connecting":        "连接中…",
        "ssh_connected":         "已连接 ✓",
        "ssh_card_file":         "远程文件",
        "ssh_field_path":        "文件路径",
        "ssh_field_tail":        "最后行数",
        "ssh_browse_remote":     "浏览…",
        "ssh_open":              "打开 ↗",
        "ssh_card_recent":       "最近连接",
        "ssh_no_recent":         "无最近连接",
        # ── Docker panel ──────────────────────────────────────────────
        "docker_title":          "Docker 日志",
        "docker_tab_containers": "容器",
        "docker_tab_compose":    "Compose",
        "docker_tab_exec":       "容器内文件",
        "docker_refresh":        "刷新 ↻",
        "docker_no_containers":  "无正在运行的容器",
        "docker_no_stacks":      "未找到 Compose 项目",
        "docker_not_available":  "PATH 中未找到 Docker CLI。\n请安装 Docker 以使用此功能。",
        "docker_field_tail":     "最后行数",
        "docker_field_path":     "容器内文件路径",
        "docker_open_container": "流式传输日志 ↗",
        "docker_open_stack":     "流式传输 Stack ↗",
        "docker_open_exec":      "追踪文件 ↗",
        # ── Vercel panel ──────────────────────────────────────────────
        "vercel_field_token":    "粘贴您的 Vercel 令牌",
        "vercel_connect":        "连接",
        "vercel_connecting":     "连接中…",
        "vercel_connected":      "已连接 ✓",
        "vercel_card_project":   "项目",
        "vercel_refresh":        "刷新 ↻",
        "vercel_no_projects":    "未找到项目",
        "vercel_card_deploy":    "部署",
        "vercel_target_prod":    "生产环境",
        "vercel_target_preview": "预览环境",
        "vercel_target_any":     "最新（任意）",
        "vercel_field_interval": "轮询间隔（秒）",
        "vercel_open":           "打开日志 ↗",
        "vercel_no_deploy":      "未找到该项目的部署",
        # ── GCP panel ─────────────────────────────────────────────────
        "gcp_auth_adc":          "应用默认凭据 (ADC)",
        "gcp_auth_sa":           "服务账号密钥",
        "gcp_field_keyfile":     "密钥文件 (.json)",
        "gcp_browse_key":        "浏览…",
        "gcp_field_project":     "项目 ID",
        "gcp_list_projects":     "列出项目 ↻",
        "gcp_connect":           "连接",
        "gcp_connecting":        "连接中…",
        "gcp_connected":         "已连接 ✓",
        "gcp_card_filter":       "日志过滤器",
        "gcp_field_resource":    "资源类型",
        "gcp_field_severity":    "最低严重性",
        "gcp_field_custom":      "自定义过滤器（可选）",
        "gcp_custom_hint":       "GCP 过滤语法，例如 labels.app=\"my-service\"",
        "gcp_field_interval":    "轮询间隔（秒）",
        "gcp_open":              "打开日志 ↗",
        "gcp_no_projects":       "未找到项目",
        # ── Azure panel ───────────────────────────────────────────────
        "azure_connect":         "连接",
        "azure_connecting":      "连接中…",
        "azure_connected":       "已连接 ✓",
        "azure_tab_tables":      "表",
        "azure_tab_kql":         "KQL 查询",
        "azure_card_table":      "日志表",
        "azure_search_table":    "搜索表…",
        "azure_field_interval":  "轮询间隔（秒）",
        "azure_open_table":      "打开表 ↗",
        "azure_card_kql":        "KQL 查询",
        "azure_kql_hint":        "输入 KQL 查询。轮询时自动添加 TimeGenerated 过滤器。",
        "azure_open_kql":        "执行 ↗",
        # ── Grafana Loki ──────────────────────────────────────────────
        "loki_auth_none":        "无认证",
        "loki_auth_basic":       "基础认证",
        "loki_auth_token":       "Bearer令牌",
        "loki_field_url":        "Loki地址",
        "loki_field_username":   "用户名",
        "loki_field_password":   "密码",
        "loki_field_token":      "Bearer令牌",
        "loki_connect":          "连接",
        "loki_connecting":       "连接中…",
        "loki_connected":        "已连接 ✓",
        "loki_card_query":       "查询",
        "loki_field_query":      "LogQL查询",
        "loki_query_hint":       "{app=\"myapp\"} |= \"error\"",
        "loki_list_labels":      "标签 ↻",
        "loki_field_interval":   "轮询间隔（秒）",
        "loki_open":             "打开日志 ↗",
        "loki_no_labels":        "未找到标签",
        # ── Datadog ───────────────────────────────────────────────────
        "datadog_field_site":    "站点",
        "datadog_field_api_key": "API密钥",
        "datadog_field_app_key": "Application密钥",
        "datadog_connect":       "连接",
        "datadog_connecting":    "连接中…",
        "datadog_connected":     "已连接 ✓",
        "datadog_card_query":    "查询",
        "datadog_field_query":   "日志查询",
        "datadog_query_hint":    "service:myapp status:error",
        "datadog_field_interval":"轮询间隔（秒）",
        "datadog_open":          "打开日志 ↗",
        # ── Elasticsearch ─────────────────────────────────────────────
        "elastic_auth_none":     "无认证",
        "elastic_auth_apikey":   "API密钥",
        "elastic_auth_basic":    "基础认证",
        "elastic_field_url":     "Elasticsearch地址",
        "elastic_field_apikey":  "API密钥",
        "elastic_field_username":"用户名",
        "elastic_field_password":"密码",
        "elastic_connect":       "连接",
        "elastic_connecting":    "连接中…",
        "elastic_connected":     "已连接 ✓",
        "elastic_card_query":    "查询",
        "elastic_field_index":   "索引",
        "elastic_field_ts":      "时间戳字段",
        "elastic_field_query":   "查询字符串",
        "elastic_query_hint":    "level:ERROR AND service:myapp",
        "elastic_field_interval":"轮询间隔（秒）",
        "elastic_open":          "打开日志 ↗",
        "elastic_no_indices":    "未找到索引",
        # ── Railway ───────────────────────────────────────────────────
        "railway_field_token":   "API令牌",
        "railway_connect":       "连接",
        "railway_connecting":    "连接中…",
        "railway_connected":     "已连接 ✓",
        "railway_card_project":  "项目",
        "railway_no_projects":   "未找到项目",
        "railway_card_service":  "服务",
        "railway_no_services":   "未找到服务",
        "railway_field_interval":"轮询间隔（秒）",
        "railway_open":          "打开日志 ↗",
        # ── Fly.io ────────────────────────────────────────────────────
        "flyio_field_token":     "API令牌",
        "flyio_connect":         "连接",
        "flyio_connecting":      "连接中…",
        "flyio_connected":       "已连接 ✓",
        "flyio_card_app":        "应用",
        "flyio_no_apps":         "未找到应用",
        "flyio_field_interval":  "轮询间隔（秒）",
        "flyio_open":            "打开日志 ↗",
        # ── Kubernetes ────────────────────────────────────────────────
        "kubernetes_not_available": "未找到kubectl。请安装kubectl并确保其在PATH中。",
        "kubernetes_card_cluster":"集群",
        "kubernetes_field_context":"上下文",
        "kubernetes_field_ns":   "命名空间",
        "kubernetes_connect":    "连接",
        "kubernetes_connecting": "连接中…",
        "kubernetes_connected":  "已连接 ✓",
        "kubernetes_card_pod":   "Pod",
        "kubernetes_no_ns":      "未找到命名空间",
        "kubernetes_no_pods":    "未找到Pod",
        "kubernetes_field_container": "容器（可选）",
        "kubernetes_open":       "流式传输日志 ↗",
        # ── Cloudflare Workers ────────────────────────────────────────
        "cf_field_token":        "API 令牌",
        "cf_field_account_id":   "账户 ID",
        "cf_connect":            "连接",
        "cf_connecting":         "连接中…",
        "cf_connected":          "已连接 ✓",
        "cf_card_workers":       "Workers",
        "cf_no_workers":         "该账户中未找到 Workers",
        "cf_missing_fields":     "需要提供 API 令牌和账户 ID",
        "cf_open":               "实时查看日志 ↗",
        # ── Credential storage ────────────────────────────────────────
        # ── Remote panel ─────────────────────────────────────────────
        "remote_title":          "远程源",
        "remote_dialog_title":   "添加远程源",
        "remote_dialog_header":  "添加源",
        "remote_back":               "← 返回",
        "remote_choose":             "选择提供商",
        "remote_open":               "打开",
        "remote_add_connection":     "+ 添加连接",
        "remote_no_connections":     "无远程连接",
        "remote_no_connections_sub": "点击添加以连接提供商",
        "remote_save_open":          "保存并打开",
        "remote_cancel":             "取消",
        "remote_select_provider":    "选择提供商进行配置",
        "remote_new_connection":     "新建连接",
        "remote_connection_name":    "连接名称",
        "remote_add_btn":            "+ 添加",
        "remote_add_title":          "添加连接",
        "remote_add_header":         "添加远程连接",
        "saved_configs":             "已保存的配置",
        "new_config":                "新配置",
        "help_dialog_title":         "配置指南",
        "help_dialog_close":         "关闭",
        # ── Provider help content ──────────────────────────────────────
        "help_cloudwatch": (
            "<h3>AWS CloudWatch</h3>"
            "<p><b>选项 1 — AWS 配置文件（推荐）</b><br>"
            "选择 <em>AWS Profile</em>，从 <code>~/.aws/credentials</code> 中选择已配置的配置文件。</p>"
            "<p><b>选项 2 — 手动密钥</b></p>"
            "<ol><li>AWS 控制台 → <b>IAM → 用户 → 您的用户 → 安全凭证</b></li>"
            "<li>点击 <b>创建访问密钥</b></li>"
            "<li>复制 <b>Access Key ID</b> 和 <b>Secret Access Key</b>，选择您的<b>区域</b></li></ol>"
            "<p>所需权限：<code>logs:DescribeLogGroups</code>、<code>logs:FilterLogEvents</code></p>"
        ),
        "help_ssh": (
            "<h3>SSH — 远程文件</h3>"
            "<p>填写连接字段：</p>"
            "<ul><li><b>Host</b>：服务器 IP 或主机名</li>"
            "<li><b>Port</b>：通常为 <code>22</code></li>"
            "<li><b>User</b>：您的 SSH 用户名</li>"
            "<li><b>SSH Key</b>：私钥路径（例如 <code>~/.ssh/id_rsa</code>）</li>"
            "<li><b>Remote path</b>：日志文件的完整路径（例如 <code>/var/log/app.log</code>）</li></ul>"
            "<p>在服务器上授权密钥：</p>"
            "<pre>ssh-copy-id -i ~/.ssh/id_rsa.pub user@host</pre>"
        ),
        "help_docker": (
            "<h3>Docker</h3>"
            "<p>Docker 必须在此机器上运行，无需凭证。</p>"
            "<p><b>Containers 标签</b>：选择一个运行中的容器以实时查看日志（相当于 <code>docker logs -f</code>）。</p>"
            "<p><b>Compose 标签</b>：选择一个 Docker Compose 项目以查看所有服务的日志。</p>"
            "<p><b>Exec 标签</b>：在容器内选择一个文件路径进行监控。</p>"
        ),
        "help_vercel": (
            "<h3>Vercel</h3>"
            "<p><b>获取 API Token：</b></p>"
            "<ol><li>访问 <b>vercel.com → Account Settings → Tokens</b></li>"
            "<li>点击 <b>Create Token</b> 并为其命名</li>"
            "<li>将 token 粘贴到 SimpleLog 并点击<b>连接</b></li></ol>"
            "<p>然后选择您的<b>项目</b>和<b>部署</b>以实时查看运行日志。</p>"
        ),
        "help_gcp": (
            "<h3>GCP Cloud Logging</h3>"
            "<p><b>创建 Service Account 密钥：</b></p>"
            "<ol><li>GCP 控制台 → <b>IAM & Admin → Service Accounts</b></li>"
            "<li>选择或创建一个具有 <b>Logging → Logs Viewer</b> 角色的账号</li>"
            "<li>选项卡 <b>Keys → Add Key → JSON</b> → 下载文件</li></ol>"
            "<p>在 SimpleLog 中：</p>"
            "<ul><li><b>Credentials file</b>：下载的 JSON 文件路径</li>"
            "<li><b>Project ID</b>：GCP 控制台标题中显示（例如 <code>my-project-123</code>）</li></ul>"
        ),
        "help_azure": (
            "<h3>Azure Monitor</h3>"
            "<p><b>1. 获取 Workspace ID：</b><br>"
            "Log Analytics Workspace → <b>Settings → Agents</b> → 复制 <b>Workspace ID</b></p>"
            "<p><b>2. 创建 App Registration：</b></p>"
            "<ol><li>Azure Active Directory → <b>App registrations → New registration</b></li>"
            "<li>复制 <b>Application (client) ID</b> 和 <b>Directory (tenant) ID</b></li>"
            "<li><b>Certificates &amp; secrets → New client secret</b> → 复制 <b>Value</b></li>"
            "<li>在 workspace 中：<b>Access control (IAM) → Add role → Log Analytics Reader</b>，分配给此应用</li></ol>"
            "<p><b>在 SimpleLog 中：</b>填写 Workspace ID、Tenant ID、Client ID、Client Secret，然后输入 KQL 查询。</p>"
        ),
        "help_loki": (
            "<h3>Grafana Loki</h3>"
            "<p><b>自托管 / 本地：</b>直接输入 URL（例如 <code>http://localhost:3100</code>），无需凭证。</p>"
            "<p><b>Grafana Cloud：</b></p>"
            "<ol><li>进入您的 Grafana Cloud 栈 → <b>Connections → Data sources → Loki</b></li>"
            "<li>复制 <b>URL</b>、<b>User</b>，并在 <b>Access Policies</b> 中生成 token</li></ol>"
            "<p><b>Query (LogQL)：</b>例如 <code>{app=\"my-app\"}</code>，或留空查看所有流。</p>"
        ),
        "help_datadog": (
            "<h3>Datadog</h3>"
            "<p><b>API 密钥：</b><br>"
            "Organization Settings → <b>API Keys → New Key</b> → 复制</p>"
            "<p><b>Application 密钥：</b><br>"
            "Organization Settings → <b>Application Keys → New Key</b> → 复制</p>"
            "<p><b>在 SimpleLog 中：</b>选择站点（例如 US1），粘贴两个密钥，可选添加查询过滤器（例如 <code>service:api</code>）。</p>"
        ),
        "help_elastic": (
            "<h3>Elasticsearch</h3>"
            "<p><b>自托管 / 本地：</b>输入 URL（例如 <code>http://localhost:9200</code>）和索引名称。禁用安全时无需凭证。</p>"
            "<p><b>Elastic Cloud：</b></p>"
            "<ol><li>进入您的部署 → <b>Security → API Keys → Create API key</b></li>"
            "<li>或使用用户名/密码</li></ol>"
            "<p><b>在 SimpleLog 中：</b>填写 URL、Index（例如 <code>logs-*</code>）和凭证（如需要）。</p>"
        ),
        "help_railway": (
            "<h3>Railway</h3>"
            "<p><b>获取 Token：</b></p>"
            "<ol><li>Railway 控制台 → <b>Account Settings → Tokens → Create Token</b></li>"
            "<li>将 token 粘贴到 SimpleLog 并点击<b>连接</b></li></ol>"
            "<p>然后选择您的<b>项目</b>和<b>服务</b>以查看日志。</p>"
        ),
        "help_flyio": (
            "<h3>Fly.io</h3>"
            "<p><b>获取 Token：</b></p>"
            "<ol><li>安装 CLI：<code>curl -L https://fly.io/install.sh | sh</code></li>"
            "<li>登录：<code>fly auth login</code></li>"
            "<li>获取 token：<code>fly auth token</code></li>"
            "<li>将输出粘贴到 SimpleLog 并点击<b>连接</b></li></ol>"
            "<p>然后选择您的 <b>app</b> 以查看日志。</p>"
        ),
        "help_kubernetes": (
            "<h3>Kubernetes</h3>"
            "<p>SimpleLog 读取您现有的 <code>~/.kube/config</code>，无需输入凭证。</p>"
            "<p><b>步骤：</b></p>"
            "<ol><li>选择一个<b>上下文</b>（集群）</li>"
            "<li>选择一个<b>命名空间</b></li>"
            "<li>点击<b>连接</b>加载 Pod 列表</li>"
            "<li>选择一个 <b>Pod</b> 以查看其日志</li></ol>"
        ),
        "help_cloudflare": (
            "<h3>Cloudflare Workers</h3>"
            "<p><b>获取 Account ID：</b><br>"
            "登录 <b>dash.cloudflare.com</b> → 选择任意域名 → Account ID 显示在右侧边栏（32 位十六进制字符）。</p>"
            "<p><b>创建 API Token：</b></p>"
            "<ol><li><b>My Profile → API Tokens → Create Token → Custom Token</b></li>"
            "<li>添加以下权限：<br>"
            "— Account → <b>Workers Scripts : Read</b><br>"
            "— Account → <b>Workers Tail : Read</b><br>"
            "— User → <b>User Details : Read</b></li>"
            "<li>复制生成的 token</li></ol>"
            "<p>将 Account ID 和 token 粘贴到 SimpleLog，点击<b>连接</b>，然后选择一个 Worker。</p>"
        ),
    },
}


def tr(key: str, **kwargs: object) -> str:
    """Return translated string for *key* in the current locale."""
    lang = _STRINGS.get(_locale, _STRINGS["en"])
    text = lang.get(key) or _STRINGS["en"].get(key) or key
    return text.format(**kwargs) if kwargs else text


def set_locale(locale: str) -> None:
    global _locale
    _locale = locale if locale in _STRINGS else "en"


def get_locale() -> str:
    return _locale


def load_locale() -> None:
    """Load persisted locale preference on startup."""
    global _locale
    try:
        prefs = json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
        candidate = prefs.get("locale", "en")
        if candidate in _STRINGS:
            _locale = candidate
    except Exception:
        pass


def save_locale() -> None:
    """Persist current locale to prefs file."""
    try:
        _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            prefs = json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
        except Exception:
            prefs = {}
        prefs["locale"] = _locale
        tmp = _PREFS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(prefs, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_PREFS_PATH)
    except Exception:
        pass
