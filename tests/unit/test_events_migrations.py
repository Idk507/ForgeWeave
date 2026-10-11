from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from forgeweave.contracts import ActorKind, Event, EventKind
from forgeweave.events import EventStore, MigrationStep


class EventMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_migration_publishes_successor_without_rewriting_original_event_json(self) -> None:
        store = EventStore.open(self.root / "events.db")
        original = store.append(
            Event(
                event_id="evt-1",
                task_id="task-1",
                attempt_id="attempt-1",
                sequence=1,
                actor=ActorKind.SYSTEM,
                kind=EventKind.TASK_CREATED,
                correlation_id="corr-1",
                payload_ref="artifact://payload-v1",
            )
        )
        before_json = store.raw_event_json("evt-1")

        step = MigrationStep(
            step_id="event-v1-to-v2",
            from_version="event.v1",
            to_version="event.v2",
            description="Publish v2 successor for event payload references.",
        )
        successor = store.publish_migration_successor(
            source_event_id=original.event_id,
            successor_event_id="evt-1-v2",
            to_schema_version=step.to_version,
            payload_ref="artifact://payload-v2",
            migration_step=step,
        )

        self.assertEqual(store.raw_event_json("evt-1"), before_json)
        self.assertEqual(successor.sequence, 2)
        self.assertEqual(successor.schema_version, "event.v2")
        self.assertEqual(successor.payload_ref, "artifact://payload-v2")
        self.assertEqual([event.event_id for event in store.list_events("task-1")], ["evt-1", "evt-1-v2"])
        self.assertEqual(store.applied_migrations(), [step])
        store.close()

    def test_migration_steps_must_be_adjacent_versions(self) -> None:
        with self.assertRaises(ValueError):
            MigrationStep(
                step_id="skip",
                from_version="event.v1",
                to_version="event.v3",
                description="Skipping versions is not allowed.",
            )

    def test_reapplying_same_migration_step_is_idempotent(self) -> None:
        store = EventStore.open(self.root / "events.db")
        step = MigrationStep(
            step_id="event-v1-to-v2",
            from_version="event.v1",
            to_version="event.v2",
            description="Publish successor.",
        )

        store.record_migration(step)
        store.record_migration(step)

        self.assertEqual(store.applied_migrations(), [step])
        store.close()


if __name__ == "__main__":
    unittest.main()
