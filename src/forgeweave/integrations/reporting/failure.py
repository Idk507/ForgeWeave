"""Inspectable local failure reports.

The reporter writes local JSON evidence only. It never sends mail, chat,
GitHub comments, deployments or other external notifications.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any

_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"(?i)(bearer)\s+([A-Za-z0-9._~+/=-]+)"),
)


@dataclass(frozen=True)
class FailureReportItem:
    """One inspectable failure included in a local report."""

    source: str
    code: str
    message: str
    evidence: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        return {"source": self.source, "code": self.code, "message": self.message, "evidence": self.evidence}


@dataclass(frozen=True)
class FailureReport:
    """Local report artifact for failed workflow/integration operations."""

    report_id: str
    task_id: str
    created_at: datetime
    title: str
    items: tuple[FailureReportItem, ...]
    notification_ready: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "task_id": self.task_id,
            "created_at": self.created_at.isoformat(),
            "title": self.title,
            "notification_ready": self.notification_ready,
            "items": [item.to_json() for item in self.items],
        }


class LocalFailureReporter:
    """Write failure reports to a local directory as JSON."""

    def __init__(self, *, report_root: Path) -> None:
        self.report_root = report_root.resolve()

    def write(self, report: FailureReport) -> Path:
        self.report_root.mkdir(parents=True, exist_ok=True)
        path = (self.report_root / f"{_safe_id(report.report_id)}.json").resolve()
        try:
            path.relative_to(self.report_root)
        except ValueError as exc:
            raise ValueError("failure report path escaped report root") from exc
        path.write_text(json.dumps(report.to_json(), indent=2, sort_keys=True), encoding="utf-8")
        return path


def build_failure_report(*, task_id: str, title: str, failures: list[dict[str, Any]], created_at: datetime | None = None) -> FailureReport:
    """Build a redacted failure report from structured failure dictionaries."""

    if not task_id.strip():
        raise ValueError("task_id must not be blank")
    if not title.strip():
        raise ValueError("title must not be blank")
    now = (created_at or datetime.now(UTC)).astimezone(UTC)
    items = tuple(_item(index, failure) for index, failure in enumerate(failures, start=1))
    material = f"{task_id}\0{title}\0{now.isoformat()}\0{len(items)}"
    report_id = "failure-report-" + _hash_fragment(material)
    return FailureReport(report_id=report_id, task_id=task_id, created_at=now, title=_redact(title.strip()), items=items)


def _item(index: int, failure: dict[str, Any]) -> FailureReportItem:
    source = _redact(str(failure.get("source") or "unknown"))
    code = _redact(str(failure.get("code") or "FAILED"))
    message = _redact(str(failure.get("message") or "failure recorded"))
    evidence = _redact_value(failure.get("evidence") or {})
    if not isinstance(evidence, dict):
        evidence = {"value": evidence}
    return FailureReportItem(source=source, code=code, message=message, evidence={"index": index, **evidence})


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact(value)
    if isinstance(value, dict):
        return {str(key): _redact_value(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value


def _redact(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}=<redacted>", redacted)
    return redacted


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.")
    if not safe:
        raise ValueError("report_id must contain a safe filename component")
    return safe


def _hash_fragment(value: str) -> str:
    from hashlib import sha256

    return sha256(value.encode("utf-8")).hexdigest()[:16]
