"""Retrieval ledger for file-backed context spans."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class RetrievalLedgerEntry(BaseModel):
    """Evidence that a file span was retrieved for context assembly."""

    model_config = ConfigDict(frozen=True)

    span_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    source_hash: str = Field(min_length=1)
    ledger_version: str = "retrieval-ledger.v1"


class RetrievalLedger:
    """Record and validate retrieved file spans against current workspace content."""

    def __init__(self, *, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def record_file_span(self, *, span_id: str, path: str, start_line: int, end_line: int) -> RetrievalLedgerEntry:
        """Record a source file span and the current full-file hash."""

        if end_line < start_line:
            raise ValueError("end_line must be greater than or equal to start_line")
        resolved = self._resolve_path(path)
        if not resolved.is_file():
            raise FileNotFoundError(str(resolved))
        return RetrievalLedgerEntry(
            span_id=span_id,
            path=self._relative_path(resolved),
            start_line=start_line,
            end_line=end_line,
            source_hash=self._file_hash(resolved),
        )

    def stale_entries(self, entries: list[RetrievalLedgerEntry] | tuple[RetrievalLedgerEntry, ...]) -> list[RetrievalLedgerEntry]:
        """Return entries whose file is missing or whose content hash changed."""

        stale: list[RetrievalLedgerEntry] = []
        for entry in entries:
            try:
                path = self._resolve_path(entry.path)
            except ValueError:
                stale.append(entry)
                continue
            if not path.is_file() or self._file_hash(path) != entry.source_hash:
                stale.append(entry)
        return stale

    def _resolve_path(self, path: str) -> Path:
        candidate = (self.workspace_root / path).resolve()
        if candidate != self.workspace_root and self.workspace_root not in candidate.parents:
            raise ValueError(f"path escapes workspace root: {path}")
        return candidate

    def _relative_path(self, path: Path) -> str:
        return path.relative_to(self.workspace_root).as_posix()

    @staticmethod
    def _file_hash(path: Path) -> str:
        return "sha256:" + sha256(path.read_bytes()).hexdigest()
