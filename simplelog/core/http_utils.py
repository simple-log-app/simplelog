"""http_utils.py — one small JSON-over-HTTP client shared by the newer log sources."""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request


def normalize_base_url(url: str, default_scheme: str = "https") -> str:
    """``host`` or ``https://host/`` -> ``https://host`` (only http / https are accepted)."""
    url = url.strip()
    if not url:
        raise RuntimeError("URL is empty")
    if "://" not in url:
        url = f"{default_scheme}://{url}"
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise RuntimeError(f"Unsupported URL: {url}")
    return f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/")


def tls_context(verify: bool = True) -> ssl.SSLContext | None:
    """None for the default (verified) context, else one that skips verification."""
    if verify:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def error_message(label: str, e: urllib.error.HTTPError) -> str:
    """``"Label 401: reason"`` from an HTTP error (the body is searched for a message)."""
    try:
        raw = e.read().decode("utf-8", errors="replace")
    except Exception:
        raw = ""
    msg = raw or str(e.reason)
    try:
        body = json.loads(raw)
        if isinstance(body, dict):
            msg = str(body.get("message") or body.get("error") or body.get("detail") or msg)
    except ValueError:
        pass
    return f"{label} {e.code}: {msg.strip()[:300]}"


def request(
    url: str,
    *,
    headers: dict | None = None,
    data: bytes | dict | None = None,
    form: dict | None = None,
    method: str | None = None,
    timeout: int = 20,
    label: str = "",
    context: ssl.SSLContext | None = None,
):
    """Open *url* and return the (still open) response; failures raise RuntimeError.

    *data* may be bytes or a dict (sent as JSON); *form* is sent urlencoded.
    """
    hdrs = dict(headers or {})
    body = None
    if form is not None:
        body = urllib.parse.urlencode(form).encode()
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif isinstance(data, dict):
        body = json.dumps(data).encode()
        hdrs.setdefault("Content-Type", "application/json")
    elif data is not None:
        body = data
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=context)
    except urllib.error.HTTPError as e:
        raise RuntimeError(error_message(label or "HTTP", e)) from e
    except Exception as e:
        raise RuntimeError(f"{label}: {e}".strip(": ")) from e


def get_json(url: str, **kwargs):
    """GET *url* and decode the JSON body."""
    with request(url, **kwargs) as resp:
        try:
            return json.loads(resp.read())
        except ValueError as e:
            raise RuntimeError(f"{kwargs.get('label', 'HTTP')}: invalid JSON in the response") from e
