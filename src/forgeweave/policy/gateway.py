"""Central policy gateway for validated tool calls.

The gateway does not parse paths, commands or URLs. Tool-specific validators own
that work in later slices; this module enforces the common decision boundary:
permission rules, action-bound approval consumption and dispatch-time
revalidation of the exact action shape that was approved.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from threading import Lock
from uuid import uuid4

from forgeweave.contracts import ApprovalGrant, PolicyDecision, PolicyOutcome, ToolCall


class ApprovalRequired(RuntimeError):
    """Raised when a caller tries to dispatch without an allow decision."""


class RevalidationError(RuntimeError):
    """Raised when the dispatch-time action no longer matches authorization."""


@dataclass(frozen=True)
class PolicyRule:
    """A shallow policy rule for a validated tool call.

    Full tool semantics belong to the tools package. This rule layer covers
    coarse allow/deny/ask decisions by tool name and declared read-only effects.
    """

    tool_name: str
    outcome: PolicyOutcome
    reason: str


@dataclass(frozen=True)
class _AuthorizedAction:
    task_id: str
    attempt_id: str
    tool_call_id: str
    tool_name: str
    tool_schema_version: str
    argument_hash: str
    effect_hash: str
    workspace_precondition_hash: str
    policy_revision: str

    @classmethod
    def from_call(
        cls,
        *,
        task_id: str,
        attempt_id: str,
        call: ToolCall,
        workspace_precondition_hash: str,
        policy_revision: str,
    ) -> "_AuthorizedAction":
        return cls(
            task_id=task_id,
            attempt_id=attempt_id,
            tool_call_id=call.call_id,
            tool_name=call.tool_name,
            tool_schema_version=call.tool_schema_version,
            argument_hash=call.argument_hash,
            effect_hash=call.effect_hash,
            workspace_precondition_hash=workspace_precondition_hash,
            policy_revision=policy_revision,
        )


class ApprovalStore:
    """Persistence boundary for human approval grants."""

    def put(self, grant: ApprovalGrant) -> ApprovalGrant:
        """Persist `grant` and return the stored grant."""

        raise NotImplementedError

    def consume_matching(
        self,
        *,
        task_id: str,
        attempt_id: str,
        tool_name: str,
        tool_schema_version: str,
        catalog_version: str,
        argument_hash: str,
        effect_hash: str,
        workspace_precondition_hash: str,
        policy_revision: str,
        now: datetime,
    ) -> ApprovalGrant | None:
        """Atomically consume and return a matching grant, if one exists."""

        raise NotImplementedError


class InMemoryApprovalStore(ApprovalStore):
    """Thread-safe approval store for unit tests and early local integration."""

    def __init__(self) -> None:
        self._grants: dict[str, ApprovalGrant] = {}
        self._lock = Lock()

    def put(self, grant: ApprovalGrant) -> ApprovalGrant:
        with self._lock:
            existing = self._grants.get(grant.grant_id)
            if existing is not None and existing != grant:
                raise ValueError(f"approval grant already exists with different content: {grant.grant_id}")
            self._grants[grant.grant_id] = grant
        return grant

    def consume_matching(
        self,
        *,
        task_id: str,
        attempt_id: str,
        tool_name: str,
        tool_schema_version: str,
        catalog_version: str,
        argument_hash: str,
        effect_hash: str,
        workspace_precondition_hash: str,
        policy_revision: str,
        now: datetime,
    ) -> ApprovalGrant | None:
        with self._lock:
            for grant in self._grants.values():
                if grant.task_id != task_id or grant.attempt_id != attempt_id:
                    continue
                if grant.tool_schema_version != tool_schema_version or grant.catalog_version != catalog_version:
                    continue
                if not grant.matches(
                    tool_name=tool_name,
                    argument_hash=argument_hash,
                    effect_hash=effect_hash,
                    workspace_precondition_hash=workspace_precondition_hash,
                    policy_revision=policy_revision,
                    now=now,
                ):
                    continue
                consumed = grant.consume(at=now)
                self._grants[grant.grant_id] = consumed
                return consumed
        return None


class SQLiteApprovalStore(ApprovalStore):
    """SQLite-backed approval store for local durable authorization grants."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @classmethod
    def open(cls, path: Path) -> "SQLiteApprovalStore":
        """Open or initialize an approval database."""

        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_grants (
                grant_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                consumed_at TEXT,
                grant_json TEXT NOT NULL
            )
            """
        )
        connection.commit()
        return cls(connection)

    def close(self) -> None:
        self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._connection.close()

    def put(self, grant: ApprovalGrant) -> ApprovalGrant:
        existing = self._connection.execute(
            "SELECT grant_json FROM approval_grants WHERE grant_id = ?",
            (grant.grant_id,),
        ).fetchone()
        if existing is not None:
            stored = ApprovalGrant.model_validate_json(existing[0])
            if stored != grant:
                raise ValueError(f"approval grant already exists with different content: {grant.grant_id}")
            return stored

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO approval_grants(grant_id, task_id, attempt_id, tool_name, consumed_at, grant_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    grant.grant_id,
                    grant.task_id,
                    grant.attempt_id,
                    grant.tool_name,
                    _datetime_to_text(grant.consumed_at),
                    grant.model_dump_json(),
                ),
            )
        return grant

    def consume_matching(
        self,
        *,
        task_id: str,
        attempt_id: str,
        tool_name: str,
        tool_schema_version: str,
        catalog_version: str,
        argument_hash: str,
        effect_hash: str,
        workspace_precondition_hash: str,
        policy_revision: str,
        now: datetime,
    ) -> ApprovalGrant | None:
        with self._connection:
            rows = self._connection.execute(
                """
                SELECT grant_json FROM approval_grants
                WHERE task_id = ? AND attempt_id = ? AND tool_name = ?
                ORDER BY grant_id
                """,
                (task_id, attempt_id, tool_name),
            ).fetchall()
            for row in rows:
                grant = ApprovalGrant.model_validate_json(row[0])
                if grant.tool_schema_version != tool_schema_version or grant.catalog_version != catalog_version:
                    continue
                if not grant.matches(
                    tool_name=tool_name,
                    argument_hash=argument_hash,
                    effect_hash=effect_hash,
                    workspace_precondition_hash=workspace_precondition_hash,
                    policy_revision=policy_revision,
                    now=now,
                ):
                    continue
                consumed = grant.consume(at=now)
                cursor = self._connection.execute(
                    """
                    UPDATE approval_grants
                    SET consumed_at = ?, grant_json = ?
                    WHERE grant_id = ? AND consumed_at IS NULL
                    """,
                    (_datetime_to_text(consumed.consumed_at), consumed.model_dump_json(), consumed.grant_id),
                )
                if cursor.rowcount != 1:
                    continue
                return consumed
        return None


class PolicyGateway:
    """Authorize tool calls and revalidate them immediately before dispatch."""

    def __init__(
        self,
        *,
        policy_revision: str,
        rules: tuple[PolicyRule, ...] = (),
        approvals: ApprovalStore | None = None,
    ) -> None:
        if not policy_revision.strip():
            raise ValueError("policy_revision must not be blank")
        self.policy_revision = policy_revision
        self._rules = rules
        self._approvals = approvals or InMemoryApprovalStore()
        self._authorized_actions: dict[str, _AuthorizedAction] = {}

    def authorize(
        self,
        *,
        task_id: str,
        attempt_id: str,
        call: ToolCall,
        workspace_precondition_hash: str,
        catalog_version: str = "tools-v1",
        now: datetime | None = None,
    ) -> PolicyDecision:
        """Return an allow, deny or ask decision for one validated call."""

        effective_now = now or datetime.now(UTC)
        rule = self._rule_for(call)
        if rule is not None and rule.outcome is PolicyOutcome.DENY:
            return self._decision(
                task_id=task_id,
                attempt_id=attempt_id,
                call=call,
                outcome=PolicyOutcome.DENY,
                reason=rule.reason,
            )
        if rule is not None and rule.outcome is PolicyOutcome.ALLOW:
            return self._allow(
                task_id=task_id,
                attempt_id=attempt_id,
                call=call,
                workspace_precondition_hash=workspace_precondition_hash,
                reason=rule.reason,
            )
        if call.effects.is_read_only:
            return self._allow(
                task_id=task_id,
                attempt_id=attempt_id,
                call=call,
                workspace_precondition_hash=workspace_precondition_hash,
                reason="read-only tool call allowed",
            )

        grant = self._approvals.consume_matching(
            task_id=task_id,
            attempt_id=attempt_id,
            tool_name=call.tool_name,
            tool_schema_version=call.tool_schema_version,
            catalog_version=catalog_version,
            argument_hash=call.argument_hash,
            effect_hash=call.effect_hash,
            workspace_precondition_hash=workspace_precondition_hash,
            policy_revision=self.policy_revision,
            now=effective_now,
        )
        if grant is not None:
            return self._allow(
                task_id=task_id,
                attempt_id=attempt_id,
                call=call,
                workspace_precondition_hash=workspace_precondition_hash,
                reason="approved matching action grant",
                approval_grant_id=grant.grant_id,
            )

        return self._decision(
            task_id=task_id,
            attempt_id=attempt_id,
            call=call,
            outcome=PolicyOutcome.ASK,
            reason="approval required for state-changing tool call",
        )

    def revalidate_for_dispatch(
        self,
        *,
        decision: PolicyDecision,
        call: ToolCall,
        workspace_precondition_hash: str,
    ) -> None:
        """Ensure the action being dispatched is still the action authorized."""

        if decision.outcome is not PolicyOutcome.ALLOW:
            raise ApprovalRequired("only allow decisions can dispatch")
        action = self._authorized_actions.get(decision.decision_id)
        if action is None:
            raise RevalidationError("authorization record is unavailable for dispatch")
        current = _AuthorizedAction.from_call(
            task_id=decision.task_id,
            attempt_id=decision.attempt_id,
            call=call,
            workspace_precondition_hash=workspace_precondition_hash,
            policy_revision=self.policy_revision,
        )
        if action != current:
            raise RevalidationError("dispatch action no longer matches policy authorization")

    def _rule_for(self, call: ToolCall) -> PolicyRule | None:
        for rule in self._rules:
            if rule.tool_name == call.tool_name:
                return rule
        return None

    def _allow(
        self,
        *,
        task_id: str,
        attempt_id: str,
        call: ToolCall,
        workspace_precondition_hash: str,
        reason: str,
        approval_grant_id: str | None = None,
    ) -> PolicyDecision:
        decision = self._decision(
            task_id=task_id,
            attempt_id=attempt_id,
            call=call,
            outcome=PolicyOutcome.ALLOW,
            reason=reason,
            approval_grant_id=approval_grant_id,
        )
        self._authorized_actions[decision.decision_id] = _AuthorizedAction.from_call(
            task_id=task_id,
            attempt_id=attempt_id,
            call=call,
            workspace_precondition_hash=workspace_precondition_hash,
            policy_revision=self.policy_revision,
        )
        return decision

    def _decision(
        self,
        *,
        task_id: str,
        attempt_id: str,
        call: ToolCall,
        outcome: PolicyOutcome,
        reason: str,
        approval_grant_id: str | None = None,
    ) -> PolicyDecision:
        return PolicyDecision(
            decision_id=f"policy-{uuid4()}",
            task_id=task_id,
            attempt_id=attempt_id,
            tool_call_id=call.call_id,
            outcome=outcome,
            reason=reason,
            policy_revision=self.policy_revision,
            approval_grant_id=approval_grant_id,
        )


def _datetime_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
