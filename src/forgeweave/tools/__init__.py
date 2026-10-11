"""Built-in ForgeWeave tool registry and local workspace tools."""

from .files import (
    FileTools,
    PathPolicyError,
    PatchConflictError,
    ReplaceResult,
    WorkspacePathGuard,
    content_hash,
    register_file_tools,
)
from .registry import ToolInvocation, ToolRegistry, ToolRegistryError
from .git import GitCommit, GitDiff, GitPolicyError, GitStatus, GitTools, register_git_tools
from .shell import ShellPolicyError, ShellResult, ShellTools, register_shell_tool
from .test_runner import TestRunnerTools, register_test_runner_tool

__all__ = [
    "FileTools",
    "GitCommit",
    "GitDiff",
    "GitPolicyError",
    "GitStatus",
    "GitTools",
    "PathPolicyError",
    "PatchConflictError",
    "ReplaceResult",
    "register_file_tools",
    "register_git_tools",
    "register_shell_tool",
    "register_test_runner_tool",
    "ShellPolicyError",
    "ShellResult",
    "ShellTools",
    "TestRunnerTools",
    "ToolInvocation",
    "ToolRegistry",
    "ToolRegistryError",
    "WorkspacePathGuard",
    "content_hash",
]
