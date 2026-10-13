"""Log list delegate and the LogViewer widget."""

from __future__ import annotations

import re
from datetime import datetime

from PyQt6.QtCore import (
    QEvent,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainterPath,
    QTextLayout,
    QTextOption,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QMenu,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

import i18n
from log_model import (
    _EXPANDED_ROLE,
    _ITEM_ROLE,
    LogItem,
    LogModel,
    _classify_line,
    _line_matches,
)
from ui_theme import (
    _SVG_CLOSE_X,
    _SVG_STOP_SQ,
    _SVG_TRASH,
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
    C_SEL_BG,
    C_TEXT,
    C_TRACE,
    C_TS,
    C_WARN,
    _svg_icon,
)

# ── LogDelegate ────────────────────────────────────────────────────────────────

_ROW_H         = 24   # px — plain / JSON-collapsed row height (normal density)
_TABLE_HEAD_H  = 22   # px — table header row height
_TABLE_ROW_H   = 18   # px — each key/value data row height
_TABLE_PAD_B   = 6    # px — padding below last table row
_BADGE_COL_W   = 52   # px — level badge column width
_TS_COL_W      = 92   # px — timestamp column width

_LEVEL_COLORS = {
    "error": C_ERR,
    "warn":  C_WARN,
    "info":  C_INFO,
    "debug": C_DEBUG,
    "trace": C_TRACE,
    "plain": C_TEXT,
}

_LEVEL_BG = {
    "error": QColor(240, 120, 120, 26),   # 10% opacity
    "warn":  QColor(240, 192, 96, 20),
    "info":  QColor(86, 207, 128, 18),
    "debug": QColor(91, 143, 255, 20),
    "trace": QColor(176, 124, 240, 20),
    "plain": QColor(0, 0, 0, 0),
}

_LEVEL_BADGE_TEXT = {
    "error": "ERROR",
    "warn":  "WARN",
    "info":  "INFO",
    "debug": "DEBUG",
    "trace": "TRACE",
    "plain": "",
}


_QCOLORS: dict[str, QColor] = {}


def _qcolor(spec: str) -> QColor:
    """Parse a colour string once (painting runs for every visible row, every frame)."""
    c = _QCOLORS.get(spec)
    if c is None:
        c = _QCOLORS[spec] = QColor(spec)
    return c


_SELECTION_BG = QColor(26, 58, 110, 85)
_MATCH_BG = QColor(255, 213, 79, 102)
_MATCH_FOCUSED_BG = QColor(255, 213, 79, 170)
_ROW_MATCH_BG = QColor(255, 213, 79, 36)          # whole JSON row that contains a match
_ROW_MATCH_FOCUSED_BG = QColor(255, 213, 79, 80)


def _match_rects(
    text: str, font: QFont, width: int, ranges: list[tuple[int, int]],
) -> list[tuple[int, QRectF]]:
    """(range index, rectangle) pairs, relative to the text origin, covering *ranges*.

    Uses the same word-wrapping as drawText(..., TextWordWrap), so a match on the second
    visual line of a long message is highlighted on that line.
    """
    if not text:
        return []
    layout = QTextLayout(text, font)
    opt = QTextOption()
    opt.setWrapMode(QTextOption.WrapMode.WordWrap)
    layout.setTextOption(opt)
    lines = []
    y = 0.0
    layout.beginLayout()
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(max(1, width))
        line.setPosition(QPointF(0, y))
        y += line.height()
        lines.append(line)
    layout.endLayout()
    rects: list[tuple[int, QRectF]] = []
    for idx, (start, length) in enumerate(ranges):
        end = start + length
        for line in lines:
            a = max(start, line.textStart())
            b = min(end, line.textStart() + line.textLength())
            if a < b:
                x0 = line.cursorToX(a)
                x1 = line.cursorToX(b)
                x0 = x0[0] if isinstance(x0, tuple) else x0
                x1 = x1[0] if isinstance(x1, tuple) else x1
                rects.append((idx, QRectF(x0, line.y(), max(1.0, x1 - x0), line.height())))
    return rects


class LogDelegate(QStyledItemDelegate):
    """Paints log rows. JSON rows are collapsible; plain rows use level colors."""

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        # viewer is the LogViewer — used to read show_timestamps flag
        self._viewer = viewer
        self._search_highlights: dict[int, list[tuple[int, int]]] = {}
        self._focused_match: tuple[int, int, int] | None = None  # (vis_idx, start, len)
        self._fm: QFontMetrics | None = None
        self._fm_key: tuple | None = None
        self._press: tuple[int, object] | None = None   # (row, pos) of the left-button press
        self._badge_cache: dict[tuple, tuple] = {}      # (font, level) -> (font, w, h)

    def set_search_highlights(
        self,
        highlights: dict[int, list[tuple[int, int]]],
    ) -> None:
        self._search_highlights = highlights

    def set_focused_match(self, vis_idx: int, char_start: int, char_len: int) -> None:
        self._focused_match = (vis_idx, char_start, char_len)

    # ── QStyledItemDelegate interface ─────────────────────────────────────────

    def _metrics(self) -> tuple[QFontMetrics, tuple]:
        font = self._viewer._log_font
        key = (font.family(), font.pointSize())
        if self._fm_key != key:
            self._fm = QFontMetrics(font)
            self._fm_key = key
        return self._fm, key   # type: ignore[return-value]

    def sizeHint(self, option, index):
        item = index.data(_ITEM_ROLE)
        fm, font_key = self._metrics()
        row_h = max(_ROW_H, fm.height() + 8)
        if item is None:
            return QSize(option.rect.width(), row_h)
        if item.is_break:
            return QSize(option.rect.width(), 28)
        if item.is_json and item.expanded and item.json_data:
            n = len(item.json_data)
            return QSize(
                option.rect.width(),
                row_h + _TABLE_HEAD_H + _TABLE_ROW_H * n + _TABLE_PAD_B,
            )
        if not item.is_json:
            vp_w = self._viewer._list_view.viewport().width()
            show_ts = bool(self._viewer.show_timestamps and item.ts_ms)
            wrap = self._viewer.wrap_lines
            # Wrapping a long line is the costly part: only redo it when the width,
            # the font, the timestamp column or the wrap mode changed.
            key = (vp_w, font_key, show_ts, wrap)
            cached = item.size_cache
            if cached is not None and cached[0] == key:
                return QSize(cached[2], cached[1])
            x_offset = _BADGE_COL_W + (_TS_COL_W if show_ts else 0)
            if wrap:
                avail_w = max(1, vp_w - x_offset - 14)
                br = fm.boundingRect(
                    QRect(0, 0, avail_w, 0), Qt.TextFlag.TextWordWrap, item.message,
                )
                height, width = max(row_h, br.height() + 6), vp_w
            else:
                # One line per row: as wide as the text so the view scrolls sideways
                height = row_h
                width = max(vp_w, x_offset + 14 + fm.horizontalAdvance(item.message))
            item.size_cache = (key, height, width)
            return QSize(width, height)
        return QSize(option.rect.width(), row_h)

    def paint(self, painter, option, index):
        item = index.data(_ITEM_ROLE)
        if item is None:
            return

        painter.save()
        painter.setFont(self._viewer._log_font)
        painter.setClipRect(option.rect)

        if item.is_break:
            self._paint_break(painter, option, item)
        else:
            # Selection background
            if option.state & QStyle.StateFlag.State_Selected:
                painter.fillRect(option.rect, _SELECTION_BG)
            if item.is_json:
                self._paint_json(painter, option, index, item)
            else:
                self._paint_plain(painter, option, index, item)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress:
            left = event.button() == Qt.MouseButton.LeftButton
            self._press = (index.row(), event.position().toPoint()) if left else None
        elif kind == QEvent.Type.MouseButtonRelease:
            press, self._press = self._press, None
            item = index.data(_ITEM_ROLE)
            # A plain left click toggles; right-click, drag-selection and Ctrl/Shift
            # clicks (multi-select) must not expand the row.
            if (press is not None
                    and event.button() == Qt.MouseButton.LeftButton
                    and press[0] == index.row()
                    and (event.position().toPoint() - press[1]).manhattanLength() < 5
                    and not (event.modifiers() & (Qt.KeyboardModifier.ShiftModifier
                                                  | Qt.KeyboardModifier.ControlModifier))
                    and item and item.is_json and item.json_data):
                model.setData(index, not item.expanded, _EXPANDED_ROLE)
                return True
        return False

    # ── Private paint helpers ─────────────────────────────────────────────────

    def _baseline(self, rect: QRect, fm: QFontMetrics, row_h: int = _ROW_H) -> int:
        """Return y baseline for text vertically centered in a row."""
        return rect.top() + (row_h - fm.height()) // 2 + fm.ascent()

    def _draw_segments(
        self,
        painter,
        x: int,
        y: int,
        segments: list[tuple[str, str]],
        fm: QFontMetrics,
    ) -> int:
        """Draw (text, color) segments left-to-right. Returns x after last segment."""
        for text, color in segments:
            painter.setPen(_qcolor(color))
            painter.drawText(x, y, text)
            x += fm.horizontalAdvance(text)
        return x

    def _paint_break(self, painter, option, item: LogItem) -> None:
        rect = option.rect
        painter.fillRect(rect, QColor("#111111"))
        mid_y = rect.top() + rect.height() // 2
        painter.setPen(QColor(C_DIVIDER))
        painter.drawLine(rect.left(), mid_y, rect.right(), mid_y)
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(item.message)
        tx = rect.left() + (rect.width() - text_w) // 2
        ty = self._baseline(rect, fm, rect.height())
        painter.fillRect(QRect(tx - 6, rect.top(), text_w + 12, rect.height()), QColor("#111111"))
        painter.setPen(QColor(C_MUTED))
        painter.drawText(tx, ty, item.message)

    @staticmethod
    def _ts_text(item: LogItem) -> str:
        if item.ts_text is None:
            item.ts_text = datetime.fromtimestamp(item.ts_ms / 1000).strftime("%H:%M:%S")
        return item.ts_text

    @staticmethod
    def _level(item: LogItem) -> str:
        if item.level is None:
            item.level = _classify_line(item.message)
        return item.level

    def _paint_plain(self, painter, option, index, item: LogItem) -> None:
        fm    = painter.fontMetrics()
        rect  = option.rect
        level = self._level(item)
        color = _LEVEL_COLORS.get(level, C_TEXT)

        vis_idx = index.row()
        # Compute message x start for search bg
        msg_x = rect.left() + _BADGE_COL_W
        if self._viewer.show_timestamps and item.ts_ms:
            msg_x += _TS_COL_W
        self._draw_search_bg(painter, rect, msg_x, item.message, vis_idx)

        # Level badge column
        self._paint_level_badge(painter, rect, level, fm)

        x = rect.left() + _BADGE_COL_W

        # Timestamp column
        if self._viewer.show_timestamps and item.ts_ms:
            ts_rect = QRect(x, rect.top(), _TS_COL_W, rect.height())
            painter.setPen(_qcolor(C_TS))
            painter.drawText(ts_rect,
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             self._ts_text(item))
            x += _TS_COL_W

        # Message column
        text_rect = QRect(x, rect.top() + 3, rect.right() - x - 14, rect.height() - 6)
        painter.setPen(_qcolor(color))
        flags = Qt.AlignmentFlag.AlignTop
        flags |= (Qt.TextFlag.TextWordWrap if self._viewer.wrap_lines
                  else Qt.TextFlag.TextSingleLine)
        painter.drawText(text_rect, flags, item.message)

    def _paint_level_badge(self, painter, rect: QRect, level: str, _fm=None) -> None:
        """Draw the level badge in the left column."""
        badge_text = _LEVEL_BADGE_TEXT.get(level, "")
        if not badge_text:
            return
        color = _qcolor(_LEVEL_COLORS.get(level, C_TEXT))
        bg    = _LEVEL_BG.get(level, QColor(0, 0, 0, 0))

        # Smaller bold badge font; its metrics only depend on the log font and the level
        orig_font = painter.font()
        cache_key = (orig_font.family(), orig_font.pointSize(), level)
        cached = self._badge_cache.get(cache_key)
        if cached is None:
            badge_font = QFont(orig_font)
            badge_font.setPointSize(max(6, badge_font.pointSize() - 1))
            badge_font.setBold(True)
            badge_fm = QFontMetrics(badge_font)
            cached = self._badge_cache[cache_key] = (
                badge_font,
                badge_fm.horizontalAdvance(badge_text) + 10,   # 5px each side
                badge_fm.height() + 2,
            )
        badge_font, badge_w, badge_h = cached
        painter.setFont(badge_font)
        bx = rect.left() + 14
        by = rect.top() + (rect.height() - badge_h) // 2

        # Draw badge background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg))
        path = QPainterPath()
        path.addRoundedRect(bx, by, badge_w, badge_h, 3, 3)
        painter.drawPath(path)

        # Draw badge text
        painter.setPen(color)
        painter.drawText(
            QRect(bx, by, badge_w, badge_h),
            Qt.AlignmentFlag.AlignCenter,
            badge_text,
        )

        # Restore font
        painter.setFont(orig_font)

    def _paint_json(self, painter, option, index, item: LogItem) -> None:
        fm   = painter.fontMetrics()
        rect = option.rect
        y    = self._baseline(rect, fm)
        level = self._level(item)
        color = _LEVEL_COLORS.get(level, C_TEXT)

        # A JSON row only shows part of its message: tint the whole row on a match
        if self._search_highlights.get(index.row()):
            focused = self._focused_match is not None and self._focused_match[0] == index.row()
            painter.fillRect(
                QRect(rect.left(), rect.top(), rect.width(), _ROW_H),
                _ROW_MATCH_FOCUSED_BG if focused else _ROW_MATCH_BG,
            )

        # Level badge column
        self._paint_level_badge(painter, rect, level, fm)

        # Restore full font after badge
        painter.setFont(self._viewer._log_font)
        fm = painter.fontMetrics()

        x = rect.left() + _BADGE_COL_W

        # Timestamp column
        if self._viewer.show_timestamps and item.ts_ms:
            x = self._draw_segments(painter, x, y, [(self._ts_text(item) + "  ", C_TS)], fm)
        else:
            x += 0  # no ts column when disabled

        # ▸/▾ toggle arrow (C_TRACE color)
        arrow = "▾" if item.expanded else "▸"
        x = self._draw_segments(painter, x, y, [(arrow + " ", C_TRACE)], fm)

        # Main message value
        if item.main_key and item.json_data:
            main_val = str(item.json_data[item.main_key])[:80]
            x = self._draw_segments(painter, x, y, [(main_val, color)], fm)
        elif item.json_data:
            pairs = list(item.json_data.items())[:2]
            for k, v in pairs:
                x = self._draw_segments(painter, x, y,
                    [(f" {k}", C_DEBUG), ("=", C_MUTED), (str(v)[:20], C_INFO)], fm)

        # Summary of remaining keys (collapsed only)
        if not item.expanded and item.json_data:
            shown_keys = {item.main_key} if item.main_key else set()
            if not item.main_key:
                shown_keys = {k for k, _ in list(item.json_data.items())[:2]}
            rest = [k for k in item.json_data if k not in shown_keys]
            for k in rest[:3]:
                x = self._draw_segments(painter, x, y,
                    [("  ", C_MUTED), (k, C_DEBUG), ("=", C_MUTED),
                     (str(item.json_data[k])[:20], C_INFO)], fm)
            if len(rest) > 3:
                x = self._draw_segments(painter, x, y,
                    [(f"  +{len(rest)-3}", C_MUTED)], fm)

        # Expanded block
        if item.expanded and item.json_data:
            self._paint_json_expanded(painter, rect, item, fm)

    def _paint_json_expanded(self, painter, rect: QRect, item: LogItem, fm: QFontMetrics) -> None:
        """Render expanded JSON as indented key: value lines below the collapsed row."""
        block_x = rect.left() + _BADGE_COL_W + 12
        block_y = rect.top() + _ROW_H + 4
        block_w = rect.width() - _BADGE_COL_W - 26

        # Block background
        n = len(item.json_data)
        block_h = n * _TABLE_ROW_H + 8
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(C_BG)))
        border_path = QPainterPath()
        border_path.addRoundedRect(block_x, block_y, block_w, block_h, 6, 6)
        painter.drawPath(border_path)
        painter.setPen(QColor(80, 80, 100, 60))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(border_path)

        key_col_w = 110
        x_key = block_x + 12
        x_colon = x_key + key_col_w
        x_val   = x_colon + fm.horizontalAdvance(": ")

        for i, (k, v) in enumerate(item.json_data.items()):
            row_top  = block_y + 4 + i * _TABLE_ROW_H
            row_base = row_top + ((_TABLE_ROW_H - fm.height()) // 2) + fm.ascent()

            painter.setPen(QColor(C_DEBUG))
            painter.drawText(x_key, row_base, str(k)[:20])

            painter.setPen(QColor(C_MUTED))
            painter.drawText(x_colon, row_base, ": ")

            val_color = self._value_color(v)
            painter.setPen(QColor(val_color))
            painter.drawText(x_val, row_base, str(v)[:80])

    def _value_color(self, v) -> str:
        if isinstance(v, bool):
            return C_TRACE
        if isinstance(v, (int, float)):
            return C_WARN
        if v is None:
            return C_MUTED
        return C_TEXT

    def _draw_search_bg(
        self,
        painter,
        row_rect: QRect,
        text_x: int,
        text: str,
        vis_idx: int,
    ) -> None:
        """Draw yellow background rects behind search matches of a (wrapped) plain row."""
        highlights = self._search_highlights.get(vis_idx)
        if not highlights:
            return
        text_w = row_rect.right() - text_x - 14        # same box as the message column
        focused = self._focused_match
        for idx, rect in _match_rects(text, painter.font(), text_w, highlights):
            is_focused = bool(
                focused and focused[0] == vis_idx and focused[1] == highlights[idx][0]
            )
            painter.fillRect(
                rect.translated(text_x, row_rect.top() + 3),
                _MATCH_FOCUSED_BG if is_focused else _MATCH_BG,
            )


# ── LogViewer ─────────────────────────────────────────────────────────────────

class _LogListView(QListView):
    """QListView that recalculates the item sizes once a resize settles."""
    focus_in = pyqtSignal()
    break_requested = pyqtSignal()

    _RELAYOUT_DELAY_MS = 100

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Wrapping every row for each intermediate width of a window drag is wasted work
        self._relayout_timer = QTimer(self)
        self._relayout_timer.setSingleShot(True)
        self._relayout_timer.setInterval(self._RELAYOUT_DELAY_MS)
        self._relayout_timer.timeout.connect(self._relayout)

    def _relayout(self) -> None:
        self.scheduleDelayedItemsLayout()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._relayout_timer.start()

    def focusInEvent(self, event) -> None:  # noqa: N802
        super().focusInEvent(event)
        self.focus_in.emit()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.break_requested.emit()
        else:
            super().keyPressEvent(event)


_SOURCE_COLORS = {
    "cloudwatch":       C_ACCENT,
    "file":             C_INFO,
    "stdin":            C_WARN,
    "ssh":              C_TRACE,
    "docker":           C_TS,
    "docker_compose":   C_TS,
    "docker_exec_file": C_TS,
    "vercel":           C_ERR,
    "gcp":              C_INFO,
    "azure":            C_ACCENT,
    "loki":             "#f46800",
    "datadog":          "#632ca6",
    "elastic":          "#f04e98",
    "railway":          "#b975f2",
    "flyio":            "#7b3fc4",
    "kubernetes":       "#326ce5",
    "cloudflare":       "#f6821f",
}


class LogViewer(QWidget):
    stop_requested       = pyqtSignal()
    json_keys_updated    = pyqtSignal(set)
    lines_appended       = pyqtSignal()
    filter_applied       = pyqtSignal()
    pane_activated       = pyqtSignal()
    pane_close_requested = pyqtSignal()

    _MAX_LINES = 10_000
    _APPEND_COOLDOWN_MS = 50   # lines arriving faster than this are added in one go

    _FONT_SIZE_MIN = 6
    _FONT_SIZE_MAX = 20
    _FONT_SIZE_DEFAULT = 9

    def __init__(self, source_type: str = "cloudwatch", parent=None):
        super().__init__(parent)
        self._source_type = source_type
        self._font_size = self._FONT_SIZE_DEFAULT
        self._search_highlights: dict[int, list[tuple[int, int]]] = {}

        self._model = LogModel(self)
        self._model.json_keys_updated.connect(self.json_keys_updated)
        self._model.rows_appended.connect(self._on_rows_appended)
        self._model.filter_applied.connect(self.filter_applied)
        self._model._MAX_LINES = self._MAX_LINES

        self._pending: list[tuple[int, str]] = []
        self._append_timer = QTimer(self)
        self._append_timer.setSingleShot(True)
        self._append_timer.setInterval(self._APPEND_COOLDOWN_MS)
        self._append_timer.timeout.connect(self._flush_on_timer)

        self._build_ui()

        _key = id(self)
        i18n.register(_key, self.retranslate)
        self.destroyed.connect(lambda _=None, k=_key: i18n.unregister(k))

    @property
    def show_timestamps(self) -> bool:
        return self.timestamps_cb.isChecked()

    @property
    def wrap_lines(self) -> bool:
        return self.wrap_cb.isChecked()

    def _on_rows_appended(self) -> None:
        if self.autoscroll_cb.isChecked():
            self._list_view.scrollToBottom()
        self.lines_appended.emit()
        self.line_badge.setText(i18n.tr("viewer_lines", n=self._model.visible_count()))

    def _build_ui(self):
        self.setMinimumSize(50, 50)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Toolbar ──
        toolbar = QWidget()
        toolbar.setFixedHeight(34)
        toolbar.setStyleSheet(
            f"background: {C_PANEL}; border-bottom: 1px solid {C_BORDER};"
        )
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(12, 0, 12, 0)
        tb.setSpacing(8)

        src_color = _SOURCE_COLORS.get(self._source_type, C_TEXT)
        self._source_badge = QLabel(self._source_type.upper())
        self._source_badge.setStyleSheet(
            f"background: rgba(91,143,255,31); color: {src_color}; border-radius: 8px;"
            "padding: 1px 8px; font-size: 10px; font-weight: bold; border: none;"
        )

        self.title_label = QLabel("—")
        self.title_label.setStyleSheet(
            f"font-size: 12px; color: {C_MUTED}; background: transparent; border: none;"
            "font-family: 'JetBrains Mono', monospace;"
        )

        self.line_badge = QLabel(i18n.tr("viewer_lines", n=0))
        self.line_badge.setStyleSheet(
            f"color: {C_MUTED}; border: none; background: transparent;"
            "font-size: 11px;"
        )

        self.autoscroll_cb = QCheckBox()
        self.autoscroll_cb.setChecked(True)

        self.timestamps_cb = QCheckBox()
        self.timestamps_cb.setChecked(True)
        self.timestamps_cb.stateChanged.connect(self._on_timestamps_toggled)

        self.wrap_cb = QCheckBox()
        self.wrap_cb.setChecked(True)
        self.wrap_cb.stateChanged.connect(self._on_wrap_toggled)

        _icon_btn_style = (
            f"QPushButton {{ background: transparent; border: 1px solid {C_BORDER};"
            f" border-radius: 5px; padding: 0; }}"
            f"QPushButton:hover {{ border-color: {C_ACCENT}; background: {C_ACCENT_DIM}; }}"
            f"QPushButton:disabled {{ opacity: 0.4; }}"
        )
        _danger_icon_style = (
            "QPushButton { background: transparent; border: 1px solid rgba(240,120,120,80);"
            " border-radius: 5px; padding: 0; }"
            "QPushButton:hover { background: rgba(240,120,120,30); }"
        )

        _font_btn_style = (
            f"QPushButton {{ background: transparent; border: 1px solid {C_BORDER};"
            f" border-radius: 5px; padding: 0; color: {C_MUTED}; font-size: 11px; font-weight: bold; }}"
            f"QPushButton:hover {{ border-color: {C_ACCENT}; background: {C_ACCENT_DIM}; color: {C_TEXT}; }}"
        )
        self.font_dec_btn = QPushButton("A−")
        self.font_dec_btn.setFixedSize(26, 26)
        self.font_dec_btn.setStyleSheet(_font_btn_style)
        self.font_dec_btn.setToolTip("Decrease font size")
        self.font_dec_btn.clicked.connect(lambda: self._change_font_size(-1))

        self.font_inc_btn = QPushButton("A+")
        self.font_inc_btn.setFixedSize(26, 26)
        self.font_inc_btn.setStyleSheet(_font_btn_style)
        self.font_inc_btn.setToolTip("Increase font size")
        self.font_inc_btn.clicked.connect(lambda: self._change_font_size(+1))

        self.clear_btn = QPushButton()
        self.clear_btn.setObjectName("danger")
        self.clear_btn.setFixedSize(26, 26)
        self.clear_btn.setIcon(_svg_icon(_SVG_TRASH, C_ERR, 14))
        self.clear_btn.setIconSize(QSize(14, 14))
        self.clear_btn.setStyleSheet(_danger_icon_style)
        self.clear_btn.clicked.connect(self.clear)

        self.stop_btn = QPushButton()
        self.stop_btn.setFixedSize(26, 26)
        self.stop_btn.setIcon(_svg_icon(_SVG_STOP_SQ, C_MUTED, 14))
        self.stop_btn.setIconSize(QSize(14, 14))
        self.stop_btn.setStyleSheet(_icon_btn_style)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_requested)

        self.close_pane_btn = QPushButton()
        self.close_pane_btn.setFixedSize(26, 26)
        self.close_pane_btn.setIcon(_svg_icon(_SVG_CLOSE_X, C_MUTED, 12))
        self.close_pane_btn.setIconSize(QSize(12, 12))
        self.close_pane_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 5px; padding: 0; }"
            "QPushButton:hover { background: rgba(240,120,120,25); }"
        )
        self.close_pane_btn.clicked.connect(self.pane_close_requested)

        tb.addWidget(self._source_badge)
        tb.addWidget(self.title_label)
        tb.addStretch()
        tb.addWidget(self.line_badge)
        tb.addWidget(self.autoscroll_cb)
        tb.addWidget(self.timestamps_cb)
        tb.addWidget(self.wrap_cb)
        tb.addWidget(self.font_dec_btn)
        tb.addWidget(self.font_inc_btn)
        tb.addWidget(self.clear_btn)
        tb.addWidget(self.stop_btn)
        tb.addWidget(self.close_pane_btn)
        layout.addWidget(toolbar)

        # ── List view ──
        self._delegate = LogDelegate(viewer=self)
        self._list_view = _LogListView()
        self._list_view.setModel(self._model)
        self._list_view.setItemDelegate(self._delegate)
        self._list_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list_view.setUniformItemSizes(False)
        self._list_view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list_view.setStyleSheet(
            f"QListView {{ background: {C_BG}; border: none; border-radius: 0; }}"
            f"QListView::item:selected {{ background: rgba(91,143,255,20); }}"
            f"QListView::item:hover {{ background: rgba(255,255,255,5); }}"
        )
        self._log_font = QFont("JetBrains Mono")
        self._log_font.setStyleHint(QFont.StyleHint.Monospace)
        self._log_font.setPointSize(self._font_size)
        self._list_view.setFont(self._log_font)
        self._list_view.viewport().setFont(self._log_font)
        self._list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list_view.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._list_view)
        self._list_view.focus_in.connect(self.pane_activated)
        self._list_view.break_requested.connect(self.insert_break)

        self.retranslate()

    def retranslate(self) -> None:
        src_key = f"src_{self._source_type}"
        self._source_badge.setText(i18n.tr(src_key))
        self.autoscroll_cb.setText(i18n.tr("viewer_autoscroll"))
        self.timestamps_cb.setText(i18n.tr("viewer_timestamps"))
        self.wrap_cb.setText(i18n.tr("viewer_wrap"))
        self.clear_btn.setToolTip(i18n.tr("viewer_clear"))
        self.stop_btn.setToolTip(i18n.tr("viewer_stop"))
        self.line_badge.setText(i18n.tr("viewer_lines", n=self._model.visible_count()))

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)

    def _on_timestamps_toggled(self, _state=None) -> None:
        # The timestamp column narrows the text area, so wrapped rows change height
        self._list_view.scheduleDelayedItemsLayout()
        self._list_view.viewport().update()

    def _on_wrap_toggled(self, _state=None) -> None:
        # Without wrapping every row is one line; long ones scroll sideways
        self._list_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff if self.wrap_lines
            else Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._list_view.scheduleDelayedItemsLayout()
        self._list_view.viewport().update()

    def append_events(self, events: list[tuple[int, str]]) -> None:
        """Add lines. The first ones show immediately; a fast stream is grouped into
        one update per cooldown period instead of one (costly) re-layout per line."""
        if not events:
            return
        if self._append_timer.isActive():
            self._pending.extend(events)
            return
        self._model.append_events(events)
        self._append_timer.start()

    def _flush_on_timer(self) -> None:
        if self._pending:
            self.flush_pending()
            self._append_timer.start()   # data is flowing: keep grouping

    def flush_pending(self) -> None:
        """Add the lines grouped since the last update right now."""
        if self._pending:
            events, self._pending = self._pending, []
            self._model.append_events(events)

    def apply_filter(self, terms: list) -> None:
        self.flush_pending()
        self._model.apply_filter(terms)
        self.line_badge.setText(i18n.tr("viewer_lines", n=self._model.visible_count()))

    def apply_search(self, terms: list) -> list:
        """Return (visible_row_idx, char_start, char_len) for every match.

        A row matches when it satisfies the AND/OR chain of the terms, and every
        occurrence of every term in a matching row is highlighted.
        """
        self.flush_pending()
        self._search_highlights.clear()
        active = [t for t in terms if t.text.strip() and not t.key]
        if not active:
            self._delegate.set_search_highlights({})
            self._list_view.viewport().update()
            return []

        patterns = [re.compile(re.escape(t.text), re.IGNORECASE) for t in active]
        # Rows remember their last result for these terms: while following a log only
        # the rows that arrived since the previous scan are actually searched.
        terms_key = tuple((t.text, t.operator) for t in active)
        results: list[tuple[int, int, int]] = []
        highlights: dict[int, list[tuple[int, int]]] = {}

        for vis_idx, item in enumerate(self._model.visible_items()):
            if item.is_break:
                continue
            cached = item.search
            if cached is not None and cached[0] == terms_key:
                spans = cached[1]
            else:
                spans = []
                if _line_matches(item.message, active):
                    for pattern in patterns:
                        spans.extend(
                            (m.start(), m.end() - m.start())
                            for m in pattern.finditer(item.message)
                        )
                item.search = (terms_key, spans)
            if spans:
                highlights[vis_idx] = spans
                results.extend((vis_idx, start, length) for start, length in spans)

        self._search_highlights = highlights
        self._delegate.set_search_highlights(highlights)
        self._list_view.viewport().update()
        return sorted(results, key=lambda t: (t[0], t[1]))

    def scroll_to_search_match(
        self, vis_idx: int, char_start: int, char_len: int, scroll: bool = True,
    ) -> None:
        if scroll:
            idx = self._model.index(vis_idx)
            self._list_view.scrollTo(idx, QAbstractItemView.ScrollHint.EnsureVisible)
        self._delegate.set_focused_match(vis_idx, char_start, char_len)
        self._list_view.viewport().update()

    def _change_font_size(self, delta: int) -> None:
        new_size = max(self._FONT_SIZE_MIN, min(self._FONT_SIZE_MAX, self._font_size + delta))
        if new_size == self._font_size:
            return
        self._font_size = new_size
        self._log_font.setPointSize(self._font_size)
        self._list_view.setFont(self._log_font)
        self._list_view.viewport().setFont(self._log_font)
        self._list_view.reset()
        self.font_dec_btn.setEnabled(self._font_size > self._FONT_SIZE_MIN)
        self.font_inc_btn.setEnabled(self._font_size < self._FONT_SIZE_MAX)

    def clear(self) -> None:
        self._pending.clear()
        self._model.clear()
        self._search_highlights.clear()
        self._delegate.set_search_highlights({})
        self.line_badge.setText(i18n.tr("viewer_lines", n=0))

    def get_json_keys(self) -> set:
        return self._model.get_json_keys()

    def insert_break(self) -> None:
        self.flush_pending()
        self._model.insert_break()

    def focus_list(self) -> None:
        self._list_view.setFocus()

    def _show_context_menu(self, pos) -> None:
        index = self._list_view.indexAt(pos)
        if index.isValid() and index not in self._list_view.selectedIndexes():
            self._list_view.setCurrentIndex(index)

        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {C_CARD}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            f" border-radius: 6px; padding: 4px; }}"
            f"QMenu::item {{ padding: 4px 16px; border-radius: 4px; }}"
            f"QMenu::item:selected {{ background: {C_SEL_BG}; }}"
        )
        copy_action = menu.addAction(i18n.tr("action_copy"))
        copy_action.setEnabled(bool(self._list_view.selectedIndexes()))
        copy_action.triggered.connect(self.copy)
        menu.exec(self._list_view.mapToGlobal(pos))

    def copy(self) -> None:
        """Copy selected rows' text to clipboard."""
        indexes = self._list_view.selectedIndexes()
        if not indexes:
            return
        texts = []
        for idx in sorted(indexes, key=lambda i: i.row()):
            item = self._model.data(idx, _ITEM_ROLE)
            if item:
                texts.append(item.message)
        QApplication.clipboard().setText("\n".join(texts))
