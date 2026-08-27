"""Repository-level hygiene checks enforced by CI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from the repository."""
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    assert isinstance(value, dict)
    return value


def test_repository_json_files_are_valid() -> None:
    """Configuration and notebook files must contain valid JSON objects."""
    for path in (
        REPO_ROOT / ".devcontainer" / "devcontainer.json",
        REPO_ROOT / "infra" / "abbreviations.json",
        REPO_ROOT / "infra" / "main.parameters.json",
        REPO_ROOT / "notebooks" / "SampleNotebook.ipynb",
    ):
        load_json(path)


def test_notebooks_have_no_committed_outputs() -> None:
    """Committed notebooks must not contain execution state or outputs."""
    for path in (REPO_ROOT / "notebooks").glob("*.ipynb"):
        notebook = load_json(path)
        cells = notebook.get("cells")
        assert isinstance(cells, list)
        for cell in cells:
            assert isinstance(cell, dict)
            if cell.get("cell_type") != "code":
                continue
            assert cell.get("execution_count") is None
            assert cell.get("outputs") == []


def test_readme_references_current_image() -> None:
    """The README image reference must resolve to the renamed asset."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    image_name = "microsoft-foundry-devcontainer.png"

    assert image_name in readme
    assert (REPO_ROOT / image_name).is_file()
    assert "aigbb-devcontainer.png" not in readme
