"""Ruff analyzer adapter for diagnostics and numeric complexity metrics."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
import subprocess

from forgeweave.verify.analyzers import AnalyzerInvocation, AnalyzerResult
from forgeweave.verify.regression import Finding

_NUMERIC_RULES = frozenset({"C901", "PLR0912", "PLR0915", "PLR1702"})
_METRIC_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*>\s*(?P<limit>\d+(?:\.\d+)?)")
_SYMBOL_RE = re.compile(r"^(?P<symbol>[A-Za-z_][\w.<>]*)\s+(?:is|has|contains)\b")


@dataclass(frozen=True)
class RuffAnalyzerAdapter:
    """Run Ruff in isolated JSON mode and normalize its output to findings."""

    executable: str = "ruff"
    selected_rules: tuple[str, ...] = ("ALL",)
    name: str = "ruff"

    def command_argv(self, invocation: AnalyzerInvocation) -> tuple[str, ...]:
        """Build the Ruff command without consulting repository-local configuration."""

        rules = ",".join(self.selected_rules)
        return (
            self.executable,
            "check",
            "--output-format",
            "json",
            "--isolated",
            "--select",
            rules,
            *tuple(_target_arg(invocation.cwd, target) for target in invocation.targets),
        )

    def run(self, invocation: AnalyzerInvocation) -> AnalyzerResult:
        """Execute Ruff and return normalized findings or infrastructure evidence."""

        command = self.command_argv(invocation)
        cwd = str(invocation.cwd)
        try:
            completed = subprocess.run(
                list(command),
                cwd=invocation.cwd,
                capture_output=True,
                text=True,
                timeout=invocation.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return AnalyzerResult(
                analyzer=self.name,
                command_argv=command,
                cwd=cwd,
                exit_code=None,
                stdout=_coerce_output(exc.stdout),
                stderr=_coerce_output(exc.stderr),
                timed_out=True,
                infrastructure_error="timeout",
            )
        except OSError as exc:
            return AnalyzerResult(
                analyzer=self.name,
                command_argv=command,
                cwd=cwd,
                exit_code=None,
                stderr=str(exc),
                infrastructure_error=type(exc).__name__,
            )
        return self.parse_stdout(
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
            command_argv=command,
            cwd=cwd,
        )

    def parse_stdout(
        self,
        *,
        stdout: str,
        stderr: str,
        exit_code: int,
        command_argv: tuple[str, ...],
        cwd: str,
    ) -> AnalyzerResult:
        """Parse Ruff JSON output into normalized findings."""

        try:
            payload = json.loads(stdout or "[]")
        except json.JSONDecodeError as exc:
            return AnalyzerResult(
                analyzer=self.name,
                command_argv=command_argv,
                cwd=cwd,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                infrastructure_error=f"invalid-json: {exc.msg}",
            )
        if not isinstance(payload, list):
            return AnalyzerResult(
                analyzer=self.name,
                command_argv=command_argv,
                cwd=cwd,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                infrastructure_error="invalid-json: expected list",
            )
        findings: list[Finding] = []
        for item in payload:
            if not isinstance(item, dict):
                return AnalyzerResult(
                    analyzer=self.name,
                    command_argv=command_argv,
                    cwd=cwd,
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    infrastructure_error="invalid-json: expected diagnostic object",
                )
            findings.append(_finding_from_item(item, analyzer=self.name))
        return AnalyzerResult(
            analyzer=self.name,
            command_argv=command_argv,
            cwd=cwd,
            findings=tuple(findings),
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )


def _finding_from_item(item: dict[str, object], *, analyzer: str) -> Finding:
    rule = str(item.get("code") or "unknown")
    message = str(item.get("message") or "")
    location = item.get("location")
    row = location.get("row", 0) if isinstance(location, dict) else 0
    filename = str(item.get("filename") or "")
    if rule in _NUMERIC_RULES:
        value, limit = _metric_pair(message)
        return Finding(
            file=filename,
            analyzer=analyzer,
            rule=rule,
            message=message,
            symbol=_symbol(message),
            line=_int_or_zero(row),
            value=value,
            limit=limit,
        )
    return Finding(
        file=filename,
        analyzer=analyzer,
        rule=rule,
        message=message,
        line=_int_or_zero(row),
    )


def _metric_pair(message: str) -> tuple[float | None, float | None]:
    match = _METRIC_RE.search(message)
    if match is None:
        return None, None
    return float(match.group("value")), float(match.group("limit"))


def _symbol(message: str) -> str | None:
    match = _SYMBOL_RE.search(message)
    if match is None:
        return None
    return match.group("symbol")


def _target_arg(cwd: Path, target: Path) -> str:
    try:
        return target.relative_to(cwd).as_posix()
    except ValueError:
        return str(target)


def _int_or_zero(value: object) -> int:
    return value if isinstance(value, int) else 0


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
