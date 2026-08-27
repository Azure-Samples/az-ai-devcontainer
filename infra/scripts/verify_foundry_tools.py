#!/usr/bin/env python3
"""Verify keyless Document Intelligence and Content Understanding access."""

from __future__ import annotations

import json
import os
from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import typer
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import DefaultAzureCredential

COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"
DOCUMENT_INTELLIGENCE_API_VERSION = "2024-11-30"
CONTENT_UNDERSTANDING_API_VERSION = "2025-11-01"


def resolve_endpoint(explicit_endpoint: str | None) -> str:
    """Resolve the Document Intelligence endpoint from CLI or environment.

    Args:
        explicit_endpoint: Endpoint supplied with ``--endpoint``.

    Returns:
        A normalized endpoint without a trailing slash.

    Raises:
        ValueError: If no endpoint is configured.
    """
    endpoint = explicit_endpoint or next(
        (
            os.environ.get(name)
            for name in (
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
                "DOCUMENTINTELLIGENCE_ENDPOINT",
                "AZURE_AI_SERVICES_ENDPOINT",
                "AI_FOUNDRY_ENDPOINT",
            )
            if os.environ.get(name)
        ),
        None,
    )
    if not endpoint:
        raise ValueError(
            "No endpoint configured. Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT "
            "or pass --endpoint."
        )
    return endpoint.rstrip("/")


def get_bearer_token() -> str:
    """Get an Entra bearer token for Foundry Tools."""
    return DefaultAzureCredential().get_token(COGNITIVE_SERVICES_SCOPE).token


def get_json(url: str, token: str) -> object:
    """Get a JSON payload from a Foundry Tools endpoint."""
    request = Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def list_document_models(endpoint: str, token: str) -> int:
    """List Document Intelligence models using an Entra bearer token."""
    payload = get_json(
        (
            f"{endpoint}/documentintelligence/documentModels"
            f"?api-version={DOCUMENT_INTELLIGENCE_API_VERSION}"
        ),
        token,
    )
    if not isinstance(payload, dict):
        raise ValueError("Document Intelligence response was not a JSON object.")
    models = payload.get("value")
    if not isinstance(models, list):
        raise ValueError("Document Intelligence response did not contain a model list.")
    return len(models)


def list_content_understanding_analyzers(endpoint: str, token: str) -> int:
    """List Content Understanding analyzers using an Entra bearer token."""
    payload = get_json(
        (
            f"{endpoint}/contentunderstanding/analyzers"
            f"?api-version={CONTENT_UNDERSTANDING_API_VERSION}"
        ),
        token,
    )
    if not isinstance(payload, dict):
        raise ValueError("Content Understanding response was not a JSON object.")
    analyzers = payload.get("value")
    if not isinstance(analyzers, list):
        raise ValueError(
            "Content Understanding response did not contain an analyzer list."
        )
    return len(analyzers)


def main(
    endpoint: Annotated[
        str | None,
        typer.Option(
            help=(
                "Document Intelligence endpoint. Defaults to the configured "
                "Foundry Tools endpoint."
            )
        ),
    ] = None,
) -> None:
    """Verify passwordless access on the shared Microsoft Foundry resource."""
    try:
        resolved_endpoint = resolve_endpoint(endpoint)
        token = get_bearer_token()
        model_count = list_document_models(resolved_endpoint, token)
        analyzer_count = list_content_understanding_analyzers(resolved_endpoint, token)
    except (ClientAuthenticationError, HTTPError, URLError, ValueError) as error:
        typer.echo(f"Verification failed: {error}", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(
        "Foundry Tools access verified with DefaultAzureCredential: "
        f"{model_count} Document Intelligence models and {analyzer_count} "
        f"Content Understanding analyzers available at {resolved_endpoint}."
    )


if __name__ == "__main__":
    typer.run(main)
