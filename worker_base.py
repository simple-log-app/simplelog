"""worker_base.py — shared plumbing for the log-source workers (see workers.py).

Three families of workers sit on top of ``LogWorker``:

* ``PollingWorker``       — cloud APIs queried every few seconds (history, then tail),
* ``ProcessStreamWorker`` — a child process whose output is streamed (docker, kubectl),
* plain ``StreamWorker``  — any other blocking line source (stdin, an SSH channel).
"""
from __future__ import annotations

import queue
import subprocess
import threading
import time
from contextlib import suppress

from PyQt6.QtCore import QThread, pyqtSignal

# A viewer keeps at most this many lines: loading more history is wasted work.
HISTORY_CAP = 10_000


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


class Dedup:
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
            newest = max(e[0] for e in events)
            self._newest = newest if self._newest is None else max(self._newest, newest)
            floor = self._newest - self._window
            self._seen = {e for e in self._seen if e[0] >= floor}
        return events


class LogWorker(QThread):
    """A thread that feeds ``new_lines`` with ``[(ts_ms, message), ...]`` batches."""

    new_lines = pyqtSignal(list)
    status = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._stop = False
        self._wakeup = threading.Event()   # set by stop(): cuts any wait short

    def stop(self) -> None:
        self._stop = True
        self._wakeup.set()

    def _emit(self, events: list) -> None:
        if events:
            self.new_lines.emit(events)


# ── Polling ──────────────────────────────────────────────────────────────────

class PollingWorker(LogWorker):
    """Loads a history, then polls for what is new every *interval_s* seconds.

    Subclasses implement ``_fetch_history()`` and ``_fetch_new()`` (each returns the
    events to show and keeps its own cursor) and describe the status line with the
    ``_MSG_*`` templates, formatted with ``{n}`` and ``self._ctx``. A RuntimeError
    from either is a failed call: the history error stops the worker at once, while a
    failed poll is retried — an error is only raised after ``_MAX_FAILS`` in a row.
    """

    history_done = pyqtSignal(int)

    _MAX_FAILS = 5

    _MSG_LOADING = ""
    _MSG_LOADED = ""      # optional
    _MSG_NEW = ""
    _MSG_IDLE = ""

    def __init__(self, interval_s: float = 5.0) -> None:
        super().__init__()
        self._interval_ms = int(interval_s * 1000)
        self._fails = 0
        self._ctx: dict = {}

    # ── to implement ──────────────────────────────────────────────────────────

    def _fetch_history(self) -> list[tuple[int, str]]:
        raise NotImplementedError

    def _fetch_new(self) -> list[tuple[int, str]]:
        raise NotImplementedError

    # ── machinery ─────────────────────────────────────────────────────────────

    def _say(self, template: str, n: int = 0) -> None:
        if template:
            self.status.emit(template.format(n=n, **self._ctx))

    def _sleep(self) -> None:
        """Wait for the poll interval, returning early if stop() is called."""
        self._wakeup.wait(self._interval_ms / 1000)

    def _poll_ok(self) -> None:
        self._fails = 0

    def _poll_failed(self, exc: Exception) -> bool:
        """Record a failed poll. Returns True when the worker should give up."""
        self._fails += 1
        if self._fails >= self._MAX_FAILS:
            self.error.emit(str(exc))
            return True
        self.status.emit(
            f"Connection problem ({self._fails}/{self._MAX_FAILS}), retrying… {exc}"
        )
        return False

    def run(self) -> None:
        self._say(self._MSG_LOADING)
        try:
            events = self._fetch_history()
        except RuntimeError as e:
            self.error.emit(str(e))
            return
        self._emit(events)
        self.history_done.emit(len(events))
        self._say(self._MSG_LOADED, len(events))

        while not self._stop:
            self._sleep()
            if self._stop:
                break
            try:
                events = self._fetch_new()
                self._emit(events)
                self._say(self._MSG_NEW if events else self._MSG_IDLE, len(events))
                self._poll_ok()
            except RuntimeError as e:
                if self._poll_failed(e):
                    return


# ── Streaming ────────────────────────────────────────────────────────────────

def clean_lines(batch: list[str], chars: str | None = None) -> list[tuple[int, str]]:
    """Stamp the lines of *batch* with the current time, dropping the empty ones."""
    now = int(time.time() * 1000)
    return [(now, line) for line in (raw.rstrip(chars) for raw in batch) if line]


class StreamWorker(LogWorker):
    """A blocking line source: lines are forwarded in batches as they arrive."""

    def _pump(self, lines, parse, is_stopped=None) -> None:
        """Forward *lines* through *parse* (batch -> events) until exhausted or stopped."""
        stopped = is_stopped or (lambda: self._stop)
        for batch in _batched(lines, stopped):
            if stopped():
                break
            self._emit(parse(batch))


class ProcessStreamWorker(StreamWorker):
    """Streams the output of a child process (``docker logs``, ``kubectl logs``, …).

    Subclasses give the command and the status text, and may override ``_parse`` (turn
    a batch of raw lines into events), ``_deliver`` and ``_finish`` (what to report
    when the process ends).
    """

    _MERGE_STDERR = True   # False: stderr is read once the process is over

    def __init__(self) -> None:
        super().__init__()
        self._proc: subprocess.Popen | None = None

    def stop(self) -> None:
        super().stop()
        proc = self._proc
        if proc is not None and proc.poll() is None:
            with suppress(Exception):
                proc.terminate()

    # ── to implement ──────────────────────────────────────────────────────────

    def _command(self) -> list[str]:
        raise NotImplementedError

    def _start_status(self) -> str:
        raise NotImplementedError

    def _parse(self, batch: list[str]) -> list[tuple[int, str]]:
        return clean_lines(batch)

    def _deliver(self, events: list[tuple[int, str]]) -> None:
        self._emit(events)

    def _finish(self) -> None:
        """The output ended without a stop request: report how the process went."""

    # ── machinery ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        self.status.emit(self._start_status())
        try:
            self._proc = subprocess.Popen(
                self._command(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT if self._MERGE_STDERR else subprocess.PIPE,
                text=True, bufsize=1,
            )
            for batch in _batched(self._proc.stdout, lambda: self._stop):
                if self._stop:
                    break
                self._deliver(self._parse(batch))
            self._finish()
        except Exception as e:
            if not self._stop:
                self.error.emit(str(e))


class DockerStreamWorker(ProcessStreamWorker):
    """A docker CLI stream: a non-zero exit (other than our own SIGTERM) is an error."""

    _ENDED_STATUS = ""

    def _exit_error(self, code: int) -> str:
        raise NotImplementedError

    def _finish(self) -> None:
        proc = self._proc
        proc.wait()  # type: ignore[union-attr]
        if self._stop:
            return
        if proc.returncode not in (0, -15):  # type: ignore[union-attr]
            self.error.emit(self._exit_error(proc.returncode))  # type: ignore[union-attr]
        else:
            self.status.emit(self._ENDED_STATUS)
