"""Workflow artifact binding validation.

Workflow steps can declare artifacts they expect a mediated executor to produce.
The runner validates those declarations against executor output before accepting a
successful step, so downstream workflow progress is tied to inspectable evidence
instead of a bare completion claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from .contracts import WorkflowStep



@dataclass(frozen=True)
class WorkflowArtifactRecord:
    """Persisted provenance for one artifact produced by a workflow step attempt."""

    artifact_id: str
    run_id: str
    step_id: str
    attempt_id: str
    name: str
    uri: str
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkflowArtifactBinding:
    """One artifact name expected from a workflow step."""

    name: str
    required: bool = True


@dataclass(frozen=True)
class WorkflowArtifactValidationResult:
    """Result of checking executor output against declared artifact bindings."""

    valid: bool
    reason: str
    required: tuple[str, ...] = ()
    present: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


def artifact_bindings_for_step(step: WorkflowStep) -> tuple[WorkflowArtifactBinding, ...]:
    """Return artifact bindings declared in ``step.parameters``.

    Supported forms are intentionally simple and JSON-friendly:
    ``{"artifacts": ["diff", {"name": "verification", "required": true}]}``.
    """

    parameters = step.parameters or {}
    raw = parameters.get("artifacts")
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError(f"workflow step artifacts must be a list: {step.step_id}")
    bindings: list[WorkflowArtifactBinding] = []
    for index, item in enumerate(raw):
        if isinstance(item, str):
            name = item.strip()
            required = True
        elif isinstance(item, dict):
            raw_name = item.get("name")
            if not isinstance(raw_name, str):
                raise ValueError(f"workflow artifact binding {index} requires a string name: {step.step_id}")
            name = raw_name.strip()
            raw_required = item.get("required", True)
            if not isinstance(raw_required, bool):
                raise ValueError(f"workflow artifact binding {name or index} requires a boolean required flag")
            required = raw_required
        else:
            raise ValueError(f"workflow artifact binding {index} must be a string or object: {step.step_id}")
        if not name:
            raise ValueError(f"workflow artifact binding {index} name must not be blank: {step.step_id}")
        bindings.append(WorkflowArtifactBinding(name=name, required=required))
    names = [binding.name for binding in bindings]
    if len(names) != len(set(names)):
        raise ValueError(f"workflow step artifact bindings must be unique: {step.step_id}")
    return tuple(bindings)


def validate_artifact_bindings(step: WorkflowStep, output: dict[str, Any] | None) -> WorkflowArtifactValidationResult:
    """Validate successful executor output against step artifact declarations."""

    bindings = artifact_bindings_for_step(step)
    required = tuple(binding.name for binding in bindings if binding.required)
    if not required:
        return WorkflowArtifactValidationResult(valid=True, reason="no required artifacts declared", required=required)
    present = _present_artifact_names(output)
    missing = tuple(name for name in required if name not in present)
    if missing:
        return WorkflowArtifactValidationResult(
            valid=False,
            reason=f"missing required workflow artifacts: {', '.join(missing)}",
            required=required,
            present=present,
            missing=missing,
        )
    return WorkflowArtifactValidationResult(
        valid=True,
        reason="required workflow artifacts produced",
        required=required,
        present=present,
    )


def _present_artifact_names(output: dict[str, Any] | None) -> tuple[str, ...]:
    if not output:
        return ()
    raw = output.get("artifacts")
    if raw is None:
        return ()
    names: list[str] = []
    if isinstance(raw, dict):
        names.extend(str(key).strip() for key in raw if str(key).strip())
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                name = item.strip()
            elif isinstance(item, dict):
                raw_name = item.get("name") or item.get("artifact_id")
                name = raw_name.strip() if isinstance(raw_name, str) else ""
            else:
                name = ""
            if name:
                names.append(name)
    return tuple(dict.fromkeys(names))



def artifact_records_from_output(
    *,
    run_id: str,
    step_id: str,
    attempt_id: str,
    output: dict[str, Any] | None,
) -> tuple[WorkflowArtifactRecord, ...]:
    """Extract durable artifact provenance records from executor output."""

    if not output:
        return ()
    raw = output.get("artifacts")
    if raw is None:
        return ()
    records: list[WorkflowArtifactRecord] = []
    if isinstance(raw, dict):
        items = raw.items()
        for name, value in items:
            normalized_name = str(name).strip()
            if not normalized_name:
                continue
            uri, metadata = _artifact_value_to_uri_and_metadata(value)
            if uri:
                records.append(_artifact_record(run_id, step_id, attempt_id, normalized_name, uri, metadata))
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                name = item.strip()
                uri = item.strip()
                metadata = None
            elif isinstance(item, dict):
                raw_name = item.get("name") or item.get("artifact_id")
                name = raw_name.strip() if isinstance(raw_name, str) else ""
                raw_uri = item.get("uri") or item.get("url") or item.get("path") or item.get("artifact_id")
                uri = raw_uri.strip() if isinstance(raw_uri, str) else ""
                metadata = {key: value for key, value in item.items() if key not in {"name", "uri", "url", "path"}}
            else:
                name = ""
                uri = ""
                metadata = None
            if name and uri:
                records.append(_artifact_record(run_id, step_id, attempt_id, name, uri, metadata))
    return tuple(records)


def _artifact_value_to_uri_and_metadata(value: Any) -> tuple[str, dict[str, Any] | None]:
    if isinstance(value, str):
        return value.strip(), None
    if isinstance(value, dict):
        raw_uri = value.get("uri") or value.get("url") or value.get("path") or value.get("artifact_id")
        uri = raw_uri.strip() if isinstance(raw_uri, str) else ""
        metadata = {key: item for key, item in value.items() if key not in {"uri", "url", "path"}}
        return uri, metadata
    return "", None


def _artifact_record(
    run_id: str,
    step_id: str,
    attempt_id: str,
    name: str,
    uri: str,
    metadata: dict[str, Any] | None,
) -> WorkflowArtifactRecord:
    payload = {"run_id": run_id, "step_id": step_id, "attempt_id": attempt_id, "name": name, "uri": uri}
    artifact_id = "workflow-artifact:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return WorkflowArtifactRecord(
        artifact_id=artifact_id,
        run_id=run_id,
        step_id=step_id,
        attempt_id=attempt_id,
        name=name,
        uri=uri,
        metadata=metadata or None,
    )
