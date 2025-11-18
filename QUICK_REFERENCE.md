# Quick Reference Card

## Installation
```bash
pip install -r requirements.txt
```

## Basic Commands
```bash
# Scan default region
python zombie_hunter.py

# Scan specific region
python zombie_hunter.py --region us-west-2

# Scan all regions
python zombie_hunter.py --all-regions

# Verbose output
python zombie_hunter.py --verbose

# Custom output file
python zombie_hunter.py --output my_report.csv
```

## What Gets Scanned

| Resource Type | What's Detected | Typical Cost |
|--------------|-----------------|--------------|
| EBS Volumes | Status = 'available' | $0.08-0.125/GB/mo |
| Snapshots | Age > 30d, no AMI | $0.05/GB/mo |
| EC2 Instances | State = 'stopped' | EBS costs continue |
| Elastic IPs | Allocated but unattached | $3.60/mo each |
| Load Balancers | Zero healthy targets | $16-20/mo each |
| RDS Instances | State = 'stopped' | Storage costs continue |
| S3 Buckets | Zero objects | Minimal (management overhead) |
| CloudFront | Disabled distributions | Minimal (config overhead) |

## AWS Credentials

### Method 1: AWS CLI
```bash
aws configure
```

### Method 2: Environment Variables
```bash
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_DEFAULT_REGION="us-east-1"
```

### Method 3: Credentials File
Edit `~/.aws/credentials`:
```ini
[default]
aws_access_key_id = your-key
aws_secret_access_key = your-secret
```

## Required IAM Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "ec2:Describe*",
      "elasticloadbalancing:Describe*",
      "rds:DescribeDBInstances",
      "s3:ListAllMyBuckets",
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "cloudfront:ListDistributions",
      "sts:GetCallerIdentity"
    ],
    "Resource": "*"
  }]
}
```

See `iam-policy.json` for complete policy.

## Output Files

| File | Description |
|------|-------------|
| `cdops_zombie_report_YYYYMMDD_HHMMSS.csv` | Detailed findings with all resource IDs |

## Common Issues

### "No credentials found"
- Run `aws configure` or set environment variables
- Verify `~/.aws/credentials` exists

### "No region configured"
- Run `aws configure set region us-east-1`
- Or use `--region` flag

### "Permission denied" warnings
- Normal if you lack permissions for some services
- Tool continues scanning other resources
- Update IAM policy if needed

## Get Help

- 📖 Full docs: `README.md`
- 🐛 Found a bug? Open a GitHub issue
- 💬 Questions? contact@cdops.tech
- 🌐 Website: https://cdops.tech

## Quick Start
```bash
./setup.sh
```

This validates your setup and runs dependency installation.
