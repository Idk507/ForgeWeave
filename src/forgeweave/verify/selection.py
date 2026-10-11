"""Select verification commands from repository configuration."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import tomllib

from .runner import VerificationCommand


@dataclass(frozen=True)
class VerificationSelection:
    """Selected verifier commands and the config evidence used to choose them."""

    commands: tuple[VerificationCommand, ...]
    config_hash: str
    workspace_fingerprint: str
    sources: tuple[str, ...]


def select_verification_commands(
    repo_root: Path,
    *,
    environment_profile_hash: str = "sha256:local",
    timeout_seconds: int = 60,
) -> VerificationSelection:
    """Select default checks from a repository without executing them."""

    root = repo_root.resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"repo_root does not exist or is not a directory: {root}")
    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be >= 1")
    if not environment_profile_hash.strip():
        raise ValueError("environment_profile_hash must not be blank")

    pyproject = root / "pyproject.toml"
    config_bytes = pyproject.read_bytes() if pyproject.exists() else b""
    config_hash = "sha256:" + sha256(config_bytes).hexdigest()
    workspace_fingerprint = _workspace_fingerprint(root)
    commands: list[VerificationCommand] = []
    sources: list[str] = []

    data = _load_pyproject(pyproject)
    tool_config = data.get("tool", {}) if isinstance(data.get("tool", {}), dict) else {}

    if isinstance(tool_config.get("pytest"), dict):
        commands.append(
            _command(
                root=root,
                criterion_id="pytest",
                argv=("python", "-m", "pytest"),
                verifier_version="pytest",
                config_hash=config_hash,
                environment_profile_hash=environment_profile_hash,
                workspace_fingerprint=workspace_fingerprint,
                timeout_seconds=timeout_seconds,
            )
        )
        sources.append("pyproject.toml:[tool.pytest]")
    elif (root / "tests").is_dir():
        commands.append(
            _command(
                root=root,
                criterion_id="unittest",
                argv=("python", "-m", "unittest", "discover", "-s", "tests"),
                verifier_version="unittest",
                config_hash=config_hash,
                environment_profile_hash=environment_profile_hash,
                workspace_fingerprint=workspace_fingerprint,
                timeout_seconds=timeout_seconds,
            )
        )
        sources.append("tests/")

    if isinstance(tool_config.get("ruff"), dict):
        commands.append(
            _command(
                root=root,
                criterion_id="ruff",
                argv=("python", "-m", "ruff", "check", "."),
                verifier_version="ruff",
                config_hash=config_hash,
                environment_profile_hash=environment_profile_hash,
                workspace_fingerprint=workspace_fingerprint,
                timeout_seconds=timeout_seconds,
            )
        )
        sources.append("pyproject.toml:[tool.ruff]")

    return VerificationSelection(
        commands=tuple(commands),
        config_hash=config_hash,
        workspace_fingerprint=workspace_fingerprint,
        sources=tuple(sources),
    )


def _load_pyproject(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _command(
    *,
    root: Path,
    criterion_id: str,
    argv: tuple[str, ...],
    verifier_version: str,
    config_hash: str,
    environment_profile_hash: str,
    workspace_fingerprint: str,
    timeout_seconds: int,
) -> VerificationCommand:
    return VerificationCommand(
        criterion_ids=(criterion_id,),
        argv=argv,
        cwd=root,
        verifier_version=verifier_version,
        config_hash=config_hash,
        environment_profile_hash=environment_profile_hash,
        workspace_fingerprint=workspace_fingerprint,
        timeout_seconds=timeout_seconds,
    )


def _workspace_fingerprint(root: Path) -> str:
    parts: list[str] = []
    for name in ("pyproject.toml", "tox.ini", "pytest.ini", "setup.cfg"):
        path = root / name
        if path.exists() and path.is_file():
            parts.append(f"{name}:{sha256(path.read_bytes()).hexdigest()}")
    tests_dir = root / "tests"
    parts.append(f"tests_dir:{tests_dir.is_dir()}")
    return "sha256:" + sha256("|".join(parts).encode("utf-8")).hexdigest()
