"""Task completion helpers that produce final reports from harness evidence."""

from __future__ import annotations

from forgeweave.verify import SelectedVerificationRun

from .final_report import FinalReport, build_final_report


def complete_from_selected_verification(
    *,
    task_id: str,
    selected_run: SelectedVerificationRun,
    modified_files: tuple[str, ...] = (),
    risks: tuple[str, ...] = (),
    artifact_links: tuple[str, ...] = (),
) -> FinalReport:
    """Build the final task report from selected verification evidence.

    Empty selected verification is preserved as a risk so task completion cannot
    accidentally report success when no configured checks ran.
    """

    if selected_run.task_id != task_id:
        raise ValueError("selected verification task_id does not match final report task_id")
    completion_risks = tuple(risks)
    if not selected_run.results:
        completion_risks = (*completion_risks, "no verification commands were selected or run")
    return build_final_report(
        task_id=task_id,
        modified_files=modified_files,
        verification_results=selected_run.results,
        risks=completion_risks,
        artifact_links=artifact_links,
    )
