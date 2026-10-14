"""Standard runtime configuration loading for local project execution."""

from __future__ import annotations

from dotenv import find_dotenv, load_dotenv


def load_runtime_environment() -> bool:
    """Load a working-directory `.env` without replacing explicitly exported values."""
    dotenv_path = find_dotenv(usecwd=True)
    if not dotenv_path:
        return False
    return load_dotenv(dotenv_path=dotenv_path, override=False)
