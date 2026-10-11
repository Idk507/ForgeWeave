"""Analyzer adapter contracts for normalized verification findings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from forgeweave.verify.regression import Finding


@dataclass(frozen=True)
class AnalyzerInvocation:
    """One analyzer run request owned by an adapter implementation."""

    analyzer: str
    cwd: Path
    targets: tuple[Path, ...]
    config_hash: str
    timeout_seconds: int = 60

    def __post_init__(self) -> None:
        if not self.analyzer.strip():
            raise ValueError("analyzer must not be blank")
        if not self.targets:
            raise ValueError("targets must not be empty")
        if not self.config_hash.strip():
            raise ValueError("config_hash must not be blank")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be >= 1")


@dataclass(frozen=True)
class AnalyzerResult:
    """Normalized analyzer output after adapter-specific invocation and parsing."""

    analyzer: str
    command_argv: tuple[str, ...]
    cwd: str
    findings: tuple[Finding, ...] = ()
    exit_code: int | None = 0
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    infrastructure_error: str | None = None

    def __post_init__(self) -> None:
        if not self.analyzer.strip():
            raise ValueError("analyzer must not be blank")
        if not self.command_argv:
            raise ValueError("command_argv must not be empty")
        if not self.cwd.strip():
            raise ValueError("cwd must not be blank")
        mismatched = sorted({finding.analyzer for finding in self.findings if finding.analyzer != self.analyzer})
        if mismatched:
            raise ValueError(f"finding analyzer mismatch: {', '.join(mismatched)}")
        if self.infrastructure_error is not None and not self.infrastructure_error.strip():
            raise ValueError("infrastructure_error must not be blank when set")

    @property
    def is_infrastructure_failure(self) -> bool:
        """Return true when the analyzer result must fail closed without consuming repair budget."""

        return self.infrastructure_error is not None or self.timed_out or self.exit_code is None

    @property
    def is_code_failure(self) -> bool:
        """Return true when findings indicate code debt/regression rather than analyzer failure."""

        return bool(self.findings) and not self.is_infrastructure_failure


class AnalyzerAdapter(Protocol):
    """Adapter interface; implementations own process invocation and output parsing."""

    name: str

    def run(self, invocation: AnalyzerInvocation) -> AnalyzerResult:
        """Run the analyzer and return normalized findings or fail-closed infrastructure evidence."""
