"""Git-based before/after snapshots for analyzer regression checks."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import subprocess
from uuid import uuid4


@dataclass(frozen=True)
class GitSnapshot:
    """Patch snapshot claimed for one mutating step boundary."""

    snapshot_id: str
    repo_root: Path
    patch_path: Path
    base_commit: str
    patch_hash: str
    changed_paths: tuple[str, ...]


class GitSnapshotStore:
    """Capture repository state as an atomically claimed Git patch artifact."""

    def __init__(self, *, snapshot_dir: Path) -> None:
        self.snapshot_dir = snapshot_dir

    def claim(self, *, repo_root: Path, snapshot_id: str) -> GitSnapshot:
        """Return an existing snapshot or atomically claim the current Git diff."""

        if not snapshot_id.strip():
            raise ValueError("snapshot_id must not be blank")
        root = repo_root.resolve()
        if not (root / ".git").exists():
            raise ValueError(f"repo_root is not a Git repository: {root}")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.snapshot_dir / f"{snapshot_id}.patch"
        if path.exists():
            return self._read(snapshot_id=snapshot_id, repo_root=root, path=path)

        patch = _git(root, "diff", "--binary")
        base_commit = _git(root, "rev-parse", "HEAD").strip()
        changed_paths = tuple(line.strip() for line in _git(root, "diff", "--name-only").splitlines() if line.strip())
        header = _header(base_commit=base_commit, changed_paths=changed_paths)
        content = header + patch
        tmp = self.snapshot_dir / f".{snapshot_id}.{uuid4().hex}.tmp"
        tmp.write_text(content, encoding="utf-8")
        try:
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()
        return GitSnapshot(
            snapshot_id=snapshot_id,
            repo_root=root,
            patch_path=path,
            base_commit=base_commit,
            patch_hash=_hash_text(content),
            changed_paths=changed_paths,
        )

    def _read(self, *, snapshot_id: str, repo_root: Path, path: Path) -> GitSnapshot:
        content = path.read_text(encoding="utf-8")
        base_commit = ""
        changed_paths: tuple[str, ...] = ()
        for line in content.splitlines():
            if line.startswith("# base_commit: "):
                base_commit = line.removeprefix("# base_commit: ")
            elif line.startswith("# changed_paths: "):
                raw = line.removeprefix("# changed_paths: ")
                changed_paths = tuple(item for item in raw.split(";") if item)
            elif line == "# ---":
                break
        return GitSnapshot(
            snapshot_id=snapshot_id,
            repo_root=repo_root,
            patch_path=path,
            base_commit=base_commit,
            patch_hash=_hash_text(content),
            changed_paths=changed_paths,
        )


def _header(*, base_commit: str, changed_paths: tuple[str, ...]) -> str:
    joined = ";".join(changed_paths)
    return (
        "# forgeweave-git-snapshot-v1\n"
        f"# base_commit: {base_commit}\n"
        f"# changed_paths: {joined}\n"
        "# ---\n"
    )


def _hash_text(content: str) -> str:
    return "sha256:" + sha256(content.encode("utf-8")).hexdigest()


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout
