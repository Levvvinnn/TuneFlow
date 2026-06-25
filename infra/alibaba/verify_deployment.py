"""
Alibaba Cloud deployment verification.
Makes real SDK calls against deployed ECS and ApsaraDB resources.
This file is linked from the hackathon submission as proof of Alibaba Cloud API usage.

Usage:
  pip install alibabacloud-ecs20140526 alibabacloud-rds20140815 python-dotenv
  python verify_deployment.py
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Load deployment IDs from deploy.sh outputs, or from env vars
def _read_or_env(file_path: str, env_key: str) -> str:
    p = Path(file_path)
    if p.exists():
        return p.read_text().strip()
    val = os.getenv(env_key, "")
    if not val:
        raise EnvironmentError(
            f"Cannot find {env_key}. Set it in .env or run deploy.sh first."
        )
    return val


def verify_ecs(region_id: str, instance_id: str, access_key_id: str, access_key_secret: str):
    """Describe ECS instance and print key info."""
    from alibabacloud_ecs20140526.client import Client as EcsClient
    from alibabacloud_ecs20140526.models import DescribeInstancesRequest
    from alibabacloud_tea_openapi.models import Config

    config = Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        region_id=region_id,
    )
    client = EcsClient(config)

    req = DescribeInstancesRequest(
        region_id=region_id,
        instance_ids=json.dumps([instance_id]),
    )
    response = client.describe_instances(req)
    instances = response.body.instances.instance
    if not instances:
        print(f"[ECS] Instance {instance_id} not found.")
        return None

    inst = instances[0]
    info = {
        "instance_id": inst.instance_id,
        "instance_name": inst.instance_name,
        "status": inst.status,
        "instance_type": inst.instance_type,
        "region_id": inst.region_id,
        "zone_id": inst.zone_id,
        "public_ip": (
            inst.public_ip_address.ip_address[0]
            if inst.public_ip_address and inst.public_ip_address.ip_address
            else "N/A"
        ),
        "creation_time": inst.creation_time,
    }
    print("\n=== ECS Instance ===")
    for k, v in info.items():
        print(f"  {k:20s}: {v}")
    return info


def verify_rds(region_id: str, instance_id: str, access_key_id: str, access_key_secret: str):
    """Describe ApsaraDB RDS instance and print key info."""
    from alibabacloud_rds20140815.client import Client as RdsClient
    from alibabacloud_rds20140815.models import DescribeDBInstancesRequest
    from alibabacloud_tea_openapi.models import Config

    config = Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        region_id=region_id,
    )
    client = RdsClient(config)

    req = DescribeDBInstancesRequest(
        region_id=region_id,
        d_b_instance_id=instance_id,
    )
    response = client.describe_d_b_instances(req)
    items = response.body.items.d_b_instance
    if not items:
        print(f"[RDS] Instance {instance_id} not found.")
        return None

    inst = items[0]
    info = {
        "instance_id": inst.d_b_instance_id,
        "description": inst.d_b_instance_description,
        "status": inst.d_b_instance_status,
        "engine": inst.engine,
        "engine_version": inst.engine_version,
        "instance_class": inst.d_b_instance_class,
        "storage_gb": inst.d_b_instance_storage,
        "region_id": inst.region_id,
        "zone_id": inst.zone_id_str,
        "creation_time": inst.create_time,
    }
    print("\n=== ApsaraDB RDS Instance ===")
    for k, v in info.items():
        print(f"  {k:20s}: {v}")
    return info


def main():
    access_key_id = os.getenv("ALIBABA_ACCESS_KEY_ID")
    access_key_secret = os.getenv("ALIBABA_ACCESS_KEY_SECRET")
    region_id = os.getenv("ALIBABA_REGION_ID", "ap-southeast-1")

    if not access_key_id or not access_key_secret:
        print("ERROR: Set ALIBABA_ACCESS_KEY_ID and ALIBABA_ACCESS_KEY_SECRET in .env")
        sys.exit(1)

    print("TuneFlow — Alibaba Cloud Deployment Verification")
    print(f"Region: {region_id}")

    try:
        ecs_id = _read_or_env("infra/alibaba/.ecs_instance_id", "ALIBABA_ECS_INSTANCE_ID")
        ecs_info = verify_ecs(region_id, ecs_id, access_key_id, access_key_secret)
    except Exception as e:
        print(f"[ECS] Error: {e}")
        ecs_info = None

    try:
        rds_id = _read_or_env("infra/alibaba/.rds_instance_id", "ALIBABA_RDS_INSTANCE_ID")
        rds_info = verify_rds(region_id, rds_id, access_key_id, access_key_secret)
    except Exception as e:
        print(f"[RDS] Error: {e}")
        rds_info = None

    print("\n=== Summary ===")
    if ecs_info:
        print(f"  ECS: {ecs_info['instance_id']} — {ecs_info['status']} — IP: {ecs_info['public_ip']}")
    if rds_info:
        print(f"  RDS: {rds_info['instance_id']} — {rds_info['status']} — {rds_info['engine']} {rds_info['engine_version']}")

    if ecs_info and rds_info:
        print("\n✓ Alibaba Cloud deployment verified successfully.")
    else:
        print("\n✗ Some resources could not be verified. Check credentials and instance IDs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
