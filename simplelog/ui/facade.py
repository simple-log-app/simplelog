"""ui.py — SimpleLog UI facade.

The UI lives in ui_theme, ui_widgets, panels/, remote_dialogs, log_model,
log_view, sidebar and main_window; this module re-exports their names so
`from ui import MainWindow` keeps working.
"""

from simplelog.core.log_model import (  # noqa: F401
    _CLASSIFY_PATTERNS,
    _EXPANDED_ROLE,
    _ITEM_ROLE,
    _MAIN_KEYS,
    LogItem,
    LogModel,
    TermRow,
    _classify_line,
    _line_matches,
    _resolve_main_key,
    _try_parse_json,
)
from simplelog.ui.highlight_dialog import (  # noqa: F401
    HighlightRulesDialog,
    _RuleRow,
)
from simplelog.ui.log_view import (  # noqa: F401
    _BADGE_COL_W,
    _LEVEL_BADGE_TEXT,
    _LEVEL_BG,
    _LEVEL_COLORS,
    _MATCH_BG,
    _MATCH_FOCUSED_BG,
    _QCOLORS,
    _ROW_H,
    _ROW_MATCH_BG,
    _ROW_MATCH_FOCUSED_BG,
    _SELECTION_BG,
    _SOURCE_COLORS,
    _TABLE_HEAD_H,
    _TABLE_PAD_B,
    _TABLE_ROW_H,
    _TS_COL_W,
    LogDelegate,
    LogViewer,
    _LogListView,
    _match_rects,
    _qcolor,
)
from simplelog.ui.main_window import (  # noqa: F401
    ChangelogDialog,
    MainWindow,
    SideStack,
    macos_app_bundle,
    macos_update_script,
)
from simplelog.ui.panels.azure import (  # noqa: F401
    AzurePanel,
    _AzureConnectWorker,
)
from simplelog.ui.panels.base import (  # noqa: F401
    FIELD_STYLE,
    LBL_STYLE,
    LIST_STYLE,
    ProviderPanel,
)
from simplelog.ui.panels.betterstack import BetterStackPanel  # noqa: F401
from simplelog.ui.panels.cloudflare import (  # noqa: F401
    CloudflarePanel,
    _CloudflareConnectWorker,
)
from simplelog.ui.panels.cloudwatch import (  # noqa: F401
    CloudWatchPanel,
)
from simplelog.ui.panels.datadog import (  # noqa: F401
    DatadogPanel,
    _DatadogConnectWorker,
)
from simplelog.ui.panels.docker import (  # noqa: F401
    DockerPanel,
)
from simplelog.ui.panels.elastic import (  # noqa: F401
    ElasticPanel,
    _ElasticConnectWorker,
)
from simplelog.ui.panels.file import (  # noqa: F401
    FilePanel,
)
from simplelog.ui.panels.flyio import (  # noqa: F401
    FlyioPanel,
    _FlyioConnectWorker,
)
from simplelog.ui.panels.form import Field, FormPanel  # noqa: F401
from simplelog.ui.panels.gcp import (  # noqa: F401
    GCPPanel,
    _GCPConnectWorker,
    _GCPListProjectsWorker,
)
from simplelog.ui.panels.heroku import HerokuPanel  # noqa: F401
from simplelog.ui.panels.journald import JournaldPanel  # noqa: F401
from simplelog.ui.panels.kubernetes import (  # noqa: F401
    KubernetesPanel,
    _K8sConnectWorker,
    _K8sListPodsWorker,
)
from simplelog.ui.panels.loki import (  # noqa: F401
    LokiPanel,
    _LokiConnectWorker,
)
from simplelog.ui.panels.railway import (  # noqa: F401
    RailwayPanel,
    _RailwayConnectWorker,
)
from simplelog.ui.panels.render import RenderPanel  # noqa: F401
from simplelog.ui.panels.sentry import SentryPanel  # noqa: F401
from simplelog.ui.panels.splunk import SplunkPanel  # noqa: F401
from simplelog.ui.panels.ssh import (  # noqa: F401
    SSHPanel,
    SSHRecentManager,
    _SftpBrowserDialog,
    _SSHConnectWorker,
)
from simplelog.ui.panels.vercel import (  # noqa: F401
    VercelPanel,
    _VercelConnectWorker,
    _VercelFetchDeployWorker,
    _VercelFetchProjectsWorker,
)
from simplelog.ui.remote_dialogs import (  # noqa: F401
    _RUNNING_WORKERS,
    AddConnectionDialog,
    RemoteHomePanel,
    _ConnRow,
    _reap_worker,
    _restore_widget_state,
    _widget_state,
)
from simplelog.ui.sidebar import (  # noqa: F401
    FilterSearchSidebar,
    _HistoryLineEdit,
    _TermRowWidget,
)
from simplelog.ui.ui_theme import (  # noqa: F401
    _SVG_AZURE,
    _SVG_CHEVRON_LEFT,
    _SVG_CHEVRON_RIGHT,
    _SVG_CLOSE_X,
    _SVG_CLOUD,
    _SVG_CLOUDFLARE,
    _SVG_DATADOG,
    _SVG_DOCKER,
    _SVG_ELASTIC,
    _SVG_FLYIO,
    _SVG_FOLDER,
    _SVG_GCP,
    _SVG_KUBERNETES,
    _SVG_LOKI,
    _SVG_RAILWAY,
    _SVG_REMOTE,
    _SVG_SSH,
    _SVG_STOP_SQ,
    _SVG_TRASH,
    _SVG_VERCEL,
    C_ACCENT,
    C_ACCENT_DIM,
    C_BG,
    C_BORDER,
    C_CARD,
    C_DEBUG,
    C_DIVIDER,
    C_ERR,
    C_INFO,
    C_MUTED,
    C_PANEL,
    C_RAIL,
    C_SEL_BG,
    C_SIDE,
    C_STATUS,
    C_TEXT,
    C_TRACE,
    C_TS,
    C_WARN,
    _svg_icon,
    apply_style,
)
from simplelog.ui.ui_widgets import (  # noqa: F401
    MergeTabsDialog,
    NavButton,
    NavRail,
    NoScrollComboBox,
    OpenModeWidget,
    _field_label,
    _FieldLabel,
    _ghost_btn,
    _HelpDialog,
    _lookback_combo,
    _primary_btn,
    _ProfileBar,
    _SidebarEdgeBtn,
    _SLTabBar,
    _SLTabWidget,
    _TabCloseBtn,
    make_card,
)
