"""Bounded local telemetry writer with explicit sink failure accounting."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Protocol

from forgeweave.telemetry.jsonl import TelemetryEvent


class TelemetrySink(Protocol):
    """Minimal sink protocol used by the bounded writer."""

    def write(self, event: TelemetryEvent) -> None:
        """Write one telemetry event or raise when the sink cannot accept it."""


@dataclass(frozen=True)
class TelemetryFlushResult:
    """Outcome of one attempt to flush buffered telemetry."""

    written: int
    failed: int
    dropped: int
    pending: int
    last_error: str | None = None


class BoundedTelemetryWriter:
    """Buffer telemetry events locally before writing them to a sink.

    The writer keeps memory bounded by dropping the oldest pending event when
    capacity is reached. A sink failure leaves the failed event queued so a
    later flush can retry it without reordering newer pending events.
    """

    def __init__(self, *, sink: TelemetrySink, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("telemetry buffer capacity must be positive")
        self._sink = sink
        self._events: deque[TelemetryEvent] = deque()
        self._capacity = capacity
        self._dropped_count = 0
        self._failure_count = 0

    @property
    def pending_count(self) -> int:
        """Number of events waiting to be flushed."""

        return len(self._events)

    @property
    def dropped_count(self) -> int:
        """Total events dropped because the bounded buffer was full."""

        return self._dropped_count

    @property
    def failure_count(self) -> int:
        """Total sink write failures observed by this writer."""

        return self._failure_count

    def record(self, event: TelemetryEvent) -> None:
        """Append an event, dropping the oldest pending event if needed."""

        if len(self._events) >= self._capacity:
            self._events.popleft()
            self._dropped_count += 1
        self._events.append(event)

    def flush(self) -> TelemetryFlushResult:
        """Write pending events in order until the buffer is empty or the sink fails."""

        written = 0
        dropped_before_flush = self._dropped_count
        while self._events:
            event = self._events[0]
            try:
                self._sink.write(event)
            except Exception as exc:
                self._failure_count += 1
                return TelemetryFlushResult(
                    written=written,
                    failed=1,
                    dropped=dropped_before_flush,
                    pending=len(self._events),
                    last_error=f"{type(exc).__name__}: {exc}",
                )
            self._events.popleft()
            written += 1
        return TelemetryFlushResult(
            written=written,
            failed=0,
            dropped=dropped_before_flush,
            pending=0,
        )
