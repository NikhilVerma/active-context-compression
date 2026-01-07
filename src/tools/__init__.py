"""Tools package."""

from .base import Tool, ToolResult
from .coding import get_coding_tools
from .focus import (
    CompleteFocusTool,
    FocusState,
    StartFocusTool,
    get_focus_tools,
    parse_focus_complete,
    parse_focus_start,
)
from .time_travel import (
    ResetContextRequest,
    ResetContextTool,
    TimeTravelRequest,
    # Backwards compatibility
    TimeTravelTool,
    parse_reset_context_signal,
    parse_time_travel_signal,
)

__all__ = [
    "Tool",
    "ToolResult",
    "ResetContextTool",
    "ResetContextRequest",
    "parse_reset_context_signal",
    # Backwards compatibility
    "TimeTravelTool",
    "TimeTravelRequest",
    "parse_time_travel_signal",
    "get_coding_tools",
    # Focus tools
    "StartFocusTool",
    "CompleteFocusTool",
    "FocusState",
    "get_focus_tools",
    "parse_focus_start",
    "parse_focus_complete",
]
