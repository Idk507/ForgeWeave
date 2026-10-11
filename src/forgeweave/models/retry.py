"""Retry helpers for model provider calls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import random
import time
from typing import TypeVar

T = TypeVar("T")


class RetryableModelError(RuntimeError):
    """Raised by providers for transient model/API failures that may be retried."""


@dataclass(frozen=True)
class RetryPolicy:
    """Capped exponential backoff policy for provider calls."""

    max_attempts: int = 3
    initial_delay_seconds: float = 0.25
    max_delay_seconds: float = 4.0
    jitter_ratio: float = 0.25

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds must not be negative")
        if self.max_delay_seconds < 0:
            raise ValueError("max_delay_seconds must not be negative")
        if self.jitter_ratio < 0:
            raise ValueError("jitter_ratio must not be negative")

    def delay_for_attempt(self, attempt_index: int, *, jitter: Callable[[int], float] | None = None) -> float:
        """Return delay before the next attempt; attempt_index is zero-based."""

        base = min(self.max_delay_seconds, self.initial_delay_seconds * (2**attempt_index))
        jitter_source = (lambda attempt: random.random()) if jitter is None else jitter
        return min(self.max_delay_seconds, base + (base * self.jitter_ratio * jitter_source(attempt_index)))


def call_with_retries(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[int], float] | None = None,
) -> T:
    """Call an operation with capped retries for `RetryableModelError` only."""

    for attempt in range(policy.max_attempts):
        try:
            return operation()
        except RetryableModelError:
            if attempt + 1 >= policy.max_attempts:
                raise
            sleep(policy.delay_for_attempt(attempt, jitter=jitter))
    raise AssertionError("unreachable retry loop exit")
