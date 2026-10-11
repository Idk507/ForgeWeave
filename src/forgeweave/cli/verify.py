"""CLI helpers for verified dispatch configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Sequence

from forgeweave.verify import (
    SelectedVerificationRun,
    VerificationSelection,
    VerifiedExecutorConfig,
    VerifiedExecutorFactory,
    run_selected_verification,
    select_verification_commands,
)


@dataclass(frozen=True)
class SelectedVerificationRunView:
    """Safe projection of executed selected verification commands."""

    task_id: str
    passed: bool
    command_count: int
    failed_count: int
    config_hash: str
    workspace_fingerprint: str
    sources: tuple[str, ...]
    results: tuple[dict[str, object], ...]


def selected_verification_run_view(
    *,
    task_id: str,
    repo_root: Path,
    output_dir: Path,
    environment_profile_hash: str = "sha256:local",
    timeout_seconds: int = 60,
    output_cap_bytes: int = 64_000,
) -> SelectedVerificationRunView:
    """Run selected verification commands and project captured evidence."""

    run = run_selected_verification(
        task_id=task_id,
        repo_root=repo_root,
        output_dir=output_dir,
        environment_profile_hash=environment_profile_hash,
        timeout_seconds=timeout_seconds,
        output_cap_bytes=output_cap_bytes,
    )
    return _selected_run_view(run)


def render_selected_verification_run(view: SelectedVerificationRunView, *, as_json: bool) -> str:
    """Render executed selected verification results."""

    if as_json:
        return json.dumps(asdict(view), sort_keys=True)
    lines = [
        f"Task: {view.task_id}",
        f"Passed: {str(view.passed).lower()}",
        f"Commands: {view.command_count}",
        f"Failed: {view.failed_count}",
        f"Config hash: {view.config_hash}",
        f"Workspace fingerprint: {view.workspace_fingerprint}",
        "Results:",
    ]
    if not view.results:
        lines.append("- none")
    else:
        for result in view.results:
            lines.append(f"- {result['outcome']}: {' '.join(result['command_argv'])} ({result['run_id']})")
    return "\n".join(lines)


def _selected_run_view(run: SelectedVerificationRun) -> SelectedVerificationRunView:
    return SelectedVerificationRunView(
        task_id=run.task_id,
        passed=run.passed,
        command_count=len(run.results),
        failed_count=len(run.failed_results),
        config_hash=run.selection.config_hash,
        workspace_fingerprint=run.selection.workspace_fingerprint,
        sources=run.selection.sources,
        results=tuple(
            {
                "run_id": result.run.run_id,
                "criterion_ids": result.run.criterion_ids,
                "command_argv": result.run.command_argv,
                "cwd": result.run.cwd,
                "outcome": result.run.outcome,
                "exit_code": result.run.exit_code,
                "timed_out": result.timed_out,
                "duration_ms": result.run.duration_ms,
                "output_artifact_id": result.run.output_artifact_id,
                "whole_input_fingerprint": result.run.whole_input_fingerprint,
            }
            for result in run.results
        ),
    )


@dataclass(frozen=True)
class VerificationSelectionView:
    """Safe projection of selected verification commands."""

    repo_root: str
    config_hash: str
    workspace_fingerprint: str
    sources: tuple[str, ...]
    commands: tuple[dict[str, object], ...]


def verification_selection_view(
    *,
    repo_root: Path,
    environment_profile_hash: str = "sha256:local",
    timeout_seconds: int = 60,
) -> VerificationSelectionView:
    """Select and project verification commands without executing them."""

    selection = select_verification_commands(
        repo_root,
        environment_profile_hash=environment_profile_hash,
        timeout_seconds=timeout_seconds,
    )
    return _selection_view(repo_root.resolve(), selection)


def render_verification_selection(view: VerificationSelectionView, *, as_json: bool) -> str:
    """Render selected verification commands."""

    if as_json:
        return json.dumps(asdict(view), sort_keys=True)
    lines = [
        f"Repository root: {view.repo_root}",
        f"Config hash: {view.config_hash}",
        f"Workspace fingerprint: {view.workspace_fingerprint}",
        "Sources: " + (", ".join(view.sources) if view.sources else "none"),
        "Commands:",
    ]
    if not view.commands:
        lines.append("- none")
    else:
        for command in view.commands:
            lines.append("- " + " ".join(command["argv"]))
    return "\n".join(lines)


def _selection_view(repo_root: Path, selection: VerificationSelection) -> VerificationSelectionView:
    return VerificationSelectionView(
        repo_root=str(repo_root),
        config_hash=selection.config_hash,
        workspace_fingerprint=selection.workspace_fingerprint,
        sources=selection.sources,
        commands=tuple(
            {
                "criterion_ids": command.criterion_ids,
                "argv": command.argv,
                "cwd": str(command.cwd),
                "verifier_version": command.verifier_version,
                "config_hash": command.config_hash,
                "environment_profile_hash": command.environment_profile_hash,
                "workspace_fingerprint": command.workspace_fingerprint,
                "timeout_seconds": command.timeout_seconds,
            }
            for command in selection.commands
        ),
    )


@dataclass(frozen=True)
class VerifiedDispatchConfigView:
    """Safe projection of verified dispatch wiring."""

    enabled: bool
    repo_root: str
    snapshot_dir: str
    targets: tuple[str, ...]
    config_hash: str
    retry_attempts: int
    timeout_seconds: int
    analyzer_names: tuple[str, ...]
    ruff_executable: str
    ruff_rules: tuple[str, ...]


def verified_dispatch_config_view(
    *,
    repo_root: Path,
    snapshot_dir: Path,
    targets: Sequence[Path],
    config_hash: str,
    retry_attempts: int = 3,
    timeout_seconds: int = 60,
    ruff_executable: str = "ruff",
    ruff_rules: tuple[str, ...] = ("ALL",),
) -> VerifiedDispatchConfigView:
    """Build and project verified-dispatch config without executing analyzers."""

    config = VerifiedExecutorConfig(
        repo_root=repo_root,
        snapshot_dir=snapshot_dir,
        targets=tuple(targets),
        config_hash=config_hash,
        retry_attempts=retry_attempts,
        timeout_seconds=timeout_seconds,
        ruff_executable=ruff_executable,
        ruff_rules=ruff_rules,
    )
    executor = VerifiedExecutorFactory().build(config)
    return VerifiedDispatchConfigView(
        enabled=True,
        repo_root=str(executor.analyzer_config.repo_root),
        snapshot_dir=str(executor.snapshot_store.snapshot_dir),
        targets=tuple(str(target) for target in executor.analyzer_config.targets),
        config_hash=executor.analyzer_config.config_hash,
        retry_attempts=executor.regression_gate.retry_budget.max_attempts,
        timeout_seconds=executor.analyzer_config.timeout_seconds,
        analyzer_names=tuple(analyzer.name for analyzer in executor.analyzers),
        ruff_executable=executor.analyzers[0].executable,
        ruff_rules=executor.analyzers[0].selected_rules,
    )


def render_verified_dispatch_config(view: VerifiedDispatchConfigView, *, as_json: bool) -> str:
    """Render verified-dispatch config without secrets."""

    if as_json:
        return json.dumps(asdict(view), sort_keys=True)
    return "\n".join(
        [
            f"Verified dispatch enabled: {str(view.enabled).lower()}",
            f"Repository root: {view.repo_root}",
            f"Snapshot directory: {view.snapshot_dir}",
            "Targets: " + ", ".join(view.targets),
            f"Config hash: {view.config_hash}",
            f"Retry attempts: {view.retry_attempts}",
            f"Timeout seconds: {view.timeout_seconds}",
            "Analyzers: " + ", ".join(view.analyzer_names),
            f"Ruff executable: {view.ruff_executable}",
            "Ruff rules: " + ", ".join(view.ruff_rules),
        ]
    )
