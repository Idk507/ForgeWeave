"""Credential resolution for model providers."""

from __future__ import annotations

import os
from typing import Mapping, Protocol


class KeyringBackend(Protocol):
    """Small subset of the keyring API used by ForgeWeave."""

    def get_password(self, service_name: str, username: str) -> str | None: ...


class CredentialError(ValueError):
    """Raised when a provider credential cannot be resolved."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class CredentialResolver:
    """Resolve secrets from OS keyring first, then explicit environment fallback."""

    def __init__(
        self,
        *,
        service_name: str = "forgeweave",
        keyring_backend: KeyringBackend | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        if not service_name.strip():
            raise ValueError("service_name must not be blank")
        self.service_name = service_name.strip()
        self._keyring = keyring_backend if keyring_backend is not None else _load_keyring_backend()
        self._env = env if env is not None else os.environ

    def resolve(self, username: str, *, env_names: tuple[str, ...]) -> str:
        """Return a secret without exposing it in errors."""

        if not username.strip():
            raise ValueError("username must not be blank")
        if self._keyring is not None:
            try:
                secret = self._keyring.get_password(self.service_name, username.strip())
            except Exception:
                secret = None
            if secret and secret.strip():
                return secret.strip()

        for name in env_names:
            value = self._env.get(name)
            if value and value.strip():
                return value.strip().strip('"').strip("'")

        names = ", ".join(env_names) if env_names else "none"
        raise CredentialError(
            "CREDENTIAL_NOT_FOUND",
            f"credential '{username.strip()}' not found in keyring service '{self.service_name}' or env vars: {names}",
        )


def _load_keyring_backend() -> KeyringBackend | None:
    try:
        import keyring  # type: ignore[import-not-found]
    except Exception:
        return None
    return keyring
