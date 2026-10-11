from __future__ import annotations

import unittest

from forgeweave.contracts import EffectSet, ToolSpec
from forgeweave.tools import ToolRegistry, ToolRegistryError


class ToolRegistryTests(unittest.TestCase):
    def test_invokes_registered_tool_with_validated_arguments(self) -> None:
        registry = ToolRegistry(catalog_version="tools-v1")
        registry.register(
            ToolSpec(
                name="read_file",
                description="Read a file.",
                input_schema={
                    "type": "object",
                    "required": ["path"],
                    "properties": {"path": {"type": "string"}},
                },
                effects=EffectSet(reads=frozenset({"workspace"})),
                schema_version="read-file.v1",
            ),
            lambda arguments: {"path": arguments["path"], "ok": True},
        )

        result = registry.invoke(
            tool_name="read_file",
            tool_schema_version="read-file.v1",
            arguments={"path": "README.md"},
        )

        self.assertEqual(result.output, {"path": "README.md", "ok": True})
        self.assertEqual(result.call.tool_name, "read_file")
        self.assertEqual(result.call.argument_hash.startswith("sha256:"), True)


    def test_model_catalog_exports_registered_tool_schema(self) -> None:
        registry = ToolRegistry(catalog_version="tools-v1")
        registry.register(
            ToolSpec(
                name="write_text",
                description="Write a file.",
                input_schema={
                    "type": "object",
                    "required": ["path"],
                    "properties": {"path": {"type": "string"}},
                },
                effects=EffectSet(writes=frozenset({"workspace"})),
                schema_version="write-text.v1",
            ),
            lambda arguments: "ok",
        )

        catalog = registry.model_catalog()

        self.assertEqual(
            catalog,
            (
                {
                    "name": "write_text",
                    "description": "Write a file.",
                    "input_schema": {
                        "type": "object",
                        "required": ["path"],
                        "properties": {"path": {"type": "string"}},
                    },
                    "schema_version": "write-text.v1",
                },
            ),
        )

    def test_unknown_stale_catalog_and_invalid_arguments_are_structured(self) -> None:
        registry = ToolRegistry(catalog_version="tools-v1")
        registry.register(
            ToolSpec(
                name="read_file",
                description="Read a file.",
                input_schema={
                    "type": "object",
                    "required": ["path"],
                    "properties": {"path": {"type": "string"}},
                },
                effects=EffectSet(reads=frozenset({"workspace"})),
                schema_version="read-file.v1",
            ),
            lambda arguments: {"path": arguments["path"]},
        )

        with self.assertRaises(ToolRegistryError) as unknown:
            registry.invoke(tool_name="missing", tool_schema_version="missing.v1", arguments={})
        with self.assertRaises(ToolRegistryError) as stale:
            registry.invoke(tool_name="read_file", tool_schema_version="old.v1", arguments={"path": "README.md"})
        with self.assertRaises(ToolRegistryError) as invalid:
            registry.invoke(tool_name="read_file", tool_schema_version="read-file.v1", arguments={"path": 123})

        self.assertEqual(unknown.exception.code, "UNKNOWN_TOOL")
        self.assertEqual(stale.exception.code, "STALE_TOOL_SCHEMA")
        self.assertEqual(invalid.exception.code, "INVALID_ARGUMENTS")
        self.assertEqual(invalid.exception.details["field"], "path")


if __name__ == "__main__":
    unittest.main()
