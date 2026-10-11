"""Immutable workflow contracts and definition validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any


class WorkflowStepKind(str, Enum):
    """Typed workflow node kinds supported by the automation contract."""

    AGENT = "agent"
    TOOL = "tool"
    VERIFICATION = "verification"
    APPROVAL = "approval"
    CONDITION = "condition"
    MAP = "map"
    JOIN = "join"


class WorkflowFailurePolicy(str, Enum):
    """How a workflow or join handles failed members."""

    FAIL_FAST = "fail_fast"
    COLLECT_ERRORS = "collect_errors"


class JoinMode(str, Enum):
    """Supported fan-in modes for bounded workflow joins."""

    ALL_SUCCESS = "all_success"
    ALL_SETTLED = "all_settled"
    QUORUM = "quorum"
    FIRST_VERIFIED = "first_verified"


class WorkflowRunStatus(str, Enum):
    """Durable workflow run status."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_EXTERNAL = "waiting_external"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStepStatus(str, Enum):
    """Durable workflow step status."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_EXTERNAL = "waiting_external"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class WorkflowValidationError(ValueError):
    """Raised when an immutable workflow definition is unsafe or invalid."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class JoinPolicy:
    """Bounded fan-in policy for join/map workflow steps."""

    mode: JoinMode
    failure_policy: WorkflowFailurePolicy = WorkflowFailurePolicy.FAIL_FAST
    quorum: int | None = None

    def validate(self, *, member_count: int) -> None:
        if member_count < 1:
            raise WorkflowValidationError("EMPTY_JOIN", "join policy requires at least one member")
        if self.mode is JoinMode.QUORUM:
            if self.quorum is None or self.quorum < 1 or self.quorum > member_count:
                raise WorkflowValidationError("INVALID_QUORUM", "quorum must be between 1 and member count")
        elif self.quorum is not None:
            raise WorkflowValidationError("UNEXPECTED_QUORUM", "quorum is only valid for quorum joins")


@dataclass(frozen=True)
class WorkflowStep:
    """One immutable node in a workflow definition DAG."""

    step_id: str
    kind: WorkflowStepKind
    depends_on: tuple[str, ...] = ()
    capability: str | None = None
    parameters: dict[str, Any] | None = None
    join_policy: JoinPolicy | None = None
    max_attempts: int = 1
    timeout_seconds: int | None = None

    def __post_init__(self) -> None:
        _require_id("step_id", self.step_id)
        if self.max_attempts < 1:
            raise WorkflowValidationError("INVALID_RETRY_LIMIT", "max_attempts must be >= 1")
        if self.timeout_seconds is not None and self.timeout_seconds < 1:
            raise WorkflowValidationError("INVALID_TIMEOUT", "timeout_seconds must be >= 1")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise WorkflowValidationError("DUPLICATE_DEPENDENCY", f"step {self.step_id} has duplicate dependencies")
        if self.kind in {WorkflowStepKind.JOIN, WorkflowStepKind.MAP} and self.join_policy is None:
            raise WorkflowValidationError("MISSING_JOIN_POLICY", f"{self.kind.value} step requires join_policy")
        if self.kind not in {WorkflowStepKind.JOIN, WorkflowStepKind.MAP} and self.join_policy is not None:
            raise WorkflowValidationError("UNEXPECTED_JOIN_POLICY", f"{self.kind.value} step cannot define join_policy")


@dataclass(frozen=True)
class WorkflowDefinition:
    """Immutable workflow DAG admitted before execution."""

    workflow_id: str
    version: int
    steps: tuple[WorkflowStep, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    failure_policy: WorkflowFailurePolicy = WorkflowFailurePolicy.FAIL_FAST
    schema_version: str = "workflow-definition.v1"

    def __post_init__(self) -> None:
        _require_id("workflow_id", self.workflow_id)
        if self.version < 1:
            raise WorkflowValidationError("INVALID_VERSION", "workflow version must be >= 1")
        if not self.steps:
            raise WorkflowValidationError("EMPTY_WORKFLOW", "workflow must contain at least one step")
        validate_workflow_definition(self)

    @property
    def definition_hash(self) -> str:
        """Return a stable hash used to bind runs to immutable definitions."""

        return _stable_hash(_definition_payload(self))


@dataclass(frozen=True)
class WorkflowRun:
    """Runtime admission record for one workflow execution."""

    run_id: str
    workflow_id: str
    definition_hash: str
    input_hash: str
    status: WorkflowRunStatus = WorkflowRunStatus.PENDING

    def __post_init__(self) -> None:
        for field, value in (
            ("run_id", self.run_id),
            ("workflow_id", self.workflow_id),
            ("definition_hash", self.definition_hash),
            ("input_hash", self.input_hash),
        ):
            _require_id(field, value)


@dataclass(frozen=True)
class StepAttempt:
    """Persisted attempt evidence for one workflow step dispatch."""

    attempt_id: str
    run_id: str
    step_id: str
    idempotency_key: str
    lease_token: str | None = None
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING

    def __post_init__(self) -> None:
        for field, value in (
            ("attempt_id", self.attempt_id),
            ("run_id", self.run_id),
            ("step_id", self.step_id),
            ("idempotency_key", self.idempotency_key),
        ):
            _require_id(field, value)


def validate_workflow_definition(definition: WorkflowDefinition) -> None:
    """Validate IDs, dependencies, join policies and cycles before dispatch."""

    step_ids = [step.step_id for step in definition.steps]
    if len(step_ids) != len(set(step_ids)):
        raise WorkflowValidationError("DUPLICATE_STEP", "workflow step IDs must be unique")
    step_by_id = {step.step_id: step for step in definition.steps}
    for step in definition.steps:
        for dependency in step.depends_on:
            if dependency not in step_by_id:
                raise WorkflowValidationError("UNKNOWN_DEPENDENCY", f"step {step.step_id} depends on unknown step {dependency}")
        if step.join_policy is not None:
            step.join_policy.validate(member_count=len(step.depends_on))
    _reject_cycles(step_by_id)


def _reject_cycles(step_by_id: dict[str, WorkflowStep]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str) -> None:
        if step_id in visited:
            return
        if step_id in visiting:
            raise WorkflowValidationError("CYCLE", f"workflow dependency cycle includes {step_id}")
        visiting.add(step_id)
        for dependency in step_by_id[step_id].depends_on:
            visit(dependency)
        visiting.remove(step_id)
        visited.add(step_id)

    for step_id in step_by_id:
        visit(step_id)


def workflow_input_hash(inputs: dict[str, Any]) -> str:
    """Return a stable hash for workflow admission inputs."""

    return _stable_hash(inputs)


def _definition_payload(definition: WorkflowDefinition) -> dict[str, Any]:
    return {
        "workflow_id": definition.workflow_id,
        "version": definition.version,
        "schema_version": definition.schema_version,
        "failure_policy": definition.failure_policy.value,
        "input_schema": definition.input_schema,
        "output_schema": definition.output_schema,
        "steps": [
            {
                "step_id": step.step_id,
                "kind": step.kind.value,
                "depends_on": list(step.depends_on),
                "capability": step.capability,
                "parameters": step.parameters or {},
                "join_policy": None
                if step.join_policy is None
                else {
                    "mode": step.join_policy.mode.value,
                    "failure_policy": step.join_policy.failure_policy.value,
                    "quorum": step.join_policy.quorum,
                },
                "max_attempts": step.max_attempts,
                "timeout_seconds": step.timeout_seconds,
            }
            for step in definition.steps
        ],
    }


def _stable_hash(value: dict[str, Any]) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _require_id(field: str, value: str) -> None:
    if not value.strip():
        raise WorkflowValidationError("BLANK_ID", f"{field} must not be blank")
