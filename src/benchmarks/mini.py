"""Mini benchmark with hand-crafted problems for quick iteration.

These problems are designed to benefit from exploration and backtracking:
- Multiple possible approaches, some of which are dead ends
- Hidden information that requires searching
- Red herrings that waste context if not pruned
"""

import tempfile
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BenchmarkProblem:
    """A benchmark problem."""

    id: str
    name: str
    description: str
    task: str
    setup_workspace: callable  # Function to set up the workspace
    check_solution: callable  # Function to check if the solution is correct


def setup_hidden_config(workspace: Path) -> None:
    """Problem 1: Find the hidden config file.

    The obvious places are empty or misleading. The actual config
    is in an unexpected location.
    """
    # Misleading configs
    (workspace / "config").mkdir()
    (workspace / "config" / "settings.json").write_text('{"note": "this is not the real config"}')
    (workspace / ".env").write_text("# Empty file, not what you need")

    # Red herring directory structure
    (workspace / "src").mkdir()
    (workspace / "src" / "config.py").write_text("# This just imports from somewhere else\nfrom core.settings import *")
    (workspace / "src" / "core").mkdir()
    (workspace / "src" / "core" / "settings.py").write_text("# Deprecated, see infrastructure/")

    # More misdirection
    (workspace / "infrastructure").mkdir()
    (workspace / "infrastructure" / "README.md").write_text("Config moved to deployment/")
    (workspace / "deployment").mkdir()
    (workspace / "deployment" / "config.yaml").write_text("# Legacy, see .secrets/")

    # The actual config
    (workspace / ".secrets").mkdir()
    (workspace / ".secrets" / "production.env").write_text("DATABASE_URL=postgres://prod:5432/db\nAPI_KEY=sk-12345")


def check_hidden_config(workspace: Path, output: str) -> bool:
    """Check if the agent found the real config."""
    return "postgres://prod:5432/db" in output or "sk-12345" in output or ".secrets/production.env" in output


def setup_bug_hunt(workspace: Path) -> None:
    """Problem 2: Find and fix a bug.

    There are multiple suspicious-looking things, but only one actual bug.
    """
    (workspace / "src").mkdir()

    # Main file with the bug
    (workspace / "src" / "calculator.py").write_text('''
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    # BUG: Should check for zero division
    return a / b

def power(a, b):
    return a ** b
''')

    # Test file that reveals the bug
    (workspace / "src" / "test_calculator.py").write_text('''
import pytest
from calculator import add, subtract, multiply, divide, power

def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 3) == 2

def test_multiply():
    assert multiply(3, 4) == 12

def test_divide():
    assert divide(10, 2) == 5

def test_divide_by_zero():
    # This test fails!
    with pytest.raises(ValueError):
        divide(10, 0)

def test_power():
    assert power(2, 3) == 8
''')

    # Red herrings
    (workspace / "src" / "utils.py").write_text('''
# This looks suspicious but is fine
def parse_number(s):
    try:
        return int(s)
    except ValueError:
        return float(s)  # This is intentional
''')

    (workspace / "src" / "legacy.py").write_text('''
# DEPRECATED - do not modify
# This code looks bad but is not used
def old_divide(a, b):
    result = a
    for _ in range(b):
        result = result  # looks wrong but this file is not used
    return result
''')


def check_bug_hunt(workspace: Path, output: str) -> bool:
    """Check if the agent fixed the divide function."""
    calc_path = workspace / "src" / "calculator.py"
    if not calc_path.exists():
        return False
    content = calc_path.read_text()
    # Should have added zero check
    return ("if b == 0" in content or "b == 0" in content or "ZeroDivisionError" in content or "ValueError" in content) and "divide" in content


def setup_dependency_maze(workspace: Path) -> None:
    """Problem 3: Figure out which dependency is causing the issue.

    Multiple packages are mentioned in error messages, but only one
    is the actual problem.
    """
    (workspace / "src").mkdir()

    (workspace / "requirements.txt").write_text('''
flask==2.0.1
requests==2.28.0
numpy==1.24.0
pandas==2.0.0
cryptography==3.4.8
''')

    (workspace / "src" / "app.py").write_text('''
from flask import Flask
import requests
import numpy as np
import pandas as pd
from cryptography.fernet import Fernet

app = Flask(__name__)

@app.route("/")
def hello():
    # This fails because cryptography 3.4.8 has a known issue with Python 3.11+
    key = Fernet.generate_key()
    return "Hello"
''')

    (workspace / "error.log").write_text('''
Traceback (most recent call last):
  File "app.py", line 5, in <module>
    from cryptography.fernet import Fernet
  File "/usr/lib/python3.11/site-packages/cryptography/fernet.py", line 8
    from cryptography.hazmat.primitives import hashes
  File "/usr/lib/python3.11/site-packages/cryptography/hazmat/primitives/__init__.py", line 2
    from cryptography.hazmat.bindings._rust import openssl
ImportError: /usr/lib/python3.11/site-packages/cryptography/hazmat/bindings/_rust.abi3.so: undefined symbol: EVP_MD_CTX_new

Note: This is a known issue with cryptography < 38.0.0 on Python 3.11+
''')

    # Red herrings in the error logs
    (workspace / "debug.log").write_text('''
WARNING: numpy version 1.24.0 deprecates some APIs
WARNING: pandas 2.0.0 changed default behavior for some operations
INFO: flask development server running
ERROR: requests connection timeout (unrelated network issue)
''')


def check_dependency_maze(workspace: Path, output: str) -> bool:
    """Check if the agent identified cryptography as the issue."""
    req_path = workspace / "requirements.txt"
    if not req_path.exists():
        return False
    content = req_path.read_text()
    # Should have updated cryptography version
    return "cryptography>=38" in content or "cryptography==38" in content or "cryptography==39" in content or "cryptography==40" in content or "cryptography==41" in content or "cryptography>=41" in content


def setup_refactor_challenge(workspace: Path) -> None:
    """Problem 4: Refactor duplicated code.

    Code is duplicated across multiple files. Need to find all instances
    and consolidate without breaking things.
    """
    (workspace / "src").mkdir()
    (workspace / "src" / "handlers").mkdir()

    # Duplicated validation logic across files
    validation_code = '''
def validate_email(email):
    import re
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+[.][a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))
'''

    (workspace / "src" / "handlers" / "user_handler.py").write_text(f'''
{validation_code}

def create_user(email, name):
    if not validate_email(email):
        raise ValueError("Invalid email")
    return {{"email": email, "name": name}}
''')

    (workspace / "src" / "handlers" / "admin_handler.py").write_text(f'''
{validation_code}

def create_admin(email, permissions):
    if not validate_email(email):
        raise ValueError("Invalid email")
    return {{"email": email, "permissions": permissions, "is_admin": True}}
''')

    (workspace / "src" / "handlers" / "guest_handler.py").write_text(f'''
{validation_code}

def create_guest(email):
    if not validate_email(email):
        raise ValueError("Invalid email")
    return {{"email": email, "is_guest": True}}
''')

    (workspace / "src" / "handlers" / "__init__.py").write_text("")


def check_refactor_challenge(workspace: Path, output: str) -> bool:
    """Check if the agent consolidated the validation logic."""
    # Should have created a shared utils file
    utils_path = workspace / "src" / "utils.py"
    validators_path = workspace / "src" / "validators.py"
    common_path = workspace / "src" / "common.py"

    shared_file_exists = utils_path.exists() or validators_path.exists() or common_path.exists()

    if not shared_file_exists:
        return False

    # Check that handlers now import instead of define
    user_handler = (workspace / "src" / "handlers" / "user_handler.py").read_text()
    admin_handler = (workspace / "src" / "handlers" / "admin_handler.py").read_text()

    # Should have imports, not inline definitions
    has_imports = ("from src" in user_handler or "from .." in user_handler or "import" in user_handler) and \
                  ("from src" in admin_handler or "from .." in admin_handler or "import" in admin_handler)

    # Definition should not be in handlers anymore
    no_inline_def = user_handler.count("def validate_email") <= 1 or "import" in user_handler

    return shared_file_exists and has_imports


def setup_test_failure_investigation(workspace: Path) -> None:
    """Problem 5: Investigate a flaky test.

    A test sometimes passes and sometimes fails. The bug is subtle
    and requires understanding the code flow.
    """
    (workspace / "src").mkdir()

    (workspace / "src" / "cache.py").write_text('''
import time

_cache = {}

def get_cached(key, ttl=60):
    """Get a cached value if not expired."""
    if key in _cache:
        value, timestamp = _cache[key]
        # BUG: Using time.time() means different results based on when called
        # Should compare against ttl properly
        if time.time() - timestamp < ttl:
            return value
    return None

def set_cached(key, value):
    """Cache a value with current timestamp."""
    _cache[key] = (value, time.time())

def clear_cache():
    """Clear the cache."""
    global _cache
    _cache = {}
''')

    (workspace / "src" / "service.py").write_text('''
from cache import get_cached, set_cached

def get_user_data(user_id):
    cached = get_cached(f"user:{user_id}")
    if cached:
        return cached

    # Simulate DB fetch
    data = {"id": user_id, "name": f"User {user_id}"}
    set_cached(f"user:{user_id}", data)
    return data
''')

    (workspace / "src" / "test_service.py").write_text('''
import time
from cache import clear_cache, set_cached, get_cached
from service import get_user_data

def test_cache_hit():
    """This test is flaky!

    Sometimes it fails because the cache expires between
    set and get if the test runs slowly.
    """
    clear_cache()

    # First call - cache miss, should fetch
    data1 = get_user_data(1)

    # Simulate some processing time (this makes it flaky)
    time.sleep(0.1)

    # Second call - should be cache hit
    # But if the machine is slow or ttl is too short, this fails
    data2 = get_user_data(1)

    # BUG: The test should mock time or use a longer TTL
    assert data1 == data2

def test_cache_miss():
    clear_cache()
    assert get_cached("nonexistent") is None
''')

    (workspace / "CI_LOG.txt").write_text('''
Run 1: test_cache_hit PASSED
Run 2: test_cache_hit PASSED
Run 3: test_cache_hit FAILED - AssertionError
Run 4: test_cache_hit PASSED
Run 5: test_cache_hit FAILED - AssertionError
Run 6: test_cache_hit PASSED

The test is flaky. Sometimes passes, sometimes fails.
No code changes between runs.
''')


def check_test_failure_investigation(workspace: Path, output: str) -> bool:
    """Check if the agent fixed the flaky test or identified the issue."""
    test_path = workspace / "src" / "test_service.py"
    cache_path = workspace / "src" / "cache.py"

    if test_path.exists():
        test_content = test_path.read_text()
        # Could fix by mocking time
        if "mock" in test_content.lower() or "patch" in test_content.lower():
            return True
        # Or by removing the sleep
        if "sleep" not in test_content:
            return True

    if cache_path.exists():
        cache_content = cache_path.read_text()
        # Or by fixing the cache implementation
        if "ttl" in cache_content and "monotomic" in cache_content.lower():
            return True

    # Or if they identified the issue in the output
    if "flaky" in output.lower() and ("time" in output.lower() or "ttl" in output.lower()):
        return True

    return False


# All problems
MINI_BENCHMARK_PROBLEMS = [
    BenchmarkProblem(
        id="hidden_config",
        name="Find Hidden Config",
        description="Find the actual configuration file among red herrings",
        task="Find the production database URL and API key. They're somewhere in this codebase but not where you'd expect.",
        setup_workspace=setup_hidden_config,
        check_solution=check_hidden_config,
    ),
    BenchmarkProblem(
        id="bug_hunt",
        name="Bug Hunt",
        description="Find and fix a bug among suspicious-looking code",
        task="The tests are failing. Find the bug and fix it. Run the tests with pytest to verify.",
        setup_workspace=setup_bug_hunt,
        check_solution=check_bug_hunt,
    ),
    BenchmarkProblem(
        id="dependency_maze",
        name="Dependency Maze",
        description="Identify which dependency is causing an import error",
        task="The app won't start due to an import error. Check error.log, identify the problematic dependency, and fix requirements.txt",
        setup_workspace=setup_dependency_maze,
        check_solution=check_dependency_maze,
    ),
    BenchmarkProblem(
        id="refactor_challenge",
        name="Refactor Challenge",
        description="Find and consolidate duplicated code",
        task="There's duplicated validation logic across multiple handler files. Consolidate it into a shared module and update the handlers to import from it.",
        setup_workspace=setup_refactor_challenge,
        check_solution=check_refactor_challenge,
    ),
    BenchmarkProblem(
        id="flaky_test",
        name="Flaky Test Investigation",
        description="Investigate and fix a flaky test",
        task="test_cache_hit is flaky - it sometimes passes and sometimes fails. Check CI_LOG.txt for history. Investigate why and fix it.",
        setup_workspace=setup_test_failure_investigation,
        check_solution=check_test_failure_investigation,
    ),
]


def get_mini_benchmark() -> list[BenchmarkProblem]:
    """Get all mini benchmark problems."""
    return MINI_BENCHMARK_PROBLEMS


def create_workspace_for_problem(problem: BenchmarkProblem) -> Path:
    """Create a temporary workspace for a problem."""
    workspace = Path(tempfile.mkdtemp(prefix=f"benchmark_{problem.id}_"))
    problem.setup_workspace(workspace)
    return workspace


def cleanup_workspace(workspace: Path) -> None:
    """Clean up a temporary workspace."""
    shutil.rmtree(workspace, ignore_errors=True)
