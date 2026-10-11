from __future__ import annotations

import json
from pathlib import Path
import unittest

from forgeweave.verify import AnalyzerInvocation, RuffAnalyzerAdapter


class RuffAnalyzerAdapterTests(unittest.TestCase):
    def test_builds_isolated_json_command_with_metric_rules_enabled(self) -> None:
        adapter = RuffAnalyzerAdapter()
        invocation = AnalyzerInvocation(
            analyzer="ruff",
            cwd=Path("C:/repo"),
            targets=(Path("C:/repo/pkg/a.py"),),
            config_hash="sha256:config",
        )

        argv = adapter.command_argv(invocation)

        self.assertEqual(argv[:6], ("ruff", "check", "--output-format", "json", "--isolated", "--select"))
        self.assertEqual(argv[6], "ALL")
        self.assertEqual(argv[-1], "pkg/a.py")

    def test_parses_standard_diagnostics_and_numeric_metric_findings(self) -> None:
        adapter = RuffAnalyzerAdapter()
        stdout = json.dumps(
            [
                {
                    "filename": "pkg/a.py",
                    "code": "F401",
                    "message": "`os` imported but unused",
                    "location": {"row": 1, "column": 1},
                },
                {
                    "filename": "pkg/a.py",
                    "code": "PLR0915",
                    "message": "process has too many statements (63 > 50)",
                    "location": {"row": 10, "column": 5},
                },
            ]
        )

        result = adapter.parse_stdout(
            stdout=stdout,
            stderr="",
            exit_code=1,
            command_argv=("ruff", "check", "pkg/a.py"),
            cwd="C:/repo",
        )

        self.assertFalse(result.is_infrastructure_failure)
        self.assertEqual(len(result.findings), 2)
        self.assertEqual(result.findings[0].rule, "F401")
        self.assertIsNone(result.findings[0].value)
        self.assertEqual(result.findings[1].rule, "PLR0915")
        self.assertEqual(result.findings[1].symbol, "process")
        self.assertEqual(result.findings[1].value, 63)
        self.assertEqual(result.findings[1].limit, 50)

    def test_numeric_metric_without_parseable_limit_remains_diagnostic(self) -> None:
        adapter = RuffAnalyzerAdapter()
        stdout = json.dumps(
            [
                {
                    "filename": "pkg/a.py",
                    "code": "C901",
                    "message": "main is too complex",
                    "location": {"row": 2, "column": 1},
                }
            ]
        )

        result = adapter.parse_stdout(
            stdout=stdout,
            stderr="",
            exit_code=1,
            command_argv=("ruff", "check", "pkg/a.py"),
            cwd="C:/repo",
        )

        self.assertEqual(result.findings[0].rule, "C901")
        self.assertEqual(result.findings[0].symbol, "main")
        self.assertIsNone(result.findings[0].value)
        self.assertIsNone(result.findings[0].limit)

    def test_invalid_json_is_infrastructure_failure(self) -> None:
        adapter = RuffAnalyzerAdapter()

        result = adapter.parse_stdout(
            stdout="not-json",
            stderr="",
            exit_code=1,
            command_argv=("ruff", "check", "pkg/a.py"),
            cwd="C:/repo",
        )

        self.assertTrue(result.is_infrastructure_failure)
        self.assertIn("invalid-json", result.infrastructure_error or "")
        self.assertEqual(result.findings, ())


if __name__ == "__main__":
    unittest.main()
