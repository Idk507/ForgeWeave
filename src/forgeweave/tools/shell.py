"""Workspace-scoped shell tool with argv, timeout and bounded output."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import subprocess
from time import monotonic
from typing import Iterable

from forgeweave.contracts import EffectSet, ToolSpec
from forgeweave.core import CancellationToken

from .files import PathPolicyError, WorkspacePathGuard
from .registry import ToolRegistry


class ShellPolicyError(ValueError):
    """Raised when a shell request violates ForgeWeave's local policy."""


@dataclass(frozen=True)
class ShellResult:
    """Bounded shell execution result."""

    argv: tuple[str, ...]
    cwd: str
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    output_truncated: bool
    cancelled: bool = False


class ShellTools:
    """Run subprocesses under a workspace cwd using argv-only execution."""

    def __init__(self, guard: WorkspacePathGuard) -> None:
        self._guard = guard

    def run(
        self,
        *,
        argv: Iterable[str],
        cwd: str,
        timeout_seconds: int,
        output_cap_bytes: int = 64_000,
        env: dict[str, str] | None = None,
        env_allowlist: frozenset[str] = frozenset(),
        cancellation: CancellationToken | None = None,
    ) -> ShellResult:
        """Execute one subprocess with bounded output and no shell string."""

        if cancellation is not None:
            cancellation.raise_if_cancelled()
        command = tuple(argv)
        self._validate_command(command)
        if timeout_seconds < 1:
            raise ShellPolicyError("timeout_seconds must be >= 1")
        if output_cap_bytes < 1:
            raise ShellPolicyError("output_cap_bytes must be >= 1")
        try:
            workdir = self._guard.resolve(cwd)
        except PathPolicyError as exc:
            raise ShellPolicyError(str(exc)) from exc
        if not workdir.is_dir():
            raise ShellPolicyError("cwd must be a workspace directory")

        safe_env = self._environment(env=env, env_allowlist=env_allowlist)
        exit_code, stdout, stderr, timed_out, cancelled = _run_subprocess(
            command=command,
            workdir=workdir,
            env=safe_env,
            timeout_seconds=timeout_seconds,
            cancellation=cancellation,
        )

        stdout, stderr, truncated = _cap_pair(stdout, stderr, output_cap_bytes)
        return ShellResult(
            argv=command,
            cwd=self._guard.relative(workdir),
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            output_truncated=truncated,
            cancelled=cancelled,
        )

    @staticmethod
    def _validate_command(argv: tuple[str, ...]) -> None:
        if not argv:
            raise ShellPolicyError("argv must contain at least one executable")
        for item in argv:
            if not isinstance(item, str) or not item:
                raise ShellPolicyError("argv entries must be non-empty strings")

    @staticmethod
    def _environment(*, env: dict[str, str] | None, env_allowlist: frozenset[str]) -> dict[str, str]:
        allowed = {key: value for key, value in os.environ.items() if key in env_allowlist}
        if env:
            for key in sorted(env_allowlist):
                if key in env:
                    allowed[key] = env[key]
        return allowed


def register_shell_tool(guard: WorkspacePathGuard, *, catalog_version: str) -> ToolRegistry:
    """Return a registry populated with the local shell tool."""

    shell = ShellTools(guard)
    registry = ToolRegistry(catalog_version=catalog_version)
    registry.register(
        ToolSpec(
            name="run_shell",
            description="Run one argv subprocess in the workspace with timeout and capped output.",
            input_schema={
                "type": "object",
                "required": ["argv", "cwd", "timeout_seconds"],
                "properties": {
                    "argv": {"type": "array"},
                    "cwd": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                    "output_cap_bytes": {"type": "integer"},
                },
            },
            effects=EffectSet(process=frozenset({"subprocess"})),
            schema_version="run-shell.v1",
        ),
        lambda arguments: asdict(
            shell.run(
                argv=arguments["argv"],
                cwd=arguments["cwd"],
                timeout_seconds=arguments["timeout_seconds"],
                output_cap_bytes=arguments.get("output_cap_bytes", 64_000),
            )
        ),
    )
    return registry


def _run_subprocess(
    *,
    command: tuple[str, ...],
    workdir: Path,
    env: dict[str, str],
    timeout_seconds: int,
    cancellation: CancellationToken | None,
) -> tuple[int | None, str, str, bool, bool]:
    process = subprocess.Popen(
        list(command),
        cwd=workdir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = monotonic() + timeout_seconds
    while True:
        if cancellation is not None and cancellation.cancelled:
            return _terminate_process(process, timed_out=False, cancelled=True)
        remaining = deadline - monotonic()
        if remaining <= 0:
            return _terminate_process(process, timed_out=True, cancelled=False)
        try:
            stdout, stderr = process.communicate(timeout=min(0.05, remaining))
            return process.returncode, stdout, stderr, False, False
        except subprocess.TimeoutExpired:
            continue


def _terminate_process(
    process: subprocess.Popen[str],
    *,
    timed_out: bool,
    cancelled: bool,
) -> tuple[int | None, str, str, bool, bool]:
    process.kill()
    stdout, stderr = process.communicate()
    return None, stdout, stderr, timed_out, cancelled


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _cap_pair(stdout: str, stderr: str, cap_bytes: int) -> tuple[str, str, bool]:
    original_bytes = len(stdout.encode("utf-8")) + len(stderr.encode("utf-8"))
    remaining = cap_bytes
    capped_stdout = _cap_text(stdout, remaining)
    remaining -= len(capped_stdout.encode("utf-8"))
    capped_stderr = _cap_text(stderr, max(0, remaining))
    capped_bytes = len(capped_stdout.encode("utf-8")) + len(capped_stderr.encode("utf-8"))
    return capped_stdout, capped_stderr, capped_bytes < original_bytes


def _cap_text(text: str, cap_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= cap_bytes:
        return text
    return encoded[:cap_bytes].decode("utf-8", errors="ignore")
