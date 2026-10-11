"""Execute selected verification commands with captured evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .runner import VerificationResult, VerificationRunner
from .selection import VerificationSelection, select_verification_commands


@dataclass(frozen=True)
class SelectedVerificationRun:
    """Results from executing a selected verification command set."""

    task_id: str
    selection: VerificationSelection
    results: tuple[VerificationResult, ...]

    @property
    def passed(self) -> bool:
        """Return true when every selected command passed and at least one command ran."""

        return bool(self.results) and all(result.run.outcome == "passed" for result in self.results)

    @property
    def failed_results(self) -> tuple[VerificationResult, ...]:
        """Return selected command results that did not pass."""

        return tuple(result for result in self.results if result.run.outcome != "passed")


def run_selected_verification(
    *,
    task_id: str,
    repo_root: Path,
    output_dir: Path,
    environment_profile_hash: str = "sha256:local",
    timeout_seconds: int = 60,
    output_cap_bytes: int = 64_000,
) -> SelectedVerificationRun:
    """Select repository checks and execute them with `VerificationRunner`."""

    if not task_id.strip():
        raise ValueError("task_id must not be blank")
    selection = select_verification_commands(
        repo_root,
        environment_profile_hash=environment_profile_hash,
        timeout_seconds=timeout_seconds,
    )
    runner = VerificationRunner(output_dir=output_dir, output_cap_bytes=output_cap_bytes)
    results = tuple(runner.run(task_id=task_id, command=command) for command in selection.commands)
    return SelectedVerificationRun(task_id=task_id, selection=selection, results=results)
