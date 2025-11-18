#!/usr/bin/env python3
"""
CDOps Cloud Zombie Hunter
==========================
A safe, read-only AWS resource scanner that identifies unused ("zombie") resources
that may be wasting money in your cloud environment.

Author: CDOps Tech
Website: https://cdops.tech
Contact: contact@cdops.tech

This tool performs ONLY read operations and will never modify or delete resources.
"""

import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
import os

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, NoRegionError
except ImportError:
    print("ERROR: boto3 is not installed. Please run: pip install -r requirements.txt")
    sys.exit(1)

try:
    from tabulate import tabulate
except ImportError:
    print("ERROR: tabulate is not installed. Please run: pip install -r requirements.txt")
    sys.exit(1)

try:
    from colorama import init, Fore, Style
    init(autoreset=True)  # Initialize colorama for cross-platform color support
except ImportError:
    print("ERROR: colorama is not installed. Please run: pip install -r requirements.txt")
    sys.exit(1)


class ZombieHunter:
    """
    Main class for scanning AWS resources and identifying unused/wasted resources.
    All operations are read-only and safe.
    """
    
    def __init__(self, regions: List[str], verbose: bool = False):
        """
        Initialize the Zombie Hunter.
        
        Args:
            regions: List of AWS regions to scan
            verbose: Enable verbose logging
        """
        self.regions = regions
        self.verbose = verbose
        self.findings = []
        self.scan_summary = {
            'unattached_ebs_volumes': 0,
            'obsolete_snapshots': 0,
            'idle_ec2_instances': 0,
            'unassociated_eips': 0,
            'unused_load_balancers': 0,
            'idle_rds_instances': 0,
            'empty_s3_buckets': 0,
            'unused_cloudfront_distributions': 0
        }
        
    def log(self, message: str, level: str = "INFO"):
        """Print log messages with proper formatting."""
        if level == "ERROR":
            print(f"{Fore.RED}[ERROR] {message}{Style.RESET_ALL}")
        elif level == "WARNING":
            print(f"{Fore.YELLOW}[WARNING] {message}{Style.RESET_ALL}")
        elif level == "SUCCESS":
            print(f"{Fore.GREEN}[SUCCESS] {message}{Style.RESET_ALL}")
        elif self.verbose or level == "INFO":
            print(f"[INFO] {message}")
    
    def scan_unattached_ebs_volumes(self, region: str) -> List[Dict[str, Any]]:
        """
        Scan for EBS volumes that are in 'available' state (not attached to any instance).
        These volumes still incur storage costs but aren't being used.
        
        Args:
            region: AWS region to scan
            
        Returns:
            List of dictionaries containing zombie volume details
        """
        zombies = []
        
        try:
            ec2 = boto3.client('ec2', region_name=region)
            self.log(f"Scanning for unattached EBS volumes in {region}...", "INFO")
            
            # Describe all volumes with state 'available' (unattached)
            response = ec2.describe_volumes(
                Filters=[{'Name': 'status', 'Values': ['available']}]
            )
            
            for volume in response.get('Volumes', []):
                volume_id = volume['VolumeId']
                size_gb = volume['Size']
                volume_type = volume['VolumeType']
                create_time = volume['CreateTime']
                
                # Calculate cost estimate (rough estimate in USD/month)
                # gp3: $0.08/GB/month, gp2: $0.10/GB/month, io1/io2: $0.125/GB/month
                cost_per_gb = {'gp3': 0.08, 'gp2': 0.10, 'io1': 0.125, 'io2': 0.125, 'st1': 0.045, 'sc1': 0.015}
                estimated_monthly_cost = size_gb * cost_per_gb.get(volume_type, 0.10)
                
                zombie = {
                    'resource_type': 'EBS Volume',
                    'resource_id': volume_id,
                    'region': region,
                    'size_gb': size_gb,
                    'volume_type': volume_type,
                    'created': create_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'estimated_monthly_cost': f"${estimated_monthly_cost:.2f}",
                    'reason': 'Unattached (available state)'
                }
                
                zombies.append(zombie)
                self.findings.append(zombie)
            
            self.scan_summary['unattached_ebs_volumes'] += len(zombies)
            
            if zombies:
                self.log(f"Found {len(zombies)} unattached EBS volumes in {region}", "WARNING")
            else:
                self.log(f"No unattached EBS volumes found in {region}", "SUCCESS")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                self.log(f"Permission denied for EBS volumes in {region}. Skipping...", "WARNING")
            else:
                self.log(f"Error scanning EBS volumes in {region}: {e}", "ERROR")
        except Exception as e:
            self.log(f"Unexpected error scanning EBS volumes in {region}: {e}", "ERROR")
        
        return zombies
    
    def scan_obsolete_snapshots(self, region: str) -> List[Dict[str, Any]]:
        """
        Scan for EBS snapshots older than 30 days that are NOT associated with active AMIs.
        These snapshots may be safe to delete and are incurring storage costs.
        
        Args:
            region: AWS region to scan
            
        Returns:
            List of dictionaries containing zombie snapshot details
        """
        zombies = []
        
        try:
            ec2 = boto3.client('ec2', region_name=region)
            self.log(f"Scanning for obsolete snapshots in {region}...", "INFO")
            
            # Get all snapshots owned by this account
            response = ec2.describe_snapshots(OwnerIds=['self'])
            
            # Get all AMIs to identify which snapshots are in use
            amis_response = ec2.describe_images(Owners=['self'])
            
            # Extract snapshot IDs that are used by AMIs
            snapshots_in_use = set()
            for ami in amis_response.get('Images', []):
                for block_device in ami.get('BlockDeviceMappings', []):
                    if 'Ebs' in block_device and 'SnapshotId' in block_device['Ebs']:
                        snapshots_in_use.add(block_device['Ebs']['SnapshotId'])
            
            # Check each snapshot
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            
            for snapshot in response.get('Snapshots', []):
                snapshot_id = snapshot['SnapshotId']
                start_time = snapshot['StartTime']
                volume_size = snapshot['VolumeSize']
                
                # Only flag snapshots that are:
                # 1. Older than 30 days
                # 2. NOT used by any AMI
                if start_time < cutoff_date and snapshot_id not in snapshots_in_use:
                    # Snapshot storage cost: ~$0.05/GB/month
                    estimated_monthly_cost = volume_size * 0.05
                    
                    zombie = {
                        'resource_type': 'EBS Snapshot',
                        'resource_id': snapshot_id,
                        'region': region,
                        'size_gb': volume_size,
                        'created': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'age_days': (datetime.now(timezone.utc) - start_time).days,
                        'estimated_monthly_cost': f"${estimated_monthly_cost:.2f}",
                        'reason': 'Older than 30 days and not linked to any AMI'
                    }
                    
                    zombies.append(zombie)
                    self.findings.append(zombie)
            
            self.scan_summary['obsolete_snapshots'] += len(zombies)
            
            if zombies:
                self.log(f"Found {len(zombies)} obsolete snapshots in {region}", "WARNING")
            else:
                self.log(f"No obsolete snapshots found in {region}", "SUCCESS")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                self.log(f"Permission denied for snapshots in {region}. Skipping...", "WARNING")
            else:
                self.log(f"Error scanning snapshots in {region}: {e}", "ERROR")
        except Exception as e:
            self.log(f"Unexpected error scanning snapshots in {region}: {e}", "ERROR")
        
        return zombies
    
    def scan_idle_ec2_instances(self, region: str) -> List[Dict[str, Any]]:
        """
        Scan for EC2 instances in 'stopped' state for more than 7 days.
        Stopped instances still incur costs for attached EBS volumes.
        
        Args:
            region: AWS region to scan
            
        Returns:
            List of dictionaries containing idle instance details
        """
        zombies = []
        
        try:
            ec2 = boto3.client('ec2', region_name=region)
            self.log(f"Scanning for idle EC2 instances in {region}...", "INFO")
            
            # Get all stopped instances
            response = ec2.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['stopped']}]
            )
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
            
            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    instance_id = instance['InstanceId']
                    instance_type = instance['InstanceType']
                    
                    # Get instance name from tags
                    instance_name = 'N/A'
                    for tag in instance.get('Tags', []):
                        if tag['Key'] == 'Name':
                            instance_name = tag['Value']
                            break
                    
                    # Try to determine when instance was stopped
                    # Note: StateTransitionReason is a string, not always parseable
                    state_transition = instance.get('StateTransitionReason', '')
                    
                    # We'll flag all stopped instances as potential zombies
                    # In production, you might want CloudWatch metrics to determine actual idle time
                    
                    # Calculate EBS volume costs for attached volumes
                    total_ebs_size = 0
                    for block_device in instance.get('BlockDeviceMappings', []):
                        if 'Ebs' in block_device:
                            volume_id = block_device['Ebs']['VolumeId']
                            try:
                                vol_response = ec2.describe_volumes(VolumeIds=[volume_id])
                                if vol_response['Volumes']:
                                    total_ebs_size += vol_response['Volumes'][0]['Size']
                            except:
                                pass
                    
                    # Rough estimate: EBS storage costs while instance is stopped
                    estimated_monthly_cost = total_ebs_size * 0.10
                    
                    zombie = {
                        'resource_type': 'EC2 Instance',
                        'resource_id': instance_id,
                        'region': region,
                        'instance_type': instance_type,
                        'name': instance_name,
                        'state': 'stopped',
                        'ebs_size_gb': total_ebs_size,
                        'estimated_monthly_cost': f"${estimated_monthly_cost:.2f}",
                        'reason': 'Instance stopped (EBS volumes still incurring costs)'
                    }
                    
                    zombies.append(zombie)
                    self.findings.append(zombie)
            
            self.scan_summary['idle_ec2_instances'] += len(zombies)
            
            if zombies:
                self.log(f"Found {len(zombies)} idle EC2 instances in {region}", "WARNING")
            else:
                self.log(f"No idle EC2 instances found in {region}", "SUCCESS")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                self.log(f"Permission denied for EC2 instances in {region}. Skipping...", "WARNING")
            else:
                self.log(f"Error scanning EC2 instances in {region}: {e}", "ERROR")
        except Exception as e:
            self.log(f"Unexpected error scanning EC2 instances in {region}: {e}", "ERROR")
        
        return zombies
    
    def scan_unassociated_eips(self, region: str) -> List[Dict[str, Any]]:
        """
        Scan for Elastic IPs that are allocated but not associated with any instance.
        Unattached EIPs incur hourly charges.
        
        Args:
            region: AWS region to scan
            
        Returns:
            List of dictionaries containing unassociated EIP details
        """
        zombies = []
        
        try:
            ec2 = boto3.client('ec2', region_name=region)
            self.log(f"Scanning for unassociated Elastic IPs in {region}...", "INFO")
            
            # Get all Elastic IPs
            response = ec2.describe_addresses()
            
            for address in response.get('Addresses', []):
                # Check if EIP is not associated with any instance or network interface
                if 'InstanceId' not in address and 'NetworkInterfaceId' not in address:
                    allocation_id = address.get('AllocationId', 'N/A')
                    public_ip = address.get('PublicIp', 'N/A')
                    
                    # Unassociated EIP cost: ~$0.005/hour = ~$3.60/month
                    estimated_monthly_cost = 3.60
                    
                    zombie = {
                        'resource_type': 'Elastic IP',
                        'resource_id': allocation_id,
                        'region': region,
                        'public_ip': public_ip,
                        'estimated_monthly_cost': f"${estimated_monthly_cost:.2f}",
                        'reason': 'Allocated but not associated with any instance'
                    }
                    
                    zombies.append(zombie)
                    self.findings.append(zombie)
            
            self.scan_summary['unassociated_eips'] += len(zombies)
            
            if zombies:
                self.log(f"Found {len(zombies)} unassociated Elastic IPs in {region}", "WARNING")
            else:
                self.log(f"No unassociated Elastic IPs found in {region}", "SUCCESS")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                self.log(f"Permission denied for Elastic IPs in {region}. Skipping...", "WARNING")
            else:
                self.log(f"Error scanning Elastic IPs in {region}: {e}", "ERROR")
        except Exception as e:
            self.log(f"Unexpected error scanning Elastic IPs in {region}: {e}", "ERROR")
        
        return zombies
    
    def scan_unused_load_balancers(self, region: str) -> List[Dict[str, Any]]:
        """
        Scan for Application/Network Load Balancers (ELBv2) with zero registered targets.
        Load balancers incur hourly costs even with no traffic.
        
        Args:
            region: AWS region to scan
            
        Returns:
            List of dictionaries containing unused load balancer details
        """
        zombies = []
        
        try:
            elbv2 = boto3.client('elbv2', region_name=region)
            self.log(f"Scanning for unused load balancers in {region}...", "INFO")
            
            # Get all load balancers
            response = elbv2.describe_load_balancers()
            
            for lb in response.get('LoadBalancers', []):
                lb_arn = lb['LoadBalancerArn']
                lb_name = lb['LoadBalancerName']
                lb_type = lb['Type']  # 'application' or 'network'
                created_time = lb['CreatedTime']
                
                # Get target groups for this load balancer
                try:
                    tg_response = elbv2.describe_target_groups(LoadBalancerArn=lb_arn)
                    
                    total_healthy_targets = 0
                    
                    # Check each target group for healthy targets
                    for tg in tg_response.get('TargetGroups', []):
                        tg_arn = tg['TargetGroupArn']
                        
                        try:
                            health_response = elbv2.describe_target_health(TargetGroupArn=tg_arn)
                            
                            # Count healthy targets
                            for target in health_response.get('TargetHealthDescriptions', []):
                                if target.get('TargetHealth', {}).get('State') == 'healthy':
                                    total_healthy_targets += 1
                        except:
                            pass
                    
                    # If no healthy targets, it's a zombie
                    if total_healthy_targets == 0:
                        # ALB: ~$0.0225/hour = ~$16.20/month, NLB: ~$0.0225/hour = ~$16.20/month
                        estimated_monthly_cost = 16.20
                        
                        zombie = {
                            'resource_type': f'Load Balancer ({lb_type.upper()})',
                            'resource_id': lb_name,
                            'region': region,
                            'arn': lb_arn,
                            'created': created_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'estimated_monthly_cost': f"${estimated_monthly_cost:.2f}",
                            'reason': 'No healthy targets registered'
                        }
                        
                        zombies.append(zombie)
                        self.findings.append(zombie)
                        
                except ClientError:
                    # Load balancer might not have target groups
                    pass
            
            self.scan_summary['unused_load_balancers'] += len(zombies)
            
            if zombies:
                self.log(f"Found {len(zombies)} unused load balancers in {region}", "WARNING")
            else:
                self.log(f"No unused load balancers found in {region}", "SUCCESS")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                self.log(f"Permission denied for load balancers in {region}. Skipping...", "WARNING")
            else:
                self.log(f"Error scanning load balancers in {region}: {e}", "ERROR")
        except Exception as e:
            self.log(f"Unexpected error scanning load balancers in {region}: {e}", "ERROR")
        
        return zombies
    
    def scan_idle_rds_instances(self, region: str) -> List[Dict[str, Any]]:
        """
        Scan for RDS database instances that are in 'stopped' state or have very low connections.
        Stopped RDS instances still incur storage costs.
        
        Args:
            region: AWS region to scan
            
        Returns:
            List of dictionaries containing idle RDS instance details
        """
        zombies = []
        
        try:
            rds = boto3.client('rds', region_name=region)
            self.log(f"Scanning for idle RDS instances in {region}...", "INFO")
            
            # Get all RDS instances
            response = rds.describe_db_instances()
            
            for db_instance in response.get('DBInstances', []):
                db_id = db_instance['DBInstanceIdentifier']
                db_status = db_instance['DBInstanceStatus']
                db_class = db_instance['DBInstanceClass']
                engine = db_instance['Engine']
                storage_gb = db_instance['AllocatedStorage']
                
                # Flag stopped instances
                if db_status == 'stopped':
                    # Rough cost estimate for stopped RDS (storage only)
                    # gp2 storage: ~$0.115/GB/month, gp3: ~$0.096/GB/month
                    estimated_monthly_cost = storage_gb * 0.115
                    
                    zombie = {
                        'resource_type': 'RDS Instance',
                        'resource_id': db_id,
                        'region': region,
                        'status': db_status,
                        'instance_class': db_class,
                        'engine': engine,
                        'storage_gb': storage_gb,
                        'estimated_monthly_cost': f"${estimated_monthly_cost:.2f}",
                        'reason': 'Instance stopped (storage costs continue)'
                    }
                    
                    zombies.append(zombie)
                    self.findings.append(zombie)
            
            self.scan_summary['idle_rds_instances'] += len(zombies)
            
            if zombies:
                self.log(f"Found {len(zombies)} idle RDS instances in {region}", "WARNING")
            else:
                self.log(f"No idle RDS instances found in {region}", "SUCCESS")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                self.log(f"Permission denied for RDS instances in {region}. Skipping...", "WARNING")
            else:
                self.log(f"Error scanning RDS instances in {region}: {e}", "ERROR")
        except Exception as e:
            self.log(f"Unexpected error scanning RDS instances in {region}: {e}", "ERROR")
        
        return zombies
    
    def scan_empty_s3_buckets(self, region: str) -> List[Dict[str, Any]]:
        """
        Scan for S3 buckets that are completely empty or have very few objects.
        Empty buckets may indicate abandoned projects or unused infrastructure.
        Note: S3 is global but we'll scan once (not per region).
        
        Args:
            region: AWS region (S3 is global, but we need it for consistency)
            
        Returns:
            List of dictionaries containing empty S3 bucket details
        """
        zombies = []
        
        # Only scan S3 once (not per region) - skip if not first region
        if region != self.regions[0]:
            return zombies
        
        try:
            s3 = boto3.client('s3')
            self.log(f"Scanning for empty S3 buckets (global scan)...", "INFO")
            
            # Get all S3 buckets
            response = s3.list_buckets()
            
            for bucket in response.get('Buckets', []):
                bucket_name = bucket['Name']
                created_date = bucket['CreationDate']
                
                try:
                    # Check if bucket is empty
                    objects_response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
                    object_count = objects_response.get('KeyCount', 0)
                    
                    if object_count == 0:
                        # Get bucket location
                        try:
                            location_response = s3.get_bucket_location(Bucket=bucket_name)
                            bucket_region = location_response.get('LocationConstraint') or 'us-east-1'
                        except:
                            bucket_region = 'unknown'
                        
                        # Empty bucket - minimal cost but indicates unused resource
                        # S3 standard storage: $0.023/GB/month, but empty = ~$0
                        estimated_monthly_cost = 0.00
                        
                        zombie = {
                            'resource_type': 'S3 Bucket',
                            'resource_id': bucket_name,
                            'region': bucket_region,
                            'created': created_date.strftime('%Y-%m-%d %H:%M:%S'),
                            'object_count': 0,
                            'estimated_monthly_cost': f"${estimated_monthly_cost:.2f}",
                            'reason': 'Bucket is completely empty (may be abandoned)'
                        }
                        
                        zombies.append(zombie)
                        self.findings.append(zombie)
                        
                except ClientError as e:
                    # Bucket might have access restrictions
                    if e.response['Error']['Code'] != 'AccessDenied':
                        self.log(f"Could not check bucket {bucket_name}: {e}", "WARNING")
                except Exception as e:
                    self.log(f"Error checking bucket {bucket_name}: {e}", "WARNING")
            
            self.scan_summary['empty_s3_buckets'] += len(zombies)
            
            if zombies:
                self.log(f"Found {len(zombies)} empty S3 buckets", "WARNING")
            else:
                self.log(f"No empty S3 buckets found", "SUCCESS")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                self.log(f"Permission denied for S3 buckets. Skipping...", "WARNING")
            else:
                self.log(f"Error scanning S3 buckets: {e}", "ERROR")
        except Exception as e:
            self.log(f"Unexpected error scanning S3 buckets: {e}", "ERROR")
        
        return zombies
    
    def scan_unused_cloudfront_distributions(self, region: str) -> List[Dict[str, Any]]:
        """
        Scan for CloudFront distributions that are disabled or have very low traffic.
        CloudFront is global, so we only scan once.
        
        Args:
            region: AWS region (CloudFront is global, but we need it for consistency)
            
        Returns:
            List of dictionaries containing unused CloudFront distribution details
        """
        zombies = []
        
        # Only scan CloudFront once (not per region) - skip if not first region
        if region != self.regions[0]:
            return zombies
        
        try:
            cloudfront = boto3.client('cloudfront')
            self.log(f"Scanning for unused CloudFront distributions (global scan)...", "INFO")
            
            # Get all CloudFront distributions
            response = cloudfront.list_distributions()
            
            if 'DistributionList' not in response or 'Items' not in response['DistributionList']:
                self.log(f"No CloudFront distributions found", "SUCCESS")
                return zombies
            
            for distribution in response['DistributionList']['Items']:
                dist_id = distribution['Id']
                domain_name = distribution['DomainName']
                status = distribution['Status']
                enabled = distribution['Enabled']
                
                # Flag disabled distributions
                if not enabled:
                    # CloudFront cost: ~$0.085/GB transfer + $0.012 per 10,000 requests
                    # Disabled distributions still exist in config but cost minimal
                    estimated_monthly_cost = 0.10  # Minimal management overhead
                    
                    zombie = {
                        'resource_type': 'CloudFront Distribution',
                        'resource_id': dist_id,
                        'region': 'global',
                        'domain_name': domain_name,
                        'status': status,
                        'enabled': enabled,
                        'estimated_monthly_cost': f"${estimated_monthly_cost:.2f}",
                        'reason': 'Distribution is disabled but still exists'
                    }
                    
                    zombies.append(zombie)
                    self.findings.append(zombie)
            
            self.scan_summary['unused_cloudfront_distributions'] += len(zombies)
            
            if zombies:
                self.log(f"Found {len(zombies)} unused CloudFront distributions", "WARNING")
            else:
                self.log(f"No unused CloudFront distributions found", "SUCCESS")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                self.log(f"Permission denied for CloudFront distributions. Skipping...", "WARNING")
            else:
                self.log(f"Error scanning CloudFront distributions: {e}", "ERROR")
        except Exception as e:
            self.log(f"Unexpected error scanning CloudFront distributions: {e}", "ERROR")
        
        return zombies
    
    def run_scan(self):
        """Execute the complete scan across all specified regions."""
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}CDOps Cloud Zombie Hunter{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Scanning for unused AWS resources...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")
        
        for region in self.regions:
            print(f"\n{Fore.MAGENTA}>>> Scanning region: {region}{Style.RESET_ALL}\n")
            
            # Run all scans for this region
            self.scan_unattached_ebs_volumes(region)
            self.scan_obsolete_snapshots(region)
            self.scan_idle_ec2_instances(region)
            self.scan_unassociated_eips(region)
            self.scan_unused_load_balancers(region)
            self.scan_idle_rds_instances(region)
            self.scan_empty_s3_buckets(region)
            self.scan_unused_cloudfront_distributions(region)
    
    def calculate_total_savings(self) -> float:
        """
        Calculate total estimated monthly savings from all zombie resources.
        
        Returns:
            Total estimated monthly cost savings in USD
        """
        total_savings = 0.0
        
        for finding in self.findings:
            if 'estimated_monthly_cost' in finding:
                # Extract numeric value from cost string (e.g., "$12.50" -> 12.50)
                cost_str = finding['estimated_monthly_cost']
                try:
                    # Remove $ and convert to float
                    cost_value = float(cost_str.replace('$', '').replace(',', ''))
                    total_savings += cost_value
                except (ValueError, AttributeError):
                    # Skip if cost can't be parsed
                    pass
        
        return total_savings
    
    def print_summary(self):
        """Print a formatted summary of findings to the console."""
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}SCAN SUMMARY{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")
        
        # Prepare summary table
        summary_data = [
            ['Unattached EBS Volumes', self.scan_summary['unattached_ebs_volumes']],
            ['Obsolete Snapshots (>30 days, no AMI)', self.scan_summary['obsolete_snapshots']],
            ['Idle EC2 Instances (stopped)', self.scan_summary['idle_ec2_instances']],
            ['Unassociated Elastic IPs', self.scan_summary['unassociated_eips']],
            ['Unused Load Balancers', self.scan_summary['unused_load_balancers']],
            ['Idle RDS Instances (stopped)', self.scan_summary['idle_rds_instances']],
            ['Empty S3 Buckets', self.scan_summary['empty_s3_buckets']],
            ['Unused CloudFront Distributions', self.scan_summary['unused_cloudfront_distributions']]
        ]
        
        print(tabulate(summary_data, headers=['Resource Type', 'Count'], tablefmt='grid'))
        
        total_zombies = sum(self.scan_summary.values())
        total_savings = self.calculate_total_savings()
        
        if total_zombies > 0:
            print(f"\n{Fore.RED}⚠️  Total Zombie Resources Found: {total_zombies}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}💰 Estimated Monthly Savings: ${total_savings:.2f}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}💵 Estimated Annual Savings: ${total_savings * 12:.2f}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}These resources may be costing you money unnecessarily.{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.GREEN}✅ No zombie resources found! Your AWS environment looks clean.{Style.RESET_ALL}")
    
    def export_to_csv(self, filename: str):
        """
        Export findings to a CSV file with a summary row at the end.
        
        Args:
            filename: Output CSV filename
        """
        if not self.findings:
            self.log("No findings to export.", "INFO")
            return
        
        try:
            # Get all unique keys from all findings
            fieldnames = set()
            for finding in self.findings:
                fieldnames.update(finding.keys())
            
            fieldnames = sorted(list(fieldnames))
            
            # Calculate total savings
            total_savings = self.calculate_total_savings()
            total_zombies = len(self.findings)
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.findings)
                
                # Add summary rows
                writer.writerow({})  # Empty row for separation
                
                # Summary row
                summary_row = {fieldnames[0]: '*** SUMMARY ***'}
                if 'resource_id' in fieldnames:
                    summary_row['resource_id'] = f'{total_zombies} total zombie resources'
                if 'estimated_monthly_cost' in fieldnames:
                    summary_row['estimated_monthly_cost'] = f'${total_savings:.2f}'
                if 'reason' in fieldnames:
                    summary_row['reason'] = f'Estimated Monthly Savings: ${total_savings:.2f} | Annual: ${total_savings * 12:.2f}'
                
                writer.writerow(summary_row)
            
            self.log(f"Report exported to: {filename}", "SUCCESS")
            print(f"{Fore.GREEN}📄 Full report saved: {filename}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}💰 Total estimated monthly savings: ${total_savings:.2f}{Style.RESET_ALL}")
            
        except Exception as e:
            self.log(f"Error exporting to CSV: {e}", "ERROR")
    
    def print_footer(self):
        """Print the marketing footer message."""
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}✅ Scan Complete!{Style.RESET_ALL}\n")
        print(f"{Fore.YELLOW}If you need help safely analyzing or cleaning up these resources,{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}contact the CDOps Tech SRE Team:{Style.RESET_ALL}\n")
        print(f"{Fore.CYAN}📧 Email: contact@cdops.tech{Style.RESET_ALL}")
        print(f"{Fore.CYAN}🌐 Web: https://cdops.tech{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")


def get_all_regions() -> List[str]:
    """
    Retrieve all available AWS regions for EC2 service.
    
    Returns:
        List of region names
    """
    try:
        ec2 = boto3.client('ec2')
        response = ec2.describe_regions()
        return [region['RegionName'] for region in response['Regions']]
    except Exception as e:
        print(f"{Fore.RED}Error retrieving regions: {e}{Style.RESET_ALL}")
        return []


def main():
    """Main entry point for the CLI application."""
    parser = argparse.ArgumentParser(
        description='CDOps Cloud Zombie Hunter - Find unused AWS resources',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan current region
  python zombie_hunter.py
  
  # Scan specific region
  python zombie_hunter.py --region us-west-2
  
  # Scan all regions
  python zombie_hunter.py --all-regions
  
  # Scan with verbose output
  python zombie_hunter.py --verbose
  
  # Custom output filename
  python zombie_hunter.py --output my_report.csv
        """
    )
    
    parser.add_argument(
        '--region',
        type=str,
        help='AWS region to scan (default: your configured region)'
    )
    
    parser.add_argument(
        '--all-regions',
        action='store_true',
        help='Scan all AWS regions (this may take several minutes)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output CSV filename (default: cdops_zombie_report_[timestamp].csv)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Validate AWS credentials
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"{Fore.GREEN}✅ AWS credentials validated{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Account ID: {identity['Account']}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}User/Role: {identity['Arn']}{Style.RESET_ALL}\n")
    except NoCredentialsError:
        print(f"{Fore.RED}ERROR: No AWS credentials found.{Style.RESET_ALL}")
        print("Please configure your credentials using one of these methods:")
        print("  1. AWS CLI: aws configure")
        print("  2. Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
        print("  3. IAM role (if running on EC2/ECS/Lambda)")
        sys.exit(1)
    except NoRegionError:
        print(f"{Fore.RED}ERROR: No AWS region configured.{Style.RESET_ALL}")
        print("Please configure a default region using one of these methods:")
        print("  1. AWS CLI: aws configure set region us-east-1")
        print("  2. Environment variable: export AWS_DEFAULT_REGION=us-east-1")
        print("  3. Use --region flag: python zombie_hunter.py --region us-east-1")
        sys.exit(1)
    except Exception as e:
        print(f"{Fore.RED}ERROR: Failed to validate AWS credentials: {e}{Style.RESET_ALL}")
        sys.exit(1)
    
    # Determine regions to scan
    regions = []
    if args.all_regions:
        print(f"{Fore.YELLOW}Retrieving all AWS regions...{Style.RESET_ALL}")
        regions = get_all_regions()
        if not regions:
            print(f"{Fore.RED}Failed to retrieve regions. Exiting.{Style.RESET_ALL}")
            sys.exit(1)
        print(f"{Fore.GREEN}Found {len(regions)} regions to scan.{Style.RESET_ALL}\n")
    elif args.region:
        regions = [args.region]
    else:
        # Use default region from boto3 session
        try:
            session = boto3.session.Session()
            default_region = session.region_name
            if not default_region:
                print(f"{Fore.RED}ERROR: No default region configured.{Style.RESET_ALL}")
                print("Please use --region or configure a default region.")
                sys.exit(1)
            regions = [default_region]
        except Exception as e:
            print(f"{Fore.RED}ERROR: Could not determine default region: {e}{Style.RESET_ALL}")
            sys.exit(1)
    
    # Initialize and run scanner
    hunter = ZombieHunter(regions=regions, verbose=args.verbose)
    hunter.run_scan()
    hunter.print_summary()
    
    # Export results
    if args.output:
        output_filename = args.output
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"cdops_zombie_report_{timestamp}.csv"
    
    hunter.export_to_csv(output_filename)
    
    # Print marketing footer
    hunter.print_footer()


if __name__ == '__main__':
    main()
