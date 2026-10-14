"""Standard runtime configuration loading for local project execution."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_runtime_environment() -> bool:
    """Load only the current working directory's `.env` without overwriting exports."""
    dotenv_path = Path.cwd() / ".env"
    if not dotenv_path.is_file():
        return False
    return load_dotenv(dotenv_path=dotenv_path, override=False)
