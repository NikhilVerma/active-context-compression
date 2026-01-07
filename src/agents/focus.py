"""Agent with focus-based context management.

The focus agent allows structured context compression:
1. start_focus - declare what you're investigating, marks start point
2. complete_focus - capture learnings, compress context back to start

This enables running very long tasks by progressively compressing
completed sub-tasks while preserving key learnings.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console

from src.tools import Tool, ToolResult
from src.tools.focus import (
    FocusState,
    get_focus_tools,
    parse_focus_complete,
    parse_focus_start,
)

from .base import Message, MessageRole, TaskResult
from .baseline import BaselineAgent


@dataclass
class KnowledgeEntry:
    """A single learning from a completed focus."""

    focus_description: str
    focus_goal: str
    outcome: str  # success, partial, blocked, abandoned
    learnings: str


class FocusAgent(BaselineAgent):
    """Agent with focus-based context compression.

    Key features:
    - start_focus/complete_focus tools for structured work
    - Persistent KNOWLEDGE section preserved across compressions
    - Tracks focus depth for nested focuses
    - Auto-manages focuses if model doesn't use them
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        tools: list[Tool] | None = None,
        max_steps: int = 50,
        temperature: float = 0.0,
        provider: str = "anthropic",
        auto_focus: bool = True,  # Automatically manage focuses
        steps_per_focus: int = 15,  # Auto-complete focus after N steps
        console: Console | None = None,  # For logging focus events
    ):
        # Add focus tools
        all_tools = list(tools or [])
        all_tools.extend(get_focus_tools())

        super().__init__(model, all_tools, max_steps, temperature, provider)

        # Focus state
        self._focus_stack: list[FocusState] = []
        self._knowledge: list[KnowledgeEntry] = []
        self._auto_focus = auto_focus
        self._steps_per_focus = steps_per_focus
        self._steps_in_current_focus = 0
        self._console = console or Console()

    def reset(self) -> None:
        """Reset agent state."""
        super().reset()
        self._focus_stack = []
        self._knowledge = []
        self._steps_in_current_focus = 0

    def _build_knowledge_section(self) -> str:
        """Build the persistent knowledge section from accumulated learnings."""
        if not self._knowledge:
            return ""

        lines = ["## KNOWLEDGE (Preserved from previous investigations)\n"]

        for i, entry in enumerate(self._knowledge, 1):
            outcome_emoji = {
                "success": "✓",
                "partial": "~",
                "blocked": "✗",
                "abandoned": "→",
            }.get(entry.outcome, "?")

            lines.append(f"### {i}. [{outcome_emoji}] {entry.focus_description}")
            lines.append(f"**Goal:** {entry.focus_goal}")
            lines.append(f"**Outcome:** {entry.outcome}")
            lines.append(f"**Learnings:** {entry.learnings}")
            lines.append("")

        return "\n".join(lines)

    def _rebuild_messages_with_knowledge(self) -> None:
        """Rebuild messages to include current knowledge section.

        Message structure:
        [0] SYSTEM: Original system prompt + knowledge section
        [1] USER: Original task
        [2...] Rest of conversation
        """
        if len(self.messages) < 2:
            return

        # Get original system prompt (strip any previous knowledge section)
        system_content = self.messages[0].content
        knowledge_marker = "## KNOWLEDGE"
        if knowledge_marker in system_content:
            system_content = system_content.split(knowledge_marker)[0].rstrip()

        # Append new knowledge section
        knowledge_section = self._build_knowledge_section()
        if knowledge_section:
            system_content = f"{system_content}\n\n{knowledge_section}"

        # Update system message
        self.messages[0] = Message(
            role=MessageRole.SYSTEM,
            content=system_content,
        )

    async def run(self, task: str, workspace: Path) -> TaskResult:
        """Run the agent with focus-based context management."""
        import time

        self.reset()
        start_time = time.time()

        # System prompt with focus tool guidance
        system_prompt = f"""You are an expert software engineer. Your task is to solve the following problem.

Workspace: {workspace}

## Tools for Organizing Your Work

You have access to `start_focus` and `complete_focus` tools:

- **start_focus**: Use when beginning a distinct line of investigation or implementation.
  This helps you organize your work and enables efficient context management.
  
- **complete_focus**: Use when you've finished investigating something. This:
  - Saves your key learnings to persistent knowledge
  - Compresses your detailed work (you keep the learnings)
  - Gives you a fresh context for the next focus

Use these especially when:
- Exploring unfamiliar parts of the codebase
- Trying different approaches that might not work out
- Working on multi-step tasks with distinct phases

## Completing the Task

When you're done with the entire task, respond with TASK_COMPLETE and a summary of what you did.
"""

        self._add_message(Message(role=MessageRole.SYSTEM, content=system_prompt))
        self._add_message(Message(role=MessageRole.USER, content=task))

        # Auto-start first focus if enabled
        if self._auto_focus:
            self._auto_start_focus(
                "Initial exploration", "Understand the problem and find relevant code"
            )

        for step in range(self.max_steps):
            self._steps_in_current_focus += 1

            # Check if we should auto-complete focus (before LLM call)
            if self._auto_focus and self._should_auto_complete_focus():
                self._auto_complete_focus()

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
                focus_completed = False

                for tool_call in response.tool_calls:
                    result = await self._execute_tool_with_focus(
                        tool_call["name"],
                        tool_call["arguments"],
                        tool_call["id"],
                    )

                    # If focus was completed, we've already truncated and added
                    # continuation message. Don't add tool result - skip to next step.
                    if result.is_compression:
                        focus_completed = True
                        self._steps_in_current_focus = 0
                        break

                    self._add_message(
                        Message(
                            role=MessageRole.TOOL,
                            content=result.output if result.success else f"Error: {result.error}",
                            tool_call_id=tool_call["id"],
                            name=tool_call["name"],
                        )
                    )

                if focus_completed:
                    # Skip to next iteration - context already set up for continuation
                    continue
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

    async def _execute_tool_with_focus(
        self,
        name: str,
        arguments: dict[str, Any],
        tool_call_id: str,
    ) -> ToolResult:
        """Execute a tool with special handling for focus tools."""
        result = await super()._execute_tool(name, arguments)

        # Handle start_focus
        if result.success and result.output:
            focus_start = parse_focus_start(result.output)
            if focus_start:
                description, goal = focus_start
                self._handle_start_focus(description, goal)
                return ToolResult(
                    success=True,
                    output=f"Focus started: {description}\nGoal: {goal}\n\nProceeding with investigation...",
                )

            # Handle complete_focus
            focus_complete = parse_focus_complete(result.output)
            if focus_complete:
                return self._handle_complete_focus(focus_complete)

        return result

    def _handle_start_focus(self, description: str, goal: str) -> None:
        """Handle starting a new focus."""
        # Record current message index (before the tool call that started this)
        # We want to keep messages up to and including the start_focus call
        start_index = len(self.messages)

        self._focus_stack.append(
            FocusState(
                description=description,
                goal=goal,
                start_message_index=start_index,
            )
        )

    def _handle_complete_focus(self, focus_data: dict) -> ToolResult:
        """Handle completing a focus - compress messages and preserve learning.

        IMPORTANT: We cannot just drop messages arbitrarily. The Anthropic API
        requires that every assistant message with tool_use has a following
        tool_result message. So we need to find a safe truncation point.
        """
        if not self._focus_stack:
            return ToolResult(
                success=False,
                error="No active focus to complete. Use start_focus first.",
            )

        # Pop the current focus
        focus = self._focus_stack.pop()

        # Create knowledge entry
        entry = KnowledgeEntry(
            focus_description=focus.description,
            focus_goal=focus.goal,
            outcome=focus_data["outcome"],
            learnings=focus_data["learnings"],
        )
        self._knowledge.append(entry)

        # Find safe truncation point - must be at a USER message to avoid
        # orphaned tool_use blocks
        # The start_message_index points to where we want to truncate TO
        truncate_to = focus.start_message_index

        # But we need to find the last safe point (after a tool_result sequence
        # or at a user message). Go backwards from truncate_to to find safe point.
        safe_point = self._find_safe_truncation_point(truncate_to)

        messages_to_drop = len(self.messages) - safe_point

        if messages_to_drop > 0:
            self.metrics.messages_dropped += messages_to_drop
            self.metrics.compressions += 1

            # Truncate messages to safe point
            self.messages = self.messages[:safe_point]

            # Log the compression
            self._console.print(
                f"[dim cyan]↩  Focus completed: {focus.description}[/dim cyan]"
            )
            self._console.print(
                f"[dim]   Dropped {messages_to_drop} messages | "
                f"Preserved {len(self._knowledge)} knowledge entries | "
                f"Stack depth: {len(self._focus_stack)}[/dim]"
            )

        # Rebuild with updated knowledge
        self._rebuild_messages_with_knowledge()

        # Add continuation message
        next_action = focus_data.get("next_action", "")
        continuation = f"""Focus completed: {focus.description}

Outcome: {focus_data["outcome"]}

Your learnings have been saved to the KNOWLEDGE section above. 

{f"Next: {next_action}" if next_action else "What would you like to do next?"}"""

        self._add_message(Message(role=MessageRole.USER, content=continuation))

        return ToolResult(
            success=True,
            output=f"Focus '{focus.description}' completed. Dropped {messages_to_drop} messages. Learnings preserved in KNOWLEDGE section.",
            is_compression=True,
        )

    def _metrics_to_dict(self) -> dict[str, Any]:
        """Convert metrics to dict, including focus-specific metrics."""
        base = super()._metrics_to_dict()
        base["knowledge_entries"] = len(self._knowledge)
        base["active_focuses"] = len(self._focus_stack)
        return base

    def _find_safe_truncation_point(self, target_index: int) -> int:
        """Find a safe truncation point at or before target_index.

        The Anthropic API requires that every assistant message with tool_use
        is immediately followed by tool_result messages. So we can only safely
        truncate at points where:
        - We're at a USER message, OR
        - We're after all tool_results for a tool_use block

        We also want to keep at least system + initial user message (indices 0, 1).
        """
        min_safe = 2  # Keep system + initial task

        # Don't go below minimum
        if target_index <= min_safe:
            return min_safe

        # Walk backwards from target to find a safe point
        for i in range(target_index, min_safe - 1, -1):
            if i >= len(self.messages):
                continue

            msg = self.messages[i]

            # A USER message is always safe to truncate after
            # (the API allows assistant->user->assistant)
            if msg.role == MessageRole.USER:
                return i + 1  # Truncate AFTER this message

            # A TOOL message is safe if the NEXT message is not also a TOOL
            # (i.e., we've completed all tool results for a tool_use)
            if msg.role == MessageRole.TOOL:
                if i + 1 >= len(self.messages) or self.messages[i + 1].role != MessageRole.TOOL:
                    return i + 1  # Truncate after the last tool result

        # Fallback to minimum
        return min_safe

    def _should_auto_complete_focus(self) -> bool:
        """Check if we should auto-complete the current focus."""
        if not self._focus_stack:
            return False
        return self._steps_in_current_focus >= self._steps_per_focus

    def _auto_start_focus(self, description: str, goal: str) -> None:
        """Programmatically start a focus."""
        self._handle_start_focus(description, goal)
        self._steps_in_current_focus = 0

    def _auto_complete_focus(self) -> None:
        """Programmatically complete the current focus with auto-generated summary."""
        if not self._focus_stack:
            return

        # Generate learnings from recent messages
        learnings = self._extract_learnings_from_messages()

        focus_data = {
            "outcome": "partial",
            "learnings": learnings,
            "next_action": "Continue with the task",
        }

        # This will truncate messages and add knowledge
        self._handle_complete_focus(focus_data)

        # Start a new focus for the next phase
        self._auto_start_focus("Continuing work", "Complete remaining tasks")

    def _extract_learnings_from_messages(self) -> str:
        """Extract key learnings from recent messages for auto-compression."""
        if not self._focus_stack:
            return "No specific learnings captured."

        focus = self._focus_stack[-1]
        recent_messages = self.messages[focus.start_message_index :]

        # Extract file paths and key findings
        files_read = set()
        files_written = set()
        findings = []

        for msg in recent_messages:
            content = msg.content

            # Look for file operations
            if "read_file" in str(msg.name or ""):
                # Try to extract file path from content
                for word in content.split():
                    if "/" in word and not word.startswith("http"):
                        files_read.add(word.strip(".,;:'\"()[]`"))

            if "write_file" in str(msg.name or "") or "edit_file" in str(msg.name or ""):
                for word in content.split():
                    if "/" in word and not word.startswith("http"):
                        files_written.add(word.strip(".,;:'\"()[]`"))

            # Look for error messages
            if "error" in content.lower() and msg.role == MessageRole.TOOL:
                # Truncate long error messages
                error_snippet = content[:200] + "..." if len(content) > 200 else content
                findings.append(f"Encountered: {error_snippet}")

        parts = []
        if files_read:
            parts.append(f"Files examined: {', '.join(list(files_read)[:5])}")
        if files_written:
            parts.append(f"Files modified: {', '.join(list(files_written)[:5])}")
        if findings:
            parts.append("Findings: " + "; ".join(findings[:3]))

        return (
            " | ".join(parts) if parts else "Exploration completed, continuing with implementation."
        )
