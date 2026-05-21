"""cloudflare_utils.py — Cloudflare Workers log helpers for SimpleLog."""
from __future__ import annotations

import base64
import contextlib
import json
import os
import socket
import ssl
import struct
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

_API_BASE = "https://api.cloudflare.com/client/v4"


def _headers(api_token: str) -> dict:
    return {
        "Authorization": f"Bearer {api_token}",
        "Content-Type":  "application/json",
    }


def _request(path: str, api_token: str, *, method: str = "GET",
             body: dict | None = None, timeout: int = 15) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        _API_BASE + path, data=data,
        headers=_headers(api_token), method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            errors = json.loads(raw).get("errors", [])
            msg = "; ".join(err.get("message", "") for err in errors if err.get("message")) or raw
        except Exception:
            msg = raw
        raise RuntimeError(f"Cloudflare {e.code}: {msg}") from e
    except Exception as e:
        raise RuntimeError(str(e)) from e


def _get(path: str, api_token: str, timeout: int = 15) -> dict:
    return _request(path, api_token, timeout=timeout)


def _post(path: str, api_token: str, body: dict | None = None) -> dict:
    return _request(path, api_token, method="POST", body=body or {})


def _delete(path: str, api_token: str) -> None:
    req = urllib.request.Request(
        _API_BASE + path, headers=_headers(api_token), method="DELETE",
    )
    with contextlib.suppress(Exception):
        urllib.request.urlopen(req, timeout=10)


def list_workers(api_token: str, account_id: str) -> list[str]:
    """Return sorted list of worker script IDs. Raises RuntimeError on failure."""
    data = _get(f"/accounts/{account_id}/workers/scripts", api_token)
    if not data.get("success"):
        errs = data.get("errors", [])
        msg = errs[0].get("message", "Unknown error") if errs else "Unknown error"
        raise RuntimeError(f"Failed to list workers: {msg}")
    return sorted(s["id"] for s in data.get("result", []) if s.get("id"))


def create_tail(api_token: str, account_id: str, script_name: str) -> dict:
    """Create a tail session. Returns dict with 'id', 'url' (wss://…), 'expires_at'."""
    data = _post(
        f"/accounts/{account_id}/workers/scripts/{script_name}/tails",
        api_token,
    )
    if not data.get("success"):
        errs = data.get("errors", [])
        msg = errs[0].get("message", "Unknown error") if errs else "Unknown error"
        raise RuntimeError(f"Failed to create tail: {msg}")
    return data["result"]


def delete_tail(api_token: str, account_id: str, script_name: str, tail_id: str) -> None:
    """Delete a tail session (cleanup on disconnect)."""
    _delete(
        f"/accounts/{account_id}/workers/scripts/{script_name}/tails/{tail_id}",
        api_token,
    )


# ── Minimal WebSocket client (no external deps) ──────────────────────────────

def _recv_exact(ssock: ssl.SSLSocket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = ssock.recv(n - len(buf))
        if not chunk:
            raise EOFError("WebSocket connection closed")
        buf += chunk
    return buf


def ws_connect(ws_url: str, api_token: str = "", timeout: int = 30) -> ssl.SSLSocket:
    """Perform the WebSocket upgrade handshake and return the connected SSL socket."""
    parsed = urlparse(ws_url)
    host = parsed.hostname
    port = parsed.port or 443
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    key = base64.b64encode(os.urandom(16)).decode()
    ctx = ssl.create_default_context()
    raw = socket.create_connection((host, port), timeout=timeout)
    ssock = ctx.wrap_socket(raw, server_hostname=host)

    handshake = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "Sec-WebSocket-Protocol: trace-v1\r\n"
        f"User-Agent: simplelog/1.0\r\n"
        "\r\n"
    ).encode()
    ssock.sendall(handshake)

    response = b""
    while b"\r\n\r\n" not in response:
        chunk = ssock.recv(4096)
        if not chunk:
            raise RuntimeError("Connection closed during WebSocket handshake")
        response += chunk

    first_line = response.split(b"\r\n")[0].decode("utf-8", errors="replace")
    if "101" not in first_line:
        raise RuntimeError(f"WebSocket upgrade failed: {first_line.strip()}")

    ssock.settimeout(35)  # > server ping interval
    return ssock


def ws_recv_frame(ssock: ssl.SSLSocket) -> tuple[int, bytes]:
    """Read one WebSocket frame. Returns (opcode, payload)."""
    header = _recv_exact(ssock, 2)
    opcode = header[0] & 0x0F
    masked = bool(header[1] & 0x80)
    length = header[1] & 0x7F

    if length == 126:
        length = struct.unpack(">H", _recv_exact(ssock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _recv_exact(ssock, 8))[0]

    mask = _recv_exact(ssock, 4) if masked else b""
    data = _recv_exact(ssock, length)

    if masked:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))

    return opcode, data


def ws_send_frame_unmasked(ssock: ssl.SSLSocket, opcode: int, payload: bytes = b"") -> None:
    """Send an unmasked WebSocket frame (Cloudflare tail init uses mask:false)."""
    n = len(payload)
    if n < 126:
        header = bytes([0x80 | opcode, n])
    elif n < 65536:
        header = bytes([0x80 | opcode, 126]) + struct.pack(">H", n)
    else:
        header = bytes([0x80 | opcode, 127]) + struct.pack(">Q", n)
    ssock.sendall(header + payload)


def ws_send_frame(ssock: ssl.SSLSocket, opcode: int, payload: bytes = b"") -> None:
    """Send a masked WebSocket frame (client→server masking is required by RFC 6455)."""
    mask = os.urandom(4)
    n = len(payload)
    if n < 126:
        header = bytes([0x80 | opcode, 0x80 | n])
    elif n < 65536:
        header = bytes([0x80 | opcode, 0x80 | 126]) + struct.pack(">H", n)
    else:
        header = bytes([0x80 | opcode, 0x80 | 127]) + struct.pack(">Q", n)
    header += mask
    masked_payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    ssock.sendall(header + masked_payload)


def ws_close(ssock: ssl.SSLSocket) -> None:
    """Send a WebSocket close frame and shut down the socket."""
    with contextlib.suppress(Exception):
        ws_send_frame(ssock, 8)
    with contextlib.suppress(Exception):
        ssock.close()


def h2_available() -> bool:
    """Return True if the h2 library is installed (HTTP/2 WebSocket support)."""
    try:
        import h2  # noqa: F401
        return True
    except ImportError:
        return False


# ── HTTP/2 WebSocket via RFC 8441 ─────────────────────────────────────────────

class _H2WSSock:
    """Thin wrapper over an HTTP/2 stream that mimics a socket for ws_recv_frame."""

    def __init__(self, ssock: ssl.SSLSocket, conn: Any, stream_id: int) -> None:
        self._ssock     = ssock
        self._conn      = conn
        self._stream_id = stream_id
        self._buf       = bytearray()

    def recv(self, n: int) -> bytes:
        """Return exactly n bytes, reading h2 DATA frames as needed."""
        while len(self._buf) < n:
            raw = self._ssock.recv(65535)
            if not raw:
                raise EOFError("Connection closed")
            events = self._conn.receive_data(raw)
            out = self._conn.data_to_send(65535)
            if out:
                self._ssock.sendall(out)
            for ev in events:
                ev_type = type(ev).__name__
                if ev_type == "DataReceived":
                    self._buf.extend(ev.data)
                    self._conn.acknowledge_received_data(
                        ev.flow_controlled_length, ev.stream_id
                    )
                elif ev_type in ("StreamEnded", "ConnectionTerminated", "StreamReset"):
                    if len(self._buf) < n:
                        raise EOFError("Stream ended")
        result = bytes(self._buf[:n])
        self._buf = self._buf[n:]
        return result

    def sendall(self, data: bytes) -> None:
        self._conn.send_data(self._stream_id, data, end_stream=False)
        out = self._conn.data_to_send(65535)
        if out:
            self._ssock.sendall(out)

    def settimeout(self, t: float) -> None:
        self._ssock.settimeout(t)

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._ssock.close()


def ws_connect_h2(ws_url: str, api_token: str = "", timeout: int = 30) -> _H2WSSock:
    """Connect via HTTP/2 WebSocket (RFC 8441). Requires the h2 library."""
    import h2.config  # type: ignore
    import h2.connection  # type: ignore
    import h2.events  # type: ignore

    parsed = urlparse(ws_url)
    host   = parsed.hostname or ""
    port   = parsed.port or 443
    path   = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    ctx = ssl.create_default_context()
    ctx.set_alpn_protocols(["h2"])
    raw   = socket.create_connection((host, port), timeout=timeout)
    ssock = ctx.wrap_socket(raw, server_hostname=host)

    if ssock.selected_alpn_protocol() != "h2":
        ssock.close()
        raise RuntimeError(
            f"Server did not negotiate h2 (got {ssock.selected_alpn_protocol()!r})"
        )

    config = h2.config.H2Configuration(client_side=True, header_encoding="utf-8")
    conn   = h2.connection.H2Connection(config=config)
    conn.initiate_connection()
    ssock.sendall(conn.data_to_send(65535))

    # Wait for server SETTINGS before sending the CONNECT request.
    # RFC 8441 requires the server to advertise SETTINGS_ENABLE_CONNECT_PROTOCOL.
    ssock.settimeout(timeout)
    settings_received = False
    while not settings_received:
        raw = ssock.recv(65535)
        if not raw:
            raise RuntimeError("Connection closed before SETTINGS")
        events = conn.receive_data(raw)
        ssock.sendall(conn.data_to_send(65535))
        for ev in events:
            if type(ev).__name__ == "SettingsAcknowledged":
                settings_received = True
            elif type(ev).__name__ == "RemoteSettingsChanged":
                settings_received = True

    ws_key    = base64.b64encode(os.urandom(16)).decode()
    stream_id = conn.get_next_available_stream_id()
    # Only RFC 8441 pseudo-headers + websocket negotiation headers.
    # Do NOT include 'upgrade' or 'connection' — they are HTTP/1.1 only and
    # forbidden in HTTP/2 (RFC 7540 §8.1.2.2), causing a 400 response.
    headers   = [
        (":method",                "CONNECT"),
        (":protocol",              "websocket"),
        (":scheme",                "https"),
        (":authority",             host),
        (":path",                  path),
        ("sec-websocket-version",  "13"),
        ("sec-websocket-key",      ws_key),
        ("sec-websocket-protocol", "trace-v1"),
    ]
    if api_token:
        headers.append(("authorization", f"Bearer {api_token}"))

    conn.send_headers(stream_id=stream_id, headers=headers, end_stream=False)
    ssock.sendall(conn.data_to_send(65535))

    ssock.settimeout(timeout)
    while True:
        raw = ssock.recv(65535)
        if not raw:
            raise RuntimeError("Connection closed before response")
        events = conn.receive_data(raw)
        ssock.sendall(conn.data_to_send(65535))
        for ev in events:
            ev_type = type(ev).__name__
            if ev_type == "ResponseReceived":
                status = next(
                    (int(v) for n, v in ev.headers if n == ":status"), None
                )
                if status != 200:
                    raise RuntimeError(f"HTTP/2 WebSocket CONNECT failed: {status}")
                sock       = _H2WSSock(ssock, conn, stream_id)
                sock.settimeout(35)
                return sock
            elif ev_type in ("StreamReset", "ConnectionTerminated"):
                raise RuntimeError("Connection rejected by server")


def parse_tail_event(data: bytes) -> list[tuple[int, str]]:
    """Parse a Cloudflare Workers tail JSON payload into (ts_ms, message) tuples."""
    try:
        ev = json.loads(data.decode("utf-8", errors="replace"))
    except Exception:
        return []

    events: list[tuple[int, str]] = []
    ev_ts   = ev.get("eventTimestamp") or int(time.time() * 1000)
    script  = ev.get("scriptName", "worker")
    outcome = ev.get("outcome", "ok")

    # One summary line per invocation (request URL + outcome)
    event_data = ev.get("event") or {}
    req = event_data.get("request") or {} if isinstance(event_data, dict) else {}
    if req:
        method = req.get("method", "?")
        url    = req.get("url", "")
        cf     = req.get("cf") or {}
        colo   = cf.get("colo", "")
        status = "" if outcome == "ok" else f" [{outcome.upper()}]"
        line   = f"[{script}] {method} {url}{status}"
        if colo:
            line += f"  ({colo})"
        events.append((ev_ts, line))

    # console.log / warn / error / debug output
    for log in ev.get("logs") or []:
        ts   = log.get("timestamp") or ev_ts
        lvl  = (log.get("level") or "log").upper()
        msgs = log.get("message", [])
        text = " ".join(str(m) for m in msgs) if isinstance(msgs, list) else str(msgs)
        prefix = f"[{lvl}] " if lvl not in ("LOG", "") else ""
        events.append((ts, prefix + text))

    # Uncaught exceptions
    for exc in ev.get("exceptions") or []:
        ts   = exc.get("timestamp") or ev_ts
        name = exc.get("name", "Error")
        msg  = exc.get("message", "")
        events.append((ts, f"[EXCEPTION] {name}: {msg}"))

    return events
