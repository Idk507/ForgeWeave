"""Event-store migration ledger contracts."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from pydantic import Field, field_validator, model_validator

from forgeweave.contracts.operational import FrozenModel


def _now() -> datetime:
    return datetime.now(UTC)


class MigrationStep(FrozenModel):
    """One adjacent schema migration step.

    Existing event JSON is immutable. A step records that a successor generation
    may be published beside the original.
    """

    step_id: str
    from_version: str
    to_version: str
    description: str
    applied_at: datetime = Field(default_factory=_now)

    @field_validator("step_id", "from_version", "to_version", "description")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @model_validator(mode="after")
    def _versions_are_adjacent(self) -> "MigrationStep":
        source = _version_number(self.from_version)
        target = _version_number(self.to_version)
        if source is None or target is None or target != source + 1:
            raise ValueError("migration steps must be adjacent vN -> vN+1")
        return self


def _version_number(value: str) -> int | None:
    match = re.search(r"\.v(\d+)$", value)
    return int(match.group(1)) if match else None
