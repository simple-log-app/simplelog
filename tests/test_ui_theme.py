"""Theme tokens: both palettes are complete, the preference round-trips."""
from __future__ import annotations

import os

import pytest
from PyQt6.QtWidgets import QApplication

import ui_theme


@pytest.fixture(autouse=True)
def _restore_theme(tmp_path, monkeypatch):
    monkeypatch.setattr(ui_theme, "_PREFS_PATH", tmp_path / "prefs.json")
    ui_theme._theme = "dark"
    yield
    ui_theme._theme = "dark"


def test_palettes_define_the_same_roles():
    assert ui_theme.DARK.keys() == ui_theme.LIGHT.keys()


def test_module_constants_are_the_dark_palette():
    assert ui_theme.C_ACCENT == ui_theme.DARK["accent"] == "#b5e853"
    assert ui_theme.C_BG == ui_theme.DARK["bg"]


def test_c_follows_the_active_theme():
    assert ui_theme.c("bg") == ui_theme.DARK["bg"]
    ui_theme._theme = "light"
    assert ui_theme.c("bg") == ui_theme.LIGHT["bg"]


def test_theme_preference_round_trip():
    assert ui_theme.load_theme() == "dark"
    ui_theme._theme = "light"
    ui_theme.save_theme()
    ui_theme._theme = "dark"
    assert ui_theme.load_theme() == "light"
    assert ui_theme.current_theme() == "dark"      # reading does not switch


def test_unknown_stored_theme_falls_back_to_dark():
    ui_theme._PREFS_PATH.write_text('{"theme": "neon"}', encoding="utf-8")
    assert ui_theme.load_theme() == "dark"


def test_rgba_helpers():
    assert ui_theme.rgba("#b5e853", 31) == "rgba(181,232,83,31)"
    assert ui_theme.rgba_tuple("#b5e853", 31) == (181, 232, 83, 31)


# ── live switch ──────────────────────────────────────────────────────────────

def test_palette_values_are_unique_so_conversion_is_reversible():
    for palette in (ui_theme.DARK, ui_theme.LIGHT):
        hexes = [v for v in palette.values() if v.startswith("#")]
        assert len(hexes) == len(set(hexes))


def test_convert_qss_round_trips():
    dark = (
        f"QFrame {{ background: {ui_theme.DARK['card']}; border: 1px solid {ui_theme.DARK['border']};"
        f" color: {ui_theme.DARK['text']}; selection: rgba(181,232,83,20); hover: rgba(255,255,255,10);"
        f" brand: #ff9900; }}"
    )
    light = ui_theme.convert_qss(dark, "light")
    assert ui_theme.LIGHT["card"] in light and ui_theme.DARK["card"] not in light
    assert "rgba(90,138,0,20)" in light and "rgba(0,0,0,10)" in light
    assert "#ff9900" in light                      # brand colours are left alone
    assert ui_theme.convert_qss(light, "dark") == dark


def test_themed_maps_dark_palette_colours_only():
    assert ui_theme.themed(ui_theme.DARK["accent"]) == ui_theme.DARK["accent"]
    ui_theme._theme = "light"
    assert ui_theme.themed(ui_theme.DARK["accent"]) == ui_theme.LIGHT["accent"]
    assert ui_theme.themed("#ff9900") == "#ff9900"


# Switching restyles every live widget: run it in a fresh process so the widgets that
# other tests leave behind do not make it crawl.
_SWITCH_SCRIPT = r"""
import os, sys, tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget
app = QApplication([])
import ui_theme
ui_theme._PREFS_PATH = Path(tempfile.mkdtemp()) / "prefs.json"
import log_view, ui_widgets, main_window

seen = []
ui_theme.on_theme_changed(1, seen.append)
w = QWidget()
w.setStyleSheet(f"background: {ui_theme.DARK['card']}; color: {ui_theme.DARK['accent']};")
ui_theme.apply_style(app, "light")
assert seen == ["light"] and ui_theme.current_theme() == "light"
assert ui_theme.LIGHT["bg"] in app.styleSheet()
assert ui_widgets.C_ACCENT == ui_theme.LIGHT["accent"] and ui_theme.C_BG == ui_theme.LIGHT["bg"]
assert ui_theme.LIGHT["card"] in w.styleSheet()
assert log_view._LEVEL_COLORS["error"] == ui_theme.LIGHT["err"]
assert log_view._SELECTION_BG.green() == 138
ui_theme.apply_style(app, "dark")
assert ui_widgets.C_ACCENT == ui_theme.DARK["accent"]
assert w.styleSheet() == f"background: {ui_theme.DARK['card']}; color: {ui_theme.DARK['accent']};"
assert log_view._LEVEL_COLORS["error"] == ui_theme.DARK["err"]

win = main_window.MainWindow()
assert win._theme_btn.text() == "Day"
win._toggle_theme()
assert ui_theme.current_theme() == "light" and ui_theme.load_theme() == "light"
assert win._theme_btn.text() == "Night"
win._toggle_theme()
assert ui_theme.load_theme() == "dark" and win._theme_btn.text() == "Day"
print("ok")
"""


def test_live_theme_switch_in_a_fresh_process(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "HOME": str(tmp_path),
           "PYTHONPATH": str(Path(__file__).resolve().parent.parent)}
    out = subprocess.run([sys.executable, "-c", _SWITCH_SCRIPT], env=env,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0 and "ok" in out.stdout, out.stderr
