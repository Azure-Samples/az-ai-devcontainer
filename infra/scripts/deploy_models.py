#!/usr/bin/env python3
"""Reconcile Azure AI Foundry model deployments from infra/deployments.yaml."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import Annotated, Any, Literal

import typer
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.mgmt.cognitiveservices.models import (
    Deployment,
    DeploymentModel,
    DeploymentProperties,
    Sku,
)
from dotenv import load_dotenv
from ruamel.yaml import YAML

DEFAULT_RUN_MODES = ("manual", "hook")
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = REPO_ROOT / "infra" / "deployments.yaml"
yaml = YAML(typ="safe")
app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)


@dataclass(frozen=True)
class Settings:
    catalog: Path
    mode: str
    dry_run: bool
    offline: bool
    account_name: str
    resource_group: str
    subscription_id: str
    location: str


@dataclass
class DeploymentResult:
    name: str
    status: str
    detail: str


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


def require_setting(value: str | None, name: str) -> str:
    if value:
        return value
    raise ValueError(f"Missing required setting: {name}")


def normalize_region(value: str) -> str:
    return value.replace(" ", "").lower()


def normalize_yaml_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalize_yaml_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_yaml_value(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def load_catalog(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Deployment catalog not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.load(handle)
    normalized = normalize_yaml_value(data)
    if not isinstance(normalized, list):
        raise ValueError("Deployment catalog must be a YAML list.")
    return normalized


def build_settings(
    *,
    catalog: Path,
    mode: str,
    dry_run: bool,
    offline: bool,
    account_name: str | None,
    resource_group: str | None,
    subscription_id: str | None,
    location: str | None,
) -> Settings:
    if offline and not dry_run:
        raise ValueError("--offline can only be used together with --dry-run.")

    load_environment()
    return Settings(
        catalog=catalog,
        mode=mode,
        dry_run=dry_run,
        offline=offline,
        account_name=require_setting(
            account_name or os.getenv("AI_FOUNDRY_NAME"), "AI_FOUNDRY_NAME"
        ),
        resource_group=require_setting(
            resource_group or os.getenv("AZURE_RESOURCE_GROUP"),
            "AZURE_RESOURCE_GROUP",
        ),
        subscription_id=require_setting(
            subscription_id or os.getenv("AZURE_SUBSCRIPTION_ID"),
            "AZURE_SUBSCRIPTION_ID",
        ),
        location=require_setting(
            location or os.getenv("AZURE_LOCATION"), "AZURE_LOCATION"
        ),
    )


def create_client(subscription_id: str) -> CognitiveServicesManagementClient:
    return CognitiveServicesManagementClient(
        credential=DefaultAzureCredential(),
        subscription_id=subscription_id,
    )


def list_existing_deployments(
    client: CognitiveServicesManagementClient,
    *,
    resource_group: str,
    account_name: str,
) -> dict[str, Deployment]:
    items = client.deployments.list(resource_group, account_name)
    return {item.name: item for item in items if item.name}


def format_registration_guidance(entry: dict[str, Any]) -> str:
    registration_url = entry.get("registrationUrl")
    if isinstance(registration_url, str) and registration_url:
        return (
            " If this subscription still needs gated access for this model, "
            f"request it at {registration_url}."
        )
    if entry.get("requiresRegistration", False):
        return " This model is marked as requiring gated access in the catalog."
    return ""


def format_entry_error(entry: dict[str, Any], error: Exception) -> str:
    detail = str(error)
    guidance = format_registration_guidance(entry)
    if guidance and guidance.strip() not in detail:
        return f"{detail}{guidance}"
    return detail


def skip_result(
    entry: dict[str, Any], *, location: str, mode: str
) -> DeploymentResult | None:
    name = str(entry.get("name", "<unnamed>"))

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


def build_sdk_deployment(entry: dict[str, Any]) -> Deployment:
    model = entry["model"]
    properties = DeploymentProperties(
        model=DeploymentModel(
            format=model.get("format"),
            name=model.get("name"),
            version=model.get("version"),
            publisher=model.get("publisher"),
            source=model.get("source"),
            source_account=model.get("sourceAccount"),
        ),
        rai_policy_name=entry.get("raiPolicyName"),
        version_upgrade_option=entry.get("versionUpgradeOption"),
        parent_deployment_name=entry.get("parentDeploymentName"),
        spillover_deployment_name=entry.get("spilloverDeploymentName"),
        capacity_settings=entry.get("capacitySettings"),
    )
    return Deployment(
        sku=Sku(
            name=entry["sku"].get("name"),
            capacity=entry["sku"].get("capacity"),
        ),
        tags=entry.get("tags"),
        properties=properties,
    )


def current_snapshot(deployment: Deployment) -> dict[str, Any]:
    properties = deployment.properties
    model = properties.model if properties else None
    sku = deployment.sku
    return {
        "sku.name": sku.name if sku else None,
        "sku.capacity": sku.capacity if sku else None,
        "model.format": model.format if model else None,
        "model.name": model.name if model else None,
        "model.version": model.version if model else None,
        "model.publisher": model.publisher if model else None,
        "model.source": model.source if model else None,
        "model.sourceAccount": model.source_account if model else None,
        "properties.versionUpgradeOption": (
            properties.version_upgrade_option if properties else None
        ),
        "properties.raiPolicyName": properties.rai_policy_name if properties else None,
        "properties.parentDeploymentName": (
            properties.parent_deployment_name if properties else None
        ),
        "properties.spilloverDeploymentName": (
            properties.spillover_deployment_name if properties else None
        ),
    }


def desired_snapshot(entry: dict[str, Any]) -> dict[str, Any]:
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
        "properties.parentDeploymentName": entry.get("parentDeploymentName"),
        "properties.spilloverDeploymentName": entry.get("spilloverDeploymentName"),
    }


def diff_entry(existing: Deployment, entry: dict[str, Any]) -> list[str]:
    current = current_snapshot(existing)
    desired = desired_snapshot(entry)
    differences: list[str] = []
    for key, expected in desired.items():
        if expected is None:
            continue
        actual = current.get(key)
        if actual != expected:
            differences.append(f"{key}: current={actual!r}, desired={expected!r}")
    return differences


def reconcile_entry(
    entry: dict[str, Any],
    *,
    existing_deployments: dict[str, Deployment],
    client: CognitiveServicesManagementClient | None,
    settings: Settings,
) -> DeploymentResult:
    name = str(entry["name"])
    existing = existing_deployments.get(name)
    if existing:
        differences = diff_entry(existing, entry)
        if not differences:
            return DeploymentResult(
                name=name,
                status="unchanged",
                detail="deployment already matches catalog",
            )
        if settings.dry_run:
            return DeploymentResult(
                name=name,
                status="planned-update",
                detail="; ".join(differences),
            )
        if client is None:
            raise RuntimeError("Client is required for live updates.")
        client.deployments.begin_create_or_update(
            settings.resource_group,
            settings.account_name,
            name,
            build_sdk_deployment(entry),
        ).result()
        return DeploymentResult(
            name=name, status="updated", detail="; ".join(differences)
        )

    if settings.dry_run:
        return DeploymentResult(
            name=name, status="planned-create", detail="deployment is missing"
        )

    if client is None:
        raise RuntimeError("Client is required for live creates.")
    client.deployments.begin_create_or_update(
        settings.resource_group,
        settings.account_name,
        name,
        build_sdk_deployment(entry),
    ).result()
    return DeploymentResult(name=name, status="created", detail="deployment created")


def print_summary(results: list[DeploymentResult]) -> None:
    for result in results:
        typer.echo(f"[{result.status}] {result.name}: {result.detail}")

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    summary = ", ".join(f"{status}={count}" for status, count in sorted(counts.items()))
    typer.echo(f"Summary: {summary}")


@app.command()
def main(
    catalog: Annotated[
        Path,
        typer.Option(help="Path to the deployment catalog YAML file."),
    ] = DEFAULT_CATALOG_PATH,
    mode: Annotated[
        Literal["manual", "hook"],
        typer.Option(help="Execution mode used for runModes filtering."),
    ] = "manual",
    dry_run: Annotated[
        bool,
        typer.Option(
            help="Print the actions that would be taken without calling Azure."
        ),
    ] = False,
    offline: Annotated[
        bool,
        typer.Option(help="Skip Azure lookups. Only valid together with --dry-run."),
    ] = False,
    account_name: Annotated[
        str | None, typer.Option(help="Override AI_FOUNDRY_NAME.")
    ] = None,
    resource_group: Annotated[
        str | None,
        typer.Option(help="Override AZURE_RESOURCE_GROUP."),
    ] = None,
    subscription_id: Annotated[
        str | None,
        typer.Option(help="Override AZURE_SUBSCRIPTION_ID."),
    ] = None,
    location: Annotated[
        str | None, typer.Option(help="Override AZURE_LOCATION.")
    ] = None,
    allow_registration_required: Annotated[
        bool,
        typer.Option(
            hidden=True,
            help="Deprecated compatibility flag. Registration-required entries are attempted by default.",
        ),
    ] = False,
) -> None:
    del allow_registration_required

    try:
        settings = build_settings(
            catalog=catalog,
            mode=mode,
            dry_run=dry_run,
            offline=offline,
            account_name=account_name,
            resource_group=resource_group,
            subscription_id=subscription_id,
            location=location,
        )
        catalog_entries = load_catalog(settings.catalog)
    except Exception as error:  # noqa: BLE001
        typer.echo(
            f"Failed to initialize model deployment reconciliation: {error}",
            err=True,
        )
        raise typer.Exit(code=1) from None

    client: CognitiveServicesManagementClient | None = None
    existing_deployments: dict[str, Deployment] = {}
    if not settings.offline:
        try:
            client = create_client(settings.subscription_id)
            existing_deployments = list_existing_deployments(
                client,
                resource_group=settings.resource_group,
                account_name=settings.account_name,
            )
        except Exception as error:  # noqa: BLE001
            typer.echo(f"Failed to list existing deployments: {error}", err=True)
            raise typer.Exit(code=1) from None

    results: list[DeploymentResult] = []
    hard_failures = 0

    for entry in catalog_entries:
        name = str(entry.get("name", "<unnamed>"))
        try:
            skipped = skip_result(entry, location=settings.location, mode=settings.mode)
            if skipped:
                results.append(skipped)
                continue
            results.append(
                reconcile_entry(
                    entry,
                    existing_deployments=existing_deployments,
                    client=client,
                    settings=settings,
                )
            )
        except HttpResponseError as error:
            hard_failures += 1
            results.append(
                DeploymentResult(
                    name=name, status="error", detail=format_entry_error(entry, error)
                )
            )
        except Exception as error:  # noqa: BLE001
            hard_failures += 1
            results.append(
                DeploymentResult(
                    name=name, status="error", detail=format_entry_error(entry, error)
                )
            )

    print_summary(results)
    if hard_failures:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
