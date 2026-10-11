"""Native ForgeWeave agent-loop primitives."""

from .control import BudgetExceeded, BudgetGuard, BudgetLimits, BudgetUsage, CancellationToken
from .diagnostics import LoopDiagnostics
from .dispatch import DispatchJob, DispatchPlanKind, DispatchPlanner, DispatchStage
from .completion import complete_from_selected_verification
from .task_completion import TaskCompletionResult, complete_repository_task
from .final_report import CheckSummary, FinalReport, build_final_report, render_final_report
from .loop import (
    LoopResult,
    ModelStreamAccumulator,
    NativeAgentLoop,
    StreamProtocolError,
    StreamResult,
    ToolRequest,
)
from .repair import RepairLoopController, RepairOrchestrator, RepairRunResult
from .stop import StopDecision, StopEvaluator, StopReason

__all__ = [
    "BudgetExceeded",
    "BudgetGuard",
    "BudgetLimits",
    "BudgetUsage",
    "CancellationToken",
    "CheckSummary",
    "DispatchJob",
    "complete_from_selected_verification",
    "complete_repository_task",
    "DispatchPlanKind",
    "DispatchPlanner",
    "DispatchStage",
    "FinalReport",
    "LoopDiagnostics",
    "LoopResult",
    "ModelStreamAccumulator",
    "NativeAgentLoop",
    "NativeLoopContextBuilder",
    "NativeLoopContextRequest",
    "build_final_report",
    "render_final_report",
    "RepairLoopController",
    "RepairOrchestrator",
    "RepairRunResult",
    "StopDecision",
    "StopEvaluator",
    "StopReason",
    "StreamProtocolError",
    "StreamResult",
    "TaskCompletionResult",
    "ToolRequest",
]


def __getattr__(name: str):
    if name in {"NativeLoopContextBuilder", "NativeLoopContextRequest"}:
        from .context import NativeLoopContextBuilder, NativeLoopContextRequest

        values = {
            "NativeLoopContextBuilder": NativeLoopContextBuilder,
            "NativeLoopContextRequest": NativeLoopContextRequest,
        }
        return values[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
