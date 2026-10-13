"""Base class for the short-lived background workers used by the connection panels."""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal


class BackgroundWorker(QThread):
    """Runs `_work()` off the UI thread.

    Subclasses declare their own `success` signal and implement `_work()`, returning
    the tuple of values to emit with it. A RuntimeError becomes a `failure` message.
    """

    failure = pyqtSignal(str)

    def _work(self) -> tuple:
        raise NotImplementedError

    def run(self) -> None:
        try:
            result = self._work()
        except RuntimeError as e:
            self.failure.emit(str(e))
            return
        self.success.emit(*result)  # type: ignore[attr-defined]
