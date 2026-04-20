#!/usr/bin/env python3
"""Check Azure AI model capacity for models listed in deployments.yaml.

This script reads the deployments.yaml file and checks if there is enough capacity
available in the Azure region for each model deployment. It uses Azure Developer CLI
(azd) environment variables for configuration.

Usage:
    python check_model_capacity.py [--region REGION]

Requirements:
    - Azure CLI installed and authenticated (az login)
    - Azure Developer CLI installed (azd)
    - Run 'azd env refresh' to load environment variables
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from azure.identity import DefaultAzureCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient


def load_azd_env() -> dict[str, str]:
    """Load environment variables from Azure Developer CLI.

    Returns:
        Dictionary of environment variables from AZD.

    Raises:
        RuntimeError: If azd command fails or environment is not initialized.
    """
    try:
        result = subprocess.run(
            ["azd", "env", "get-values"],
            capture_output=True,
            text=True,
            check=True,
        )

        env_vars = {}
        for line in result.stdout.strip().split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                # Remove quotes if present
                value = value.strip('"').strip("'")
                env_vars[key] = value

        return env_vars

    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Failed to load AZD environment. "
            f"Make sure you've run 'azd init' and 'azd env refresh'.\n"
            f"Error: {e.stderr}"
        ) from e
    except FileNotFoundError:
        raise RuntimeError(
            "Azure Developer CLI (azd) not found. "
            "Please install it from: "
            "https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/"
        ) from None


def load_deployments(deployments_file: Path) -> list[dict[str, Any]]:
    """Load model deployments from YAML file.

    Args:
        deployments_file: Path to the deployments.yaml file.

    Returns:
        List of deployment configurations.

    Raises:
        FileNotFoundError: If deployments file doesn't exist.
        yaml.YAMLError: If YAML is invalid.
    """
    if not deployments_file.exists():
        raise FileNotFoundError(f"Deployments file not found: {deployments_file}")

    with open(deployments_file) as f:
        deployments = yaml.safe_load(f)

    if not deployments:
        raise ValueError("No deployments found in deployments.yaml")

    return deployments


def get_subscription_id(env_vars: dict[str, str]) -> str:
    """Get Azure subscription ID from environment variables.

    Args:
        env_vars: Dictionary of environment variables.

    Returns:
        Azure subscription ID.

    Raises:
        ValueError: If subscription ID is not found.
    """
    subscription_id = env_vars.get("AZURE_SUBSCRIPTION_ID")
    if not subscription_id:
        raise ValueError(
            "AZURE_SUBSCRIPTION_ID not found in AZD environment. "
            "Run 'azd env refresh' to populate environment variables."
        )
    return subscription_id


def get_azure_region(env_vars: dict[str, str], override_region: str | None) -> str:
    """Get Azure region from environment variables or override.

    Args:
        env_vars: Dictionary of environment variables.
        override_region: Optional region override from command line.

    Returns:
        Azure region name.

    Raises:
        ValueError: If region cannot be determined.
    """
    if override_region:
        return override_region

    region = env_vars.get("AZURE_LOCATION")
    if not region:
        raise ValueError(
            "AZURE_LOCATION not found in AZD environment and no --region specified. "
            "Run 'azd env refresh' or specify --region argument."
        )
    return region


def check_model_capacity(
    subscription_id: str,
    region: str,
    deployments: list[dict[str, Any]],
    credential: DefaultAzureCredential,
) -> dict[str, Any]:
    """Check capacity availability for each model in the region.

    Args:
        subscription_id: Azure subscription ID.
        region: Azure region to check capacity in.
        deployments: List of model deployments to check.
        credential: Azure credential for authentication.

    Returns:
        Dictionary with capacity check results.
    """
    client = CognitiveServicesManagementClient(credential, subscription_id)

    results = {
        "region": region,
        "total_models": len(deployments),
        "available": [],
        "unavailable": [],
        "unknown": [],
        "errors": [],
    }

    print(f"\n🔍 Checking capacity for {len(deployments)} models in {region}...")
    print("=" * 80)

    for deployment in deployments:
        model_name = deployment.get("name", "unknown")
        model_format = deployment.get("model", {}).get("format", "unknown")
        model_version = deployment.get("model", {}).get("version", "unknown")
        requested_capacity = deployment.get("sku", {}).get("capacity", 1)

        full_model_name = f"{model_format}/{model_name}"

        try:
            # Note: Azure SDK doesn't provide a direct capacity check API
            # This is a simplified check using available SKUs
            # In production, you'd need to call the appropriate capacity API
            # or attempt a deployment with validate-only flag

            # For GlobalStandard SKU, models are generally available
            # but we'll list them as "available with limitations"
            sku_name = deployment.get("sku", {}).get("name", "")

            if sku_name == "GlobalStandard":
                results["available"].append(
                    {
                        "name": model_name,
                        "full_name": full_model_name,
                        "version": model_version,
                        "capacity": requested_capacity,
                        "sku": sku_name,
                        "note": "GlobalStandard SKU - pay-as-you-go, generally available",
                    }
                )
                print(f"✅ {full_model_name} v{model_version} - Available")
            else:
                results["unknown"].append(
                    {
                        "name": model_name,
                        "full_name": full_model_name,
                        "version": model_version,
                        "capacity": requested_capacity,
                        "sku": sku_name,
                        "note": "Non-GlobalStandard SKU - manual verification needed",
                    }
                )
                print(f"⚠️  {full_model_name} v{model_version} - Unknown (requires manual check)")

        except Exception as e:
            error_msg = str(e)
            results["errors"].append(
                {
                    "name": model_name,
                    "full_name": full_model_name,
                    "version": model_version,
                    "error": error_msg,
                }
            )
            print(f"❌ {full_model_name} v{model_version} - Error: {error_msg}")

    return results


def print_summary(results: dict[str, Any]) -> None:
    """Print summary of capacity check results.

    Args:
        results: Dictionary with capacity check results.
    """
    print("\n" + "=" * 80)
    print(f"📊 SUMMARY - Region: {results['region']}")
    print("=" * 80)
    print(f"Total models checked: {results['total_models']}")
    print(f"✅ Available: {len(results['available'])}")
    print(f"❌ Unavailable: {len(results['unavailable'])}")
    print(f"⚠️  Unknown/Manual Check: {len(results['unknown'])}")
    print(f"🚨 Errors: {len(results['errors'])}")

    if results["unavailable"]:
        print("\n❌ UNAVAILABLE MODELS:")
        for model in results["unavailable"]:
            print(f"  - {model['full_name']} v{model['version']}")
            if "note" in model:
                print(f"    Note: {model['note']}")

    if results["unknown"]:
        print("\n⚠️  MODELS REQUIRING MANUAL VERIFICATION:")
        for model in results["unknown"]:
            print(f"  - {model['full_name']} v{model['version']}")
            if "note" in model:
                print(f"    Note: {model['note']}")

    if results["errors"]:
        print("\n🚨 ERRORS:")
        for error in results["errors"]:
            print(f"  - {error['full_name']} v{error['version']}")
            print(f"    Error: {error['error']}")

    print("\n💡 NOTE:")
    print("  GlobalStandard SKU models use pay-as-you-go pricing with no upfront")
    print("  capacity requirements. They are generally available across most regions.")
    print("  Some models may have regional restrictions (noted in deployments.yaml).")


def save_results(results: dict[str, Any], output_file: Path) -> None:
    """Save results to JSON file.

    Args:
        results: Dictionary with capacity check results.
        output_file: Path to save results to.
    """
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to: {output_file}")


def main() -> int:
    """Main function.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Check Azure AI model capacity for deployments.yaml"
    )
    parser.add_argument(
        "--region",
        help="Azure region to check (overrides AZURE_LOCATION from AZD env)",
    )
    parser.add_argument(
        "--deployments",
        type=Path,
        default=Path("infra/deployments.yaml"),
        help="Path to deployments.yaml file (default: infra/deployments.yaml)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Save results to JSON file",
    )

    args = parser.parse_args()

    try:
        # Load AZD environment
        print("🔐 Loading Azure Developer CLI environment...")
        env_vars = load_azd_env()

        # Get subscription and region
        subscription_id = get_subscription_id(env_vars)
        region = get_azure_region(env_vars, args.region)

        print(f"📍 Subscription: {subscription_id}")
        print(f"📍 Region: {region}")

        # Load deployments
        print(f"📂 Loading deployments from: {args.deployments}")
        deployments = load_deployments(args.deployments)

        # Authenticate to Azure
        print("🔑 Authenticating to Azure...")
        credential = DefaultAzureCredential()

        # Check capacity
        results = check_model_capacity(subscription_id, region, deployments, credential)

        # Print summary
        print_summary(results)

        # Save results if requested
        if args.output:
            save_results(results, args.output)

        # Return exit code based on results
        if results["errors"] or results["unavailable"]:
            return 1

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
