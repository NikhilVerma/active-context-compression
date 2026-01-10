"""Base agent interface and common functionality."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.tools import Tool, ToolResult


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A message in the conversation."""

    role: MessageRole
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None  # For tool messages


@dataclass
class StepSnapshot:
    """Snapshot of agent state at a specific step."""

    step: int
    message_count: int
    total_tokens: int
    compressions_so_far: int
    timestamp: float


@dataclass
class AgentMetrics:
    """Metrics collected during agent execution."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    compressions: int = 0
    messages_dropped: int = 0
    wall_time_seconds: float = 0.0
    trajectory: list[StepSnapshot] = field(default_factory=list)


class TaskResult(BaseModel):
    """Result of running a task."""

    success: bool
    output: str
    error: str | None = None
    metrics: dict[str, Any] = {}


class Agent(ABC):
    """Abstract base class for agents."""

    def __init__(
        self,
        model: str,
        tools: list[Tool],
        max_steps: int = 50,
        temperature: float = 0.0,
    ):
        self.model = model
        self.tools = tools
        self.max_steps = max_steps
        self.temperature = temperature
        self.messages: list[Message] = []
        self.metrics = AgentMetrics()

    @abstractmethod
    async def run(self, task: str, workspace: Path) -> TaskResult:
        """Run the agent on a task.

        Args:
            task: Natural language description of the task
            workspace: Path to the workspace directory

        Returns:
            TaskResult with success status, output, and metrics
        """
        ...

    @abstractmethod
    async def _call_llm(self, messages: list[Message]) -> Message:
        """Call the LLM with messages and return the response."""
        ...

    def _add_message(self, message: Message) -> None:
        """Add a message to the conversation history."""
        self.messages.append(message)

    def _get_tool_by_name(self, name: str) -> Tool | None:
        """Get a tool by name."""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    async def _execute_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a tool and return the result."""
        tool = self._get_tool_by_name(name)
        if tool is None:
            return ToolResult(success=False, output="", error=f"Unknown tool: {name}")

        self.metrics.tool_calls += 1
        return await tool.execute(**arguments)

    def reset(self) -> None:
        """Reset the agent state for a new task."""
        self.messages = []
        self.metrics = AgentMetrics()
