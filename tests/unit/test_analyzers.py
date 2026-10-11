from __future__ import annotations

from pathlib import Path
import unittest

from forgeweave.verify import AnalyzerInvocation, AnalyzerResult, Finding


class AnalyzerContractTests(unittest.TestCase):
    def test_invocation_requires_targets_and_stable_config_hash(self) -> None:
        with self.assertRaisesRegex(ValueError, "targets"):
            AnalyzerInvocation(analyzer="ruff", cwd=Path("C:/repo"), targets=(), config_hash="sha256:config")
        with self.assertRaisesRegex(ValueError, "config_hash"):
            AnalyzerInvocation(analyzer="ruff", cwd=Path("C:/repo"), targets=(Path("a.py"),), config_hash=" ")

    def test_result_accepts_normalized_findings_for_matching_analyzer(self) -> None:
        finding = Finding(file="a.py", analyzer="ruff", rule="F401", message="unused import", line=1)

        result = AnalyzerResult(
            analyzer="ruff",
            command_argv=("ruff", "check", "a.py", "--output-format", "json"),
            cwd="C:/repo",
            findings=(finding,),
            exit_code=1,
            stdout="[]",
        )

        self.assertTrue(result.is_code_failure)
        self.assertFalse(result.is_infrastructure_failure)
        self.assertEqual(result.findings, (finding,))

    def test_result_rejects_findings_from_a_different_analyzer(self) -> None:
        finding = Finding(file="a.py", analyzer="mypy", rule="attr-defined")

        with self.assertRaisesRegex(ValueError, "finding analyzer mismatch"):
            AnalyzerResult(
                analyzer="ruff",
                command_argv=("ruff", "check", "a.py"),
                cwd="C:/repo",
                findings=(finding,),
            )

    def test_infrastructure_failure_fails_closed_without_code_failure(self) -> None:
        result = AnalyzerResult(
            analyzer="ruff",
            command_argv=("ruff", "check", "a.py"),
            cwd="C:/repo",
            exit_code=None,
            stderr="timed out",
            timed_out=True,
            infrastructure_error="timeout",
        )

        self.assertTrue(result.is_infrastructure_failure)
        self.assertFalse(result.is_code_failure)


if __name__ == "__main__":
    unittest.main()
