from __future__ import annotations

import unittest

from forgeweave.contracts import EffectSet
from forgeweave.core import DispatchJob, DispatchPlanner, DispatchPlanKind


class DispatchSchedulingTests(unittest.TestCase):
    def test_read_only_jobs_share_parallel_stage(self) -> None:
        jobs = [
            DispatchJob(index=0, tool_name="read_a", payload={}, effects=EffectSet(reads=frozenset({"workspace:a"}))),
            DispatchJob(index=1, tool_name="read_b", payload={}, effects=EffectSet(reads=frozenset({"workspace:b"}))),
        ]

        stages = DispatchPlanner().plan(jobs)

        self.assertEqual(len(stages), 1)
        self.assertEqual(stages[0].kind, DispatchPlanKind.PARALLEL_READS)
        self.assertEqual([job.tool_name for job in stages[0].jobs], ["read_a", "read_b"])

    def test_write_jobs_are_serialized_in_model_order(self) -> None:
        jobs = [
            DispatchJob(index=0, tool_name="write_a", payload={}, effects=EffectSet(writes=frozenset({"workspace"}))),
            DispatchJob(index=1, tool_name="write_b", payload={}, effects=EffectSet(writes=frozenset({"workspace"}))),
        ]

        stages = DispatchPlanner().plan(jobs)

        self.assertEqual([stage.kind for stage in stages], [DispatchPlanKind.SERIAL, DispatchPlanKind.SERIAL])
        self.assertEqual([stage.jobs[0].tool_name for stage in stages], ["write_a", "write_b"])

    def test_read_stage_flushes_before_write_then_new_reads_group(self) -> None:
        jobs = [
            DispatchJob(index=0, tool_name="read_a", payload={}, effects=EffectSet(reads=frozenset({"workspace"}))),
            DispatchJob(index=1, tool_name="write", payload={}, effects=EffectSet(writes=frozenset({"workspace"}))),
            DispatchJob(index=2, tool_name="read_b", payload={}, effects=EffectSet(reads=frozenset({"workspace"}))),
        ]

        stages = DispatchPlanner().plan(jobs)

        self.assertEqual([stage.kind for stage in stages], [DispatchPlanKind.PARALLEL_READS, DispatchPlanKind.SERIAL, DispatchPlanKind.PARALLEL_READS])
        self.assertEqual([[job.tool_name for job in stage.jobs] for stage in stages], [["read_a"], ["write"], ["read_b"]])

    def test_process_network_and_external_effects_are_serialized(self) -> None:
        jobs = [
            DispatchJob(index=0, tool_name="shell", payload={}, effects=EffectSet(process=frozenset({"subprocess"}))),
            DispatchJob(index=1, tool_name="fetch", payload={}, effects=EffectSet(network=frozenset({"https://example.test"}))),
            DispatchJob(index=2, tool_name="publish", payload={}, effects=EffectSet(external=frozenset({"github"}))),
        ]

        stages = DispatchPlanner().plan(jobs)

        self.assertEqual([stage.kind for stage in stages], [DispatchPlanKind.SERIAL, DispatchPlanKind.SERIAL, DispatchPlanKind.SERIAL])


if __name__ == "__main__":
    unittest.main()
