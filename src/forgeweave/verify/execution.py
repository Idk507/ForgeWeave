"""Verified tool execution with snapshot and analyzer regression gates."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from forgeweave.contracts import ToolCall
from forgeweave.verify.analyzers import AnalyzerAdapter, AnalyzerInvocation, AnalyzerResult
from forgeweave.verify.gate import RegressionGate, RegressionGateDecision
from forgeweave.verify.snapshots import GitSnapshot, GitSnapshotStore


@dataclass(frozen=True)
class VerifiedToolExecutionResult:
    """Tool output plus optional analyzer gate evidence for one dispatch."""

    output: Any
    before_snapshot: GitSnapshot | None
    after_snapshot: GitSnapshot | None
    before_results: tuple[AnalyzerResult, ...]
    after_results: tuple[AnalyzerResult, ...]
    gate_decision: RegressionGateDecision | None


@dataclass(frozen=True)
class AnalyzerExecutionConfig:
    """Configuration needed to run analyzers around mutating tool execution."""

    repo_root: Path
    targets: tuple[Path, ...]
    config_hash: str
    timeout_seconds: int = 60


class VerifiedToolExecutor:
    """Execute tool calls and gate mutating effects with analyzer regression checks."""

    def __init__(
        self,
        *,
        snapshot_store: GitSnapshotStore,
        analyzers: Sequence[AnalyzerAdapter],
        regression_gate: RegressionGate,
        analyzer_config: AnalyzerExecutionConfig,
    ) -> None:
        self.snapshot_store = snapshot_store
        self.analyzers = tuple(analyzers)
        self.regression_gate = regression_gate
        self.analyzer_config = analyzer_config

    def run(self, *, call: ToolCall, dispatch: Callable[[], Any]) -> VerifiedToolExecutionResult:
        """Dispatch a tool and run before/after analyzer gates for mutating calls."""

        if call.effects.is_read_only:
            return VerifiedToolExecutionResult(
                output=dispatch(),
                before_snapshot=None,
                after_snapshot=None,
                before_results=(),
                after_results=(),
                gate_decision=None,
            )

        before_snapshot = self.snapshot_store.claim(
            repo_root=self.analyzer_config.repo_root,
            snapshot_id=f"{call.call_id}-before",
        )
        before_results = self._run_analyzers()
        output = dispatch()
        after_snapshot = self.snapshot_store.claim(
            repo_root=self.analyzer_config.repo_root,
            snapshot_id=f"{call.call_id}-after",
        )
        after_results = self._run_analyzers()
        decision = self.regression_gate.evaluate(
            before=before_results,
            after=after_results,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )
        return VerifiedToolExecutionResult(
            output=output,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            before_results=before_results,
            after_results=after_results,
            gate_decision=decision,
        )

    def _run_analyzers(self) -> tuple[AnalyzerResult, ...]:
        invocation_base = self.analyzer_config
        results: list[AnalyzerResult] = []
        for analyzer in self.analyzers:
            results.append(
                analyzer.run(
                    AnalyzerInvocation(
                        analyzer=analyzer.name,
                        cwd=invocation_base.repo_root,
                        targets=invocation_base.targets,
                        config_hash=invocation_base.config_hash,
                        timeout_seconds=invocation_base.timeout_seconds,
                    )
                )
            )
        return tuple(results)
