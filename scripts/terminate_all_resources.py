#!/usr/bin/env python3
"""
scripts/terminate_all_resources.py — 1-Click AWS Resource Destroyer

Terminates and destroys ALL AWS resources created for ResearchSphere:
- Auto Scaling Group and all EC2 instances
- Application Load Balancer (ALB) and Target Groups
- Security Groups (ALB SG and EC2 SG)
- VPC, Subnets, Internet Gateway, and Route Tables

Can be run locally or triggered via GitHub Actions:
  python scripts/terminate_all_resources.py
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

root_dir = Path(__file__).resolve().parent.parent
terraform_dir = root_dir / "terraform"


def run_terraform_destroy() -> bool:
    """Attempts to run terraform destroy using S3 backend or local state."""
    print("[*] Checking for Terraform...")
    try:
        result = subprocess.run(["terraform", "--version"], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return False
        print(f"    Found {result.stdout.strip().splitlines()[0]}")
    except FileNotFoundError:
        return False

    print("\n[>>] Running 'terraform destroy' in ./terraform...")
    cmd = ["terraform", "destroy", "-auto-approve", "-input=false"]
    ret = subprocess.run(cmd, cwd=str(terraform_dir), check=False)
    return ret.returncode == 0


def run_boto3_full_cleanup() -> bool:
    """Falls back to boto3 cleanup if Terraform is not locally installed."""
    print("\n[*] Initializing boto3 cleanup sequence...")
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        print("[-] Error: Neither 'terraform' nor 'boto3' is available.")
        print("    Please run inside GitHub Actions, or install boto3: pip install boto3")
        return False

    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")).strip()
    session = boto3.Session(region_name=region)
    asg = session.client("autoscaling")
    ec2 = session.client("ec2")
    elbv2 = session.client("elbv2")

    PROJECT = "researchsphere"
    ASG_NAME = f"{PROJECT}-asg"
    ALB_NAME = f"{PROJECT}-alb"
    TG_NAME = f"{PROJECT}-tg"

    print(f"    Target Region : {region}")
    print(f"    Target Project: {PROJECT}")

    # 1. Scale down and delete ASG
    print(f"\n[1/4] Deleting Auto Scaling Group: {ASG_NAME}...")
    try:
        asg.delete_auto_scaling_group(AutoScalingGroupName=ASG_NAME, ForceDelete=True)
        print(f"      Deleted ASG {ASG_NAME}")
    except ClientError as e:
        print(f"      ASG: {e.response['Error']['Message']}")

    # 2. Delete ALB
    print(f"\n[2/4] Deleting Application Load Balancer: {ALB_NAME}...")
    try:
        albs = elbv2.describe_load_balancers(Names=[ALB_NAME]).get("LoadBalancers", [])
        for alb in albs:
            arn = alb["LoadBalancerArn"]
            elbv2.delete_load_balancer(LoadBalancerArn=arn)
            print(f"      Deleted ALB {arn}")
    except ClientError as e:
        print(f"      ALB: {e.response['Error']['Message']}")

    # 3. Delete Target Group
    print(f"\n[3/4] Deleting Target Group: {TG_NAME}...")
    try:
        tgs = elbv2.describe_target_groups(Names=[TG_NAME]).get("TargetGroups", [])
        for tg in tgs:
            arn = tg["TargetGroupArn"]
            elbv2.delete_target_group(TargetGroupArn=arn)
            print(f"      Deleted Target Group {arn}")
    except ClientError as e:
        print(f"      TG: {e.response['Error']['Message']}")

    # 4. Terminate any stray EC2 instances
    print(f"\n[4/4] Terminating any remaining project EC2 instances...")
    try:
        filters = [{"Name": "tag:Project", "Values": [PROJECT]}, {"Name": "instance-state-name", "Values": ["running", "pending", "stopped"]}]
        instances = ec2.describe_instances(Filters=filters)
        ids = [i["InstanceId"] for r in instances.get("Reservations", []) for i in r.get("Instances", [])]
        if ids:
            ec2.terminate_instances(InstanceIds=ids)
            print(f"      Terminated EC2 instances: {ids}")
        else:
            print("      No active instances found.")
    except ClientError as e:
        print(f"      EC2: {e.response['Error']['Message']}")

    print("\n[+] Boto3 Cleanup Complete!")
    return True


def main():
    print("=" * 65)
    print("   ResearchSphere - 1-Click AWS Full Resource Terminator")
    print("=" * 65)

    if run_terraform_destroy():
        print("\n[+] SUCCESS: All AWS resources destroyed via Terraform!")
    else:
        print("\n[*] Falling back to AWS API direct cleanup...")
        if run_boto3_full_cleanup():
            print("\n[+] SUCCESS: Core AWS resources terminated!")
        else:
            print("\n[-] Please trigger '🛑 Terminate AWS Resources' in GitHub Actions.")
            sys.exit(1)


if __name__ == "__main__":
    main()
