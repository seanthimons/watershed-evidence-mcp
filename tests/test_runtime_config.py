import os
from pathlib import Path

from watershed_evidence_mcp.config import load_runtime_environment


def test_dotenv_loads_from_current_project_directory_without_overriding_exported_values(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text("ATTAINS_API_KEY=dotenv-value\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ATTAINS_API_KEY", raising=False)

    assert load_runtime_environment() is True
    assert os.environ["ATTAINS_API_KEY"] == "dotenv-value"

    monkeypatch.setenv("ATTAINS_API_KEY", "exported-value")
    assert load_runtime_environment() is True
    assert os.environ["ATTAINS_API_KEY"] == "exported-value"


def test_dotenv_returns_false_when_no_project_file_exists(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    assert load_runtime_environment() is False
