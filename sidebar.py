"""Filter / search sidebar."""

from __future__ import annotations

from PyQt6.QtCore import (
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QKeySequence,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import i18n
from log_model import TermRow
from log_view import LogViewer
from ui_theme import (
    C_ACCENT,
    C_ACCENT_HOVER,
    C_BG,
    C_BORDER,
    C_BORDER2,
    C_DEBUG,
    C_ERR,
    C_HOVER,
    C_MUTED,
    C_ON_ACCENT,
    C_PANEL,
    C_TEXT,
    C_TRACE,
    C_TS,
    _svg_icon,
    rgba,
)

_KEY_PREV = "Shift+F3"
_KEY_NEXT = "F3"

# ── Sidebar helper: one term input row ────────────────────────────────────────

class _TermRowWidget(QWidget):
    """A single filter/search term row: [op toggle] [input(s)] [×]."""

    changed          = pyqtSignal()
    remove_requested = pyqtSignal()

    def __init__(self, operator: str = "", mode: str = "text", parent=None):
        super().__init__(parent)
        self._operator = operator
        self._mode = mode  # "text" | "kv"

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        # Operator toggle (AND ↔ OR), hidden for first row
        self._op_btn = QPushButton()
        self._op_btn.setFixedSize(36, 20)
        self._op_btn.setVisible(bool(operator))
        self._op_btn.setStyleSheet(
            f"QPushButton {{ background: {rgba(C_TS, 33)}; color: {C_TS}; "
            f"border-radius: 3px; font-size: 9px; font-weight: bold; border: none; padding: 0; }}"
            f"QPushButton:hover {{ background: {rgba(C_TS, 66)}; }}"
        )
        self._op_btn.clicked.connect(self._toggle_operator)
        row.addWidget(self._op_btn)
        self.retranslate_op()

        _input_style = (
            f"background: transparent; color: {C_TEXT}; border: none; "
            "padding: 0 4px; font-size: 11px;"
        )

        if mode == "kv":
            self._key_input = QLineEdit()
            self._key_input.setFixedWidth(60)
            self._key_input.setStyleSheet(
                f"background: transparent; color: {C_TRACE}; border: none; "
                "padding: 0 4px; font-size: 11px;"
            )
            self._key_input.textChanged.connect(self.changed)
            row.addWidget(self._key_input)

            eq_lbl = QLabel("=")
            eq_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 11px; background: transparent;")
            eq_lbl.setFixedWidth(10)
            row.addWidget(eq_lbl)

            self._val_input = QLineEdit()
            self._val_input.setStyleSheet(_input_style)
            self._val_input.textChanged.connect(self.changed)
            row.addWidget(self._val_input, stretch=1)

            # Alias for common API (set_placeholder, focus_input target val)
            self._input = self._val_input
        else:
            self._input = QLineEdit()
            self._input.setStyleSheet(_input_style)
            self._input.textChanged.connect(self.changed)
            row.addWidget(self._input, stretch=1)

        # Remove button
        self._rm_btn = QPushButton("×")
        self._rm_btn.setFixedSize(20, 20)
        self._rm_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_MUTED}; "
            "border: none; font-size: 14px; padding: 0; }"
            f"QPushButton:hover {{ color: {C_ERR}; }}"
        )
        self._rm_btn.clicked.connect(self.remove_requested)
        row.addWidget(self._rm_btn)

    def _toggle_operator(self) -> None:
        self._operator = "OR" if self._operator == "AND" else "AND"
        self.retranslate_op()
        self.changed.emit()

    def retranslate_op(self) -> None:
        """Show the AND / OR toggle in the current language (the stored value stays AND / OR)."""
        key = "sidebar_op_or" if self._operator == "OR" else "sidebar_op_and"
        self._op_btn.setText(i18n.tr(key))

    def to_term_row(self) -> TermRow:
        if self._mode == "kv":
            return TermRow(
                text=self._val_input.text(),
                operator=self._operator,
                key=self._key_input.text(),
            )
        return TermRow(text=self._input.text(), operator=self._operator)

    def set_placeholder(self, text: str) -> None:
        self._input.setPlaceholderText(text)

    def clear(self) -> None:
        """Empty the row's inputs (what × does on the only remaining row)."""
        if self._mode == "kv":
            self._key_input.clear()
        self._input.clear()

    def focus_input(self) -> None:
        self._input.setFocus()

    def set_text(self, text: str) -> None:
        """In kv mode, sets the key field. In text mode, sets the single input."""
        if self._mode == "kv":
            self._key_input.setText(text)
        else:
            self._input.setText(text)


# ── Right sidebar: filter + search + JSON keys ─────────────────────────────────

class FilterSearchSidebar(QWidget):
    """Global right sidebar. Call set_active_viewer() when the active tab changes."""

    # SVG templates for the 3 tab icons
    _TAB_SVGS = [
        # Search (magnifier)
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">'
        '<circle cx="6.5" cy="6.5" r="4" stroke="{color}" stroke-width="1.5"/>'
        '<path d="M10 10L14 14" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>'
        '</svg>',
        # Filter (3 horizontal lines, decreasing)
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">'
        '<path d="M2 4h12M4 8h8M6 12h4" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>'
        '</svg>',
        # JSON Keys (curly braces)
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none">'
        '<path d="M5 2C3.5 2 3 2.8 3 4v2c0 .7-.5 1.2-1 1.5.5.3 1 .8 1 1.5v2c0 1.2.5 2 2 2'
        'M11 2c1.5 0 2 .8 2 2v2c0 .7.5 1.2 1 1.5-.5.3-1 .8-1 1.5v2c0 1.2-.5 2-2 2"'
        ' stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>'
        '</svg>',
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(180)
        self.setMaximumWidth(520)
        self.setStyleSheet(
            f"FilterSearchSidebar {{ background: {C_PANEL}; "
            f"border-left: 1px solid {C_BORDER}; }}"
        )

        self._active_viewer: LogViewer | None = None
        self._search_matches: list[tuple[int, int, int]] = []
        self._search_match_index: int = -1
        self._search_term_widgets: list[_TermRowWidget] = []
        self._filter_term_widgets: list[_TermRowWidget] = []

        # Debounce timers
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(150)
        self._filter_timer.timeout.connect(self._apply_filter_now)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._apply_search_now)

        self._lines_timer = QTimer(self)
        self._lines_timer.setSingleShot(True)
        self._lines_timer.setInterval(300)
        self._lines_timer.timeout.connect(self._refresh_search_keep_position)

        self._build_ui()

        _key = id(self)
        i18n.register(_key, self.retranslate)
        self.destroyed.connect(lambda _=None, k=_key: i18n.unregister(k))

    # ── UI construction ───────────────────────────────────────────────────────

    def _set_tab(self, idx: int) -> None:
        self._content_stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._tab_btns):
            active = i == idx
            btn.setIcon(_svg_icon(self._TAB_SVGS[i], C_ACCENT if active else C_MUTED, 16))
            if active:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {C_BG}; border: none; "
                    f"border-bottom: 2px solid {C_ACCENT}; border-radius: 0; "
                    f"padding: 0; }}"
                    f"QPushButton:hover {{ background: {C_BG}; }}"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background: transparent; border: none; "
                    "border-radius: 0; padding: 0; }"
                    f"QPushButton:hover {{ background: {C_HOVER}; }}"
                )

    def retheme(self) -> None:
        """Re-colour the tab icons after a theme switch."""
        self._set_tab(self._content_stack.currentIndex())

    def _and_btn_style(self) -> str:
        return (
            f"QPushButton {{ background: {C_ACCENT}; color: {C_ON_ACCENT}; border: none; "
            f"border-radius: 5px; font-size: 11px; font-weight: 700; padding: 4px 10px; }}"
            f"QPushButton:hover {{ background: {C_ACCENT_HOVER}; }}"
        )

    def _or_btn_style(self) -> str:
        return (
            f"QPushButton {{ background: {rgba(C_TRACE, 38)}; color: {C_TRACE}; "
            f"border: 1px solid {rgba(C_TRACE, 77)}; border-radius: 5px; "
            f"font-size: 11px; font-weight: 700; padding: 4px 10px; }}"
            f"QPushButton:hover {{ background: {rgba(C_TRACE, 77)}; }}"
        )

    def _nav_btn_style(self) -> str:
        return (
            f"QPushButton {{ background: transparent; color: {C_MUTED}; "
            f"border: 1px solid {C_BORDER}; border-radius: 5px;"
            f"font-size: 11px; padding: 3px 10px; }}"
            f"QPushButton:hover {{ color: {C_TEXT}; border-color: {C_BORDER2}; }}"
        )

    def _term_block_style(self) -> str:
        return (
            f"background: {C_BG}; border: 1px solid {C_BORDER}; border-radius: 5px;"
        )

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Icon tab strip ────────────────────────────────────────────────────
        tab_bar = QWidget()
        tab_bar.setFixedHeight(40)
        tab_bar.setStyleSheet(
            f"QWidget {{ background: {C_PANEL}; border-bottom: 1px solid {C_BORDER}; }}"
        )
        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(6, 6, 6, 0)
        tab_layout.setSpacing(0)

        self._tab_btns: list[QPushButton] = []
        for i in range(3):
            btn = QPushButton()
            btn.setFixedHeight(32)
            btn.setIconSize(QSize(16, 16))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, idx=i: self._set_tab(idx))
            self._tab_btns.append(btn)
            tab_layout.addWidget(btn, 1)

        outer.addWidget(tab_bar)

        # ── Stacked content pages ─────────────────────────────────────────────
        self._content_stack = QStackedWidget()
        self._content_stack.setStyleSheet(
            f"QStackedWidget {{ background: {C_PANEL}; border: none; }}"
        )

        for build_fn in (
            self._build_search_content,
            self._build_filter_content,
            self._build_json_content,
        ):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet(
                f"QScrollArea {{ border: none; background: {C_PANEL}; }}"
            )
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            page = QWidget()
            page.setStyleSheet(f"QWidget {{ background: {C_PANEL}; }}")
            build_fn(page)
            if page.layout():
                page.layout().addStretch()
            scroll.setWidget(page)
            self._content_stack.addWidget(scroll)

        outer.addWidget(self._content_stack, 1)

        # Ctrl+F: focus search tab
        sc = QShortcut(QKeySequence("Ctrl+F"), self)
        sc.setContext(Qt.ShortcutContext.WindowShortcut)
        sc.activated.connect(self._focus_first_search)

        # Previous / next match, the usual F3 pair
        for key, handler in ((_KEY_PREV, self._search_prev), (_KEY_NEXT, self._search_next_match)):
            nav_sc = QShortcut(QKeySequence(key), self)
            nav_sc.setContext(Qt.ShortcutContext.WindowShortcut)
            nav_sc.activated.connect(handler)

        self._set_tab(0)
        self.retranslate()

    def _build_search_content(self, parent: QWidget) -> None:
        vbox = QVBoxLayout(parent)
        vbox.setContentsMargins(10, 8, 10, 8)
        vbox.setSpacing(4)

        # Term rows block
        self._search_block = QWidget()
        self._search_block.setStyleSheet(self._term_block_style())
        self._search_rows_layout = QVBoxLayout(self._search_block)
        self._search_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._search_rows_layout.setSpacing(0)
        vbox.addWidget(self._search_block)
        self._add_search_row("")   # initial empty row

        # Add AND/OR buttons
        add_row = QHBoxLayout()
        add_row.setSpacing(4)
        add_row.setContentsMargins(0, 0, 0, 0)
        self._btn_add_search_and = QPushButton()
        self._btn_add_search_and.clicked.connect(lambda: self._add_search_row("AND"))
        self._btn_add_search_and.setFixedHeight(24)
        self._btn_add_search_and.setStyleSheet(self._and_btn_style())
        self._btn_add_search_or = QPushButton()
        self._btn_add_search_or.clicked.connect(lambda: self._add_search_row("OR"))
        self._btn_add_search_or.setFixedHeight(24)
        self._btn_add_search_or.setStyleSheet(self._or_btn_style())
        add_row.addWidget(self._btn_add_search_and)
        add_row.addWidget(self._btn_add_search_or)
        add_row.addStretch()
        vbox.addLayout(add_row)

        # Prev / Next / hits inline
        nav_row = QHBoxLayout()
        nav_row.setSpacing(4)
        nav_row.setContentsMargins(0, 2, 0, 0)
        self._btn_prev = QPushButton()
        self._btn_next = QPushButton()
        self._lbl_hits = QLabel()
        self._lbl_hits.setStyleSheet(f"color: {C_MUTED}; font-size: 10px;")
        for btn in (self._btn_prev, self._btn_next):
            btn.setFixedHeight(22)
            btn.setStyleSheet(self._nav_btn_style())
        self._btn_prev.clicked.connect(self._search_prev)
        self._btn_next.clicked.connect(self._search_next_match)
        nav_row.addWidget(self._btn_prev)
        nav_row.addWidget(self._btn_next)
        nav_row.addStretch()
        vbox.addLayout(nav_row)
        # On its own line: next to the buttons, a longer translation made the panel overflow
        self._lbl_hits.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        vbox.addWidget(self._lbl_hits)

    def _build_filter_content(self, parent: QWidget) -> None:
        vbox = QVBoxLayout(parent)
        vbox.setContentsMargins(10, 8, 10, 8)
        vbox.setSpacing(4)

        self._filter_block = QWidget()
        self._filter_block.setStyleSheet(self._term_block_style())
        self._filter_rows_layout = QVBoxLayout(self._filter_block)
        self._filter_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._filter_rows_layout.setSpacing(0)
        vbox.addWidget(self._filter_block)
        self._add_filter_row("")   # initial empty row

        add_row = QHBoxLayout()
        add_row.setSpacing(4)
        add_row.setContentsMargins(0, 0, 0, 0)
        self._btn_add_filter_and = QPushButton()
        self._btn_add_filter_and.clicked.connect(lambda: self._add_filter_row("AND"))
        self._btn_add_filter_and.setFixedHeight(24)
        self._btn_add_filter_and.setStyleSheet(self._and_btn_style())
        self._btn_add_filter_or = QPushButton()
        self._btn_add_filter_or.clicked.connect(lambda: self._add_filter_row("OR"))
        self._btn_add_filter_or.setFixedHeight(24)
        self._btn_add_filter_or.setStyleSheet(self._or_btn_style())
        self._btn_add_filter_kv = QPushButton()
        self._btn_add_filter_kv.clicked.connect(lambda: self._add_filter_row("AND", mode="kv"))
        self._btn_add_filter_kv.setFixedHeight(24)
        self._btn_add_filter_kv.setStyleSheet(self._nav_btn_style())
        add_row.addWidget(self._btn_add_filter_and)
        add_row.addWidget(self._btn_add_filter_or)
        add_row.addStretch()
        vbox.addLayout(add_row)

        # Own row: with the two buttons above it did not fit once translated (e.g. German)
        kv_row = QHBoxLayout()
        kv_row.setContentsMargins(0, 0, 0, 0)
        kv_row.addWidget(self._btn_add_filter_kv)
        kv_row.addStretch()
        vbox.addLayout(kv_row)

        live_row = QHBoxLayout()
        live_row.setContentsMargins(0, 2, 0, 0)
        self._cb_live = QCheckBox()
        self._cb_live.setChecked(True)
        self._cb_live.setStyleSheet(f"color: {C_MUTED}; font-size: 10px;")
        self._cb_live.stateChanged.connect(lambda _: self._filter_timer.start())
        live_row.addWidget(self._cb_live)
        live_row.addStretch()
        vbox.addLayout(live_row)

    def _build_json_content(self, parent: QWidget) -> None:
        vbox = QVBoxLayout(parent)
        vbox.setContentsMargins(10, 8, 10, 10)
        vbox.setSpacing(4)

        self._json_container = QWidget()
        self._json_container.setStyleSheet("background: transparent;")
        self._json_layout = QVBoxLayout(self._json_container)
        self._json_layout.setContentsMargins(0, 0, 0, 0)
        self._json_layout.setSpacing(4)
        self._lbl_json_ph = QLabel()
        self._lbl_json_ph.setStyleSheet(f"color: {C_MUTED}; font-size: 10px;")
        self._json_layout.addWidget(self._lbl_json_ph)
        vbox.addWidget(self._json_container)

    # ── Term row management ───────────────────────────────────────────────────

    def _add_search_row(self, operator: str) -> None:
        if self._search_term_widgets:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f"color: {C_BORDER}; max-height: 1px;")
            self._search_rows_layout.addWidget(sep)
        row = _TermRowWidget(operator, parent=self)
        row.setContentsMargins(8, 4, 4, 4)
        row.changed.connect(self._on_search_changed)
        row.remove_requested.connect(lambda r=row: self._remove_search_row(r))
        self._search_term_widgets.append(row)
        self._search_rows_layout.addWidget(row)
        row.set_placeholder(i18n.tr("sidebar_term_ph"))

    def _rebuild_row_block(
        self,
        layout: QVBoxLayout,
        widgets: list,
    ) -> None:
        """Clear layout and re-insert all term rows with separators between them."""
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w and w not in widgets:
                w.deleteLater()
        for i, w in enumerate(widgets):
            if i > 0:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet(f"color: {C_BORDER}; max-height: 1px;")
                layout.addWidget(sep)
            layout.addWidget(w)

    def _remove_search_row(self, row: _TermRowWidget) -> None:
        if len(self._search_term_widgets) == 1:
            row.clear()   # always keep at least one row: × just empties it
            return
        self._search_term_widgets.remove(row)
        self._search_rows_layout.removeWidget(row)
        row.deleteLater()
        self._rebuild_row_block(self._search_rows_layout, self._search_term_widgets)
        self._on_search_changed()

    def _add_filter_row(self, operator: str, mode: str = "text", prefill_key: str = "") -> None:
        if self._filter_term_widgets:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f"color: {C_BORDER}; max-height: 1px;")
            self._filter_rows_layout.addWidget(sep)
        row = _TermRowWidget(operator, mode=mode, parent=self)
        row.setContentsMargins(8, 4, 4, 4)
        row.changed.connect(self._on_filter_changed)
        row.remove_requested.connect(lambda r=row: self._remove_filter_row(r))
        self._filter_term_widgets.append(row)
        self._filter_rows_layout.addWidget(row)
        row.set_placeholder(i18n.tr("sidebar_term_ph"))
        if prefill_key:
            row.set_text(prefill_key)

    def _remove_filter_row(self, row: _TermRowWidget) -> None:
        if len(self._filter_term_widgets) == 1:
            row.clear()
            return
        self._filter_term_widgets.remove(row)
        self._filter_rows_layout.removeWidget(row)
        row.deleteLater()
        self._rebuild_row_block(self._filter_rows_layout, self._filter_term_widgets)
        self._on_filter_changed()

    # ── Signal handlers ───────────────────────────────────────────────────────

    def _on_search_changed(self) -> None:
        self._search_timer.start()

    def _on_filter_changed(self) -> None:
        if self._cb_live.isChecked():
            self._filter_timer.start()

    def _on_json_keys_updated(self, keys: set) -> None:
        self._rebuild_json_chips(keys)

    def _on_lines_appended(self) -> None:
        self._lines_timer.start()   # debounced search re-scan

    # ── Active viewer management ──────────────────────────────────────────────

    def set_active_viewer(self, viewer: LogViewer | None) -> None:
        if self._active_viewer is not None:
            self._active_viewer.json_keys_updated.disconnect(self._on_json_keys_updated)
            self._active_viewer.lines_appended.disconnect(self._on_lines_appended)
            self._active_viewer.filter_applied.disconnect(self._refresh_search)
        self._active_viewer = viewer
        if viewer is not None:
            viewer.json_keys_updated.connect(self._on_json_keys_updated)
            viewer.lines_appended.connect(self._on_lines_appended)
            viewer.filter_applied.connect(self._refresh_search)
            self._on_json_keys_updated(viewer.get_json_keys())
            viewer.apply_filter(self._current_filter_terms())
            # _refresh_search is triggered by filter_applied signal

    def _current_filter_terms(self) -> list[TermRow]:
        return [w.to_term_row() for w in self._filter_term_widgets]

    def _current_search_terms(self) -> list[TermRow]:
        return [w.to_term_row() for w in self._search_term_widgets]

    # ── Apply filter / search ─────────────────────────────────────────────────

    def _apply_filter_now(self) -> None:
        if self._active_viewer:
            self._active_viewer.apply_filter(self._current_filter_terms())

    def _apply_search_now(self) -> None:
        self._refresh_search()

    def _refresh_search(self) -> None:
        if self._active_viewer is None:
            self._search_matches = []
            self._search_match_index = -1
            self._update_hits_label()
            return
        terms = self._current_search_terms()
        self._search_matches = self._active_viewer.apply_search(terms)
        self._search_match_index = 0 if self._search_matches else -1
        self._update_hits_label()
        if self._search_matches:
            self._scroll_to_match(0)

    def _refresh_search_keep_position(self) -> None:
        """Re-scan after new lines arrived without yanking the view to the first match."""
        if self._active_viewer is None:
            return
        previous = self._search_match_index
        self._search_matches = self._active_viewer.apply_search(self._current_search_terms())
        if self._search_matches:
            self._search_match_index = min(max(previous, 0), len(self._search_matches) - 1)
            vis_idx, char_start, char_len = self._search_matches[self._search_match_index]
            self._active_viewer.scroll_to_search_match(vis_idx, char_start, char_len, scroll=False)
        else:
            self._search_match_index = -1
        self._update_hits_label()

    def _search_prev(self) -> None:
        if not self._search_matches:
            return
        self._search_match_index = (self._search_match_index - 1) % len(self._search_matches)
        self._scroll_to_match(self._search_match_index)
        self._update_hits_label()

    def _search_next_match(self) -> None:
        if not self._search_matches:
            return
        self._search_match_index = (self._search_match_index + 1) % len(self._search_matches)
        self._scroll_to_match(self._search_match_index)
        self._update_hits_label()

    def _scroll_to_match(self, index: int) -> None:
        if self._active_viewer is None or not self._search_matches:
            return
        vis_idx, char_start, char_len = self._search_matches[index]
        self._active_viewer.scroll_to_search_match(vis_idx, char_start, char_len)

    def _update_hits_label(self) -> None:
        n = len(self._search_matches)
        if n == 0:
            self._lbl_hits.setText(i18n.tr("sidebar_no_hits"))
        else:
            self._lbl_hits.setText(i18n.tr("sidebar_hits", n=n))

    # ── JSON chips ────────────────────────────────────────────────────────────

    def _rebuild_json_chips(self, keys: set) -> None:
        # Clear existing chips, but do NOT delete the placeholder label widget
        while self._json_layout.count():
            item = self._json_layout.takeAt(0)
            w = item.widget()
            if w and w is not self._lbl_json_ph:
                w.deleteLater()

        sorted_keys = sorted(keys)[:50]  # cap at 50
        if not sorted_keys:
            self._json_layout.addWidget(self._lbl_json_ph)
            return

        for key in sorted_keys:
            btn = QPushButton(key)
            btn.setFixedHeight(22)
            btn.setStyleSheet(
                f"QPushButton {{ background: {C_BG}; color: {C_DEBUG}; "
                f"border: 1px solid {C_BORDER}; border-radius: 5px; font-size: 11px; "
                f"font-family: 'JetBrains Mono', monospace; "
                f"padding: 2px 8px; text-align: left; }}"
                f"QPushButton:hover {{ border-color: {C_ACCENT}; }}"
            )
            btn.clicked.connect(lambda checked=False, k=key: self._add_filter_from_key(k))
            self._json_layout.addWidget(btn)

    def _add_filter_from_key(self, key: str) -> None:
        self._set_tab(1)  # switch to Filter tab
        self._add_filter_row("AND", mode="kv", prefill_key=key)
        self._filter_term_widgets[-1].focus_input()
        if self._cb_live.isChecked():
            self._filter_timer.start()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _focus_first_search(self) -> None:
        self._set_tab(0)
        if self._search_term_widgets:
            self._search_term_widgets[0].focus_input()
        self.show()

    def retranslate(self) -> None:
        self._btn_add_search_and.setText(i18n.tr("sidebar_add_and"))
        self._btn_add_search_or.setText(i18n.tr("sidebar_add_or"))
        self._btn_prev.setText(i18n.tr("sidebar_prev"))
        self._btn_next.setText(i18n.tr("sidebar_next"))
        self._btn_prev.setToolTip(f"{i18n.tr('tip_search_prev')}  ({_KEY_PREV})")
        self._btn_next.setToolTip(f"{i18n.tr('tip_search_next')}  ({_KEY_NEXT})")
        self._btn_add_filter_and.setText(i18n.tr("sidebar_add_and"))
        self._btn_add_filter_or.setText(i18n.tr("sidebar_add_or"))
        self._btn_add_filter_kv.setText(i18n.tr("sidebar_add_kv"))
        self._cb_live.setText(i18n.tr("sidebar_live_filter"))
        self._lbl_json_ph.setText(i18n.tr("sidebar_json_ph"))
        for w in self._search_term_widgets + self._filter_term_widgets:
            w.set_placeholder(i18n.tr("sidebar_term_ph"))
            w.retranslate_op()
        self._update_hits_label()
