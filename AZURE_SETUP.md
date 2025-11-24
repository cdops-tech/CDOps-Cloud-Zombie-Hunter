# Azure Provider Setup Guide

## Overview

The Azure provider for CDOps Cloud Zombie Hunter scans your Azure subscription for zombie resources that are generating unnecessary costs.

## Supported Azure Resources

The Azure provider scans for these zombie resources:

1. **Unattached Managed Disks** - Disks not attached to any VM
2. **Obsolete Snapshots** - Snapshots older than 30 days
3. **Stopped Virtual Machines** - VMs in deallocated/stopped state (managed disks still cost money)
4. **Unassociated Public IPs** - Public IP addresses not associated with any resource
5. **Unused Load Balancers** - Load balancers with no backend pools configured
6. **Stopped SQL Databases** - Azure SQL databases in paused state
7. **Empty Storage Accounts** - Storage accounts that may be empty
8. **Unused CDN Endpoints** - CDN endpoints that are stopped or disabled

---

## Prerequisites

### 1. Azure CLI (Recommended)

Install the Azure CLI:

```bash
# macOS
brew install azure-cli

# Windows
# Download from https://aka.ms/installazurecliwindows

# Linux (Ubuntu/Debian)
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

### 2. Python Dependencies

The Azure provider requires additional Python packages:

```bash
pip install azure-identity azure-mgmt-compute azure-mgmt-storage \
            azure-mgmt-network azure-mgmt-resource azure-mgmt-sql \
            azure-mgmt-cdn azure-mgmt-monitor
```

Or simply:

```bash
pip install -r requirements.txt
```

---

## Authentication Methods

### Option 1: Azure CLI (Recommended for Development)

The easiest method for local development:

```bash
# Login to Azure
az login

# Verify your subscription
az account show

# Set a specific subscription (if you have multiple)
az account set --subscription "Your-Subscription-Name"
```

Once logged in, the tool will automatically use your Azure CLI credentials.

### Option 2: Service Principal (Recommended for Production/CI/CD)

Create a service principal for automated scanning:

```bash
# Create a service principal
az ad sp create-for-rbac --name "CDOpsZombieHunter" --role Reader --scopes /subscriptions/{subscription-id}
```

This will output:

```json
{
  "appId": "00000000-0000-0000-0000-000000000000",
  "displayName": "CDOpsZombieHunter",
  "password": "xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "tenant": "00000000-0000-0000-0000-000000000000"
}
```

Set environment variables:

```bash
export AZURE_CLIENT_ID="<appId>"
export AZURE_TENANT_ID="<tenant>"
export AZURE_CLIENT_SECRET="<password>"
export AZURE_SUBSCRIPTION_ID="<your-subscription-id>"
```

### Option 3: Managed Identity (Recommended for Azure VMs)

If running on an Azure VM, assign a managed identity:

```bash
# Enable system-assigned managed identity
az vm identity assign --name MyVM --resource-group MyResourceGroup

# Assign Reader role to the managed identity
az role assignment create --assignee <managed-identity-principal-id> \
  --role Reader --scope /subscriptions/{subscription-id}
```

The tool will automatically use the managed identity when running on the Azure VM.

---

## RBAC Permissions

The Azure provider requires **read-only** permissions. Create a custom role or use the built-in **Reader** role.

### Using Built-in Reader Role (Simplest)

```bash
# Assign Reader role to a user
az role assignment create --assignee user@domain.com \
  --role Reader --scope /subscriptions/{subscription-id}

# Or assign to a service principal
az role assignment create --assignee <service-principal-app-id> \
  --role Reader --scope /subscriptions/{subscription-id}
```

### Creating a Custom Role (Most Secure)

Create a custom role with minimal permissions:

```bash
# Create custom role from JSON file
az role definition create --role-definition azure-rbac-role.json
```

The `azure-rbac-role.json` file is included in this repository with the exact permissions needed.

### Required Permissions

The tool needs these read permissions:

- `Microsoft.Compute/disks/read`
- `Microsoft.Compute/snapshots/read`
- `Microsoft.Compute/virtualMachines/read`
- `Microsoft.Compute/virtualMachines/instanceView/read`
- `Microsoft.Network/publicIPAddresses/read`
- `Microsoft.Network/loadBalancers/read`
- `Microsoft.Sql/servers/read`
- `Microsoft.Sql/servers/databases/read`
- `Microsoft.Storage/storageAccounts/read`
- `Microsoft.Cdn/profiles/read`
- `Microsoft.Cdn/profiles/endpoints/read`
- `Microsoft.Resources/subscriptions/read`
- `Microsoft.Resources/subscriptions/resourceGroups/read`

---

## Usage

### Scan a Specific Azure Region

```bash
python zombie_hunter.py --cloud azure --region eastus
```

### Scan All Azure Regions

```bash
python zombie_hunter.py --cloud azure --all-regions
```

### Export Results to CSV

```bash
python zombie_hunter.py --cloud azure --region westus --output azure_report.csv
```

---

## Azure Region Names

Common Azure region names:

| Region Name | Location |
|-------------|----------|
| `eastus` | East US |
| `eastus2` | East US 2 |
| `westus` | West US |
| `westus2` | West US 2 |
| `westus3` | West US 3 |
| `centralus` | Central US |
| `northcentralus` | North Central US |
| `southcentralus` | South Central US |
| `westcentralus` | West Central US |
| `canadacentral` | Canada Central |
| `canadaeast` | Canada East |
| `brazilsouth` | Brazil South |
| `northeurope` | North Europe |
| `westeurope` | West Europe |
| `uksouth` | UK South |
| `ukwest` | UK West |
| `francecentral` | France Central |
| `germanywestcentral` | Germany West Central |
| `norwayeast` | Norway East |
| `switzerlandnorth` | Switzerland North |
| `swedencentral` | Sweden Central |
| `southeastasia` | Southeast Asia |
| `eastasia` | East Asia |
| `australiaeast` | Australia East |
| `australiasoutheast` | Australia Southeast |
| `japaneast` | Japan East |
| `japanwest` | Japan West |
| `koreacentral` | Korea Central |
| `southindia` | South India |
| `centralindia` | Central India |
| `westindia` | West India |

Get all available regions:

```bash
az account list-locations --query "[].name" -o table
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

🔧 Initializing Azure Provider...

✅ Azure credentials validated
Subscription: Production Subscription
Subscription ID: 12345678-1234-1234-1234-123456789012

📍 Scanning region: eastus

================================================================================
CDOps Cloud Zombie Hunter - Azure
Scanning for unused Azure resources...
================================================================================

>>> Scanning region: eastus

[INFO] Scanning for unattached managed disks in eastus...
[WARNING] Found 3 unattached managed disks in eastus
[INFO] Scanning for obsolete snapshots in eastus...
[SUCCESS] No obsolete snapshots found in eastus
[INFO] Scanning for stopped VMs in eastus...
[WARNING] Found 2 stopped VMs in eastus
[INFO] Scanning for unassociated public IPs in eastus...
[WARNING] Found 1 unassociated public IPs in eastus

================================================================================
SCAN SUMMARY
================================================================================

+------------------------------------------+-------+
| Resource Type                            | Count |
+==========================================+=======+
| Unattached Managed Disks                 |     3 |
+------------------------------------------+-------+
| Obsolete Snapshots (>30 days)            |     0 |
+------------------------------------------+-------+
| Stopped Virtual Machines                 |     2 |
+------------------------------------------+-------+
| Unassociated Public IPs                  |     1 |
+------------------------------------------+-------+
| Unused Load Balancers                    |     0 |
+------------------------------------------+-------+
| Stopped SQL Databases                    |     0 |
+------------------------------------------+-------+
| Empty Storage Accounts                   |     0 |
+------------------------------------------+-------+
| Unused CDN Endpoints                     |     0 |
+------------------------------------------+-------+

⚠️  Total Zombie Resources Found: 6
💰 Estimated Monthly Savings: $45.20
💵 Estimated Annual Savings: $542.40
```

---

## Troubleshooting

### Error: "No Azure subscriptions found"

**Solution:** Login with Azure CLI:

```bash
az login
az account list
```

### Error: "Failed to import Azure SDK"

**Solution:** Install Azure dependencies:

```bash
pip install -r requirements.txt
```

### Error: "Authorization failed"

**Solution:** Ensure you have at least **Reader** role on the subscription:

```bash
az role assignment list --assignee user@domain.com --scope /subscriptions/{subscription-id}
```

### Scanning Multiple Subscriptions

The tool currently scans the first available subscription. To scan multiple subscriptions, you can:

1. Run the tool multiple times with different credentials
2. Modify `providers/azure.py` to loop through all subscriptions

---

## Cost Estimates

Azure cost estimates used by the tool:

| Resource Type | Estimated Cost |
|---------------|----------------|
| Managed Disk (Standard SSD) | $0.08/GB/month |
| Snapshot | $0.05/GB/month |
| Public IP (unassociated) | $3.60/month |
| Load Balancer (Basic) | $18/month |
| SQL Database (paused) | Storage costs continue |
| Storage Account | Minimal, management overhead |

**Note:** Costs are approximate and vary by region, SKU, and Azure pricing changes.

---

## Automation

### Azure DevOps Pipeline

```yaml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '3.8'
  
- script: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt
  displayName: 'Install dependencies'

- task: AzureCLI@2
  inputs:
    azureSubscription: 'Your-Service-Connection'
    scriptType: 'bash'
    scriptLocation: 'inlineScript'
    inlineScript: |
      python zombie_hunter.py --cloud azure --all-regions --output azure_zombies.csv
  displayName: 'Run Zombie Hunter'

- task: PublishBuildArtifacts@1
  inputs:
    pathToPublish: 'azure_zombies.csv'
    artifactName: 'ZombieReport'
```

### GitHub Actions

```yaml
name: Azure Zombie Scan

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
          python-version: '3.8'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      
      - name: Run Zombie Hunter
        run: python zombie_hunter.py --cloud azure --all-regions
      
      - name: Upload Report
        uses: actions/upload-artifact@v3
        with:
          name: zombie-report
          path: '*.csv'
```

---

## Security Best Practices

1. **Use Service Principals for Automation** - Never hardcode credentials
2. **Principle of Least Privilege** - Use custom RBAC role with minimal permissions
3. **Rotate Secrets Regularly** - Change service principal passwords periodically
4. **Use Managed Identities** - When running on Azure resources
5. **Audit Access** - Monitor who runs the scanner and when
6. **Encrypt Reports** - CSV reports contain resource information

---

## Need Help?

For Azure-specific assistance or professional cloud optimization services:

📧 **Email:** contact@cdops.tech  
🌐 **Website:** https://cdops.tech  
💼 **Services:** DevSecOps, SRE, Multi-Cloud Cost Optimization

---

## Contributing

Found a bug or want to add Azure resource types? See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## License

MIT License - See [LICENSE](LICENSE) file for details
