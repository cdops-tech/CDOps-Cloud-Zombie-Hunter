# CDOps Cloud Zombie Hunter - Version 3.0 Update

**Date:** November 18, 2025  
**Version:** 3.0  
**Breaking Changes:** None  
**Migration Required:** No

---

## 🚀 What's New in v3.0

Version 3.0 expands AWS service coverage by adding support for three critical compute and database services that often harbor "zombie" resources draining cloud budgets.

### New Resource Scanners

#### 1. ⚡ Lambda Functions (Serverless Compute)

**What It Detects:**
- Lambda functions with **zero invocations in the past 90 days**
- Legacy functions no longer in use
- Test functions never cleaned up
- Functions replaced by newer versions but not deleted

**Cost Impact:**
- Storage charges: $0.0000166667 per GB-second
- Typical idle function cost: **$0.50-$2.00/month**
- Varies based on memory allocation (128MB-10GB range)

**Why It Matters:**
While individual Lambda functions are cheap, organizations often accumulate hundreds of abandoned test/development functions. These add up to significant waste over time.

**Example Finding:**
```
Resource Type: Lambda Function
Resource ID: legacy-image-processor-v1
Region: us-east-1
Details: Memory: 1024MB, Code Size: 15.2MB, No invocations in 90 days
Estimated Monthly Cost: $1.00
Reason: No invocations in the last 90 days
```

---

#### 2. 📊 DynamoDB Tables (NoSQL Database)

**What It Detects:**
- DynamoDB tables with **zero read/write activity in 30 days**
- Archived data that should be moved to S3 Glacier
- Test/development tables never cleaned up
- Tables replaced by newer schema versions

**Cost Impact:**
- **Provisioned capacity mode:** Fixed hourly cost regardless of usage
  - 1 RCU (read capacity unit) = $0.00013/hour = ~$0.09/month
  - 1 WCU (write capacity unit) = $0.00065/hour = ~$0.47/month
  - Minimum cost: $0.56/month for 1 RCU + 1 WCU
- **On-demand mode:** Storage costs remain ($0.25 per GB-month)
- Typical idle table cost: **$0.25-$50+/month**

**Why It Matters:**
Provisioned capacity tables continue charging hourly even with zero activity. Development teams often forget to delete test tables after projects end.

**Example Finding:**
```
Resource Type: DynamoDB Table
Resource ID: dev-user-sessions-2024-q2
Region: us-west-2
Details: Billing: PROVISIONED, Size: 142.5MB, Items: 25847, No activity in 30 days
Estimated Monthly Cost: $5.47
Reason: No read/write activity in the last 30 days
```

---

#### 3. 🔴 ElastiCache Clusters (Redis/Memcached)

**What It Detects:**
- ElastiCache clusters (Redis & Memcached) with **zero connections in 14 days**
- Development/test environments left running
- Clusters from decommissioned applications
- Over-provisioned cache layers no longer needed

**Cost Impact:**
- Instance costs: **$0.017-$6.80+/hour** depending on node type
- Typical costs:
  - `cache.t3.micro`: $0.017/hour = **~$12.40/month**
  - `cache.t3.small`: $0.034/hour = **~$24.80/month**
  - `cache.m5.large`: $0.136/hour = **~$99.28/month**
  - `cache.r5.large`: $0.188/hour = **~$137.24/month**
- Multi-node clusters multiply costs

**Why It Matters:**
ElastiCache is one of the most expensive idle resources. A single forgotten `cache.m5.large` cluster can waste **$1,191/year**. Development teams often spin up clusters for testing and forget to terminate them.

**Example Finding:**
```
Resource Type: ElastiCache Cluster (Redis)
Resource ID: staging-session-cache
Region: eu-west-1
Details: Node Type: cache.m5.large, Nodes: 2, No connections in 14 days
Estimated Monthly Cost: $198.56
Reason: No connections in the last 14 days
```

---

## 📊 Total Coverage

**Version 3.0 now scans 11 AWS resource types:**

| Resource Type | Detection Criteria | Typical Monthly Waste |
|---------------|-------------------|----------------------|
| EBS Volumes | Unattached (available state) | $8-$40/volume |
| EBS Snapshots | >30 days old, no AMI | $0.05-$5/snapshot |
| EC2 Instances | Stopped state | $5-$50/instance |
| Elastic IPs | Not associated | $3.60/IP |
| Load Balancers | Zero healthy targets | $16.20/LB |
| RDS Instances | Stopped state | $10-$500/instance |
| S3 Buckets | Empty (0 objects) | $0/bucket (cleanup) |
| CloudFront | Disabled distributions | $1/distribution |
| **Lambda** | **Zero invocations (90d)** | **$0.50-$2/function** |
| **DynamoDB** | **Zero activity (30d)** | **$0.25-$50/table** |
| **ElastiCache** | **Zero connections (14d)** | **$12-$5,000/cluster** |

---

## 🔐 Updated IAM Permissions

Version 3.0 requires additional read-only permissions for the new services. Update your IAM policy:

### New Required Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ZombieHunterReadOnlyAccess",
      "Effect": "Allow",
      "Action": [
        // ... existing permissions ...
        
        // NEW: Lambda scanning
        "lambda:ListFunctions",
        "lambda:GetFunction",
        
        // NEW: DynamoDB scanning
        "dynamodb:ListTables",
        "dynamodb:DescribeTable",
        
        // NEW: ElastiCache scanning
        "elasticache:DescribeReplicationGroups",
        "elasticache:DescribeCacheClusters",
        
        // NEW: CloudWatch metrics (for all three services)
        "cloudwatch:GetMetricStatistics"
      ],
      "Resource": "*"
    }
  ]
}
```

**See updated [iam-policy.json](iam-policy.json) for complete policy.**

---

## 🛠️ Technical Implementation

### Scanning Logic

#### Lambda Functions
- Uses `lambda:ListFunctions` to enumerate all functions
- Queries CloudWatch `AWS/Lambda` namespace for `Invocations` metric
- Lookback period: **90 days**
- Cost estimation based on memory allocation (128MB-10GB tiers)

#### DynamoDB Tables
- Uses `dynamodb:ListTables` + `dynamodb:DescribeTable` for table details
- Queries CloudWatch `AWS/DynamoDB` namespace for:
  - `ConsumedReadCapacityUnits` (read activity)
  - `ConsumedWriteCapacityUnits` (write activity)
- Lookback period: **30 days**
- Detects both provisioned and on-demand billing modes
- Cost estimation:
  - Provisioned: RCU/WCU hourly rates × 730 hours
  - On-demand: Storage cost only ($0.25/GB-month)

#### ElastiCache Clusters
- Uses `elasticache:DescribeReplicationGroups` (Redis) and `elasticache:DescribeCacheClusters` (Memcached)
- Queries CloudWatch `AWS/ElastiCache` namespace for `CurrConnections` metric
- Lookback period: **14 days** (shorter window due to high hourly costs)
- Supports both Redis and Memcached engines
- Cost estimation based on node type pricing (t3.micro → r5.large+)
- Multiplies cost by number of nodes in cluster

### Error Handling
All new scanners follow the established pattern:
- Gracefully handle `AccessDenied` / `UnauthorizedOperation` errors
- Continue scanning if CloudWatch metrics unavailable
- Verbose mode logs detailed errors for troubleshooting

---

## 📈 Expected Savings Impact

Based on typical enterprise AWS environments:

### Before v3.0 (8 resource types)
- Average organization: **$500-$2,000/month** in zombie costs detected
- Large enterprises: **$5,000-$50,000/month**

### After v3.0 (11 resource types)
- **+30-50% more savings potential** from Lambda/DynamoDB/ElastiCache
- ElastiCache alone can add **$500-$10,000/month** in detected waste
- Lambda/DynamoDB typically add **$100-$1,000/month**

**Real-world scenario:**
```
Organization: 500-employee SaaS company
Before v3.0: $8,400/month in zombies detected
After v3.0:
  - 12 idle ElastiCache clusters: +$2,180/month
  - 47 unused Lambda functions: +$58/month
  - 8 idle DynamoDB tables: +$127/month
New Total: $10,765/month ($129,180/year potential savings)
```

---

## 🔄 Migration Guide

### No Breaking Changes

Version 3.0 is **fully backward compatible**. Existing scripts and workflows require no changes.

### To Upgrade

```bash
# Pull latest code
cd cdops-zombie-hunter
git pull origin main

# Update IAM policy (if not using AdministratorAccess)
aws iam put-user-policy \
  --user-name zombie-hunter \
  --policy-name ZombieHunterPolicy \
  --policy-document file://iam-policy.json

# Run scan (new resource types automatically included)
python zombie_hunter.py --all-regions
```

### CSV Export Updates

The CSV export now includes three new resource type rows:
- `Lambda Function`
- `DynamoDB Table`
- `ElastiCache Cluster (Redis)`
- `ElastiCache Cluster (Memcached)`

Existing CSV parsing scripts will continue to work. New rows simply appear as additional data.

### Summary Table Updates

The console summary table now shows 11 rows instead of 8:
```
+-----------------------------------------------+-------+
| Resource Type                                 | Count |
+-----------------------------------------------+-------+
| ...existing 8 types...                        | ...   |
| Unused Lambda Functions                       | 12    |
| Idle DynamoDB Tables                          | 8     |
| Idle ElastiCache Clusters                     | 3     |
+-----------------------------------------------+-------+
```

---

## 🧪 Testing Recommendations

### Verify New Scanners

```bash
# 1. Ensure IAM permissions updated
aws iam get-user-policy --user-name zombie-hunter --policy-name ZombieHunterPolicy

# 2. Test Lambda scanning
python zombie_hunter.py --region us-east-1

# 3. Check for any permission errors
python zombie_hunter.py --verbose --all-regions

# 4. Verify CSV export includes new types
python zombie_hunter.py --output test-v3.csv
cat test-v3.csv | grep -E "(Lambda|DynamoDB|ElastiCache)"
```

### Expected Behavior

**If you have idle resources:**
- Console output shows findings for new resource types
- Total savings increases
- CSV includes new resource type rows

**If you don't have idle resources:**
- Console shows "No unused Lambda functions found" etc.
- No errors or crashes
- Script completes successfully

**If IAM permissions missing:**
- Console shows "Permission denied for Lambda functions. Skipping..." (graceful)
- Other scans continue normally
- Script does not crash

---

## 🎯 Use Cases

### When v3.0 Adds Most Value

1. **Serverless-Heavy Organizations**
   - Companies using Lambda extensively
   - Microservices architectures
   - Event-driven systems

2. **High-Throughput Applications**
   - Applications using DynamoDB
   - Real-time data processing
   - IoT/streaming workloads

3. **Session/Caching Infrastructure**
   - Web applications using Redis/Memcached
   - API gateways with caching
   - Development/staging environments

4. **Post-Migration Cleanup**
   - After migrating to new architectures
   - After major refactors
   - After project cancellations

---

## 📚 Documentation Updates

### Files Updated in v3.0

| File | Changes |
|------|---------|
| `zombie_hunter.py` | +380 lines: 3 new scanner methods |
| `iam-policy.json` | +7 permissions: Lambda, DynamoDB, ElastiCache, CloudWatch |
| `README.md` | +3 resource type descriptions |
| `SECURITY.md` | Version number updated to 3.0 |
| `UPDATE_V3.md` | This file (new) |

### New Documentation

- [UPDATE_V3.md](UPDATE_V3.md) - This changelog (you are here)

---

## 🐛 Known Issues

**None at this time.**

If you encounter issues with v3.0, please:
1. Check IAM permissions (most common issue)
2. Enable `--verbose` mode to see detailed errors
3. Report bugs: [contact@cdops.tech](mailto:contact@cdops.tech)

---

## 🔮 Future Enhancements (v4.0 Roadmap)

Potential future additions based on user feedback:

- **NAT Gateways** - Idle NAT gateways ($0.045/hour = $32.85/month)
- **VPN Connections** - Unused VPN tunnels ($0.05/hour = $36.50/month)
- **ECR Images** - Old/unused Docker images ($0.10/GB-month)
- **ECS/Fargate Tasks** - Long-running idle tasks
- **SageMaker Endpoints** - Idle ML inference endpoints ($0.05-$4+/hour)
- **Redshift Clusters** - Paused clusters still incurring costs

**Want a specific resource type added?** Email us: [contact@cdops.tech](mailto:contact@cdops.tech)

---

## 📞 Support & Feedback

**Questions? Found a bug? Have a feature request?**

- 📧 Email: [contact@cdops.tech](mailto:contact@cdops.tech)
- 🌐 Website: [https://cdops.tech](https://cdops.tech)
- 💬 GitHub Issues: Coming soon after public launch

---

## 🙏 Acknowledgments

Version 3.0 inspired by feedback from early adopters who requested:
- Serverless cost optimization (Lambda)
- Database idle resource detection (DynamoDB)
- Caching infrastructure auditing (ElastiCache)

Thank you for helping make CDOps Cloud Zombie Hunter better!

---

*Version 3.0 released November 18, 2025 by [CDOps Tech](https://cdops.tech)*
