"""Standard coding tools for the agent."""

import asyncio
import os
from pathlib import Path
from typing import Any

from .base import Tool, ToolResult


class ReadFileTool(Tool):
    """Read contents of a file."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file at the given path."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to workspace root.",
                },
            },
            "required": ["path"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", "")
        full_path = self.workspace_root / path

        # Security: prevent path traversal
        try:
            full_path = full_path.resolve()
            if not str(full_path).startswith(str(self.workspace_root.resolve())):
                return ToolResult(success=False, output="", error="Path traversal not allowed")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

        if not full_path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")

        if not full_path.is_file():
            return ToolResult(success=False, output="", error=f"Not a file: {path}")

        try:
            content = full_path.read_text()
            return ToolResult(success=True, output=content)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class WriteFileTool(Tool):
    """Write contents to a file."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file. Creates the file if it doesn't exist."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file, relative to workspace root.",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file.",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        full_path = self.workspace_root / path

        # Security: prevent path traversal
        try:
            full_path = full_path.resolve()
            if not str(full_path).startswith(str(self.workspace_root.resolve())):
                return ToolResult(success=False, output="", error="Path traversal not allowed")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            return ToolResult(success=True, output=f"Successfully wrote to {path}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ListDirectoryTool(Tool):
    """List contents of a directory."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return "List files and directories at the given path."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the directory, relative to workspace root. Use '.' for root.",
                },
            },
            "required": ["path"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", ".")
        full_path = self.workspace_root / path

        try:
            full_path = full_path.resolve()
            if not str(full_path).startswith(str(self.workspace_root.resolve())):
                return ToolResult(success=False, output="", error="Path traversal not allowed")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

        if not full_path.exists():
            return ToolResult(success=False, output="", error=f"Directory not found: {path}")

        if not full_path.is_dir():
            return ToolResult(success=False, output="", error=f"Not a directory: {path}")

        try:
            entries = []
            for entry in sorted(full_path.iterdir()):
                suffix = "/" if entry.is_dir() else ""
                entries.append(f"{entry.name}{suffix}")
            return ToolResult(success=True, output="\n".join(entries))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class RunCommandTool(Tool):
    """Run a shell command."""

    def __init__(self, workspace_root: Path, timeout: int = 30):
        self.workspace_root = workspace_root
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "run_command"

    @property
    def description(self) -> str:
        return f"Run a shell command in the workspace. Timeout: {self.timeout}s."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to run.",
                },
            },
            "required": ["command"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        command = kwargs.get("command", "")

        # Basic command sanitization
        dangerous_patterns = ["rm -rf /", "sudo", "chmod 777", "> /dev/"]
        for pattern in dangerous_patterns:
            if pattern in command:
                return ToolResult(
                    success=False, output="", error=f"Dangerous command pattern: {pattern}"
                )

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_root,
                env={**os.environ, "HOME": str(self.workspace_root)},
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
            except TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {self.timeout}s",
                )

            output = stdout.decode() + stderr.decode()

            if process.returncode == 0:
                return ToolResult(success=True, output=output)
            else:
                return ToolResult(
                    success=False,
                    output=output,
                    error=f"Command failed with exit code {process.returncode}",
                )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class SearchFilesTool(Tool):
    """Search for files matching a pattern."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return "Search for files matching a glob pattern."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files, e.g., '**/*.py' or 'src/**/*.ts'",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        pattern = kwargs.get("pattern", "")

        try:
            matches = list(self.workspace_root.glob(pattern))
            # Make paths relative
            relative_paths = [
                str(p.relative_to(self.workspace_root)) for p in matches if p.is_file()
            ][:100]  # Limit results

            if not relative_paths:
                return ToolResult(success=True, output="No files found matching pattern.")

            return ToolResult(success=True, output="\n".join(relative_paths))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GrepTool(Tool):
    """Search for text in files."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return "Search for a text pattern in files."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Text pattern to search for.",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Glob pattern for files to search, e.g., '**/*.py'. Default: all files.",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        pattern = kwargs.get("pattern", "")
        file_pattern = kwargs.get("file_pattern", "**/*")

        try:
            results = []
            files = list(self.workspace_root.glob(file_pattern))[:1000]  # Limit files

            for file_path in files:
                if not file_path.is_file():
                    continue
                try:
                    content = file_path.read_text()
                    for i, line in enumerate(content.splitlines(), 1):
                        if pattern.lower() in line.lower():
                            rel_path = file_path.relative_to(self.workspace_root)
                            results.append(f"{rel_path}:{i}: {line.strip()}")
                            if len(results) >= 50:  # Limit matches
                                break
                except (UnicodeDecodeError, PermissionError):
                    continue

                if len(results) >= 50:
                    break

            if not results:
                return ToolResult(success=True, output="No matches found.")

            return ToolResult(success=True, output="\n".join(results))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


def get_coding_tools(workspace_root: Path) -> list[Tool]:
    """Get all standard coding tools for a workspace."""
    return [
        ReadFileTool(workspace_root),
        WriteFileTool(workspace_root),
        ListDirectoryTool(workspace_root),
        RunCommandTool(workspace_root),
        SearchFilesTool(workspace_root),
        GrepTool(workspace_root),
    ]
