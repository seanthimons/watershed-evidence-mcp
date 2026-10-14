import os
import subprocess
import sys
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


def test_dotenv_ignores_parent_directory_files(monkeypatch, tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    child = parent / "child"
    child.mkdir(parents=True)
    (parent / ".env").write_text("ATTAINS_API_KEY=parent-value\n", encoding="utf-8")
    monkeypatch.chdir(child)
    monkeypatch.delenv("ATTAINS_API_KEY", raising=False)

    assert load_runtime_environment() is False
    assert "ATTAINS_API_KEY" not in os.environ


def test_package_import_loads_exact_current_directory_dotenv(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("ATTAINS_API_KEY=dotenv-value\n", encoding="utf-8")
    source_root = Path(__file__).parents[1] / "src"
    environment = os.environ.copy()
    environment.pop("ATTAINS_API_KEY", None)
    environment["PYTHONPATH"] = str(source_root)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; import watershed_evidence_mcp; "
                "print(os.environ.get('ATTAINS_API_KEY', ''))"
            ),
        ],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "dotenv-value"


def test_package_import_preserves_exported_environment_value(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("ATTAINS_API_KEY=dotenv-value\n", encoding="utf-8")
    source_root = Path(__file__).parents[1] / "src"
    environment = os.environ.copy()
    environment["ATTAINS_API_KEY"] = "exported-value"
    environment["PYTHONPATH"] = str(source_root)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; import watershed_evidence_mcp; print(os.environ['ATTAINS_API_KEY'])",
        ],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "exported-value"
