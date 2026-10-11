"""SQLite event store and content-addressed artifact storage."""

from __future__ import annotations

import sqlite3
from hashlib import sha256
from pathlib import Path

from forgeweave.contracts import Artifact, ArtifactKind, Event, ToolExecution, ToolExecutionState

from .migrations import MigrationStep


class EventStore:
    """Append-only local event store using SQLite WAL mode."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @classmethod
    def open(cls, path: Path) -> "EventStore":
        """Open a store and initialize the current schema."""

        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                event_json TEXT NOT NULL,
                event_hash TEXT NOT NULL,
                UNIQUE(task_id, sequence)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS event_migrations (
                step_id TEXT PRIMARY KEY,
                from_version TEXT NOT NULL,
                to_version TEXT NOT NULL,
                step_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tool_executions (
                execution_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                attempt_id TEXT NOT NULL,
                state TEXT NOT NULL,
                execution_json TEXT NOT NULL
            )
            """
        )
        connection.commit()
        return cls(connection)

    def close(self) -> None:
        self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._connection.close()

    def journal_mode(self) -> str:
        """Return SQLite's effective journal mode for diagnostics/tests."""

        return str(self._connection.execute("PRAGMA journal_mode").fetchone()[0])

    def append(self, event: Event) -> Event:
        """Append `event`, assigning the next sequence for its task.

        Re-delivering the same event id with identical content is idempotent.
        Reusing the id for different content is rejected.
        """

        existing = self._connection.execute(
            "SELECT event_json, event_hash FROM events WHERE event_id = ?",
            (event.event_id,),
        ).fetchone()
        if existing is not None:
            stored_json, stored_hash = existing
            stored_event = Event.model_validate_json(stored_json)
            incoming = event.model_copy(update={"sequence": stored_event.sequence}).model_dump_json()
            if _hash_text(incoming) != stored_hash:
                raise ValueError(f"event_id already exists with different content: {event.event_id}")
            return stored_event

        with self._connection:
            next_sequence = self._next_sequence(event.task_id)
            stored = event.model_copy(update={"sequence": next_sequence})
            event_json = stored.model_dump_json()
            self._connection.execute(
                """
                INSERT INTO events(event_id, task_id, attempt_id, sequence, event_json, event_hash)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    stored.event_id,
                    stored.task_id,
                    stored.attempt_id,
                    stored.sequence,
                    event_json,
                    _hash_text(event_json),
                ),
            )
        return stored

    def list_events(self, task_id: str) -> list[Event]:
        """Return events for one task ordered by sequence."""

        rows = self._connection.execute(
            "SELECT event_json FROM events WHERE task_id = ? ORDER BY sequence",
            (task_id,),
        ).fetchall()
        return [Event.model_validate_json(row[0]) for row in rows]

    def raw_event_json(self, event_id: str) -> str:
        """Return the stored event JSON exactly as committed."""

        row = self._connection.execute(
            "SELECT event_json FROM events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if row is None:
            raise KeyError(event_id)
        return str(row[0])

    def record_tool_execution(self, execution: ToolExecution) -> ToolExecution:
        """Store or update the restart-reconciliation projection for a tool call."""

        existing = self._connection.execute(
            "SELECT execution_json FROM tool_executions WHERE execution_id = ?",
            (execution.execution_id,),
        ).fetchone()
        if existing is not None:
            stored = ToolExecution.model_validate_json(existing[0])
            self._validate_tool_execution_update(stored, execution)

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO tool_executions(execution_id, task_id, attempt_id, state, execution_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(execution_id) DO UPDATE SET
                    state = excluded.state,
                    execution_json = excluded.execution_json
                """,
                (
                    execution.execution_id,
                    execution.task_id,
                    execution.attempt_id,
                    execution.state.value,
                    execution.model_dump_json(),
                ),
            )
        return execution

    def get_tool_execution(self, execution_id: str) -> ToolExecution:
        """Return the current execution projection for one tool call."""

        row = self._connection.execute(
            "SELECT execution_json FROM tool_executions WHERE execution_id = ?",
            (execution_id,),
        ).fetchone()
        if row is None:
            raise KeyError(execution_id)
        return ToolExecution.model_validate_json(row[0])

    def list_tool_executions(self, *, state: ToolExecutionState | None = None) -> list[ToolExecution]:
        """Return execution projections, optionally filtered by state."""

        if state is None:
            rows = self._connection.execute(
                "SELECT execution_json FROM tool_executions ORDER BY task_id, execution_id",
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT execution_json FROM tool_executions WHERE state = ? ORDER BY task_id, execution_id",
                (state.value,),
            ).fetchall()
        return [ToolExecution.model_validate_json(row[0]) for row in rows]

    def record_migration(self, step: MigrationStep) -> MigrationStep:
        """Record an applied migration step idempotently."""

        existing = self._connection.execute(
            "SELECT step_json FROM event_migrations WHERE step_id = ?",
            (step.step_id,),
        ).fetchone()
        if existing is not None:
            stored = MigrationStep.model_validate_json(existing[0])
            if stored != step:
                raise ValueError(f"migration step already exists with different content: {step.step_id}")
            return stored

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO event_migrations(step_id, from_version, to_version, step_json)
                VALUES (?, ?, ?, ?)
                """,
                (step.step_id, step.from_version, step.to_version, step.model_dump_json()),
            )
        return step

    def applied_migrations(self) -> list[MigrationStep]:
        """Return recorded migration steps ordered by insertion key."""

        rows = self._connection.execute(
            "SELECT step_json FROM event_migrations ORDER BY step_id",
        ).fetchall()
        return [MigrationStep.model_validate_json(row[0]) for row in rows]

    def publish_migration_successor(
        self,
        *,
        source_event_id: str,
        successor_event_id: str,
        to_schema_version: str,
        payload_ref: str,
        migration_step: MigrationStep,
    ) -> Event:
        """Publish a successor event beside a committed source event."""

        source = Event.model_validate_json(self.raw_event_json(source_event_id))
        if migration_step.to_version != to_schema_version:
            raise ValueError("successor schema version must match migration target")
        successor = source.model_copy(
            update={
                "event_id": successor_event_id,
                "sequence": 1,
                "payload_ref": payload_ref,
                "schema_version": to_schema_version,
            }
        )
        self.record_migration(migration_step)
        return self.append(successor)

    def _next_sequence(self, task_id: str) -> int:
        row = self._connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM events WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        return int(row[0])

    @staticmethod
    def _validate_tool_execution_update(stored: ToolExecution, incoming: ToolExecution) -> None:
        if (
            stored.task_id != incoming.task_id
            or stored.attempt_id != incoming.attempt_id
            or stored.tool_name != incoming.tool_name
            or stored.effect_hash != incoming.effect_hash
            or stored.idempotency_key != incoming.idempotency_key
        ):
            raise ValueError(f"tool execution identity changed: {incoming.execution_id}")
        if stored.state in {
            ToolExecutionState.SUCCEEDED,
            ToolExecutionState.FAILED,
            ToolExecutionState.CANCELLED,
            ToolExecutionState.OUTCOME_UNKNOWN,
        } and stored != incoming:
            raise ValueError(f"terminal tool execution cannot be changed: {incoming.execution_id}")


class ArtifactStore:
    """Task-scoped content-addressed artifact directory."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def put_bytes(self, *, task_id: str, kind: ArtifactKind, data: bytes, redacted: bool = False) -> Artifact:
        """Persist bytes under the task directory and return artifact metadata."""

        if not task_id.strip():
            raise ValueError("task_id must not be blank")
        digest = sha256(data).hexdigest()
        task_dir = self.root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        path = task_dir / digest
        if not path.exists():
            path.write_bytes(data)
        return Artifact(
            artifact_id=digest,
            task_id=task_id,
            kind=kind,
            uri=f"artifact://{task_id}/{digest}",
            sha256=digest,
            size_bytes=len(data),
            redacted=redacted,
        )

    def read_bytes(self, artifact: Artifact) -> bytes:
        """Read artifact bytes back from the local store."""

        path = self.root / artifact.task_id / artifact.sha256
        return path.read_bytes()


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()
