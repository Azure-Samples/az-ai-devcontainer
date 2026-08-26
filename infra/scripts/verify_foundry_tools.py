#!/usr/bin/env python3
"""Verify keyless Document Intelligence and Content Understanding access."""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
    """Get an Entra bearer token for Azure AI services.

    Returns:
        A bearer token accepted by Azure AI services data-plane APIs.

    Raises:
        ClientAuthenticationError: If the active Azure identity cannot get a token.
    """
    return DefaultAzureCredential().get_token(COGNITIVE_SERVICES_SCOPE).token


def list_document_models(endpoint: str, token: str) -> int:
    """List Document Intelligence models using an Entra bearer token.

    Args:
        endpoint: Document Intelligence or Foundry shared-resource endpoint.
        token: Microsoft Entra bearer token for Azure AI services.

    Returns:
        The number of models returned by the API.

    Raises:
        ClientAuthenticationError: If the active Azure identity cannot get a token.
        HTTPError: If the endpoint rejects the authenticated request.
        URLError: If the endpoint cannot be reached.
        ValueError: If the API response has no model list.
    """
    request = Request(
        (
            f"{endpoint}/documentintelligence/documentModels"
            f"?api-version={DOCUMENT_INTELLIGENCE_API_VERSION}"
        ),
        headers={"Authorization": f"Bearer {token}"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)

    models = payload.get("value")
    if not isinstance(models, list):
        raise ValueError("Document Intelligence response did not contain a model list.")
    return len(models)


def list_content_understanding_analyzers(endpoint: str, token: str) -> int:
    """List Content Understanding analyzers using an Entra bearer token.

    Args:
        endpoint: Content Understanding or Foundry shared-resource endpoint.
        token: Microsoft Entra bearer token for Azure AI services.

    Returns:
        The number of analyzers returned by the API.

    Raises:
        HTTPError: If the endpoint rejects the authenticated request.
        URLError: If the endpoint cannot be reached.
        ValueError: If the API response has no analyzer list.
    """
    request = Request(
        (
            f"{endpoint}/contentunderstanding/analyzers"
            f"?api-version={CONTENT_UNDERSTANDING_API_VERSION}"
        ),
        headers={"Authorization": f"Bearer {token}"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)

    analyzers = payload.get("value")
    if not isinstance(analyzers, list):
        raise ValueError(
            "Content Understanding response did not contain an analyzer list."
        )
    return len(analyzers)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Verify passwordless Document Intelligence access on the shared "
            "Microsoft Foundry resource."
        )
    )
    parser.add_argument(
        "--endpoint",
        help=(
            "Document Intelligence endpoint. Defaults to "
            "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT, DOCUMENTINTELLIGENCE_ENDPOINT, "
            "AZURE_AI_SERVICES_ENDPOINT, or AI_FOUNDRY_ENDPOINT."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """Run non-destructive shared Foundry Tools access checks."""
    args = parse_args()
    try:
        endpoint = resolve_endpoint(args.endpoint)
        token = get_bearer_token()
        model_count = list_document_models(endpoint, token)
        analyzer_count = list_content_understanding_analyzers(endpoint, token)
    except (ClientAuthenticationError, HTTPError, URLError, ValueError) as error:
        print(f"Verification failed: {error}", file=sys.stderr)
        return 1

    print(
        "Foundry Tools access verified with DefaultAzureCredential: "
        f"{model_count} Document Intelligence models and {analyzer_count} "
        f"Content Understanding analyzers available at {endpoint}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
