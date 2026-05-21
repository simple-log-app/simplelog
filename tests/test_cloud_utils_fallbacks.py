"""Cover remaining HTTP error JSON-parse fallback paths across cloud utils."""
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

import datadog_utils
import elastic_utils
import flyio_utils
import loki_utils
import railway_utils


def _http_error(code: int, body: bytes):
    err = urllib.error.HTTPError(url="", code=code, msg="", hdrs={}, fp=MagicMock())
    err.read = lambda: body
    return err


# -- datadog_utils _post: non-JSON HTTPError body --------------------------------

def test_datadog_post_http_error_non_json_body():
    err = _http_error(500, b"<html>boom</html>")
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RuntimeError, match="500"):
            datadog_utils.verify_connection("https://api.datadoghq.com", "k", "a")


def test_datadog_post_general_exception():
    with patch("urllib.request.urlopen", side_effect=ConnectionError("net")):
        with pytest.raises(RuntimeError, match="net"):
            datadog_utils.verify_connection("https://api.datadoghq.com", "k", "a")


# -- loki_utils _get: non-JSON HTTPError body -----------------------------------

def test_loki_get_http_error_non_json_body():
    err = _http_error(503, b"plain error text")
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RuntimeError, match="503"):
            loki_utils.verify_connection("http://localhost:3100")


def test_loki_get_general_exception():
    with patch("urllib.request.urlopen", side_effect=ConnectionError("down")):
        with pytest.raises(RuntimeError, match="down"):
            loki_utils.verify_connection("http://localhost:3100")


# -- railway_utils _post: non-JSON HTTPError body --------------------------------

def test_railway_post_http_error_non_json_body():
    err = _http_error(401, b"unauthorized text")
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RuntimeError, match="401"):
            railway_utils.verify_token("bad_token")


def test_railway_post_general_exception():
    with patch("urllib.request.urlopen", side_effect=ConnectionError("net")):
        with pytest.raises(RuntimeError, match="net"):
            railway_utils.verify_token("tok")


# -- elastic_utils _request: HTTPError body, plus fallback "reason" --------------

def test_elastic_request_http_error_non_json_body():
    err = _http_error(500, b"plain text")
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RuntimeError, match="500"):
            elastic_utils.verify_connection("http://localhost:9200")


def test_elastic_request_general_exception():
    with patch("urllib.request.urlopen", side_effect=ConnectionError("dropped")):
        with pytest.raises(RuntimeError, match="dropped"):
            elastic_utils.verify_connection("http://localhost:9200")


# -- flyio sse: TimeoutError suppressed ------------------------------------------

def test_flyio_sse_timeout_returns_empty():
    """TimeoutError during SSE should be swallowed and return whatever was collected."""
    with patch("urllib.request.urlopen", side_effect=TimeoutError("slow")):
        result = flyio_utils.fetch_logs_sse("tok", "app")
    assert result == []
