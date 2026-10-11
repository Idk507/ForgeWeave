"""SQLite persistence for task-owned Git worktree records."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from forgeweave.contracts import Worktree, WorktreeState


class WorkspaceStore:
    """Persist worktree projections in SQLite WAL mode."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @classmethod
    def open(cls, path: Path) -> "WorkspaceStore":
        """Open the workspace store and initialize the schema."""

        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS worktrees (
                worktree_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                repository_path TEXT NOT NULL,
                worktree_path TEXT NOT NULL,
                branch TEXT NOT NULL,
                state TEXT NOT NULL,
                worktree_json TEXT NOT NULL,
                UNIQUE(repository_path, branch),
                UNIQUE(worktree_path)
            )
            """
        )
        connection.commit()
        return cls(connection)

    def close(self) -> None:
        self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._connection.close()

    def record_worktree(
        self,
        *,
        worktree_id: str,
        task_id: str,
        repository_path: str,
        worktree_path: str,
        base_commit: str,
        branch: str,
        state: WorktreeState,
        dirty: bool = False,
    ) -> Worktree:
        """Persist a worktree record idempotently when identity fields match."""

        record = Worktree(
            worktree_id=worktree_id,
            task_id=task_id,
            repository_path=repository_path,
            worktree_path=worktree_path,
            base_commit=base_commit,
            branch=branch,
            state=state,
            dirty=dirty,
        )
        existing = self._row(worktree_id)
        if existing is not None:
            stored = Worktree.model_validate_json(existing)
            self._validate_same_identity(stored, record)
            return stored

        with self._connection:
            self._connection.execute(
                """
                INSERT INTO worktrees(worktree_id, task_id, repository_path, worktree_path, branch, state, worktree_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.worktree_id,
                    record.task_id,
                    record.repository_path,
                    record.worktree_path,
                    record.branch,
                    record.state.value,
                    record.model_dump_json(),
                ),
            )
        return record

    def get_worktree(self, worktree_id: str) -> Worktree:
        """Return one worktree record by ID."""

        row = self._row(worktree_id)
        if row is None:
            raise KeyError(worktree_id)
        return Worktree.model_validate_json(row)

    def list_worktrees(self, *, task_id: str | None = None) -> list[Worktree]:
        """List worktrees ordered by task and worktree ID."""

        if task_id is None:
            rows = self._connection.execute(
                "SELECT worktree_json FROM worktrees ORDER BY task_id, worktree_id",
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT worktree_json FROM worktrees WHERE task_id = ? ORDER BY worktree_id",
                (task_id,),
            ).fetchall()
        return [Worktree.model_validate_json(row[0]) for row in rows]

    def update_state(self, worktree_id: str, *, state: WorktreeState, dirty: bool | None = None) -> Worktree:
        """Update lifecycle state and dirty projection without changing identity."""

        current = self.get_worktree(worktree_id)
        updated = current.model_copy(update={"state": state, "dirty": current.dirty if dirty is None else dirty})
        with self._connection:
            self._connection.execute(
                "UPDATE worktrees SET state = ?, worktree_json = ? WHERE worktree_id = ?",
                (updated.state.value, updated.model_dump_json(), updated.worktree_id),
            )
        return updated

    def _row(self, worktree_id: str) -> str | None:
        row = self._connection.execute(
            "SELECT worktree_json FROM worktrees WHERE worktree_id = ?",
            (worktree_id,),
        ).fetchone()
        return None if row is None else str(row[0])

    @staticmethod
    def _validate_same_identity(stored: Worktree, incoming: Worktree) -> None:
        if (
            stored.task_id != incoming.task_id
            or stored.repository_path != incoming.repository_path
            or stored.worktree_path != incoming.worktree_path
            or stored.base_commit != incoming.base_commit
            or stored.branch != incoming.branch
        ):
            raise ValueError(f"worktree identity changed: {incoming.worktree_id}")
