"""Agent with reset_context capabilities."""

from pathlib import Path

from src.tools import ResetContextTool, Tool, ToolResult, parse_reset_context_signal

from .base import Message, MessageRole, TaskResult
from .baseline import BaselineAgent


class TimeTravelAgent(BaselineAgent):
    """Agent that can reset context - drop messages and keep learnings.

    This is the experimental group. Identical to BaselineAgent but with
    the reset_context tool added, which allows dropping messages and injecting learnings.

    Note: In practice, models rarely self-invoke the reset_context tool.
    See FocusAgent for a more practical implementation with automatic compression.
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        tools: list[Tool] | None = None,
        max_steps: int = 50,
        temperature: float = 0.0,
        provider: str = "anthropic",
    ):
        # Add reset_context tool to the tool list
        all_tools = list(tools or [])
        all_tools.append(ResetContextTool())

        super().__init__(model, all_tools, max_steps, temperature, provider)

    async def run(self, task: str, workspace: Path) -> "TaskResult":
        """Run the agent (inherits from BaselineAgent, with reset_context tool available)."""
        import time

        from .base import TaskResult

        self.reset()
        start_time = time.time()

        # System prompt (same as baseline)
        system_prompt = f"""You are an expert software engineer. Your task is to solve the following problem.

Workspace: {workspace}

You have access to various tools. Use them to explore the codebase, understand the problem, and implement a solution.
When you're done, respond with TASK_COMPLETE and a summary of what you did."""

        self._add_message(Message(role=MessageRole.SYSTEM, content=system_prompt))
        self._add_message(Message(role=MessageRole.USER, content=task))

        for step in range(self.max_steps):
            # Call LLM
            response = await self._call_llm(self.messages)
            self._add_message(response)

            # Check if done
            if "TASK_COMPLETE" in response.content:
                self.metrics.wall_time_seconds = time.time() - start_time
                return TaskResult(
                    success=True,
                    output=response.content,
                    metrics=self._metrics_to_dict(),
                )

            # Handle tool calls
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    result = await self._execute_tool(tool_call["name"], tool_call["arguments"])

                    self._add_message(
                        Message(
                            role=MessageRole.TOOL,
                            content=result.output if result.success else f"Error: {result.error}",
                            tool_call_id=tool_call["id"],
                            name=tool_call["name"],
                        )
                    )
            else:
                # No tool calls and not done
                self._add_message(
                    Message(
                        role=MessageRole.USER,
                        content="Continue working on the task. Use tools to make progress.",
                    )
                )

        # Max steps reached
        self.metrics.wall_time_seconds = time.time() - start_time
        return TaskResult(
            success=False,
            output="Max steps reached without completing task.",
            error="max_steps_exceeded",
            metrics=self._metrics_to_dict(),
        )

    async def _execute_tool(self, name: str, arguments: dict) -> ToolResult:
        """Execute a tool, with special handling for reset_context."""
        result = await super()._execute_tool(name, arguments)

        # Check for reset context signal
        if result.success:
            reset_request = parse_reset_context_signal(result.output)
            if reset_request:
                self._handle_reset_context(reset_request.learning, reset_request.steps_back)
                # Return a modified result so the caller knows reset happened
                return ToolResult(
                    success=True,
                    output=f"Context reset. Dropped {reset_request.steps_back} messages. Learning preserved.",
                    is_time_travel=True,
                )

        return result

    def _handle_reset_context(self, learning: str, steps_back: int) -> None:
        """Handle a reset context request.

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
        learning_message = f"""[Previous exploration summary]

{learning}

Continue from here with this knowledge. Don't repeat the exploration that led to this learning."""

        self._add_message(Message(role=MessageRole.USER, content=learning_message))
