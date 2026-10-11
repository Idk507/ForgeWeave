"""Verification: regression policy, command evidence and repair guards."""

from .analyzers import AnalyzerAdapter, AnalyzerInvocation, AnalyzerResult
from .execution import AnalyzerExecutionConfig, VerifiedToolExecutionResult, VerifiedToolExecutor
from .factory import VerifiedExecutorConfig, VerifiedExecutorFactory, build_verified_executor
from .gate import RegressionGate, RegressionGateDecision
from .regression import Finding, RetryBudget, regressions
from .ruff import RuffAnalyzerAdapter
from .runner import RepairGuard, VerificationCommand, VerificationResult, VerificationRunner, repair_fingerprint
from .selected_runner import SelectedVerificationRun, run_selected_verification
from .selection import VerificationSelection, select_verification_commands
from .snapshots import GitSnapshot, GitSnapshotStore

__all__ = [
    "AnalyzerAdapter",
    "AnalyzerInvocation",
    "AnalyzerResult",
    "AnalyzerExecutionConfig",
    "Finding",
    "GitSnapshot",
    "GitSnapshotStore",
    "RegressionGate",
    "RegressionGateDecision",
    "RepairGuard",
    "RetryBudget",
    "RuffAnalyzerAdapter",
    "SelectedVerificationRun",
    "VerificationCommand",
    "VerificationResult",
    "VerificationRunner",
    "VerificationSelection",
    "VerifiedExecutorConfig",
    "VerifiedExecutorFactory",
    "VerifiedToolExecutionResult",
    "VerifiedToolExecutor",
    "regressions",
    "run_selected_verification",
    "select_verification_commands",
    "build_verified_executor",
    "repair_fingerprint",
]
