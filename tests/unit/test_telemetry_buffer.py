from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from forgeweave.telemetry import BoundedTelemetryWriter, JsonlTelemetrySink, TelemetryEvent


class BoundedTelemetryWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_flushes_buffered_events_to_sink(self) -> None:
        sink = JsonlTelemetrySink(self.root / "telemetry.jsonl")
        writer = BoundedTelemetryWriter(sink=sink, capacity=3)

        writer.record(TelemetryEvent(event="one", task_id="task-1", attempt_id="attempt-1", correlation_id="corr-1"))
        writer.record(TelemetryEvent(event="two", task_id="task-1", attempt_id="attempt-1", correlation_id="corr-1"))
        result = writer.flush()

        lines = (self.root / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(result.written, 2)
        self.assertEqual(result.failed, 0)
        self.assertEqual([json.loads(line)["event"] for line in lines], ["one", "two"])
        self.assertEqual(writer.pending_count, 0)

    def test_drops_oldest_event_when_capacity_is_reached(self) -> None:
        sink = JsonlTelemetrySink(self.root / "telemetry.jsonl")
        writer = BoundedTelemetryWriter(sink=sink, capacity=2)

        writer.record(TelemetryEvent(event="one", task_id="task-1", attempt_id="attempt-1", correlation_id="corr-1"))
        writer.record(TelemetryEvent(event="two", task_id="task-1", attempt_id="attempt-1", correlation_id="corr-1"))
        writer.record(TelemetryEvent(event="three", task_id="task-1", attempt_id="attempt-1", correlation_id="corr-1"))
        result = writer.flush()

        lines = (self.root / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(result.dropped, 1)
        self.assertEqual(writer.dropped_count, 1)
        self.assertEqual([json.loads(line)["event"] for line in lines], ["two", "three"])

    def test_sink_failure_preserves_failed_event_and_counts_failure(self) -> None:
        sink = FailingSink(failures_before_success=1, path=self.root / "telemetry.jsonl")
        writer = BoundedTelemetryWriter(sink=sink, capacity=2)
        writer.record(TelemetryEvent(event="one", task_id="task-1", attempt_id="attempt-1", correlation_id="corr-1"))

        failed = writer.flush()

        self.assertEqual(failed.written, 0)
        self.assertEqual(failed.failed, 1)
        self.assertEqual(writer.pending_count, 1)

        recovered = writer.flush()

        self.assertEqual(recovered.written, 1)
        self.assertEqual(writer.failure_count, 1)
        payload = json.loads((self.root / "telemetry.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(payload["event"], "one")

    def test_rejects_non_positive_capacity(self) -> None:
        with self.assertRaises(ValueError):
            BoundedTelemetryWriter(sink=JsonlTelemetrySink(self.root / "telemetry.jsonl"), capacity=0)


class FailingSink(JsonlTelemetrySink):
    def __init__(self, *, failures_before_success: int, path: Path) -> None:
        super().__init__(path)
        self.failures_before_success = failures_before_success

    def write(self, event: TelemetryEvent) -> None:
        if self.failures_before_success > 0:
            self.failures_before_success -= 1
            raise OSError("disk unavailable")
        super().write(event)


if __name__ == "__main__":
    unittest.main()
