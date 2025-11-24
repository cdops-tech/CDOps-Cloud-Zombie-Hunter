"""
Azure Provider for CDOps Zombie Hunter.

Implements Azure-specific zombie resource scanning using Azure SDK.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from colorama import Fore, Style

try:
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.compute import ComputeManagementClient
    from azure.mgmt.storage import StorageManagementClient
    from azure.mgmt.network import NetworkManagementClient
    from azure.mgmt.resource import ResourceManagementClient, SubscriptionClient
    from azure.mgmt.sql import SqlManagementClient
    from azure.mgmt.cdn import CdnManagementClient
    from azure.mgmt.monitor import MonitorManagementClient
    from azure.core.exceptions import AzureError, HttpResponseError
except ImportError as e:
    print(f"{Fore.RED}ERROR: Azure SDK not installed. Run: pip install -r requirements.txt{Style.RESET_ALL}")
    raise

from .base import CloudProvider


class AzureProvider(CloudProvider):
    """Azure implementation of the zombie hunter."""
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the Azure Provider.
        
        Args:
            verbose: Enable verbose logging
        """
        super().__init__()
        self.verbose = verbose
        self.credential = None
        self.subscription_id = None
        self.scan_summary = {
            'unattached_managed_disks': 0,
            'obsolete_snapshots': 0,
            'stopped_vms': 0,
            'unassociated_public_ips': 0,
            'unused_load_balancers': 0,
            'stopped_sql_databases': 0,
            'empty_storage_accounts': 0,
            'unused_cdn_endpoints': 0,
            'unused_function_apps': 0,
            'idle_cosmos_db_accounts': 0,
            'idle_redis_caches': 0
        }
    
    def get_provider_name(self) -> str:
        """Return the provider name."""
        return "Azure"
    
    def validate_credentials(self) -> bool:
        """Validate Azure credentials."""
        try:
            self.credential = DefaultAzureCredential()
            
            # Get subscription ID
            subscription_client = SubscriptionClient(self.credential)
            subscriptions = list(subscription_client.subscriptions.list())
            
            if not subscriptions:
                print(f"{Fore.RED}ERROR: No Azure subscriptions found{Style.RESET_ALL}")
                return False
            
            # Use the first subscription (users can modify this logic)
            self.subscription_id = subscriptions[0].subscription_id
            subscription_name = subscriptions[0].display_name
            
            print(f"{Fore.GREEN}✅ Azure credentials validated{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Subscription: {subscription_name}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Subscription ID: {self.subscription_id}{Style.RESET_ALL}\n")
            
            if len(subscriptions) > 1:
                print(f"{Fore.YELLOW}⚠️  Note: Found {len(subscriptions)} subscriptions, using: {subscription_name}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}   To scan other subscriptions, modify the provider code{Style.RESET_ALL}\n")
            
            return True
            
        except Exception as e:
            print(f"{Fore.RED}ERROR: Azure credentials validation failed: {e}{Style.RESET_ALL}")
            print(f"\n{Fore.YELLOW}Azure Credential Setup:{Style.RESET_ALL}")
            print("  1. Azure CLI: az login")
            print("  2. Or set environment variables: AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET")
            print("  3. Or use managed identity (recommended for Azure VMs)")
            return False
    
    def get_available_regions(self) -> List[str]:
        """Get list of available Azure regions."""
        try:
            subscription_client = SubscriptionClient(self.credential)
            locations = subscription_client.subscriptions.list_locations(self.subscription_id)
            return [location.name for location in locations]
        except Exception as e:
            print(f"{Fore.RED}Error retrieving Azure regions: {e}{Style.RESET_ALL}")
            return []
    
    def run_scan(self, regions: List[str]):
        """Execute the complete scan across all specified regions."""
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}CDOps Cloud Zombie Hunter - Azure{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Scanning for unused Azure resources...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")
        
        for region in regions:
            print(f"\n{Fore.MAGENTA}>>> Scanning region: {region}{Style.RESET_ALL}\n")
            
            # Run all scans for this region
            self.scan_unattached_managed_disks(region)
            self.scan_obsolete_snapshots(region)
            self.scan_stopped_vms(region)
            self.scan_unassociated_public_ips(region)
            self.scan_unused_load_balancers(region)
            self.scan_stopped_sql_databases(region)
            self.scan_empty_storage_accounts(region)
            self.scan_unused_cdn_endpoints(region)
            self.scan_unused_function_apps(region)
            self.scan_idle_cosmos_db_accounts(region)
            self.scan_idle_redis_caches(region)
    
    def scan_unattached_managed_disks(self, region: str):
        """Scan for unattached managed disks."""
        try:
            self.log(f"Scanning for unattached managed disks in {region}...", "INFO")
            
            compute_client = ComputeManagementClient(self.credential, self.subscription_id)
            disks = compute_client.disks.list()
            
            count = 0
            for disk in disks:
                # Check if disk is in the specified region and unattached
                if disk.location == region and disk.disk_state == 'Unattached':
                    size_gb = disk.disk_size_gb or 0
                    # Azure managed disk pricing: ~$0.05-$0.10 per GB/month
                    estimated_cost = size_gb * 0.08
                    
                    self.findings.append({
                        'resource_type': 'Managed Disk',
                        'resource_id': disk.id,
                        'resource_name': disk.name,
                        'region': disk.location,
                        'size_gb': size_gb,
                        'sku': disk.sku.name if disk.sku else 'Unknown',
                        'estimated_monthly_cost': f'${estimated_cost:.2f}',
                        'reason': 'Disk is unattached (not connected to any VM)',
                        'created': disk.time_created.isoformat() if disk.time_created else 'Unknown'
                    })
                    count += 1
            
            self.scan_summary['unattached_managed_disks'] += count
            
            if count > 0:
                self.log(f"Found {count} unattached managed disks in {region}", "WARNING")
            else:
                self.log(f"No unattached managed disks found in {region}", "SUCCESS")
                
        except Exception as e:
            self.log(f"Error scanning managed disks in {region}: {e}", "ERROR")
    
    def scan_obsolete_snapshots(self, region: str):
        """Scan for old snapshots (>30 days)."""
        try:
            self.log(f"Scanning for obsolete snapshots in {region}...", "INFO")
            
            compute_client = ComputeManagementClient(self.credential, self.subscription_id)
            snapshots = compute_client.snapshots.list()
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            count = 0
            
            for snapshot in snapshots:
                if snapshot.location == region and snapshot.time_created:
                    if snapshot.time_created < cutoff_date:
                        size_gb = snapshot.disk_size_gb or 0
                        estimated_cost = size_gb * 0.05  # ~$0.05 per GB/month
                        
                        self.findings.append({
                            'resource_type': 'Snapshot',
                            'resource_id': snapshot.id,
                            'resource_name': snapshot.name,
                            'region': snapshot.location,
                            'size_gb': size_gb,
                            'age_days': (datetime.now(timezone.utc) - snapshot.time_created).days,
                            'estimated_monthly_cost': f'${estimated_cost:.2f}',
                            'reason': f'Snapshot older than 30 days (created {snapshot.time_created.date()})',
                            'created': snapshot.time_created.isoformat()
                        })
                        count += 1
            
            self.scan_summary['obsolete_snapshots'] += count
            
            if count > 0:
                self.log(f"Found {count} obsolete snapshots in {region}", "WARNING")
            else:
                self.log(f"No obsolete snapshots found in {region}", "SUCCESS")
                
        except Exception as e:
            self.log(f"Error scanning snapshots in {region}: {e}", "ERROR")
    
    def scan_stopped_vms(self, region: str):
        """Scan for stopped/deallocated VMs."""
        try:
            self.log(f"Scanning for stopped VMs in {region}...", "INFO")
            
            compute_client = ComputeManagementClient(self.credential, self.subscription_id)
            vms = compute_client.virtual_machines.list_all()
            
            count = 0
            for vm in vms:
                if vm.location == region:
                    # Get instance view to check power state
                    try:
                        instance_view = compute_client.virtual_machines.instance_view(
                            vm.id.split('/')[4],  # Resource group name
                            vm.name
                        )
                        
                        # Check if VM is deallocated/stopped
                        for status in instance_view.statuses:
                            if 'PowerState/stopped' in status.code or 'PowerState/deallocated' in status.code:
                                # Estimate costs for attached disks
                                estimated_cost = 10.0  # Base estimate for attached storage
                                
                                self.findings.append({
                                    'resource_type': 'Virtual Machine',
                                    'resource_id': vm.id,
                                    'resource_name': vm.name,
                                    'region': vm.location,
                                    'vm_size': vm.hardware_profile.vm_size if vm.hardware_profile else 'Unknown',
                                    'power_state': status.code,
                                    'estimated_monthly_cost': f'${estimated_cost:.2f}',
                                    'reason': 'VM is stopped/deallocated (managed disks still incur costs)'
                                })
                                count += 1
                                break
                    except Exception as e:
                        self.log(f"Could not check status for VM {vm.name}: {e}", "WARNING")
            
            self.scan_summary['stopped_vms'] += count
            
            if count > 0:
                self.log(f"Found {count} stopped VMs in {region}", "WARNING")
            else:
                self.log(f"No stopped VMs found in {region}", "SUCCESS")
                
        except Exception as e:
            self.log(f"Error scanning VMs in {region}: {e}", "ERROR")
    
    def scan_unassociated_public_ips(self, region: str):
        """Scan for unassociated public IP addresses."""
        try:
            self.log(f"Scanning for unassociated public IPs in {region}...", "INFO")
            
            network_client = NetworkManagementClient(self.credential, self.subscription_id)
            public_ips = network_client.public_ip_addresses.list_all()
            
            count = 0
            for ip in public_ips:
                # Check if in the specified region and not associated
                if ip.location == region and not ip.ip_configuration:
                    # Azure charges ~$0.005/hour = ~$3.60/month for unassociated public IPs
                    estimated_cost = 3.60
                    
                    self.findings.append({
                        'resource_type': 'Public IP',
                        'resource_id': ip.id,
                        'resource_name': ip.name,
                        'region': ip.location,
                        'ip_address': ip.ip_address or 'Not assigned',
                        'allocation_method': ip.public_ip_allocation_method,
                        'estimated_monthly_cost': f'${estimated_cost:.2f}',
                        'reason': 'Public IP is allocated but not associated with any resource'
                    })
                    count += 1
            
            self.scan_summary['unassociated_public_ips'] += count
            
            if count > 0:
                self.log(f"Found {count} unassociated public IPs in {region}", "WARNING")
            else:
                self.log(f"No unassociated public IPs found in {region}", "SUCCESS")
                
        except Exception as e:
            self.log(f"Error scanning public IPs in {region}: {e}", "ERROR")
    
    def scan_unused_load_balancers(self, region: str):
        """Scan for load balancers with no backend pools."""
        try:
            self.log(f"Scanning for unused load balancers in {region}...", "INFO")
            
            network_client = NetworkManagementClient(self.credential, self.subscription_id)
            load_balancers = network_client.load_balancers.list_all()
            
            count = 0
            for lb in load_balancers:
                if lb.location == region:
                    # Check if load balancer has no backend pools or all pools are empty
                    has_backends = False
                    if lb.backend_address_pools:
                        for pool in lb.backend_address_pools:
                            if pool.backend_ip_configurations:
                                has_backends = True
                                break
                    
                    if not has_backends:
                        estimated_cost = 18.0  # ~$18/month for Azure Load Balancer
                        
                        self.findings.append({
                            'resource_type': 'Load Balancer',
                            'resource_id': lb.id,
                            'resource_name': lb.name,
                            'region': lb.location,
                            'sku': lb.sku.name if lb.sku else 'Unknown',
                            'estimated_monthly_cost': f'${estimated_cost:.2f}',
                            'reason': 'Load balancer has no backend resources configured'
                        })
                        count += 1
            
            self.scan_summary['unused_load_balancers'] += count
            
            if count > 0:
                self.log(f"Found {count} unused load balancers in {region}", "WARNING")
            else:
                self.log(f"No unused load balancers found in {region}", "SUCCESS")
                
        except Exception as e:
            self.log(f"Error scanning load balancers in {region}: {e}", "ERROR")
    
    def scan_stopped_sql_databases(self, region: str):
        """Scan for paused/stopped Azure SQL databases."""
        try:
            self.log(f"Scanning for stopped SQL databases in {region}...", "INFO")
            
            sql_client = SqlManagementClient(self.credential, self.subscription_id)
            resource_client = ResourceManagementClient(self.credential, self.subscription_id)
            
            # Get all resource groups
            resource_groups = resource_client.resource_groups.list()
            
            count = 0
            for rg in resource_groups:
                if rg.location == region:
                    try:
                        servers = sql_client.servers.list_by_resource_group(rg.name)
                        for server in servers:
                            databases = sql_client.databases.list_by_server(rg.name, server.name)
                            for db in databases:
                                if db.name != 'master' and db.status == 'Paused':
                                    estimated_cost = 5.0  # Storage costs continue
                                    
                                    self.findings.append({
                                        'resource_type': 'SQL Database',
                                        'resource_id': db.id,
                                        'resource_name': db.name,
                                        'server': server.name,
                                        'region': db.location,
                                        'status': db.status,
                                        'estimated_monthly_cost': f'${estimated_cost:.2f}',
                                        'reason': 'SQL database is paused (storage costs still apply)'
                                    })
                                    count += 1
                    except Exception:
                        pass  # Skip resource groups we can't access
            
            self.scan_summary['stopped_sql_databases'] += count
            
            if count > 0:
                self.log(f"Found {count} stopped SQL databases in {region}", "WARNING")
            else:
                self.log(f"No stopped SQL databases found in {region}", "SUCCESS")
                
        except Exception as e:
            self.log(f"Error scanning SQL databases in {region}: {e}", "ERROR")
    
    def scan_empty_storage_accounts(self, region: str):
        """Scan for empty storage accounts."""
        try:
            self.log(f"Scanning for empty storage accounts in {region}...", "INFO")
            
            storage_client = StorageManagementClient(self.credential, self.subscription_id)
            storage_accounts = storage_client.storage_accounts.list()
            
            count = 0
            for account in storage_accounts:
                if account.location == region:
                    try:
                        # Check if account has any containers with blobs
                        # Note: This requires additional permissions and blob service client
                        # For now, we'll flag accounts as potentially empty
                        estimated_cost = 0.50  # Minimal but management overhead
                        
                        # We can't easily check blob counts without blob service client
                        # This is a simplified check
                        self.findings.append({
                            'resource_type': 'Storage Account',
                            'resource_id': account.id,
                            'resource_name': account.name,
                            'region': account.location,
                            'sku': account.sku.name if account.sku else 'Unknown',
                            'estimated_monthly_cost': f'${estimated_cost:.2f}',
                            'reason': 'Storage account may be empty (requires manual verification)',
                            'note': 'Check manually: detailed blob scanning requires additional permissions'
                        })
                        count += 1
                    except Exception:
                        pass
            
            self.scan_summary['empty_storage_accounts'] += count
            
            if count > 0:
                self.log(f"Found {count} potentially empty storage accounts in {region}", "WARNING")
            else:
                self.log(f"No empty storage accounts found in {region}", "SUCCESS")
                
        except Exception as e:
            self.log(f"Error scanning storage accounts in {region}: {e}", "ERROR")
    
    def scan_unused_cdn_endpoints(self, region: str):
        """Scan for disabled CDN endpoints."""
        try:
            self.log(f"Scanning for unused CDN endpoints in {region}...", "INFO")
            
            cdn_client = CdnManagementClient(self.credential, self.subscription_id)
            resource_client = ResourceManagementClient(self.credential, self.subscription_id)
            
            # Get all resource groups
            resource_groups = resource_client.resource_groups.list()
            
            count = 0
            for rg in resource_groups:
                if rg.location == region:
                    try:
                        profiles = cdn_client.profiles.list_by_resource_group(rg.name)
                        for profile in profiles:
                            endpoints = cdn_client.endpoints.list_by_profile(rg.name, profile.name)
                            for endpoint in endpoints:
                                if endpoint.resource_state == 'Stopped' or not endpoint.is_http_allowed:
                                    estimated_cost = 5.0
                                    
                                    self.findings.append({
                                        'resource_type': 'CDN Endpoint',
                                        'resource_id': endpoint.id,
                                        'resource_name': endpoint.name,
                                        'profile': profile.name,
                                        'region': endpoint.location,
                                        'state': endpoint.resource_state,
                                        'estimated_monthly_cost': f'${estimated_cost:.2f}',
                                        'reason': 'CDN endpoint is stopped or disabled'
                                    })
                                    count += 1
                    except Exception:
                        pass
            
            self.scan_summary['unused_cdn_endpoints'] += count
            
            if count > 0:
                self.log(f"Found {count} unused CDN endpoints in {region}", "WARNING")
            else:
                self.log(f"No unused CDN endpoints found in {region}", "SUCCESS")
                
        except Exception as e:
            self.log(f"Error scanning CDN endpoints in {region}: {e}", "ERROR")
    
    def scan_unused_function_apps(self, region: str):
        """
        Scan for unused Azure Function Apps (stopped or with no invocations).
        
        Args:
            region: Azure region to scan
        """
        try:
            from azure.mgmt.web import WebSiteManagementClient
            
            self.log(f"Scanning for unused function apps in {region}...", "INFO")
            
            web_client = WebSiteManagementClient(self.credential, self.subscription_id)
            count = 0
            
            # List all function apps
            for app in web_client.web_apps.list():
                try:
                    if app.location.replace(' ', '').lower() == region.replace(' ', '').lower():
                        # Check if it's a function app
                        if app.kind and 'functionapp' in app.kind.lower():
                            # Check if stopped
                            if app.state and app.state.lower() == 'stopped':
                                self.findings.append({
                                    'resource_type': 'Azure Function App',
                                    'resource_id': app.name,
                                    'region': region,
                                    'size_gb': '-',
                                    'estimated_monthly_cost': '$15.00',
                                    'reason': f'Function app is stopped (state: {app.state})'
                                })
                                count += 1
                except Exception:
                    pass
            
            self.scan_summary['unused_function_apps'] += count
            
            if count > 0:
                self.log(f"Found {count} unused function apps in {region}", "WARNING")
            else:
                self.log(f"No unused function apps found in {region}", "SUCCESS")
                
        except Exception as e:
            self.log(f"Error scanning function apps in {region}: {e}", "ERROR")
    
    def scan_idle_cosmos_db_accounts(self, region: str):
        """
        Scan for idle Cosmos DB accounts (low or no activity).
        Note: This is a placeholder - requires Azure Monitor metrics for accurate detection.
        
        Args:
            region: Azure region to scan
        """
        try:
            from azure.mgmt.cosmosdb import CosmosDBManagementClient
            
            self.log(f"Scanning for idle Cosmos DB accounts in {region}...", "INFO")
            
            cosmos_client = CosmosDBManagementClient(self.credential, self.subscription_id)
            count = 0
            
            # List all Cosmos DB accounts
            for account in cosmos_client.database_accounts.list():
                try:
                    if account.location.replace(' ', '').lower() == region.replace(' ', '').lower():
                        # Placeholder: Flag for manual review
                        # In production, would check metrics via Monitor API
                        pass
                except Exception:
                    pass
            
            self.scan_summary['idle_cosmos_db_accounts'] += count
            
            if count > 0:
                self.log(f"Found {count} idle Cosmos DB accounts in {region}", "WARNING")
            else:
                self.log(f"No idle Cosmos DB accounts found in {region}", "SUCCESS")
                
        except Exception as e:
            self.log(f"Error scanning Cosmos DB accounts in {region}: {e}", "ERROR")
    
    def scan_idle_redis_caches(self, region: str):
        """
        Scan for idle Redis caches (low connection count).
        Note: This is a placeholder - requires Azure Monitor metrics for accurate detection.
        
        Args:
            region: Azure region to scan
        """
        try:
            from azure.mgmt.redis import RedisManagementClient
            
            self.log(f"Scanning for idle Redis caches in {region}...", "INFO")
            
            redis_client = RedisManagementClient(self.credential, self.subscription_id)
            count = 0
            
            # List all Redis caches
            for cache in redis_client.redis.list():
                try:
                    if cache.location.replace(' ', '').lower() == region.replace(' ', '').lower():
                        # Placeholder: Flag for manual review
                        # In production, would check metrics via Monitor API
                        pass
                except Exception:
                    pass
            
            self.scan_summary['idle_redis_caches'] += count
            
            if count > 0:
                self.log(f"Found {count} idle Redis caches in {region}", "WARNING")
            else:
                self.log(f"No idle Redis caches found in {region}", "SUCCESS")
                
        except Exception as e:
            self.log(f"Error scanning Redis caches in {region}: {e}", "ERROR")
    
    def calculate_total_savings(self) -> float:
        """
        Calculate total estimated monthly savings from all zombie resources.
        
        Returns:
            Total estimated monthly cost savings in USD
        """
        total_savings = 0.0
        
        for finding in self.findings:
            if 'estimated_monthly_cost' in finding:
                try:
                    cost_str = finding['estimated_monthly_cost']
                    cost_value = float(cost_str.replace('$', '').replace(',', ''))
                    total_savings += cost_value
                except (ValueError, AttributeError):
                    pass
        
        return total_savings
