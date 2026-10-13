"""workers.py — QThread workers for all log sources in SimpleLog."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

from PyQt6.QtCore import QThread, pyqtSignal

import azure_utils
import changelog
import cloudflare_utils
import cloudwatch
import datadog_utils
import elastic_utils
import flyio_utils
import gcp_utils
import i18n
import kubernetes_utils
import loki_utils
import railway_utils
import vercel_utils
from worker_base import (
    HISTORY_CAP,
    Dedup,
    DockerStreamWorker,
    LogWorker,
    PollingWorker,
    ProcessStreamWorker,
    StreamWorker,
    clean_lines,
)

# ── Timestamp helpers ────────────────────────────────────────────────────────

def _parse_rfc3339_prefix(line: str, fallback_ms: int) -> tuple[int, str]:
    """Strip a leading RFC3339 timestamp from a log line.

    Returns (ts_ms, rest). Falls back to *fallback_ms* if the prefix can't
    be parsed. Used for docker/kubectl --timestamps output.
    """
    parts = line.split(" ", 1)
    if len(parts) == 2:
        try:
            dt = datetime.fromisoformat(parts[0].replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000), parts[1]
        except ValueError:
            pass
    return fallback_ms, line


def _parse_docker_ts(line: str) -> tuple[int, str]:
    """Docker variant: falls back to current time on parse failure."""
    return _parse_rfc3339_prefix(line, int(time.time() * 1000))


def _parse_k8s_line(line: str, fallback_ms: int) -> tuple[int, str]:
    """Kubernetes variant: falls back to caller-provided *fallback_ms*."""
    return _parse_rfc3339_prefix(line, fallback_ms)


def _ts_ms_to_iso(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"



def _read_last_n_lines(path: str, n: int) -> tuple[list[str], int]:
    """Read the last *n* lines of *path* without loading the whole file.

    Uses binary seeks so it's O(tail size), not O(file size).
    Returns *(lines, eof_byte_offset)* — the offset is used to resume tailing.
    """
    CHUNK = 1 << 16  # 64 KB per backwards step
    with open(path, "rb") as f:
        f.seek(0, 2)
        file_size = f.tell()
        if file_size == 0 or n == 0:
            return [], file_size

        # Newer chunks are collected as they are read and joined once at the end
        # (prepending to one growing buffer is quadratic on big tails).
        chunks: list[bytes] = []
        newlines = 0
        pos = file_size
        while pos > 0 and newlines <= n:
            step = min(CHUNK, pos)
            pos -= step
            f.seek(pos)
            chunk = f.read(step)
            chunks.append(chunk)
            newlines += chunk.count(b"\n")
        buf = b"".join(reversed(chunks))

    lines = buf.decode("utf-8", errors="replace").splitlines()
    result = lines[-n:] if len(lines) > n else lines
    return result, file_size


class TailWorker(PollingWorker):
    """Polls an AWS CloudWatch log group / stream."""

    _SRC = "CloudWatch"

    def __init__(self, client, log_group, log_stream, filter_pattern,
                 interval_s, lookback_s):
        super().__init__(interval_s)
        self._client         = client
        self._log_group      = log_group
        self._log_stream     = log_stream
        self._filter_pattern = filter_pattern
        self._lookback_s     = lookback_s
        self._dedup          = Dedup(window_ms=self._LATE_MS)
        self._ctx            = {"label": log_group}

    _LATE_MS = 5000   # CloudWatch ingests events a few seconds after their timestamp

    def _fetch_history(self):
        start_ms = int((time.time() - self._lookback_s) * 1000)
        events = cloudwatch.fetch_events(
            self._client, self._log_group, self._log_stream or None,
            start_ms=start_ms,
            filter_pattern=self._filter_pattern,
            max_events=None, keep_last=HISTORY_CAP,
        )
        self._last_ts = events[-1][0] if events else int(time.time() * 1000)
        return self._dedup.new(events)

    def _fetch_new(self):
        events = cloudwatch.fetch_events(
            self._client, self._log_group, self._log_stream or None,
            start_ms=self._last_ts - self._LATE_MS,
            filter_pattern=self._filter_pattern,
            max_events=5000,
        )
        new = self._dedup.new(events)
        if new:
            self._last_ts = max(self._last_ts, new[-1][0])
        return new


class FileWorker(LogWorker):
    _PARTIAL_LINE_MS = 1000   # show an unterminated last line after this much silence

    def __init__(self, path, tail_lines=100, interval_ms=200):
        super().__init__()
        self._path        = path
        self._tail_lines  = tail_lines
        self._interval_ms = interval_ms

    def _ends_with_newline(self, size: int) -> bool:
        with open(self._path, "rb") as f:
            f.seek(size - 1)
            return f.read(1) == b"\n"

    def _emit_lines(self, raw_lines: list[bytes]) -> None:
        """Decode each line on its own (so a multi-byte character is never split)."""
        now = int(time.time() * 1000)
        events = []
        for raw in raw_lines:
            line = raw.decode("utf-8", errors="replace").rstrip("\r")
            if line:
                events.append((now, line))
        self._emit(events)

    def _was_rotated(self, f, inode: int) -> bool:
        """True when the file was replaced (logrotate) or truncated since we opened it."""
        try:
            st = os.stat(self._path)
        except OSError:
            return False   # briefly missing while being rotated: keep waiting
        return st.st_ino != inode or st.st_size < f.tell()

    def run(self):
        try:
            self.status.emit(i18n.tr("msg_file_loading", path=self._path))
            lines, eof_pos = _read_last_n_lines(self._path, min(self._tail_lines, HISTORY_CAP))
            pending = b""
            if lines and eof_pos > 0 and not self._ends_with_newline(eof_pos):
                # The last line is still being written: show it once it is complete
                pending = lines.pop().encode("utf-8")
            if lines:
                self._emit_lines([line.encode("utf-8") for line in lines])
            self.status.emit(i18n.tr("msg_tailing", path=self._path))

            # Resume tailing from EOF — only new bytes are read from here on
            f = open(self._path, "rb")  # noqa: SIM115
            try:
                inode = os.fstat(f.fileno()).st_ino
                f.seek(eof_pos)
                idle_ms = 0
                while not self._stop:
                    if self._was_rotated(f, inode):
                        if pending:
                            self._emit_lines([pending])
                            pending = b""
                        f.close()
                        f = open(self._path, "rb")  # noqa: SIM115
                        inode = os.fstat(f.fileno()).st_ino
                        continue
                    raw = f.read(1 << 20)   # bounded: a huge append is shown in several steps
                    if raw:
                        idle_ms = 0
                        *complete, pending = (pending + raw).split(b"\n")
                        self._emit_lines(complete)
                        continue
                    idle_ms += self._interval_ms
                    if pending and idle_ms >= self._PARTIAL_LINE_MS:
                        self._emit_lines([pending])   # the writer never finished this line
                        pending = b""
                    self._wakeup.wait(self._interval_ms / 1000)
            finally:
                f.close()
        except OSError as e:
            self.error.emit(str(e))


class StdinWorker(StreamWorker):
    def run(self):
        self.status.emit(i18n.tr("msg_stdin_reading"))
        try:
            with contextlib.suppress(Exception):
                sys.stdin.reconfigure(errors="replace")
            self._pump(sys.stdin, clean_lines)
            if not self._stop:
                self.status.emit(i18n.tr("msg_stdin_closed"))
        except Exception as e:
            self.error.emit(str(e))


def _version_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except ValueError:
        return (0,)


class UpdateWorker(QThread):
    """Checks GitHub releases for a newer version."""
    update_available = pyqtSignal(str, str, str)  # (latest_tag, html_url, changelog_md)
    up_to_date       = pyqtSignal(str)       # (current_version)
    error            = pyqtSignal(str)

    _API = "https://api.github.com/repos/simple-log-app/simplelog/releases/latest"

    def __init__(self, current_version: str, locale: str = "en"):
        super().__init__()
        self._current = current_version
        self._locale = locale

    def _fetch_notes(self, tag: str) -> str:
        """Changes between the current version and *tag*; "" if unavailable."""
        for locale in dict.fromkeys((self._locale, "en")):
            try:
                req = urllib.request.Request(
                    changelog.raw_url(tag, locale),
                    headers={"User-Agent": f"SimpleLog/{self._current}"},
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    text = resp.read().decode("utf-8")
                return changelog.notes_between(text, self._current, tag)
            except Exception:
                continue
        return ""

    def run(self):
        try:
            req = urllib.request.Request(
                self._API,
                headers={"User-Agent": f"SimpleLog/{self._current}"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())
            latest = data.get("tag_name", "")
            if latest and _version_tuple(latest) > _version_tuple(self._current):
                self.update_available.emit(
                    latest, data.get("html_url", ""), self._fetch_notes(latest)
                )
            else:
                self.up_to_date.emit(self._current)
        except Exception as exc:
            self.error.emit(str(exc))


class DownloadWorker(QThread):
    """Downloads a file from a URL, emitting progress as it goes."""
    progress = pyqtSignal(int)   # 0-100
    finished = pyqtSignal(str)   # destination path
    error    = pyqtSignal(str)

    def __init__(self, url: str, dest: str, current_version: str):
        super().__init__()
        self._url = url
        self._dest = dest
        self._current = current_version

    def _expected_sha256(self) -> str | None:
        """The published SHA-256 of the asset, or None for releases without SHA256SUMS."""
        sums_url = self._url.rsplit("/", 1)[0] + "/SHA256SUMS"
        name = self._url.rsplit("/", 1)[1]
        req = urllib.request.Request(sums_url, headers={"User-Agent": f"SimpleLog/{self._current}"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        for line in text.splitlines():
            digest, _, entry = line.strip().partition(" ")
            if entry.strip().lstrip("*") == name:
                return digest.lower()
        raise OSError(i18n.tr("err_checksum_mismatch"))   # sums published, asset not in them

    def run(self):
        try:
            req = urllib.request.Request(
                self._url,
                headers={"User-Agent": f"SimpleLog/{self._current}"},
            )
            sha = hashlib.sha256()
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(self._dest, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        sha.update(chunk)
                        downloaded += len(chunk)
                        if total:
                            self.progress.emit(int(downloaded * 100 / total))
            if total and downloaded != total:
                raise OSError(i18n.tr("err_incomplete_download", done=downloaded, total=total))
            expected = self._expected_sha256()
            if expected is not None and expected != sha.hexdigest():
                raise OSError(i18n.tr("err_checksum_mismatch"))
            self.progress.emit(100)
            self.finished.emit(self._dest)
        except Exception as exc:
            with contextlib.suppress(OSError):
                os.unlink(self._dest)
            self.error.emit(str(exc))


class DebInstallWorker(QThread):
    """Installs a downloaded .deb through pkexec without freezing the UI."""
    done = pyqtSignal(int, str)   # (return code, error detail — "" on success)

    def __init__(self, deb_path: str) -> None:
        super().__init__()
        self._deb = deb_path

    def run(self) -> None:
        # No output capture: polkit has to show its authentication dialog
        import tempfile
        fd, log_path = tempfile.mkstemp(prefix="simplelog-update-", suffix=".log")
        detail = ""
        try:
            with os.fdopen(fd, "w") as log_f:
                result = subprocess.run(  # noqa: S603
                    ["pkexec", "dpkg", "-i", self._deb], stdout=log_f, stderr=log_f,
                )
            code = result.returncode
            if code != 0:
                try:
                    with open(log_path) as f:
                        detail = f.read(500)
                except OSError:
                    pass
                detail = detail or i18n.tr("err_exit_code", code=code)
        except OSError as e:
            code, detail = 1, str(e)
        with contextlib.suppress(OSError):
            os.unlink(self._deb)
        with contextlib.suppress(OSError):
            os.unlink(log_path)
        self.done.emit(code, detail)


# ── SSH worker ────────────────────────────────────────────────────────────────

def _lenient(lines):
    """Iterate *lines* without dying on a line that is not valid UTF-8 (shown as U+FFFD)."""
    it = iter(lines)
    while True:
        try:
            yield next(it)
        except StopIteration:
            return
        except UnicodeDecodeError:
            yield "\ufffd"


class SSHWorker(StreamWorker):
    def __init__(self, client, remote_path: str, tail_lines: int = 100) -> None:
        super().__init__()
        self._client      = client
        self._remote_path = remote_path
        self._tail_lines  = tail_lines
        self._channel     = None

    def stop(self) -> None:
        super().stop()
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass

    def run(self) -> None:
        self.status.emit(i18n.tr("msg_ssh_connecting", path=self._remote_path))
        try:
            cmd = (
                f"tail -n {min(self._tail_lines, HISTORY_CAP)} -f {shlex.quote(self._remote_path)}"
            )
            _, stdout, stderr = self._client.exec_command(cmd, get_pty=False)
            self._channel = stdout.channel
            self.status.emit(i18n.tr("msg_tailing", path=self._remote_path))
            self._pump(
                _lenient(stdout), lambda batch: clean_lines(batch, "\n\r"),
                is_stopped=lambda: self._stop or self._channel.closed,
            )
            if not self._stop:
                err = stderr.read().decode("utf-8", errors="replace").strip()
                if err:
                    self.error.emit(err)
                else:
                    self.status.emit(i18n.tr("msg_ssh_ended"))
        except Exception as e:
            if not self._stop:
                self.error.emit(str(e))
        finally:
            try:
                self._client.close()
            except Exception:
                pass


# ── Docker workers ────────────────────────────────────────────────────────────

class _DockerTimestampedWorker(DockerStreamWorker):
    """`docker ... logs --timestamps`: each line starts with the event time."""

    def _parse(self, batch):
        return [_parse_docker_ts(line) for line in (raw.rstrip() for raw in batch) if line]


class DockerContainerWorker(_DockerTimestampedWorker):
    _ENDED_STATUS = "msg_docker_ended"

    def __init__(self, container_id: str, lookback_s: float = 3600.0) -> None:
        super().__init__()
        self._container_id = container_id
        self._lookback_s   = lookback_s

    def _start_status(self) -> str:
        return i18n.tr("msg_docker_streaming", name=self._container_id[:12])

    def _command(self) -> list[str]:
        return ["docker", "logs", "-f", "--timestamps",
                f"--since={int(self._lookback_s)}s", self._container_id]

    def _exit_error(self, code: int) -> str:
        return i18n.tr("err_cmd_exit", cmd="docker logs", code=code)


class DockerComposeWorker(_DockerTimestampedWorker):
    _ENDED_STATUS = "msg_compose_ended"

    def __init__(self, project_name: str, lookback_s: float = 3600.0) -> None:
        super().__init__()
        self._project    = project_name
        self._lookback_s = lookback_s

    def _start_status(self) -> str:
        return i18n.tr("msg_compose_streaming", name=self._project)

    def _command(self) -> list[str]:
        return ["docker", "compose", "-p", self._project,
                "logs", "-f", "--timestamps", f"--since={int(self._lookback_s)}s"]

    def _exit_error(self, code: int) -> str:
        return i18n.tr("err_cmd_exit", cmd="docker compose logs", code=code)


class DockerExecFileWorker(DockerStreamWorker):
    _ENDED_STATUS = "msg_exec_ended"

    def __init__(self, container_id: str, remote_path: str, tail_lines: int = 100) -> None:
        super().__init__()
        self._container_id = container_id
        self._remote_path  = remote_path
        self._tail_lines   = tail_lines

    def _start_status(self) -> str:
        return i18n.tr("msg_exec_tailing", path=self._remote_path, name=self._container_id[:12])

    def _command(self) -> list[str]:
        return ["docker", "exec", self._container_id,
                "tail", f"-n{min(self._tail_lines, HISTORY_CAP)}", "-f", self._remote_path]

    def _exit_error(self, code: int) -> str:
        return i18n.tr("err_cmd_exit", cmd="docker exec", code=code)


# ── Kubernetes worker ─────────────────────────────────────────────────────────

class KubernetesWorker(ProcessStreamWorker):
    """Streams kubectl logs for a pod and emits new lines."""
    history_done = pyqtSignal(int)

    _MERGE_STDERR = False   # kubectl's error text is shown if it fails

    def __init__(self, pod: str, namespace: str, context: str = "",
                 container: str = "", lookback_s: float = 3600.0) -> None:
        super().__init__()
        self._pod       = pod
        self._namespace = namespace
        self._context   = context
        self._container = container
        self._lookback_s = lookback_s
        self._label     = f"{namespace}/{pod}"
        self._first     = True
        self._now_ms    = 0

    def _start_status(self) -> str:
        return i18n.tr("msg_k8s_starting", name=self._label)

    def _command(self) -> list[str]:
        self._now_ms = int(time.time() * 1000)
        return kubernetes_utils.build_logs_cmd(
            self._pod, self._namespace, self._context, self._container,
            since_s=int(self._lookback_s),
        )

    def _parse(self, batch):
        return [_parse_k8s_line(raw.rstrip("\n"), self._now_ms) for raw in batch]

    def _deliver(self, events) -> None:
        self._emit(events)
        if self._first:
            self._first = False
            self.history_done.emit(len(events))
            self.status.emit(i18n.tr("msg_k8s_streaming", name=self._label))

    def _finish(self) -> None:
        if self._proc.poll() != 0 and not self._stop:  # type: ignore[union-attr]
            err = self._stderr_output().strip()
            if err:
                self.error.emit(err)


# ── Vercel worker ─────────────────────────────────────────────────────────────

class VercelWorker(PollingWorker):
    """Polls Vercel deployment events and emits new log lines."""

    _SRC = "Vercel"

    def __init__(self, token: str, project_id: str, project_name: str,
                 deployment_id: str, interval_s: float = 3.0,
                 lookback_s: float = 3600.0) -> None:
        super().__init__(interval_s)
        self._token         = token
        self._project_id    = project_id
        self._deployment_id = deployment_id
        self._lookback_s    = lookback_s
        self._ctx           = {"label": project_name}

    def _fetch_history(self):
        since_ms = int(time.time() * 1000) - int(self._lookback_s * 1000)
        events = vercel_utils.fetch_deployment_events(
            self._token, self._deployment_id, since_ms=since_ms,
        )
        self._last_ts = events[-1][0] + 1 if events else int(time.time() * 1000)
        return events

    def _fetch_new(self):
        events = vercel_utils.fetch_deployment_events(
            self._token, self._deployment_id, since_ms=self._last_ts
        )
        if events:
            self._last_ts = events[-1][0] + 1
        return events

# ── GCP Cloud Logging worker ──────────────────────────────────────────────────

class GCPWorker(PollingWorker):
    """Polls Google Cloud Logging and emits new log entries."""

    _SRC = "GCP"

    def __init__(self, client, project_id: str, resource_type: str,
                 severity: str, custom_filter: str,
                 lookback_s: float = 3600.0, interval_s: float = 5.0) -> None:
        super().__init__(interval_s)
        self._client        = client
        self._project_id    = project_id
        self._resource_type = resource_type
        self._severity      = severity
        self._custom        = custom_filter
        self._lookback_h    = lookback_s / 3600
        self._dedup         = Dedup(window_ms=1000)   # filter is truncated to the second
        self._ctx           = {"label": project_id}

    def _make_filter(self, since: datetime | None) -> str:
        return gcp_utils.build_filter(
            resource_type=self._resource_type,
            severity=self._severity,
            custom=self._custom,
            since=since,
        )

    def _fetch_history(self):
        since = datetime.now(UTC) - timedelta(hours=self._lookback_h)
        events = self._dedup.new(
            gcp_utils.fetch_entries(self._client, self._make_filter(since))
        )
        self._last_ts = (
            datetime.fromtimestamp(events[-1][0] / 1000, tz=UTC) if events
            else datetime.now(UTC)
        )
        return events

    def _fetch_new(self):
        # Oldest first: a burst larger than one page is drained over several polls
        # instead of silently skipping its oldest entries.
        events = self._dedup.new(gcp_utils.fetch_entries(
            self._client,
            self._make_filter(self._last_ts),
            max_results=500,
            ascending=True,
        ))
        if events:
            self._last_ts = datetime.fromtimestamp(events[-1][0] / 1000, tz=UTC)
        return events

# ── Azure Monitor worker ──────────────────────────────────────────────────────

class AzureWorker(PollingWorker):
    """Polls Azure Monitor Log Analytics and emits new log rows."""

    _SRC = "Azure"
    _LATE_MS = 60_000   # Log Analytics ingests rows up to a minute after their TimeGenerated

    def __init__(self, logs_client, workspace_id: str, query: str,
                 label: str = "", lookback_s: float = 3600.0,
                 interval_s: float = 10.0) -> None:
        super().__init__(interval_s)
        self._client       = logs_client
        self._workspace_id = workspace_id
        self._query        = query
        self._label        = label or workspace_id[:8]
        self._timespan_h   = lookback_s / 3600
        self._dedup        = Dedup(window_ms=self._LATE_MS)
        self._ctx          = {"label": self._label}

    def _fetch_history(self):
        events = self._dedup.new(azure_utils.fetch_logs(
            self._client, self._workspace_id, self._query, self._timespan_h,
        ))
        self._last_dt = (
            datetime.fromtimestamp(events[-1][0] / 1000, tz=UTC) if events
            else datetime.now(UTC)
        )
        return events

    def _fetch_new(self):
        events = self._dedup.new(azure_utils.fetch_logs_since(
            self._client, self._workspace_id, self._query,
            self._last_dt - timedelta(milliseconds=self._LATE_MS),
        ))
        if events:
            self._last_dt = datetime.fromtimestamp(events[-1][0] / 1000, tz=UTC)
        return events

# ── Grafana Loki worker ───────────────────────────────────────────────────────

class LokiWorker(PollingWorker):
    """Polls Grafana Loki via query_range and emits new log entries."""

    _SRC = "Loki"

    def __init__(self, url: str, query: str,
                 username: str = "", password: str = "", token: str = "",
                 lookback_s: float = 3600.0, interval_s: float = 5.0) -> None:
        super().__init__(interval_s)
        self._url        = url
        self._query      = query
        self._username   = username
        self._password   = password
        self._token      = token
        self._lookback_h = lookback_s / 3600
        self._dedup      = Dedup()
        self._ctx        = {"label": url.split("//", 1)[-1].split("/")[0]}

    def _fetch_history(self):
        now_ns   = int(time.time() * 1e9)
        start_ns = int((time.time() - self._lookback_h * 3600) * 1e9)
        events = self._dedup.new(loki_utils.fetch_logs(
            self._url, self._query, start_ns, now_ns,
            self._username, self._password, self._token,
            latest=True,
        ))
        self._last_ns = events[-1][0] * 1_000_000 if events else now_ns
        return events

    def _fetch_new(self):
        end_ns = int(time.time() * 1e9)
        # _last_ns is inclusive (ms precision): the dedup drops the repeats
        events = self._dedup.new(loki_utils.fetch_logs(
            self._url, self._query, self._last_ns, end_ns,
            self._username, self._password, self._token,
            limit=200,
        ))
        if events:
            self._last_ns = events[-1][0] * 1_000_000
        return events

# ── Datadog Logs worker ───────────────────────────────────────────────────────

class DatadogWorker(PollingWorker):
    """Polls Datadog Logs Search API v2 and emits new log entries."""

    _SRC = "Datadog"

    def __init__(self, base_url: str, query: str, api_key: str, app_key: str,
                 lookback_s: float = 3600.0, interval_s: float = 10.0) -> None:
        super().__init__(interval_s)
        self._base_url    = base_url
        self._query       = query
        self._api_key     = api_key
        self._app_key     = app_key
        self._lookback_h  = lookback_s / 3600
        self._dedup       = Dedup()
        self._ctx         = {"label": base_url.split("//", 1)[-1]}

    def _fetch_history(self):
        from_iso = datadog_utils.offset_iso(self._lookback_h)
        to_iso   = datadog_utils.now_iso()
        events = self._dedup.new(datadog_utils.fetch_logs(
            self._base_url, self._query, from_iso, to_iso,
            self._api_key, self._app_key, latest=True,
        ))
        self._last_iso = _ts_ms_to_iso(events[-1][0]) if events else to_iso
        return events

    def _fetch_new(self):
        to_iso = datadog_utils.now_iso()
        # _last_iso is inclusive: the dedup drops the entry already shown
        events = self._dedup.new(datadog_utils.fetch_logs(
            self._base_url, self._query, self._last_iso, to_iso,
            self._api_key, self._app_key, limit=200,
        ))
        if events:
            self._last_iso = _ts_ms_to_iso(events[-1][0])
        return events

# ── Elasticsearch / OpenSearch worker ────────────────────────────────────────

class ElasticWorker(PollingWorker):
    """Polls Elasticsearch / OpenSearch _search API and emits new log entries."""

    _SRC = "Elastic"

    def __init__(self, url: str, index: str, query: str,
                 api_key: str = "", username: str = "", password: str = "",
                 ts_field: str = "@timestamp",
                 lookback_s: float = 3600.0, interval_s: float = 10.0) -> None:
        super().__init__(interval_s)
        self._url         = url
        self._index       = index
        self._query       = query
        self._api_key     = api_key
        self._username    = username
        self._password    = password
        self._ts_field    = ts_field
        self._lookback_h  = lookback_s / 3600
        self._dedup       = Dedup()
        self._ctx         = {"label": f"{url.split('//', 1)[-1].split('/')[0]}/{index}"}

    def _search(self, **kwargs) -> list:
        events, _ = elastic_utils.fetch_logs(
            self._url, self._index, self._query,
            api_key=self._api_key, username=self._username, password=self._password,
            ts_field=self._ts_field, **kwargs,
        )
        return self._dedup.new(events)

    def _fetch_history(self):
        since = datetime.now(UTC) - timedelta(hours=self._lookback_h)
        since_iso = since.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        events = self._search(since_iso=since_iso, latest=True)
        self._last_iso = _ts_ms_to_iso(events[-1][0]) if events else since_iso
        return events

    def _fetch_new(self):
        # Inclusive start (timestamps are compared at millisecond precision): the
        # entries already shown come back and are dropped by the dedup.
        events = self._search(since_iso=self._last_iso, inclusive=True, size=200)
        if events:
            self._last_iso = _ts_ms_to_iso(events[-1][0])
        return events

# ── Railway worker ────────────────────────────────────────────────────────────

class RailwayWorker(PollingWorker):
    """Polls Railway deployment logs and emits new entries."""

    _SRC = "Railway"

    def __init__(self, token: str, project_name: str, service_name: str,
                 service_id: str, interval_s: float = 10.0,
                 lookback_s: float = 3600.0) -> None:
        super().__init__(interval_s)
        self._token        = token
        self._service_id   = service_id
        self._lookback_s   = lookback_s
        self._ctx          = {"label": f"{project_name}/{service_name}"}

    def _fetch_history(self):
        since_ts_ms = int(time.time() * 1000) - int(self._lookback_s * 1000)
        deploy = railway_utils.get_latest_deployment(self._token, self._service_id)
        if not deploy:
            raise RuntimeError(i18n.tr("err_no_deployment", label=self._ctx["label"]))
        self._deploy_id = deploy["id"]
        all_events = railway_utils.fetch_deployment_logs(self._token, self._deploy_id)
        self._dedup = Dedup(window_ms=60_000)
        return self._dedup.new([(ts, m) for ts, m in all_events if ts >= since_ts_ms])

    def _fetch_new(self):
        # Check if a new deployment was created
        deploy = railway_utils.get_latest_deployment(self._token, self._service_id)
        if deploy and deploy["id"] != self._deploy_id:
            self._deploy_id = deploy["id"]
            self._dedup = Dedup(window_ms=60_000)
        newest = self._dedup.newest
        since = None if newest is None else max(newest - 60_000, 0)
        return self._dedup.new(
            railway_utils.fetch_deployment_logs(self._token, self._deploy_id, since))

# ── Fly.io worker ─────────────────────────────────────────────────────────────

class FlyioWorker(PollingWorker):
    """Polls Fly.io SSE log stream and emits new log entries."""

    _SRC = "Fly.io"

    def __init__(self, token: str, app_name: str, interval_s: float = 5.0,
                 lookback_s: float = 3600.0) -> None:
        super().__init__(interval_s)
        self._token       = token
        self._app_name    = app_name
        self._lookback_s  = lookback_s
        self._dedup       = Dedup(window_ms=60_000)
        self._ctx         = {"label": app_name}

    def _fetch_history(self):
        since_ts_ms = int(time.time() * 1000) - int(self._lookback_s * 1000)
        events = self._dedup.new(
            flyio_utils.fetch_logs_sse(self._token, self._app_name, limit=300)
        )
        return [(ts, m) for ts, m in events if ts >= since_ts_ms]

    def _fetch_new(self):
        return self._dedup.new(
            flyio_utils.fetch_logs_sse(self._token, self._app_name, limit=100)
        )

# ── Cloudflare Workers tail worker ────────────────────────────────────────────

class CloudflareWorker(LogWorker):
    """Streams Cloudflare Workers tail events over the tail WebSocket."""
    history_done = pyqtSignal(int)

    def __init__(self, api_token: str, account_id: str, script_name: str) -> None:
        super().__init__()
        self._api_token   = api_token
        self._account_id  = account_id
        self._script_name = script_name
        self._proc        = None
        self._sock        = None

    def stop(self) -> None:
        super().stop()
        if self._proc and self._proc.poll() is None:
            with contextlib.suppress(Exception):
                self._proc.terminate()
        if self._sock is not None:
            with contextlib.suppress(Exception):
                self._sock.close()

    def run(self) -> None:
        label = self._script_name
        self.status.emit(i18n.tr("msg_cf_connecting", name=label))

        try:
            tail = cloudflare_utils.create_tail(
                self._api_token, self._account_id, self._script_name
            )
        except RuntimeError as e:
            self.error.emit(str(e))
            return

        ws_url  = tail["url"]
        tail_id = tail["id"]

        try:
            self._sock = cloudflare_utils.ws_connect(ws_url, self._api_token)
        except Exception as e:
            cloudflare_utils.delete_tail(
                self._api_token, self._account_id, self._script_name, tail_id
            )
            self.error.emit(str(e))
            return

        # Send init message unmasked — wrangler uses {mask: false, binary: false}
        init = json.dumps({"debug": False}).encode()

        try:
            cloudflare_utils.ws_send_frame_unmasked(self._sock, 1, init)
            self.history_done.emit(0)
            self.status.emit(i18n.tr("msg_cf_waiting", name=label))
            while not self._stop:
                try:
                    opcode, payload = cloudflare_utils.ws_recv_frame(self._sock)
                except TimeoutError:
                    continue  # no data yet, keep waiting
                if opcode == 8:   # close
                    break
                if opcode == 9:   # ping → respond with pong
                    cloudflare_utils.ws_send_frame(self._sock, 10, payload)
                elif opcode in (1, 2):  # text or binary
                    events = cloudflare_utils.parse_tail_event(payload)
                    if events:
                        self.new_lines.emit(events)
                        self.status.emit(i18n.tr("msg_cf_live", name=label))
        except (EOFError, OSError):
            pass
        except Exception as e:
            if not self._stop:
                self.error.emit(str(e))
        finally:
            cloudflare_utils.ws_close(self._sock)
            cloudflare_utils.delete_tail(
                self._api_token, self._account_id, self._script_name, tail_id
            )
