"""Theme: SVG icons, colour constants and the global stylesheet."""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import (
    QRectF,
    Qt,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QIcon,
    QPainter,
    QPalette,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
)

from simplelog.core.config_store import CONFIG_DIR, read_json, write_json

try:
    from PyQt6.QtCore import QByteArray
    from PyQt6.QtSvg import QSvgRenderer
    _HAS_SVG = True
except ImportError:
    QByteArray = QSvgRenderer = None  # type: ignore[assignment,misc]
    _HAS_SVG = False


_SVG_CLOUD = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M19.35 10.04A7.49 7.49 0 0 0 12 4'
    'C9.11 4 6.6 5.64 5.35 8.04A5.994 5.994 0 0 0 0 14'
    'c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5'
    ' 0-2.64-2.05-4.78-4.65-4.96z"/>'
    "</svg>"
)

_SVG_FOLDER = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M20 6h-8l-2-2H4c-1.1 0-1.99.9-1.99 2'
    'L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2z'
    'm0 12H4V8h16v10z"/>'
    "</svg>"
)

_SVG_SSH = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16'
    'c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zM4 18V8h16v10H4zm2-3h4v-2H6v2z'
    'm6 0h4v-2h-4v2zM6 11h2V9H6v2zm4 0h4V9h-4v2zm6 0h2V9h-2v2z"/>'
    "</svg>"
)

_SVG_DOCKER = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M13.98 8H10V6h3.98V8zm-5.98 0H4.02V6H8V8z'
    'm5.98 2.03H10V8.03h3.98v2zM8 10.03H4.02V8.03H8v2z'
    'm5.98 2H10v-2h3.98v2zM8 12.03H4.02v-2H8v2z'
    'm10 2.03h-4V12h4V14zm4 0h-3.98v2H18v-2z'
    'm3.18 2.5C20.76 6 20 4.53 20 4.53s-1 .47-1.82 1.97'
    'c-.56.99-.18 2.5-.18 2.5H23s.5-1.5-.82-2.5z'
    'M2 14c0 2.21 2.69 4 6 4h8c3.31 0 6-1.79 6-4H2z"/>'
    "</svg>"
)

_SVG_VERCEL = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M12 2L2 19.5h20L12 2z"/>'
    "</svg>"
)

_SVG_GCP = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z'
    'm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93z'
    'm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2'
    'c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>'
    "</svg>"
)

_SVG_AZURE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M13.05 4.24L6.56 18.05l14.36.02-1.52-1.46-9.1-1.84 5.2-4.62-3.45-5.91z'
    'M11.4 6.22l-7.88 12.1 2.57-.01 5.29-8.46-.34-1.24 .36-2.39z"/>'
    "</svg>"
)

_SVG_LOKI = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M4 5h2v14H4V5zM8 6h12v2H8V6zM8 11h9v2H8v-2zM8 16h12v2H8v-2z"/>'
    "</svg>"
)

_SVG_DATADOG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M12 2l8.5 4.9v10.2L12 22l-8.5-4.9V6.9L12 2z"/>'
    "</svg>"
)

_SVG_ELASTIC = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z'
    'm1 15H7v-2h6v2zm4-4H7V9h10v2z"/>'
    "</svg>"
)

_SVG_RAILWAY = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M4 16h16v2H4v-2zM4 6h16v2H4V6zm4 5h8v2H8v-2z'
    'M6 19l-2 3h2l1-1.5L8 22h2l-2-3H6zm10 0l-2 3h2l1-1.5 1 1.5h2l-2-3h-2z"/>'
    "</svg>"
)

_SVG_FLYIO = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M12 2C8.13 2 5 5.13 5 9c0 2.74 1.54 5.12 3.82 6.38'
    'L8 20h2l.5-3h3l.5 3h2l-.82-4.62C17.46 14.12 19 11.74 19 9c0-3.87-3.13-7-7-7z'
    'm0 2c2.76 0 5 2.24 5 5s-2.24 5-5 5-5-2.24-5-5 2.24-5 5-5z"/>'
    "</svg>"
)

_SVG_KUBERNETES = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M12 2l9 4.5v9L12 20l-9-4.5v-9L12 2zm0 2.18L5 7.64v8.72'
    'L12 19.82l7-3.46V7.64L12 4.18zm-1 3.32h2v5l-1 1-1-1V7.5zm0 7h2v2h-2v-2z"/>'
    "</svg>"
)

_SVG_CLOUDFLARE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M18.92 10.36c-.28-3-2.79-5.36-5.89-5.36'
    '-2.33 0-4.36 1.37-5.35 3.38-.44-.22-.93-.34-1.45-.34-1.79 0-3.23 1.45-3.23 3.24'
    ' 0 .18.02.36.05.53C1.84 12.51 1 13.72 1 15.15 1 17.01 2.49 18.5 4.35 18.5h14.3'
    'c1.86 0 3.35-1.49 3.35-3.35 0-1.77-1.38-3.22-3.13-3.33l.05-.46z"/>'
    "</svg>"
)

_SVG_REMOTE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2'
    'C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0z'
    'm-4-4 2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/>'
    "</svg>"
)

_SVG_SUN = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}"'
    ' stroke-width="1.8" stroke-linecap="round">'
    '<circle cx="12" cy="12" r="4"/>'
    '<path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6L7 7M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4"/>'
    "</svg>"
)

_SVG_MOON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}"'
    ' stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>'
    "</svg>"
)

_SVG_SEARCH = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
    '<circle cx="11" cy="11" r="6.5" stroke="{color}" stroke-width="2"/>'
    '<path d="M16 16l4.5 4.5" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
    "</svg>"
)

_SVG_TRASH = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="{color}" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12z'
    'M8 9h8v10H8V9zm7.5-5-1-1h-5l-1 1H5v2h14V4z"/>'
    "</svg>"
)

_SVG_STOP_SQ = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<rect fill="{color}" x="6" y="6" width="12" height="12" rx="2" ry="2"/>'
    "</svg>"
)

_SVG_CLOSE_X = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path stroke="{color}" stroke-width="2.5" stroke-linecap="round"'
    ' fill="none" d="M5 5L19 19M19 5L5 19"/>'
    "</svg>"
)

_SVG_CHEVRON_LEFT = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
    '<path fill="{color}" d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/>'
    "</svg>"
)

_SVG_CHEVRON_RIGHT = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
    '<path fill="{color}" d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/>'
    "</svg>"
)


def _svg_icon(svg_tmpl: str, color: str, size: int = 16) -> QIcon:
    """Render an SVG template (with {color} placeholder) to a QIcon."""
    if not _HAS_SVG:
        return QIcon()
    svg = svg_tmpl.replace("{color}", color)
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    return QIcon(pm)


_BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))  # repo root
_logo_cache: dict[tuple, QPixmap] = {}


def _logo_svg(logo: str, color: str) -> bytes | None:
    """The bundled SVG *logo* painted in *color*, or None when it is missing."""
    try:
        svg = (_BASE / logo).read_text(encoding="utf-8")
    except OSError:
        return None
    if "{color}" in svg:
        return svg.replace("{color}", color).encode()
    return svg.replace("<svg ", f'<svg fill="{color}" ', 1).encode()


def provider_logo(logo: str, glyph: str, color: str, size: int, tile: bool = True) -> QPixmap:
    """Brand logo of a provider: monochrome glyph tinted with *color*.

    With *tile* the logo sits on a rounded square (colour at 10 %, border at 20 %);
    without it only the glyph is drawn. Falls back to the text *glyph* when the asset
    or SVG support is missing.
    """
    if _theme == "light" and QColor(color).lightness() > 200:
        color = LIGHT["text"]   # a near-white brand colour would vanish on a light surface
    key = (logo, glyph, color, size, tile)
    cached = _logo_cache.get(key)
    if cached is not None:
        return cached
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.setDevicePixelRatio(scale)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    base = QColor(color)
    if tile:
        radius = size / 4.5
        fill, border = QColor(base), QColor(base)
        fill.setAlphaF(0.10)
        border.setAlphaF(0.20)
        p.setBrush(fill)
        p.setPen(border)
        p.drawRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1), radius, radius)
    glyph_size = size * 0.62 if tile else size
    off = (size - glyph_size) / 2
    rect = QRectF(off, off, glyph_size, glyph_size)
    data = _logo_svg(logo, color) if logo and _HAS_SVG else None
    renderer = QSvgRenderer(QByteArray(data)) if data else None
    if renderer is not None and renderer.isValid():
        renderer.render(p, rect)
    else:
        font = QFont("Inter")
        font.setPixelSize(max(8, int(glyph_size)))
        p.setFont(font)
        p.setPen(base)
        p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, glyph)
    p.end()
    _logo_cache[key] = pm
    return pm


def with_status_dot(pixmap: QPixmap, color: str) -> QPixmap:
    """*pixmap* with a small filled dot of *color* in its bottom-right corner."""
    out = QPixmap(pixmap)
    ratio = out.devicePixelRatio() or 1.0
    size = out.width() / ratio
    radius = max(2.5, size * 0.22)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    centre = size - radius - 0.5
    # a ring in the tab colour keeps the dot readable over the logo
    p.setBrush(QColor(THEMES[_theme]["panel"]))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(centre - radius - 1, centre - radius - 1, 2 * radius + 2, 2 * radius + 2))
    p.setBrush(QColor(color))
    p.drawEllipse(QRectF(centre - radius, centre - radius, 2 * radius, 2 * radius))
    p.end()
    return out


# ── Colour tokens ──────────────────────────────────────────────────────────────

DARK: dict[str, str] = {
    "bg": "#0c0c0e",
    "rail": "#09090b",
    "side": "#0f0f11",
    "panel": "#121214",
    "card": "#161619",
    "el": "#1b1b1f",
    "status": "#09090c",
    "border": "#232327",
    "border2": "#2e2e33",
    "text": "#e4e4e7",
    "muted": "#71717a",
    "muted2": "#4a4a52",
    "accent": "#b5e853",
    "accent_hover": "#c6f06a",
    "accent_press": "#a3d445",
    "accent_dim": "rgba(181,232,83,31)",
    "sel_bg": "rgba(181,232,83,31)",
    "on_accent": "#0c0f06",
    "err": "#ef6b6b",
    "warn": "#e8b04a",
    "info": "#5fc48a",
    "debug": "#6e9bff",
    "trace": "#b08cf0",
    "ts": "#5cc0d0",
    "hover": "rgba(255,255,255,10)",
    "handle": "rgba(255,255,255,31)",
    "overlay_surface": "#111114",
}

LIGHT: dict[str, str] = {
    "bg": "#fafafa",
    "rail": "#f0f0f2",
    "side": "#f6f6f7",
    "panel": "#f1f1f3",
    "card": "#ffffff",
    "el": "#ececef",
    "status": "#f2f2f4",
    "border": "#e2e2e6",
    "border2": "#d1d1d6",
    "text": "#18181b",
    "muted": "#6b6b76",
    "muted2": "#a1a1aa",
    "accent": "#5a8a00",
    "accent_hover": "#4a7400",
    "accent_press": "#3d6200",
    "accent_dim": "rgba(90,138,0,31)",
    "sel_bg": "rgba(90,138,0,31)",
    "on_accent": "#fdfdfd",
    "err": "#d64545",
    "warn": "#b7791f",
    "info": "#2e8f57",
    "debug": "#2f5fd0",
    "trace": "#7c4dd1",
    "ts": "#0e8a9c",
    "hover": "rgba(0,0,0,10)",
    "handle": "rgba(0,0,0,38)",
    "overlay_surface": "#fefefe",
}

THEMES: dict[str, dict[str, str]] = {"dark": DARK, "light": LIGHT}

_theme = "dark"          # the theme in use: "dark" | "light"
_mode = "dark"           # the preference: "dark" | "light" | "auto" (follow the system)
MODES = ("auto", "light", "dark")
_PREFS_PATH = CONFIG_DIR / "prefs.json"


_theme_callbacks: dict[int, Callable[[str], None]] = {}


def on_theme_changed(key: int, fn: Callable[[str], None]) -> None:
    """Register *fn(theme)*, called after every theme switch (replaces any *key* entry)."""
    _theme_callbacks[key] = fn


def off_theme_changed(key: int) -> None:
    _theme_callbacks.pop(key, None)


def current_theme() -> str:
    return _theme


def c(role: str) -> str:
    """Colour of *role* (``"bg"``, ``"accent"``...) in the active theme."""
    return THEMES[_theme][role]


def theme_mode() -> str:
    """The preference: "dark", "light" or "auto" (follow the system)."""
    return _mode


def system_theme() -> str:
    """"light" or "dark" according to the operating system ("dark" when it cannot tell)."""
    hints = QGuiApplication.styleHints()
    scheme = hints.colorScheme() if hints is not None else Qt.ColorScheme.Unknown
    return "light" if scheme == Qt.ColorScheme.Light else "dark"


def resolve_theme(mode: str) -> str:
    return system_theme() if mode == "auto" else (mode if mode in THEMES else "dark")


def load_theme() -> str:
    """The persisted preference ("dark" by default); apply it with apply_mode()."""
    prefs = read_json(_PREFS_PATH, {})
    candidate = prefs.get("theme") if isinstance(prefs, dict) else None
    return candidate if candidate in MODES else "dark"


def save_theme() -> None:
    prefs = read_json(_PREFS_PATH, {})
    if not isinstance(prefs, dict):
        prefs = {}
    prefs["theme"] = _mode
    try:
        write_json(_PREFS_PATH, prefs)
    except OSError:
        pass


# Module-level constants hold the dark palette; widgets that must follow a theme switch
# read their colours through c() instead.
C_BG         = DARK["bg"]
C_RAIL       = DARK["rail"]
C_SIDE       = DARK["side"]
C_PANEL      = DARK["panel"]
C_CARD       = DARK["card"]
C_EL         = DARK["el"]
C_STATUS     = DARK["status"]
C_BORDER     = DARK["border"]
C_BORDER2    = DARK["border2"]
C_ACCENT     = DARK["accent"]
C_ACCENT_DIM = DARK["accent_dim"]
C_ACCENT_HOVER = DARK["accent_hover"]
C_ACCENT_PRESS = DARK["accent_press"]
C_ON_ACCENT  = DARK["on_accent"]
C_TEXT       = DARK["text"]
C_MUTED      = DARK["muted"]
C_MUTED2     = DARK["muted2"]
C_SEL_BG     = DARK["sel_bg"]
C_ERR        = DARK["err"]
C_WARN       = DARK["warn"]
C_INFO       = DARK["info"]
C_DEBUG      = DARK["debug"]
C_TRACE      = DARK["trace"]
C_TS         = DARK["ts"]
C_HOVER      = DARK["hover"]
C_OVERLAY_SURFACE = DARK["overlay_surface"]

C_DIVIDER  = C_BORDER  # alias used in painter pens


def rgba(hex_color: str, alpha: int) -> str:
    """Stylesheet ``rgba()`` string for *hex_color* at *alpha* (0-255)."""
    q = QColor(hex_color)
    return f"rgba({q.red()},{q.green()},{q.blue()},{alpha})"


def rgba_tuple(hex_color: str, alpha: int) -> tuple[int, int, int, int]:
    """``(r, g, b, a)`` of *hex_color* at *alpha*, for ``QColor(*...)``."""
    q = QColor(hex_color)
    return q.red(), q.green(), q.blue(), alpha


# ── Switching theme at runtime ─────────────────────────────────────────────────

_CONST_ROLES = {
    "C_BG": "bg", "C_RAIL": "rail", "C_SIDE": "side", "C_PANEL": "panel", "C_CARD": "card",
    "C_EL": "el", "C_STATUS": "status", "C_BORDER": "border", "C_BORDER2": "border2",
    "C_ACCENT": "accent", "C_ACCENT_DIM": "accent_dim", "C_ACCENT_HOVER": "accent_hover",
    "C_ACCENT_PRESS": "accent_press", "C_ON_ACCENT": "on_accent", "C_TEXT": "text",
    "C_MUTED": "muted", "C_MUTED2": "muted2", "C_SEL_BG": "sel_bg", "C_ERR": "err",
    "C_WARN": "warn", "C_INFO": "info", "C_DEBUG": "debug", "C_TRACE": "trace", "C_TS": "ts",
    "C_HOVER": "hover", "C_OVERLAY_SURFACE": "overlay_surface", "C_DIVIDER": "border",
}

_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}(?![0-9a-fA-F])")
_RGBA_RE = re.compile(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,")


def _triple(color: str) -> tuple[int, int, int]:
    q = QColor(color) if color.startswith("#") else None
    if q is not None:
        return q.red(), q.green(), q.blue()
    nums = [int(n) for n in re.findall(r"\d+", color)[:3]]
    return nums[0], nums[1], nums[2]


def _colour_maps(src: str, dst: str) -> tuple[dict[str, str], dict[tuple, tuple]]:
    hexes: dict[str, str] = {}
    triples: dict[tuple, tuple] = {}
    for role, sv in THEMES[src].items():
        dv = THEMES[dst][role]
        if sv.startswith("#"):
            hexes[sv.lower()] = dv
        triples[_triple(sv)] = _triple(dv)
    return hexes, triples


def convert_qss(qss: str, to: str) -> str:
    """Rewrite the palette colours of *qss* from the other theme to theme *to*."""
    src = "light" if to == "dark" else "dark"
    hexes, triples = _colour_maps(src, to)

    def hex_sub(m: re.Match) -> str:
        return hexes.get(m.group(0).lower(), m.group(0))

    def rgba_sub(m: re.Match) -> str:
        r, g, b = triples.get((int(m.group(1)), int(m.group(2)), int(m.group(3))),
                              (m.group(1), m.group(2), m.group(3)))
        return f"rgba({r},{g},{b},"

    return _RGBA_RE.sub(rgba_sub, _HEX_RE.sub(hex_sub, qss))


def themed(color: str) -> str:
    """*color* if it is not a palette colour, else its equivalent in the active theme."""
    for role, dark_value in DARK.items():
        if color == dark_value:
            return THEMES[_theme][role]
    return color


def _rewrite_constants(old: str, new: str) -> None:
    """Point every module's imported ``C_*`` constants at the *new* theme's colours."""
    for mod in list(sys.modules.values()):
        d = getattr(mod, "__dict__", None)
        if not d or "C_BG" not in d and "C_TEXT" not in d and "C_ACCENT" not in d:
            continue
        for name, role in _CONST_ROLES.items():
            if name in d and d[name] == THEMES[old][role]:
                d[name] = THEMES[new][role]


def _convert_widgets(new: str) -> None:
    for w in QApplication.allWidgets():
        qss = w.styleSheet()
        if qss:
            converted = convert_qss(qss, new)
            if converted != qss:
                w.setStyleSheet(converted)


# ── apply_style ────────────────────────────────────────────────────────────────

def apply_mode(app: QApplication, mode: str) -> None:
    """Set the preference to *mode* and show the matching theme."""
    global _mode
    _mode = mode if mode in MODES else "dark"
    apply_style(app, resolve_theme(_mode))


def apply_style(app: QApplication, theme: str | None = None) -> None:
    """Apply the palette and global stylesheet of *theme* (default: the active one)."""
    global _theme
    old = _theme
    changed = theme is not None and theme in THEMES and theme != old
    if changed:
        _theme = theme
        _rewrite_constants(old, theme)
    t = THEMES[_theme]
    C_BG, C_RAIL, C_PANEL, C_CARD = t["bg"], t["rail"], t["panel"], t["card"]
    C_STATUS, C_BORDER, C_BORDER2 = t["status"], t["border"], t["border2"]
    C_TEXT, C_MUTED, C_ERR = t["text"], t["muted"], t["err"]
    C_ACCENT, C_ACCENT_DIM, C_SEL_BG = t["accent"], t["accent_dim"], t["sel_bg"]
    C_HOVER, C_HANDLE = t["hover"], t["handle"]

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(C_BG))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(C_TEXT))
    palette.setColor(QPalette.ColorRole.Base,            QColor(C_CARD))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(C_BG))
    palette.setColor(QPalette.ColorRole.Text,            QColor(C_TEXT))
    palette.setColor(QPalette.ColorRole.Button,          QColor(C_CARD))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(C_TEXT))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(C_ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(t["on_accent"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(C_MUTED))
    palette.setColor(QPalette.ColorRole.BrightText,      QColor(C_ERR))
    app.setPalette(palette)

    app.setStyleSheet(f"""
        QWidget {{
            background-color: {C_BG};
            color: {C_TEXT};
            font-family: "Inter", sans-serif;
            font-size: 12px;
        }}
        QLineEdit, QComboBox, QSpinBox {{
            background: {C_BG};
            border: 1px solid {C_BORDER2};
            border-radius: 5px;
            padding: 0 9px;
            color: {C_TEXT};
            min-height: 28px;
            max-height: 28px;
            font-size: 12px;
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
            border: 1px solid {C_ACCENT};
        }}
        QPushButton {{
            background-color: transparent;
            border: 1px solid {C_BORDER};
            border-radius: 5px;
            padding: 0 12px;
            color: {C_MUTED};
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: {C_HOVER};
            color: {C_TEXT};
        }}
        QPushButton#primary {{
            background-color: {C_ACCENT};
            color: {t['on_accent']};
            border: none;
            font-weight: bold;
        }}
        QPushButton#primary:hover {{
            background-color: {t['accent_hover']};
        }}
        QPushButton#primary:pressed {{
            background-color: {t['accent_press']};
        }}
        QPushButton#danger {{
            color: {C_ERR};
            border-color: {rgba(C_ERR, 77)};
            background: transparent;
        }}
        QPushButton#danger:hover {{
            background: {rgba(C_ERR, 20)};
        }}
        QPushButton:disabled {{
            background-color: {C_ACCENT_DIM};
            color: {C_MUTED};
            border: none;
        }}
        QListWidget {{
            background: {C_BG};
            border: 1px solid {C_BORDER};
            border-radius: 5px;
            font-family: "JetBrains Mono", monospace;
            font-size: 11px;
        }}
        QListWidget::item {{
            padding: 0 10px;
            min-height: 24px;
            border-radius: 0;
        }}
        QListWidget::item:selected {{
            background: {C_SEL_BG};
            color: {C_ACCENT};
            border-left: 2px solid {C_ACCENT};
        }}
        QListWidget::item:hover {{
            background: {C_HOVER};
        }}
        QTabWidget::pane {{
            border: none;
        }}
        QTabBar::tab {{
            background: {C_PANEL};
            border: none;
            border-right: 1px solid {C_BORDER};
            padding: 0 14px;
            min-height: 34px;
            color: {C_MUTED};
            font-size: 12px;
        }}
        QTabBar::tab:selected {{
            background: {C_BG};
            color: {C_TEXT};
            border-bottom: 2px solid {C_ACCENT};
        }}
        QTabBar::tab:hover:!selected {{
            color: {C_TEXT};
            background: {C_HOVER};
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QComboBox QAbstractItemView {{
            background: {C_CARD};
            border: 1px solid {C_BORDER};
            selection-background-color: {C_SEL_BG};
            selection-color: {C_ACCENT};
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 6px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {C_HANDLE};
            border-radius: 3px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {rgba(C_ACCENT, 128)};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 6px;
        }}
        QScrollBar::handle:horizontal {{
            background: {C_HANDLE};
            border-radius: 3px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {rgba(C_ACCENT, 128)};
        }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
        QCheckBox {{
            spacing: 6px;
            color: {C_MUTED};
            font-size: 11px;
        }}
        QCheckBox::indicator {{
            width: 14px;
            height: 14px;
            border: 1px solid {C_BORDER};
            border-radius: 3px;
            background: {C_BG};
        }}
        QCheckBox::indicator:checked {{
            background: {C_ACCENT};
            border-color: {C_ACCENT};
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QToolTip {{
            background: {C_CARD};
            color: {C_TEXT};
            border: 1px solid {C_BORDER};
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 11px;
        }}
        QStatusBar {{
            background: {C_STATUS};
            border-top: 1px solid {C_BORDER};
            color: {C_MUTED};
            font-family: "JetBrains Mono", monospace;
            font-size: 11px;
        }}
        QMenuBar {{
            background: {C_RAIL};
            color: {C_TEXT};
            border-bottom: 1px solid {C_BORDER};
            font-size: 12px;
            padding: 2px 4px;
        }}
        QMenuBar::item {{
            background: transparent;
            padding: 5px 12px;
            border-radius: 4px;
        }}
        QMenuBar::item:selected {{
            background: {C_HOVER};
            color: {C_ACCENT};
        }}
        QMenu {{
            background: {C_CARD};
            border: 1px solid {C_BORDER};
            border-radius: 6px;
            padding: 4px 0;
            font-size: 12px;
        }}
        QMenu::item {{
            padding: 8px 24px 8px 16px;
            color: {C_TEXT};
        }}
        QMenu::item:selected {{
            background: {C_SEL_BG};
            color: {C_ACCENT};
        }}
        QMenu::separator {{
            height: 1px;
            background: {C_BORDER};
            margin: 4px 8px;
        }}
    """)
    if changed:
        _convert_widgets(_theme)
        for fn in list(_theme_callbacks.values()):
            try:
                fn(_theme)
            except Exception:
                pass
