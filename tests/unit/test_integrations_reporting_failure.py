from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import json
import tempfile
import unittest

from forgeweave.integrations.reporting import LocalFailureReporter, build_failure_report


class FailureReportingTests(unittest.TestCase):
    def test_builds_redacted_failure_report(self) -> None:
        report = build_failure_report(
            task_id="task-1",
            title="Workflow failed token=abc123",
            created_at=datetime(2026, 10, 11, 12, 0, tzinfo=UTC),
            failures=[
                {
                    "source": "workflow",
                    "code": "GIT_FAILED",
                    "message": "command failed with api_key=secret-value",
                    "evidence": {"stderr": "Bearer abc.def", "attempt_id": "attempt-1"},
                }
            ],
        )

        payload = report.to_json()

        self.assertEqual(report.task_id, "task-1")
        self.assertEqual(report.created_at, datetime(2026, 10, 11, 12, 0, tzinfo=UTC))
        self.assertIn("<redacted>", payload["title"])
        self.assertEqual(payload["items"][0]["source"], "workflow")
        self.assertEqual(payload["items"][0]["message"], "command failed with api_key=<redacted>")
        self.assertEqual(payload["items"][0]["evidence"]["stderr"], "Bearer=<redacted>")
        self.assertFalse(payload["notification_ready"])

    def test_writes_report_under_report_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = build_failure_report(
                task_id="task-1",
                title="Workflow failed",
                created_at=datetime(2026, 10, 11, 12, 0, tzinfo=UTC),
                failures=[{"source": "workflow", "code": "FAILED", "message": "bad", "evidence": {}}],
            )
            reporter = LocalFailureReporter(report_root=Path(tmp) / "reports")

            path = reporter.write(report)

            self.assertTrue(path.exists())
            self.assertEqual(path.parent, (Path(tmp) / "reports").resolve())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["report_id"], report.report_id)

    def test_rejects_blank_task_or_title(self) -> None:
        with self.assertRaises(ValueError):
            build_failure_report(task_id=" ", title="Failed", failures=[])
        with self.assertRaises(ValueError):
            build_failure_report(task_id="task", title=" ", failures=[])

    def test_non_dict_evidence_is_wrapped(self) -> None:
        report = build_failure_report(task_id="task", title="Failed", failures=[{"evidence": "plain"}])

        self.assertEqual(report.items[0].evidence["value"], "plain")


if __name__ == "__main__":
    unittest.main()
