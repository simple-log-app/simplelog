"""Base class for the short-lived background workers used by the connection panels."""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

# Started workers stay referenced until they finish: dropping the last reference to a
# running QThread (e.g. when its panel is closed) makes Qt abort the whole process.
_ACTIVE: set = set()


class BackgroundWorker(QThread):
    """Runs `_work()` off the UI thread.

    Subclasses declare their own `success` signal and implement `_work()`, returning
    the tuple of values to emit with it. Any exception becomes a `failure` message
    (an uncaught one in a thread would take the application down).
    """

    failure = pyqtSignal(str)

    def start(self, *args) -> None:  # noqa: D102
        _ACTIVE.add(self)
        self.finished.connect(self._release)
        super().start(*args)

    def _release(self) -> None:
        self.wait()   # finished was just emitted: returns at once
        _ACTIVE.discard(self)

    def _work(self) -> tuple:
        raise NotImplementedError

    def run(self) -> None:
        try:
            result = self._work()
        except Exception as e:
            self.failure.emit(str(e))
            return
        self.success.emit(*result)  # type: ignore[attr-defined]


class CallWorker(BackgroundWorker):
    """Calls ``fn(*args, **kwargs)`` in the background and emits its result."""

    success = pyqtSignal(object)

    def __init__(self, fn, *args, **kwargs) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def _work(self) -> tuple:
        return (self._fn(*self._args, **self._kwargs),)
