from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forgeweave.contracts import ActorKind, ArtifactKind, Event, EventKind
from forgeweave.events import ArtifactStore, EventStore


class EventStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_store_opens_database_in_wal_mode(self) -> None:
        store = EventStore.open(self.root / "events.db")

        mode = store.journal_mode()

        store.close()
        self.assertEqual(mode.lower(), "wal")

    def test_append_assigns_per_task_monotonic_sequence_and_reads_ordered_events(self) -> None:
        store = EventStore.open(self.root / "events.db")
        first = store.append(
            Event(
                event_id="evt-1",
                task_id="task-1",
                attempt_id="attempt-1",
                sequence=1,
                actor=ActorKind.SYSTEM,
                kind=EventKind.TASK_CREATED,
                correlation_id="corr-1",
                payload_ref="artifact://payload-1",
            )
        )
        second = store.append(
            Event(
                event_id="evt-2",
                task_id="task-1",
                attempt_id="attempt-1",
                sequence=1,
                actor=ActorKind.POLICY,
                kind=EventKind.POLICY_DECISION,
                correlation_id="corr-1",
                payload_ref="artifact://payload-2",
            )
        )

        self.assertEqual(first.sequence, 1)
        self.assertEqual(second.sequence, 2)
        self.assertEqual([event.event_id for event in store.list_events("task-1")], ["evt-1", "evt-2"])
        store.close()

    def test_duplicate_event_id_is_idempotent_only_for_same_payload(self) -> None:
        store = EventStore.open(self.root / "events.db")
        event = Event(
            event_id="evt-1",
            task_id="task-1",
            attempt_id="attempt-1",
            sequence=99,
            actor=ActorKind.SYSTEM,
            kind=EventKind.TASK_CREATED,
            correlation_id="corr-1",
            payload_ref="artifact://payload-1",
        )

        first = store.append(event)
        duplicate = store.append(event)
        self.assertEqual(first, duplicate)
        self.assertEqual(len(store.list_events("task-1")), 1)

        with self.assertRaises(ValueError):
            store.append(event.model_copy(update={"payload_ref": "artifact://different"}))
        store.close()


class ArtifactStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_put_bytes_writes_task_scoped_content_addressed_artifact(self) -> None:
        store = ArtifactStore(self.root / "artifacts")
        artifact = store.put_bytes(task_id="task-1", kind=ArtifactKind.TEXT, data=b"hello")

        self.assertEqual(artifact.task_id, "task-1")
        self.assertEqual(artifact.size_bytes, 5)
        self.assertTrue(artifact.uri.startswith("artifact://task-1/"))
        self.assertEqual(store.read_bytes(artifact), b"hello")
        self.assertTrue((self.root / "artifacts" / "task-1").is_dir())

    def test_put_bytes_rejects_empty_task_id(self) -> None:
        store = ArtifactStore(self.root / "artifacts")

        with self.assertRaises(ValueError):
            store.put_bytes(task_id=" ", kind=ArtifactKind.TEXT, data=b"hello")


if __name__ == "__main__":
    unittest.main()
