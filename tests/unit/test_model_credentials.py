from __future__ import annotations

import unittest

from forgeweave.models.credentials import CredentialError, CredentialResolver


class CredentialResolverTests(unittest.TestCase):
    def test_reads_secret_from_keyring_before_environment(self) -> None:
        keyring = _FakeKeyring({("forgeweave", "azure_api_key"): "keyring-secret"})
        resolver = CredentialResolver(service_name="forgeweave", keyring_backend=keyring, env={"AZURE_OPENAI_API_KEY": "env-secret"})

        value = resolver.resolve("azure_api_key", env_names=("AZURE_OPENAI_API_KEY",))

        self.assertEqual(value, "keyring-secret")

    def test_falls_back_to_environment_when_keyring_is_empty(self) -> None:
        resolver = CredentialResolver(service_name="forgeweave", keyring_backend=_FakeKeyring({}), env={"AZURE_OPENAI_API_KEY": " env-secret "})

        value = resolver.resolve("azure_api_key", env_names=("AZURE_OPENAI_API_KEY",))

        self.assertEqual(value, "env-secret")

    def test_missing_secret_error_does_not_expose_secret_values(self) -> None:
        resolver = CredentialResolver(service_name="forgeweave", keyring_backend=_BrokenKeyring("secret-in-error"), env={})

        with self.assertRaises(CredentialError) as raised:
            resolver.resolve("azure_api_key", env_names=("AZURE_OPENAI_API_KEY",))

        self.assertEqual(raised.exception.code, "CREDENTIAL_NOT_FOUND")
        self.assertNotIn("secret-in-error", str(raised.exception))
        self.assertIn("azure_api_key", str(raised.exception))
        self.assertIn("AZURE_OPENAI_API_KEY", str(raised.exception))


class _FakeKeyring:
    def __init__(self, values: dict[tuple[str, str], str]) -> None:
        self.values = values

    def get_password(self, service_name: str, username: str) -> str | None:
        return self.values.get((service_name, username))


class _BrokenKeyring:
    def __init__(self, message: str) -> None:
        self.message = message

    def get_password(self, service_name: str, username: str) -> str | None:
        raise RuntimeError(self.message)


if __name__ == "__main__":
    unittest.main()
