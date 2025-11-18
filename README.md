# CDOps Cloud Zombie Hunter 🧟‍♂️☁️

<div align="center">

**A safe, read-only tool to detect wasted cloud spend in AWS**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![boto3](https://img.shields.io/badge/AWS-boto3-orange.svg)](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
[![Security](https://img.shields.io/badge/security-audited-green.svg)](SECURITY.md)

*By [CDOps Tech](https://cdops.tech) - Your trusted DevSecOps partner*

</div>

---

## 🎯 What is This?

**CDOps Cloud Zombie Hunter** is an open-source command-line utility that scans your AWS environment for unused resources—what we call "zombies"—that are quietly draining your budget. These include:

- 🗄️ **Unattached EBS Volumes** - Storage volumes not connected to any instance
- 📸 **Obsolete EBS Snapshots** - Snapshots older than 30 days not linked to any AMI
- 💤 **Idle EC2 Instances** - Stopped instances still incurring EBS storage costs
- 🌐 **Unassociated Elastic IPs** - Allocated IPs not attached to any resource
- ⚖️ **Unused Load Balancers** - ALBs/NLBs with zero healthy targets
- 🗃️ **Idle RDS Instances** - Stopped databases still incurring storage costs
- 🪣 **Empty S3 Buckets** - Completely empty buckets indicating abandoned projects
- 🌍 **Unused CloudFront Distributions** - Disabled distributions still in configuration

### 🔒 Safety First

This tool is **100% read-only**. It will:
- ✅ **NEVER** modify or delete any resources
- ✅ **NEVER** make changes to your infrastructure
- ✅ Only use AWS `Describe*` APIs to gather information

You can review the source code with confidence—it's heavily commented and transparent.

**🔒 Security:** This tool has been audited for security vulnerabilities. See [SECURITY.md](SECURITY.md) for details.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- AWS credentials configured (see [AWS Credentials Setup](#aws-credentials-setup))
- AWS IAM permissions for read-only access (see [IAM Policy](#iam-policy))

### Installation

```bash
# Clone the repository
git clone https://github.com/cdops-tech/cdops-zombie-hunter.git
cd cdops-zombie-hunter

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

```bash
# Activate virtual environment (if using venv)
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Scan your default AWS region
python zombie_hunter.py

# Scan a specific region
python zombie_hunter.py --region us-west-2

# Scan ALL regions (comprehensive audit)
python zombie_hunter.py --all-regions

# Enable verbose output
python zombie_hunter.py --verbose

# Save report with custom filename
python zombie_hunter.py --output my_audit_2024.csv
```

---

## 📋 AWS Credentials Setup

The tool uses the standard AWS credentials chain. Configure credentials using **one** of these methods:

### Option 1: AWS CLI (Recommended)
```bash
aws configure
```

### Option 2: Environment Variables
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

### Option 3: IAM Role
If running on an EC2 instance, ECS task, or Lambda function, attach an IAM role with the required permissions.

### Option 4: AWS Credentials File
Create or edit `~/.aws/credentials`:
```ini
[default]
aws_access_key_id = your-access-key
aws_secret_access_key = your-secret-key
```

And `~/.aws/config`:
```ini
[default]
region = us-east-1
```

---

## 🔐 IAM Policy

To run this tool safely, create a dedicated IAM user or role with **read-only** permissions. Here's the exact policy you need:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeVolumes",
        "ec2:DescribeSnapshots",
        "ec2:DescribeInstances",
        "ec2:DescribeAddresses",
        "ec2:DescribeImages",
        "ec2:DescribeRegions",
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetHealth",
        "rds:DescribeDBInstances",
        "s3:ListAllMyBuckets",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "cloudfront:ListDistributions",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

### How to Apply This Policy

#### Method 1: AWS Console
1. Go to **IAM** → **Policies** → **Create Policy**
2. Choose **JSON** tab and paste the policy above
3. Name it `ZombieHunterReadOnly`
4. Attach to your IAM user or role

#### Method 2: AWS CLI
```bash
# Save the policy to a file: zombie-hunter-policy.json
aws iam create-policy \
  --policy-name ZombieHunterReadOnly \
  --policy-document file://zombie-hunter-policy.json

# Attach to an existing user
aws iam attach-user-policy \
  --user-name your-username \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/ZombieHunterReadOnly
```

A complete policy file is included in this repository: [`iam-policy.json`](iam-policy.json)

---

## 📊 Sample Output

### Console Output
```
================================================================================
CDOps Cloud Zombie Hunter
Scanning for unused AWS resources...
================================================================================

>>> Scanning region: us-east-1

[INFO] Scanning for unattached EBS volumes in us-east-1...
[WARNING] Found 3 unattached EBS volumes in us-east-1
[INFO] Scanning for obsolete snapshots in us-east-1...
[SUCCESS] No obsolete snapshots found in us-east-1
[INFO] Scanning for idle EC2 instances in us-east-1...
[WARNING] Found 2 idle EC2 instances in us-east-1
[INFO] Scanning for unassociated Elastic IPs in us-east-1...
[WARNING] Found 1 unassociated Elastic IPs in us-east-1
[INFO] Scanning for unused load balancers in us-east-1...
[SUCCESS] No unused load balancers found in us-east-1

================================================================================
SCAN SUMMARY
================================================================================

+------------------------------------------+-------+
| Resource Type                            | Count |
+==========================================+=======+
| Unattached EBS Volumes                   |     3 |
+------------------------------------------+-------+
| Obsolete Snapshots (>30 days, no AMI)    |     0 |
+------------------------------------------+-------+
| Idle EC2 Instances (stopped)             |     2 |
+------------------------------------------+-------+
| Unassociated Elastic IPs                 |     1 |
+------------------------------------------+-------+
| Unused Load Balancers                    |     0 |
+------------------------------------------+-------+
| Idle RDS Instances (stopped)             |     1 |
+------------------------------------------+-------+
| Empty S3 Buckets                         |     5 |
+------------------------------------------+-------+
| Unused CloudFront Distributions          |     0 |
+------------------------------------------+-------+

⚠️  Total Zombie Resources Found: 12
💰 Estimated Monthly Savings: $127.45
💵 Estimated Annual Savings: $1,529.40
These resources may be costing you money unnecessarily.

[SUCCESS] Report exported to: cdops_zombie_report_20241118_143022.csv
📄 Full report saved: cdops_zombie_report_20241118_143022.csv
💰 Total estimated monthly savings: $127.45

================================================================================
✅ Scan Complete!

If you need help safely analyzing or cleaning up these resources,
contact the CDOps Tech SRE Team:

📧 Email: contact@cdops.tech
🌐 Web: https://cdops.tech
================================================================================
```

### CSV Export
The tool automatically generates a detailed CSV report with all findings and a summary:

| resource_type | resource_id | region | size_gb | estimated_monthly_cost | reason |
|---------------|-------------|--------|---------|------------------------|--------|
| EBS Volume | vol-0abc123def456 | us-east-1 | 100 | $8.00 | Unattached (available state) |
| EC2 Instance | i-0xyz789abc123 | us-east-1 | 50 | $5.00 | Instance stopped (EBS volumes still incurring costs) |
| Elastic IP | eipalloc-0abc123 | us-east-1 | - | $3.60 | Allocated but not associated |
| ... | ... | ... | ... | ... | ... |
| ***** SUMMARY ***** | 12 total zombie resources | | | **$127.45** | **Estimated Monthly Savings: $127.45 \| Annual: $1,529.40** |

---

## 🛡️ What Gets Scanned?

### 1. **Unattached EBS Volumes**
- **Criteria**: Volume state is `available` (not attached to any EC2 instance)
- **Why it matters**: You pay for EBS storage even when volumes are unattached
- **Cost impact**: $0.08-$0.125 per GB/month depending on volume type

### 2. **Obsolete EBS Snapshots**
- **Criteria**: 
  - Snapshot is older than 30 days
  - NOT associated with any active AMI
- **Why it matters**: Old snapshots accumulate quickly and cost adds up
- **Cost impact**: ~$0.05 per GB/month

### 3. **Idle EC2 Instances**
- **Criteria**: Instance is in `stopped` state
- **Why it matters**: Stopped instances still incur EBS storage costs
- **Cost impact**: EBS volume charges continue (~$0.10/GB/month)

### 4. **Unassociated Elastic IPs**
- **Criteria**: EIP is allocated but not attached to any instance or network interface
- **Why it matters**: AWS charges for unattached EIPs
- **Cost impact**: ~$0.005/hour = ~$3.60/month per EIP

### 5. **Unused Load Balancers**
- **Criteria**: ALB/NLB has zero healthy registered targets
- **Why it matters**: Load balancers cost money even with no traffic
- **Cost impact**: ~$16-$20/month per load balancer

### 6. **Idle RDS Instances**
- **Criteria**: RDS database instance is in `stopped` state
- **Why it matters**: Stopped RDS instances still incur storage costs
- **Cost impact**: Storage charges continue (~$0.115/GB/month)

### 7. **Empty S3 Buckets**
- **Criteria**: S3 bucket has zero objects
- **Why it matters**: Empty buckets may indicate abandoned projects or forgotten infrastructure
- **Cost impact**: Minimal storage cost but management overhead

### 8. **Unused CloudFront Distributions**
- **Criteria**: CloudFront distribution is disabled
- **Why it matters**: Disabled distributions still exist in configuration and may cause confusion
- **Cost impact**: Minimal but indicates unused infrastructure

---

## 🎨 Features

- ✅ **Color-Coded Output** - Easy-to-read console output with status indicators
- ✅ **CSV Export** - Detailed report for spreadsheet analysis with savings summary
- ✅ **Multi-Region Support** - Scan specific regions or all regions at once
- ✅ **Cost Estimates** - Approximate monthly costs for each zombie resource
- ✅ **Total Savings Calculator** - Automatic calculation of monthly and annual savings
- ✅ **Graceful Error Handling** - Skips resources you don't have permission to access
- ✅ **Verbose Mode** - Detailed logging for debugging
- ✅ **Zero Dependencies** - Only uses boto3, tabulate, and colorama
- ✅ **Production-Ready** - Proper exception handling and logging

---

## 🔧 Advanced Usage

### Scanning Multiple Regions
```bash
# Scan all US regions
python zombie_hunter.py --all-regions

# Or use AWS CLI to get specific regions and loop
for region in us-east-1 us-west-2 eu-west-1; do
  python zombie_hunter.py --region $region
done
```

### Automation with Cron
Run weekly scans automatically:

```bash
# Add to crontab (run every Monday at 9 AM)
0 9 * * 1 cd /path/to/cdops-zombie-hunter && python zombie_hunter.py --all-regions --output /reports/weekly_scan.csv
```

### Integration with CI/CD
Use in your pipeline to monitor cloud hygiene:

```yaml
# GitHub Actions example
- name: Run Zombie Hunter
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
  run: |
    pip install -r requirements.txt
    python zombie_hunter.py --all-regions
```

---

## 🤝 Need Help?

This tool identifies the problem—but what about the solution?

If you've discovered zombie resources and need expert help:
- 🔍 Analyzing which resources are truly safe to delete
- 🛠️ Setting up automated cleanup processes
- 📊 Implementing cost optimization strategies
- 🏗️ Architecting more efficient cloud infrastructure

**Contact the CDOps Tech SRE Team:**
- 📧 Email: [contact@cdops.tech](mailto:contact@cdops.tech)
- 🌐 Website: [https://cdops.tech](https://cdops.tech)
- 💼 We specialize in DevSecOps, SRE, and cloud cost optimization

---

## 🔒 Security

### Security Audit Status: ✅ PASSED

This tool has undergone comprehensive security review:
- ✅ No shell injection vulnerabilities
- ✅ No hardcoded credentials
- ✅ Read-only AWS operations only
- ✅ Secure credential handling
- ✅ Minimal, vetted dependencies

**For detailed security information, see [SECURITY.md](SECURITY.md)**

### Reporting Security Issues

If you discover a security vulnerability, please email **contact@cdops.tech** with:
- Description of the issue
- Steps to reproduce
- Potential impact

**DO NOT** open public GitHub issues for security vulnerabilities.

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Contributing

Contributions are welcome! This is an open-source project designed to help the community.

To contribute:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 🐛 Found a Bug?

Please open an issue on GitHub with:
- Description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS

---

## 🗺️ Roadmap

Future enhancements we're considering:
- [ ] Support for more AWS services (Lambda, DynamoDB, ElastiCache)
- [ ] CloudWatch metrics analysis for truly idle resources
- [ ] Azure and GCP support
- [ ] Interactive cleanup mode (with confirmations)
- [ ] Cost trend analysis over time
- [ ] Slack/Email notifications
- [ ] Web dashboard

---

## ⭐ Show Your Support

If this tool saved you money or time, please:
- ⭐ Star this repository
- 🐦 Share it on social media
- 📝 Write about your experience

---

<div align="center">

**Built with ❤️ by [CDOps Tech](https://cdops.tech)**

*Helping engineering teams build secure, reliable, and cost-efficient systems*

</div>
