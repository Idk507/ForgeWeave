"""Engine registry. Core code selects engines by name; vendor SDKs load lazily."""

from __future__ import annotations

from typing import Callable

from .contracts import DelegatedEngine, EngineUnavailable


def _jsonrpc(**kwargs: object) -> DelegatedEngine:
    from .general import JsonRpcEngine

    return JsonRpcEngine(**kwargs)  # type: ignore[arg-type]


def _appserver(**kwargs: object) -> DelegatedEngine:
    from .general import AppServerEngine

    return AppServerEngine(**kwargs)  # type: ignore[arg-type]


_FACTORIES: dict[str, Callable[..., DelegatedEngine]] = {
    "jsonrpc": _jsonrpc,
    "appserver": _appserver,
}


def get_engine(name: str, **kwargs: object) -> DelegatedEngine:
    """Return an engine by name. `native` is not an engine: it uses the core loop."""
    if name == "native":
        raise ValueError("'native' is the core agent loop, not a delegated engine")
    try:
        factory = _FACTORIES[name]
    except KeyError as exc:
        raise EngineUnavailable(f"unknown engine {name!r}") from exc
    return factory(**kwargs)
