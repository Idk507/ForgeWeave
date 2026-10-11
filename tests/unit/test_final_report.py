from __future__ import annotations

import json
import unittest

from forgeweave.contracts import VerificationRun
from forgeweave.core import build_final_report, render_final_report
from forgeweave.verify import VerificationResult


class FinalReportTests(unittest.TestCase):
    def test_builds_report_with_failed_checks_and_artifacts(self) -> None:
        passed = _result("run-pass", "passed", 0, artifact_id="artifact-pass")
        failed = _result("run-fail", "failed", 1, artifact_id="artifact-fail")

        report = build_final_report(
            task_id="task-1",
            modified_files=("src/app.py", "tests/test_app.py"),
            verification_results=(passed, failed),
            risks=("manual review still needed",),
            artifact_links=("artifact://task-1/patch",),
        )

        self.assertFalse(report.passed)
        self.assertEqual([check.run_id for check in report.checks], ["run-pass", "run-fail"])
        self.assertEqual([check.run_id for check in report.failed_checks], ["run-fail"])
        self.assertEqual(report.failed_checks[0].output_artifact_id, "artifact-fail")

    def test_json_render_is_stable_and_reviewable(self) -> None:
        report = build_final_report(task_id="task-1", verification_results=(_result("run-pass", "passed", 0),))

        payload = json.loads(render_final_report(report, as_json=True))

        self.assertEqual(payload["task_id"], "task-1")
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["checks"][0]["command"], ["python", "-m", "unittest"])
        self.assertEqual(payload["checks"][0]["duration_ms"], 12.5)
        self.assertEqual(payload["failed_checks"], [])

    def test_text_render_includes_required_sections(self) -> None:
        report = build_final_report(
            task_id="task-1",
            modified_files=("src/app.py",),
            verification_results=(_result("run-fail", "failed", 1),),
            risks=("network tests not run",),
        )

        rendered = render_final_report(report, as_json=False)

        self.assertIn("Modified files:", rendered)
        self.assertIn("Checks run:", rendered)
        self.assertIn("Failed checks:", rendered)
        self.assertIn("Risks:", rendered)
        self.assertIn("Artifacts:", rendered)
        self.assertIn("network tests not run", rendered)

    def test_rejects_blank_identity_and_items(self) -> None:
        with self.assertRaises(ValueError):
            build_final_report(task_id=" ")
        with self.assertRaises(ValueError):
            build_final_report(task_id="task-1", modified_files=(" ",))


def _result(run_id: str, outcome: str, exit_code: int, *, artifact_id: str | None = None) -> VerificationResult:
    run = VerificationRun(
        run_id=run_id,
        task_id="task-1",
        criterion_ids=("criterion-1",),
        command_argv=("python", "-m", "unittest"),
        cwd="C:/repo",
        environment_profile_hash="sha256:env",
        verifier_version="verify-v1",
        config_hash="sha256:config",
        workspace_fingerprint="sha256:workspace",
        duration_ms=12.5,
        exit_code=exit_code,
        output_artifact_id=artifact_id,
        outcome=outcome,  # type: ignore[arg-type]
    )
    return VerificationResult(run=run, stdout="", stderr="", timed_out=outcome == "inconclusive")


if __name__ == "__main__":
    unittest.main()
