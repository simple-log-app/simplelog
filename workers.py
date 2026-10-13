"""workers.py — QThread workers for all log sources in SimpleLog."""
from __future__ import annotations

import contextlib
import json
import os
import queue
import shlex
import subprocess
import sys
import threading
import time
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
import kubernetes_utils
import loki_utils
import railway_utils
import vercel_utils

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
    CHUNK = 1 << 14  # 16 KB per backwards step
    with open(path, "rb") as f:
        f.seek(0, 2)
        file_size = f.tell()
        if file_size == 0 or n == 0:
            return [], file_size

        buf = b""
        pos = file_size
        while pos > 0 and buf.count(b"\n") <= n:
            step = min(CHUNK, pos)
            pos -= step
            f.seek(pos)
            buf = f.read(step) + buf

    lines = buf.decode("utf-8", errors="replace").splitlines()
    result = lines[-n:] if len(lines) > n else lines
    return result, file_size


def _batched(lines, is_stopped, max_batch: int = 200, max_wait: float = 0.1):
    """Group a blocking line iterator into lists, flushing every *max_wait* seconds.

    Lets a worker show the first lines of a slow stream right away instead of waiting
    for a full batch or for the stream to end. Stops when the iterator is exhausted
    or *is_stopped()* turns true.
    """
    q: queue.Queue = queue.Queue()
    end = object()

    def _reader() -> None:
        try:
            for item in lines:
                q.put(item)
        except Exception:
            pass   # the source was closed under us (stop requested)
        finally:
            q.put(end)

    threading.Thread(target=_reader, daemon=True).start()
    batch: list = []
    started = 0.0
    while True:
        try:
            item = q.get(timeout=max_wait if batch else 0.2)
        except queue.Empty:
            if batch:
                yield batch
                batch = []
            if is_stopped():
                return
            continue
        if item is end:
            if batch:
                yield batch
            return
        if not batch:
            started = time.monotonic()
        batch.append(item)
        if len(batch) >= max_batch or time.monotonic() - started >= max_wait:
            yield batch
            batch = []


class _Dedup:
    """Drops events already delivered when a poll re-reads a window it overlaps.

    Pollers restart slightly before the last event (timestamps are truncated to the
    millisecond or second by the APIs), so the same entries come back. *window_ms* is
    the precision loss to absorb; events older than ``newest - window_ms`` are assumed
    already delivered.
    """

    def __init__(self, window_ms: int = 0) -> None:
        self._window = window_ms
        self._newest: int | None = None
        self._seen: set[tuple[int, str]] = set()

    def new(self, events: list[tuple[int, str]]) -> list[tuple[int, str]]:
        if self._newest is not None:
            floor = self._newest - self._window
            events = [e for e in events if e[0] >= floor and e not in self._seen]
        else:
            events = list(events)
        if events:
            self._seen.update(events)
            self._newest = max(e[0] for e in events + ([(self._newest, "")] if self._newest else []))
            floor = self._newest - self._window
            self._seen = {e for e in self._seen if e[0] >= floor}
        return events


class _PollWorker(QThread):
    """Base for workers that poll an API: tolerates transient failures.

    A failed poll is reported in the status bar and retried; only after
    ``_MAX_FAILS`` consecutive failures is an error raised (which stops the tail).
    """

    _MAX_FAILS = 5

    def __init__(self) -> None:
        super().__init__()
        self._stop = False
        self._fails = 0
        self._wakeup = threading.Event()

    def stop(self) -> None:
        self._stop = True
        self._wakeup.set()   # cut the current sleep short

    def _sleep(self) -> None:
        """Wait for the poll interval, returning early if stop() is called."""
        self._wakeup.wait(self._interval_ms / 1000)   # type: ignore[attr-defined]

    def _poll_ok(self) -> None:
        self._fails = 0

    def _poll_failed(self, exc: Exception) -> bool:
        """Record a failed poll. Returns True when the worker should give up."""
        self._fails += 1
        if self._fails >= self._MAX_FAILS:
            self.error.emit(str(exc))  # type: ignore[attr-defined]
            return True
        self.status.emit(  # type: ignore[attr-defined]
            f"Connection problem ({self._fails}/{self._MAX_FAILS}), retrying… {exc}"
        )
        return False


class TailWorker(_PollWorker):
    new_lines    = pyqtSignal(list)  # [(ts_ms, message), ...]
    error        = pyqtSignal(str)
    status       = pyqtSignal(str)
    history_done = pyqtSignal(int)

    def __init__(self, client, log_group, log_stream, filter_pattern,
                 interval_s, lookback_s):
        super().__init__()
        self._client         = client
        self._log_group      = log_group
        self._log_stream     = log_stream
        self._filter_pattern = filter_pattern
        self._interval_ms    = int(interval_s * 1000)
        self._lookback_s     = lookback_s

    def run(self):
        start_ms = int((time.time() - self._lookback_s) * 1000)
        self.status.emit("Loading history…")
        try:
            events = cloudwatch.fetch_events(
                self._client, self._log_group, self._log_stream or None,
                start_ms=start_ms,
                filter_pattern=self._filter_pattern,
                max_events=None,
            )
            self._last_ts = events[-1][0] + 1 if events else int(time.time() * 1000)
            if events:
                self.new_lines.emit(events)
            self.history_done.emit(len(events))
        except RuntimeError as e:
            self.error.emit(str(e))
            return

        while not self._stop:
            self._sleep()
            if self._stop:
                break
            try:
                events = cloudwatch.fetch_events(
                    self._client, self._log_group, self._log_stream or None,
                    start_ms=self._last_ts,
                    filter_pattern=self._filter_pattern,
                    max_events=500,
                )
                if events:
                    self._last_ts = events[-1][0] + 1
                    self.new_lines.emit(events)
                    self.status.emit(f"Updated  —  {len(events)} new events")
                else:
                    self.status.emit("Tailing…  no new events")
                self._poll_ok()
            except RuntimeError as e:
                if self._poll_failed(e):
                    return


class FileWorker(QThread):
    new_lines = pyqtSignal(list)  # [(ts_ms, message), ...]
    status    = pyqtSignal(str)
    error     = pyqtSignal(str)

    _PARTIAL_LINE_MS = 1000   # show an unterminated last line after this much silence

    def __init__(self, path, tail_lines=100, interval_ms=200):
        super().__init__()
        self._path        = path
        self._tail_lines  = tail_lines
        self._interval_ms = interval_ms
        self._stop        = False

    def stop(self):
        self._stop = True

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
        if events:
            self.new_lines.emit(events)

    def _was_rotated(self, f, inode: int) -> bool:
        """True when the file was replaced (logrotate) or truncated since we opened it."""
        try:
            st = os.stat(self._path)
        except OSError:
            return False   # briefly missing while being rotated: keep waiting
        return st.st_ino != inode or st.st_size < f.tell()

    def run(self):
        try:
            self.status.emit(f"Loading {self._path}…")
            lines, eof_pos = _read_last_n_lines(self._path, self._tail_lines)
            pending = b""
            if lines and eof_pos > 0 and not self._ends_with_newline(eof_pos):
                # The last line is still being written: show it once it is complete
                pending = lines.pop().encode("utf-8")
            if lines:
                self._emit_lines([line.encode("utf-8") for line in lines])
            self.status.emit(f"Tailing {self._path}")

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
                    raw = f.read()
                    if raw:
                        idle_ms = 0
                        *complete, pending = (pending + raw).split(b"\n")
                        self._emit_lines(complete)
                        continue
                    idle_ms += self._interval_ms
                    if pending and idle_ms >= self._PARTIAL_LINE_MS:
                        self._emit_lines([pending])   # the writer never finished this line
                        pending = b""
                    self.msleep(self._interval_ms)
            finally:
                f.close()
        except OSError as e:
            self.error.emit(str(e))


class StdinWorker(QThread):
    new_lines = pyqtSignal(list)  # [(ts_ms, message), ...]
    status    = pyqtSignal(str)
    error     = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        self.status.emit("Reading stdin…")
        try:
            for batch in _batched(sys.stdin, lambda: self._stop):
                if self._stop:
                    break
                ts = int(time.time() * 1000)
                events = [(ts, line) for line in (r.rstrip() for r in batch) if line]
                if events:
                    self.new_lines.emit(events)
            if not self._stop:
                self.status.emit("stdin — stream closed")
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

    def run(self):
        try:
            req = urllib.request.Request(
                self._url,
                headers={"User-Agent": f"SimpleLog/{self._current}"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(self._dest, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            self.progress.emit(int(downloaded * 100 / total))
            if total and downloaded != total:
                raise OSError(f"Incomplete download ({downloaded} of {total} bytes)")
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
        log_path = os.path.join(tempfile.gettempdir(), "simplelog-update.log")
        detail = ""
        try:
            with open(log_path, "w") as log_f:
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
                detail = detail or f"exit code {code}"
        except OSError as e:
            code, detail = 1, str(e)
        with contextlib.suppress(OSError):
            os.unlink(self._deb)
        self.done.emit(code, detail)


# ── SSH worker ────────────────────────────────────────────────────────────────

class SSHWorker(QThread):
    new_lines = pyqtSignal(list)   # [(ts_ms, message), ...]
    status    = pyqtSignal(str)
    error     = pyqtSignal(str)

    def __init__(self, client, remote_path: str, tail_lines: int = 100) -> None:
        super().__init__()
        self._client      = client
        self._remote_path = remote_path
        self._tail_lines  = tail_lines
        self._stop        = False
        self._channel     = None

    def stop(self) -> None:
        self._stop = True
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass

    def run(self) -> None:
        self.status.emit(f"Connecting to {self._remote_path}…")
        try:
            cmd = f"tail -n {self._tail_lines} -f {shlex.quote(self._remote_path)}"
            _, stdout, stderr = self._client.exec_command(cmd, get_pty=False)
            self._channel = stdout.channel
            self.status.emit(f"Tailing {self._remote_path}")
            for batch in _batched(stdout, lambda: self._stop or self._channel.closed):
                if self._stop or self._channel.closed:
                    break
                ts = int(time.time() * 1000)
                events = [(ts, line) for line in (r.rstrip("\n\r") for r in batch) if line]
                if events:
                    self.new_lines.emit(events)
            if not self._stop:
                err = stderr.read().decode("utf-8", errors="replace").strip()
                if err:
                    self.error.emit(err)
                else:
                    self.status.emit("SSH stream ended")
        except Exception as e:
            if not self._stop:
                self.error.emit(str(e))
        finally:
            try:
                self._client.close()
            except Exception:
                pass


# ── Docker container worker ───────────────────────────────────────────────────

class DockerContainerWorker(QThread):
    new_lines = pyqtSignal(list)
    status    = pyqtSignal(str)
    error     = pyqtSignal(str)

    def __init__(self, container_id: str, lookback_s: float = 3600.0) -> None:
        super().__init__()
        self._container_id = container_id
        self._lookback_s   = lookback_s
        self._stop         = False
        self._proc         = None

    def stop(self) -> None:
        self._stop = True
        if self._proc:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def run(self) -> None:
        short = self._container_id[:12]
        self.status.emit(f"Streaming docker logs for {short}…")
        try:
            self._proc = subprocess.Popen(
                ["docker", "logs", "-f", "--timestamps",
                 f"--since={int(self._lookback_s)}s", self._container_id],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            for batch in _batched(self._proc.stdout, lambda: self._stop):
                if self._stop:
                    break
                events = [_parse_docker_ts(line) for line in (r.rstrip() for r in batch) if line]
                if events:
                    self.new_lines.emit(events)
            self._proc.wait()
            if not self._stop and self._proc.returncode not in (0, -15):
                self.error.emit(f"docker logs exited with code {self._proc.returncode}")
            elif not self._stop:
                self.status.emit("Docker log stream ended")
        except Exception as e:
            if not self._stop:
                self.error.emit(str(e))


# ── Docker Compose worker ─────────────────────────────────────────────────────

class DockerComposeWorker(QThread):
    new_lines = pyqtSignal(list)
    status    = pyqtSignal(str)
    error     = pyqtSignal(str)

    def __init__(self, project_name: str, lookback_s: float = 3600.0) -> None:
        super().__init__()
        self._project    = project_name
        self._lookback_s = lookback_s
        self._stop       = False
        self._proc       = None

    def stop(self) -> None:
        self._stop = True
        if self._proc:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def run(self) -> None:
        self.status.emit(f"Streaming compose stack {self._project}…")
        try:
            self._proc = subprocess.Popen(
                ["docker", "compose", "-p", self._project,
                 "logs", "-f", "--timestamps", f"--since={int(self._lookback_s)}s"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            for batch in _batched(self._proc.stdout, lambda: self._stop):
                if self._stop:
                    break
                events = [_parse_docker_ts(line) for line in (r.rstrip() for r in batch) if line]
                if events:
                    self.new_lines.emit(events)
            self._proc.wait()
            if not self._stop and self._proc.returncode not in (0, -15):
                self.error.emit(f"docker compose logs exited {self._proc.returncode}")
            elif not self._stop:
                self.status.emit("Compose log stream ended")
        except Exception as e:
            if not self._stop:
                self.error.emit(str(e))


# ── Docker exec file worker ───────────────────────────────────────────────────

class DockerExecFileWorker(QThread):
    new_lines = pyqtSignal(list)
    status    = pyqtSignal(str)
    error     = pyqtSignal(str)

    def __init__(self, container_id: str, remote_path: str, tail_lines: int = 100) -> None:
        super().__init__()
        self._container_id = container_id
        self._remote_path  = remote_path
        self._tail_lines   = tail_lines
        self._stop         = False
        self._proc         = None

    def stop(self) -> None:
        self._stop = True
        if self._proc:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def run(self) -> None:
        short = self._container_id[:12]
        self.status.emit(f"Tailing {self._remote_path} in {short}…")
        try:
            self._proc = subprocess.Popen(
                ["docker", "exec", self._container_id,
                 "tail", f"-n{self._tail_lines}", "-f", self._remote_path],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            for batch in _batched(self._proc.stdout, lambda: self._stop):
                if self._stop:
                    break
                ts = int(time.time() * 1000)
                events = [(ts, line) for line in (r.rstrip() for r in batch) if line]
                if events:
                    self.new_lines.emit(events)
            self._proc.wait()
            if not self._stop and self._proc.returncode not in (0, -15):
                self.error.emit(f"docker exec exited with code {self._proc.returncode}")
            elif not self._stop:
                self.status.emit("Container file stream ended")
        except Exception as e:
            if not self._stop:
                self.error.emit(str(e))


# ── Vercel worker ─────────────────────────────────────────────────────────────

class VercelWorker(_PollWorker):
    """Polls Vercel deployment events and emits new log lines."""
    new_lines    = pyqtSignal(list)  # [(ts_ms, message), ...]
    status       = pyqtSignal(str)
    error        = pyqtSignal(str)
    history_done = pyqtSignal(int)

    def __init__(self, token: str, project_id: str, project_name: str,
                 deployment_id: str, interval_s: float = 3.0,
                 lookback_s: float = 3600.0) -> None:
        super().__init__()
        self._token         = token
        self._project_id    = project_id
        self._project_name  = project_name
        self._deployment_id = deployment_id
        self._interval_ms   = int(interval_s * 1000)
        self._lookback_s    = lookback_s

    def run(self) -> None:
        self.status.emit(f"Loading logs for {self._project_name}…")
        since_ms = int(time.time() * 1000) - int(self._lookback_s * 1000)
        try:
            events = vercel_utils.fetch_deployment_events(
                self._token, self._deployment_id, since_ms=since_ms,
            )
            self._last_ts = events[-1][0] + 1 if events else int(time.time() * 1000)
            if events:
                self.new_lines.emit(events)
            self.history_done.emit(len(events))
            self.status.emit(f"Tailing {self._project_name} — {len(events)} events loaded")
        except RuntimeError as e:
            self.error.emit(str(e))
            return

        while not self._stop:
            self._sleep()
            if self._stop:
                break
            try:
                events = vercel_utils.fetch_deployment_events(
                    self._token, self._deployment_id, since_ms=self._last_ts
                )
                if events:
                    self._last_ts = events[-1][0] + 1
                    self.new_lines.emit(events)
                    self.status.emit(f"{self._project_name} — {len(events)} new events")
                else:
                    self.status.emit(f"Tailing {self._project_name}…")
                self._poll_ok()
            except RuntimeError as e:
                if self._poll_failed(e):
                    return


# ── GCP Cloud Logging worker ──────────────────────────────────────────────────

class GCPWorker(_PollWorker):
    """Polls Google Cloud Logging and emits new log entries."""
    new_lines    = pyqtSignal(list)  # [(ts_ms, message), ...]
    status       = pyqtSignal(str)
    error        = pyqtSignal(str)
    history_done = pyqtSignal(int)

    def __init__(self, client, project_id: str, resource_type: str,
                 severity: str, custom_filter: str,
                 lookback_s: float = 3600.0, interval_s: float = 5.0) -> None:
        super().__init__()
        self._client        = client
        self._project_id    = project_id
        self._resource_type = resource_type
        self._severity      = severity
        self._custom        = custom_filter
        self._lookback_h    = lookback_s / 3600
        self._interval_ms   = int(interval_s * 1000)
        self._dedup         = _Dedup(window_ms=1000)   # filter is truncated to the second

    def _make_filter(self, since: datetime | None) -> str:
        return gcp_utils.build_filter(
            resource_type=self._resource_type,
            severity=self._severity,
            custom=self._custom,
            since=since,
        )

    def run(self) -> None:
        self.status.emit(f"Loading GCP logs for {self._project_id}…")
        since = datetime.now(UTC) - timedelta(hours=self._lookback_h)
        try:
            events = self._dedup.new(
                gcp_utils.fetch_entries(self._client, self._make_filter(since))
            )
            self._last_ts = (
                datetime.fromtimestamp(events[-1][0] / 1000, tz=UTC)
                if events else datetime.now(UTC)
            )
            if events:
                self.new_lines.emit(events)
            self.history_done.emit(len(events))
            self.status.emit(f"GCP {self._project_id} — {len(events)} entries loaded")
        except RuntimeError as e:
            self.error.emit(str(e))
            return

        while not self._stop:
            self._sleep()
            if self._stop:
                break
            try:
                # Oldest first: a burst larger than one page is drained over several
                # polls instead of silently skipping its oldest entries.
                events = self._dedup.new(gcp_utils.fetch_entries(
                    self._client,
                    self._make_filter(self._last_ts),
                    max_results=500,
                    ascending=True,
                ))
                if events:
                    self._last_ts = datetime.fromtimestamp(events[-1][0] / 1000, tz=UTC)
                    self.new_lines.emit(events)
                    self.status.emit(f"GCP {self._project_id} — {len(events)} new entries")
                else:
                    self.status.emit(f"GCP {self._project_id} — tailing…")
                self._poll_ok()
            except RuntimeError as e:
                if self._poll_failed(e):
                    return


# ── Azure Monitor worker ──────────────────────────────────────────────────────

class AzureWorker(_PollWorker):
    """Polls Azure Monitor Log Analytics and emits new log rows."""
    new_lines    = pyqtSignal(list)  # [(ts_ms, message), ...]
    status       = pyqtSignal(str)
    error        = pyqtSignal(str)
    history_done = pyqtSignal(int)

    def __init__(self, logs_client, workspace_id: str, query: str,
                 label: str = "", lookback_s: float = 3600.0,
                 interval_s: float = 10.0) -> None:
        super().__init__()
        self._client       = logs_client
        self._workspace_id = workspace_id
        self._query        = query
        self._label        = label or workspace_id[:8]
        self._timespan_h   = lookback_s / 3600
        self._interval_ms  = int(interval_s * 1000)
        self._dedup        = _Dedup()

    def run(self) -> None:
        self.status.emit(f"Loading Azure logs — {self._label}…")
        try:
            events = self._dedup.new(azure_utils.fetch_logs(
                self._client, self._workspace_id,
                self._query, self._timespan_h,
            ))
            self._last_dt = (
                datetime.fromtimestamp(events[-1][0] / 1000, tz=UTC)
                if events else datetime.now(UTC)
            )
            if events:
                self.new_lines.emit(events)
            self.history_done.emit(len(events))
            self.status.emit(f"Azure {self._label} — {len(events)} rows loaded")
        except RuntimeError as e:
            self.error.emit(str(e))
            return

        while not self._stop:
            self._sleep()
            if self._stop:
                break
            try:
                events = self._dedup.new(azure_utils.fetch_logs_since(
                    self._client, self._workspace_id,
                    self._query, self._last_dt,
                ))
                if events:
                    self._last_dt = datetime.fromtimestamp(events[-1][0] / 1000, tz=UTC)
                    self.new_lines.emit(events)
                    self.status.emit(f"Azure {self._label} — {len(events)} new rows")
                else:
                    self.status.emit(f"Azure {self._label} — tailing…")
                self._poll_ok()
            except RuntimeError as e:
                if self._poll_failed(e):
                    return


# ── Grafana Loki worker ───────────────────────────────────────────────────────

class LokiWorker(_PollWorker):
    """Polls Grafana Loki via query_range and emits new log entries."""
    new_lines    = pyqtSignal(list)  # [(ts_ms, message), ...]
    status       = pyqtSignal(str)
    error        = pyqtSignal(str)
    history_done = pyqtSignal(int)

    def __init__(self, url: str, query: str,
                 username: str = "", password: str = "", token: str = "",
                 lookback_s: float = 3600.0, interval_s: float = 5.0) -> None:
        super().__init__()
        self._url        = url
        self._query      = query
        self._username   = username
        self._password   = password
        self._token      = token
        self._lookback_h = lookback_s / 3600
        self._interval_ms = int(interval_s * 1000)
        self._dedup      = _Dedup()

    def run(self) -> None:
        label = self._url.split("//", 1)[-1].split("/")[0]
        self.status.emit(f"Loading Loki logs from {label}…")
        now_ns   = int(time.time() * 1e9)
        start_ns = int((time.time() - self._lookback_h * 3600) * 1e9)
        try:
            events = self._dedup.new(loki_utils.fetch_logs(
                self._url, self._query, start_ns, now_ns,
                self._username, self._password, self._token,
                latest=True,
            ))
            self._last_ns = events[-1][0] * 1_000_000 if events else now_ns
            if events:
                self.new_lines.emit(events)
            self.history_done.emit(len(events))
            self.status.emit(f"Loki {label} — {len(events)} entries loaded")
        except RuntimeError as e:
            self.error.emit(str(e))
            return

        while not self._stop:
            self._sleep()
            if self._stop:
                break
            try:
                end_ns = int(time.time() * 1e9)
                # _last_ns is inclusive (ms precision): the dedup drops the repeats
                events = self._dedup.new(loki_utils.fetch_logs(
                    self._url, self._query, self._last_ns, end_ns,
                    self._username, self._password, self._token,
                    limit=200,
                ))
                if events:
                    self._last_ns = events[-1][0] * 1_000_000
                    self.new_lines.emit(events)
                    self.status.emit(f"Loki {label} — {len(events)} new entries")
                else:
                    self.status.emit(f"Loki {label} — tailing…")
                self._poll_ok()
            except RuntimeError as e:
                if self._poll_failed(e):
                    return


# ── Datadog Logs worker ───────────────────────────────────────────────────────

class DatadogWorker(_PollWorker):
    """Polls Datadog Logs Search API v2 and emits new log entries."""
    new_lines    = pyqtSignal(list)
    status       = pyqtSignal(str)
    error        = pyqtSignal(str)
    history_done = pyqtSignal(int)

    def __init__(self, base_url: str, query: str, api_key: str, app_key: str,
                 lookback_s: float = 3600.0, interval_s: float = 10.0) -> None:
        super().__init__()
        self._base_url    = base_url
        self._query       = query
        self._api_key     = api_key
        self._app_key     = app_key
        self._lookback_h  = lookback_s / 3600
        self._interval_ms = int(interval_s * 1000)
        self._dedup       = _Dedup()

    def run(self) -> None:
        site = self._base_url.split("//", 1)[-1]
        self.status.emit(f"Loading Datadog logs from {site}…")
        from_iso = datadog_utils.offset_iso(self._lookback_h)
        to_iso   = datadog_utils.now_iso()
        try:
            events = self._dedup.new(datadog_utils.fetch_logs(
                self._base_url, self._query, from_iso, to_iso,
                self._api_key, self._app_key, latest=True,
            ))
            if events:
                self._last_iso = _ts_ms_to_iso(events[-1][0])
                self.new_lines.emit(events)
            else:
                self._last_iso = to_iso
            self.history_done.emit(len(events))
            self.status.emit(f"Datadog {site} — {len(events)} entries loaded")
        except RuntimeError as e:
            self.error.emit(str(e))
            return

        while not self._stop:
            self._sleep()
            if self._stop:
                break
            try:
                to_iso = datadog_utils.now_iso()
                # _last_iso is inclusive: the dedup drops the entry already shown
                events = self._dedup.new(datadog_utils.fetch_logs(
                    self._base_url, self._query, self._last_iso, to_iso,
                    self._api_key, self._app_key, limit=200,
                ))
                if events:
                    self._last_iso = _ts_ms_to_iso(events[-1][0])
                    self.new_lines.emit(events)
                    self.status.emit(f"Datadog {site} — {len(events)} new entries")
                else:
                    self.status.emit(f"Datadog {site} — tailing…")
                self._poll_ok()
            except RuntimeError as e:
                if self._poll_failed(e):
                    return


# ── Elasticsearch / OpenSearch worker ────────────────────────────────────────

class ElasticWorker(_PollWorker):
    """Polls Elasticsearch / OpenSearch _search API and emits new log entries."""
    new_lines    = pyqtSignal(list)
    status       = pyqtSignal(str)
    error        = pyqtSignal(str)
    history_done = pyqtSignal(int)

    def __init__(self, url: str, index: str, query: str,
                 api_key: str = "", username: str = "", password: str = "",
                 ts_field: str = "@timestamp",
                 lookback_s: float = 3600.0, interval_s: float = 10.0) -> None:
        super().__init__()
        self._url         = url
        self._index       = index
        self._query       = query
        self._api_key     = api_key
        self._username    = username
        self._password    = password
        self._ts_field    = ts_field
        self._lookback_h  = lookback_s / 3600
        self._interval_ms = int(interval_s * 1000)
        self._dedup       = _Dedup()

    def run(self) -> None:
        label = self._url.split("//", 1)[-1].split("/")[0]
        self.status.emit(f"Loading Elasticsearch logs from {label}…")
        since = datetime.now(UTC) - timedelta(hours=self._lookback_h)
        since_iso = since.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        try:
            events, _ = elastic_utils.fetch_logs(
                self._url, self._index, self._query,
                since_iso=since_iso,
                api_key=self._api_key, username=self._username, password=self._password,
                ts_field=self._ts_field, latest=True,
            )
            events = self._dedup.new(events)
            self._last_iso  = since_iso
            if events:
                self._last_iso = _ts_ms_to_iso(events[-1][0])
                self.new_lines.emit(events)
            self.history_done.emit(len(events))
            self.status.emit(f"Elastic {label}/{self._index} — {len(events)} hits loaded")
        except RuntimeError as e:
            self.error.emit(str(e))
            return

        while not self._stop:
            self._sleep()
            if self._stop:
                break
            try:
                # Inclusive start (timestamps are compared at millisecond precision):
                # the entries already shown come back and are dropped by the dedup.
                events, _ = elastic_utils.fetch_logs(
                    self._url, self._index, self._query,
                    since_iso=self._last_iso, inclusive=True,
                    api_key=self._api_key, username=self._username, password=self._password,
                    ts_field=self._ts_field, size=200,
                )
                events = self._dedup.new(events)
                if events:
                    self._last_iso  = _ts_ms_to_iso(events[-1][0])
                    self.new_lines.emit(events)
                    self.status.emit(f"Elastic {label} — {len(events)} new hits")
                else:
                    self.status.emit(f"Elastic {label} — tailing…")
                self._poll_ok()
            except RuntimeError as e:
                if self._poll_failed(e):
                    return


# ── Railway worker ────────────────────────────────────────────────────────────

class RailwayWorker(_PollWorker):
    """Polls Railway deployment logs and emits new entries."""
    new_lines    = pyqtSignal(list)
    status       = pyqtSignal(str)
    error        = pyqtSignal(str)
    history_done = pyqtSignal(int)

    def __init__(self, token: str, project_name: str, service_name: str,
                 service_id: str, interval_s: float = 10.0,
                 lookback_s: float = 3600.0) -> None:
        super().__init__()
        self._token        = token
        self._project_name = project_name
        self._service_name = service_name
        self._service_id   = service_id
        self._interval_ms  = int(interval_s * 1000)
        self._lookback_s   = lookback_s

    def run(self) -> None:
        label = f"{self._project_name}/{self._service_name}"
        self.status.emit(f"Loading Railway logs for {label}…")
        since_ts_ms = int(time.time() * 1000) - int(self._lookback_s * 1000)
        try:
            deploy = railway_utils.get_latest_deployment(self._token, self._service_id)
            if not deploy:
                self.error.emit(f"No deployment found for {label}")
                return
            self._deploy_id = deploy["id"]
            all_events = railway_utils.fetch_deployment_logs(self._token, self._deploy_id)
            events = [(ts, m) for ts, m in all_events if ts >= since_ts_ms]
            self._seen: set = {(ts, m) for ts, m in all_events}
            if events:
                self.new_lines.emit(events)
            self.history_done.emit(len(events))
            self.status.emit(f"Railway {label} — {len(events)} lines loaded")
        except RuntimeError as e:
            self.error.emit(str(e))
            return

        while not self._stop:
            self._sleep()
            if self._stop:
                break
            try:
                # Check if a new deployment was created
                deploy = railway_utils.get_latest_deployment(self._token, self._service_id)
                if deploy and deploy["id"] != self._deploy_id:
                    self._deploy_id = deploy["id"]
                    self._seen = set()
                events = railway_utils.fetch_deployment_logs(self._token, self._deploy_id)
                new = [(ts, m) for ts, m in events if (ts, m) not in self._seen]
                if new:
                    self._seen.update(new)
                    self.new_lines.emit(new)
                    self.status.emit(f"Railway {label} — {len(new)} new lines")
                else:
                    self.status.emit(f"Railway {label} — tailing…")
                self._poll_ok()
            except RuntimeError as e:
                if self._poll_failed(e):
                    return


# ── Fly.io worker ─────────────────────────────────────────────────────────────

class FlyioWorker(_PollWorker):
    """Polls Fly.io SSE log stream and emits new log entries."""
    new_lines    = pyqtSignal(list)
    status       = pyqtSignal(str)
    error        = pyqtSignal(str)
    history_done = pyqtSignal(int)

    def __init__(self, token: str, app_name: str, interval_s: float = 5.0,
                 lookback_s: float = 3600.0) -> None:
        super().__init__()
        self._token       = token
        self._app_name    = app_name
        self._interval_ms = int(interval_s * 1000)
        self._lookback_s  = lookback_s
        self._dedup       = _Dedup(window_ms=60_000)

    def run(self) -> None:
        self.status.emit(f"Loading Fly.io logs for {self._app_name}…")
        since_ts_ms = int(time.time() * 1000) - int(self._lookback_s * 1000)
        try:
            events = self._dedup.new(
                flyio_utils.fetch_logs_sse(self._token, self._app_name, limit=300)
            )
            visible = [(ts, m) for ts, m in events if ts >= since_ts_ms]
            if visible:
                self.new_lines.emit(visible)
            self.history_done.emit(len(visible))
            self.status.emit(f"Fly.io {self._app_name} — {len(events)} entries loaded")
        except RuntimeError as e:
            self.error.emit(str(e))
            return

        while not self._stop:
            self._sleep()
            if self._stop:
                break
            try:
                new = self._dedup.new(
                    flyio_utils.fetch_logs_sse(self._token, self._app_name, limit=100)
                )
                if new:
                    self.new_lines.emit(new)
                    self.status.emit(f"Fly.io {self._app_name} — {len(new)} new entries")
                else:
                    self.status.emit(f"Fly.io {self._app_name} — tailing…")
                self._poll_ok()
            except RuntimeError as e:
                if self._poll_failed(e):
                    return


# ── Kubernetes worker ─────────────────────────────────────────────────────────

class KubernetesWorker(QThread):
    """Streams kubectl logs for a pod and emits new lines."""
    new_lines    = pyqtSignal(list)
    status       = pyqtSignal(str)
    error        = pyqtSignal(str)
    history_done = pyqtSignal(int)

    def __init__(self, pod: str, namespace: str, context: str = "",
                 container: str = "", lookback_s: float = 3600.0) -> None:
        super().__init__()
        self._pod       = pod
        self._namespace = namespace
        self._context   = context
        self._container = container
        self._lookback_s = lookback_s
        self._stop      = False
        self._proc      = None

    def stop(self) -> None:
        self._stop = True
        if self._proc and self._proc.poll() is None:
            with contextlib.suppress(Exception):
                self._proc.terminate()

    def run(self) -> None:
        label = f"{self._namespace}/{self._pod}"
        self.status.emit(f"Streaming Kubernetes logs for {label}…")
        cmd = kubernetes_utils.build_logs_cmd(
            self._pod, self._namespace, self._context, self._container,
            since_s=int(self._lookback_s),
        )
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1,
            )
        except Exception as e:
            self.error.emit(str(e))
            return

        now_ms = int(time.time() * 1000)
        first = True
        for batch in _batched((raw.rstrip("\n") for raw in self._proc.stdout),  # type: ignore[union-attr]
                              lambda: self._stop):
            if self._stop:
                break
            events = [_parse_k8s_line(line, now_ms) for line in batch]
            self.new_lines.emit(events)
            if first:
                self.history_done.emit(len(events))
                self.status.emit(f"k8s {label} — streaming")
                first = False

        if self._proc.poll() != 0 and not self._stop:
            err = (self._proc.stderr.read() or "").strip()  # type: ignore[union-attr]
            if err:
                self.error.emit(err)


# ── Cloudflare Workers tail worker ────────────────────────────────────────────

class CloudflareWorker(QThread):
    """Streams Cloudflare Workers tail events.

    Uses native HTTP/2 WebSocket (RFC 8441) via the h2 library when available.
    Falls back to the wrangler CLI subprocess if h2 is not installed.
    """
    new_lines    = pyqtSignal(list)  # [(ts_ms, message), ...]
    status       = pyqtSignal(str)
    error        = pyqtSignal(str)
    history_done = pyqtSignal(int)

    def __init__(self, api_token: str, account_id: str, script_name: str) -> None:
        super().__init__()
        self._api_token   = api_token
        self._account_id  = account_id
        self._script_name = script_name
        self._stop        = False
        self._proc        = None
        self._sock        = None

    def stop(self) -> None:
        self._stop = True
        if self._proc and self._proc.poll() is None:
            with contextlib.suppress(Exception):
                self._proc.terminate()
        if self._sock is not None:
            with contextlib.suppress(Exception):
                self._sock.close()

    def run(self) -> None:
        label = self._script_name
        self.status.emit(f"Connecting to Cloudflare tail for {label}…")

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
        cloudflare_utils.ws_send_frame_unmasked(self._sock, 1, init)

        self.history_done.emit(0)
        self.status.emit(f"Tailing {label} — waiting for requests…")

        try:
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
                        self.status.emit(f"Tailing {label} — live")
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
