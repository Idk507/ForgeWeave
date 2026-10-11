"""Verification command runner and repair-stop guard."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from time import perf_counter
import subprocess
from uuid import uuid4

from forgeweave.contracts import VerificationRun


@dataclass(frozen=True)
class VerificationCommand:
    """One verifier command with the evidence needed for replay."""

    criterion_ids: tuple[str, ...]
    argv: tuple[str, ...]
    cwd: Path
    verifier_version: str
    config_hash: str
    environment_profile_hash: str
    workspace_fingerprint: str
    untracked_input_hashes: dict[str, str] | None = None
    timeout_seconds: int = 60

    def __post_init__(self) -> None:
        if not self.criterion_ids:
            raise ValueError("criterion_ids must not be empty")
        if not self.argv:
            raise ValueError("argv must not be empty")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be >= 1")
        for value_name, value in (
            ("verifier_version", self.verifier_version),
            ("config_hash", self.config_hash),
            ("environment_profile_hash", self.environment_profile_hash),
            ("workspace_fingerprint", self.workspace_fingerprint),
        ):
            if not value.strip():
                raise ValueError(f"{value_name} must not be blank")


@dataclass(frozen=True)
class VerificationResult:
    """Completed verifier execution with bounded text retained for display."""

    run: VerificationRun
    stdout: str
    stderr: str
    timed_out: bool = False


class VerificationRunner:
    """Run local verifier commands and produce `VerificationRun` evidence."""

    def __init__(self, *, output_dir: Path, output_cap_bytes: int = 64_000) -> None:
        if output_cap_bytes < 1:
            raise ValueError("output_cap_bytes must be >= 1")
        self.output_dir = output_dir
        self.output_cap_bytes = output_cap_bytes

    def run(self, *, task_id: str, command: VerificationCommand) -> VerificationResult:
        """Execute one verifier command using argv, timeout and bounded output."""

        cwd = command.cwd.resolve()
        if not cwd.exists() or not cwd.is_dir():
            raise ValueError(f"verification cwd does not exist or is not a directory: {cwd}")

        timed_out = False
        started_at = perf_counter()
        try:
            completed = subprocess.run(
                list(command.argv),
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=command.timeout_seconds,
                check=False,
            )
            exit_code: int | None = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
            outcome = "passed" if completed.returncode == 0 else "failed"
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = None
            stdout = _coerce_output(exc.stdout)
            stderr = _coerce_output(exc.stderr)
            outcome = "inconclusive"

        duration_ms = max(0.0, (perf_counter() - started_at) * 1000.0)
        stdout, stderr = _cap_pair(stdout, stderr, self.output_cap_bytes)
        artifact_id = self._write_output_artifact(stdout=stdout, stderr=stderr, timed_out=timed_out)
        run = VerificationRun(
            run_id=f"verify-{uuid4()}",
            task_id=task_id,
            criterion_ids=command.criterion_ids,
            command_argv=command.argv,
            cwd=str(cwd),
            environment_profile_hash=command.environment_profile_hash,
            verifier_version=command.verifier_version,
            config_hash=command.config_hash,
            workspace_fingerprint=command.workspace_fingerprint,
            untracked_input_hashes=command.untracked_input_hashes or {},
            timeout_seconds=command.timeout_seconds,
            duration_ms=duration_ms,
            exit_code=exit_code,
            output_artifact_id=artifact_id,
            outcome=outcome,  # type: ignore[arg-type]
        )
        return VerificationResult(run=run, stdout=stdout, stderr=stderr, timed_out=timed_out)

    def _write_output_artifact(self, *, stdout: str, stderr: str, timed_out: bool) -> str:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        artifact_id = "verify-output-" + sha256(f"{uuid4()}|{stdout}|{stderr}|{timed_out}".encode("utf-8")).hexdigest()
        content = f"timed_out: {timed_out}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        (self.output_dir / f"{artifact_id}.txt").write_text(content, encoding="utf-8")
        return artifact_id


@dataclass(frozen=True)
class RepairDecision:
    """Decision after observing one failed or inconclusive verification result."""

    should_stop: bool
    reason: str | None
    fingerprint: str
    observed_failures: int


class RepairGuard:
    """Harness-wide guard against endless repair loops."""

    def __init__(self, *, max_repairs: int) -> None:
        if max_repairs < 1:
            raise ValueError("max_repairs must be >= 1")
        self.max_repairs = max_repairs
        self._seen: set[str] = set()
        self._failures = 0

    def record_failure(
        self,
        whole_input_fingerprint: str,
        criterion_ids: tuple[str, ...],
        outcome: str,
        exit_code: int | None,
    ) -> RepairDecision:
        """Record a failed verification and decide whether repair must stop."""

        fingerprint = repair_fingerprint(
            whole_input_fingerprint=whole_input_fingerprint,
            criterion_ids=criterion_ids,
            outcome=outcome,
            exit_code=exit_code,
        )
        repeated = fingerprint in self._seen
        self._seen.add(fingerprint)
        self._failures += 1

        if repeated:
            return RepairDecision(True, "repeated-identical-failure", fingerprint, self._failures)
        if self._failures >= self.max_repairs:
            return RepairDecision(True, "repair-budget-exhausted", fingerprint, self._failures)
        return RepairDecision(False, None, fingerprint, self._failures)

    def record_pass(self) -> None:
        """Clear failure history after a verified pass."""

        self._seen.clear()
        self._failures = 0


def repair_fingerprint(
    *,
    whole_input_fingerprint: str,
    criterion_ids: tuple[str, ...],
    outcome: str,
    exit_code: int | None,
) -> str:
    """Return a stable fingerprint for repeated-failure detection."""

    payload = "|".join([whole_input_fingerprint, ",".join(sorted(criterion_ids)), outcome, str(exit_code)])
    return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _cap_pair(stdout: str, stderr: str, cap_bytes: int) -> tuple[str, str]:
    remaining = cap_bytes
    capped_stdout = _cap_text(stdout, remaining)
    remaining -= len(capped_stdout.encode("utf-8"))
    capped_stderr = _cap_text(stderr, max(0, remaining))
    return capped_stdout, capped_stderr


def _cap_text(text: str, cap_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= cap_bytes:
        return text
    return encoded[:cap_bytes].decode("utf-8", errors="ignore")
