"""SWE-bench optimized tools: persistent bash + string replacement editor.

These tools match the best-practice scaffold used by top SWE-bench submissions:
1. Persistent bash session (cd persists, environment persists)
2. String replacement file editor (targeted edits, not full file rewrites)

Model-agnostic - works with any LLM provider.
"""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

from .base import Tool, ToolResult


class BashTool(Tool):
    """Bash execution with persistent working directory.
    
    Maintains working directory across calls by tracking cd commands
    and running each command from the current directory.
    
    This is simpler and more reliable than PTY-based approaches.
    """

    def __init__(self, workspace_root: Path, timeout: int = 120):
        self.workspace_root = workspace_root.resolve()
        self.timeout = timeout
        self._cwd = self.workspace_root
        self._env: dict[str, str] = {
            **os.environ,
            "HOME": str(self.workspace_root),
            "TERM": "dumb",
        }

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return """Execute a bash command in a persistent shell session.

The session maintains state between calls:
- Working directory persists (cd commands work across calls)
- You can run any bash command

Use this for:
- Navigating the codebase (cd, ls, find, grep)
- Running tests (pytest, npm test, etc.)
- Installing dependencies
- Git operations
- Any shell command

The command will timeout after 120 seconds."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute",
                },
            },
            "required": ["command"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute command with persistent working directory."""
        command = kwargs.get("command", "")
        
        if not command.strip():
            return ToolResult(success=False, output="", error="Empty command")

        try:
            # Run command and capture new working directory
            # We append pwd to track directory changes
            full_command = f"{command}\n__EXIT_CODE__=$?\necho \"__CWD__$(pwd)__CWD__\"\nexit $__EXIT_CODE__"
            
            process = await asyncio.create_subprocess_shell(
                full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._cwd,
                env=self._env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {self.timeout}s",
                )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")
            
            # Extract and update working directory
            if "__CWD__" in stdout_str:
                parts = stdout_str.split("__CWD__")
                if len(parts) >= 3:
                    new_cwd = parts[1].strip()
                    if new_cwd and os.path.isdir(new_cwd):
                        # Verify it's still within workspace (security)
                        new_cwd_path = Path(new_cwd).resolve()
                        if str(new_cwd_path).startswith(str(self.workspace_root)):
                            self._cwd = new_cwd_path
                    # Remove the CWD marker from output
                    stdout_str = parts[0] + "".join(parts[2:])

            # Combine output
            output = stdout_str.strip()
            if stderr_str.strip():
                if output:
                    output += "\n" + stderr_str.strip()
                else:
                    output = stderr_str.strip()

            # Truncate very long outputs
            if len(output) > 100000:
                output = output[:50000] + "\n\n... (output truncated) ...\n\n" + output[-50000:]

            if process.returncode == 0:
                return ToolResult(success=True, output=output)
            else:
                return ToolResult(
                    success=False,
                    output=output,
                    error=f"Exit code: {process.returncode}",
                )

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def cleanup(self) -> None:
        """No cleanup needed for this simpler implementation."""
        pass


class StrReplaceEditorTool(Tool):
    """File editor using string replacement.
    
    This is more precise than full file rewrites:
    - Only changes the specific text you want to change
    - Preserves surrounding context
    - Less prone to errors from regenerating entire files
    - Matches how developers actually edit (find and replace)
    
    Supports:
    - view: Read file contents (with optional line range)
    - create: Create a new file
    - str_replace: Replace exact string with new string
    - insert: Insert text at a specific line number
    """

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root.resolve()

    @property
    def name(self) -> str:
        return "str_replace_editor"

    @property
    def description(self) -> str:
        return """A file editor that uses string replacement for precise edits.

Commands:
- view: Read a file's contents. Use view_range for specific lines.
- create: Create a new file with given content.
- str_replace: Replace an exact string with a new string. The old_str must match EXACTLY (including whitespace/indentation).
- insert: Insert text after a specific line number.

This is safer than rewriting entire files because:
1. You only change what you need to change
2. Surrounding code is preserved exactly
3. Less chance of introducing errors

For str_replace:
- old_str must be unique in the file (include enough context)
- old_str must match EXACTLY including all whitespace and indentation
- Use view first to see the exact content you're replacing"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["view", "create", "str_replace", "insert"],
                    "description": "The command to execute",
                },
                "path": {
                    "type": "string", 
                    "description": "Path to the file (relative to workspace root)",
                },
                "file_text": {
                    "type": "string",
                    "description": "Content for 'create' command",
                },
                "old_str": {
                    "type": "string",
                    "description": "Exact string to replace (for 'str_replace'). Must match exactly including whitespace.",
                },
                "new_str": {
                    "type": "string",
                    "description": "Replacement string (for 'str_replace'). Can be empty to delete.",
                },
                "insert_line": {
                    "type": "integer",
                    "description": "Line number after which to insert (for 'insert'). 0 = beginning of file.",
                },
                "new_str_for_insert": {
                    "type": "string",
                    "description": "Text to insert (for 'insert' command)",
                },
                "view_range": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Optional [start_line, end_line] for 'view' command (1-indexed, inclusive)",
                },
            },
            "required": ["command", "path"],
        }

    def _resolve_path(self, path: str) -> tuple[Path, str | None]:
        """Resolve and validate path. Returns (full_path, error_message)."""
        full_path = self.workspace_root / path
        try:
            full_path = full_path.resolve()
            if not str(full_path).startswith(str(self.workspace_root)):
                return full_path, "Path traversal not allowed"
        except Exception as e:
            return full_path, str(e)
        return full_path, None

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the file editor command."""
        command = kwargs.get("command", "")
        path = kwargs.get("path", "")

        if not path:
            return ToolResult(success=False, output="", error="Path is required")

        full_path, error = self._resolve_path(path)
        if error:
            return ToolResult(success=False, output="", error=error)

        if command == "view":
            return await self._view(full_path, kwargs.get("view_range"))
        elif command == "create":
            return await self._create(full_path, kwargs.get("file_text", ""))
        elif command == "str_replace":
            return await self._str_replace(
                full_path, 
                kwargs.get("old_str", ""), 
                kwargs.get("new_str", "")
            )
        elif command == "insert":
            return await self._insert(
                full_path,
                kwargs.get("insert_line", 0),
                kwargs.get("new_str_for_insert", ""),
            )
        else:
            return ToolResult(
                success=False, 
                output="", 
                error=f"Unknown command: {command}. Use view, create, str_replace, or insert."
            )

    async def _view(self, full_path: Path, view_range: list[int] | None) -> ToolResult:
        """View file contents."""
        if not full_path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {full_path.name}")
        
        if not full_path.is_file():
            return ToolResult(success=False, output="", error=f"Not a file: {full_path.name}")

        try:
            content = full_path.read_text()
            lines = content.splitlines(keepends=True)
            
            if view_range and len(view_range) == 2:
                start, end = view_range
                # Convert to 0-indexed
                start = max(0, start - 1)
                end = min(len(lines), end)
                lines = lines[start:end]
                # Add line numbers
                numbered = [f"{i+start+1:4d} | {line}" for i, line in enumerate(lines)]
                output = "".join(numbered)
            else:
                # Add line numbers to all lines
                numbered = [f"{i+1:4d} | {line}" for i, line in enumerate(lines)]
                output = "".join(numbered)
            
            # Truncate if too long
            if len(output) > 50000:
                output = output[:25000] + "\n\n... (truncated - use view_range for specific sections) ...\n\n" + output[-10000:]
            
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _create(self, full_path: Path, content: str) -> ToolResult:
        """Create a new file."""
        if full_path.exists():
            return ToolResult(
                success=False, 
                output="", 
                error=f"File already exists: {full_path.name}. Use str_replace to edit."
            )

        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            return ToolResult(success=True, output=f"Created {full_path.name} ({len(content)} bytes)")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _str_replace(self, full_path: Path, old_str: str, new_str: str) -> ToolResult:
        """Replace exact string in file."""
        if not full_path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {full_path.name}")

        if not old_str:
            return ToolResult(success=False, output="", error="old_str is required for str_replace")

        try:
            content = full_path.read_text()
            
            # Check if old_str exists
            count = content.count(old_str)
            if count == 0:
                # Help debug by showing similar lines
                lines = content.splitlines()
                old_first_line = old_str.splitlines()[0] if old_str else ""
                similar = [f"  {i+1}: {l}" for i, l in enumerate(lines) 
                          if old_first_line[:20] in l][:5]
                hint = ""
                if similar:
                    hint = f"\n\nSimilar lines found:\n" + "\n".join(similar)
                return ToolResult(
                    success=False, 
                    output="", 
                    error=f"old_str not found in {full_path.name}. Make sure it matches exactly including whitespace.{hint}"
                )
            
            if count > 1:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"old_str found {count} times in {full_path.name}. Include more context to make it unique."
                )

            # Perform replacement
            new_content = content.replace(old_str, new_str, 1)
            full_path.write_text(new_content)
            
            # Show a snippet of the change
            lines_changed = len(old_str.splitlines())
            return ToolResult(
                success=True, 
                output=f"Replaced {lines_changed} line(s) in {full_path.name}"
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _insert(self, full_path: Path, line_num: int, text: str) -> ToolResult:
        """Insert text after a specific line."""
        if not full_path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {full_path.name}")

        if not text:
            return ToolResult(success=False, output="", error="new_str_for_insert is required")

        try:
            content = full_path.read_text()
            lines = content.splitlines(keepends=True)
            
            # Handle insertion point
            if line_num <= 0:
                # Insert at beginning
                insert_idx = 0
            elif line_num >= len(lines):
                # Insert at end
                insert_idx = len(lines)
            else:
                insert_idx = line_num

            # Ensure text ends with newline if inserting in middle
            if not text.endswith("\n") and insert_idx < len(lines):
                text += "\n"

            lines.insert(insert_idx, text)
            new_content = "".join(lines)
            full_path.write_text(new_content)
            
            return ToolResult(
                success=True,
                output=f"Inserted {len(text.splitlines())} line(s) after line {line_num} in {full_path.name}"
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


def get_swebench_tools(workspace_root: Path) -> list[Tool]:
    """Get the optimized SWE-bench tools (bash + str_replace_editor)."""
    return [
        BashTool(workspace_root),
        StrReplaceEditorTool(workspace_root),
    ]
