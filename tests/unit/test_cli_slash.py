from __future__ import annotations

import json
import unittest

from forgeweave.cli.slash import parse_slash_command, render_slash_command


class SlashCommandTests(unittest.TestCase):
    def test_normal_prompt_is_not_a_slash_command(self) -> None:
        self.assertIsNone(parse_slash_command("please edit the file"))

    def test_parses_known_command_with_arguments(self) -> None:
        command = parse_slash_command("  /status task-1 --json  ")

        assert command is not None
        self.assertEqual(command.name, "status")
        self.assertEqual(command.arguments, ("task-1", "--json"))
        self.assertEqual(command.raw, "/status task-1 --json")

    def test_rejects_blank_slash_command(self) -> None:
        with self.assertRaises(ValueError):
            parse_slash_command("/   ")

    def test_rejects_unknown_slash_command(self) -> None:
        with self.assertRaises(ValueError):
            parse_slash_command("/deploy now")

    def test_renders_help_as_json(self) -> None:
        command = parse_slash_command("/help")
        assert command is not None

        payload = json.loads(render_slash_command(command, as_json=True))

        self.assertEqual(payload["slash_command"], "help")
        self.assertIn("/status", payload["text"])


if __name__ == "__main__":
    unittest.main()
