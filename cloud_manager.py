"""
cloud_manager.py — AWS Cloud Instance Management for ResearchSphere

Provides one-click controls to:
1. Scale the Auto Scaling Group to 0 and terminate all running EC2 instances immediately.
2. Inspect the live status of AWS Auto Scaling Groups and EC2 instances.
3. Restore/scale instances back up on demand.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    BotoCoreError = Exception
    ClientError = Exception


DEFAULT_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
DEFAULT_PROJECT = "researchsphere"
DEFAULT_ASG = f"{DEFAULT_PROJECT}-asg"


def get_aws_credentials(
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    region: Optional[str] = None,
) -> Dict[str, str]:
    """Resolve AWS credentials from arguments or environment variables."""
    resolved_key = (access_key or "").strip() or os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    resolved_secret = (secret_key or "").strip() or os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    resolved_region = (region or "").strip() or os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", DEFAULT_REGION)).strip()
    return {
        "access_key": resolved_key,
        "secret_key": resolved_secret,
        "region": resolved_region or DEFAULT_REGION,
    }


def _create_clients(
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    region: Optional[str] = None,
):
    """Instantiate boto3 autoscaling and ec2 clients."""
    if not BOTO3_AVAILABLE:
        raise RuntimeError("boto3 is not installed. Please install boto3 via pip install boto3.")

    creds = get_aws_credentials(access_key, secret_key, region)
    session_kwargs: Dict[str, Any] = {"region_name": creds["region"]}

    if creds["access_key"] and creds["secret_key"]:
        session_kwargs["aws_access_key_id"] = creds["access_key"]
        session_kwargs["aws_secret_access_key"] = creds["secret_key"]

    session = boto3.Session(**session_kwargs)
    asg_client = session.client("autoscaling")
    ec2_client = session.client("ec2")
    return asg_client, ec2_client, creds["region"]


def get_cloud_status(
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    region: Optional[str] = None,
    project_name: str = DEFAULT_PROJECT,
    asg_name: str = DEFAULT_ASG,
) -> Dict[str, Any]:
    """
    Fetch current AWS Auto Scaling Group status and list all project EC2 instances.
    """
    if not BOTO3_AVAILABLE:
        return {
            "success": False,
            "error": "boto3 library is not installed.",
            "asg": None,
            "instances": [],
        }

    try:
        asg_client, ec2_client, resolved_region = _create_clients(access_key, secret_key, region)

        # 1. Fetch Auto Scaling Group
        asg_info = None
        try:
            resp = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
            groups = resp.get("AutoScalingGroups", [])
            if groups:
                g = groups[0]
                asg_info = {
                    "name": g.get("AutoScalingGroupName"),
                    "desired_capacity": g.get("DesiredCapacity", 0),
                    "min_size": g.get("MinSize", 0),
                    "max_size": g.get("MaxSize", 0),
                    "status": g.get("Status", "Active"),
                    "instances_count": len(g.get("Instances", [])),
                    "created_time": str(g.get("CreatedTime")),
                    "target_groups": g.get("TargetGroupARNs", []),
                }
        except ClientError as e:
            asg_info = {"error": str(e)}

        # 2. Fetch EC2 instances tagged with Project or ASG
        instances: List[Dict[str, Any]] = []
        try:
            filters = [
                {
                    "Name": "tag:Project",
                    "Values": [project_name],
                }
            ]
            ec2_resp = ec2_client.describe_instances(Filters=filters)
            found_ids = set()

            for reservation in ec2_resp.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    inst_id = inst.get("InstanceId")
                    found_ids.add(inst_id)
                    instances.append(_parse_instance(inst))

            # Also check if any instances are attached to ASG that might not have the tag
            if asg_info and "error" not in asg_info:
                resp = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
                for g in resp.get("AutoScalingGroups", []):
                    for member in g.get("Instances", []):
                        m_id = member.get("InstanceId")
                        if m_id and m_id not in found_ids:
                            try:
                                single_resp = ec2_client.describe_instances(InstanceIds=[m_id])
                                for res in single_resp.get("Reservations", []):
                                    for inst in res.get("Instances", []):
                                        instances.append(_parse_instance(inst))
                                        found_ids.add(m_id)
                            except Exception:
                                pass
        except ClientError as e:
            return {
                "success": False,
                "error": f"AWS EC2 Error: {e}",
                "region": resolved_region,
                "asg": asg_info,
                "instances": [],
            }

        running_count = sum(1 for i in instances if i["state"] == "running")

        return {
            "success": True,
            "region": resolved_region,
            "asg": asg_info,
            "instances": instances,
            "running_count": running_count,
            "total_count": len(instances),
        }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "asg": None,
            "instances": [],
        }


def _parse_instance(inst: Dict[str, Any]) -> Dict[str, Any]:
    name = "Unnamed"
    for tag in inst.get("Tags", []):
        if tag.get("Key") == "Name":
            name = tag.get("Value", name)
            break

    state = inst.get("State", {}).get("Name", "unknown")
    launch_time = inst.get("LaunchTime")
    launch_str = launch_time.strftime("%Y-%m-%d %H:%M:%S UTC") if isinstance(launch_time, datetime) else str(launch_time or "")

    return {
        "id": inst.get("InstanceId"),
        "name": name,
        "state": state,
        "type": inst.get("InstanceType", ""),
        "public_ip": inst.get("PublicIpAddress") or "None",
        "private_ip": inst.get("PrivateIpAddress") or "None",
        "launch_time": launch_str,
    }


def delete_all_running_instances(
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    region: Optional[str] = None,
    project_name: str = DEFAULT_PROJECT,
    asg_name: str = DEFAULT_ASG,
) -> Dict[str, Any]:
    """
    ONE-CLICK ACTION:
    1. Scales the Auto Scaling Group to min=0, desired=0.
    2. Terminates all active EC2 instances immediately.
    3. Prevents ASG from auto-recreating instances.
    """
    if not BOTO3_AVAILABLE:
        return {"success": False, "error": "boto3 is not installed."}

    try:
        asg_client, ec2_client, resolved_region = _create_clients(access_key, secret_key, region)
        actions_taken = []
        terminated_ids: List[str] = []

        # Step 1: Scale ASG down to 0
        asg_scaled = False
        try:
            asg_client.update_auto_scaling_group(
                AutoScalingGroupName=asg_name,
                MinSize=0,
                DesiredCapacity=0,
            )
            asg_scaled = True
            actions_taken.append(f"Scaled Auto Scaling Group '{asg_name}' down to min_size=0, desired_capacity=0.")
        except ClientError as e:
            actions_taken.append(f"Notice: ASG update skipped or failed ({e.response.get('Error', {}).get('Message', str(e))}).")

        # Step 2: Discover all running or pending instances for this project / ASG
        instances_to_kill = []
        try:
            resp = ec2_client.describe_instances(
                Filters=[
                    {"Name": "tag:Project", "Values": [project_name]},
                    {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]},
                ]
            )
            for res in resp.get("Reservations", []):
                for inst in res.get("Instances", []):
                    i_id = inst.get("InstanceId")
                    if i_id:
                        instances_to_kill.append(i_id)

            # Also check ASG members
            try:
                asg_resp = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
                for g in asg_resp.get("AutoScalingGroups", []):
                    for member in g.get("Instances", []):
                        m_id = member.get("InstanceId")
                        if m_id and m_id not in instances_to_kill:
                            instances_to_kill.append(m_id)
            except Exception:
                pass

        except Exception as e:
            actions_taken.append(f"Warning discovering instances: {e}")

        # Step 3: Terminate the instances
        if instances_to_kill:
            try:
                term_resp = ec2_client.terminate_instances(InstanceIds=instances_to_kill)
                for item in term_resp.get("TerminatingInstances", []):
                    terminated_ids.append(item.get("InstanceId"))
                actions_taken.append(
                    f"Successfully sent termination signal to {len(terminated_ids)} instance(s): {', '.join(terminated_ids)}"
                )
            except ClientError as e:
                actions_taken.append(f"Error during instance termination: {e}")
        else:
            actions_taken.append("No active EC2 instances found running.")

        return {
            "success": True,
            "region": resolved_region,
            "asg_scaled": asg_scaled,
            "terminated_count": len(terminated_ids),
            "terminated_ids": terminated_ids,
            "actions": actions_taken,
        }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }


def scale_up_instances(
    count: int = 1,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    region: Optional[str] = None,
    asg_name: str = DEFAULT_ASG,
) -> Dict[str, Any]:
    """
    Restore / scale up instances in the Auto Scaling Group.
    """
    if not BOTO3_AVAILABLE:
        return {"success": False, "error": "boto3 is not installed."}

    try:
        asg_client, _, resolved_region = _create_clients(access_key, secret_key, region)
        asg_client.update_auto_scaling_group(
            AutoScalingGroupName=asg_name,
            MinSize=1,
            DesiredCapacity=count,
        )
        return {
            "success": True,
            "region": resolved_region,
            "message": f"Successfully updated '{asg_name}' to min_size=1, desired_capacity={count}. New instances will launch shortly.",
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }
