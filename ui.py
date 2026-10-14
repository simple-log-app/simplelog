"""ui.py — SimpleLog UI facade.

The UI lives in ui_theme, ui_widgets, panels/, remote_dialogs, log_model,
log_view, sidebar and main_window; this module re-exports their names so
`from ui import MainWindow` keeps working.
"""

from highlight_dialog import (  # noqa: F401
    HighlightRulesDialog,
    _RuleRow,
)
from log_model import (  # noqa: F401
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
from log_view import (  # noqa: F401
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
from main_window import (  # noqa: F401
    ChangelogDialog,
    MainWindow,
    SideStack,
    macos_app_bundle,
    macos_update_script,
)
from panels.azure import (  # noqa: F401
    AzurePanel,
    _AzureConnectWorker,
)
from panels.base import (  # noqa: F401
    FIELD_STYLE,
    LBL_STYLE,
    LIST_STYLE,
    ProviderPanel,
)
from panels.cloudflare import (  # noqa: F401
    CloudflarePanel,
    _CloudflareConnectWorker,
)
from panels.cloudwatch import (  # noqa: F401
    CloudWatchPanel,
)
from panels.datadog import (  # noqa: F401
    DatadogPanel,
    _DatadogConnectWorker,
)
from panels.docker import (  # noqa: F401
    DockerPanel,
)
from panels.elastic import (  # noqa: F401
    ElasticPanel,
    _ElasticConnectWorker,
)
from panels.file import (  # noqa: F401
    FilePanel,
)
from panels.flyio import (  # noqa: F401
    FlyioPanel,
    _FlyioConnectWorker,
)
from panels.gcp import (  # noqa: F401
    GCPPanel,
    _GCPConnectWorker,
    _GCPListProjectsWorker,
)
from panels.kubernetes import (  # noqa: F401
    KubernetesPanel,
    _K8sConnectWorker,
    _K8sListPodsWorker,
)
from panels.loki import (  # noqa: F401
    LokiPanel,
    _LokiConnectWorker,
)
from panels.railway import (  # noqa: F401
    RailwayPanel,
    _RailwayConnectWorker,
)
from panels.ssh import (  # noqa: F401
    SSHPanel,
    SSHRecentManager,
    _SftpBrowserDialog,
    _SSHConnectWorker,
)
from panels.vercel import (  # noqa: F401
    VercelPanel,
    _VercelConnectWorker,
    _VercelFetchDeployWorker,
    _VercelFetchProjectsWorker,
)
from remote_dialogs import (  # noqa: F401
    _RUNNING_WORKERS,
    AddConnectionDialog,
    RemoteHomePanel,
    _ConnRow,
    _reap_worker,
    _restore_widget_state,
    _widget_state,
)
from sidebar import (  # noqa: F401
    FilterSearchSidebar,
    _HistoryLineEdit,
    _TermRowWidget,
)
from ui_theme import (  # noqa: F401
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
from ui_widgets import (  # noqa: F401
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
