"""Agents package."""

from .base import Agent, AgentMetrics, Message, MessageRole, TaskResult
from .baseline import BaselineAgent
from .focus import FocusAgent
from .swebench_agent import SWEBenchAgent
from .swebench_focus_agent import SWEBenchFocusAgent

__all__ = [
    "Agent",
    "AgentMetrics",
    "Message",
    "MessageRole",
    "TaskResult",
    "BaselineAgent",
    "FocusAgent",
    # New optimized agents
    "SWEBenchAgent",
    "SWEBenchFocusAgent",
]
