# AWS EC2 Create Instance

Script to launch an EC2 instance

Links: [[aws-cli-sso-config]]
Tags: #aws #script #ec2

## Prerequisites

- AWS CLI configured with SSO (see [[aws-cli-sso-config]])

## Variables

Edit and run this block first. It writes the variables to a gitignored file in `notes/scripts/env/` so all other blocks can source them.

```bash
mkdir -p "@vault_path/notes/scripts/env"
cat > "@vault_path/notes/scripts/env/aws-ec2-create-instance.env" << 'EOF'
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

export AWS_PROFILE="<aws-profile>"
export REGION="<aws-region>"
export INSTANCE_TYPE="<instance-type>"
export KEY_NAME="<key-pair-name>"
export INSTANCE_NAME="<instance-name>"
export VPC_ID="<vpc-id>"
export SUBNET_ID="<subnet-id>"
export SG_NAME="<security-group-name>"
EOF

echo "Variables saved to notes/scripts/env/aws-ec2-create-instance.env"
```

## AWS Login

Before running the scripts you need to authenticate to AWS

```bash
source "@vault_path/notes/scripts/env/aws-ec2-create-instance.env"

aws sso login --sso-session <sso-session>
```

## Create Instance

```bash
source "@vault_path/notes/scripts/env/aws-ec2-create-instance.env"

# --- Create Key Pair ---
aws ec2 create-key-pair \
  --region "$REGION" \
  --key-name "$KEY_NAME" \
  --query "KeyMaterial" \
  --output text > ~/.ssh/"$KEY_NAME.pem"
chmod 400 ~/.ssh/"$KEY_NAME.pem"
echo "Key pair created and saved to: ~/.ssh/$KEY_NAME.pem"

# --- Create Security Group ---
SG_ID=$(aws ec2 create-security-group \
  --region "$REGION" \
  --group-name "$SG_NAME" \
  --description "Allow EC2 to ECS service connectivity" \
  --vpc-id "$VPC_ID" \
  --query "GroupId" \
  --output text)
echo "Security Group: $SG_ID"

aws ec2 authorize-security-group-ingress \
  --region "$REGION" \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr "0.0.0.0/0"

# --- Get latest Amazon Linux 2023 AMI ---
AMI_ID=$(aws ec2 describe-images \
  --region "$REGION" \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023*-x86_64" "Name=state,Values=available" \
  --query "Images | sort_by(@, &CreationDate) | [-1].ImageId" \
  --output text)
echo "AMI: $AMI_ID"

# --- Launch Instance ---
INSTANCE_ID=$(aws ec2 run-instances \
  --region "$REGION" \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --key-name "$KEY_NAME" \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$SG_ID" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
  --query "Instances[0].InstanceId" \
  --output text)
echo "Instance launched: $INSTANCE_ID"

# --- Wait and get private IP ---
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"
PRIVATE_IP=$(aws ec2 describe-instances \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].PrivateIpAddress" \
  --output text)
echo "Instance ready — Private IP: $PRIVATE_IP"
```

## Connect via SSH

> [!NOTE]
> This section should be run from the terminal, don't execute the code snippet

```bash
source "@vault_path/notes/scripts/env/aws-ec2-create-instance.env"

PRIVATE_IP=$(aws ec2 describe-instances \
  --region "$REGION" \
  --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].PrivateIpAddress" \
  --output text)

ssh -i ~/.ssh/"$KEY_NAME.pem" ec2-user@"$PRIVATE_IP"
```

## Cleanup

Terminate the instance, delete the security group and the key-pair.

```bash
source "@vault_path/notes/scripts/env/aws-ec2-create-instance.env"

# --- Terminate Instance ---
INSTANCE_ID=$(aws ec2 describe-instances \
  --region "$REGION" \
  --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=running,stopped" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text)
echo "Terminating instance: $INSTANCE_ID"
aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-terminated --region "$REGION" --instance-ids "$INSTANCE_ID"
echo "Instance terminated."

# --- Delete Security Group ---
SG_ID=$(aws ec2 describe-security-groups \
  --region "$REGION" \
  --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query "SecurityGroups[0].GroupId" \
  --output text)
echo "Deleting security group: $SG_ID"
aws ec2 delete-security-group --region "$REGION" --group-id "$SG_ID"
echo "Security group deleted."

# --- Delete Key Pair ---
aws ec2 delete-key-pair --region "$REGION" --key-name "$KEY_NAME"
rm -f ~/.ssh/"$KEY_NAME.pem"
echo "Key pair deleted."

# --- Remove the run's env file ---
rm -f "@vault_path/notes/scripts/env/aws-ec2-create-instance.env"

echo "Cleanup complete."
```

## References

- [AWS EC2 Run Instances CLI](https://docs.aws.amazon.com/cli/latest/reference/ec2/run-instances.html)
