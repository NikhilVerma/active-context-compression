#!/usr/bin/env python3
"""
Infinite Memory Test: "The Detective Game"

This script demonstrates "Active Context Compression" by simulating a long
investigation where the agent must retain specific facts ("needles") while
filtering out noise ("haystack").

It compares:
1. Baseline Agent (Standard Append-Only)
2. Focus Agent (Active Compression)

Metrics:
- Accuracy (Needle retrieval)
- Token Usage
- Context Size (Message count)
"""

import asyncio
import argparse
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from src.agents import BaselineAgent, FocusAgent
from src.tools import Tool, ToolResult

# Load environment variables from .env
load_dotenv()

# Use Haiku for cost efficiency (it's smart enough for this)
MODEL = "claude-haiku-4-5-20251001"

@dataclass
class CaseFile:
    reports: List[str]
    suspect: str
    weapon: str
    location: str
    clue_indices: dict

def generate_case_file(length: int = 50) -> CaseFile:
    """Generate a synthetic case file with hidden clues."""
    suspects = ["Colonel Mustard", "Miss Scarlet", "Professor Plum", "Mrs. Peacock"]
    weapons = ["Candlestick", "Dagger", "Lead Pipe", "Revolver"]
    locations = ["Library", "Conservatory", "Kitchen", "Ballroom"]
    
    truth_suspect = random.choice(suspects)
    truth_weapon = random.choice(weapons)
    truth_location = random.choice(locations)
    
    reports = []
    
    # Fill with noise
    noise_templates = [
        "Officer {name} patrolled the {place}. Nothing unusual reported.",
        "Interviewed witness {name}. They claimed to be asleep.",
        "Forensics examined the {object}. No fingerprints found.",
        "Neighbor {name} heard a noise but saw nothing.",
        "Checked CCTV at {place}. Camera was malfunctioning.",
    ]
    names = ["Smith", "Jones", "Doe", "Wilson", "Brown"]
    places = ["Garden", "Garage", "Attic", "Basement", "Street"]
    objects = ["Door handle", "Window", "Carpet", "Glass", "Table"]
    
    for i in range(length):
        template = random.choice(noise_templates)
        report = template.format(
            name=random.choice(names),
            place=random.choice(places),
            object=random.choice(objects)
        )
        reports.append(f"[Report #{i+1}] {report}")
        
    # Insert Clues at 25%, 50%, 75%
    idx1 = int(length * 0.25)
    idx2 = int(length * 0.50)
    idx3 = int(length * 0.75)
    
    reports[idx1] = f"[Report #{idx1+1}] WITNESS STATEMENT: A suspicious person looking like {truth_suspect} was seen entering the building."
    reports[idx2] = f"[Report #{idx2+1}] FORENSICS MATCH: The murder weapon was definitely a {truth_weapon}."
    reports[idx3] = f"[Report #{idx3+1}] SURVEILLANCE: The crime took place in the {truth_location}."
    
    return CaseFile(
        reports=reports,
        suspect=truth_suspect,
        weapon=truth_weapon,
        location=truth_location,
        clue_indices={"suspect": idx1, "weapon": idx2, "location": idx3}
    )

class ReadReportTool(Tool):
    """Tool to read police reports one by one."""
    
    def __init__(self, reports: List[str]):
        self.reports = reports
        self.current_index = 0
        
    @property
    def name(self) -> str:
        return "read_next_batch"
        
    @property
    def description(self) -> str:
        return "Read the next batch of 5 police reports."
        
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {},
        }
        
    async def execute(self, **kwargs) -> ToolResult:
        if self.current_index >= len(self.reports):
            return ToolResult(success=False, output="No more reports. You have read all files.", error="EOF")
            
        batch_size = 5
        end_index = min(self.current_index + batch_size, len(self.reports))
        batch = self.reports[self.current_index:end_index]
        self.current_index = end_index
        
        content = "\n\n".join(batch)
        status = f"Reading reports {self.current_index-batch_size+1} to {self.current_index} of {len(self.reports)}"
        
        return ToolResult(
            success=True,
            output=f"{status}:\n\n{content}\n\n(Use this tool again to read more)"
        )

async def run_agent_test(agent_type: str, case: CaseFile):
    """Run a single agent on the case."""
    tool = ReadReportTool(case.reports)
    
    if agent_type == "baseline":
        agent = BaselineAgent(
            model=MODEL,
            tools=[tool],
            max_steps=30, # Enough to read 50 reports (5 per step = 10 steps) + think
        )
    else:
        # Parse steps_per_focus from agent_type if it has "_"
        if "_" in agent_type:
            _, steps = agent_type.split("_")
            steps_per_focus = int(steps) if steps.isdigit() else 0
        else:
            steps_per_focus = 15  # Default
            
        agent = FocusAgent(
            model=MODEL,
            tools=[tool],
            max_steps=30,
            auto_focus=True,
            steps_per_focus=steps_per_focus,
        )
        
    prompt = """You are a detective. You must read ALL the police reports to find the Suspect, Weapon, and Location.
    
    1. Use `read_next_batch` repeatedly until you have read all reports.
    2. While reading, you MUST memorize the key facts (Suspect, Weapon, Location).
    3. Ignore the irrelevant noise.
    4. When finished reading, respond with TASK_COMPLETE and the solution in this format:
       "SOLUTION: Suspect=<name>, Weapon=<weapon>, Location=<location>"
    """
    
    result = await agent.run(prompt, Path("/tmp"))
    
    # Check answer
    output = result.output
    score = 0
    if case.suspect in output: score += 1
    if case.weapon in output: score += 1
    if case.location in output: score += 1
    
    return {
        "score": score,
        "metrics": result.metrics
    }

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--length", type=int, default=50, help="Number of reports")
    args = parser.parse_args()
    
    console = Console()
    console.print(f"[bold]Running Detective Game (Length={args.length})[/bold]")
    
    case = generate_case_file(args.length)
    console.print(f"Truth: {case.suspect} w/ {case.weapon} in {case.location}")
    
    results = {}
    
    # Run ablation: baseline, focus_15, focus_30, focus_auto
    agent_types = ["baseline", "focus_5", "focus_10", "focus_auto"]
    
    for agent_type in agent_types:
        console.print(f"\n[cyan]Running {agent_type}...[/cyan]")
        start = time.time()
        res = await run_agent_test(agent_type, case)
        duration = time.time() - start
        
        metrics = res["metrics"]
        results[agent_type] = {
            "score": res["score"],
            "tokens": metrics["total_input_tokens"] + metrics["total_output_tokens"],
            "messages": metrics.get("message_count", 0),
            "dropped": metrics.get("messages_dropped", 0),
            "compressions": metrics.get("compressions", 0),
            "duration": duration
        }
        
    # Print Table
    table = Table(title="Memory Test Ablation Results")
    table.add_column("Metric")
    table.add_column("Baseline")
    table.add_column("Focus (5)")
    table.add_column("Focus (10)")
    table.add_column("Focus (Auto)")
    
    base = results["baseline"]
    f5 = results["focus_5"]
    f10 = results["focus_10"]
    fauto = results["focus_auto"]
    
    def delta(val, baseline):
        if baseline == 0:
            return "N/A"
        return f"{((val - baseline) / baseline) * 100:.1f}%"
    
    table.add_row("Accuracy", f"{base['score']}/3", f"{f5['score']}/3", f"{f10['score']}/3", f"{fauto['score']}/3")
    table.add_row("Total Tokens", f"{base['tokens']:,}", 
                  f"{f5['tokens']:,} ({delta(f5['tokens'], base['tokens'])})",
                  f"{f10['tokens']:,} ({delta(f10['tokens'], base['tokens'])})",
                  f"{fauto['tokens']:,} ({delta(fauto['tokens'], base['tokens'])})")
    table.add_row("Final Context", f"{base['messages']}", 
                  f"{f5['messages']} ({delta(f5['messages'], base['messages'])})",
                  f"{f10['messages']} ({delta(f10['messages'], base['messages'])})",
                  f"{fauto['messages']} ({delta(fauto['messages'], base['messages'])})")
    table.add_row("Compressions", "0", f"{f5['compressions']}", f"{f10['compressions']}", f"{fauto['compressions']}")
    table.add_row("Messages Dropped", "0", f"{f5['dropped']}", f"{f10['dropped']}", f"{fauto['dropped']}")
    
    console.print(table)

if __name__ == "__main__":
    asyncio.run(main())
