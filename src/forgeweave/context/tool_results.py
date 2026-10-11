"""Projection of tool results into bounded model context."""

from __future__ import annotations

from dataclasses import dataclass

from forgeweave.context.assembler import ContextItem
from forgeweave.contracts import Artifact, ArtifactKind
from forgeweave.events import ArtifactStore


@dataclass(frozen=True)
class ToolResultProjection:
    """Projected model-visible result plus optional lossless artifact."""

    item: ContextItem
    artifact: Artifact | None = None


class ToolResultProjector:
    """Create bounded context items for tool output while preserving full artifacts."""

    def __init__(self, *, artifact_store: ArtifactStore, inline_cap_bytes: int = 16_000) -> None:
        if inline_cap_bytes < 1:
            raise ValueError("inline_cap_bytes must be positive")
        self.artifact_store = artifact_store
        self.inline_cap_bytes = inline_cap_bytes

    def project_text_result(self, *, task_id: str, call_id: str, tool_name: str, text: str) -> ContextItem:
        """Project text output as a bounded `ContextItem`.

        Small results remain inline. Large results are capped by UTF-8 bytes and
        the complete output is stored as a task artifact for scoped rehydration.
        """

        projection = self.project_text_result_with_artifact(
            task_id=task_id,
            call_id=call_id,
            tool_name=tool_name,
            text=text,
        )
        return projection.item

    def project_text_result_with_artifact(self, *, task_id: str, call_id: str, tool_name: str, text: str) -> ToolResultProjection:
        """Project text output and return artifact metadata when output is capped."""

        encoded = text.encode("utf-8")
        item_id = f"tool-result:{call_id}"
        source = f"tool:{tool_name}:{call_id}"
        if len(encoded) <= self.inline_cap_bytes:
            return ToolResultProjection(
                item=ContextItem(
                    item_id=item_id,
                    source=source,
                    authority="tool",
                    text=f"Tool result from {tool_name} ({call_id}):\n{text}",
                    priority=1_000,
                )
            )

        artifact = self.artifact_store.put_bytes(task_id=task_id, kind=ArtifactKind.LOG, data=encoded, redacted=False)
        capped = _decode_prefix(encoded, self.inline_cap_bytes)
        projected = (
            f"Tool result from {tool_name} ({call_id}) truncated to {self.inline_cap_bytes} bytes.\n"
            f"{capped}\n"
            f"Full output: {artifact.uri} sha256:{artifact.sha256} size_bytes:{artifact.size_bytes}"
        )
        return ToolResultProjection(
            item=ContextItem(
                item_id=item_id,
                source=source,
                authority="tool",
                text=projected,
                priority=1_000,
                redacted=True,
            ),
            artifact=artifact,
        )

    def rehydrate_text(self, artifact_uri: str) -> str:
        """Read a text artifact back by `artifact://<task_id>/<sha256>` URI."""

        prefix = "artifact://"
        if not artifact_uri.startswith(prefix):
            raise ValueError("artifact_uri must start with artifact://")
        rest = artifact_uri[len(prefix) :]
        task_id, sep, digest = rest.partition("/")
        if not sep or not task_id or not digest:
            raise ValueError("artifact_uri must be artifact://<task_id>/<sha256>")
        artifact = Artifact(
            artifact_id=digest,
            task_id=task_id,
            kind=ArtifactKind.LOG,
            uri=artifact_uri,
            sha256=digest,
            size_bytes=0,
        )
        return self.artifact_store.read_bytes(artifact).decode("utf-8")


def _decode_prefix(data: bytes, limit: int) -> str:
    return data[:limit].decode("utf-8", errors="ignore")
