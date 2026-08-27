#!/usr/bin/env python3
"""Refresh infra/deployments.yaml from the Microsoft Foundry model catalog.

The script uses the same ARM endpoint as `az cognitiveservices account list-models`
and updates only the fields backed by the API:

- name
- sku.name
- model.format
- model.name
- model.version

Local catalog-only fields such as `enabled`, `runModes`, `allowedRegions`,
`requiresRegistration`, `registrationUrl`, and `notes` are preserved. Existing
`sku.capacity` values are also preserved unless `--sync-capacity` or
`--sync-available-capacity` is provided.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Annotated, Any, Literal

import typer
from azure.identity import DefaultAzureCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from dotenv import load_dotenv
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

DEFAULT_API_VERSION = "2025-04-01-preview"
DEFAULT_SKU_NAME = "GlobalStandard"
DEFAULT_UPGRADE_OPTION = "OnceCurrentVersionExpired"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = REPO_ROOT / "infra" / "deployments.yaml"


@dataclass(frozen=True)
class CatalogModel:
    """Normalized model metadata returned by the Azure management API."""

    name: str
    format: str
    version: str
    sku_name: str
    default_capacity: int
    available_capacity: int | None
    is_default_version: bool
    lifecycle_status: str | None


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


def az_rest(method: str, url: str) -> Any:
    command = ["az", "rest", "--method", method, "--url", url, "--output", "json"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or result.stdout.strip() or "az rest failed"
        )
    return json.loads(result.stdout)


def create_client(subscription_id: str) -> CognitiveServicesManagementClient:
    return CognitiveServicesManagementClient(
        credential=DefaultAzureCredential(),
        subscription_id=subscription_id,
    )


def build_models_url(
    subscription_id: str,
    resource_group: str,
    account_name: str,
    api_version: str,
) -> str:
    return (
        "https://management.azure.com/subscriptions/"
        f"{subscription_id}/resourceGroups/{resource_group}/providers/"
        f"Microsoft.CognitiveServices/accounts/{account_name}/models"
        f"?api-version={api_version}"
    )


def version_sort_key(value: str) -> tuple[Any, ...]:
    parts = re.split(r"(\d+)", value)
    key: list[Any] = []
    for part in parts:
        if not part:
            continue
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part.casefold())
    return tuple(key)


def choose_preferred_model(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    def priority(item: dict[str, Any]) -> tuple[Any, ...]:
        return (
            1 if item.get("isDefaultVersion") else 0,
            1 if item.get("lifecycleStatus") == "Stable" else 0,
            version_sort_key(str(item.get("version", ""))),
        )

    return max(candidates, key=priority)


def pick_sku(item: dict[str, Any], sku_name: str) -> dict[str, Any] | None:
    skus = item.get("skus", [])
    if not isinstance(skus, list):
        return None
    for sku in skus:
        if isinstance(sku, dict) and sku.get("name") == sku_name:
            return sku
    return None


def normalize_catalog_models(
    items: list[dict[str, Any]], sku_name: str
) -> dict[str, CatalogModel]:
    by_name: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        if not pick_sku(item, sku_name):
            continue
        name = item.get("name")
        model_format = item.get("format")
        version = item.get("version")
        if (
            not isinstance(name, str)
            or not isinstance(model_format, str)
            or not isinstance(version, str)
        ):
            continue
        by_name.setdefault(name, []).append(item)

    normalized: dict[str, CatalogModel] = {}
    for name, candidates in by_name.items():
        chosen = choose_preferred_model(candidates)
        chosen_sku = pick_sku(chosen, sku_name)
        if chosen_sku is None:
            continue
        capacity_data = chosen_sku.get("capacity", {})
        default_capacity = (
            capacity_data.get("default") if isinstance(capacity_data, dict) else None
        )
        if not isinstance(default_capacity, int):
            continue
        normalized[name] = CatalogModel(
            name=name,
            format=str(chosen["format"]),
            version=str(chosen["version"]),
            sku_name=sku_name,
            default_capacity=default_capacity,
            available_capacity=None,
            is_default_version=bool(chosen.get("isDefaultVersion")),
            lifecycle_status=(
                str(chosen["lifecycleStatus"])
                if isinstance(chosen.get("lifecycleStatus"), str)
                else None
            ),
        )

    return dict(
        sorted(
            normalized.items(),
            key=lambda item: (
                item[1].format.casefold(),
                item[1].name.casefold(),
                version_sort_key(item[1].version),
            ),
        )
    )


def fetch_account_models(
    subscription_id: str,
    resource_group: str,
    account_name: str,
    api_version: str,
    sku_name: str,
) -> dict[str, CatalogModel]:
    payload = az_rest(
        "get",
        build_models_url(
            subscription_id=subscription_id,
            resource_group=resource_group,
            account_name=account_name,
            api_version=api_version,
        ),
    )
    items = payload if isinstance(payload, list) else payload.get("value", [])
    if not isinstance(items, list):
        raise ValueError("Unexpected models payload; expected a list response.")
    return normalize_catalog_models(items, sku_name)


def fetch_available_capacities(
    client: CognitiveServicesManagementClient,
    *,
    location: str,
    models: dict[str, CatalogModel],
) -> dict[str, int]:
    capacities: dict[str, int] = {}
    for name, model in models.items():
        items = client.location_based_model_capacities.list(
            location,
            model.format,
            model.name,
            model.version,
        )
        for item in items:
            properties = getattr(item, "properties", None)
            if properties is None or properties.sku_name != model.sku_name:
                continue
            available_capacity = properties.available_capacity
            if isinstance(available_capacity, float | int):
                capacities[name] = int(available_capacity)
                break
    return capacities


def load_yaml_catalog(path: Path) -> tuple[YAML, CommentedSeq]:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 120
    yaml.indent(mapping=2, sequence=4, offset=2)
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.load(handle)
    if not isinstance(data, CommentedSeq):
        raise ValueError("Deployment catalog must be a top-level YAML sequence.")
    return yaml, data


def index_entries(catalog: CommentedSeq) -> dict[str, CommentedMap]:
    entries: dict[str, CommentedMap] = {}
    for item in catalog:
        if not isinstance(item, CommentedMap):
            continue
        name = item.get("name")
        if isinstance(name, str):
            entries[name] = item
    return entries


def ensure_commented_map(parent: CommentedMap, key: str) -> CommentedMap:
    value = parent.get(key)
    if isinstance(value, CommentedMap):
        return value
    replacement = CommentedMap()
    parent[key] = replacement
    return replacement


def set_if_changed(
    entry: CommentedMap, key: str, value: Any, changes: list[str]
) -> None:
    if entry.get(key) != value:
        entry[key] = value
        changes.append(key)


def apply_model_to_entry(
    entry: CommentedMap,
    model: CatalogModel,
    *,
    sync_capacity: bool,
    sync_available_capacity: bool,
) -> list[str]:
    changes: list[str] = []
    set_if_changed(entry, "name", model.name, changes)

    sku = ensure_commented_map(entry, "sku")
    set_if_changed(sku, "name", model.sku_name, changes)
    if sync_available_capacity:
        if model.available_capacity is not None:
            set_if_changed(sku, "capacity", model.available_capacity, changes)
    elif sync_capacity or "capacity" not in sku:
        set_if_changed(sku, "capacity", model.default_capacity, changes)

    model_map = ensure_commented_map(entry, "model")
    set_if_changed(model_map, "format", model.format, changes)
    set_if_changed(model_map, "name", model.name, changes)
    set_if_changed(model_map, "version", model.version, changes)

    return changes


def build_new_entry(model: CatalogModel, default_upgrade_option: str) -> CommentedMap:
    entry = CommentedMap()
    entry["name"] = model.name
    entry["sku"] = CommentedMap(
        {
            "name": model.sku_name,
            "capacity": (
                model.available_capacity
                if model.available_capacity is not None
                else model.default_capacity
            ),
        }
    )
    entry["model"] = CommentedMap(
        {
            "format": model.format,
            "name": model.name,
            "version": model.version,
        }
    )
    entry["versionUpgradeOption"] = default_upgrade_option
    return entry


def render_summary(lines: list[str]) -> None:
    for line in lines:
        print(line)


def main(
    catalog_path: Annotated[
        Path,
        typer.Option("--catalog", help="Path to the deployment catalog YAML file."),
    ] = DEFAULT_CATALOG_PATH,
    api_version: Annotated[
        str,
        typer.Option(help="Management API version for the resource models endpoint."),
    ] = DEFAULT_API_VERSION,
    sku_name: Annotated[
        str,
        typer.Option(help="Only synchronize models that expose this SKU."),
    ] = DEFAULT_SKU_NAME,
    default_upgrade_option: Annotated[
        Literal[
            "NoAutoUpgrade",
            "OnceCurrentVersionExpired",
            "OnceNewDefaultVersionAvailable",
        ],
        typer.Option(help="Upgrade option assigned to newly appended entries."),
    ] = DEFAULT_UPGRADE_OPTION,
    sync_capacity: Annotated[
        bool,
        typer.Option(help="Use Azure's default capacity for existing entries."),
    ] = False,
    sync_available_capacity: Annotated[
        bool,
        typer.Option(help="Use currently available regional capacity."),
    ] = False,
    append_new: Annotated[
        bool,
        typer.Option(help="Append models not already present in the catalog."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(help="Report changes without writing the catalog."),
    ] = False,
    account_name: Annotated[
        str | None,
        typer.Option(help="Override AI_FOUNDRY_NAME."),
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
        str | None,
        typer.Option(help="Override AZURE_LOCATION."),
    ] = None,
) -> None:
    """Refresh curated deployment metadata from the Foundry model catalog."""
    load_environment()

    if sync_capacity and sync_available_capacity:
        typer.echo(
            "Choose only one of --sync-capacity or --sync-available-capacity.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        account_name = require_setting(
            account_name or os.getenv("AI_FOUNDRY_NAME"), "AI_FOUNDRY_NAME"
        )
        resource_group = require_setting(
            resource_group or os.getenv("AZURE_RESOURCE_GROUP"),
            "AZURE_RESOURCE_GROUP",
        )
        subscription_id = require_setting(
            subscription_id or os.getenv("AZURE_SUBSCRIPTION_ID"),
            "AZURE_SUBSCRIPTION_ID",
        )
        yaml, catalog = load_yaml_catalog(catalog_path)
        api_models = fetch_account_models(
            subscription_id=subscription_id,
            resource_group=resource_group,
            account_name=account_name,
            api_version=api_version,
            sku_name=sku_name,
        )

        if sync_available_capacity:
            location = require_setting(
                location or os.getenv("AZURE_LOCATION"),
                "AZURE_LOCATION",
            )
            client = create_client(subscription_id)
            available_capacities = fetch_available_capacities(
                client,
                location=location,
                models=api_models,
            )
            api_models = {
                name: CatalogModel(
                    name=model.name,
                    format=model.format,
                    version=model.version,
                    sku_name=model.sku_name,
                    default_capacity=model.default_capacity,
                    available_capacity=available_capacities.get(name),
                    is_default_version=model.is_default_version,
                    lifecycle_status=model.lifecycle_status,
                )
                for name, model in api_models.items()
            }
    except Exception as error:  # noqa: BLE001
        typer.echo(f"Failed to initialize deployment catalog sync: {error}", err=True)
        raise typer.Exit(code=1) from None

    existing_entries = index_entries(catalog)
    summary: list[str] = []
    updated_count = 0
    unchanged_count = 0
    appended_count = 0

    for name, entry in existing_entries.items():
        model = api_models.get(name)
        if model is None:
            summary.append(
                f"[missing] {name}: not returned by Azure for sku={sku_name}"
            )
            continue

        changes = apply_model_to_entry(
            entry,
            model,
            sync_capacity=sync_capacity,
            sync_available_capacity=sync_available_capacity,
        )
        if changes:
            updated_count += 1
            summary.append(f"[updated] {name}: refreshed {', '.join(changes)}")
        else:
            unchanged_count += 1
            summary.append(f"[unchanged] {name}: already matches Azure")

    if append_new:
        for name, model in api_models.items():
            if name in existing_entries:
                continue
            catalog.append(build_new_entry(model, default_upgrade_option))
            appended_count += 1
            summary.append(f"[appended] {name}: added new catalog entry")

    if not dry_run and (updated_count or appended_count):
        with catalog_path.open("w", encoding="utf-8") as handle:
            yaml.dump(catalog, handle)

    if dry_run and (updated_count or appended_count):
        summary.append("[dry-run] No file changes were written.")

    stale_count = sum(1 for line in summary if line.startswith("[missing]"))
    summary.append(
        "Summary: "
        f"updated={updated_count}, unchanged={unchanged_count}, "
        f"appended={appended_count}, missing={stale_count}"
    )
    render_summary(summary)


if __name__ == "__main__":
    typer.run(main)
