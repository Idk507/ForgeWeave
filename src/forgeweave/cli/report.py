"""CLI helpers for structured final task reports."""

from __future__ import annotations

import json
from pathlib import Path

from forgeweave.contracts import VerificationRun
from forgeweave.core import FinalReport, build_final_report, render_final_report
from forgeweave.verify import VerificationResult


def final_report_from_files(
    *,
    task_id: str,
    modified_files: tuple[str, ...] = (),
    verification_run_files: tuple[Path, ...] = (),
    risks: tuple[str, ...] = (),
    artifact_links: tuple[str, ...] = (),
) -> FinalReport:
    """Build a final report from explicit CLI inputs and verification-run JSON files."""

    results = tuple(_verification_result_from_file(path) for path in verification_run_files)
    return build_final_report(
        task_id=task_id,
        modified_files=modified_files,
        verification_results=results,
        risks=risks,
        artifact_links=artifact_links,
    )


def render_final_report_from_files(
    *,
    task_id: str,
    modified_files: tuple[str, ...] = (),
    verification_run_files: tuple[Path, ...] = (),
    risks: tuple[str, ...] = (),
    artifact_links: tuple[str, ...] = (),
    as_json: bool,
) -> str:
    """Build and render a final report from explicit CLI inputs."""

    report = final_report_from_files(
        task_id=task_id,
        modified_files=modified_files,
        verification_run_files=verification_run_files,
        risks=risks,
        artifact_links=artifact_links,
    )
    return render_final_report(report, as_json=as_json)


def _verification_result_from_file(path: Path) -> VerificationResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("verification run file must contain a JSON object")
    run = VerificationRun.model_validate(payload)
    return VerificationResult(run=run, stdout="", stderr="", timed_out=run.outcome == "inconclusive")
