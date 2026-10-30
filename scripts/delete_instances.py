#!/usr/bin/env python3
"""
scripts/delete_instances.py

1-Click script to delete/terminate all running cloud EC2 instances
for ResearchSphere and scale the Auto Scaling Group down to 0.

Usage:
    python scripts/delete_instances.py
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path so cloud_manager can be imported
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from cloud_manager import delete_all_running_instances, get_cloud_status, DEFAULT_PROJECT, DEFAULT_ASG, DEFAULT_REGION


def main():
    print("=" * 65)
    print("  ResearchSphere - 1-Click Cloud Instance Terminator")
    print("=" * 65)
    print(f"  Target Project : {DEFAULT_PROJECT}")
    print(f"  Target ASG     : {DEFAULT_ASG}")
    print(f"  Target Region  : {DEFAULT_REGION}")
    print("=" * 65)

    print("\n[*] Checking current cloud status...")
    status = get_cloud_status()

    if not status.get("success"):
        print(f"[!] Note during status check: {status.get('error')}")
        print("    Attempting termination sequence anyway with available credentials...\n")
    else:
        running = status.get("running_count", 0)
        total = status.get("total_count", 0)
        asg = status.get("asg") or {}
        print(f"  * Running EC2 Instances : {running}")
        print(f"  * Total Tracked Instances: {total}")
        if asg and "desired_capacity" in asg:
            print(f"  * ASG Desired Capacity  : {asg.get('desired_capacity')} (min: {asg.get('min_size')}, max: {asg.get('max_size')})")

    print("\n[>>] Executing 1-Click Delete Action...")
    result = delete_all_running_instances()

    if result.get("success"):
        print("\n[+] SUCCESS!")
        for action in result.get("actions", []):
            print(f"  -> {action}")
        print(f"\nTotal instances terminated: {result.get('terminated_count', 0)}")
        print("Auto Scaling Group scaled to 0. AWS billing for EC2 instances has stopped.")
    else:
        err = result.get('error', '')
        print(f"\n[-] FAILED: {err}")
        if "credentials" in err.lower():
            print("\n[!] Tip: Set your AWS credentials using environment variables:")
            print("       set AWS_ACCESS_KEY_ID=your_key")
            print("       set AWS_SECRET_ACCESS_KEY=your_secret")
            print("       set AWS_REGION=us-east-1")
            print("    Or configure AWS CLI via 'aws configure'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
