"""Workspace-scoped file tools."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from hashlib import sha256
from pathlib import Path
import re
import shutil
import subprocess

from forgeweave.contracts import EffectSet, ToolSpec

from .registry import ToolRegistry


class PathPolicyError(ValueError):
    """Raised when a requested path escapes or violates the workspace scope."""


class PatchConflictError(ValueError):
    """Raised when a hash-conditional patch cannot apply."""

    def __init__(self, message: str, *, current_hash: str) -> None:
        super().__init__(message)
        self.current_hash = current_hash


@dataclass(frozen=True)
class ReplaceResult:
    """Result from a hash-conditional text replacement."""

    path: str
    before_hash: str
    after_hash: str


class WorkspacePathGuard:
    """Normalize relative workspace paths and reject escapes."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def resolve(self, path: str, *, must_exist: bool = True) -> Path:
        """Return an absolute path inside the workspace."""

        if not path.strip():
            raise PathPolicyError("path must not be blank")
        requested = Path(path)
        if requested.is_absolute():
            raise PathPolicyError("absolute paths are not allowed")
        if _has_forbidden_part(requested):
            raise PathPolicyError("path contains a forbidden component")

        candidate = self.root / requested
        if must_exist:
            resolved = candidate.resolve(strict=True)
        else:
            parent = candidate.parent.resolve(strict=True)
            resolved = parent / candidate.name
        if not _is_relative_to(resolved, self.root):
            raise PathPolicyError("path escapes the workspace")
        return resolved

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()


class FileTools:
    """Read-only file tools and hash-conditional text replacement."""

    def __init__(self, guard: WorkspacePathGuard) -> None:
        self._guard = guard

    def list_dir(self, path: str = ".") -> list[str]:
        directory = self._guard.resolve(path)
        if not directory.is_dir():
            raise PathPolicyError("path is not a directory")
        results: list[str] = []
        for child in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
            resolved = self._guard.resolve(self._guard.relative(child))
            suffix = "/" if resolved.is_dir() else ""
            results.append(f"{self._guard.relative(resolved)}{suffix}")
        return results

    def glob(self, pattern: str) -> list[str]:
        if not pattern.strip() or Path(pattern).is_absolute() or _pattern_has_escape(pattern):
            raise PathPolicyError("glob pattern must stay inside the workspace")
        matches: list[str] = []
        for path in self._guard.root.rglob("*"):
            relative = self._guard.relative(path)
            if _matches_pattern(relative, pattern):
                self._guard.resolve(relative)
                matches.append(relative)
        return sorted(matches)

    def read_text(self, path: str, *, max_bytes: int = 1_000_000) -> str:
        resolved = self._guard.resolve(path)
        if not resolved.is_file():
            raise PathPolicyError("path is not a file")
        data = resolved.read_bytes()
        if len(data) > max_bytes:
            raise PathPolicyError("file exceeds read limit")
        return data.decode("utf-8")

    def search(self, pattern: str, *, glob_pattern: str = "**/*", max_results: int = 100) -> list[dict[str, object]]:
        if not pattern:
            raise ValueError("search pattern must not be empty")
        compiled = re.compile(pattern)
        rg_results = self._search_with_rg(pattern=pattern, glob_pattern=glob_pattern, max_results=max_results)
        if rg_results is not None:
            return rg_results
        results: list[dict[str, object]] = []
        for relative in self.glob(glob_pattern):
            resolved = self._guard.resolve(relative)
            if not resolved.is_file():
                continue
            try:
                text = resolved.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if compiled.search(line):
                    results.append({"path": relative, "line": line_number, "text": line})
                    if len(results) >= max_results:
                        return results
        return results

    def _search_with_rg(
        self,
        *,
        pattern: str,
        glob_pattern: str,
        max_results: int,
    ) -> list[dict[str, object]] | None:
        if shutil.which("rg") is None:
            return None
        completed = subprocess.run(
            [
                "rg",
                "--line-number",
                "--no-heading",
                "--color",
                "never",
                "--glob",
                glob_pattern,
                "--",
                pattern,
                ".",
            ],
            cwd=self._guard.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode == 1:
            return []
        if completed.returncode != 0:
            return None

        results: list[dict[str, object]] = []
        for raw_line in completed.stdout.splitlines():
            parsed = _parse_rg_line(raw_line)
            if parsed is None:
                continue
            path, line_number, text = parsed
            self._guard.resolve(path)
            results.append({"path": path, "line": line_number, "text": text})
            if len(results) >= max_results:
                return results
        return results

    def replace_text(self, *, path: str, expected_hash: str, old: str, new: str) -> ReplaceResult:
        resolved = self._guard.resolve(path)
        before_bytes = resolved.read_bytes()
        before_hash = content_hash(before_bytes)
        if before_hash != expected_hash:
            raise PatchConflictError("file hash does not match expected hash", current_hash=before_hash)

        text = before_bytes.decode("utf-8")
        occurrences = text.count(old)
        if occurrences != 1:
            raise PatchConflictError("replacement text must occur exactly once", current_hash=before_hash)

        resolved.write_text(text.replace(old, new, 1), encoding="utf-8")
        after_hash = content_hash(resolved.read_bytes())
        return ReplaceResult(path=self._guard.relative(resolved), before_hash=before_hash, after_hash=after_hash)


def register_file_tools(guard: WorkspacePathGuard, *, catalog_version: str) -> ToolRegistry:
    """Return a registry populated with the initial workspace file tools."""

    tools = FileTools(guard)
    registry = ToolRegistry(catalog_version=catalog_version)
    registry.register(
        ToolSpec(
            name="list_dir",
            description="List one workspace directory.",
            input_schema={
                "type": "object",
                "required": ["path"],
                "properties": {"path": {"type": "string"}},
            },
            effects=EffectSet(reads=frozenset({"workspace"})),
            schema_version="list-dir.v1",
        ),
        lambda arguments: tools.list_dir(arguments["path"]),
    )
    registry.register(
        ToolSpec(
            name="glob",
            description="Find workspace paths matching a glob pattern.",
            input_schema={
                "type": "object",
                "required": ["pattern"],
                "properties": {"pattern": {"type": "string"}},
            },
            effects=EffectSet(reads=frozenset({"workspace"})),
            schema_version="glob.v1",
        ),
        lambda arguments: tools.glob(arguments["pattern"]),
    )
    registry.register(
        ToolSpec(
            name="read_file",
            description="Read one UTF-8 workspace file.",
            input_schema={
                "type": "object",
                "required": ["path"],
                "properties": {"path": {"type": "string"}},
            },
            effects=EffectSet(reads=frozenset({"workspace"})),
            schema_version="read-file.v1",
        ),
        lambda arguments: tools.read_text(arguments["path"]),
    )
    registry.register(
        ToolSpec(
            name="search_text",
            description="Search UTF-8 workspace files for literal text.",
            input_schema={
                "type": "object",
                "required": ["pattern"],
                "properties": {
                    "pattern": {"type": "string"},
                    "glob_pattern": {"type": "string"},
                },
            },
            effects=EffectSet(reads=frozenset({"workspace"})),
            schema_version="search-text.v1",
        ),
        lambda arguments: tools.search(arguments["pattern"], glob_pattern=arguments.get("glob_pattern", "**/*")),
    )
    registry.register(
        ToolSpec(
            name="replace_text",
            description="Replace exact text in one workspace file when the file hash matches.",
            input_schema={
                "type": "object",
                "required": ["path", "expected_hash", "old", "new"],
                "properties": {
                    "path": {"type": "string"},
                    "expected_hash": {"type": "string"},
                    "old": {"type": "string"},
                    "new": {"type": "string"},
                },
            },
            effects=EffectSet(writes=frozenset({"workspace"})),
            schema_version="replace-text.v1",
        ),
        lambda arguments: tools.replace_text(
            path=arguments["path"],
            expected_hash=arguments["expected_hash"],
            old=arguments["old"],
            new=arguments["new"],
        ).__dict__,
    )
    return registry


def content_hash(data: bytes) -> str:
    """Return ForgeWeave's canonical sha256 text for bytes."""

    return "sha256:" + sha256(data).hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _has_forbidden_part(path: Path) -> bool:
    return any(part in {"", ".", ".."} or ":" in part for part in path.parts)


def _pattern_has_escape(pattern: str) -> bool:
    return any(part in {"", ".", ".."} or ":" in part for part in Path(pattern).parts)


def _matches_pattern(relative_path: str, pattern: str) -> bool:
    if pattern == "**/*":
        return True
    return fnmatch(relative_path, pattern)


def _parse_rg_line(raw_line: str) -> tuple[str, int, str] | None:
    first = raw_line.find(":")
    if first == -1:
        return None
    second = raw_line.find(":", first + 1)
    if second == -1:
        return None
    path = raw_line[:first].replace("\\", "/")
    line_text = raw_line[first + 1 : second]
    if path.startswith("./"):
        path = path[2:]
    try:
        line_number = int(line_text)
    except ValueError:
        return None
    return path, line_number, raw_line[second + 1 :]
