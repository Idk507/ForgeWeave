"""Factory for constructing verified tool execution from local configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from forgeweave.verify.execution import AnalyzerExecutionConfig, VerifiedToolExecutor
from forgeweave.verify.gate import RegressionGate
from forgeweave.verify.regression import RetryBudget
from forgeweave.verify.ruff import RuffAnalyzerAdapter
from forgeweave.verify.snapshots import GitSnapshotStore


@dataclass(frozen=True)
class VerifiedExecutorConfig:
    """Safe local configuration for verified mutating-tool execution."""

    repo_root: Path
    snapshot_dir: Path
    targets: tuple[Path, ...]
    config_hash: str
    retry_attempts: int = 3
    timeout_seconds: int = 60
    ruff_executable: str = "ruff"
    ruff_rules: tuple[str, ...] = ("ALL",)

    def __post_init__(self) -> None:
        if not self.targets:
            raise ValueError("targets must not be empty")
        if not self.config_hash.strip():
            raise ValueError("config_hash must not be blank")
        if self.retry_attempts < 1:
            raise ValueError("retry_attempts must be >= 1")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be >= 1")
        if not self.ruff_executable.strip():
            raise ValueError("ruff_executable must not be blank")
        if not self.ruff_rules:
            raise ValueError("ruff_rules must not be empty")


class VerifiedExecutorFactory:
    """Build a configured `VerifiedToolExecutor` for native loop dispatch."""

    def build(self, config: VerifiedExecutorConfig) -> VerifiedToolExecutor:
        """Construct snapshot, analyzer and regression-gate dependencies."""

        repo_root = config.repo_root.resolve()
        snapshot_dir = config.snapshot_dir.resolve()
        targets = tuple(_resolve_target(repo_root, target) for target in config.targets)
        return VerifiedToolExecutor(
            snapshot_store=GitSnapshotStore(snapshot_dir=snapshot_dir),
            analyzers=(
                RuffAnalyzerAdapter(
                    executable=config.ruff_executable,
                    selected_rules=config.ruff_rules,
                ),
            ),
            regression_gate=RegressionGate(retry_budget=RetryBudget(config.retry_attempts)),
            analyzer_config=AnalyzerExecutionConfig(
                repo_root=repo_root,
                targets=targets,
                config_hash=config.config_hash,
                timeout_seconds=config.timeout_seconds,
            ),
        )


def build_verified_executor(
    *,
    repo_root: Path,
    snapshot_dir: Path,
    targets: Sequence[Path],
    config_hash: str,
    retry_attempts: int = 3,
    timeout_seconds: int = 60,
    ruff_executable: str = "ruff",
    ruff_rules: tuple[str, ...] = ("ALL",),
) -> VerifiedToolExecutor:
    """Convenience function for CLI/task setup callers."""

    return VerifiedExecutorFactory().build(
        VerifiedExecutorConfig(
            repo_root=repo_root,
            snapshot_dir=snapshot_dir,
            targets=tuple(targets),
            config_hash=config_hash,
            retry_attempts=retry_attempts,
            timeout_seconds=timeout_seconds,
            ruff_executable=ruff_executable,
            ruff_rules=ruff_rules,
        )
    )


def _resolve_target(repo_root: Path, target: Path) -> Path:
    return target if target.is_absolute() else repo_root / target
