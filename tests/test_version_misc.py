"""Cover trivial gaps: version.py and a handful of branches in other modules."""
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

import flyio_utils
import vercel_utils
import version

# -- version.py ----------------------------------------------------------------

def test_version_string_present():
    assert isinstance(version.__version__, str)
    assert len(version.__version__) > 0
    # semver-ish: at least one dot
    assert "." in version.__version__


# -- flyio_utils._get fallbacks ------------------------------------------------

def test_flyio_get_http_error_non_json_body():
    err = urllib.error.HTTPError(url="", code=500, msg="x", hdrs={}, fp=MagicMock())
    err.read = lambda: b"not json"
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RuntimeError, match="500"):
            flyio_utils.list_apps("t")


def test_flyio_get_general_exception():
    with patch("urllib.request.urlopen", side_effect=ConnectionError("down")):
        with pytest.raises(RuntimeError, match="down"):
            flyio_utils.list_apps("t")


def test_flyio_sse_invalid_timestamp_uses_now():
    """Invalid ts string triggers the time.time() fallback."""
    events = [{"message": "x", "timestamp": "not-iso", "region": "", "level": ""}]
    lines = [f"data: {json.dumps(e)}\n".encode() for e in events]
    resp = MagicMock()
    resp.__iter__ = lambda s: iter(lines)
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=resp):
        result = flyio_utils.fetch_logs_sse("t", "a")
    assert len(result) == 1
    assert result[0][0] > 0  # filled by time.time()


def test_flyio_sse_returns_partial_on_late_exception():
    """If a non-timeout exception fires after some events were collected, return partial."""
    good = json.dumps({"message": "ok", "timestamp": "", "region": "", "level": ""}).encode()

    class _Stream:
        def __init__(self):
            self._lines = [b"data: " + good + b"\n"]
            self._i = 0

        def __iter__(self):
            return self

        def __next__(self):
            if self._i == 0:
                self._i += 1
                return self._lines[0]
            raise ValueError("midstream boom")

    resp = MagicMock()
    resp.__iter__ = lambda s: _Stream()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=resp):
        result = flyio_utils.fetch_logs_sse("t", "a")
    # one event was captured before the exception
    assert len(result) == 1
    assert result[0][1] == "ok"


def test_flyio_sse_raises_on_immediate_exception():
    """If the exception fires before any event, RuntimeError is raised."""
    class _Boom:
        def __iter__(self):
            raise ValueError("immediate")

    resp = MagicMock()
    resp.__iter__ = lambda s: _Boom().__iter__()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=resp):
        with pytest.raises(RuntimeError, match="immediate"):
            flyio_utils.fetch_logs_sse("t", "a")


# -- vercel_utils: token persistence + branches --------------------------------

def _fake_urlopen(payload) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_vercel_load_token_returns_value(tmp_path, monkeypatch):
    cfg = tmp_path / "vercel_config.json"
    cfg.write_text(json.dumps({"token": "abc"}))
    monkeypatch.setattr(vercel_utils, "_CONFIG_PATH", cfg)
    assert vercel_utils.load_token() == "abc"


def test_vercel_load_token_returns_empty_when_missing(tmp_path, monkeypatch):
    cfg = tmp_path / "missing.json"
    monkeypatch.setattr(vercel_utils, "_CONFIG_PATH", cfg)
    assert vercel_utils.load_token() == ""


def test_vercel_load_token_returns_empty_on_invalid_json(tmp_path, monkeypatch):
    cfg = tmp_path / "bad.json"
    cfg.write_text("{not json")
    monkeypatch.setattr(vercel_utils, "_CONFIG_PATH", cfg)
    assert vercel_utils.load_token() == ""


def test_vercel_save_token_creates_file(tmp_path, monkeypatch):
    cfg = tmp_path / "sub" / "vercel_config.json"
    monkeypatch.setattr(vercel_utils, "_CONFIG_PATH", cfg)
    vercel_utils.save_token("xyz")
    assert json.loads(cfg.read_text())["token"] == "xyz"


def test_vercel_get_general_exception_wrapped():
    with patch("urllib.request.urlopen", side_effect=ConnectionError("nope")):
        with pytest.raises(RuntimeError, match="nope"):
            vercel_utils.list_projects("t")


def test_vercel_get_http_error_non_json_body():
    err = urllib.error.HTTPError(url="", code=503, msg="x", hdrs={}, fp=MagicMock())
    err.read = lambda: b"plain text"
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RuntimeError, match="503"):
            vercel_utils.list_projects("t")


def test_vercel_verify_token_returns_user_info():
    payload = {"user": {"id": "u1", "username": "alice"}}
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(payload)):
        result = vercel_utils.verify_token("tok")
    assert result == payload


def test_vercel_fetch_deployment_events_passes_since():
    """fetch with since_ms > 0 should include 'since' in URL."""
    captured = {}

    def fake_urlopen(req, **_kw):
        captured["url"] = req.full_url
        return _fake_urlopen([])

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        vercel_utils.fetch_deployment_events("tok", "dpl", since_ms=12345)
    assert "since=12345" in captured["url"]


def test_vercel_fetch_deployment_events_skips_non_dict_items():
    payload = [
        "not a dict",
        {"payload": {"text": "ok", "date": 1}},
    ]
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(payload)):
        result = vercel_utils.fetch_deployment_events("tok", "dpl")
    assert len(result) == 1
    assert result[0][1] == "ok"


def test_vercel_fetch_deployment_events_invalid_iso_ts_yields_zero():
    payload = [{"payload": {"text": "x", "date": "not-iso"}}]
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(payload)):
        result = vercel_utils.fetch_deployment_events("tok", "dpl")
    assert result == [(0, "x")]
