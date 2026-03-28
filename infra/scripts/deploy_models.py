#!/usr/bin/env python3
"""Reconcile Azure AI Foundry model deployments from infra/deployments.yaml."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

DEPLOYMENT_API_VERSION = "2025-12-01"
DEFAULT_RUN_MODES = ("manual", "hook")
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = REPO_ROOT / "infra" / "deployments.yaml"


@dataclass
class DeploymentResult:
    name: str
    status: str
    detail: str


def format_registration_guidance(entry: dict[str, Any]) -> str:
    registration_url = entry.get("registrationUrl")
    if isinstance(registration_url, str) and registration_url:
        return (
            " If this subscription still needs gated access for this model, "
            f"request it at {registration_url}."
        )
    if entry.get("requiresRegistration", False):
        return (
            " This model is marked as requiring gated access in the catalog."
        )
    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create or update Azure AI Foundry model deployments declared in "
            "infra/deployments.yaml."
        )
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG_PATH,
        help="Path to the deployment catalog YAML file.",
    )
    parser.add_argument(
        "--mode",
        choices=DEFAULT_RUN_MODES,
        default="manual",
        help="Execution mode used for runModes filtering.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the actions that would be taken without calling Azure.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip Azure lookups. Only valid together with --dry-run.",
    )
    parser.add_argument(
        "--allow-registration-required",
        action="store_true",
        help=(
            "Deprecated compatibility flag. Registration-required entries are "
            "attempted by default."
        ),
    )
    parser.add_argument("--account-name", help="Override AI_FOUNDRY_NAME.")
    parser.add_argument("--resource-group", help="Override AZURE_RESOURCE_GROUP.")
    parser.add_argument("--subscription-id", help="Override AZURE_SUBSCRIPTION_ID.")
    parser.add_argument("--location", help="Override AZURE_LOCATION.")
    return parser.parse_args()


def load_environment() -> None:
    result = subprocess.run(
        ["azd", "env", "get-values"],
        capture_output=True,
        cwd=REPO_ROOT,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout:
        load_dotenv(stream=StringIO(result.stdout), override=False)
    load_dotenv(override=False)


def require_setting(value: str | None, setting_name: str) -> str:
    if value:
        return value
    raise ValueError(f"Missing required setting: {setting_name}")


def normalize_region(value: str) -> str:
    return value.replace(" ", "").lower()


def normalize_catalog_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalize_catalog_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_catalog_value(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def load_catalog(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Deployment catalog not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Deployment catalog must be a YAML list.")
    normalized = normalize_catalog_value(data)
    if not isinstance(normalized, list):
        raise ValueError("Deployment catalog must be a YAML list.")
    return normalized


def az_rest(method: str, url: str, body: dict[str, Any] | None = None) -> Any:
    command = ["az", "rest", "--method", method, "--url", url, "--output", "json"]
    if body is not None:
        command.extend(["--body", json.dumps(body)])

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or result.stdout.strip() or "az rest failed"
        )

    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def build_deployments_url(
    subscription_id: str,
    resource_group: str,
    account_name: str,
    deployment_name: str | None = None,
) -> str:
    base_url = (
        "https://management.azure.com/subscriptions/"
        f"{subscription_id}/resourceGroups/{resource_group}/providers/"
        f"Microsoft.CognitiveServices/accounts/{account_name}/deployments"
    )
    if deployment_name:
        base_url = f"{base_url}/{deployment_name}"
    return f"{base_url}?api-version={DEPLOYMENT_API_VERSION}"


def list_existing_deployments(
    subscription_id: str, resource_group: str, account_name: str
) -> dict[str, dict[str, Any]]:
    payload = az_rest(
        "get",
        build_deployments_url(subscription_id, resource_group, account_name),
    )
    items = payload if isinstance(payload, list) else payload.get("value", [])
    return {item["name"]: item for item in items}


def should_skip_entry(
    entry: dict[str, Any],
    *,
    location: str,
    mode: str,
    allow_registration_required: bool,
) -> DeploymentResult | None:
    name = str(entry.get("name", "<unnamed>"))

    del allow_registration_required

    if entry.get("enabled", True) is False:
        return DeploymentResult(
            name=name, status="skipped", detail="disabled in catalog"
        )

    run_modes = entry.get("runModes", list(DEFAULT_RUN_MODES))
    if not isinstance(run_modes, list) or not all(
        isinstance(item, str) for item in run_modes
    ):
        raise ValueError(
            f"Entry '{name}' has invalid runModes; expected a list of strings."
        )
    if mode not in run_modes:
        return DeploymentResult(
            name=name,
            status="skipped",
            detail=f"runModes excludes mode '{mode}'",
        )

    allowed_regions = entry.get("allowedRegions", [])
    if not isinstance(allowed_regions, list) or not all(
        isinstance(item, str) for item in allowed_regions
    ):
        raise ValueError(
            f"Entry '{name}' has invalid allowedRegions; expected a list of strings."
        )
    if allowed_regions and normalize_region(location) not in {
        normalize_region(item) for item in allowed_regions
    }:
        return DeploymentResult(
            name=name,
            status="skipped",
            detail=f"region '{location}' is not in allowedRegions",
        )

    return None


def build_desired_body(entry: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "sku": entry["sku"],
        "properties": {
            "model": entry["model"],
        },
    }

    for property_name in (
        "capacitySettings",
        "deploymentState",
        "parentDeploymentName",
        "raiPolicyName",
        "scaleSettings",
        "serviceTier",
        "spilloverDeploymentName",
        "versionUpgradeOption",
    ):
        if property_name in entry:
            body["properties"][property_name] = entry[property_name]

    if "tags" in entry:
        body["tags"] = entry["tags"]

    return body


def flatten_deployment(existing: dict[str, Any]) -> dict[str, Any]:
    properties = existing.get("properties", {})
    model = properties.get("model", {})
    sku = existing.get("sku", {})
    return {
        "sku.name": sku.get("name"),
        "sku.capacity": sku.get("capacity"),
        "model.format": model.get("format"),
        "model.name": model.get("name"),
        "model.version": model.get("version"),
        "model.publisher": model.get("publisher"),
        "model.source": model.get("source"),
        "model.sourceAccount": model.get("sourceAccount"),
        "properties.versionUpgradeOption": properties.get("versionUpgradeOption"),
        "properties.raiPolicyName": properties.get("raiPolicyName"),
        "properties.deploymentState": properties.get("deploymentState"),
        "properties.serviceTier": properties.get("serviceTier"),
    }


def flatten_desired(entry: dict[str, Any]) -> dict[str, Any]:
    model = entry["model"]
    sku = entry["sku"]
    return {
        "sku.name": sku.get("name"),
        "sku.capacity": sku.get("capacity"),
        "model.format": model.get("format"),
        "model.name": model.get("name"),
        "model.version": model.get("version"),
        "model.publisher": model.get("publisher"),
        "model.source": model.get("source"),
        "model.sourceAccount": model.get("sourceAccount"),
        "properties.versionUpgradeOption": entry.get("versionUpgradeOption"),
        "properties.raiPolicyName": entry.get("raiPolicyName"),
        "properties.deploymentState": entry.get("deploymentState"),
        "properties.serviceTier": entry.get("serviceTier"),
    }


def diff_deployment(existing: dict[str, Any], desired: dict[str, Any]) -> list[str]:
    current = flatten_deployment(existing)
    target = flatten_desired(desired)
    differences: list[str] = []
    for key, desired_value in target.items():
        if desired_value is None:
            continue
        if current.get(key) != desired_value:
            differences.append(
                f"{key}: current={current.get(key)!r}, desired={desired_value!r}"
            )
    return differences


def reconcile_deployment(
    entry: dict[str, Any],
    *,
    existing_deployments: dict[str, dict[str, Any]],
    subscription_id: str,
    resource_group: str,
    account_name: str,
    dry_run: bool,
) -> DeploymentResult:
    deployment_name = entry["name"]
    existing = existing_deployments.get(deployment_name)
    body = build_desired_body(entry)

    if existing:
        differences = diff_deployment(existing, entry)
        if not differences:
            return DeploymentResult(
                name=deployment_name,
                status="unchanged",
                detail="deployment already matches catalog",
            )
        if dry_run:
            return DeploymentResult(
                name=deployment_name,
                status="planned-update",
                detail="; ".join(differences),
            )
        az_rest(
            "put",
            build_deployments_url(
                subscription_id,
                resource_group,
                account_name,
                deployment_name=deployment_name,
            ),
            body=body,
        )
        return DeploymentResult(
            name=deployment_name,
            status="updated",
            detail="; ".join(differences),
        )

    if dry_run:
        return DeploymentResult(
            name=deployment_name,
            status="planned-create",
            detail="deployment is missing",
        )

    az_rest(
        "put",
        build_deployments_url(
            subscription_id,
            resource_group,
            account_name,
            deployment_name=deployment_name,
        ),
        body=body,
    )
    return DeploymentResult(
        name=deployment_name,
        status="created",
        detail="deployment created",
    )


def print_summary(results: list[DeploymentResult]) -> None:
    for result in results:
        print(f"[{result.status}] {result.name}: {result.detail}")

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    summary = ", ".join(f"{status}={count}" for status, count in sorted(counts.items()))
    print(f"Summary: {summary}")


def format_entry_error(entry: dict[str, Any], error: Exception) -> str:
    detail = str(error)
    guidance = format_registration_guidance(entry)
    if guidance and guidance.strip() not in detail:
        detail = f"{detail}{guidance}"
    return detail


def main() -> int:
    args = parse_args()
    if args.offline and not args.dry_run:
        print("--offline can only be used together with --dry-run.", file=sys.stderr)
        return 1

    load_environment()

    try:
        account_name = require_setting(
            args.account_name or os.getenv("AI_FOUNDRY_NAME"), "AI_FOUNDRY_NAME"
        )
        resource_group = require_setting(
            args.resource_group or os.getenv("AZURE_RESOURCE_GROUP"),
            "AZURE_RESOURCE_GROUP",
        )
        subscription_id = require_setting(
            args.subscription_id or os.getenv("AZURE_SUBSCRIPTION_ID"),
            "AZURE_SUBSCRIPTION_ID",
        )
        location = require_setting(
            args.location or os.getenv("AZURE_LOCATION"), "AZURE_LOCATION"
        )
        catalog = load_catalog(args.catalog)
    except Exception as error:  # noqa: BLE001
        print(
            f"Failed to initialize model deployment reconciliation: {error}",
            file=sys.stderr,
        )
        return 1

    if args.offline:
        existing_deployments = {}
    else:
        try:
            existing_deployments = list_existing_deployments(
                subscription_id, resource_group, account_name
            )
        except Exception as error:  # noqa: BLE001
            print(f"Failed to list existing deployments: {error}", file=sys.stderr)
            return 1

    results: list[DeploymentResult] = []
    hard_failures = 0

    for entry in catalog:
        name = str(entry.get("name", "<unnamed>"))
        try:
            skipped = should_skip_entry(
                entry,
                location=location,
                mode=args.mode,
                allow_registration_required=args.allow_registration_required,
            )
            if skipped:
                results.append(skipped)
                continue

            results.append(
                reconcile_deployment(
                    entry,
                    existing_deployments=existing_deployments,
                    subscription_id=subscription_id,
                    resource_group=resource_group,
                    account_name=account_name,
                    dry_run=args.dry_run,
                )
            )
        except Exception as error:  # noqa: BLE001
            hard_failures += 1
            results.append(
                DeploymentResult(
                    name=name,
                    status="error",
                    detail=format_entry_error(entry, error),
                )
            )

    print_summary(results)
    return 1 if hard_failures else 0


if __name__ == "__main__":
    sys.exit(main())
