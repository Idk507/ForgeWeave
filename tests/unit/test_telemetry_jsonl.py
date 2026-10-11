from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest

from forgeweave.telemetry import JsonlTelemetrySink, TelemetryEvent, TelemetrySpan


class JsonlTelemetrySinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_writes_structured_jsonl_event(self) -> None:
        sink = JsonlTelemetrySink(self.root / "telemetry.jsonl")
        event = TelemetryEvent(
            event="loop.step.started",
            task_id="task-1",
            attempt_id="attempt-1",
            correlation_id="corr-1",
            fields={"catalog_version": "tools-v1"},
        )

        sink.write(event)

        line = (self.root / "telemetry.jsonl").read_text(encoding="utf-8").strip()
        payload = json.loads(line)
        self.assertEqual(payload["event"], "loop.step.started")
        self.assertEqual(payload["correlation_id"], "corr-1")
        self.assertEqual(payload["fields"], {"catalog_version": "tools-v1"})

    def test_redacts_sensitive_field_names(self) -> None:
        sink = JsonlTelemetrySink(self.root / "telemetry.jsonl")
        event = TelemetryEvent(
            event="provider.call",
            task_id="task-1",
            attempt_id="attempt-1",
            correlation_id="corr-1",
            fields={"api_key": "secret", "nested": {"token": "secret-token", "safe": "ok"}},
        )

        sink.write(event)

        payload = json.loads((self.root / "telemetry.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(payload["fields"]["api_key"], "[REDACTED]")
        self.assertEqual(payload["fields"]["nested"]["token"], "[REDACTED]")
        self.assertEqual(payload["fields"]["nested"]["safe"], "ok")

    def test_keeps_token_count_fields_while_redacting_secret_tokens(self) -> None:
        sink = JsonlTelemetrySink(self.root / "telemetry.jsonl")
        event = TelemetryEvent(
            event="loop.diagnostics",
            task_id="task-1",
            attempt_id="attempt-1",
            correlation_id="corr-1",
            fields={"budget_usage_tokens": 42, "context_token_estimate": 120, "output_token": "secret"},
        )

        sink.write(event)

        payload = json.loads((self.root / "telemetry.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(payload["fields"]["budget_usage_tokens"], 42)
        self.assertEqual(payload["fields"]["context_token_estimate"], 120)
        self.assertEqual(payload["fields"]["output_token"], "[REDACTED]")

    def test_writes_span_start_and_end_with_parent_and_duration(self) -> None:
        sink = JsonlTelemetrySink(self.root / "telemetry.jsonl")
        started_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        ended_at = started_at + timedelta(milliseconds=250)

        span = sink.start_span(
            name="core.dispatch",
            task_id="task-1",
            attempt_id="attempt-1",
            correlation_id="corr-1",
            span_id="span-1",
            parent_span_id="root-span",
            fields={"catalog_version": "tools-v1"},
            started_at=started_at,
        )
        sink.end_span(span, status="ok", fields={"output_token": "secret"}, ended_at=ended_at)

        lines = (self.root / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()
        started = json.loads(lines[0])
        ended = json.loads(lines[1])
        self.assertEqual(started["event"], "span.started")
        self.assertEqual(started["timestamp"], "2026-01-01T12:00:00Z")
        self.assertEqual(started["fields"]["span_id"], "span-1")
        self.assertEqual(started["fields"]["span_name"], "core.dispatch")
        self.assertEqual(started["fields"]["parent_span_id"], "root-span")
        self.assertEqual(started["fields"]["catalog_version"], "tools-v1")
        self.assertEqual(ended["event"], "span.ended")
        self.assertEqual(ended["fields"]["span_id"], "span-1")
        self.assertEqual(ended["fields"]["duration_ms"], 250.0)
        self.assertEqual(ended["fields"]["status"], "ok")
        self.assertEqual(ended["fields"]["output_token"], "[REDACTED]")

    def test_span_rejects_blank_name(self) -> None:
        with self.assertRaises(ValueError):
            TelemetrySpan(
                span_id="span-1",
                name=" ",
                task_id="task-1",
                attempt_id="attempt-1",
                correlation_id="corr-1",
            )

    def test_rotates_jsonl_file_before_write_when_size_limit_would_be_exceeded(self) -> None:
        sink = JsonlTelemetrySink(self.root / "telemetry.jsonl", max_bytes=220, backup_count=2)

        sink.write(
            TelemetryEvent(
                event="first",
                task_id="task-1",
                attempt_id="attempt-1",
                correlation_id="corr-1",
                fields={"message": "x" * 80},
            )
        )
        sink.write(
            TelemetryEvent(
                event="second",
                task_id="task-1",
                attempt_id="attempt-1",
                correlation_id="corr-1",
                fields={"message": "y" * 80},
            )
        )

        active = (self.root / "telemetry.jsonl").read_text(encoding="utf-8")
        rotated = (self.root / "telemetry.jsonl.1").read_text(encoding="utf-8")
        self.assertEqual(json.loads(active)["event"], "second")
        self.assertEqual(json.loads(rotated)["event"], "first")

    def test_rotation_keeps_configured_backup_count(self) -> None:
        sink = JsonlTelemetrySink(self.root / "telemetry.jsonl", max_bytes=220, backup_count=1)

        for index in range(3):
            sink.write(
                TelemetryEvent(
                    event=f"event-{index}",
                    task_id="task-1",
                    attempt_id="attempt-1",
                    correlation_id="corr-1",
                    fields={"message": str(index) * 80},
                )
            )

        self.assertTrue((self.root / "telemetry.jsonl").exists())
        self.assertTrue((self.root / "telemetry.jsonl.1").exists())
        self.assertFalse((self.root / "telemetry.jsonl.2").exists())
        self.assertEqual(json.loads((self.root / "telemetry.jsonl").read_text(encoding="utf-8"))["event"], "event-2")
        self.assertEqual(json.loads((self.root / "telemetry.jsonl.1").read_text(encoding="utf-8"))["event"], "event-1")

    def test_rotation_rejects_invalid_limits(self) -> None:
        with self.assertRaises(ValueError):
            JsonlTelemetrySink(self.root / "telemetry.jsonl", max_bytes=0)
        with self.assertRaises(ValueError):
            JsonlTelemetrySink(self.root / "telemetry.jsonl", backup_count=-1)

    def test_rejects_blank_event_name(self) -> None:
        with self.assertRaises(ValueError):
            TelemetryEvent(event=" ", task_id="task-1", attempt_id="attempt-1", correlation_id="corr-1")


if __name__ == "__main__":
    unittest.main()
