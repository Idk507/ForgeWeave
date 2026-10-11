"""Policy-mediated test runner tool backed by verification evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from forgeweave.contracts import EffectSet, ToolSpec
from forgeweave.verify import VerificationCommand, VerificationResult, VerificationRunner

from .files import PathPolicyError, WorkspacePathGuard
from .registry import ToolRegistry


class TestRunnerTools:
    """Run explicit test commands and return captured verification evidence."""

    def __init__(self, guard: WorkspacePathGuard, *, output_dir: Path, output_cap_bytes: int = 64_000) -> None:
        self._guard = guard
        self._output_dir = output_dir
        self._output_cap_bytes = output_cap_bytes

    def run_tests(
        self,
        *,
        task_id: str,
        criterion_ids: Iterable[str],
        argv: Iterable[str],
        cwd: str,
        timeout_seconds: int,
        verifier_version: str,
        config_hash: str,
        environment_profile_hash: str,
        workspace_fingerprint: str,
        untracked_input_hashes: dict[str, str] | None = None,
    ) -> VerificationResult:
        """Run one explicit test command inside a guarded workspace cwd."""

        try:
            resolved_cwd = self._guard.resolve(cwd)
        except PathPolicyError as exc:
            raise ValueError(str(exc)) from exc
        if not resolved_cwd.is_dir():
            raise ValueError("test cwd must be a workspace directory")
        command = VerificationCommand(
            criterion_ids=tuple(criterion_ids),
            argv=tuple(argv),
            cwd=resolved_cwd,
            verifier_version=verifier_version,
            config_hash=config_hash,
            environment_profile_hash=environment_profile_hash,
            workspace_fingerprint=workspace_fingerprint,
            untracked_input_hashes=untracked_input_hashes,
            timeout_seconds=timeout_seconds,
        )
        return VerificationRunner(output_dir=self._output_dir, output_cap_bytes=self._output_cap_bytes).run(
            task_id=task_id,
            command=command,
        )


def register_test_runner_tool(guard: WorkspacePathGuard, *, output_dir: Path, catalog_version: str) -> ToolRegistry:
    """Return a registry populated with the test runner tool."""

    runner = TestRunnerTools(guard, output_dir=output_dir)
    registry = ToolRegistry(catalog_version=catalog_version)
    registry.register(
        ToolSpec(
            name="run_tests",
            description="Run one explicit test command and capture verification evidence.",
            input_schema={
                "type": "object",
                "required": [
                    "task_id",
                    "criterion_ids",
                    "argv",
                    "cwd",
                    "timeout_seconds",
                    "verifier_version",
                    "config_hash",
                    "environment_profile_hash",
                    "workspace_fingerprint",
                ],
                "properties": {
                    "task_id": {"type": "string"},
                    "criterion_ids": {"type": "array"},
                    "argv": {"type": "array"},
                    "cwd": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                    "verifier_version": {"type": "string"},
                    "config_hash": {"type": "string"},
                    "environment_profile_hash": {"type": "string"},
                    "workspace_fingerprint": {"type": "string"},
                },
            },
            effects=EffectSet(reads=frozenset({"workspace"}), process=frozenset({"test-runner"})),
            schema_version="run-tests.v1",
        ),
        lambda arguments: _result_to_dict(
            runner.run_tests(
                task_id=arguments["task_id"],
                criterion_ids=arguments["criterion_ids"],
                argv=arguments["argv"],
                cwd=arguments["cwd"],
                timeout_seconds=arguments["timeout_seconds"],
                verifier_version=arguments["verifier_version"],
                config_hash=arguments["config_hash"],
                environment_profile_hash=arguments["environment_profile_hash"],
                workspace_fingerprint=arguments["workspace_fingerprint"],
            )
        ),
    )
    return registry


def _result_to_dict(result: VerificationResult) -> dict[str, object]:
    return {
        "run": result.run.model_dump(mode="json"),
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": result.timed_out,
    }
