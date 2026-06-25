#!/usr/bin/env bash
# Alibaba Cloud deployment script for TuneFlow
# Uses aliyun CLI. Requires: aliyun CLI installed and configured with your credentials.
# Usage: ./deploy.sh [region]

set -euo pipefail

REGION=${1:-ap-southeast-1}
ECS_INSTANCE_TYPE="ecs.c6.xlarge"      # 4 vCPU, 8 GB RAM
IMAGE_ID="ubuntu_22_04_x64_20G_alibase_20240131.vhd"  # Update for your region
SECURITY_GROUP_NAME="tuneflow-sg"
VPC_NAME="tuneflow-vpc"
VSWITCH_CIDR="172.16.0.0/24"
VPC_CIDR="172.16.0.0/16"
RDS_ENGINE="PostgreSQL"
RDS_ENGINE_VERSION="15.0"
RDS_CLASS="pg.n2.small.2c"             # 2 vCPU, 4 GB
RDS_STORAGE="50"                       # GB
TAG="tuneflow"

echo "=== TuneFlow Alibaba Cloud Deployment ==="
echo "Region: $REGION"

# ── VPC ──────────────────────────────────────────────────────────────────────
echo "[1/7] Creating VPC..."
VPC_ID=$(aliyun vpc CreateVpc \
  --RegionId "$REGION" \
  --CidrBlock "$VPC_CIDR" \
  --VpcName "$VPC_NAME" \
  --Description "TuneFlow VPC" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['VpcId'])")
echo "VPC: $VPC_ID"

VSWITCH_ID=$(aliyun vpc CreateVSwitch \
  --RegionId "$REGION" \
  --VpcId "$VPC_ID" \
  --CidrBlock "$VSWITCH_CIDR" \
  --ZoneId "${REGION}a" \
  --VSwitchName "tuneflow-vsw" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['VSwitchId'])")
echo "VSwitch: $VSWITCH_ID"

# ── Security Group ────────────────────────────────────────────────────────────
echo "[2/7] Creating Security Group..."
SG_ID=$(aliyun ecs CreateSecurityGroup \
  --RegionId "$REGION" \
  --VpcId "$VPC_ID" \
  --SecurityGroupName "$SECURITY_GROUP_NAME" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['SecurityGroupId'])")
echo "Security Group: $SG_ID"

# Allow SSH, HTTP (service + orchestrator + dashboard)
for PORT in 22 8000 8080 3000; do
  aliyun ecs AuthorizeSecurityGroup \
    --RegionId "$REGION" \
    --SecurityGroupId "$SG_ID" \
    --IpProtocol tcp \
    --PortRange "${PORT}/${PORT}" \
    --SourceCidrIp "0.0.0.0/0" \
    --Policy accept > /dev/null
done
echo "Security group rules added."

# ── SSH Key Pair ───────────────────────────────────────────────────────────────
# Use key-based auth instead of a hardcoded password — this script lives in a
# public repo (hackathon submission requirement), so a literal password here
# would hand root access to anyone who reads the source.
echo "[3/7] Creating SSH key pair..."
KEY_PAIR_NAME="tuneflow-key-$(date +%s)"
KEY_FILE="infra/alibaba/${KEY_PAIR_NAME}.pem"
aliyun ecs CreateKeyPair \
  --RegionId "$REGION" \
  --KeyPairName "$KEY_PAIR_NAME" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['PrivateKeyBody'])" > "$KEY_FILE"
chmod 600 "$KEY_FILE"
echo "Key pair: $KEY_PAIR_NAME (private key saved to $KEY_FILE — gitignored, do not commit)"

# ── ECS Instance ──────────────────────────────────────────────────────────────
echo "[4/7] Creating ECS instance..."
ECS_ID=$(aliyun ecs RunInstances \
  --RegionId "$REGION" \
  --ImageId "$IMAGE_ID" \
  --InstanceType "$ECS_INSTANCE_TYPE" \
  --SecurityGroupId "$SG_ID" \
  --VSwitchId "$VSWITCH_ID" \
  --InstanceName "tuneflow-server" \
  --KeyPairName "$KEY_PAIR_NAME" \
  --SystemDisk.Category "cloud_essd" \
  --SystemDisk.Size "40" \
  --InternetMaxBandwidthOut "100" \
  --InternetChargeType "PayByTraffic" \
  --Amount 1 \
  | python3 -c "import sys,json; data=json.load(sys.stdin); print(data['InstanceIdSets']['InstanceIdSet'][0])")
echo "ECS Instance: $ECS_ID"

# Save instance ID for verify script
echo "$ECS_ID" > infra/alibaba/.ecs_instance_id

# ── ApsaraDB for PostgreSQL ───────────────────────────────────────────────────
echo "[5/7] Creating ApsaraDB RDS (PostgreSQL 15)..."
RDS_ID=$(aliyun rds CreateDBInstance \
  --RegionId "$REGION" \
  --Engine "$RDS_ENGINE" \
  --EngineVersion "$RDS_ENGINE_VERSION" \
  --DBInstanceClass "$RDS_CLASS" \
  --DBInstanceStorage "$RDS_STORAGE" \
  --DBInstanceStorageType "cloud_essd" \
  --DBInstanceNetType "Intranet" \
  --VpcId "$VPC_ID" \
  --VSwitchId "$VSWITCH_ID" \
  --SecurityIPList "172.16.0.0/16" \
  --PayType "Postpaid" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['DBInstanceId'])")
echo "ApsaraDB RDS Instance: $RDS_ID"

# Save for verify script
echo "$RDS_ID" > infra/alibaba/.rds_instance_id

echo "[6/7] Waiting for instances to start (this takes ~2-3 minutes)..."
sleep 120

# Get ECS public IP
ECS_IP=$(aliyun ecs DescribeInstances \
  --RegionId "$REGION" \
  --InstanceIds "[\"$ECS_ID\"]" \
  | python3 -c "import sys,json; inst=json.load(sys.stdin)['Instances']['Instance'][0]; print(inst['PublicIpAddress']['IpAddress'][0] if inst['PublicIpAddress']['IpAddress'] else 'pending')")
echo "ECS Public IP: $ECS_IP"

echo ""
echo "=== Deployment Summary ==="
echo "VPC ID:         $VPC_ID"
echo "ECS Instance:   $ECS_ID ($ECS_IP)"
echo "RDS Instance:   $RDS_ID"
echo "SSH Key:        $KEY_FILE"
echo ""
echo "[7/7] Next steps:"
echo "  1. SSH into ECS: ssh -i $KEY_FILE root@$ECS_IP"
echo "  2. Install Docker: curl -fsSL https://get.docker.com | sh"
echo "  3. Clone repo and copy .env with QWEN_API_KEY"
echo "  4. Update .env: SERVICE_DB_URL to point to RDS endpoint"
echo "  5. docker-compose up -d (run seed.py once)"
echo "  6. Run verify_deployment.py to confirm resources"
echo ""
echo "NOTE: $KEY_FILE is your only copy of the private key and is gitignored —"
echo "      back it up somewhere safe before this directory is cleaned up."
