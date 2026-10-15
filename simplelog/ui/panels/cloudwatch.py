"""Cloudwatch connection panel."""

from __future__ import annotations

from PyQt6.QtCore import (
    Qt,
    QTimer,
)
from PyQt6.QtGui import (
    QColor,
)
from PyQt6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from simplelog.core import i18n
from simplelog.sources import cloudwatch
from simplelog.ui.panels.base import ProviderPanel
from simplelog.ui.ui_theme import C_ACCENT, C_SIDE, C_TEXT
from simplelog.ui.ui_widgets import (
    MessageBox,
    NoScrollComboBox,
    OpenModeWidget,
    _field_label,
    _ghost_btn,
    _primary_btn,
    _ProfileBar,
    make_card,
)
from simplelog.ui.ui_workers import CallWorker


class CloudWatchPanel(ProviderPanel):
    profile_type = "cloudwatch"
    _profile_bar_attr = "_cw_profile_bar"

    def default_profile_name(self) -> str:
        return "My account"
    _REGIONS = [
        "us-east-1", "us-east-2", "us-west-1", "us-west-2",
        "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1",
        "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
        "ap-south-1", "ca-central-1", "sa-east-1",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._client = None
        self._all_groups: list[str] = []
        self._connecting = False
        self._region_chosen = False   # True: keep the region instead of the profile's
        self._restore: tuple[str, str] | None = None   # saved (group, stream) to re-select
        self._saved_target: tuple[str, str] = ("", "")
        self._groups_gen = 0      # bumped per request: older answers are ignored
        self._streams_gen = 0
        self._build_ui()
        _key = id(self)
        i18n.register(_key, self.retranslate)
        self.destroyed.connect(lambda _=None, k=_key: i18n.unregister(k))

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        content.setStyleSheet(f"background: {C_SIDE};")
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(12, 16, 12, 16)
        vbox.setSpacing(12)

        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-size: 15px; font-weight: 700;"
            "background: transparent; border: none; margin-bottom: 4px;"
        )
        vbox.addWidget(self._title_lbl)

        # ── Saved configs card ────────────────────────────────────────────────
        saved_card_cw, saved_lay_cw, _ = make_card(i18n.tr("saved_configs"))
        self._cw_profile_bar = _ProfileBar("cloudwatch", wrapper=saved_card_cw)
        self._cw_profile_bar.profile_loaded.connect(self._load_cw_profile)
        saved_lay_cw.addWidget(self._cw_profile_bar)
        vbox.addWidget(saved_card_cw)

        # ── Connection card ───────────────────────────────────────────────────
        card, cl, self._lbl_connection = make_card(i18n.tr("new_config"), help_key="help_cloudwatch")

        self._lbl_auth_mode = _field_label("")
        self._auth_mode_combo = NoScrollComboBox()
        self._auth_mode_combo.currentIndexChanged.connect(self._on_auth_mode_changed)
        cl.addWidget(self._lbl_auth_mode)
        cl.addWidget(self._auth_mode_combo)

        profiles = cloudwatch.list_profiles()
        self.profile_combo = NoScrollComboBox()
        self.profile_combo.addItem("(default)")
        self.profile_combo.addItems(list(profiles))
        self._lbl_profile = _field_label("")
        self._profile_widgets = [self._lbl_profile, self.profile_combo]
        cl.addWidget(self._lbl_profile)
        cl.addWidget(self.profile_combo)

        self.access_key_input = QLineEdit()
        self.secret_key_input = QLineEdit()
        self.secret_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._lbl_access_key = _field_label("")
        self._lbl_secret_key = _field_label("")
        self._key_widgets = [
            self._lbl_access_key, self.access_key_input,
            self._lbl_secret_key, self.secret_key_input,
        ]
        for w in self._key_widgets:
            cl.addWidget(w)
            w.setVisible(False)

        # Region section — hidden until credentials validated
        self._region_section = QWidget()
        rs_lay = QVBoxLayout(self._region_section)
        rs_lay.setContentsMargins(0, 0, 0, 0)
        rs_lay.setSpacing(4)
        self._lbl_region = _field_label("")
        self.region_combo = NoScrollComboBox()
        self.region_combo.addItems(self._REGIONS)
        self.region_combo.currentIndexChanged.connect(self._on_region_changed)
        rs_lay.addWidget(self._lbl_region)
        rs_lay.addWidget(self.region_combo)
        self._region_section.setVisible(False)
        cl.addWidget(self._region_section)

        self._save_profile_btn_cw = _ghost_btn(i18n.tr("profile_save_btn"))
        self._save_profile_btn_cw.clicked.connect(self._save_profile)
        self.connect_btn = _primary_btn()
        self.connect_btn.clicked.connect(self._on_connect)
        cl.addWidget(self._save_profile_btn_cw)
        cl.addWidget(self.connect_btn)
        vbox.addWidget(card)

        # ── Log groups card ───────────────────────────────────────────────────
        card2, gl, self._lbl_groups = make_card(i18n.tr("cw_card_groups"))
        self._card_groups = card2
        self.group_search = QLineEdit()
        self.group_search.textChanged.connect(self._filter_groups)
        self.group_list = QListWidget()
        self.group_list.setFixedHeight(180)
        self.group_list.currentTextChanged.connect(self._on_group_selected)
        gl.addWidget(self.group_search)
        gl.addWidget(self.group_list)
        card2.setVisible(False)
        vbox.addWidget(card2)

        # ── Log streams card ──────────────────────────────────────────────────
        card3, sl, self._lbl_streams = make_card(i18n.tr("cw_card_streams"))
        self._card_streams = card3
        self.stream_list = QListWidget()
        self.stream_list.setFixedHeight(180)
        sl.addWidget(self.stream_list)
        card3.setVisible(False)
        vbox.addWidget(card3)

        # ── Options card ──────────────────────────────────────────────────────
        card4, ol, self._lbl_options = make_card(i18n.tr("cw_card_options"))
        self._card_options = card4

        self.lookback_combo = NoScrollComboBox()
        for label, secs in [
            ("15 min", 900), ("1 hour", 3600), ("6 hours", 21600),
            ("24 hours", 86400), ("3 days", 259200), ("7 days", 604800),
        ]:
            self.lookback_combo.addItem(label, secs)
        self.lookback_combo.setCurrentIndex(1)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(3)
        self.interval_spin.setSuffix(" s")

        self.filter_input = QLineEdit()
        self._open_mode_w = OpenModeWidget()
        self._get_open_mode = self._open_mode_w.get_mode
        self.open_btn = _primary_btn()
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._on_open_clicked)

        self._lbl_lookback = _field_label("")
        self._lbl_poll     = _field_label("")
        self._lbl_filter   = _field_label("")
        ol.addWidget(self._lbl_lookback)
        ol.addWidget(self.lookback_combo)
        ol.addWidget(self._lbl_poll)
        ol.addWidget(self.interval_spin)
        ol.addWidget(self._lbl_filter)
        ol.addWidget(self.filter_input)
        ol.addWidget(self._open_mode_w)
        ol.addWidget(self.open_btn)
        card4.setVisible(False)
        vbox.addWidget(card4)

        vbox.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self.retranslate()

    def retranslate(self) -> None:
        self._title_lbl.setText(i18n.tr("cw_title"))
        if self._lbl_connection:
            self._lbl_connection.setText(i18n.tr("cw_card_connection").upper())
        if self._lbl_groups:
            self._lbl_groups.setText(i18n.tr("cw_card_groups").upper())
        if self._lbl_streams:
            self._lbl_streams.setText(i18n.tr("cw_card_streams").upper())
        if self._lbl_options:
            self._lbl_options.setText(i18n.tr("cw_card_options").upper())
        self._lbl_auth_mode.setText(i18n.tr("cw_auth_mode"))
        current_idx = self._auth_mode_combo.currentIndex()
        self._auth_mode_combo.blockSignals(True)
        self._auth_mode_combo.clear()
        self._auth_mode_combo.addItem(i18n.tr("cw_auth_profile"))
        self._auth_mode_combo.addItem(i18n.tr("cw_auth_keys"))
        self._auth_mode_combo.setCurrentIndex(max(0, current_idx))
        self._auth_mode_combo.blockSignals(False)
        self._lbl_profile.setText(i18n.tr("cw_field_profile"))
        self._lbl_access_key.setText(i18n.tr("cw_field_access_key"))
        self._lbl_secret_key.setText(i18n.tr("cw_field_secret_key"))
        self._lbl_region.setText(i18n.tr("cw_field_region"))
        self._lbl_lookback.setText(i18n.tr("cw_field_lookback"))
        self._lbl_poll.setText(i18n.tr("cw_field_poll"))
        self._lbl_filter.setText(i18n.tr("cw_field_filter"))
        self.group_search.setPlaceholderText(i18n.tr("cw_search_groups"))
        self.filter_input.setPlaceholderText(i18n.tr("cw_filter_ph"))
        self.open_btn.setText(i18n.tr("cw_open"))
        # connect_btn: derive label from connection state, not from current text
        if not getattr(self, "_connecting", False):
            self.connect_btn.setText(
                i18n.tr("cw_refresh") if self._client else i18n.tr("cw_connect")
            )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _load_cw_profile(self, p: dict) -> None:
        if p.get("access_key_id"):
            self._auth_mode_combo.setCurrentIndex(1)
            self.access_key_input.setText(p.get("access_key_id", ""))
            self.secret_key_input.setText(p.get("secret_key", ""))
        else:
            self._auth_mode_combo.setCurrentIndex(0)
            idx = self.profile_combo.findText(p.get("aws_profile", "(default)"))
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
        region_idx = self.region_combo.findText(p.get("region", ""))
        self._region_chosen = region_idx >= 0   # a saved region wins over the profile's
        if region_idx >= 0:
            self.region_combo.setCurrentIndex(region_idx)
        lookback_idx = self.lookback_combo.findData(p.get("lookback"))
        if lookback_idx >= 0:
            self.lookback_combo.setCurrentIndex(lookback_idx)
        if p.get("interval"):
            self.interval_spin.setValue(p["interval"])
        self.filter_input.setText(p.get("filter", ""))

    def _restore_saved_target(self, group: str, stream: str) -> None:
        """Connect, then re-select the saved log group / stream once they are listed."""
        self._restore = (group, stream) if group else None
        self._on_connect()

    def _apply_restore_group(self) -> None:
        if not self._restore:
            return
        items = self.group_list.findItems(self._restore[0], Qt.MatchFlag.MatchExactly)
        if items:
            self.group_list.setCurrentItem(items[0])   # loads the streams
        else:
            self._restore = None

    def _apply_restore_stream(self, group: str) -> None:
        if not self._restore or self._restore[0] != group:
            return
        stream = self._restore[1]
        self._restore = None
        if stream:
            streams = self.stream_list.findItems(stream, Qt.MatchFlag.MatchExactly)
            if streams:
                self.stream_list.setCurrentItem(streams[0])

    def _on_auth_mode_changed(self, index: int):
        use_keys = index == 1
        for w in self._profile_widgets:
            w.setVisible(not use_keys)
        for w in self._key_widgets:
            w.setVisible(use_keys)

    def _on_connect(self):
        if self._connecting:
            return
        self._connecting = True
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText(i18n.tr("cw_connecting"))
        self._apply_profile_region()
        try:
            self._make_client(self.region_combo.currentText())
        except Exception as exc:
            self._on_connect_failed(str(exc))
            return
        self._region_section.setVisible(True)
        self._load_groups(first=True)

    def _apply_profile_region(self) -> None:
        """Pre-select the region configured for the chosen AWS profile."""
        if self._region_chosen or self._auth_mode_combo.currentIndex() == 1:
            return
        profile = self.profile_combo.currentText()
        region = cloudwatch.profile_region(None if profile == "(default)" else profile)
        if not region:
            return
        if self.region_combo.findText(region) < 0:
            self.region_combo.addItem(region)
        self.region_combo.blockSignals(True)
        self.region_combo.setCurrentText(region)
        self.region_combo.blockSignals(False)

    def _on_connect_failed(self, msg: str) -> None:
        self._client = None
        self._restore = None
        self._region_section.setVisible(False)
        self._card_groups.setVisible(False)
        MessageBox.critical(self, i18n.tr("err_connection"), msg)
        self.connect_btn.setText(i18n.tr("cw_connect"))
        self._connecting = False
        self.connect_btn.setEnabled(True)

    def _make_client(self, region: str) -> None:
        if self._auth_mode_combo.currentIndex() == 1:
            ak = self.access_key_input.text().strip()
            sk = self.secret_key_input.text().strip()
            self._client = cloudwatch.make_client(
                region=region,
                access_key_id=ak,
                secret_access_key=sk,
            )
        else:
            profile = self.profile_combo.currentText()
            self._client = cloudwatch.make_client(
                None if profile == "(default)" else profile, region
            )

    def _load_groups(self, first: bool = False) -> None:
        """List the log groups in the background (can be many pages of results)."""
        region = self.region_combo.currentText()
        try:
            self._make_client(region)
        except Exception as exc:
            if first:
                self._on_connect_failed(str(exc))
            else:
                MessageBox.critical(self, i18n.tr("err_connection"), str(exc))
            return
        self._groups_gen += 1
        gen = self._groups_gen
        worker = CallWorker(cloudwatch.list_log_groups, self._client)
        worker.success.connect(lambda groups: self._on_groups_loaded(gen, groups, first))
        worker.failure.connect(lambda msg: self._on_groups_failed(gen, msg, first))
        self._groups_worker = worker
        worker.start()

    def _on_groups_loaded(self, gen: int, groups: list, first: bool) -> None:
        if gen != self._groups_gen:
            return   # the region changed meanwhile: a newer request is on its way
        self._all_groups = groups
        self._populate_groups(groups)
        self._card_groups.setVisible(True)
        if first:
            self.connect_btn.setText(i18n.tr("cw_refresh"))
            self._connecting = False
            self.connect_btn.setEnabled(True)
        self._apply_restore_group()

    def _on_groups_failed(self, gen: int, msg: str, first: bool) -> None:
        if gen != self._groups_gen:
            return
        if first:
            self._on_connect_failed(msg)
        else:
            MessageBox.critical(self, i18n.tr("err_connection"), msg)

    def _on_region_changed(self) -> None:
        self._region_chosen = True   # picked by the user
        if self._client:
            self._load_groups()

    def _populate_groups(self, groups: list[str]):
        self.group_list.clear()
        for g in groups:
            self.group_list.addItem(g)

    def _filter_groups(self, text: str):
        lo = text.lower()
        self._populate_groups([g for g in self._all_groups if lo in g.lower()])

    def _on_group_selected(self, group: str):
        if not group or not self._client:
            return
        self.stream_list.clear()
        self._streams_gen += 1
        gen = self._streams_gen
        worker = CallWorker(cloudwatch.list_log_streams, self._client, group)
        worker.success.connect(lambda streams: self._on_streams_loaded(gen, group, streams))
        worker.failure.connect(lambda msg: self._on_streams_failed(gen, msg))
        self._streams_worker = worker
        worker.start()

    def _show_stream_cards(self) -> None:
        self._card_streams.setVisible(True)
        self._card_options.setVisible(True)
        self.open_btn.setEnabled(True)

    def _on_streams_loaded(self, gen: int, group: str, streams: list) -> None:
        if gen != self._streams_gen:
            return   # another group was selected meanwhile
        all_item = QListWidgetItem("— All streams —")
        all_item.setForeground(QColor(C_ACCENT))
        self.stream_list.addItem(all_item)
        for s in streams:
            self.stream_list.addItem(s)
        self.stream_list.setCurrentRow(0)
        self._show_stream_cards()
        self._apply_restore_stream(group)

    def _on_streams_failed(self, gen: int, msg: str) -> None:
        if gen != self._streams_gen:
            return
        MessageBox.warning(self, i18n.tr("err_streams"), msg)
        self._show_stream_cards()

    def _on_open_clicked(self):
        group_item  = self.group_list.currentItem()
        stream_item = self.stream_list.currentItem()
        if not self._client or not group_item:
            return
        stream_name = ""
        if stream_item and stream_item.text() != "— All streams —":
            stream_name = stream_item.text()
        self.open_tab.emit({
            "type":      "cloudwatch",
            "client":    self._client,
            "group":     group_item.text(),
            "stream":    stream_name,
            "filter":    self.filter_input.text(),
            "interval":  self.interval_spin.value(),
            "lookback":  self.lookback_combo.currentData(),
            "auth_mode": self._auth_mode_combo.currentIndex(),
            "profile":   self.profile_combo.currentText(),
            "region":    self.region_combo.currentText(),
        }, self._get_open_mode())

    # ── Embedding contract (see ProviderPanel) ────────────────────────────────

    def load_profile(self, data: dict) -> None:
        self._load_cw_profile(data)
        self._saved_target = (data.get("group", ""), data.get("stream", ""))

    def connect_now(self) -> None:
        # Once the dialog is shown: connect, then re-select the saved group / stream
        group, stream = self._saved_target
        QTimer.singleShot(0, lambda: self._restore_saved_target(group, stream))

    def profile_extra(self, cfg: dict) -> dict:
        return {key: cfg[key] for key in ("group", "stream", "filter", "interval", "lookback")}

    def can_open(self) -> bool:
        return self.open_btn.isEnabled()

    def open_selected(self) -> None:
        self._on_open_clicked()

    def profile_data(self) -> dict:
        """Region + credentials (the selected group / stream travel with the opened tab)."""
        data: dict = {"region": self.region_combo.currentText()}
        if self._auth_mode_combo.currentIndex() == 1:
            data["access_key_id"] = self.access_key_input.text().strip()
            data["secret_key"] = self.secret_key_input.text().strip()
        else:
            data["aws_profile"] = self.profile_combo.currentText()
        return data

    def _embedded_hidden(self) -> list:
        return [self._title_lbl, self._save_profile_btn_cw, self.open_btn]
