import threading
import time


class CircuitBreaker:
    """Stops calling the LLM for a while after repeated failures."""

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: int = 120):
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown_seconds
        self._failures = 0
        self._opened_at = None
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return True
            if time.monotonic() - self._opened_at >= self.cooldown:
                self._opened_at = time.monotonic()   # let one probe through, re-arm the timer
                return True
            return False

    def record_success(self) -> bool:
        """Returns True if the breaker had been open (i.e. the service just recovered)."""
        with self._lock:
            was_open = self._opened_at is not None
            self._failures = 0
            self._opened_at = None
            return was_open

    def record_failure(self) -> bool:
        """Returns True if this failure just opened the breaker."""
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold and self._opened_at is None:
                self._opened_at = time.monotonic()
                return True
            return False

    def is_open(self) -> bool:
        """Read-only check: True while LLM calls are being skipped."""
        with self._lock:
            return (
                self._opened_at is not None
                and time.monotonic() - self._opened_at < self.cooldown
            )