#!/usr/bin/env python3
"""Run the supported Microsoft Foundry model maintenance workflows."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Annotated, Literal

import typer

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parent
app = typer.Typer(
    add_completion=False,
    help="Preview, update, and reconcile the curated Foundry model catalog.",
    pretty_exceptions_show_locals=False,
)


def run_script(script: str, *arguments: str) -> None:
    """Run a model workflow implementation script.

    Args:
        script: Script filename in ``infra/scripts``.
        *arguments: Arguments passed to the script.

    Raises:
        SystemExit: If the implementation script fails.
    """
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script), *arguments],
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode:
        raise SystemExit(result.returncode)


def sync_arguments(
    *,
    dry_run: bool,
    sync_capacity: bool,
    sync_available_capacity: bool,
) -> list[str]:
    """Build arguments for catalog synchronization."""
    arguments: list[str] = []
    if dry_run:
        arguments.append("--dry-run")
    if sync_capacity:
        arguments.append("--sync-capacity")
    if sync_available_capacity:
        arguments.append("--sync-available-capacity")
    return arguments


@app.command()
def preview(
    sync_available_capacity: Annotated[
        bool,
        typer.Option(
            help="Preview capacities currently available in the target region."
        ),
    ] = False,
) -> None:
    """Preview catalog metadata changes and deployment reconciliation."""
    run_script(
        "sync_deployments_catalog.py",
        *sync_arguments(
            dry_run=True,
            sync_capacity=False,
            sync_available_capacity=sync_available_capacity,
        ),
    )
    run_script("deploy_models.py", "--mode", "manual", "--dry-run")


@app.command("sync")
def sync_catalog(
    sync_capacity: Annotated[
        bool,
        typer.Option(help="Replace configured capacities with Azure defaults."),
    ] = False,
    sync_available_capacity: Annotated[
        bool,
        typer.Option(help="Use currently available regional capacity."),
    ] = False,
) -> None:
    """Refresh curated entries from the live resource model catalog."""
    run_script(
        "sync_deployments_catalog.py",
        *sync_arguments(
            dry_run=False,
            sync_capacity=sync_capacity,
            sync_available_capacity=sync_available_capacity,
        ),
    )


@app.command()
def deploy(
    mode: Annotated[
        Literal["manual", "hook"],
        typer.Option(help="Execution mode used for catalog filtering."),
    ] = "manual",
    dry_run: Annotated[
        bool,
        typer.Option(help="Report deployment changes without applying them."),
    ] = False,
    prune: Annotated[
        bool,
        typer.Option(help="Delete deployments absent from the curated catalog."),
    ] = False,
) -> None:
    """Reconcile the curated catalog with the Foundry resource."""
    arguments = ["--mode", mode]
    if dry_run:
        arguments.append("--dry-run")
    if prune:
        arguments.append("--prune")
    run_script("deploy_models.py", *arguments)


@app.command()
def upgrade(
    apply: Annotated[
        bool,
        typer.Option(help="Write catalog changes and apply deployment changes."),
    ] = False,
    sync_capacity: Annotated[
        bool,
        typer.Option(help="Replace configured capacities with Azure defaults."),
    ] = False,
    sync_available_capacity: Annotated[
        bool,
        typer.Option(help="Use currently available regional capacity."),
    ] = False,
    prune: Annotated[
        bool,
        typer.Option(help="Delete deployments absent from the catalog when applying."),
    ] = False,
) -> None:
    """Refresh catalog metadata, then reconcile deployments."""
    dry_run = not apply
    run_script(
        "sync_deployments_catalog.py",
        *sync_arguments(
            dry_run=dry_run,
            sync_capacity=sync_capacity,
            sync_available_capacity=sync_available_capacity,
        ),
    )
    deploy_arguments = ["--mode", "manual"]
    if dry_run:
        deploy_arguments.append("--dry-run")
    if prune:
        deploy_arguments.append("--prune")
    run_script("deploy_models.py", *deploy_arguments)


if __name__ == "__main__":
    app()
