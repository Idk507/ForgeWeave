"""Operational contracts shared by context, policy, tools and verification.

These models encode the M0.R1 schema boundary from SYSTEM_DESIGN section 13.
They are intentionally persistence-agnostic; stores and CLIs can serialize them
without inheriting subsystem behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _now() -> datetime:
    return datetime.now(UTC)


class FrozenModel(BaseModel):
    """Common immutable Pydantic base for contracts."""

    model_config = ConfigDict(frozen=True)


class ConstraintStatus(str, Enum):
    """Lifecycle for an acceptance criterion or protected requirement."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"


class AcceptanceCriterion(FrozenModel):
    """Human-visible requirement with an explicit validator."""

    criterion_id: str
    text: str
    origin: str
    authority: str
    validator: str
    status: ConstraintStatus = ConstraintStatus.ACTIVE
    superseded_by: str | None = None
    created_at: datetime = Field(default_factory=_now)

    @field_validator("criterion_id", "text", "origin", "authority", "validator")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @model_validator(mode="after")
    def _supersession_matches_status(self) -> "AcceptanceCriterion":
        if self.status is ConstraintStatus.SUPERSEDED and not self.superseded_by:
            raise ValueError("superseded constraints must name their successor")
        if self.status is ConstraintStatus.ACTIVE and self.superseded_by:
            raise ValueError("active constraints cannot name a successor")
        return self


class ConstraintLedger(FrozenModel):
    """Protected requirement ledger; summaries may cite it but cannot rewrite it."""

    task_id: str
    constraints: tuple[AcceptanceCriterion, ...] = ()
    schema_version: str = "constraint-ledger.v1"

    @field_validator("constraints", mode="before")
    @classmethod
    def _tuple(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _unique_active_ids(self) -> "ConstraintLedger":
        active = [item.criterion_id for item in self.constraints if item.status is ConstraintStatus.ACTIVE]
        if len(active) != len(set(active)):
            raise ValueError("active constraint IDs must be unique")
        return self

    @property
    def active_ids(self) -> frozenset[str]:
        return frozenset(item.criterion_id for item in self.constraints if item.status is ConstraintStatus.ACTIVE)


class FidelityMode(str, Enum):
    """Replay fidelity promised by a context or audit record."""

    EXACT = "exact"
    REDACTED = "redacted"
    REFERENCE_ONLY = "reference-only"


class ContextSpan(FrozenModel):
    """One ordered unit selected into a model request."""

    span_id: str
    source: str
    source_hash: str
    authority: str
    sensitivity: str
    token_estimate: int = Field(ge=0)
    redacted: bool = False


class ContextManifest(FrozenModel):
    """Reconstructable manifest for a provider-bound model request."""

    request_id: str
    task_id: str
    attempt_id: str
    provider: str
    model: str
    adapter_version: str
    effective_policy_hash: str
    effective_config_hash: str
    workspace_revision: str
    catalog_version: str
    spans: tuple[ContextSpan, ...] = ()
    omitted_spans: tuple[str, ...] = ()
    summary_lineage: tuple[str, ...] = ()
    token_estimate: int = Field(ge=0)
    fidelity: FidelityMode = FidelityMode.REDACTED
    schema_version: str = "context-manifest.v1"

    @field_validator("spans", "omitted_spans", "summary_lineage", mode="before")
    @classmethod
    def _tuple(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @property
    def ordered_span_ids(self) -> tuple[str, ...]:
        return tuple(span.span_id for span in self.spans)


class SummaryRecord(FrozenModel):
    """Validated, disposable projection over lossless events."""

    summary_id: str
    task_id: str
    source_event_range: tuple[str, str]
    cited_decisions: tuple[str, ...] = ()
    unresolved_work: tuple[str, ...] = ()
    changed_file_hashes: dict[str, str] = Field(default_factory=dict)
    verification_fingerprint: str
    constraint_ledger_hash: str
    protected_constraint_ids: tuple[str, ...] = ()
    covered_constraint_ids: tuple[str, ...] = ()
    schema_version: str = "summary-record.v1"

    @field_validator("cited_decisions", "unresolved_work", "protected_constraint_ids", "covered_constraint_ids", mode="before")
    @classmethod
    def _tuple(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _covers_protected_constraints(self) -> "SummaryRecord":
        missing = set(self.protected_constraint_ids) - set(self.covered_constraint_ids)
        if missing:
            raise ValueError(f"summary does not cover protected constraints: {sorted(missing)}")
        return self


class ApprovalScope(str, Enum):
    """How many matching actions a grant can authorize."""

    ONE_ACTION = "one-action"
    BOUNDED_SESSION = "bounded-session"


class ApprovalGrant(FrozenModel):
    """Human authorization bound to one exact action shape."""

    grant_id: str
    task_id: str
    attempt_id: str
    tool_name: str
    tool_schema_version: str
    catalog_version: str
    argument_hash: str
    effect_hash: str
    workspace_precondition_hash: str
    policy_revision: str
    human_actor: str
    scope: ApprovalScope = ApprovalScope.ONE_ACTION
    expires_at: datetime
    consumed_at: datetime | None = None
    revoked_at: datetime | None = None

    def matches(
        self,
        *,
        tool_name: str,
        argument_hash: str,
        effect_hash: str,
        workspace_precondition_hash: str,
        policy_revision: str,
        now: datetime,
    ) -> bool:
        """Return whether this grant still authorizes the requested action."""

        if self.revoked_at is not None or self.expires_at <= now:
            return False
        if self.scope is ApprovalScope.ONE_ACTION and self.consumed_at is not None:
            return False
        return (
            self.tool_name == tool_name
            and self.argument_hash == argument_hash
            and self.effect_hash == effect_hash
            and self.workspace_precondition_hash == workspace_precondition_hash
            and self.policy_revision == policy_revision
        )

    def consume(self, *, at: datetime | None = None) -> "ApprovalGrant":
        """Return a consumed copy; storage will enforce the atomic write."""

        if self.consumed_at is not None:
            raise ValueError("approval grant is already consumed")
        return self.model_copy(update={"consumed_at": at or _now()})


class IsolationClaim(FrozenModel):
    """One independently reported containment dimension."""

    level: str
    backend: str
    measured: bool
    evidence: str | None = None


class ExecutionProfile(FrozenModel):
    """Effective execution limits; a worktree alone is not a sandbox."""

    profile_id: str
    filesystem: IsolationClaim
    network: IsolationClaim
    credentials: IsolationClaim
    process_tree: IsolationClaim
    resources: IsolationClaim

    @property
    def has_measured_restricted_execution(self) -> bool:
        claims = (self.filesystem, self.network, self.credentials, self.process_tree, self.resources)
        return all(claim.measured and claim.level not in {"host-user", "shared-egress"} for claim in claims)


class ToolExecutionState(str, Enum):
    """Execution-level state, separate from task lifecycle."""

    REQUESTED = "REQUESTED"
    AUTHORIZED = "AUTHORIZED"
    DISPATCHING = "DISPATCHING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class ToolExecution(FrozenModel):
    """Recorded tool invocation state used for restart reconciliation."""

    execution_id: str
    task_id: str
    attempt_id: str
    tool_name: str
    state: ToolExecutionState
    effect_hash: str
    idempotency_key: str
    reconciliation_evidence: str | None = None

    @model_validator(mode="after")
    def _unknown_outcome_has_evidence(self) -> "ToolExecution":
        if self.state is ToolExecutionState.OUTCOME_UNKNOWN and not self.reconciliation_evidence:
            raise ValueError("OUTCOME_UNKNOWN requires reconciliation evidence")
        return self


class BudgetReservation(FrozenModel):
    """Conservative reservation for a future or completed operation."""

    reservation_id: str
    purpose: str
    estimated_tokens: int = Field(ge=0)
    estimated_cost: float = Field(ge=0)
    actual_tokens: int | None = Field(default=None, ge=0)
    actual_cost: float | None = Field(default=None, ge=0)

    @property
    def is_reconciled(self) -> bool:
        return self.actual_tokens is not None and self.actual_cost is not None


class BudgetLedger(FrozenModel):
    """Token and money ledger that keeps missing usage reserved."""

    task_id: str
    currency: str
    price_source_version: str
    reservations: tuple[BudgetReservation, ...] = ()
    schema_version: str = "budget-ledger.v1"

    @field_validator("reservations", mode="before")
    @classmethod
    def _tuple(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @property
    def remaining_reserved_cost(self) -> float:
        return sum(item.estimated_cost for item in self.reservations if not item.is_reconciled)

    def reconcile(self, reservation_id: str, *, actual_tokens: int | None, actual_cost: float | None) -> "BudgetLedger":
        """Return a ledger copy with one reservation reconciled when full usage is known."""

        updated: list[BudgetReservation] = []
        found = False
        for item in self.reservations:
            if item.reservation_id != reservation_id:
                updated.append(item)
                continue
            found = True
            if actual_tokens is None or actual_cost is None:
                updated.append(item)
            else:
                updated.append(item.model_copy(update={"actual_tokens": actual_tokens, "actual_cost": actual_cost}))
        if not found:
            raise ValueError(f"unknown reservation: {reservation_id}")
        return self.model_copy(update={"reservations": tuple(updated)})


class AcceptanceSpec(FrozenModel):
    """Versioned set of completion criteria."""

    spec_id: str
    criteria: tuple[AcceptanceCriterion, ...]
    version: int = Field(default=1, ge=1)

    @field_validator("criteria", mode="before")
    @classmethod
    def _tuple(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @property
    def required_ids(self) -> frozenset[str]:
        return frozenset(item.criterion_id for item in self.criteria if item.status is ConstraintStatus.ACTIVE)


class VerificationRun(FrozenModel):
    """Evidence from one verifier execution over an exact workspace input."""

    run_id: str
    task_id: str
    criterion_ids: tuple[str, ...]
    command_argv: tuple[str, ...]
    cwd: str
    environment_profile_hash: str
    verifier_version: str
    config_hash: str
    workspace_fingerprint: str
    untracked_input_hashes: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int | None = Field(default=None, ge=1)
    duration_ms: float | None = Field(default=None, ge=0)
    exit_code: int | None = None
    output_artifact_id: str | None = None
    outcome: Literal["passed", "failed", "inconclusive"] = "passed"

    @field_validator("criterion_ids", "command_argv", mode="before")
    @classmethod
    def _tuple(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @property
    def whole_input_fingerprint(self) -> str:
        payload = "|".join(
            [
                self.workspace_fingerprint,
                self.environment_profile_hash,
                self.config_hash,
                *self.command_argv,
                *self.criterion_ids,
                *(f"{key}={value}" for key, value in sorted(self.untracked_input_hashes.items())),
            ]
        )
        return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()
