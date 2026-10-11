"""Slash-command parsing for ForgeWeave CLI input."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SlashCommand:
    """Parsed slash command entered in an interactive-style prompt."""

    name: str
    arguments: tuple[str, ...]
    raw: str


SUPPORTED_SLASH_COMMANDS: tuple[str, ...] = ("config", "help", "status")


def parse_slash_command(text: str) -> SlashCommand | None:
    """Return a parsed slash command, or None when text is a normal prompt.

    A slash command must start at the first non-whitespace character and use a
    known command name. Unknown slash commands fail closed instead of being sent
    to the model as ordinary prompt text.
    """

    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    body = stripped[1:].strip()
    if not body:
        raise ValueError("slash command name must not be blank")
    parts = tuple(part for part in body.split() if part)
    name = parts[0].lower()
    if name not in SUPPORTED_SLASH_COMMANDS:
        raise ValueError(f"unsupported slash command: /{name}")
    return SlashCommand(name=name, arguments=parts[1:], raw=stripped)


def render_slash_command(command: SlashCommand, *, as_json: bool = False) -> str:
    """Render supported slash commands without invoking the model loop."""

    if command.name == "help":
        text = "Available slash commands: /help, /config, /status"
    elif command.name == "config":
        text = "Use `fw config show` for the effective local runtime configuration."
    elif command.name == "status":
        text = "Use `fw task status --task-file ...` or `--event-store ... --task-id ...` for durable task status."
    else:  # pragma: no cover - protected by parser validation
        raise ValueError(f"unsupported slash command: /{command.name}")

    if as_json:
        import json

        return json.dumps({"slash_command": command.name, "arguments": list(command.arguments), "text": text}, sort_keys=True)
    return text
