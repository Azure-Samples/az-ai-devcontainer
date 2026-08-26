#!/usr/bin/env python3
"""Run the supported Microsoft Foundry model maintenance workflows."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parent


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


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Preview, update, and reconcile the curated Foundry model catalog."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preview = subparsers.add_parser(
        "preview",
        help="Preview catalog metadata changes and deployment reconciliation.",
    )
    preview.add_argument(
        "--sync-available-capacity",
        action="store_true",
        help="Preview capacities currently available in the target region.",
    )

    sync = subparsers.add_parser(
        "sync",
        help="Refresh curated entries from the live account model catalog.",
    )
    sync.add_argument(
        "--sync-capacity",
        action="store_true",
        help="Replace configured capacities with Azure's default capacities.",
    )
    sync.add_argument(
        "--sync-available-capacity",
        action="store_true",
        help="Replace capacities with currently available regional capacity.",
    )

    deploy = subparsers.add_parser(
        "deploy",
        help="Reconcile the curated catalog with the Foundry account.",
    )
    deploy.add_argument("--mode", choices=("manual", "hook"), default="manual")
    deploy.add_argument(
        "--dry-run",
        action="store_true",
        help="Report deployment changes without applying them.",
    )
    deploy.add_argument(
        "--prune",
        action="store_true",
        help="Delete deployments absent from the curated catalog.",
    )

    upgrade = subparsers.add_parser(
        "upgrade",
        help="Refresh catalog metadata, then reconcile deployments.",
    )
    upgrade.add_argument(
        "--apply",
        action="store_true",
        help="Write catalog changes and apply deployment changes.",
    )
    upgrade.add_argument(
        "--sync-capacity",
        action="store_true",
        help="Replace configured capacities with Azure's default capacities.",
    )
    upgrade.add_argument(
        "--sync-available-capacity",
        action="store_true",
        help="Replace capacities with currently available regional capacity.",
    )
    upgrade.add_argument(
        "--prune",
        action="store_true",
        help="Delete deployments absent from the curated catalog when applying.",
    )

    return parser.parse_args()


def sync_arguments(args: argparse.Namespace, *, dry_run: bool) -> list[str]:
    """Build arguments for catalog synchronization."""
    arguments: list[str] = []
    if dry_run:
        arguments.append("--dry-run")
    if getattr(args, "sync_capacity", False):
        arguments.append("--sync-capacity")
    if getattr(args, "sync_available_capacity", False):
        arguments.append("--sync-available-capacity")
    return arguments


def main() -> None:
    """Run the selected model workflow."""
    args = parse_args()

    if args.command == "preview":
        run_script(
            "sync_deployments_catalog.py",
            *sync_arguments(args, dry_run=True),
        )
        run_script("deploy_models.py", "--mode", "manual", "--dry-run")
        return

    if args.command == "sync":
        run_script(
            "sync_deployments_catalog.py",
            *sync_arguments(args, dry_run=False),
        )
        return

    if args.command == "deploy":
        arguments = ["--mode", args.mode]
        if args.dry_run:
            arguments.append("--dry-run")
        if args.prune:
            arguments.append("--prune")
        run_script("deploy_models.py", *arguments)
        return

    dry_run = not args.apply
    run_script(
        "sync_deployments_catalog.py",
        *sync_arguments(args, dry_run=dry_run),
    )
    deploy_arguments = ["--mode", "manual"]
    if dry_run:
        deploy_arguments.append("--dry-run")
    if args.prune:
        deploy_arguments.append("--prune")
    run_script("deploy_models.py", *deploy_arguments)


if __name__ == "__main__":
    main()
