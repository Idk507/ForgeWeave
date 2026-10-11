from __future__ import annotations

import unittest

from forgeweave.contracts import EffectSet
from forgeweave.core import DispatchJob, DispatchPlanner


class DispatchStageExecutionTests(unittest.TestCase):
    def test_parallel_read_stage_uses_parallel_executor_and_orders_results(self) -> None:
        jobs = [
            DispatchJob(index=0, tool_name="read_a", payload={"value": "a"}, effects=EffectSet(reads=frozenset({"a"}))),
            DispatchJob(index=1, tool_name="read_b", payload={"value": "b"}, effects=EffectSet(reads=frozenset({"b"}))),
        ]
        parallel_batches: list[list[str]] = []

        def parallel_executor(batch: tuple[DispatchJob, ...]) -> list[tuple[int, dict[str, object]]]:
            parallel_batches.append([job.tool_name for job in batch])
            return [(job.index, {"tool_name": job.tool_name, "output": job.payload["value"]}) for job in reversed(batch)]

        observations = DispatchPlanner().dispatch_stages(
            jobs=jobs,
            serial_dispatch=lambda job: {"tool_name": job.tool_name, "output": job.payload["value"]},
            parallel_dispatch=parallel_executor,
        )

        self.assertEqual(parallel_batches, [["read_a", "read_b"]])
        self.assertEqual([item["tool_name"] for item in observations], ["read_a", "read_b"])

    def test_serial_stage_uses_serial_executor_in_model_order(self) -> None:
        jobs = [
            DispatchJob(index=0, tool_name="write_a", payload={}, effects=EffectSet(writes=frozenset({"workspace"}))),
            DispatchJob(index=1, tool_name="write_b", payload={}, effects=EffectSet(writes=frozenset({"workspace"}))),
        ]
        serial_order: list[str] = []

        observations = DispatchPlanner().dispatch_stages(
            jobs=jobs,
            serial_dispatch=lambda job: serial_order.append(job.tool_name) or {"tool_name": job.tool_name, "output": "ok"},
        )

        self.assertEqual(serial_order, ["write_a", "write_b"])
        self.assertEqual([item["tool_name"] for item in observations], ["write_a", "write_b"])

    def test_parallel_executor_error_is_reported_per_job(self) -> None:
        jobs = [
            DispatchJob(index=0, tool_name="read_a", payload={}, effects=EffectSet(reads=frozenset({"a"}))),
            DispatchJob(index=1, tool_name="read_b", payload={}, effects=EffectSet(reads=frozenset({"b"}))),
        ]

        observations = DispatchPlanner().dispatch_stages(
            jobs=jobs,
            serial_dispatch=lambda job: {},
            parallel_dispatch=lambda batch: (_ for _ in ()).throw(RuntimeError("pool crashed")),
        )

        self.assertEqual(
            observations,
            [
                {"tool_name": "read_a", "error": "pool crashed"},
                {"tool_name": "read_b", "error": "pool crashed"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
