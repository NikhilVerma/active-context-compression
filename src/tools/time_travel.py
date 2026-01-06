"""The time_travel tool - core of the experiment.

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


class TimeTravelRequest(BaseModel):
    """Request to time travel."""

    learning: str
    steps_back: int


class TimeTravelTool(Tool):
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
        return "time_travel"

    @property
    def description(self) -> str:
        return """Time Travel Tool

This tool allows you go back in time by dropping recent conversation messages while preserving key learnings. This is very useful if you are solving a complex problem and you have ended up going down unproductive paths. This is also useful if you have discovered important information that should be retained but the surrounding context is no longer relevant.

For example:

1. You have been trying to debug a piece of code for a while and have made several failed attempts. You realize that your previous approach was flawed. You can use this tool to drop the irrelevant messages while keeping the important insights you gained.
2. You have been searching through files and logs but have not found the root cause of an issue. After some exploration, you finally discover a crucial piece of information. You can use this tool to drop the previous search attempts while retaining the key learning.

This tool allows you to keep your context clean and focused by removing clutter from unproductive explorations, while still preserving the valuable knowledge you have acquired.
"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "learning": {
                    "type": "string",
                    "description": (
                        "What you learned from this exploration. This will be injected "
                        "back into context after dropping messages. Be specific and actionable."
                    ),
                },
                "steps_back": {
                    "type": "integer",
                    "description": (
                        "How many messages to drop from the conversation. "
                        "Count your recent messages to determine this. "
                        "Must be at least 1."
                    ),
                    "minimum": 1,
                },
            },
            "required": ["learning", "steps_back"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Signal time travel request.

        The actual context manipulation happens in the agent harness.
        This just validates the request and returns a signal.
        """
        try:
            request = TimeTravelRequest(**kwargs)

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
                output=f"TIME_TRAVEL_SIGNAL::{request.learning}::{request.steps_back}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid time travel request: {e}",
            )


def parse_time_travel_signal(output: str) -> TimeTravelRequest | None:
    """Parse a time travel signal from tool output.

    Returns None if not a time travel signal.
    """
    if not output.startswith("TIME_TRAVEL_SIGNAL::"):
        return None

    parts = output.split("::", 2)
    if len(parts) != 3:
        return None

    try:
        return TimeTravelRequest(
            learning=parts[1],
            steps_back=int(parts[2]),
        )
    except (ValueError, IndexError):
        return None
