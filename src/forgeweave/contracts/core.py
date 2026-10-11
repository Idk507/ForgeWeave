"""Core versioned contracts for tasks, events, tools and workspace records."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .operational import FrozenModel


def _now() -> datetime:
    return datetime.now(UTC)


class TaskStatus(str, Enum):
    """Canonical task lifecycle states."""

    CREATED = "CREATED"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AttemptStatus(str, Enum):
    """Execution state for one resumable task attempt."""

    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    """Fine-grained unit status inside one attempt."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class EventKind(str, Enum):
    """Canonical event families persisted in the append-only log."""

    TASK_CREATED = "TaskCreated"
    TASK_STATE_CHANGED = "TaskStateChanged"
    ATTEMPT_STARTED = "AttemptStarted"
    TURN_RECORDED = "TurnRecorded"
    STEP_RECORDED = "StepRecorded"
    TOOL_CALL_REQUESTED = "ToolCallRequested"
    POLICY_DECISION = "PolicyDecision"
    TOOL_RESULT = "ToolResult"
    TOOL_FAILURE = "ToolFailure"
    ARTIFACT_RECORDED = "ArtifactRecorded"
    WORKTREE_RECORDED = "WorktreeRecorded"


class ActorKind(str, Enum):
    """Actor responsible for an event."""

    USER = "user"
    SYSTEM = "system"
    MODEL = "model"
    TOOL = "tool"
    POLICY = "policy"
    VERIFIER = "verifier"


class TurnRole(str, Enum):
    """Model conversation roles retained by the session log."""

    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class ArtifactKind(str, Enum):
    """Artifact payload categories."""

    TEXT = "text"
    JSON = "json"
    BINARY = "binary"
    PATCH = "patch"
    LOG = "log"


class WorktreeState(str, Enum):
    """Lifecycle for a task-owned worktree record."""

    ACTIVE = "active"
    LOCKED = "locked"
    PRESERVED = "preserved"
    CLEANED = "cleaned"


class PolicyOutcome(str, Enum):
    """Policy gateway decision for a validated tool call."""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class VersionedModel(FrozenModel):
    """Core contract base with a schema version."""

    schema_version: str

    @field_validator("schema_version")
    @classmethod
    def _schema_version_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("schema_version must not be blank")
        return value


class IdentifiedModel(VersionedModel):
    """Base for contracts with common non-empty string validation."""

    @field_validator("*")
    @classmethod
    def _strings_not_blank(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            raise ValueError("string fields must not be blank")
        return value


class Task(IdentifiedModel):
    """Top-level user objective."""

    task_id: str
    title: str
    status: TaskStatus = TaskStatus.CREATED
    created_at: datetime = Field(default_factory=_now)
    schema_version: str = "task.v1"


class Attempt(IdentifiedModel):
    """One execution attempt for a task; resume creates a new attempt."""

    attempt_id: str
    task_id: str
    status: AttemptStatus
    started_at: datetime = Field(default_factory=_now)
    completed_at: datetime | None = None
    schema_version: str = "attempt.v1"


class Session(IdentifiedModel):
    """Conversation/session root for a task."""

    session_id: str
    task_id: str
    created_at: datetime = Field(default_factory=_now)
    schema_version: str = "session.v1"


class Turn(IdentifiedModel):
    """One model-visible or user-visible conversation turn."""

    turn_id: str
    task_id: str
    attempt_id: str
    role: TurnRole
    content_ref: str
    context_manifest_id: str | None = None
    created_at: datetime = Field(default_factory=_now)
    schema_version: str = "turn.v1"


class Step(IdentifiedModel):
    """One planner/controller step inside an attempt."""

    step_id: str
    task_id: str
    attempt_id: str
    status: StepStatus
    objective: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    schema_version: str = "step.v1"


class Event(IdentifiedModel):
    """Append-only event identity envelope."""

    event_id: str
    task_id: str
    attempt_id: str
    sequence: int = Field(ge=1)
    occurred_at: datetime = Field(default_factory=_now)
    actor: ActorKind
    kind: EventKind
    correlation_id: str
    payload_ref: str
    schema_version: str = "event.v1"


class Artifact(IdentifiedModel):
    """Content-addressed task artifact metadata."""

    artifact_id: str
    task_id: str
    kind: ArtifactKind
    uri: str
    sha256: str
    size_bytes: int = Field(ge=0)
    redacted: bool = False
    retention: Literal["default", "exact-opt-in", "tombstone"] = "default"
    schema_version: str = "artifact.v1"


class Worktree(IdentifiedModel):
    """Task-owned Git worktree record."""

    worktree_id: str
    task_id: str
    repository_path: str
    worktree_path: str
    base_commit: str
    branch: str
    state: WorktreeState
    dirty: bool = False
    schema_version: str = "worktree.v1"


class EffectSet(FrozenModel):
    """Declared side effects for policy review."""

    reads: frozenset[str] = frozenset()
    writes: frozenset[str] = frozenset()
    network: frozenset[str] = frozenset()
    credentials: frozenset[str] = frozenset()
    process: frozenset[str] = frozenset()
    external: frozenset[str] = frozenset()

    @field_validator("reads", "writes", "network", "credentials", "process", "external", mode="before")
    @classmethod
    def _frozenset(cls, value: object) -> object:
        return frozenset(value) if isinstance(value, (list, set, tuple)) else value

    @property
    def is_read_only(self) -> bool:
        return not (self.writes or self.network or self.credentials or self.process or self.external)

    @property
    def fingerprint(self) -> str:
        parts: list[str] = []
        for name in ("reads", "writes", "network", "credentials", "process", "external"):
            values = sorted(getattr(self, name))
            parts.append(f"{name}={','.join(values)}")
        return "sha256:" + sha256("|".join(parts).encode("utf-8")).hexdigest()


class ToolSpec(IdentifiedModel):
    """Registered tool schema exposed to a model after policy/context filtering."""

    name: str
    description: str
    input_schema: dict[str, Any]
    effects: EffectSet = Field(default_factory=EffectSet)
    schema_version: str


class ToolCall(IdentifiedModel):
    """Validated model request to invoke one tool."""

    call_id: str
    tool_name: str
    tool_schema_version: str
    arguments: dict[str, Any]
    argument_hash: str
    effects: EffectSet
    schema_version: str = "tool-call.v1"

    @property
    def effect_hash(self) -> str:
        return self.effects.fingerprint


class ToolResult(IdentifiedModel):
    """Successful tool observation."""

    call_id: str
    output_ref: str
    output_hash: str
    schema_version: str = "tool-result.v1"


class ToolFailure(IdentifiedModel):
    """Failed tool observation with a bounded, non-secret message."""

    call_id: str
    error_type: str
    message: str
    retryable: bool = False
    schema_version: str = "tool-failure.v1"


class PolicyDecision(IdentifiedModel):
    """Decision made by the policy gateway for one tool call."""

    decision_id: str
    task_id: str
    attempt_id: str
    tool_call_id: str
    outcome: PolicyOutcome
    reason: str
    policy_revision: str
    approval_grant_id: str | None = None
    decided_at: datetime = Field(default_factory=_now)
    schema_version: str = "policy-decision.v1"

    @model_validator(mode="after")
    def _ask_decision_has_grant_or_reason(self) -> "PolicyDecision":
        if self.outcome is PolicyOutcome.ASK and self.approval_grant_id is not None:
            raise ValueError("ask decisions cannot already name an approval grant")
        return self
