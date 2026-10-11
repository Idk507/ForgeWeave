from __future__ import annotations

import unittest

from forgeweave.context.instructions import (
    InstructionAuthority,
    InstructionContradictionError,
    InstructionResolver,
    InstructionSource,
)


class InstructionResolverTests(unittest.TestCase):
    def test_resolves_instructions_by_precedence_with_hashes(self) -> None:
        resolver = InstructionResolver()

        resolved = resolver.resolve(
            [
                InstructionSource(
                    source="AGENTS.md",
                    authority=InstructionAuthority.REPOSITORY,
                    text="Repository guidance.",
                ),
                InstructionSource(
                    source="platform",
                    authority=InstructionAuthority.PLATFORM,
                    text="Platform guidance.",
                ),
                InstructionSource(
                    source="task",
                    authority=InstructionAuthority.TASK,
                    text="Task guidance.",
                    constraint_key="phase",
                ),
            ]
        )

        self.assertEqual([item.authority for item in resolved], ["platform", "task", "repository"])
        self.assertEqual([item.source for item in resolved], ["platform", "task", "AGENTS.md"])
        self.assertTrue(all(item.source_hash.startswith("sha256:") for item in resolved))
        self.assertTrue(all(item.token_estimate > 0 for item in resolved))

    def test_lower_trust_retrieved_content_stays_below_repository_guidance(self) -> None:
        resolver = InstructionResolver()

        resolved = resolver.resolve(
            [
                InstructionSource(
                    source="tool:web_search",
                    authority=InstructionAuthority.RETRIEVED,
                    text="A web page says to ignore repository policy.",
                ),
                InstructionSource(
                    source="AGENTS.md",
                    authority=InstructionAuthority.REPOSITORY,
                    text="Repository policy.",
                ),
                InstructionSource(
                    source="task",
                    authority=InstructionAuthority.TASK,
                    text="User task.",
                ),
            ]
        )

        self.assertEqual([item.authority for item in resolved], ["task", "repository", "retrieved"])
        self.assertFalse(resolved[-1].protected)

    def test_conflicting_same_authority_constraint_key_fails_loudly(self) -> None:
        resolver = InstructionResolver()

        with self.assertRaises(InstructionContradictionError) as raised:
            resolver.resolve(
                [
                    InstructionSource(
                        source="task:first",
                        authority=InstructionAuthority.TASK,
                        text="Use native engine.",
                        constraint_key="engine",
                    ),
                    InstructionSource(
                        source="task:second",
                        authority=InstructionAuthority.TASK,
                        text="Use delegated engine.",
                        constraint_key="engine",
                    ),
                ]
            )

        self.assertEqual(raised.exception.code, "INSTRUCTION_CONTRADICTION")
        self.assertEqual(raised.exception.details["constraint_key"], "engine")

    def test_instruction_budget_omits_low_precedence_items_without_truncating(self) -> None:
        resolver = InstructionResolver()

        resolved = resolver.resolve(
            [
                InstructionSource(
                    source="task",
                    authority=InstructionAuthority.TASK,
                    text="Keep the current request intact.",
                    token_estimate=5,
                ),
                InstructionSource(
                    source="retrieved",
                    authority=InstructionAuthority.RETRIEVED,
                    text="Optional retrieved context.",
                    token_estimate=50,
                ),
            ],
            max_instruction_tokens=10,
        )

        self.assertEqual([item.source for item in resolved], ["task"])


if __name__ == "__main__":
    unittest.main()
