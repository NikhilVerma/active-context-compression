"""Tests for the reset_context tool (formerly time_travel)."""

import pytest

from src.tools import ResetContextTool, parse_reset_context_signal


@pytest.mark.asyncio
async def test_reset_context_tool_basic():
    """Test basic reset_context tool execution."""
    tool = ResetContextTool()

    result = await tool.execute(
        learning="The config file is at /src/config.yaml",
        steps_back=10,
    )

    assert result.success
    assert "RESET_CONTEXT_SIGNAL" in result.output
    assert "The config file is at /src/config.yaml" in result.output
    assert "10" in result.output


@pytest.mark.asyncio
async def test_reset_context_tool_invalid_steps():
    """Test reset_context with invalid steps_back."""
    tool = ResetContextTool()

    result = await tool.execute(
        learning="Some learning",
        steps_back=0,  # Invalid, must be >= 1
    )

    # Should fail validation
    assert not result.success


def test_parse_reset_context_signal():
    """Test parsing reset_context signal from tool output."""
    signal = "RESET_CONTEXT_SIGNAL::Found the bug in line 42::5"

    request = parse_reset_context_signal(signal)

    assert request is not None
    assert request.learning == "Found the bug in line 42"
    assert request.steps_back == 5


def test_parse_reset_context_signal_not_a_signal():
    """Test parsing non-signal output."""
    output = "Just some normal tool output"

    request = parse_reset_context_signal(output)

    assert request is None


def test_tool_schema():
    """Test tool schema generation."""
    tool = ResetContextTool()

    anthropic_schema = tool.to_anthropic_schema()
    assert anthropic_schema["name"] == "reset_context"
    assert "learning" in anthropic_schema["input_schema"]["properties"]
    assert "steps_back" in anthropic_schema["input_schema"]["properties"]

    openai_schema = tool.to_openai_schema()
    assert openai_schema["type"] == "function"
    assert openai_schema["function"]["name"] == "reset_context"
