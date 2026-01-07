"""The reset_context tool - core of the experiment.

This tool allows an agent to:
1. Extract a learning from the current exploration
2. Signal that the last N messages should be dropped
3. Continue with just the learning injected

The actual context manipulation happens in the agent harness,
but this tool provides the interface for the agent to invoke it.
"""

from typing import Any

from pydantic import BaseModel

from .base import Tool, ToolResult


class ResetContextRequest(BaseModel):
    """Request to reset context with a learning."""

    learning: str
    steps_back: int


class ResetContextTool(Tool):
    """Tool that lets the agent drop context and keep only a learning.

    When invoked, this signals to the agent harness that it should:
    1. Take the 'learning' string
    2. Drop the last 'steps_back' messages from the conversation
    3. Inject the learning as a system/user message
    4. Continue from there

    This is a "meta" tool - it doesn't execute anything itself,
    it returns a signal that the harness interprets.
    """

    @property
    def name(self) -> str:
        return "reset_context"

    @property
    def description(self) -> str:
        return """Reset the conversation context by dropping recent messages and preserving a summary.

Use this when:
- You've been exploring unproductive paths and want to start fresh
- You found what you needed and the search steps are now clutter
- You want to try a different approach without confusion from failed attempts

What it does:
1. Drops the last N messages from the conversation
2. Injects your "learning" summary back into context
3. You continue from there with a clean slate

Example: After 8 messages searching for a config file, you find it at /src/config.yaml.
Call: reset_context(learning="Config file is at /src/config.yaml", steps_back=8)
Result: The 8 search messages are removed, your learning is preserved, context is cleaner.
"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "learning": {
                    "type": "string",
                    "description": (
                        "A summary of what you learned. This will be preserved "
                        "after dropping messages. Be specific: include file paths, "
                        "line numbers, root causes, or key decisions."
                    ),
                },
                "steps_back": {
                    "type": "integer",
                    "description": (
                        "How many recent messages to drop. Count your tool calls "
                        "and responses since you started this exploration path."
                    ),
                    "minimum": 1,
                },
            },
            "required": ["learning", "steps_back"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Signal reset context request.

        The actual context manipulation happens in the agent harness.
        This just validates the request and returns a signal.
        """
        try:
            request = ResetContextRequest(**kwargs)

            # Validate steps_back is at least 1
            if request.steps_back < 1:
                return ToolResult(
                    success=False,
                    output="",
                    error="steps_back must be at least 1",
                )

            # Return a special signal that the harness will interpret
            return ToolResult(
                success=True,
                output=f"RESET_CONTEXT_SIGNAL::{request.learning}::{request.steps_back}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid reset_context request: {e}",
            )


def parse_reset_context_signal(output: str) -> ResetContextRequest | None:
    """Parse a reset context signal from tool output.

    Returns None if not a reset context signal.
    """
    if not output.startswith("RESET_CONTEXT_SIGNAL::"):
        return None

    parts = output.split("::", 2)
    if len(parts) != 3:
        return None

    try:
        return ResetContextRequest(
            learning=parts[1],
            steps_back=int(parts[2]),
        )
    except (ValueError, IndexError):
        return None


# Backwards compatibility aliases
TimeTravelTool = ResetContextTool
TimeTravelRequest = ResetContextRequest
parse_time_travel_signal = parse_reset_context_signal
