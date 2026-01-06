"""Baseline agent without time travel capabilities."""

import json
import time
from pathlib import Path
from typing import Any

import anthropic
import openai

from src.tools import Tool

from .base import Agent, AgentMetrics, Message, MessageRole, TaskResult


class BaselineAgent(Agent):
    """Standard agent that keeps all context.

    This is the control group - it uses the same tools and model
    but cannot drop context or time travel.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        tools: list[Tool] | None = None,
        max_steps: int = 50,
        temperature: float = 0.0,
        provider: str = "anthropic",
    ):
        super().__init__(model, tools or [], max_steps, temperature)
        self.provider = provider

        if provider == "anthropic":
            self.client = anthropic.AsyncAnthropic()
        elif provider == "openai":
            self.client = openai.AsyncOpenAI()
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def run(self, task: str, workspace: Path) -> TaskResult:
        """Run the agent on a task."""
        self.reset()
        start_time = time.time()

        # System prompt
        system_prompt = f"""You are an expert software engineer. Your task is to solve the following problem.

Workspace: {workspace}

You have access to tools to read files, write files, run commands, and search.
Work step by step to understand the problem and implement a solution.
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
                    result = await self._execute_tool(
                        tool_call["name"], tool_call["arguments"]
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
                # No tool calls and not done - might be stuck
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

    async def _call_llm(self, messages: list[Message]) -> Message:
        """Call the LLM and return the response."""
        self.metrics.llm_calls += 1

        if self.provider == "anthropic":
            return await self._call_anthropic(messages)
        else:
            return await self._call_openai(messages)

    async def _call_anthropic(self, messages: list[Message]) -> Message:
        """Call Anthropic API."""
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
                    content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["arguments"],
                    })
                api_messages.append({"role": "assistant", "content": content})
            elif msg.role == MessageRole.TOOL:
                api_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content,
                    }],
                })

        tools = [t.to_anthropic_schema() for t in self.tools]

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=self.temperature,
            system=system_content,
            messages=api_messages,
            tools=tools if tools else anthropic.NOT_GIVEN,
        )

        # Track tokens
        self.metrics.total_input_tokens += response.usage.input_tokens
        self.metrics.total_output_tokens += response.usage.output_tokens

        # Parse response
        text_content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_content = block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })

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
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })

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
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })

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
            "time_travels": self.metrics.time_travels,
            "messages_dropped": self.metrics.messages_dropped,
            "wall_time_seconds": self.metrics.wall_time_seconds,
            "message_count": len(self.messages),
        }
