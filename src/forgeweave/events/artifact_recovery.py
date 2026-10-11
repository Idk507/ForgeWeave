"""Artifact publication recovery ledger for post-tool crash reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
import json


class ArtifactPublicationState(str, Enum):
    """Durable publication states around tool-result event append."""

    STAGED = "STAGED"
    PUBLISHED = "PUBLISHED"
    MISSING = "MISSING"
    CORRUPT = "CORRUPT"


@dataclass(frozen=True)
class ArtifactPublication:
    """One artifact publication intent or reconciled result."""

    publication_id: str
    task_id: str
    attempt_id: str
    call_id: str
    artifact_uri: str
    expected_sha256: str
    state: ArtifactPublicationState
    evidence: str | None = None

    def __post_init__(self) -> None:
        for field, value in (
            ("publication_id", self.publication_id),
            ("task_id", self.task_id),
            ("attempt_id", self.attempt_id),
            ("call_id", self.call_id),
            ("artifact_uri", self.artifact_uri),
            ("expected_sha256", self.expected_sha256),
        ):
            if not value.strip():
                raise ValueError(f"{field} must not be blank")
        if self.state in {ArtifactPublicationState.MISSING, ArtifactPublicationState.CORRUPT} and not self.evidence:
            raise ValueError("unrecoverable artifact states require evidence")


class ArtifactPublicationLedger:
    """Persist artifact publication intents as JSON files for restart recovery."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def stage(
        self,
        *,
        task_id: str,
        attempt_id: str,
        call_id: str,
        artifact_path: Path,
        expected_sha256: str | None = None,
    ) -> ArtifactPublication:
        """Record artifact publication intent before appending the tool result."""

        artifact = artifact_path.resolve()
        digest = expected_sha256 or _file_sha256(artifact)
        publication = ArtifactPublication(
            publication_id=_publication_id(task_id=task_id, attempt_id=attempt_id, call_id=call_id, artifact_uri=str(artifact)),
            task_id=task_id,
            attempt_id=attempt_id,
            call_id=call_id,
            artifact_uri=str(artifact),
            expected_sha256=digest,
            state=ArtifactPublicationState.STAGED,
        )
        return self._write(publication)

    def mark_published(self, publication_id: str) -> ArtifactPublication:
        """Mark a staged publication as committed after the corresponding event append."""

        publication = self.get(publication_id)
        if publication.state is not ArtifactPublicationState.STAGED:
            raise ValueError("only staged artifact publications can be marked published")
        return self._write(_replace(publication, state=ArtifactPublicationState.PUBLISHED, evidence=None))

    def reconcile_staged(self) -> tuple[ArtifactPublication, ...]:
        """Reconcile staged publications after restart without replaying side effects."""

        reconciled: list[ArtifactPublication] = []
        for publication in self.list(state=ArtifactPublicationState.STAGED):
            artifact = Path(publication.artifact_uri)
            if not artifact.exists():
                reconciled.append(
                    self._write(
                        _replace(
                            publication,
                            state=ArtifactPublicationState.MISSING,
                            evidence="artifact file missing during restart reconciliation",
                        )
                    )
                )
                continue
            actual = _file_sha256(artifact)
            if actual != publication.expected_sha256:
                reconciled.append(
                    self._write(
                        _replace(
                            publication,
                            state=ArtifactPublicationState.CORRUPT,
                            evidence=f"artifact hash mismatch: expected {publication.expected_sha256}, actual {actual}",
                        )
                    )
                )
                continue
            reconciled.append(
                self._write(
                    _replace(
                        publication,
                        state=ArtifactPublicationState.PUBLISHED,
                        evidence="artifact exists with expected hash during restart reconciliation",
                    )
                )
            )
        return tuple(reconciled)

    def get(self, publication_id: str) -> ArtifactPublication:
        path = self.root / f"{publication_id}.json"
        if not path.exists():
            raise KeyError(publication_id)
        return _from_json(path.read_text(encoding="utf-8"))

    def list(self, *, state: ArtifactPublicationState | None = None) -> tuple[ArtifactPublication, ...]:
        publications = tuple(_from_json(path.read_text(encoding="utf-8")) for path in sorted(self.root.glob("*.json")))
        if state is None:
            return publications
        return tuple(publication for publication in publications if publication.state is state)

    def _write(self, publication: ArtifactPublication) -> ArtifactPublication:
        path = self.root / f"{publication.publication_id}.json"
        existing = _from_json(path.read_text(encoding="utf-8")) if path.exists() else None
        if existing is not None:
            _validate_identity(existing, publication)
        path.write_text(_to_json(publication), encoding="utf-8")
        return publication


def _replace(publication: ArtifactPublication, **updates: object) -> ArtifactPublication:
    values = publication.__dict__.copy()
    values.update(updates)
    return ArtifactPublication(**values)


def _validate_identity(existing: ArtifactPublication, incoming: ArtifactPublication) -> None:
    if (
        existing.task_id != incoming.task_id
        or existing.attempt_id != incoming.attempt_id
        or existing.call_id != incoming.call_id
        or existing.artifact_uri != incoming.artifact_uri
        or existing.expected_sha256 != incoming.expected_sha256
    ):
        raise ValueError(f"artifact publication identity changed: {incoming.publication_id}")


def _publication_id(*, task_id: str, attempt_id: str, call_id: str, artifact_uri: str) -> str:
    payload = "|".join((task_id, attempt_id, call_id, artifact_uri))
    return "artifact-publication-" + sha256(payload.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        raise ValueError(f"artifact path does not exist or is not a file: {path}")
    return "sha256:" + sha256(path.read_bytes()).hexdigest()


def _to_json(publication: ArtifactPublication) -> str:
    payload = {**publication.__dict__, "state": publication.state.value}
    return json.dumps(payload, sort_keys=True)


def _from_json(text: str) -> ArtifactPublication:
    payload = json.loads(text)
    payload["state"] = ArtifactPublicationState(payload["state"])
    return ArtifactPublication(**payload)
