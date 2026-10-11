"""Deterministic tool dispatch observation ordering."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from forgeweave.contracts import EffectSet


class DispatchPlanKind(StrEnum):
    """Execution strategy for a dispatch stage."""

    PARALLEL_READS = "parallel_reads"
    SERIAL = "serial"


@dataclass(frozen=True)
class DispatchJob:
    """One dispatchable tool request with its model-order index."""

    index: int
    tool_name: str
    payload: dict[str, Any]
    effects: EffectSet = field(default_factory=EffectSet)


@dataclass(frozen=True)
class DispatchStage:
    """A group of jobs that may share one dispatch scheduling policy."""

    kind: DispatchPlanKind
    jobs: tuple[DispatchJob, ...]


class DispatchPlanner:
    """Execute dispatch jobs and return observations in model request order."""

    def plan(self, jobs: Iterable[DispatchJob]) -> list[DispatchStage]:
        """Group read-only jobs and serialize all effectful jobs in model order."""

        stages: list[DispatchStage] = []
        pending_reads: list[DispatchJob] = []
        for job in sorted(jobs, key=lambda item: item.index):
            if job.effects.is_read_only:
                pending_reads.append(job)
                continue
            if pending_reads:
                stages.append(DispatchStage(DispatchPlanKind.PARALLEL_READS, tuple(pending_reads)))
                pending_reads = []
            stages.append(DispatchStage(DispatchPlanKind.SERIAL, (job,)))
        if pending_reads:
            stages.append(DispatchStage(DispatchPlanKind.PARALLEL_READS, tuple(pending_reads)))
        self._validate_unique_indexes(job for stage in stages for job in stage.jobs)
        return stages

    def dispatch(
        self,
        *,
        jobs: Iterable[DispatchJob],
        dispatch: Callable[[DispatchJob], dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Run jobs and return observations sorted by the original request index."""

        job_list = list(jobs)
        self._validate_unique_indexes(job_list)
        observations: list[tuple[int, dict[str, Any]]] = []
        for job in job_list:
            observations.append((job.index, self._dispatch_one(job, dispatch)))
        return self._ordered_observations(observations)

    def dispatch_stages(
        self,
        *,
        jobs: Iterable[DispatchJob],
        serial_dispatch: Callable[[DispatchJob], dict[str, Any]],
        parallel_dispatch: Callable[[tuple[DispatchJob, ...]], list[tuple[int, dict[str, Any]]]] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute planned stages while preserving model-visible observation order.

        The optional parallel executor receives each read-only stage as a batch.
        If it is omitted, read stages fall back to serial execution.
        """

        observations: list[tuple[int, dict[str, Any]]] = []
        for stage in self.plan(jobs):
            if stage.kind is DispatchPlanKind.PARALLEL_READS and parallel_dispatch is not None:
                try:
                    observations.extend(parallel_dispatch(stage.jobs))
                except Exception as exc:
                    observations.extend((job.index, {"tool_name": job.tool_name, "error": str(exc)}) for job in stage.jobs)
                continue
            for job in stage.jobs:
                observations.append((job.index, self._dispatch_one(job, serial_dispatch)))
        return self._ordered_observations(observations)

    @staticmethod
    def _dispatch_one(job: DispatchJob, dispatch: Callable[[DispatchJob], dict[str, Any]]) -> dict[str, Any]:
        try:
            return dispatch(job)
        except Exception as exc:
            return {"tool_name": job.tool_name, "error": str(exc)}

    @staticmethod
    def _ordered_observations(observations: list[tuple[int, dict[str, Any]]]) -> list[dict[str, Any]]:
        return [observation for _, observation in sorted(observations, key=lambda item: item[0])]

    @staticmethod
    def _validate_unique_indexes(jobs: Iterable[DispatchJob]) -> None:
        seen: set[int] = set()
        for job in jobs:
            if job.index in seen:
                raise ValueError(f"duplicate dispatch index: {job.index}")
            seen.add(job.index)
