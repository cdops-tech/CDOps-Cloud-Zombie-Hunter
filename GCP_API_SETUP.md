# GCP API Setup Guide

## Required APIs for CDOps Zombie Hunter

To scan all 11 resource types in GCP, you need to enable the following APIs in your project:

### Core APIs (Required for Most Scans)

#### 1. **Compute Engine API**
- **Required for**: Persistent Disks, Snapshots, Compute Instances, Static IPs, Load Balancers, Cloud CDN
- **Enable via Console**: https://console.cloud.google.com/apis/library/compute.googleapis.com
- **Enable via CLI**:
  ```bash
  gcloud services enable compute.googleapis.com --project=YOUR_PROJECT_ID
  ```

#### 2. **Cloud Storage API**
- **Required for**: Storage Buckets
- **Enable via Console**: https://console.cloud.google.com/apis/library/storage.googleapis.com
- **Enable via CLI**:
  ```bash
  gcloud services enable storage.googleapis.com --project=YOUR_PROJECT_ID
  ```

### Optional APIs (For Enhanced Scanning)

#### 3. **Cloud SQL Admin API**
- **Required for**: Cloud SQL Instances
- **Enable via Console**: https://console.cloud.google.com/apis/library/sqladmin.googleapis.com
- **Enable via CLI**:
  ```bash
  gcloud services enable sqladmin.googleapis.com --project=YOUR_PROJECT_ID
  ```

#### 4. **Cloud Functions API**
- **Required for**: Cloud Functions
- **Enable via Console**: https://console.cloud.google.com/apis/library/cloudfunctions.googleapis.com
- **Enable via CLI**:
  ```bash
  gcloud services enable cloudfunctions.googleapis.com --project=YOUR_PROJECT_ID
  ```

#### 5. **Cloud Firestore API**
- **Required for**: Firestore/Datastore Databases
- **Enable via Console**: https://console.cloud.google.com/apis/library/firestore.googleapis.com
- **Enable via CLI**:
  ```bash
  gcloud services enable firestore.googleapis.com --project=YOUR_PROJECT_ID
  ```

#### 6. **Cloud Memorystore for Redis API**
- **Required for**: Memorystore (Redis) Instances
- **Enable via Console**: https://console.cloud.google.com/apis/library/redis.googleapis.com
- **Enable via CLI**:
  ```bash
  gcloud services enable redis.googleapis.com --project=YOUR_PROJECT_ID
  ```

#### 7. **Cloud Monitoring API**
- **Required for**: Enhanced metrics and monitoring data
- **Enable via Console**: https://console.cloud.google.com/apis/library/monitoring.googleapis.com
- **Enable via CLI**:
  ```bash
  gcloud services enable monitoring.googleapis.com --project=YOUR_PROJECT_ID
  ```

---

## Quick Enable All APIs

### Using gcloud CLI:

```bash
# Set your project ID
PROJECT_ID="your-project-id"

# Enable all APIs at once
gcloud services enable \
  compute.googleapis.com \
  storage.googleapis.com \
  sqladmin.googleapis.com \
  cloudfunctions.googleapis.com \
  firestore.googleapis.com \
  redis.googleapis.com \
  monitoring.googleapis.com \
  --project=$PROJECT_ID

echo "✅ All APIs enabled! Wait 1-2 minutes for propagation."
```

### Using Console:

1. Go to [APIs & Services](https://console.cloud.google.com/apis/dashboard)
2. Click **+ ENABLE APIS AND SERVICES**
3. Search for each API listed above
4. Click **ENABLE** for each one

---

## Current Scan Coverage

A recent scan successfully scanned:

✅ **Working** (APIs enabled):
- Snapshots (Compute Engine API - partially enabled)
- Static IPs (Compute Engine API - partially enabled)
- Storage Buckets (Cloud Storage API - enabled)

⏸️ **Skipped** (APIs not enabled):
- Persistent Disks (Compute Engine API needed)
- Compute Instances (Compute Engine API needed)
- Load Balancers (Compute Engine API needed)
- Cloud SQL Instances (Cloud SQL Admin API needed)
- Cloud Functions (Cloud Functions API needed)
- Firestore Databases (Firestore API needed)
- Memorystore Instances (Redis API needed)
- Cloud CDN (Compute Engine API needed)

---

## Verifying API Status

Check which APIs are currently enabled:

```bash
gcloud services list --enabled --project=YOUR_PROJECT_ID
```

Check if a specific API is enabled:

```bash
gcloud services list --enabled --project=YOUR_PROJECT_ID | grep compute
```

---

## Troubleshooting

### Error: "API has not been used in project before or it is disabled"

**Solution**: Enable the required API using the commands above. Wait 1-2 minutes for propagation.

### Error: "Permission denied"

**Solution**: Ensure your account has the `serviceusage.services.enable` permission:
```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="user:YOUR_EMAIL" \
  --role="roles/serviceusage.serviceUsageAdmin"
```

### Error: "Quota exceeded"

**Solution**: 
1. Go to [IAM & Admin > Quotas](https://console.cloud.google.com/iam-admin/quotas)
2. Request quota increase for the affected API
3. Or wait for the quota to reset (usually 24 hours)

---

## Cost Considerations

**Important**: Enabling these APIs does NOT incur costs by itself. You only pay for:
- API calls made (most have generous free tiers)
- Resources created/used
- Data transfer

The Zombie Hunter tool makes **read-only API calls** which are typically free or very low cost (< $1/month for most scans).

---

## Next Steps

1. Enable the required APIs (at minimum: Compute Engine API)
2. Wait 1-2 minutes for propagation
3. Re-run the scan:
   ```bash
   python zombie_hunter.py --cloud gcp --region asia-southeast1
   ```
4. You should now see results for all 11 resource types

---

**Need help?** Contact CDOps Tech: contact@cdops.tech
