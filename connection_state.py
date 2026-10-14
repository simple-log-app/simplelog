"""Connection state of a remote log tab, and the back-off used to reconnect it."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

# A tab goes: connecting -> live -> (error) -> reconnecting -> connecting -> live ...
# or ends in "failed" (gave up), "stopped" (the user stopped it) or "ended" (stream over).
CONNECTING = "connecting"
LIVE = "live"
RECONNECTING = "reconnecting"
FAILED = "failed"
STOPPED = "stopped"
ENDED = "ended"

#: Seconds to wait before each successive reconnection attempt
RECONNECT_DELAYS = (3, 6, 12, 24, 48, 60)

# Colour roles, worst first: a tab with several logs shows its worst state
_SEVERITY = (FAILED, RECONNECTING, CONNECTING, LIVE, ENDED, STOPPED)


def worst(states: list[str]) -> str | None:
    """The state a tab holding logs in *states* should show (None when there are none)."""
    for state in _SEVERITY:
        if state in states:
            return state
    return None


@dataclass
class Link:
    """What is needed to bring a remote tab back: its provider, config and retry count."""

    provider: object                 # providers.Provider
    cfg: dict
    state: str = CONNECTING
    attempts: int = 0
    generation: int = 0              # bumped to cancel a scheduled reconnection
    detail: str = ""                 # e.g. the countdown shown in the tab's tooltip
    last_ok: float = field(default_factory=time.time)

    def can_retry(self) -> bool:
        return self.attempts < len(RECONNECT_DELAYS)

    def next_delay(self) -> int:
        """Seconds before the next attempt; counts it."""
        delay = RECONNECT_DELAYS[min(self.attempts, len(RECONNECT_DELAYS) - 1)]
        self.attempts += 1
        return delay

    def cancel(self) -> None:
        """Forget any scheduled reconnection (the user stopped or closed the tab)."""
        self.generation += 1

    def connected(self) -> None:
        self.attempts = 0
        self.last_ok = time.time()

    def reconnect_cfg(self, gap_s: float) -> dict:
        """The config to restart with: history only reaches back over what was missed."""
        cfg = dict(self.cfg)
        wanted = max(60, int(gap_s) + 30)
        for key in ("lookback_s", "lookback"):
            if key in cfg and isinstance(cfg[key], int | float):
                cfg[key] = min(cfg[key], wanted)
        return cfg
