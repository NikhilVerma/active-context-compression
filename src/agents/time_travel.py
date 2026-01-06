"""Agent with time travel capabilities."""

from pathlib import Path

from src.tools import TimeTravelTool, parse_time_travel_signal, Tool

from .base import Message, MessageRole
from .baseline import BaselineAgent


class TimeTravelAgent(BaselineAgent):
    """Agent that can time travel - drop context and keep learnings.

    This is the experimental group. Identical to BaselineAgent but with
    the time_travel tool added, which allows dropping messages and injecting learnings.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        tools: list[Tool] | None = None,
        max_steps: int = 50,
        temperature: float = 0.0,
        provider: str = "anthropic",
    ):
        # Add time_travel tool to the tool list
        all_tools = list(tools or [])
        all_tools.append(TimeTravelTool())

        super().__init__(model, all_tools, max_steps, temperature, provider)

    async def _execute_tool(self, name: str, arguments: dict) -> "ToolResult":
        """Execute a tool, with special handling for time_travel."""
        result = await super()._execute_tool(name, arguments)

        # Check for time travel signal
        if result.success:
            tt_request = parse_time_travel_signal(result.output)
            if tt_request:
                self._handle_time_travel(tt_request.learning, tt_request.steps_back)
                # Return a modified result so the caller knows time travel happened
                from src.tools import ToolResult
                return ToolResult(
                    success=True,
                    output=f"Time travel executed. Dropped {tt_request.steps_back} messages. Learning preserved.",
                    is_time_travel=True,
                )

        return result

    def _handle_time_travel(self, learning: str, steps_back: int) -> None:
        """Handle a time travel request.

        1. Drop the last N messages (but keep system and initial user message)
        2. Inject the learning as a user message
        """
        self.metrics.time_travels += 1

        # Ensure we keep at least system + initial task message
        min_messages = 2
        max_drop = len(self.messages) - min_messages

        actual_steps = min(steps_back, max_drop)
        self.metrics.messages_dropped += actual_steps

        if actual_steps > 0:
            self.messages = self.messages[:-actual_steps]

        # Inject the learning
        learning_message = f"""[TIME TRAVEL - Previous exploration summary]

{learning}

Continue from here with this knowledge. Don't repeat the exploration that led to this learning."""

        self._add_message(Message(role=MessageRole.USER, content=learning_message))
