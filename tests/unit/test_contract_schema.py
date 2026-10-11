from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from forgeweave.contracts import (
    Event,
    EventKind,
    ToolCall,
    AcceptanceCriterion,
    ConstraintLedger,
    EffectSet,
    ActorKind,
    export_contract_schemas,
    schema_models,
)


class ContractSchemaTests(unittest.TestCase):
    def test_schema_registry_contains_core_and_operational_contracts(self) -> None:
        names = {model.__name__ for model in schema_models()}

        self.assertIn("Task", names)
        self.assertIn("Event", names)
        self.assertIn("ToolCall", names)
        self.assertIn("ConstraintLedger", names)
        self.assertIn("VerificationRun", names)

    def test_export_contract_schemas_writes_stable_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            written = export_contract_schemas(output)

            self.assertIn(output / "event.schema.json", written)
            self.assertIn(output / "constraint-ledger.schema.json", written)
            event_schema = json.loads((output / "event.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(event_schema["title"], "Event")
            self.assertEqual(event_schema["properties"]["schema_version"]["default"], "event.v1")

    def test_representative_contracts_round_trip_json(self) -> None:
        event = Event(
            event_id="evt-1",
            task_id="task-1",
            attempt_id="attempt-1",
            sequence=1,
            actor=ActorKind.SYSTEM,
            kind=EventKind.TOOL_CALL_REQUESTED,
            correlation_id="corr-1",
            payload_ref="artifact://payload",
        )
        call = ToolCall(
            call_id="call-1",
            tool_name="read_file",
            tool_schema_version="read-file.v1",
            arguments={"path": "README.md"},
            argument_hash="sha256:args",
            effects=EffectSet(reads=frozenset({"workspace"})),
        )
        ledger = ConstraintLedger(
            task_id="task-1",
            constraints=[
                AcceptanceCriterion(
                    criterion_id="must-test",
                    text="Run unit tests.",
                    origin="todo.md",
                    authority="repository",
                    validator="python -m unittest discover -s tests/unit",
                )
            ],
        )

        self.assertEqual(Event.model_validate_json(event.model_dump_json()), event)
        self.assertEqual(ToolCall.model_validate_json(call.model_dump_json()), call)
        self.assertEqual(ConstraintLedger.model_validate_json(ledger.model_dump_json()), ledger)


if __name__ == "__main__":
    unittest.main()
