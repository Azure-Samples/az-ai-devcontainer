"""Tests for the Microsoft Foundry model maintenance workflow."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from azure.core.exceptions import HttpResponseError
from azure.mgmt.cognitiveservices.models import Deployment

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str) -> ModuleType:
    """Load a script as a module for focused unit tests."""
    path = REPO_ROOT / "infra" / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_expected_catalog_blockers_are_soft() -> None:
    """Deprecation and gated-access errors must not fail AZD provisioning."""
    module = load_script("deploy_models.py")
    entry = {"name": "example"}

    for code in (
        "ServiceModelDeprecated",
        "ServiceModelDeprecating",
        "SpecialFeatureOrQuotaIdRequired",
    ):
        error = HttpResponseError(message=f"({code}) blocked")
        error.code = code
        assert module.is_soft_blocker(entry, error)


def test_curated_catalog_is_small_and_has_current_default() -> None:
    """The catalog should remain intentional rather than mirror Azure wholesale.

    Cross-provider families (DeepSeek, MoonshotAI, Meta, Anthropic, Microsoft
    MAI) are deliberately represented with every currently non-deprecated
    model tier, not just one representative each -- this is why the cap is
    higher than the original OpenAI-only catalog.
    """
    module = load_script("deploy_models.py")
    catalog = module.load_catalog(REPO_ROOT / "infra" / "deployments.yaml")

    assert len(catalog) <= 45
    assert catalog[0]["name"] == "gpt-5.4-mini"
    assert {entry["name"] for entry in catalog} >= {
        "gpt-5.4",
        "gpt-5.3-codex",
        "text-embedding-3-small",
        "gpt-image-1.5",
        "DeepSeek-V4-Pro",
    }


def test_unmanaged_deployments_are_found_for_explicit_pruning() -> None:
    """Only deployments absent from the catalog should be prune candidates."""
    module = load_script("deploy_models.py")
    existing = {
        "gpt-5.4-mini": Deployment(),
        "legacy-model": Deployment(),
    }

    assert module.find_unmanaged_deployments(
        [{"name": "gpt-5.4-mini"}],
        existing,
    ) == ["legacy-model"]


def test_model_workflow_forwards_deploy_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Typer facade must preserve deployment mode and safety options."""
    module = load_script("models.py")
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        module,
        "run_script",
        lambda script, *arguments: calls.append((script, *arguments)),
    )

    module.deploy(mode="hook", dry_run=True, prune=True)

    assert calls == [("deploy_models.py", "--mode", "hook", "--dry-run", "--prune")]
