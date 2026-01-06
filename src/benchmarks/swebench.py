"""SWE-bench Lite benchmark loader."""

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from datasets import load_dataset


@dataclass
class SWEBenchInstance:
    """A single SWE-bench instance."""

    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    hints_text: str
    patch: str  # Gold patch for evaluation
    test_patch: str  # Tests to run


def load_swebench_lite(limit: int | None = None) -> list[SWEBenchInstance]:
    """Load SWE-bench Lite dataset.

    Args:
        limit: Maximum number of instances to load (for quick testing)

    Returns:
        List of SWEBenchInstance objects
    """
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

    instances = []
    for i, item in enumerate(dataset):
        if limit and i >= limit:
            break

        instances.append(
            SWEBenchInstance(
                instance_id=item["instance_id"],
                repo=item["repo"],
                base_commit=item["base_commit"],
                problem_statement=item["problem_statement"],
                hints_text=item.get("hints_text", ""),
                patch=item["patch"],
                test_patch=item["test_patch"],
            )
        )

    return instances


def setup_swebench_workspace(instance: SWEBenchInstance, workspace: Path) -> bool:
    """Set up a workspace for a SWE-bench instance.

    Clones the repo and checks out the base commit.

    Args:
        instance: The SWE-bench instance
        workspace: Path to create the workspace

    Returns:
        True if setup succeeded
    """
    try:
        # Clone the repo
        repo_url = f"https://github.com/{instance.repo}.git"
        subprocess.run(
            ["git", "clone", "--depth", "100", repo_url, str(workspace)],
            check=True,
            capture_output=True,
            timeout=300,
        )

        # Checkout the base commit
        subprocess.run(
            ["git", "checkout", instance.base_commit],
            cwd=workspace,
            check=True,
            capture_output=True,
        )

        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"Failed to setup workspace for {instance.instance_id}: {e}")
        return False


def check_swebench_solution(instance: SWEBenchInstance, workspace: Path) -> bool:
    """Check if the solution passes the test patch.

    This is a simplified check - the full SWE-bench harness is more rigorous.

    Args:
        instance: The SWE-bench instance
        workspace: Path to the workspace with the agent's solution

    Returns:
        True if the solution appears correct
    """
    try:
        # Apply the test patch
        test_patch_file = workspace / "test_patch.diff"
        test_patch_file.write_text(instance.test_patch)

        subprocess.run(
            ["git", "apply", str(test_patch_file)],
            cwd=workspace,
            check=True,
            capture_output=True,
        )

        # Try to run the tests (this is repo-specific, simplified here)
        # In reality, you'd need repo-specific test commands
        result = subprocess.run(
            ["python", "-m", "pytest", "-x", "--tb=short"],
            cwd=workspace,
            capture_output=True,
            timeout=120,
        )

        return result.returncode == 0
    except Exception:
        return False


def get_task_prompt(instance: SWEBenchInstance) -> str:
    """Generate a task prompt for the agent.

    Args:
        instance: The SWE-bench instance

    Returns:
        Task prompt string
    """
    prompt = f"""Fix the following issue in the codebase:

{instance.problem_statement}

"""

    if instance.hints_text:
        prompt += f"""Hints:
{instance.hints_text}

"""

    prompt += """Find the relevant code, understand the issue, and implement a fix.
When done, respond with TASK_COMPLETE and describe what you changed."""

    return prompt
