"""SWE-bench optimized agent matching best-practice scaffold.

This agent follows the approach used by top SWE-bench submissions:
- 2 tools only: bash (persistent) + str_replace_editor
- Better prompting: "use tools 100+ times", "implement tests first"
- Optional extended thinking for Claude models
- Higher step limits (200+)

Model-agnostic design - works with any LLM provider.
"""

import json
import time
from pathlib import Path
from typing import Any

import anthropic
import openai

from src.tools import Tool, get_swebench_tools
from src.tools.swebench_tools import BashTool

from .base import Agent, AgentMetrics, Message, MessageRole, StepSnapshot, TaskResult


# System prompt following Anthropic's guidance
SWEBENCH_SYSTEM_PROMPT = """You are an expert software engineer tasked with solving a GitHub issue.

IMPORTANT GUIDELINES:
1. You should use tools as much as possible, ideally more than 100 times.
2. You should implement your own tests first before attempting to fix the problem.
3. Be careful about edge cases and potential bugs in your solution.
4. Avoid repeating approaches that have already failed.
5. Read error messages carefully and adjust your approach accordingly.

STRATEGY:
1. First, explore the codebase to understand the structure and find relevant files
2. Read the failing test or create a test that reproduces the issue
3. Understand the root cause by reading the relevant code
4. Implement a fix
5. Run tests to verify the fix works
6. Make sure you haven't broken anything else

WORKSPACE: {workspace}

When you have successfully fixed the issue and verified with tests, respond with TASK_COMPLETE."""


class SWEBenchAgent(Agent):
    """Optimized agent for SWE-bench using bash + str_replace_editor.
    
    Key features:
    - Persistent bash session (cd commands work across calls)
    - String replacement editor (precise edits, not full file rewrites)
    - Better prompting following Anthropic's guidance
    - Optional extended thinking for Claude models
    - Higher step limits (200+)
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        workspace: Path | None = None,
        max_steps: int = 200,
        temperature: float = 1.0,  # Anthropic uses default temp
        provider: str = "anthropic",
        extended_thinking: bool = False,
        thinking_budget: int = 128000,
    ):
        # Tools will be created when workspace is set
        super().__init__(model, [], max_steps, temperature)
        self.provider = provider
        self.extended_thinking = extended_thinking
        self.thinking_budget = thinking_budget
        self._workspace = workspace
        self._bash_tool: BashTool | None = None

        if provider == "anthropic":
            self.client = anthropic.AsyncAnthropic()
        elif provider == "openai":
            self.client = openai.AsyncOpenAI()
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _setup_tools(self, workspace: Path) -> None:
        """Setup tools for the given workspace."""
        self._workspace = workspace
        self.tools = get_swebench_tools(workspace)
        # Keep reference to bash tool for cleanup
        for tool in self.tools:
            if isinstance(tool, BashTool):
                self._bash_tool = tool
                break

    def cleanup(self) -> None:
        """Clean up resources (bash session, etc.)."""
        if self._bash_tool:
            self._bash_tool.cleanup()

    async def run(self, task: str, workspace: Path) -> TaskResult:
        """Run the agent on a SWE-bench task."""
        self.reset()
        self._setup_tools(workspace)
        start_time = time.time()

        # Build system prompt
        system_prompt = SWEBENCH_SYSTEM_PROMPT.format(workspace=workspace)

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
                    for tool_call in response.tool_calls:
                        result = await self._execute_tool(
                            tool_call["name"], 
                            tool_call["arguments"]
                        )
                        self._add_message(
                            Message(
                                role=MessageRole.TOOL,
                                content=result.output if result.success else f"Error: {result.error}",
                                tool_call_id=tool_call["id"],
                                name=tool_call["name"],
                            )
                        )
                else:
                    # No tool calls and not done - nudge to continue
                    self._add_message(
                        Message(
                            role=MessageRole.USER,
                            content="Continue working on the task. Use the bash and str_replace_editor tools to make progress.",
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

    async def _call_llm(self, messages: list[Message]) -> Message:
        """Call the LLM and return the response."""
        self.metrics.llm_calls += 1

        if self.provider == "anthropic":
            return await self._call_anthropic(messages)
        else:
            return await self._call_openai(messages)

    async def _call_anthropic(self, messages: list[Message]) -> Message:
        """Call Anthropic API with optional extended thinking."""
        # Separate system message
        system_content = ""
        api_messages = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_content = msg.content
            elif msg.role == MessageRole.USER:
                api_messages.append({"role": "user", "content": msg.content})
            elif msg.role == MessageRole.ASSISTANT:
                content: list[dict[str, Any]] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["name"],
                            "input": tc["arguments"],
                        }
                    )
                api_messages.append({"role": "assistant", "content": content})
            elif msg.role == MessageRole.TOOL:
                api_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )

        tools = [t.to_anthropic_schema() for t in self.tools]

        # Build request kwargs
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 16384,
            "system": system_content,
            "messages": api_messages,
            "tools": tools if tools else anthropic.NOT_GIVEN,
        }

        # Add extended thinking if enabled (Claude 3.5+ only)
        if self.extended_thinking:
            request_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget,
            }
            # Extended thinking requires temperature=1
            request_kwargs["temperature"] = 1.0
        else:
            request_kwargs["temperature"] = self.temperature

        response = await self.client.messages.create(**request_kwargs)

        # Track tokens
        self.metrics.total_input_tokens += response.usage.input_tokens
        self.metrics.total_output_tokens += response.usage.output_tokens

        # Parse response
        text_content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_content = block.text
            elif block.type == "thinking":
                # Extended thinking block - we could log this but don't add to response
                pass
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "arguments": block.input,
                    }
                )

        return Message(
            role=MessageRole.ASSISTANT,
            content=text_content,
            tool_calls=tool_calls,
        )

    async def _call_openai(self, messages: list[Message]) -> Message:
        """Call OpenAI API."""
        api_messages = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                api_messages.append({"role": "system", "content": msg.content})
            elif msg.role == MessageRole.USER:
                api_messages.append({"role": "user", "content": msg.content})
            elif msg.role == MessageRole.ASSISTANT:
                m: dict[str, Any] = {"role": "assistant", "content": msg.content}
                if msg.tool_calls:
                    m["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["arguments"]),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                api_messages.append(m)
            elif msg.role == MessageRole.TOOL:
                api_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                )

        tools = [t.to_openai_schema() for t in self.tools] if self.tools else None

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            temperature=self.temperature,
            tools=tools,
        )

        # Track tokens
        if response.usage:
            self.metrics.total_input_tokens += response.usage.prompt_tokens
            self.metrics.total_output_tokens += response.usage.completion_tokens

        # Parse response
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                    }
                )

        return Message(
            role=MessageRole.ASSISTANT,
            content=message.content or "",
            tool_calls=tool_calls,
        )

    def _metrics_to_dict(self) -> dict[str, Any]:
        """Convert metrics to dict for TaskResult."""
        return {
            "total_input_tokens": self.metrics.total_input_tokens,
            "total_output_tokens": self.metrics.total_output_tokens,
            "llm_calls": self.metrics.llm_calls,
            "tool_calls": self.metrics.tool_calls,
            "compressions": self.metrics.compressions,
            "messages_dropped": self.metrics.messages_dropped,
            "wall_time_seconds": self.metrics.wall_time_seconds,
            "message_count": len(self.messages),
            "extended_thinking": self.extended_thinking,
            "trajectory": [
                {
                    "step": s.step,
                    "message_count": s.message_count,
                    "total_tokens": s.total_tokens,
                    "compressions_so_far": s.compressions_so_far,
                    "timestamp": s.timestamp,
                }
                for s in self.metrics.trajectory
            ],
        }
