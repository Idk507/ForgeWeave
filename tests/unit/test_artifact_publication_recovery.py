from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from forgeweave.events import ArtifactPublicationLedger, ArtifactPublicationState


class ArtifactPublicationLedgerTests(unittest.TestCase):
    def test_stages_and_marks_artifact_publication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact.txt"
            artifact.write_text("hello", encoding="utf-8")
            ledger = ArtifactPublicationLedger(root / "ledger")

            publication = ledger.stage(task_id="task-1", attempt_id="attempt-1", call_id="call-1", artifact_path=artifact)
            published = ledger.mark_published(publication.publication_id)

            self.assertEqual(publication.state, ArtifactPublicationState.STAGED)
            self.assertEqual(publication.expected_sha256, "sha256:" + sha256(b"hello").hexdigest())
            self.assertEqual(published.state, ArtifactPublicationState.PUBLISHED)
            self.assertEqual(ledger.get(publication.publication_id).state, ArtifactPublicationState.PUBLISHED)

    def test_reconcile_staged_artifact_as_published_when_hash_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact.txt"
            artifact.write_text("stable", encoding="utf-8")
            ledger = ArtifactPublicationLedger(root / "ledger")
            publication = ledger.stage(task_id="task-1", attempt_id="attempt-1", call_id="call-1", artifact_path=artifact)

            reconciled = ledger.reconcile_staged()

            self.assertEqual([item.publication_id for item in reconciled], [publication.publication_id])
            self.assertEqual(reconciled[0].state, ArtifactPublicationState.PUBLISHED)
            self.assertIn("expected hash", reconciled[0].evidence or "")

    def test_reconcile_missing_artifact_requires_attention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact.txt"
            artifact.write_text("stable", encoding="utf-8")
            ledger = ArtifactPublicationLedger(root / "ledger")
            ledger.stage(task_id="task-1", attempt_id="attempt-1", call_id="call-1", artifact_path=artifact)
            artifact.unlink()

            reconciled = ledger.reconcile_staged()

            self.assertEqual(reconciled[0].state, ArtifactPublicationState.MISSING)
            self.assertIn("missing", reconciled[0].evidence or "")

    def test_reconcile_corrupt_artifact_requires_attention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact.txt"
            artifact.write_text("before", encoding="utf-8")
            ledger = ArtifactPublicationLedger(root / "ledger")
            ledger.stage(task_id="task-1", attempt_id="attempt-1", call_id="call-1", artifact_path=artifact)
            artifact.write_text("after", encoding="utf-8")

            reconciled = ledger.reconcile_staged()

            self.assertEqual(reconciled[0].state, ArtifactPublicationState.CORRUPT)
            self.assertIn("hash mismatch", reconciled[0].evidence or "")

    def test_rejects_identity_change_for_existing_publication_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact.txt"
            artifact.write_text("hello", encoding="utf-8")
            ledger = ArtifactPublicationLedger(root / "ledger")
            publication = ledger.stage(task_id="task-1", attempt_id="attempt-1", call_id="call-1", artifact_path=artifact)
            path = ledger.root / f"{publication.publication_id}.json"
            payload = path.read_text(encoding="utf-8").replace("task-1", "task-2")
            path.write_text(payload, encoding="utf-8")

            with self.assertRaises(ValueError):
                ledger.stage(task_id="task-1", attempt_id="attempt-1", call_id="call-1", artifact_path=artifact)


if __name__ == "__main__":
    unittest.main()
