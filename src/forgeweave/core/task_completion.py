"""Repository task completion orchestration for the native harness."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from forgeweave.verify import SelectedVerificationRun, run_selected_verification

from .completion import complete_from_selected_verification
from .final_report import FinalReport


@dataclass(frozen=True)
class TaskCompletionResult:
    """Selected verification evidence plus the final handoff report."""

    selected_run: SelectedVerificationRun
    report: FinalReport

    @property
    def passed(self) -> bool:
        """Return true when selected verification and the final report both pass."""

        return self.selected_run.passed and self.report.passed


def complete_repository_task(
    *,
    task_id: str,
    repo_root: Path,
    output_dir: Path,
    modified_files: tuple[str, ...] = (),
    risks: tuple[str, ...] = (),
    artifact_links: tuple[str, ...] = (),
    environment_profile_hash: str = "sha256:local",
    timeout_seconds: int = 60,
    output_cap_bytes: int = 64_000,
) -> TaskCompletionResult:
    """Run selected repository verification and build the final task report.

    This is the native-loop boundary used when an implementation attempt is
    ready for handoff: verification is selected from repository evidence, run
    once, and the resulting report preserves every passed, failed or missing
    check as reviewable completion evidence.
    """

    selected_run = run_selected_verification(
        task_id=task_id,
        repo_root=repo_root,
        output_dir=output_dir,
        environment_profile_hash=environment_profile_hash,
        timeout_seconds=timeout_seconds,
        output_cap_bytes=output_cap_bytes,
    )
    report = complete_from_selected_verification(
        task_id=task_id,
        selected_run=selected_run,
        modified_files=modified_files,
        risks=risks,
        artifact_links=artifact_links,
    )
    return TaskCompletionResult(selected_run=selected_run, report=report)
