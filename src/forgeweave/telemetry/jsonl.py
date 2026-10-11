"""Local JSONL telemetry sink with secret redaction."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from uuid import uuid4
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SENSITIVE_NAME_PARTS = ("secret", "password", "api_key", "apikey", "authorization", "credential")
_TOKEN_METRIC_SUFFIXES = ("_tokens", "_token_count", "_token_estimate")


class TelemetryEvent(BaseModel):
    """One structured local telemetry event."""

    model_config = ConfigDict(frozen=True)

    event: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    fields: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("event", "task_id", "attempt_id", "correlation_id")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("telemetry identity fields must not be blank")
        return value.strip()


class TelemetrySpan(BaseModel):
    """A local causal span that can be written as start and end events."""

    model_config = ConfigDict(frozen=True)

    span_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    parent_span_id: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    fields: dict[str, Any] = Field(default_factory=dict)

    @field_validator("span_id", "name", "task_id", "attempt_id", "correlation_id")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("telemetry span identity fields must not be blank")
        return value.strip()

    @field_validator("parent_span_id")
    @classmethod
    def _parent_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("parent_span_id must not be blank when provided")
        return value.strip() if value is not None else None


class JsonlTelemetrySink:
    """Append local telemetry events as redacted JSON lines."""

    def __init__(self, path: Path, *, max_bytes: int | None = None, backup_count: int = 0) -> None:
        if max_bytes is not None and max_bytes <= 0:
            raise ValueError("max_bytes must be positive when provided")
        if backup_count < 0:
            raise ValueError("backup_count must not be negative")
        self.path = path
        self.max_bytes = max_bytes
        self.backup_count = backup_count

    def start_span(
        self,
        *,
        name: str,
        task_id: str,
        attempt_id: str,
        correlation_id: str,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        fields: dict[str, Any] | None = None,
        started_at: datetime | None = None,
    ) -> TelemetrySpan:
        """Create and record a span start event."""

        span = TelemetrySpan(
            span_id=span_id or str(uuid4()),
            name=name,
            task_id=task_id,
            attempt_id=attempt_id,
            correlation_id=correlation_id,
            parent_span_id=parent_span_id,
            started_at=started_at or datetime.now(UTC),
            fields=fields or {},
        )
        self.write(
            TelemetryEvent(
                event="span.started",
                task_id=span.task_id,
                attempt_id=span.attempt_id,
                correlation_id=span.correlation_id,
                timestamp=span.started_at,
                fields=_span_fields(span, span.fields),
            )
        )
        return span

    def end_span(
        self,
        span: TelemetrySpan,
        *,
        status: str,
        fields: dict[str, Any] | None = None,
        ended_at: datetime | None = None,
    ) -> None:
        """Record a span end event with elapsed duration in milliseconds."""

        clean_status = status.strip()
        if not clean_status:
            raise ValueError("span status must not be blank")
        completed_at = ended_at or datetime.now(UTC)
        duration_ms = max(0.0, (completed_at - span.started_at).total_seconds() * 1000.0)
        end_fields = {"duration_ms": duration_ms, "status": clean_status}
        if fields:
            end_fields.update(fields)
        self.write(
            TelemetryEvent(
                event="span.ended",
                task_id=span.task_id,
                attempt_id=span.attempt_id,
                correlation_id=span.correlation_id,
                timestamp=completed_at,
                fields=_span_fields(span, end_fields),
            )
        )

    def write(self, event: TelemetryEvent) -> None:
        """Append one event to the JSONL file."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = event.model_dump(mode="json")
        payload["fields"] = _redact(payload.get("fields", {}))
        line = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
        self._rotate_if_needed(len(line.encode("utf-8")))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        if self.max_bytes is None or not self.path.exists():
            return
        if self.path.stat().st_size + incoming_bytes <= self.max_bytes:
            return
        if self.backup_count == 0:
            self.path.unlink()
            return
        oldest = self._backup_path(self.backup_count)
        if oldest.exists():
            oldest.unlink()
        for index in range(self.backup_count - 1, 0, -1):
            source = self._backup_path(index)
            if source.exists():
                source.replace(self._backup_path(index + 1))
        self.path.replace(self._backup_path(1))

    def _backup_path(self, index: int) -> Path:
        return self.path.with_name(f"{self.path.name}.{index}")


def _span_fields(span: TelemetrySpan, extra_fields: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "span_id": span.span_id,
        "span_name": span.name,
        "parent_span_id": span.parent_span_id,
    }
    fields.update(extra_fields)
    return fields


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_name(str(key)):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _is_sensitive_name(name: str) -> bool:
    lowered = name.lower().replace("-", "_")
    if any(part in lowered for part in _SENSITIVE_NAME_PARTS):
        return True
    if "token" not in lowered:
        return False
    return not lowered.endswith(_TOKEN_METRIC_SUFFIXES)
