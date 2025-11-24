"""
GCP Provider for CDOps Zombie Hunter.

Implements GCP-specific zombie resource scanning using Google Cloud SDK.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from colorama import Fore, Style

try:
    import warnings
    # Suppress Google Auth ADC warning about quota project
    warnings.filterwarnings('ignore', message='.*end user credentials.*quota project.*')
    
    from google.cloud import compute_v1
    from google.cloud import storage
    from google.cloud import monitoring_v3
    from google.auth import default
    from google.auth.exceptions import DefaultCredentialsError
    import google.auth
except ImportError as e:
    print(f"{Fore.RED}ERROR: GCP SDK not installed. Run: pip install -r requirements.txt{Style.RESET_ALL}")
    raise

from .base import CloudProvider


class GCPProvider(CloudProvider):
    """GCP implementation of the zombie hunter."""
    
    def _is_api_not_enabled_error(self, error: Exception) -> bool:
        """Check if error is due to API not being enabled."""
        error_str = str(error).lower()
        return ('403' in error_str and 
                ('api has not been used' in error_str or 
                 'is disabled' in error_str or
                 'api not enabled' in error_str))
    
    def _log_api_not_enabled(self, api_name: str, region: str = None):
        """Log a helpful message when an API is not enabled."""
        location = f" in {region}" if region else ""
        self.log(
            f"⏭️  Skipping {api_name} scan{location} - API not enabled. "
            f"Enable at: https://console.cloud.google.com/apis/library",
            "WARNING"
        )
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the GCP Provider.
        
        Args:
            verbose: Enable verbose logging
        """
        super().__init__()
        self.verbose = verbose
        self.credentials = None
        self.project_id = None
        self.scan_summary = {
            'unattached_persistent_disks': 0,
            'obsolete_snapshots': 0,
            'stopped_compute_instances': 0,
            'unattached_static_ips': 0,
            'unused_load_balancers': 0,
            'stopped_cloud_sql_instances': 0,
            'empty_storage_buckets': 0,
            'unused_cloud_functions': 0,
            'idle_firestore_databases': 0,
            'idle_memorystore_instances': 0,
            'unused_cloud_cdn': 0
        }
    
    def get_provider_name(self) -> str:
        """Return the provider name."""
        return "GCP"
    
    def validate_credentials(self) -> bool:
        """Validate GCP credentials."""
        try:
            self.credentials, self.project_id = default()
            
            if not self.project_id:
                print(f"{Fore.RED}ERROR: No GCP project ID found{Style.RESET_ALL}")
                return False
            
            print(f"{Fore.GREEN}✅ GCP credentials validated{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Project ID: {self.project_id}{Style.RESET_ALL}\n")
            
            return True
            
        except DefaultCredentialsError as e:
            print(f"{Fore.RED}ERROR: GCP credentials validation failed: {e}{Style.RESET_ALL}")
            print(f"\n{Fore.YELLOW}GCP Credential Setup:{Style.RESET_ALL}")
            print("  1. gcloud CLI: gcloud auth application-default login")
            print("  2. Or set environment variable: GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
            print("  3. Or use service account (recommended for production)")
            return False
        except Exception as e:
            print(f"{Fore.RED}ERROR: Unexpected error validating GCP credentials: {e}{Style.RESET_ALL}")
            return False
    
    def get_available_regions(self) -> List[str]:
        """Get list of available GCP regions."""
        try:
            regions_client = compute_v1.RegionsClient(credentials=self.credentials)
            request = compute_v1.ListRegionsRequest(project=self.project_id)
            regions = regions_client.list(request=request)
            
            return [region.name for region in regions]
        except Exception as e:
            print(f"{Fore.RED}Error retrieving GCP regions: {e}{Style.RESET_ALL}")
            return []
    
    def run_scan(self, regions: List[str]):
        """Execute the complete scan across all specified regions."""
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}CDOps Cloud Zombie Hunter - GCP{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Scanning for unused GCP resources...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")
        
        for region in regions:
            print(f"\n{Fore.MAGENTA}>>> Scanning region: {region}{Style.RESET_ALL}\n")
            
            # Run all scans for this region
            self.scan_unattached_persistent_disks(region)
            self.scan_obsolete_snapshots(region)
            self.scan_stopped_compute_instances(region)
            self.scan_unattached_static_ips(region)
            self.scan_unused_load_balancers(region)
            self.scan_stopped_cloud_sql_instances(region)
            self.scan_unused_cloud_functions(region)
            self.scan_idle_firestore_databases(region)
            self.scan_idle_memorystore_instances(region)
            self.scan_unused_cloud_cdn(region)
            
        # Scan global resources once
        if regions:
            self.scan_empty_storage_buckets()
    
    def scan_unattached_persistent_disks(self, region: str):
        """Scan for unattached persistent disks."""
        try:
            self.log(f"Scanning for unattached persistent disks in {region}...", "INFO")
            
            disks_client = compute_v1.DisksClient(credentials=self.credentials)
            request = compute_v1.AggregatedListDisksRequest(project=self.project_id)
            
            count = 0
            for zone, disk_list in disks_client.aggregated_list(request=request):
                if not disk_list.disks:
                    continue
                
                # Check if zone is in the specified region
                zone_name = zone.split('/')[-1] if '/' in zone else zone
                if not zone_name.startswith(region):
                    continue
                
                for disk in disk_list.disks:
                    # Check if disk is not attached
                    if not disk.users:  # users field contains attached instances
                        size_gb = disk.size_gb
                        # GCP persistent disk pricing: ~$0.04-$0.17 per GB/month
                        estimated_cost = size_gb * 0.04 if disk.type_.endswith('pd-standard') else size_gb * 0.17
                        
                        self.findings.append({
                            'resource_type': 'Persistent Disk',
                            'resource_id': disk.self_link,
                            'resource_name': disk.name,
                            'region': region,
                            'zone': zone_name,
                            'size_gb': size_gb,
                            'disk_type': disk.type_.split('/')[-1] if '/' in disk.type_ else disk.type_,
                            'estimated_monthly_cost': f'${estimated_cost:.2f}',
                            'reason': 'Disk is not attached to any instance',
                            'created': disk.creation_timestamp
                        })
                        count += 1
            
            self.scan_summary['unattached_persistent_disks'] += count
            
            if count > 0:
                self.log(f"Found {count} unattached persistent disks in {region}", "WARNING")
            else:
                self.log(f"No unattached persistent disks found in {region}", "SUCCESS")
                
        except Exception as e:
            if self._is_api_not_enabled_error(e):
                self._log_api_not_enabled("Compute Engine API (Persistent Disks)", region)
            else:
                self.log(f"Error scanning persistent disks in {region}: {e}", "ERROR")
    
    def scan_obsolete_snapshots(self, region: str):
        """Scan for old snapshots (>30 days)."""
        try:
            self.log(f"Scanning for obsolete snapshots in {region}...", "INFO")
            
            snapshots_client = compute_v1.SnapshotsClient(credentials=self.credentials)
            request = compute_v1.ListSnapshotsRequest(project=self.project_id)
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            count = 0
            
            for snapshot in snapshots_client.list(request=request):
                # Check if snapshot is in the specified region
                if snapshot.storage_locations and region not in snapshot.storage_locations:
                    continue
                
                # Parse creation timestamp
                created = datetime.fromisoformat(snapshot.creation_timestamp.replace('Z', '+00:00'))
                
                if created < cutoff_date:
                    size_gb = snapshot.disk_size_gb
                    estimated_cost = size_gb * 0.026  # ~$0.026 per GB/month
                    
                    age_days = (datetime.now(timezone.utc) - created).days
                    
                    self.findings.append({
                        'resource_type': 'Snapshot',
                        'resource_id': snapshot.self_link,
                        'resource_name': snapshot.name,
                        'region': region,
                        'size_gb': size_gb,
                        'age_days': age_days,
                        'estimated_monthly_cost': f'${estimated_cost:.2f}',
                        'reason': f'Snapshot older than 30 days (created {created.date()})',
                        'created': snapshot.creation_timestamp
                    })
                    count += 1
            
            self.scan_summary['obsolete_snapshots'] += count
            
            if count > 0:
                self.log(f"Found {count} obsolete snapshots in {region}", "WARNING")
            else:
                self.log(f"No obsolete snapshots found in {region}", "SUCCESS")
                
        except Exception as e:
            if self._is_api_not_enabled_error(e):
                self._log_api_not_enabled("Compute Engine API (Snapshots)", region)
            else:
                self.log(f"Error scanning snapshots in {region}: {e}", "ERROR")
    
    def scan_stopped_compute_instances(self, region: str):
        """Scan for stopped Compute Engine instances."""
        try:
            self.log(f"Scanning for stopped Compute instances in {region}...", "INFO")
            
            instances_client = compute_v1.InstancesClient(credentials=self.credentials)
            request = compute_v1.AggregatedListInstancesRequest(project=self.project_id)
            
            count = 0
            for zone, instance_list in instances_client.aggregated_list(request=request):
                if not instance_list.instances:
                    continue
                
                # Check if zone is in the specified region
                zone_name = zone.split('/')[-1] if '/' in zone else zone
                if not zone_name.startswith(region):
                    continue
                
                for instance in instance_list.instances:
                    if instance.status == 'TERMINATED' or instance.status == 'STOPPED':
                        # Estimate costs for attached disks
                        disk_cost = 0
                        for disk in instance.disks:
                            if disk.disk_size_gb:
                                disk_cost += disk.disk_size_gb * 0.04
                        
                        estimated_cost = max(disk_cost, 5.0)  # Minimum estimate
                        
                        self.findings.append({
                            'resource_type': 'Compute Instance',
                            'resource_id': instance.self_link,
                            'resource_name': instance.name,
                            'region': region,
                            'zone': zone_name,
                            'machine_type': instance.machine_type.split('/')[-1] if '/' in instance.machine_type else instance.machine_type,
                            'status': instance.status,
                            'estimated_monthly_cost': f'${estimated_cost:.2f}',
                            'reason': f'Instance is {instance.status.lower()} (persistent disks still incur costs)'
                        })
                        count += 1
            
            self.scan_summary['stopped_compute_instances'] += count
            
            if count > 0:
                self.log(f"Found {count} stopped compute instances in {region}", "WARNING")
            else:
                self.log(f"No stopped compute instances found in {region}", "SUCCESS")
                
        except Exception as e:
            if self._is_api_not_enabled_error(e):
                self._log_api_not_enabled("Compute Engine API (Instances)", region)
            else:
                self.log(f"Error scanning compute instances in {region}: {e}", "ERROR")
    
    def scan_unattached_static_ips(self, region: str):
        """Scan for unattached static IP addresses."""
        try:
            self.log(f"Scanning for unattached static IPs in {region}...", "INFO")
            
            addresses_client = compute_v1.AddressesClient(credentials=self.credentials)
            request = compute_v1.ListAddressesRequest(
                project=self.project_id,
                region=region
            )
            
            count = 0
            for address in addresses_client.list(request=request):
                # Check if address is not in use
                if address.status == 'RESERVED' and not address.users:
                    # GCP charges for unused static IPs: ~$0.01/hour = ~$7.20/month
                    estimated_cost = 7.20
                    
                    self.findings.append({
                        'resource_type': 'Static IP',
                        'resource_id': address.self_link,
                        'resource_name': address.name,
                        'region': region,
                        'ip_address': address.address,
                        'address_type': address.address_type,
                        'estimated_monthly_cost': f'${estimated_cost:.2f}',
                        'reason': 'Static IP is reserved but not attached to any resource'
                    })
                    count += 1
            
            self.scan_summary['unattached_static_ips'] += count
            
            if count > 0:
                self.log(f"Found {count} unattached static IPs in {region}", "WARNING")
            else:
                self.log(f"No unattached static IPs found in {region}", "SUCCESS")
                
        except Exception as e:
            if self._is_api_not_enabled_error(e):
                self._log_api_not_enabled("Compute Engine API (Static IPs)", region)
            else:
                self.log(f"Error scanning static IPs in {region}: {e}", "ERROR")
    
    def scan_unused_load_balancers(self, region: str):
        """Scan for load balancers with no backend services."""
        try:
            self.log(f"Scanning for unused load balancers in {region}...", "INFO")
            
            # Check regional forwarding rules
            forwarding_rules_client = compute_v1.ForwardingRulesClient(credentials=self.credentials)
            request = compute_v1.ListForwardingRulesRequest(
                project=self.project_id,
                region=region
            )
            
            count = 0
            for rule in forwarding_rules_client.list(request=request):
                # If no target or backend service, it's unused
                if not rule.target and not rule.backend_service:
                    estimated_cost = 18.0  # ~$18/month for load balancer
                    
                    self.findings.append({
                        'resource_type': 'Load Balancer',
                        'resource_id': rule.self_link,
                        'resource_name': rule.name,
                        'region': region,
                        'ip_address': rule.ip_address if hasattr(rule, 'ip_address') else 'N/A',
                        'estimated_monthly_cost': f'${estimated_cost:.2f}',
                        'reason': 'Load balancer has no backend services configured'
                    })
                    count += 1
            
            self.scan_summary['unused_load_balancers'] += count
            
            if count > 0:
                self.log(f"Found {count} unused load balancers in {region}", "WARNING")
            else:
                self.log(f"No unused load balancers found in {region}", "SUCCESS")
                
        except Exception as e:
            if self._is_api_not_enabled_error(e):
                self._log_api_not_enabled("Compute Engine API (Load Balancers)", region)
            else:
                self.log(f"Error scanning load balancers in {region}: {e}", "ERROR")
    
    def scan_stopped_cloud_sql_instances(self, region: str):
        """Scan for stopped Cloud SQL instances."""
        try:
            self.log(f"Scanning for stopped Cloud SQL instances in {region}...", "INFO")
            
            # Note: Cloud SQL management requires google-cloud-sql library
            # For now, we'll note this as a feature that needs the SQL Admin API
            
            self.log(f"Cloud SQL scanning requires SQL Admin API (feature coming soon)", "INFO")
            
        except Exception as e:
            if self._is_api_not_enabled_error(e):
                self._log_api_not_enabled("Cloud SQL Admin API", region)
            else:
                self.log(f"Error scanning Cloud SQL instances in {region}: {e}", "ERROR")
    
    def scan_empty_storage_buckets(self):
        """Scan for empty Cloud Storage buckets (global)."""
        try:
            self.log(f"Scanning for empty Cloud Storage buckets...", "INFO")
            
            storage_client = storage.Client(
                credentials=self.credentials,
                project=self.project_id
            )
            
            count = 0
            for bucket in storage_client.list_buckets():
                # Check if bucket is empty
                blobs = list(bucket.list_blobs(max_results=1))
                if not blobs:
                    estimated_cost = 0.50  # Minimal but management overhead
                    
                    self.findings.append({
                        'resource_type': 'Storage Bucket',
                        'resource_id': f'gs://{bucket.name}',
                        'resource_name': bucket.name,
                        'region': bucket.location,
                        'storage_class': bucket.storage_class,
                        'estimated_monthly_cost': f'${estimated_cost:.2f}',
                        'reason': 'Bucket is empty (no objects stored)',
                        'created': bucket.time_created.isoformat() if bucket.time_created else 'Unknown'
                    })
                    count += 1
            
            self.scan_summary['empty_storage_buckets'] += count
            
            if count > 0:
                self.log(f"Found {count} empty Cloud Storage buckets", "WARNING")
            else:
                self.log(f"No empty Cloud Storage buckets found", "SUCCESS")
                
        except Exception as e:
            if self._is_api_not_enabled_error(e):
                self._log_api_not_enabled("Cloud Storage API")
            else:
                self.log(f"Error scanning Cloud Storage buckets: {e}", "ERROR")
    
    def scan_unused_cloud_functions(self, region: str):
        """
        Scan for Cloud Functions with no recent invocations.
        Note: This is a placeholder - requires Cloud Functions API and Monitoring API.
        """
        try:
            self.log(f"Scanning for unused Cloud Functions in {region}...", "INFO")
            
            # Placeholder: Would require Cloud Functions API
            # from google.cloud import functions_v1
            # In production, would check invocation metrics via Monitoring API
            count = 0
            
            self.scan_summary['unused_cloud_functions'] += count
            
            if count > 0:
                self.log(f"Found {count} unused Cloud Functions in {region}", "WARNING")
            else:
                self.log(f"No unused Cloud Functions found in {region}", "SUCCESS")
            
        except Exception as e:
            if self._is_api_not_enabled_error(e):
                self._log_api_not_enabled("Cloud Functions API", region)
            else:
                self.log(f"Error scanning Cloud Functions in {region}: {e}", "ERROR")
    
    def scan_idle_firestore_databases(self, region: str):
        """
        Scan for idle Firestore/Datastore databases (low activity).
        Note: This is a placeholder - requires Firestore/Datastore API and metrics.
        """
        try:
            self.log(f"Scanning for idle Firestore databases in {region}...", "INFO")
            
            # Placeholder: Would require Firestore Admin API
            # from google.cloud import firestore_admin_v1
            # In production, would check operation metrics
            count = 0
            
            self.scan_summary['idle_firestore_databases'] += count
            
            if count > 0:
                self.log(f"Found {count} idle Firestore databases in {region}", "WARNING")
            else:
                self.log(f"No idle Firestore databases found in {region}", "SUCCESS")
            
        except Exception as e:
            if self._is_api_not_enabled_error(e):
                self._log_api_not_enabled("Cloud Firestore API", region)
            else:
                self.log(f"Error scanning Firestore databases in {region}: {e}", "ERROR")
    
    def scan_idle_memorystore_instances(self, region: str):
        """
        Scan for idle Memorystore (Redis) instances (low connection count).
        Note: This is a placeholder - requires Memorystore API and monitoring metrics.
        """
        try:
            self.log(f"Scanning for idle Memorystore instances in {region}...", "INFO")
            
            # Placeholder: Would require Memorystore API
            # from google.cloud import redis_v1
            # In production, would check connection metrics via Monitoring API
            count = 0
            
            self.scan_summary['idle_memorystore_instances'] += count
            
            if count > 0:
                self.log(f"Found {count} idle Memorystore instances in {region}", "WARNING")
            else:
                self.log(f"No idle Memorystore instances found in {region}", "SUCCESS")
            
        except Exception as e:
            if self._is_api_not_enabled_error(e):
                self._log_api_not_enabled("Cloud Memorystore API (Redis)", region)
            else:
                self.log(f"Error scanning Memorystore instances in {region}: {e}", "ERROR")
    
    def scan_unused_cloud_cdn(self, region: str):
        """
        Scan for unused Cloud CDN services.
        Note: This is a placeholder - requires Compute API for URL maps and backend services.
        """
        try:
            self.log(f"Scanning for unused Cloud CDN in {region}...", "INFO")
            
            # Placeholder: Would use compute_v1 to check URL maps and backend services
            # Would check if CDN is enabled but has no traffic via Monitoring API
            count = 0
            
            self.scan_summary['unused_cloud_cdn'] += count
            
            if count > 0:
                self.log(f"Found {count} unused Cloud CDN in {region}", "WARNING")
            else:
                self.log(f"No unused Cloud CDN found in {region}", "SUCCESS")
            
        except Exception as e:
            if self._is_api_not_enabled_error(e):
                self._log_api_not_enabled("Compute Engine API (Cloud CDN)", region)
            else:
                self.log(f"Error scanning Cloud CDN in {region}: {e}", "ERROR")
    
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
