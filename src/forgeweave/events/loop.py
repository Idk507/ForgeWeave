"""Loop-level append-only event recording."""

from __future__ import annotations

from uuid import uuid4

from forgeweave.contracts import ActorKind, Event, EventKind
from forgeweave.core import StopDecision

from .store import EventStore


class LoopEventRecorder:
    """Persist coarse loop lifecycle events into the append-only event log."""

    def __init__(self, store: EventStore) -> None:
        self._store = store

    def record_loop_started(
        self,
        *,
        task_id: str,
        attempt_id: str,
        correlation_id: str,
        diagnostics_ref: str,
    ) -> Event:
        """Append a loop-start event that points at prompt-free diagnostics."""

        clean_ref = _clean_ref(diagnostics_ref)
        return self._store.append(
            _event(
                task_id=task_id,
                attempt_id=attempt_id,
                correlation_id=correlation_id,
                payload_ref=f"loop-started://{clean_ref}",
            )
        )

    def record_loop_ended(
        self,
        *,
        task_id: str,
        attempt_id: str,
        correlation_id: str,
        stop_decision: StopDecision,
        diagnostics_ref: str,
    ) -> Event:
        """Append a loop-end event that includes the canonical stop reason in its reference."""

        clean_ref = _clean_ref(diagnostics_ref)
        return self._store.append(
            _event(
                task_id=task_id,
                attempt_id=attempt_id,
                correlation_id=correlation_id,
                payload_ref=f"loop-ended://{stop_decision.reason.value}/{clean_ref}",
            )
        )


def _event(*, task_id: str, attempt_id: str, correlation_id: str, payload_ref: str) -> Event:
    return Event(
        event_id=f"evt-{uuid4()}",
        task_id=task_id,
        attempt_id=attempt_id,
        sequence=1,
        actor=ActorKind.SYSTEM,
        kind=EventKind.STEP_RECORDED,
        correlation_id=correlation_id,
        payload_ref=payload_ref,
    )


def _clean_ref(value: str) -> str:
    clean = value.strip()
    if not clean:
        raise ValueError("diagnostics_ref must not be blank")
    return clean
