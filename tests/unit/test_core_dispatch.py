from __future__ import annotations

import unittest

from forgeweave.core import DispatchJob, DispatchPlanner


class DispatchPlannerTests(unittest.TestCase):
    def test_returns_observations_in_request_order_even_when_execution_order_differs(self) -> None:
        execution_order: list[str] = []
        jobs = [
            DispatchJob(index=0, tool_name="first", payload={"value": 1}),
            DispatchJob(index=1, tool_name="second", payload={"value": 2}),
        ]

        def dispatch(job: DispatchJob) -> dict[str, object]:
            execution_order.append(job.tool_name)
            return {"tool_name": job.tool_name, "output": job.payload["value"]}

        results = DispatchPlanner().dispatch(jobs=reversed(jobs), dispatch=dispatch)

        self.assertEqual(execution_order, ["second", "first"])
        self.assertEqual(
            results,
            [
                {"tool_name": "first", "output": 1},
                {"tool_name": "second", "output": 2},
            ],
        )

    def test_captures_dispatch_errors_as_observations(self) -> None:
        jobs = [DispatchJob(index=0, tool_name="bad", payload={})]

        def dispatch(job: DispatchJob) -> dict[str, object]:
            raise RuntimeError("boom")

        results = DispatchPlanner().dispatch(jobs=jobs, dispatch=dispatch)

        self.assertEqual(results, [{"tool_name": "bad", "error": "boom"}])

    def test_rejects_duplicate_request_index(self) -> None:
        jobs = [DispatchJob(index=0, tool_name="a", payload={}), DispatchJob(index=0, tool_name="b", payload={})]

        with self.assertRaises(ValueError):
            DispatchPlanner().dispatch(jobs=jobs, dispatch=lambda job: {})


if __name__ == "__main__":
    unittest.main()
