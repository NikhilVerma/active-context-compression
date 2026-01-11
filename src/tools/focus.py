"""Focus tools for structured context management.

These tools allow an agent to explicitly declare what it's working on,
then compress that work into learnings when done.
"""

from dataclasses import dataclass

from .base import Tool, ToolResult


@dataclass
class FocusState:
    """Tracks the current focus state."""

    description: str
    goal: str
    start_message_index: int


class StartFocusTool(Tool):
    """Tool to declare a new focus/investigation."""

    name = "start_focus"
    description = """Declare what you're about to focus on investigating or implementing.

Use this BEFORE starting a new line of investigation or implementation work.
This helps organize your work and enables efficient context management.

When to use:
- Starting to explore a new part of the codebase
- Beginning implementation of a specific feature
- Investigating a bug or issue
- Any distinct subtask that has a clear goal

Example:
  start_focus(
    description="Investigate config loading system",
    goal="Find where API keys are loaded from"
  )
"""

    parameters = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "What you're about to focus on (e.g., 'Investigate config loading')",
            },
            "goal": {
                "type": "string",
                "description": "The specific goal of this focus (e.g., 'Find where API keys are loaded')",
            },
        },
        "required": ["description", "goal"],
    }

    async def execute(self, description: str, goal: str) -> ToolResult:
        """Record the start of a new focus.

        Note: The actual state management happens in the agent.
        This tool just returns a signal that the agent intercepts.
        """
        return ToolResult(
            success=True,
            output=f"FOCUS_START::{description}::{goal}",
        )


class CompleteFocusTool(Tool):
    """Tool to complete a focus and capture learnings."""

    name = "complete_focus"
    description = """Complete your current focus and capture what you learned.

Use this when you've finished investigating or implementing something,
whether successful, partially successful, or blocked.

This will:
1. Save your learnings to persistent knowledge
2. Clear the detailed work from context (you keep the learnings)
3. Let you continue with a fresh context for the next focus

Outcomes:
- "success": Achieved the goal
- "partial": Made progress but didn't fully achieve goal
- "blocked": Couldn't proceed (missing info, error, etc.)
- "abandoned": Decided this path isn't worth pursuing

Example:
  complete_focus(
    outcome="success",
    learnings="Config is loaded from .env via python-dotenv. API keys are in .secrets/production.env which is gitignored.",
    next_action="Now implement the fix to load from the correct path"
  )
"""

    parameters = {
        "type": "object",
        "properties": {
            "outcome": {
                "type": "string",
                "enum": ["success", "partial", "blocked", "abandoned"],
                "description": "How this focus concluded",
            },
            "learnings": {
                "type": "string",
                "description": "Key learnings to preserve (be specific - file paths, function names, etc.)",
            },
            "next_action": {
                "type": "string",
                "description": "What to do next (optional)",
            },
        },
        "required": ["outcome", "learnings"],
    }

    async def execute(self, outcome: str, learnings: str, next_action: str = "") -> ToolResult:
        """Complete the focus and return signal for agent to process."""
        return ToolResult(
            success=True,
            output=f"FOCUS_COMPLETE::{outcome}::{learnings}::{next_action}",
        )


def parse_focus_start(output: str) -> tuple[str, str] | None:
    """Parse a focus start signal. Returns (description, goal) or None."""
    if output.startswith("FOCUS_START::"):
        parts = output.split("::", 2)
        if len(parts) == 3:
            return parts[1], parts[2]
    return None


def parse_focus_complete(output: str) -> dict | None:
    """Parse a focus complete signal. Returns dict with outcome, learnings, next_action or None."""
    if output.startswith("FOCUS_COMPLETE::"):
        parts = output.split("::", 3)
        if len(parts) >= 3:
            return {
                "outcome": parts[1],
                "learnings": parts[2],
                "next_action": parts[3] if len(parts) > 3 else "",
            }
    return None


def get_focus_tools() -> list[Tool]:
    """Get the focus management tools."""
    return [StartFocusTool(), CompleteFocusTool()]
