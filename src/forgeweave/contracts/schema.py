"""JSON Schema export helpers for ForgeWeave contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeAlias

from pydantic import BaseModel

from .core import (
    Artifact,
    Attempt,
    EffectSet,
    Event,
    PolicyDecision,
    Session,
    Step,
    Task,
    ToolCall,
    ToolFailure,
    ToolResult,
    ToolSpec,
    Turn,
    Worktree,
)
from .operational import (
    AcceptanceCriterion,
    AcceptanceSpec,
    ApprovalGrant,
    BudgetLedger,
    BudgetReservation,
    ConstraintLedger,
    ContextManifest,
    ContextSpan,
    ExecutionProfile,
    IsolationClaim,
    SummaryRecord,
    ToolExecution,
    VerificationRun,
)

ContractModel: TypeAlias = type[BaseModel]


def schema_models() -> tuple[ContractModel, ...]:
    """Return every contract model exported as JSON Schema."""

    return (
        Task,
        Attempt,
        Session,
        Turn,
        Step,
        Event,
        Artifact,
        Worktree,
        EffectSet,
        ToolSpec,
        ToolCall,
        ToolResult,
        ToolFailure,
        PolicyDecision,
        AcceptanceCriterion,
        ConstraintLedger,
        ContextSpan,
        ContextManifest,
        SummaryRecord,
        ApprovalGrant,
        IsolationClaim,
        ExecutionProfile,
        ToolExecution,
        BudgetReservation,
        BudgetLedger,
        AcceptanceSpec,
        VerificationRun,
    )


def schema_filename(model: ContractModel) -> str:
    """Return a stable kebab-case schema filename for a model."""

    chars: list[str] = []
    for index, char in enumerate(model.__name__):
        if char.isupper() and index > 0:
            chars.append("-")
        chars.append(char.lower())
    return "".join(chars) + ".schema.json"


def export_contract_schemas(output_dir: Path) -> tuple[Path, ...]:
    """Write contract schemas to `output_dir` and return written paths."""

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for model in schema_models():
        path = output_dir / schema_filename(model)
        schema = model.model_json_schema()
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return tuple(written)
