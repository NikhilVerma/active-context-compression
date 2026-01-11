"""Configuration management for the benchmark suite."""

import os
from pathlib import Path


def get_docker_socket() -> str | None:
    """
    Find and return the Docker socket path.

    Supports:
    - Standard Linux: /var/run/docker.sock
    - OrbStack (macOS): ~/.orbstack/run/docker.sock
    - Docker Desktop (macOS): ~/.docker/run/docker.sock
    - Custom: DOCKER_HOST environment variable

    Returns:
        Socket path if found, None otherwise.
    """
    # Check if DOCKER_HOST is already set
    if "DOCKER_HOST" in os.environ:
        host = os.environ["DOCKER_HOST"]
        if host.startswith("unix://"):
            return host[7:]  # Strip unix:// prefix
        return host

    # Check common socket locations
    socket_paths = [
        "/var/run/docker.sock",
        os.path.expanduser("~/.orbstack/run/docker.sock"),  # OrbStack
        os.path.expanduser("~/.docker/run/docker.sock"),  # Docker Desktop
        "/run/docker.sock",
    ]

    for socket_path in socket_paths:
        if os.path.exists(socket_path):
            return socket_path

    return None


def setup_docker_env() -> bool:
    """
    Configure Docker environment variables.

    Returns:
        True if Docker is configured, False otherwise.
    """
    socket = get_docker_socket()
    if socket:
        os.environ["DOCKER_HOST"] = f"unix://{socket}"
        return True
    return False


# Default models
DEFAULT_MODEL_FAST = "claude-haiku-4-5-20251001"
DEFAULT_MODEL_SMART = "claude-sonnet-4-5-20250929"
DEFAULT_MODEL = DEFAULT_MODEL_FAST  # Use Haiku for all tests by default

# Benchmark defaults - increased to match Anthropic's "100+ tool uses" guidance
DEFAULT_MAX_STEPS = 200
DEFAULT_STEPS_PER_FOCUS = 15
DEFAULT_MAX_WORKERS = 4

# Extended thinking budget (for Claude models when enabled)
DEFAULT_THINKING_BUDGET = 128000

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
LOGS_DIR = PROJECT_ROOT / "logs"
