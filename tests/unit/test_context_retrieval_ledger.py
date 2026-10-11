from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from forgeweave.context import RetrievalLedger, RetrievalLedgerEntry


class RetrievalLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.root / "src").mkdir()
        self.file_path = self.root / "src" / "app.py"
        self.file_path.write_text("print('hello')\n", encoding="utf-8")

    def test_records_file_span_with_content_hash(self) -> None:
        ledger = RetrievalLedger(workspace_root=self.root)

        entry = ledger.record_file_span(span_id="span-1", path="src/app.py", start_line=1, end_line=1)

        self.assertEqual(entry.path, "src/app.py")
        self.assertEqual(entry.start_line, 1)
        self.assertEqual(entry.end_line, 1)
        self.assertTrue(entry.source_hash.startswith("sha256:"))
        self.assertFalse(ledger.stale_entries([entry]))

    def test_marks_entry_stale_when_file_changes(self) -> None:
        ledger = RetrievalLedger(workspace_root=self.root)
        entry = ledger.record_file_span(span_id="span-1", path="src/app.py", start_line=1, end_line=1)
        self.file_path.write_text("print('changed')\n", encoding="utf-8")

        stale = ledger.stale_entries([entry])

        self.assertEqual([item.span_id for item in stale], ["span-1"])

    def test_rejects_path_escape(self) -> None:
        ledger = RetrievalLedger(workspace_root=self.root)

        with self.assertRaises(ValueError):
            ledger.record_file_span(span_id="bad", path="../outside.py", start_line=1, end_line=1)

    def test_can_check_entries_restored_from_json(self) -> None:
        ledger = RetrievalLedger(workspace_root=self.root)
        entry = ledger.record_file_span(span_id="span-1", path="src/app.py", start_line=1, end_line=1)
        restored = RetrievalLedgerEntry.model_validate_json(entry.model_dump_json())

        self.assertFalse(ledger.stale_entries([restored]))


if __name__ == "__main__":
    unittest.main()
