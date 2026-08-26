"""Tests for shared Microsoft Foundry Tools access verification."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script() -> ModuleType:
    """Load the Foundry Tools verifier for focused unit tests."""
    path = REPO_ROOT / "infra" / "scripts" / "verify_foundry_tools.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_explicit_endpoint_takes_precedence_and_is_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit endpoint must override local AZD environment values."""
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "https://from-env/")
    module = load_script()

    assert module.resolve_endpoint("https://from-cli/") == "https://from-cli"


def test_azure_ai_services_endpoint_is_a_supported_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shared Foundry Tools endpoint is usable without service aliases."""
    for variable in (
        "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
        "DOCUMENTINTELLIGENCE_ENDPOINT",
        "AI_FOUNDRY_ENDPOINT",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("AZURE_AI_SERVICES_ENDPOINT", "https://shared-foundry/")
    module = load_script()

    assert module.resolve_endpoint(None) == "https://shared-foundry"


def test_missing_endpoint_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verifier should fail explicitly rather than target an unknown resource."""
    for variable in (
        "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
        "DOCUMENTINTELLIGENCE_ENDPOINT",
        "AZURE_AI_SERVICES_ENDPOINT",
        "AI_FOUNDRY_ENDPOINT",
    ):
        monkeypatch.delenv(variable, raising=False)
    module = load_script()

    with pytest.raises(ValueError, match="No endpoint configured"):
        module.resolve_endpoint(None)
