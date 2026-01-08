#!/usr/bin/env python3
"""Trace token accumulation to verify we track paid tokens correctly."""

import asyncio

from src.agents import FocusAgent
from src.benchmarks import create_workspace_for_problem, get_mini_benchmark
from src.tools import get_coding_tools


async def trace():
    problems = get_mini_benchmark()
    problem = [p for p in problems if p.id == "hidden_config"][0]
    workspace = create_workspace_for_problem(problem)
    tools = get_coding_tools(workspace)

    agent = FocusAgent(tools=tools, auto_focus=True)

    # Patch to trace token accumulation
    original_call = agent._call_llm
    call_log = []

    async def traced_call(messages):
        result = await original_call(messages)
        call_log.append(
            {
                "messages_in_context": len(messages),
                "cumulative_input": agent.metrics.total_input_tokens,
                "cumulative_output": agent.metrics.total_output_tokens,
            }
        )
        return result

    agent._call_llm = traced_call

    _ = await agent.run(problem.task, workspace)

    print("=== Token Accumulation Trace ===")
    for i, c in enumerate(call_log):
        print(
            f"Call {i+1}: context={c['messages_in_context']} msgs, "
            f"cumulative_input={c['cumulative_input']}, "
            f"cumulative_output={c['cumulative_output']}"
        )

    print("\nFinal metrics:")
    print(f"  Total input tokens: {agent.metrics.total_input_tokens}")
    print(f"  Total output tokens: {agent.metrics.total_output_tokens}")
    print(f"  Messages dropped: {agent.metrics.messages_dropped}")
    print(f"  Final message count: {len(agent.messages)}")
    print(f"  Compressions: {agent.metrics.compressions}")


if __name__ == "__main__":
    asyncio.run(trace())
