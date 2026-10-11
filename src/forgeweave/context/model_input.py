"""Convert assembled context packets into provider-ready model messages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from forgeweave.context.assembler import ContextPacket
from forgeweave.core.diagnostics import LoopDiagnostics


@dataclass(frozen=True)
class ContextModelInput:
    """Provider-ready messages plus prompt-free diagnostics for one context packet."""

    messages: list[dict[str, Any]]
    diagnostics: LoopDiagnostics
    diagnostics_ref: str

    @classmethod
    def from_packet(cls, packet: ContextPacket, *, user_message: str) -> "ContextModelInput":
        """Build ordered model messages from manifest spans and a final user message."""

        cleaned_user_message = user_message.strip()
        if not cleaned_user_message:
            raise ValueError("user_message must not be blank")

        messages: list[dict[str, Any]] = []
        for span in packet.manifest.spans:
            try:
                text = packet.text_by_span_id[span.span_id]
            except KeyError as exc:
                raise ValueError(f"missing context text for span: {span.span_id}") from exc
            messages.append(
                {
                    "role": "system",
                    "content": f"Context span {span.span_id} from {span.source}:\n{text}",
                }
            )
        messages.append({"role": "user", "content": cleaned_user_message})
        return cls(
            messages=messages,
            diagnostics=LoopDiagnostics(context_manifest=packet.manifest),
            diagnostics_ref=f"context-manifest://{packet.manifest.request_id}",
        )
