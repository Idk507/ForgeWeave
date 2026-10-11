"""OpenAI-compatible Responses API provider adapter."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Callable, Iterable, Mapping

from .credentials import CredentialResolver
from .fake import ModelChunk
from .retry import RetryPolicy, RetryableModelError, call_with_retries


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    """Connection settings for an OpenAI-compatible Responses API deployment."""

    base_url: str
    model: str


class OpenAICompatibleProvider:
    """Provider adapter for Azure/OpenAI-compatible `client.responses.create` APIs."""

    def __init__(
        self,
        *,
        config: OpenAICompatibleConfig,
        client: Any,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        if not config.base_url.strip():
            raise ValueError("base_url must not be blank")
        if not config.model.strip():
            raise ValueError("model must not be blank")
        self.config = config
        self._client = client
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        client_factory: Callable[..., Any] | None = None,
        credential_resolver: CredentialResolver | None = None,
    ) -> "OpenAICompatibleProvider":
        """Create a provider from ForgeWeave's Azure/OpenAI-compatible env keys."""

        source = env or os.environ
        endpoint = _first_present(source, "endpoint", "OPENAI_BASE_URL", "AZURE_OPENAI_ENDPOINT")
        model = _first_present(source, "deployment_name", "OPENAI_MODEL", "AZURE_OPENAI_DEPLOYMENT")
        missing = [
            name
            for name, value in (
                ("endpoint", endpoint),
                ("deployment_name", model),
            )
            if not value
        ]
        if missing:
            raise ValueError("missing OpenAI-compatible provider configuration: " + ", ".join(missing))
        resolver = credential_resolver or CredentialResolver(env=source)
        api_key = resolver.resolve("azure_api_key", env_names=("azure_api_key", "OPENAI_API_KEY", "AZURE_OPENAI_API_KEY"))

        factory = client_factory or _default_client_factory
        return cls(
            config=OpenAICompatibleConfig(base_url=endpoint or "", model=model or ""),
            client=factory(base_url=endpoint, api_key=api_key),
        )

    def stream(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> Iterable[ModelChunk]:
        """Call the Responses API and expose the result as ForgeWeave chunks."""

        response = call_with_retries(
            lambda: self._create_response(messages=messages, tools=tools, options=options),
            policy=self._retry_policy,
            sleep=self._sleep or __import__("time").sleep,
        )
        yielded = False
        for chunk in _response_chunks(response, tools):
            yielded = True
            yield chunk
        if not yielded:
            text = _response_text(response)
            if text:
                yield ModelChunk(kind="text", content=text)
        yield ModelChunk(kind="done", usage=_usage_dict(getattr(response, "usage", None)))



    def _create_response(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]], options: dict[str, Any]) -> Any:
        try:
            return self._client.responses.create(
                model=options.get("model", self.config.model),
                input=_input_from_messages(messages),
                tools=tools,
            )
        except Exception as exc:
            if _is_retryable_provider_error(exc):
                raise RetryableModelError(str(exc)) from exc
            raise


def _response_chunks(response: Any, tools: list[dict[str, Any]]) -> Iterable[ModelChunk]:
    schema_versions = _tool_schema_versions(tools)
    for item in getattr(response, "output", []) or []:
        item_type = getattr(item, "type", None)
        if item_type == "function_call":
            name = getattr(item, "name", None)
            if not isinstance(name, str) or not name:
                continue
            arguments = _function_arguments(getattr(item, "arguments", {}))
            payload = {
                "tool_name": name,
                "tool_schema_version": schema_versions.get(name, "unknown"),
                "arguments": arguments,
            }
            call_id = getattr(item, "call_id", None) or getattr(item, "id", None)
            yield ModelChunk(
                kind="tool_call",
                call_id=str(call_id) if call_id else None,
                content=json.dumps(payload, separators=(",", ":"), sort_keys=False),
            )
            continue
        text = _item_text(item)
        if text:
            yield ModelChunk(kind="text", content=text)


def _item_text(item: Any) -> str:
    parts: list[str] = []
    for content in getattr(item, "content", []) or []:
        text = getattr(content, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _function_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            return loaded
    return {}


def _tool_schema_versions(tools: list[dict[str, Any]]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for tool in tools:
        name = tool.get("name")
        version = tool.get("schema_version") or tool.get("tool_schema_version")
        if isinstance(name, str) and isinstance(version, str):
            versions[name] = version
    return versions


def _is_retryable_provider_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if isinstance(status_code, int):
        return status_code in {408, 409, 425, 429} or 500 <= status_code <= 599
    name = exc.__class__.__name__.lower()
    return any(part in name for part in ("ratelimit", "rate_limit", "timeout", "connection"))

def _default_client_factory(*, base_url: str, api_key: str) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is required for OpenAI-compatible provider") from exc
    return OpenAI(base_url=base_url, api_key=api_key)


def _first_present(source: Mapping[str, str], *names: str) -> str | None:
    for name in names:
        value = source.get(name)
        if value and value.strip():
            return value.strip().strip('"').strip("'")
    return None


def _input_from_messages(messages: list[dict[str, Any]]) -> str | list[dict[str, Any]]:
    if len(messages) == 1 and messages[0].get("role") == "user":
        content = messages[0].get("content")
        if isinstance(content, str):
            return content
    return messages


def _response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text

    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _usage_dict(usage: Any) -> dict[str, int] | None:
    if usage is None:
        return None
    values: dict[str, int] = {}
    for name in ("input_tokens", "output_tokens", "total_tokens", "prompt_tokens", "completion_tokens"):
        value = getattr(usage, name, None)
        if isinstance(value, int):
            values[name] = value
    return values or None
