"""SWE-bench Lite benchmark loader."""

import subprocess
import sys
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


def load_swebench_lite(
    limit: int | None = None, instance_ids: list[str] | None = None
) -> list[SWEBenchInstance]:
    """Load SWE-bench Lite dataset.

    Args:
        limit: Maximum number of instances to load (for quick testing)
        instance_ids: Specific instance IDs to load (overrides limit if provided)

    Returns:
        List of SWEBenchInstance objects
    """
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

    instances = []

    # Create a lookup set for O(1) checking if we are filtering
    target_ids = set(instance_ids) if instance_ids else None

    for i, item in enumerate(dataset):
        # If we are looking for specific IDs, check first
        if target_ids:
            if item["instance_id"] not in target_ids:
                continue
        # Otherwise respect the limit
        elif limit and len(instances) >= limit:
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

        # If we found all target IDs, we can stop early
        if target_ids and len(instances) == len(target_ids):
            break

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

        # Try full clone if shallow fails or commit not found
        try:
            subprocess.run(
                ["git", "clone", repo_url, str(workspace)],
                check=True,
                capture_output=True,
                timeout=600,
            )
        except Exception:
            # Fallback to shallow clone if full fails (though full is safer for old commits)
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

        # ENVIRONMENT SETUP: Create venv and install dependencies
        # This is crucial for agents to run tests and actually solve the problem.
        venv_path = workspace / "venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)], check=True, capture_output=True
        )

        # Install the repo in editable mode with test dependencies
        # We try a few common patterns
        pip_cmd = str(venv_path / "bin" / "pip")

        # Upgrade pip first
        subprocess.run([pip_cmd, "install", "--upgrade", "pip"], cwd=workspace, capture_output=True)

        # Try installing dependencies
        install_cmds = [
            [pip_cmd, "install", "-e", ".[test]"],
            [pip_cmd, "install", "-e", ".[dev]"],
            [pip_cmd, "install", "-e", "."],
            [pip_cmd, "install", "-r", "requirements.txt"],
            [pip_cmd, "install", "-r", "requirements-dev.txt"],
        ]

        for cmd in install_cmds:
            try:
                subprocess.run(cmd, cwd=workspace, capture_output=True, timeout=300)
            except subprocess.TimeoutExpired:
                continue
            except subprocess.CalledProcessError:
                continue

        # Also install pytest if not present
        subprocess.run([pip_cmd, "install", "pytest"], cwd=workspace, capture_output=True)

        return True
    except subprocess.TimeoutExpired as e:
        print(f"Setup timed out for {instance.instance_id}: {e}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Setup failed for {instance.instance_id}: {e}")
        print(f"Stderr: {e.stderr.decode() if e.stderr else 'None'}")
        return False


def check_swebench_solution(instance: SWEBenchInstance, workspace: Path) -> float:
    """Check the solution and return the percentage of tests passed.

    Args:
        instance: The SWE-bench instance
        workspace: Path to the workspace with the agent's solution

    Returns:
        float: Success rate (0.0 to 1.0)
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

        # Run tests and capture output
        # Use the venv python we set up
        venv_python = workspace / "venv" / "bin" / "python"
        if not venv_python.exists():
            raise RuntimeError(f"Virtual environment python not found at {venv_python}")

        result = subprocess.run(
            [str(venv_python), "-m", "pytest", "--tb=short"],
            cwd=workspace,
            capture_output=True,
            timeout=120,
            text=True,  # Get string output
        )

        # Parse pytest output
        output = result.stdout + result.stderr

        # DEBUG: Print output to see what happened
        # logger.debug(f"Pytest Output for {instance.instance_id}: {len(output)} chars")

        # Regex to find "X passed, Y failed"
        import re

        # Pattern 1: "15 passed, 2 failed in..."
        # Pattern 2: "17 passed in..." (Perfect score)
        # Pattern 3: "3 failed in..." (0 passed)

        passed = 0
        failed = 0

        passed_match = re.search(r"(\d+) passed", output)
        if passed_match:
            passed = int(passed_match.group(1))

        failed_match = re.search(r"(\d+) failed", output)
        if failed_match:
            failed = int(failed_match.group(1))

        error_match = re.search(r"(\d+) error", output)
        if error_match:
            failed += int(error_match.group(1))

        total = passed + failed

        if total == 0:
            # Maybe it collected 0 tests or crashed before collection
            # If exit code 0, assume 100% (e.g. no tests found but script passed)
            # If exit code != 0, assume 0%
            return 1.0 if result.returncode == 0 else 0.0

        return passed / total

    except Exception as e:
        print(f"Error checking solution: {e}")
        return 0.0


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
