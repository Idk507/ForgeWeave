"""Build native-loop model input from assembled context inputs."""

from __future__ import annotations

from dataclasses import dataclass

from typing import TYPE_CHECKING

from forgeweave.context.assembler import ContextAssembler, ContextBudget, ContextItem
from forgeweave.context.instructions import ResolvedInstruction
from forgeweave.contracts import ConstraintLedger, FidelityMode

if TYPE_CHECKING:
    from forgeweave.context.model_input import ContextModelInput


@dataclass(frozen=True)
class NativeLoopContextRequest:
    """Inputs needed to assemble one native-loop model request."""

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
    latest_user_request: str
    constraint_ledger: ConstraintLedger
    instructions: tuple[ResolvedInstruction, ...]
    optional_items: tuple[ContextItem, ...]
    budget: ContextBudget
    user_message: str | None = None
    fidelity: FidelityMode = FidelityMode.REDACTED
    summary_lineage: tuple[str, ...] = ()


class NativeLoopContextBuilder:
    """Assemble context and convert it into native-loop model input."""

    def __init__(self, assembler: ContextAssembler | None = None) -> None:
        self._assembler = assembler or ContextAssembler()

    def build(self, request: NativeLoopContextRequest) -> "ContextModelInput":
        """Build provider-ready model input for one native loop turn."""

        if request.constraint_ledger.task_id != request.task_id:
            raise ValueError("constraint ledger task_id must match context request task_id")
        from forgeweave.context.model_input import ContextModelInput

        packet = self._assembler.assemble(
            request_id=request.request_id,
            task_id=request.task_id,
            attempt_id=request.attempt_id,
            provider=request.provider,
            model=request.model,
            adapter_version=request.adapter_version,
            effective_policy_hash=request.effective_policy_hash,
            effective_config_hash=request.effective_config_hash,
            workspace_revision=request.workspace_revision,
            catalog_version=request.catalog_version,
            latest_user_request=request.latest_user_request,
            constraint_ledger=request.constraint_ledger,
            instructions=request.instructions,
            optional_items=request.optional_items,
            budget=request.budget,
            fidelity=request.fidelity,
            summary_lineage=request.summary_lineage,
        )
        return ContextModelInput.from_packet(
            packet,
            user_message=request.user_message if request.user_message is not None else request.latest_user_request,
        )
