# GCP Provider Setup Guide

## Overview

The GCP provider for CDOps Cloud Zombie Hunter scans your Google Cloud Platform projects for zombie resources that are generating unnecessary costs.

## Supported GCP Resources

The GCP provider scans for these zombie resources:

1. **Unattached Persistent Disks** - Disks not attached to any Compute Engine instance
2. **Obsolete Snapshots** - Snapshots older than 30 days
3. **Stopped Compute Instances** - VMs in TERMINATED/STOPPED state (disks still cost money)
4. **Unattached Static IPs** - Reserved IP addresses not attached to any resource
5. **Unused Load Balancers** - Forwarding rules with no backend services
6. **Stopped Cloud SQL Instances** - SQL instances in stopped state (coming soon)
7. **Empty Storage Buckets** - Cloud Storage buckets with no objects
8. **Unused Cloud Functions** - Functions with no recent invocations (coming soon)

---

## Prerequisites

### 1. Google Cloud SDK (gcloud CLI)

Install the gcloud CLI:

```bash
# macOS
brew install --cask google-cloud-sdk

# Windows
# Download from https://cloud.google.com/sdk/docs/install

# Linux (Debian/Ubuntu)
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
sudo apt-get update && sudo apt-get install google-cloud-sdk
```

### 2. Python Dependencies

The GCP provider requires additional Python packages:

```bash
pip install google-cloud-compute google-cloud-storage \
            google-cloud-monitoring google-auth
```

Or simply:

```bash
pip install -r requirements.txt
```

---

## Authentication Methods

### Option 1: gcloud CLI (Recommended for Development)

The easiest method for local development:

```bash
# Login to GCP
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Verify your setup
gcloud auth application-default print-access-token
```

Once logged in, the tool will automatically use your gcloud credentials.

### Option 2: Service Account (Recommended for Production/CI/CD)

Create a service account for automated scanning:

```bash
# Set project
PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Create service account
gcloud iam service-accounts create cdops-zombie-hunter \
    --display-name="CDOps Zombie Hunter" \
    --description="Read-only scanner for unused cloud resources"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:cdops-zombie-hunter@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/viewer"

# Create and download key
gcloud iam service-accounts keys create ~/cdops-zombie-hunter-key.json \
    --iam-account="cdops-zombie-hunter@${PROJECT_ID}.iam.gserviceaccount.com"
```

Set environment variable:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=~/cdops-zombie-hunter-key.json
```

### Option 3: Workload Identity (Recommended for GKE)

If running on Google Kubernetes Engine, use Workload Identity:

```bash
# Enable Workload Identity on your cluster
gcloud container clusters update CLUSTER_NAME \
    --workload-pool=PROJECT_ID.svc.id.goog

# Create Kubernetes service account
kubectl create serviceaccount cdops-zombie-hunter

# Bind to GCP service account
gcloud iam service-accounts add-iam-policy-binding \
    cdops-zombie-hunter@PROJECT_ID.iam.gserviceaccount.com \
    --role roles/iam.workloadIdentityUser \
    --member "serviceAccount:PROJECT_ID.svc.id.goog[NAMESPACE/cdops-zombie-hunter]"
```

The tool will automatically use the Workload Identity when running in GKE.

---

## IAM Permissions

The GCP provider requires **read-only** permissions. Use either the built-in Viewer role or create a custom role with minimal permissions.

### Using Built-in Viewer Role (Simplest)

```bash
# Assign Viewer role to a user
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="user:user@example.com" \
    --role="roles/viewer"

# Or assign to a service account
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:cdops-zombie-hunter@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/viewer"
```

### Creating a Custom Role (Most Secure)

Create a custom role with minimal permissions:

```bash
gcloud iam roles create CDOpsZombieHunter \
    --project=PROJECT_ID \
    --file=gcp-iam-role.json
```

The `gcp-iam-role.json` file is included in this repository with the exact permissions needed.

### Required Permissions

The tool needs these read permissions:

**Compute Engine:**
- `compute.disks.list`
- `compute.disks.get`
- `compute.snapshots.list`
- `compute.instances.list`
- `compute.instances.get`
- `compute.addresses.list`
- `compute.forwardingRules.list`
- `compute.backendServices.list`
- `compute.regions.list`
- `compute.zones.list`

**Cloud Storage:**
- `storage.buckets.list`
- `storage.buckets.get`
- `storage.objects.list`

**Cloud Functions:**
- `cloudfunctions.functions.list`
- `cloudfunctions.functions.get`

**Monitoring:**
- `monitoring.timeSeries.list`

**Resource Manager:**
- `resourcemanager.projects.get`

---

## Usage

### Scan a Specific GCP Region

```bash
python zombie_hunter.py --cloud gcp --region us-central1
```

### Scan All GCP Regions

```bash
python zombie_hunter.py --cloud gcp --all-regions
```

### Export Results to CSV

```bash
python zombie_hunter.py --cloud gcp --region us-west1 --output gcp_report.csv
```

---

## GCP Region Names

Common GCP region names:

| Region Name | Location |
|-------------|----------|
| `us-central1` | Iowa, USA |
| `us-east1` | South Carolina, USA |
| `us-east4` | Northern Virginia, USA |
| `us-west1` | Oregon, USA |
| `us-west2` | Los Angeles, USA |
| `us-west3` | Salt Lake City, USA |
| `us-west4` | Las Vegas, USA |
| `northamerica-northeast1` | Montreal, Canada |
| `southamerica-east1` | São Paulo, Brazil |
| `europe-west1` | Belgium |
| `europe-west2` | London, UK |
| `europe-west3` | Frankfurt, Germany |
| `europe-west4` | Netherlands |
| `europe-west6` | Zurich, Switzerland |
| `europe-north1` | Finland |
| `asia-east1` | Taiwan |
| `asia-east2` | Hong Kong |
| `asia-northeast1` | Tokyo, Japan |
| `asia-northeast2` | Osaka, Japan |
| `asia-northeast3` | Seoul, South Korea |
| `asia-south1` | Mumbai, India |
| `asia-southeast1` | Singapore |
| `australia-southeast1` | Sydney, Australia |

Get all available regions:

```bash
gcloud compute regions list
```

---

## Sample Output

```
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║          🔍  CDOps Cloud Zombie Hunter v4.0                      ║
║                                                                   ║
║          Hunt Down Cost Zombies Across Multiple Clouds            ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝

🔧 Initializing GCP Provider...

✅ GCP credentials validated
Project ID: my-production-project

📍 Scanning region: us-central1

================================================================================
CDOps Cloud Zombie Hunter - GCP
Scanning for unused GCP resources...
================================================================================

>>> Scanning region: us-central1

[INFO] Scanning for unattached persistent disks in us-central1...
[WARNING] Found 3 unattached persistent disks in us-central1
[INFO] Scanning for obsolete snapshots in us-central1...
[SUCCESS] No obsolete snapshots found in us-central1
[INFO] Scanning for stopped Compute instances in us-central1...
[WARNING] Found 2 stopped Compute instances in us-central1
[INFO] Scanning for unattached static IPs in us-central1...
[WARNING] Found 1 unattached static IPs in us-central1

================================================================================
SCAN SUMMARY
================================================================================

+------------------------------------------+-------+
| Resource Type                            | Count |
+==========================================+=======+
| Unattached Persistent Disks              |     3 |
+------------------------------------------+-------+
| Obsolete Snapshots (>30 days)            |     0 |
+------------------------------------------+-------+
| Stopped Compute Instances                |     2 |
+------------------------------------------+-------+
| Unattached Static IPs                    |     1 |
+------------------------------------------+-------+
| Unused Load Balancers                    |     0 |
+------------------------------------------+-------+
| Stopped Cloud SQL Instances              |     0 |
+------------------------------------------+-------+
| Empty Storage Buckets                    |     2 |
+------------------------------------------+-------+
| Unused Cloud Functions                   |     0 |
+------------------------------------------+-------+

⚠️  Total Zombie Resources Found: 8
💰 Estimated Monthly Savings: $52.80
💵 Estimated Annual Savings: $633.60
```

---

## Troubleshooting

### Error: "No GCP project ID found"

**Solution:** Set your project with gcloud:

```bash
gcloud config set project YOUR_PROJECT_ID
```

### Error: "Failed to import GCP SDK"

**Solution:** Install GCP dependencies:

```bash
pip install -r requirements.txt
```

### Error: "Permission denied"

**Solution:** Ensure you have at least Viewer role on the project:

```bash
gcloud projects get-iam-policy PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:user:YOUR_EMAIL"
```

### Scanning Multiple Projects

The tool currently scans one project at a time. To scan multiple projects:

1. Use a loop in your shell:
```bash
for project in project-1 project-2 project-3; do
  gcloud config set project $project
  python zombie_hunter.py --cloud gcp --all-regions --output "${project}_report.csv"
done
```

2. Or modify `providers/gcp.py` to iterate through multiple projects

---

## Cost Estimates

GCP cost estimates used by the tool:

| Resource Type | Estimated Cost |
|---------------|----------------|
| Persistent Disk (Standard) | $0.04/GB/month |
| Persistent Disk (SSD) | $0.17/GB/month |
| Snapshot | $0.026/GB/month |
| Static IP (unattached) | $7.20/month |
| Load Balancer | $18/month |
| Cloud Storage (Standard) | Minimal, management overhead |

**Note:** Costs vary by region and are subject to GCP pricing changes.

---

## Automation

### Cloud Build Pipeline

```yaml
steps:
  - name: 'python:3.9'
    entrypoint: 'bash'
    args:
      - '-c'
      - |
        pip install -r requirements.txt
        python zombie_hunter.py --cloud gcp --all-regions --output gcp_zombies.csv
    env:
      - 'GOOGLE_APPLICATION_CREDENTIALS=/workspace/service-account-key.json'

artifacts:
  objects:
    location: 'gs://my-bucket/zombie-reports'
    paths: ['gcp_zombies.csv']
```

### GitHub Actions

```yaml
name: GCP Zombie Scan

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM
  workflow_dispatch:

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Authenticate to GCP
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - name: Run Zombie Hunter
        run: python zombie_hunter.py --cloud gcp --all-regions
      
      - name: Upload Report
        uses: actions/upload-artifact@v3
        with:
          name: zombie-report
          path: '*.csv'
```

---

## Security Best Practices

1. **Use Service Accounts for Automation** - Never use personal credentials
2. **Principle of Least Privilege** - Use custom IAM roles with minimal permissions
3. **Rotate Keys Regularly** - Change service account keys periodically
4. **Use Workload Identity** - When running on GKE
5. **Audit Access** - Monitor who runs the scanner and when
6. **Encrypt Reports** - CSV reports contain resource information

---

## Known Limitations

### Current Implementation

- **Cloud SQL Scanning:** Requires SQL Admin API (coming soon)
- **Cloud Functions Monitoring:** Requires additional Monitoring API setup (coming soon)
- **Single Project:** Currently scans one project per run
- **Regional Resources Only:** Some global resources not yet scanned

### Future Enhancements (v5.1)

- [ ] Cloud SQL instance scanning
- [ ] Cloud Functions invocation metrics
- [ ] Multi-project scanning
- [ ] Cloud CDN unused distributions
- [ ] BigQuery unused datasets
- [ ] Pub/Sub unused topics

---

## Need Help?

For GCP-specific assistance or professional cloud optimization services:

📧 **Email:** contact@cdops.tech  
🌐 **Website:** https://cdops.tech  
💼 **Services:** DevSecOps, SRE, Multi-Cloud Cost Optimization

---

## Contributing

Found a bug or want to add GCP resource types? See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## License

MIT License - See [LICENSE](LICENSE) file for details
