"""Typed registry for policy-mediated tool calls."""

from __future__ import annotations

from dataclasses import dataclass
import json
from hashlib import sha256
from typing import Any, Callable
from uuid import uuid4

from forgeweave.contracts import ToolCall, ToolSpec


class ToolRegistryError(ValueError):
    """Structured validation error for model-requested tool invocations."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class ToolInvocation:
    """A validated tool call and its handler output."""

    call: ToolCall
    output: Any


ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class _RegisteredTool:
    spec: ToolSpec
    handler: ToolHandler


class ToolRegistry:
    """Register typed tools and validate calls before dispatch."""

    def __init__(self, *, catalog_version: str) -> None:
        if not catalog_version.strip():
            raise ValueError("catalog_version must not be blank")
        self.catalog_version = catalog_version
        self._tools: dict[str, _RegisteredTool] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        """Register one tool spec and its local handler."""

        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = _RegisteredTool(spec=spec, handler=handler)

    def model_catalog(self) -> tuple[dict[str, Any], ...]:
        """Return registered tool schemas for model-provider tool selection."""

        return tuple(
            {
                "name": registered.spec.name,
                "description": registered.spec.description,
                "input_schema": registered.spec.input_schema,
                "schema_version": registered.spec.schema_version,
            }
            for registered in self._tools.values()
        )

    def invoke(self, *, tool_name: str, tool_schema_version: str, arguments: dict[str, Any]) -> ToolInvocation:
        """Validate and invoke a registered tool."""

        call = self.build_call(tool_name=tool_name, tool_schema_version=tool_schema_version, arguments=arguments)
        return ToolInvocation(call=call, output=self.dispatch(call))

    def build_call(self, *, tool_name: str, tool_schema_version: str, arguments: dict[str, Any]) -> ToolCall:
        """Validate arguments and build a ToolCall without dispatching the handler."""

        registered = self._tools.get(tool_name)
        if registered is None:
            raise ToolRegistryError("UNKNOWN_TOOL", f"unknown tool: {tool_name}", details={"tool_name": tool_name})
        spec = registered.spec
        if spec.schema_version != tool_schema_version:
            raise ToolRegistryError(
                "STALE_TOOL_SCHEMA",
                f"stale schema for tool: {tool_name}",
                details={
                    "tool_name": tool_name,
                    "requested": tool_schema_version,
                    "current": spec.schema_version,
                    "catalog_version": self.catalog_version,
                },
            )

        self._validate_arguments(spec.input_schema, arguments)
        return ToolCall(
            call_id=f"call-{uuid4()}",
            tool_name=spec.name,
            tool_schema_version=spec.schema_version,
            arguments=arguments,
            argument_hash=_stable_hash(arguments),
            effects=spec.effects,
        )

    def dispatch(self, call: ToolCall) -> Any:
        """Run a previously validated call against its registered handler."""

        registered = self._tools.get(call.tool_name)
        if registered is None:
            raise ToolRegistryError("UNKNOWN_TOOL", f"unknown tool: {call.tool_name}", details={"tool_name": call.tool_name})
        if registered.spec.schema_version != call.tool_schema_version:
            raise ToolRegistryError(
                "STALE_TOOL_SCHEMA",
                f"stale schema for tool: {call.tool_name}",
                details={"tool_name": call.tool_name},
            )
        self._validate_arguments(registered.spec.input_schema, call.arguments)
        return registered.handler(call.arguments)

    @staticmethod
    def _validate_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> None:
        if schema.get("type") != "object":
            raise ToolRegistryError("INVALID_SCHEMA", "tool input schema must be an object")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            raise ToolRegistryError("INVALID_SCHEMA", "tool input schema properties/required are malformed")
        for field in required:
            if field not in arguments:
                raise ToolRegistryError(
                    "INVALID_ARGUMENTS",
                    f"missing required argument: {field}",
                    details={"field": field, "reason": "missing"},
                )
        for field, value in arguments.items():
            expected = properties.get(field)
            if expected is None:
                raise ToolRegistryError(
                    "INVALID_ARGUMENTS",
                    f"unexpected argument: {field}",
                    details={"field": field, "reason": "unexpected"},
                )
            expected_type = expected.get("type")
            if expected_type is not None and not _matches_type(value, expected_type):
                raise ToolRegistryError(
                    "INVALID_ARGUMENTS",
                    f"invalid argument type for: {field}",
                    details={"field": field, "expected": expected_type, "actual": type(value).__name__},
                )


def _stable_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()


def _matches_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int | float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    return True
