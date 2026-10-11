from __future__ import annotations

from types import SimpleNamespace
import unittest

from forgeweave.models import CredentialResolver, OpenAICompatibleConfig, OpenAICompatibleProvider, RetryPolicy


class OpenAICompatibleProviderTests(unittest.TestCase):
    def test_stream_normalizes_response_text_and_usage(self) -> None:
        client = _FakeClient(
            response=SimpleNamespace(
                output_text="azure-smoke-ok",
                usage=SimpleNamespace(input_tokens=3, output_tokens=2, total_tokens=5),
            )
        )
        provider = OpenAICompatibleProvider(
            config=OpenAICompatibleConfig(base_url="https://example.test/openai/v1", model="gpt-4o"),
            client=client,
        )

        chunks = list(provider.stream(messages=[{"role": "user", "content": "ping"}], tools=[], options={}))

        self.assertEqual([chunk.kind for chunk in chunks], ["text", "done"])
        self.assertEqual(chunks[0].content, "azure-smoke-ok")
        self.assertEqual(chunks[1].usage, {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5})
        self.assertEqual(client.requests[0]["model"], "gpt-4o")
        self.assertEqual(client.requests[0]["input"], "ping")

    def test_stream_falls_back_to_output_content_parts(self) -> None:
        client = _FakeClient(
            response=SimpleNamespace(
                output=[
                    SimpleNamespace(
                        content=[
                            SimpleNamespace(text="hello "),
                            SimpleNamespace(text="world"),
                        ]
                    )
                ],
                usage=None,
            )
        )
        provider = OpenAICompatibleProvider(
            config=OpenAICompatibleConfig(base_url="https://example.test/openai/v1", model="gpt-4o"),
            client=client,
        )

        chunks = list(provider.stream(messages=[{"role": "user", "content": "say hi"}], tools=[], options={}))

        self.assertEqual(chunks[0].content, "hello world")
        self.assertIsNone(chunks[1].usage)


    def test_stream_normalizes_response_function_call_items(self) -> None:
        client = _FakeClient(
            response=SimpleNamespace(
                output=[
                    SimpleNamespace(type="message", content=[SimpleNamespace(text="I will read it.")]),
                    SimpleNamespace(
                        type="function_call",
                        call_id="call-openai-1",
                        name="read_file",
                        arguments='{"path":"README.md"}',
                    ),
                ],
                usage=SimpleNamespace(input_tokens=9, output_tokens=4, total_tokens=13),
            )
        )
        provider = OpenAICompatibleProvider(
            config=OpenAICompatibleConfig(base_url="https://example.test/openai/v1", model="gpt-4o"),
            client=client,
        )

        chunks = list(
            provider.stream(
                messages=[{"role": "user", "content": "read README"}],
                tools=[{"name": "read_file", "schema_version": "read-file.v1"}],
                options={},
            )
        )

        self.assertEqual([chunk.kind for chunk in chunks], ["text", "tool_call", "done"])
        self.assertEqual(chunks[0].content, "I will read it.")
        self.assertEqual(chunks[1].call_id, "call-openai-1")
        self.assertEqual(
            chunks[1].content,
            '{"tool_name":"read_file","tool_schema_version":"read-file.v1","arguments":{"path":"README.md"}}',
        )
        self.assertEqual(chunks[2].usage, {"input_tokens": 9, "output_tokens": 4, "total_tokens": 13})
        self.assertEqual(client.requests[0]["tools"], [{"name": "read_file", "schema_version": "read-file.v1"}])


    def test_stream_retries_transient_provider_errors(self) -> None:
        client = _FakeClient(
            response=SimpleNamespace(output_text="ok-after-retry", usage=None),
            failures=[_ProviderError("temporary", status_code=429)],
        )
        provider = OpenAICompatibleProvider(
            config=OpenAICompatibleConfig(base_url="https://example.test/openai/v1", model="gpt-4o"),
            client=client,
            retry_policy=RetryPolicy(max_attempts=2, initial_delay_seconds=0, max_delay_seconds=0, jitter_ratio=0),
            sleep=lambda delay: None,
        )

        chunks = list(provider.stream(messages=[{"role": "user", "content": "ping"}], tools=[], options={}))

        self.assertEqual(chunks[0].content, "ok-after-retry")
        self.assertEqual(len(client.requests), 2)

    def test_stream_does_not_retry_non_retryable_provider_errors(self) -> None:
        client = _FakeClient(
            response=SimpleNamespace(output_text="unused", usage=None),
            failures=[_ProviderError("bad request", status_code=400)],
        )
        provider = OpenAICompatibleProvider(
            config=OpenAICompatibleConfig(base_url="https://example.test/openai/v1", model="gpt-4o"),
            client=client,
            retry_policy=RetryPolicy(max_attempts=3, initial_delay_seconds=0, max_delay_seconds=0, jitter_ratio=0),
            sleep=lambda delay: None,
        )

        with self.assertRaises(_ProviderError):
            list(provider.stream(messages=[{"role": "user", "content": "ping"}], tools=[], options={}))

        self.assertEqual(len(client.requests), 1)


    def test_from_env_can_read_api_key_from_credential_resolver(self) -> None:
        resolver = CredentialResolver(
            service_name="forgeweave",
            keyring_backend=_FakeKeyring({("forgeweave", "azure_api_key"): "keyring-secret"}),
            env={},
        )
        provider = OpenAICompatibleProvider.from_env(
            {
                "endpoint": "https://example.test/openai/v1",
                "deployment_name": "gpt-4o",
            },
            credential_resolver=resolver,
            client_factory=lambda *, base_url, api_key: _FakeClient(
                response=SimpleNamespace(output_text="ok", usage=None),
                base_url=base_url,
                api_key=api_key,
            ),
        )

        list(provider.stream(messages=[{"role": "user", "content": "ping"}], tools=[], options={}))

        self.assertEqual(provider._client.api_key, "keyring-secret")

    def test_from_env_requires_endpoint_model_and_key_without_exposing_secret(self) -> None:
        provider = OpenAICompatibleProvider.from_env(
            {
                "endpoint": "https://example.test/openai/v1",
                "deployment_name": "gpt-4o",
                "azure_api_key": "secret-value",
            },
            client_factory=lambda *, base_url, api_key: _FakeClient(
                response=SimpleNamespace(output_text="ok", usage=None),
                base_url=base_url,
                api_key=api_key,
            ),
        )
        chunks = list(provider.stream(messages=[{"role": "user", "content": "ping"}], tools=[], options={}))

        self.assertEqual(chunks[0].content, "ok")

        with self.assertRaises(ValueError) as missing:
            OpenAICompatibleProvider.from_env({"endpoint": "https://example.test/openai/v1"})

        self.assertNotIn("secret-value", str(missing.exception))
        self.assertIn("deployment_name", str(missing.exception))


class _FakeKeyring:
    def __init__(self, values: dict[tuple[str, str], str]) -> None:
        self.values = values

    def get_password(self, service_name: str, username: str) -> str | None:
        return self.values.get((service_name, username))


class _ProviderError(Exception):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class _FakeResponses:
    def __init__(self, owner: "_FakeClient") -> None:
        self._owner = owner

    def create(self, **kwargs: object) -> object:
        self._owner.requests.append(kwargs)
        if self._owner.failures:
            raise self._owner.failures.pop(0)
        return self._owner.response


class _FakeClient:
    def __init__(
        self,
        *,
        response: object,
        base_url: str | None = None,
        api_key: str | None = None,
        failures: list[Exception] | None = None,
    ) -> None:
        self.response = response
        self.failures = list(failures or [])
        self.base_url = base_url
        self.api_key = api_key
        self.requests: list[dict[str, object]] = []
        self.responses = _FakeResponses(self)


if __name__ == "__main__":
    unittest.main()
