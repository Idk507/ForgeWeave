"""SQLite persistence for workflow definitions, runs and step attempts."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
from typing import Any

from .contracts import StepAttempt, WorkflowDefinition, WorkflowFailurePolicy, WorkflowRun, WorkflowRunStatus, WorkflowStepStatus


class WorkflowStoreError(ValueError):
    """Raised when workflow persistence rejects a state change."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class WorkflowStore:
    """SQLite store for durable workflow admission and resume state."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @classmethod
    def open(cls, path: Path) -> "WorkflowStore":
        """Open the workflow store and initialize schema."""

        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_definitions (
                definition_hash TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                definition_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_runs (
                run_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                definition_hash TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                run_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS step_attempts (
                attempt_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt_json TEXT NOT NULL,
                UNIQUE(run_id, idempotency_key)
            )
            """
        )
        connection.commit()
        return cls(connection)

    def close(self) -> None:
        """Close the store after checkpointing the WAL."""

        self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._connection.close()

    def record_definition(self, definition: WorkflowDefinition) -> WorkflowDefinition:
        """Persist an immutable workflow definition by stable definition hash."""

        payload = _definition_to_json(definition)
        existing = self._connection.execute(
            "SELECT definition_json FROM workflow_definitions WHERE definition_hash = ?",
            (definition.definition_hash,),
        ).fetchone()
        if existing is not None:
            if str(existing[0]) != payload:
                raise WorkflowStoreError("DEFINITION_HASH_COLLISION", "definition hash already exists with different payload")
            return definition
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO workflow_definitions(definition_hash, workflow_id, version, definition_json)
                VALUES (?, ?, ?, ?)
                """,
                (definition.definition_hash, definition.workflow_id, definition.version, payload),
            )
        return definition

    def get_definition(self, definition_hash: str) -> WorkflowDefinition:
        """Return one persisted workflow definition by hash."""

        row = self._connection.execute(
            "SELECT definition_json FROM workflow_definitions WHERE definition_hash = ?",
            (definition_hash,),
        ).fetchone()
        if row is None:
            raise KeyError(definition_hash)
        return _definition_from_json(str(row[0]))

    def list_definitions(self) -> tuple[WorkflowDefinition, ...]:
        """Return persisted workflow definitions ordered by workflow id and version."""

        rows = self._connection.execute(
            "SELECT definition_json FROM workflow_definitions ORDER BY workflow_id, version, definition_hash"
        ).fetchall()
        return tuple(_definition_from_json(str(row[0])) for row in rows)

    def admit_run(self, run: WorkflowRun) -> WorkflowRun:
        """Persist a workflow run bound to an already-recorded definition hash."""

        self.get_definition(run.definition_hash)
        payload = _run_to_json(run)
        existing = self._connection.execute("SELECT run_json FROM workflow_runs WHERE run_id = ?", (run.run_id,)).fetchone()
        if existing is not None:
            stored = _run_from_json(str(existing[0]))
            if stored != run:
                raise WorkflowStoreError("RUN_ID_CONFLICT", f"run already exists with different payload: {run.run_id}")
            return stored
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO workflow_runs(run_id, workflow_id, definition_hash, input_hash, status, run_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run.run_id, run.workflow_id, run.definition_hash, run.input_hash, run.status.value, payload),
            )
        return run

    def update_run_status(self, run_id: str, status: WorkflowRunStatus) -> WorkflowRun:
        """Update a workflow run status without changing definition/input binding."""

        run = self.get_run(run_id)
        updated = WorkflowRun(
            run_id=run.run_id,
            workflow_id=run.workflow_id,
            definition_hash=run.definition_hash,
            input_hash=run.input_hash,
            status=status,
        )
        with self._connection:
            self._connection.execute(
                "UPDATE workflow_runs SET status = ?, run_json = ? WHERE run_id = ?",
                (updated.status.value, _run_to_json(updated), run_id),
            )
        return updated

    def get_run(self, run_id: str) -> WorkflowRun:
        """Return one workflow run."""

        row = self._connection.execute("SELECT run_json FROM workflow_runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return _run_from_json(str(row[0]))

    def list_runs(self, *, workflow_id: str | None = None) -> tuple[WorkflowRun, ...]:
        """Return persisted workflow runs ordered by workflow id and run id."""

        if workflow_id is None:
            rows = self._connection.execute(
                "SELECT run_json FROM workflow_runs ORDER BY workflow_id, run_id"
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT run_json FROM workflow_runs WHERE workflow_id = ? ORDER BY workflow_id, run_id",
                (workflow_id,),
            ).fetchall()
        return tuple(_run_from_json(str(row[0])) for row in rows)

    def record_attempt(self, attempt: StepAttempt) -> StepAttempt:
        """Persist a step attempt idempotently by run/idempotency key."""

        self.get_run(attempt.run_id)
        payload = _attempt_to_json(attempt)
        existing = self._connection.execute(
            "SELECT attempt_json FROM step_attempts WHERE run_id = ? AND idempotency_key = ?",
            (attempt.run_id, attempt.idempotency_key),
        ).fetchone()
        if existing is not None:
            stored = _attempt_from_json(str(existing[0]))
            if stored != attempt:
                raise WorkflowStoreError("IDEMPOTENCY_CONFLICT", "idempotency key already exists with different attempt payload")
            return stored
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO step_attempts(attempt_id, run_id, step_id, idempotency_key, status, attempt_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (attempt.attempt_id, attempt.run_id, attempt.step_id, attempt.idempotency_key, attempt.status.value, payload),
            )
        return attempt

    def update_attempt_status(self, attempt_id: str, status: WorkflowStepStatus) -> StepAttempt:
        """Update a step attempt status while preserving idempotency and lease evidence."""

        attempt = self.get_attempt(attempt_id)
        updated = StepAttempt(
            attempt_id=attempt.attempt_id,
            run_id=attempt.run_id,
            step_id=attempt.step_id,
            idempotency_key=attempt.idempotency_key,
            lease_token=attempt.lease_token,
            status=status,
        )
        with self._connection:
            self._connection.execute(
                "UPDATE step_attempts SET status = ?, attempt_json = ? WHERE attempt_id = ?",
                (updated.status.value, _attempt_to_json(updated), attempt_id),
            )
        return updated

    def get_attempt(self, attempt_id: str) -> StepAttempt:
        """Return one step attempt."""

        row = self._connection.execute("SELECT attempt_json FROM step_attempts WHERE attempt_id = ?", (attempt_id,)).fetchone()
        if row is None:
            raise KeyError(attempt_id)
        return _attempt_from_json(str(row[0]))

    def list_attempts(self, run_id: str) -> tuple[StepAttempt, ...]:
        """Return step attempts for a run ordered by insertion key."""

        rows = self._connection.execute(
            "SELECT attempt_json FROM step_attempts WHERE run_id = ? ORDER BY attempt_id",
            (run_id,),
        ).fetchall()
        return tuple(_attempt_from_json(str(row[0])) for row in rows)


def _definition_to_json(definition: WorkflowDefinition) -> str:
    return json.dumps(_definition_payload(definition), sort_keys=True)


def _definition_from_json(text: str) -> WorkflowDefinition:
    payload = json.loads(text)
    return WorkflowDefinition(
        workflow_id=payload["workflow_id"],
        version=payload["version"],
        input_schema=payload["input_schema"],
        output_schema=payload["output_schema"],
        failure_policy=WorkflowFailurePolicy(payload["failure_policy"]),
        schema_version=payload["schema_version"],
        steps=tuple(_step_from_payload(item) for item in payload["steps"]),
    )


def _definition_payload(definition: WorkflowDefinition) -> dict[str, Any]:
    from .contracts import _definition_payload as contract_payload

    return contract_payload(definition)


def _step_from_payload(payload: dict[str, Any]):
    from .contracts import JoinMode, JoinPolicy, WorkflowFailurePolicy, WorkflowStep, WorkflowStepKind

    join = payload.get("join_policy")
    return WorkflowStep(
        step_id=payload["step_id"],
        kind=WorkflowStepKind(payload["kind"]),
        depends_on=tuple(payload["depends_on"]),
        capability=payload.get("capability"),
        parameters=payload.get("parameters") or None,
        join_policy=None
        if join is None
        else JoinPolicy(
            mode=JoinMode(join["mode"]),
            failure_policy=WorkflowFailurePolicy(join["failure_policy"]),
            quorum=join.get("quorum"),
        ),
        max_attempts=payload["max_attempts"],
        timeout_seconds=payload.get("timeout_seconds"),
    )


def _run_to_json(run: WorkflowRun) -> str:
    return json.dumps({**asdict(run), "status": run.status.value}, sort_keys=True)


def _run_from_json(text: str) -> WorkflowRun:
    payload = json.loads(text)
    return WorkflowRun(
        run_id=payload["run_id"],
        workflow_id=payload["workflow_id"],
        definition_hash=payload["definition_hash"],
        input_hash=payload["input_hash"],
        status=WorkflowRunStatus(payload["status"]),
    )


def _attempt_to_json(attempt: StepAttempt) -> str:
    return json.dumps({**asdict(attempt), "status": attempt.status.value}, sort_keys=True)


def _attempt_from_json(text: str) -> StepAttempt:
    payload = json.loads(text)
    return StepAttempt(
        attempt_id=payload["attempt_id"],
        run_id=payload["run_id"],
        step_id=payload["step_id"],
        idempotency_key=payload["idempotency_key"],
        lease_token=payload.get("lease_token"),
        status=WorkflowStepStatus(payload["status"]),
    )
