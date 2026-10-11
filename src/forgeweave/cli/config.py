"""Safe configuration inspection for the minimal CLI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import sys

from forgeweave import __version__
from forgeweave.cli.isolation import IsolationView, default_host_isolation_profile, isolation_view
from forgeweave.contracts import ExecutionProfile


@dataclass(frozen=True)
class ConfigView:
    """Non-secret runtime configuration shown by `fw config show`."""

    package: str
    version: str
    python: str
    default_engine: str
    laya_enabled: bool
    repository_root_required_for_worktrees: bool
    isolation: IsolationView


def current_config_view(profile: ExecutionProfile | None = None) -> ConfigView:
    """Return a safe configuration projection without credential values."""

    effective_profile = profile or default_host_isolation_profile()
    return ConfigView(
        package="forgeweave",
        version=__version__,
        python=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        default_engine="native",
        laya_enabled=False,
        repository_root_required_for_worktrees=True,
        isolation=isolation_view(effective_profile),
    )


def render_config(view: ConfigView, *, as_json: bool) -> str:
    """Render safe configuration as text or JSON."""

    if as_json:
        payload = asdict(view)
        payload["isolation"] = view.isolation.to_dict()
        return json.dumps(payload, sort_keys=True)
    return "\n".join(
        [
            f"Package: {view.package}",
            f"Version: {view.version}",
            f"Python: {view.python}",
            f"Default engine: {view.default_engine}",
            f"Laya enabled: {str(view.laya_enabled).lower()}",
            f"Worktree root required: {str(view.repository_root_required_for_worktrees).lower()}",
            f"Isolation profile: {view.isolation.profile_id}",
            f"Restricted execution measured: {str(view.isolation.restricted_execution_measured).lower()}",
        ]
    )
