"""Structured final report contract for task handoff."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from forgeweave.verify import VerificationResult


@dataclass(frozen=True)
class CheckSummary:
    """Reviewable summary of one verification run."""

    run_id: str
    criterion_ids: tuple[str, ...]
    command: tuple[str, ...]
    outcome: str
    exit_code: int | None
    timed_out: bool
    duration_ms: float | None
    output_artifact_id: str | None
    workspace_fingerprint: str


@dataclass(frozen=True)
class FinalReport:
    """Final task handoff data required by the native harness."""

    task_id: str
    modified_files: tuple[str, ...]
    checks: tuple[CheckSummary, ...]
    failed_checks: tuple[CheckSummary, ...]
    risks: tuple[str, ...]
    artifact_links: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Return true when no check failed and no unresolved risk was recorded."""

        return not self.failed_checks and not self.risks


def build_final_report(
    *,
    task_id: str,
    modified_files: tuple[str, ...] = (),
    verification_results: tuple[VerificationResult, ...] = (),
    risks: tuple[str, ...] = (),
    artifact_links: tuple[str, ...] = (),
) -> FinalReport:
    """Build a deterministic final report from existing harness evidence."""

    if not task_id.strip():
        raise ValueError("task_id must not be blank")
    cleaned_files = tuple(_clean_items(modified_files, "modified_files"))
    cleaned_risks = tuple(_clean_items(risks, "risks"))
    cleaned_artifacts = tuple(_clean_items(artifact_links, "artifact_links"))
    checks = tuple(_check_summary(result) for result in verification_results)
    failed = tuple(check for check in checks if check.outcome != "passed")
    return FinalReport(
        task_id=task_id,
        modified_files=cleaned_files,
        checks=checks,
        failed_checks=failed,
        risks=cleaned_risks,
        artifact_links=cleaned_artifacts,
    )


def render_final_report(report: FinalReport, *, as_json: bool) -> str:
    """Render the final report as stable JSON or a human-readable handoff."""

    if as_json:
        payload = asdict(report)
        payload["passed"] = report.passed
        return json.dumps(payload, sort_keys=True)

    lines = [
        f"Task: {report.task_id}",
        f"Passed: {str(report.passed).lower()}",
        "Modified files:",
    ]
    lines.extend(_bullet_list(report.modified_files))
    lines.append("Checks run:")
    if report.checks:
        for check in report.checks:
            command = " ".join(check.command)
            lines.append(f"- {check.outcome}: {command} ({check.run_id})")
    else:
        lines.append("- none")
    lines.append("Failed checks:")
    if report.failed_checks:
        for check in report.failed_checks:
            command = " ".join(check.command)
            lines.append(f"- {check.outcome}: {command} ({check.run_id})")
    else:
        lines.append("- none")
    lines.append("Risks:")
    lines.extend(_bullet_list(report.risks))
    lines.append("Artifacts:")
    lines.extend(_bullet_list(report.artifact_links))
    return "\n".join(lines)


def _check_summary(result: VerificationResult) -> CheckSummary:
    run = result.run
    return CheckSummary(
        run_id=run.run_id,
        criterion_ids=run.criterion_ids,
        command=run.command_argv,
        outcome=run.outcome,
        exit_code=run.exit_code,
        timed_out=result.timed_out,
        duration_ms=run.duration_ms,
        output_artifact_id=run.output_artifact_id,
        workspace_fingerprint=run.workspace_fingerprint,
    )


def _clean_items(items: tuple[str, ...], field: str) -> tuple[str, ...]:
    cleaned = []
    for item in items:
        if not item.strip():
            raise ValueError(f"{field} must not contain blank items")
        cleaned.append(item)
    return tuple(cleaned)


def _bullet_list(items: tuple[str, ...]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- none"]
