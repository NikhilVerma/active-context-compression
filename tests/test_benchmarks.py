"""Tests for the mini benchmark problems."""

import shutil
import tempfile
from pathlib import Path

import pytest

from src.benchmarks.mini import (
    check_bug_hunt,
    check_dependency_maze,
    check_hidden_config,
    get_mini_benchmark,
    setup_bug_hunt,
    setup_dependency_maze,
    setup_hidden_config,
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    workspace = Path(tempfile.mkdtemp())
    yield workspace
    shutil.rmtree(workspace, ignore_errors=True)


class TestHiddenConfig:
    def test_setup_creates_structure(self, temp_workspace):
        setup_hidden_config(temp_workspace)

        # Should have created red herrings
        assert (temp_workspace / "config" / "settings.json").exists()
        assert (temp_workspace / ".env").exists()

        # Should have created the actual config
        assert (temp_workspace / ".secrets" / "production.env").exists()

    def test_check_finds_correct_answer(self, temp_workspace):
        setup_hidden_config(temp_workspace)

        # Output that found the real config
        assert check_hidden_config(temp_workspace, "Found it in .secrets/production.env")
        assert check_hidden_config(temp_workspace, "DATABASE_URL=postgres://prod:5432/db")
        assert check_hidden_config(temp_workspace, "API_KEY=sk-12345")

        # Output that didn't find it
        assert not check_hidden_config(temp_workspace, "Found config in config/settings.json")


class TestBugHunt:
    def test_setup_creates_structure(self, temp_workspace):
        setup_bug_hunt(temp_workspace)

        assert (temp_workspace / "src" / "calculator.py").exists()
        assert (temp_workspace / "src" / "test_calculator.py").exists()

    def test_check_detects_fix(self, temp_workspace):
        setup_bug_hunt(temp_workspace)

        # Initially should fail (bug not fixed)
        assert not check_bug_hunt(temp_workspace, "")

        # Fix the bug
        calc_path = temp_workspace / "src" / "calculator.py"
        content = calc_path.read_text()
        fixed_content = content.replace(
            "def divide(a, b):\n    # BUG: Should check for zero division\n    return a / b",
            "def divide(a, b):\n    if b == 0:\n        raise ValueError('Cannot divide by zero')\n    return a / b",
        )
        calc_path.write_text(fixed_content)

        # Should now pass
        assert check_bug_hunt(temp_workspace, "")


class TestDependencyMaze:
    def test_setup_creates_structure(self, temp_workspace):
        setup_dependency_maze(temp_workspace)

        assert (temp_workspace / "requirements.txt").exists()
        assert (temp_workspace / "error.log").exists()

    def test_check_detects_fix(self, temp_workspace):
        setup_dependency_maze(temp_workspace)

        # Initially should fail
        assert not check_dependency_maze(temp_workspace, "")

        # Fix the requirements
        req_path = temp_workspace / "requirements.txt"
        content = req_path.read_text()
        fixed_content = content.replace("cryptography==3.4.8", "cryptography>=41.0.0")
        req_path.write_text(fixed_content)

        # Should now pass
        assert check_dependency_maze(temp_workspace, "")


def test_all_problems_have_required_fields():
    """Test that all benchmark problems have required fields."""
    problems = get_mini_benchmark()

    assert len(problems) >= 5

    for problem in problems:
        assert problem.id
        assert problem.name
        assert problem.description
        assert problem.task
        assert callable(problem.setup_workspace)
        assert callable(problem.check_solution)
