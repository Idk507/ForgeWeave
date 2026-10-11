"""Helpers shared by engine adapters."""

from __future__ import annotations

from typing import Any

from .contracts import EngineEvent

_MAX_REPR = 2000


def to_payload(obj: Any) -> dict[str, Any]:
    """Convert a vendor object into a bounded, JSON-safe payload."""
    if isinstance(obj, dict):
        return {"raw": {str(k): repr(v)[:_MAX_REPR] for k, v in obj.items()}}
    return {"repr": repr(obj)[:_MAX_REPR]}


def import_events(engine: str, items: list[Any] | tuple[Any, ...], kind: str) -> list[EngineEvent]:
    """Wrap vendor event objects as untrusted EngineEvent records."""
    return [
        EngineEvent(engine=engine, sequence=i, kind=kind, payload=to_payload(item))
        for i, item in enumerate(items)
    ]
