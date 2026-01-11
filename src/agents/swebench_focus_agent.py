"""SWE-bench Focus Agent - combines optimized scaffold with context compression.

This agent extends SWEBenchAgent with Focus tools for autonomous context management:
- start_focus/complete_focus for structured work phases
- Automatic context compression when focus is completed
- Persistent knowledge preservation across compressions

The hypothesis: Focus should help more on longer tasks where context bloat
becomes a problem, while maintaining the benefits of the optimized scaffold.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console

from src.tools import Tool, ToolResult, get_swebench_tools
from src.tools.focus import (
    FocusState,
    get_focus_tools,
    parse_focus_complete,
    parse_focus_start,
)
from src.tools.swebench_tools import BashTool

from .base import Message, MessageRole, StepSnapshot, TaskResult
from .swebench_agent import SWEBenchAgent


# Extended system prompt with AGGRESSIVE focus tool guidance
SWEBENCH_FOCUS_SYSTEM_PROMPT = """You are an expert software engineer tasked with solving a GitHub issue.

CRITICAL - CONTEXT MANAGEMENT:
You MUST use focus tools aggressively to manage your context window. Your context will fill up quickly and degrade your performance if you don't compress regularly.

**MANDATORY WORKFLOW:**
1. ALWAYS call `start_focus` before ANY exploration or implementation phase
2. ALWAYS call `complete_focus` after 10-15 tool calls to compress and preserve learnings
3. NEVER let more than 15-20 tool calls pass without completing a focus
4. Each focus should be SHORT and FOCUSED - don't try to do everything in one focus

## Focus Tools (USE THESE CONSTANTLY)

- **start_focus(description, goal)**: Call this FIRST before exploring or implementing anything.
  Examples:
  - start_focus("Find relevant files", "Locate files related to the bug")
  - start_focus("Understand the bug", "Read code to understand root cause")  
  - start_focus("Implement fix", "Write the code fix")
  - start_focus("Test the fix", "Run tests to verify")

- **complete_focus(outcome, learnings, next_action)**: Call this FREQUENTLY (every 10-15 tool calls).
  This compresses your context and preserves key learnings. Your learnings are saved permanently.
  
  Outcomes: "success" | "partial" | "blocked" | "abandoned"

## Typical Session Structure (4-6 focuses minimum):
1. Focus 1: Explore codebase structure (5-10 calls) → complete_focus
2. Focus 2: Find relevant files for the bug (5-10 calls) → complete_focus  
3. Focus 3: Understand the bug/read code (10-15 calls) → complete_focus
4. Focus 4: Implement the fix (10-15 calls) → complete_focus
5. Focus 5: Test and verify (5-10 calls) → complete_focus
6. TASK_COMPLETE

## Other Guidelines:
- Use tools extensively (100+ times total is fine)
- Implement tests first when possible
- Avoid repeating failed approaches
- Read error messages carefully

WORKSPACE: {workspace}

When you have successfully fixed the issue and verified with tests, respond with TASK_COMPLETE."""


# Reminder message to inject periodically
FOCUS_REMINDER = """REMINDER: You should call `complete_focus` to compress your context and preserve learnings. 
Your context is growing large. Summarize what you've learned so far and call complete_focus with:
- outcome: "success", "partial", "blocked", or "abandoned"  
- learnings: Key facts discovered (file paths, function names, root cause, etc.)
- next_action: What to do next

Then call start_focus for your next phase of work."""


@dataclass
class KnowledgeEntry:
    """A single learning from a completed focus."""

    focus_description: str
    focus_goal: str
    outcome: str
    learnings: str


class SWEBenchFocusAgent(SWEBenchAgent):
    """SWE-bench agent with Focus-based context compression.
    
    Extends SWEBenchAgent with:
    - start_focus/complete_focus tools
    - Automatic context compression
    - Persistent knowledge section
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        workspace: Path | None = None,
        max_steps: int = 200,
        temperature: float = 1.0,
        provider: str = "anthropic",
        extended_thinking: bool = False,
        thinking_budget: int = 128000,
        console: Console | None = None,
    ):
        super().__init__(
            model=model,
            workspace=workspace,
            max_steps=max_steps,
            temperature=temperature,
            provider=provider,
            extended_thinking=extended_thinking,
            thinking_budget=thinking_budget,
        )
        self._focus_stack: list[FocusState] = []
        self._knowledge: list[KnowledgeEntry] = []
        self._console = console or Console()
        self._run_start_time: float = 0.0
        self._tool_calls_since_focus: int = 0  # Track calls to remind about compression
        self._reminder_threshold: int = 15  # Remind after this many tool calls without focus

    def _setup_tools(self, workspace: Path) -> None:
        """Setup tools including focus tools."""
        self._workspace = workspace
        # Get base SWE-bench tools (bash + str_replace_editor)
        self.tools = get_swebench_tools(workspace)
        # Add focus tools
        self.tools.extend(get_focus_tools())
        # Keep reference to bash tool for cleanup
        for tool in self.tools:
            if isinstance(tool, BashTool):
                self._bash_tool = tool
                break

    def reset(self) -> None:
        """Reset agent state."""
        super().reset()
        self._focus_stack = []
        self._knowledge = []
        self._tool_calls_since_focus = 0

    def _build_knowledge_section(self) -> str:
        """Build the persistent knowledge section."""
        if not self._knowledge:
            return ""

        lines = ["\n## KNOWLEDGE (Preserved from previous investigations)\n"]

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
        """Rebuild system message to include current knowledge."""
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
            system_content = f"{system_content}\n{knowledge_section}"

        self.messages[0] = Message(
            role=MessageRole.SYSTEM,
            content=system_content,
        )

    async def run(self, task: str, workspace: Path) -> TaskResult:
        """Run the agent with focus-based context management."""
        self.reset()
        self._setup_tools(workspace)
        start_time = time.time()
        self._run_start_time = start_time

        # Build system prompt with focus guidance
        system_prompt = SWEBENCH_FOCUS_SYSTEM_PROMPT.format(workspace=workspace)

        self._add_message(Message(role=MessageRole.SYSTEM, content=system_prompt))
        self._add_message(Message(role=MessageRole.USER, content=task))

        try:
            for step in range(self.max_steps):
                # Call LLM
                response = await self._call_llm(self.messages)
                self._add_message(response)

                # Track trajectory
                self.metrics.trajectory.append(
                    StepSnapshot(
                        step=step,
                        message_count=len(self.messages),
                        total_tokens=self.metrics.total_input_tokens + self.metrics.total_output_tokens,
                        compressions_so_far=self.metrics.compressions,
                        timestamp=time.time() - start_time,
                    )
                )

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

                        # If focus was completed, context was compressed
                        if result.is_compression:
                            focus_completed = True
                            self._tool_calls_since_focus = 0  # Reset counter
                            break

                        self._add_message(
                            Message(
                                role=MessageRole.TOOL,
                                content=result.output if result.success else f"Error: {result.error}",
                                tool_call_id=tool_call["id"],
                                name=tool_call["name"],
                            )
                        )
                        
                        # Track tool calls (excluding focus tools themselves)
                        if tool_call["name"] not in ("start_focus", "complete_focus"):
                            self._tool_calls_since_focus += 1

                    if focus_completed:
                        continue
                    
                    # Inject reminder if too many tool calls without compression
                    if self._tool_calls_since_focus >= self._reminder_threshold:
                        self._add_message(
                            Message(
                                role=MessageRole.USER,
                                content=FOCUS_REMINDER,
                            )
                        )
                        self._console.print(f"[dim yellow]⚠ Injected focus reminder (calls since focus: {self._tool_calls_since_focus})[/dim yellow]")
                else:
                    # No tool calls and not done
                    self._add_message(
                        Message(
                            role=MessageRole.USER,
                            content="Continue working on the task. Use the bash, str_replace_editor, or focus tools to make progress.",
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
        finally:
            self.cleanup()

    async def _execute_tool_with_focus(
        self,
        name: str,
        arguments: dict[str, Any],
        tool_call_id: str,
    ) -> ToolResult:
        """Execute a tool with special handling for focus tools."""
        result = await self._execute_tool(name, arguments)

        # Handle focus tool signals
        if result.success and result.output:
            focus_start = parse_focus_start(result.output)
            if focus_start:
                description, goal = focus_start
                self._handle_start_focus(description, goal)
                return ToolResult(
                    success=True,
                    output=f"Focus started: {description}\nGoal: {goal}\n\nProceeding with investigation...",
                )

            focus_complete = parse_focus_complete(result.output)
            if focus_complete:
                return self._handle_complete_focus(focus_complete)

        return result

    def _handle_start_focus(self, description: str, goal: str) -> None:
        """Handle starting a new focus."""
        start_index = len(self.messages)
        self._focus_stack.append(
            FocusState(
                description=description,
                goal=goal,
                start_message_index=start_index,
            )
        )
        # Don't reset counter here - we want to track total calls since last COMPLETION
        self._console.print(f"[dim cyan]▶ Focus started: {description}[/dim cyan]")

    def _handle_complete_focus(self, focus_data: dict) -> ToolResult:
        """Handle completing a focus - compress messages and preserve learning."""
        if not self._focus_stack:
            return ToolResult(
                success=False,
                output="",
                error="No active focus to complete. Use start_focus first.",
            )

        focus = self._focus_stack.pop()

        # Create knowledge entry
        entry = KnowledgeEntry(
            focus_description=focus.description,
            focus_goal=focus.goal,
            outcome=focus_data["outcome"],
            learnings=focus_data["learnings"],
        )
        self._knowledge.append(entry)

        # Find safe truncation point
        truncate_to = focus.start_message_index
        safe_point = self._find_safe_truncation_point(truncate_to)
        messages_to_drop = len(self.messages) - safe_point

        if messages_to_drop > 0:
            self.metrics.messages_dropped += messages_to_drop
            self.metrics.compressions += 1
            self.messages = self.messages[:safe_point]

            self._console.print(f"[dim cyan]◀ Focus completed: {focus.description}[/dim cyan]")
            self._console.print(
                f"[dim]   Dropped {messages_to_drop} messages | "
                f"Preserved {len(self._knowledge)} knowledge entries[/dim]"
            )

        # Rebuild with updated knowledge
        self._rebuild_messages_with_knowledge()

        # Track post-compression snapshot
        self.metrics.trajectory.append(
            StepSnapshot(
                step=self.metrics.llm_calls,
                message_count=len(self.messages),
                total_tokens=self.metrics.total_input_tokens + self.metrics.total_output_tokens,
                compressions_so_far=self.metrics.compressions,
                timestamp=time.time() - self._run_start_time,
            )
        )

        # Add continuation message
        next_action = focus_data.get("next_action", "")
        continuation = f"""Focus completed: {focus.description}

Outcome: {focus_data["outcome"]}

Your learnings have been saved to the KNOWLEDGE section above.

{f"Next: {next_action}" if next_action else "What would you like to do next?"}"""

        self._add_message(Message(role=MessageRole.USER, content=continuation))

        return ToolResult(
            success=True,
            output=f"Focus '{focus.description}' completed. Dropped {messages_to_drop} messages. Learnings preserved.",
            is_compression=True,
        )

    def _find_safe_truncation_point(self, target_index: int) -> int:
        """Find a safe truncation point respecting API message ordering rules."""
        min_safe = 2  # Keep system + initial task

        if target_index <= min_safe:
            return min_safe

        for i in range(target_index, min_safe - 1, -1):
            if i >= len(self.messages):
                continue

            msg = self.messages[i]

            if msg.role == MessageRole.USER:
                return i + 1

            if msg.role == MessageRole.TOOL:
                if i + 1 >= len(self.messages) or self.messages[i + 1].role != MessageRole.TOOL:
                    return i + 1

        return min_safe

    def _metrics_to_dict(self) -> dict[str, Any]:
        """Convert metrics to dict, including focus-specific metrics."""
        base = super()._metrics_to_dict()
        base["knowledge_entries"] = len(self._knowledge)
        base["active_focuses"] = len(self._focus_stack)
        return base
