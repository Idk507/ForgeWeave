"""Context assembly primitives for ForgeWeave model requests."""

from forgeweave.context.assembler import ContextAssembler, ContextBudget, ContextFitError, ContextItem, ContextPacket
from forgeweave.context.instructions import (
    InstructionAuthority,
    InstructionContradictionError,
    InstructionResolver,
    InstructionSource,
    ResolvedInstruction,
)
from forgeweave.context.length_errors import (
    ContextLengthError,
    ContextLengthRecovery,
    ContextLengthRetryPlan,
    detect_context_length_error,
)
from forgeweave.context.model_input import ContextModelInput
from forgeweave.context.retrieval import RetrievalLedger, RetrievalLedgerEntry
from forgeweave.context.tool_results import ToolResultProjection, ToolResultProjector

__all__ = [
    "ContextAssembler",
    "ContextBudget",
    "ContextFitError",
    "ContextItem",
    "ContextLengthError",
    "ContextLengthRecovery",
    "ContextLengthRetryPlan",
    "ContextModelInput",
    "ContextPacket",
    "InstructionAuthority",
    "InstructionContradictionError",
    "InstructionResolver",
    "InstructionSource",
    "ResolvedInstruction",
    "RetrievalLedger",
    "RetrievalLedgerEntry",
    "ToolResultProjection",
    "ToolResultProjector",
    "detect_context_length_error",
]
