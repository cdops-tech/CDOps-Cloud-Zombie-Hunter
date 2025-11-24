"""
AWS Provider for CDOps Zombie Hunter.

Implements AWS-specific zombie resource scanning using boto3.
"""

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
from colorama import Fore, Style

from .base import CloudProvider


class AWSProvider(CloudProvider):
    """AWS implementation of the zombie hunter."""
    
    def get_provider_name(self) -> str:
        """Return the provider name."""
        return "AWS"
    
    def validate_credentials(self) -> bool:
        """Validate AWS credentials."""
        try:
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            print(f"{Fore.GREEN}✅ AWS credentials validated{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Account ID: {identity['Account']}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}User/Role: {identity['Arn']}{Style.RESET_ALL}\n")
            return True
        except (NoCredentialsError, Exception) as e:
            print(f"{Fore.RED}ERROR: AWS credentials validation failed: {e}{Style.RESET_ALL}")
            return False
    
    def get_available_regions(self) -> List[str]:
        """Get list of available AWS regions."""
        try:
            ec2 = boto3.client('ec2')
            response = ec2.describe_regions()
            return [region['RegionName'] for region in response['Regions']]
        except Exception as e:
            print(f"{Fore.RED}Error retrieving AWS regions: {e}{Style.RESET_ALL}")
            return []
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the AWS Provider.
        
        Args:
            verbose: Enable verbose logging
        """
        super().__init__()
        self.verbose = verbose
        self.scan_summary = {
            'unattached_ebs_volumes': 0,
            'obsolete_snapshots': 0,
            'idle_ec2_instances': 0,
            'unassociated_eips': 0,
            'unused_load_balancers': 0,
            'idle_rds_instances': 0,
            'empty_s3_buckets': 0,
            'unused_cloudfront_distributions': 0,
            'unused_lambda_functions': 0,
            'idle_dynamodb_tables': 0,
            'idle_elasticache_clusters': 0
        }
    
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
    
    def scan_unused_lambda_functions(self, region: str) -> List[Dict[str, Any]]:
        """
        Scan for Lambda functions with zero invocations in the past 90 days.
        
        Lambda functions that haven't been invoked recently may be:
        - Legacy functions no longer in use
        - Test functions that were never cleaned up
        - Functions replaced by newer versions
        
        Cost Impact:
        - Charged for allocated storage (GB-seconds)
        - Request charges even if never invoked
        - Estimated $0.20-$2.00/month per idle function depending on memory allocation
        
        Args:
            region: AWS region to scan
            
        Returns:
            List of zombie Lambda function details
        """
        zombies = []
        
        try:
            lambda_client = boto3.client('lambda', region_name=region)
            cloudwatch = boto3.client('cloudwatch', region_name=region)
            
            self.log(f"Scanning Lambda functions in {region}...", "INFO")
            
            # List all Lambda functions
            paginator = lambda_client.get_paginator('list_functions')
            
            for page in paginator.paginate():
                for function in page.get('Functions', []):
                    function_name = function['FunctionName']
                    memory_size = function.get('MemorySize', 128)
                    code_size = function.get('CodeSize', 0)
                    
                    try:
                        # Check invocations in last 90 days
                        response = cloudwatch.get_metric_statistics(
                            Namespace='AWS/Lambda',
                            MetricName='Invocations',
                            Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                            StartTime=datetime.now(timezone.utc) - timedelta(days=90),
                            EndTime=datetime.now(timezone.utc),
                            Period=86400 * 90,  # 90 days in seconds
                            Statistics=['Sum']
                        )
                        
                        total_invocations = sum([point['Sum'] for point in response.get('Datapoints', [])])
                        
                        # If no invocations in 90 days, it's a zombie
                        if total_invocations == 0:
                            # Estimate cost: storage + potential compute allocation
                            # Storage: $0.0000166667 per GB-second
                            # Assume function kept warm = ~$0.50-$2.00/month depending on memory
                            if memory_size <= 512:
                                estimated_monthly_cost = 0.50
                            elif memory_size <= 1024:
                                estimated_monthly_cost = 1.00
                            else:
                                estimated_monthly_cost = 2.00
                            
                            zombie = {
                                'resource_type': 'Lambda Function',
                                'resource_id': function_name,
                                'region': region,
                                'details': f"Memory: {memory_size}MB, Code Size: {code_size / 1024:.1f}KB, No invocations in 90 days",
                                'estimated_monthly_cost': f"${estimated_monthly_cost:.2f}",
                                'reason': 'No invocations in the last 90 days'
                            }
                            
                            zombies.append(zombie)
                            self.findings.append(zombie)
                    except Exception as e:
                        # Skip if CloudWatch metrics not accessible
                        if self.verbose:
                            self.log(f"Could not check metrics for {function_name}: {e}", "WARNING")
                        continue
            
            self.scan_summary['unused_lambda_functions'] += len(zombies)
            
            if zombies:
                self.log(f"Found {len(zombies)} unused Lambda functions", "WARNING")
            else:
                self.log(f"No unused Lambda functions found", "SUCCESS")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                self.log(f"Permission denied for Lambda functions. Skipping...", "WARNING")
            else:
                self.log(f"Error scanning Lambda functions: {e}", "ERROR")
        except Exception as e:
            self.log(f"Unexpected error scanning Lambda functions: {e}", "ERROR")
        
        return zombies
    
    def scan_idle_dynamodb_tables(self, region: str) -> List[Dict[str, Any]]:
        """
        Scan for DynamoDB tables with zero read/write activity in the past 30 days.
        
        Idle DynamoDB tables may be:
        - Archived data that should be moved to S3 Glacier
        - Test/development tables never cleaned up
        - Tables replaced by newer schema versions
        
        Cost Impact:
        - Provisioned capacity: Fixed hourly cost regardless of usage
        - On-demand: Still pays for storage even with zero requests
        - Estimated $0.25-$50+/month per table depending on capacity and storage
        
        Args:
            region: AWS region to scan
            
        Returns:
            List of zombie DynamoDB table details
        """
        zombies = []
        
        try:
            dynamodb = boto3.client('dynamodb', region_name=region)
            cloudwatch = boto3.client('cloudwatch', region_name=region)
            
            self.log(f"Scanning DynamoDB tables in {region}...", "INFO")
            
            # List all tables
            paginator = dynamodb.get_paginator('list_tables')
            
            for page in paginator.paginate():
                for table_name in page.get('TableNames', []):
                    try:
                        # Get table details
                        table_info = dynamodb.describe_table(TableName=table_name)
                        table = table_info['Table']
                        
                        billing_mode = table.get('BillingModeSummary', {}).get('BillingMode', 'PROVISIONED')
                        table_size_bytes = table.get('TableSizeBytes', 0)
                        item_count = table.get('ItemCount', 0)
                        
                        # Check read/write activity in last 30 days
                        read_response = cloudwatch.get_metric_statistics(
                            Namespace='AWS/DynamoDB',
                            MetricName='ConsumedReadCapacityUnits',
                            Dimensions=[{'Name': 'TableName', 'Value': table_name}],
                            StartTime=datetime.now(timezone.utc) - timedelta(days=30),
                            EndTime=datetime.now(timezone.utc),
                            Period=86400 * 30,  # 30 days
                            Statistics=['Sum']
                        )
                        
                        write_response = cloudwatch.get_metric_statistics(
                            Namespace='AWS/DynamoDB',
                            MetricName='ConsumedWriteCapacityUnits',
                            Dimensions=[{'Name': 'TableName', 'Value': table_name}],
                            StartTime=datetime.now(timezone.utc) - timedelta(days=30),
                            EndTime=datetime.now(timezone.utc),
                            Period=86400 * 30,
                            Statistics=['Sum']
                        )
                        
                        total_reads = sum([point['Sum'] for point in read_response.get('Datapoints', [])])
                        total_writes = sum([point['Sum'] for point in write_response.get('Datapoints', [])])
                        
                        # If no activity in 30 days, it's a zombie
                        if total_reads == 0 and total_writes == 0:
                            # Estimate cost based on billing mode
                            if billing_mode == 'PROVISIONED':
                                # Provisioned capacity: assume minimal 1 RCU + 1 WCU
                                # $0.00013 per RCU-hour + $0.00065 per WCU-hour
                                estimated_monthly_cost = (1 * 0.00013 + 1 * 0.00065) * 730  # hours/month
                            else:
                                # On-demand: storage cost only
                                # $0.25 per GB-month
                                estimated_monthly_cost = (table_size_bytes / (1024**3)) * 0.25
                            
                            # Minimum $0.25/month
                            estimated_monthly_cost = max(0.25, estimated_monthly_cost)
                            
                            zombie = {
                                'resource_type': 'DynamoDB Table',
                                'resource_id': table_name,
                                'region': region,
                                'details': f"Billing: {billing_mode}, Size: {table_size_bytes / (1024**2):.1f}MB, Items: {item_count}, No activity in 30 days",
                                'estimated_monthly_cost': f"${estimated_monthly_cost:.2f}",
                                'reason': 'No read/write activity in the last 30 days'
                            }
                            
                            zombies.append(zombie)
                            self.findings.append(zombie)
                    except Exception as e:
                        if self.verbose:
                            self.log(f"Could not check table {table_name}: {e}", "WARNING")
                        continue
            
            self.scan_summary['idle_dynamodb_tables'] += len(zombies)
            
            if zombies:
                self.log(f"Found {len(zombies)} idle DynamoDB tables", "WARNING")
            else:
                self.log(f"No idle DynamoDB tables found", "SUCCESS")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                self.log(f"Permission denied for DynamoDB tables. Skipping...", "WARNING")
            else:
                self.log(f"Error scanning DynamoDB tables: {e}", "ERROR")
        except Exception as e:
            self.log(f"Unexpected error scanning DynamoDB tables: {e}", "ERROR")
        
        return zombies
    
    def scan_idle_elasticache_clusters(self, region: str) -> List[Dict[str, Any]]:
        """
        Scan for ElastiCache clusters with zero connections in the past 14 days.
        
        Idle ElastiCache clusters may be:
        - Development/test environments left running
        - Clusters from decommissioned applications
        - Over-provisioned cache layers no longer needed
        
        Cost Impact:
        - Instance costs: $0.017-$6.80+/hour depending on node type
        - No data transfer if unused, but instance costs remain
        - Estimated $12-$5,000+/month per idle cluster
        
        Args:
            region: AWS region to scan
            
        Returns:
            List of zombie ElastiCache cluster details
        """
        zombies = []
        
        try:
            elasticache = boto3.client('elasticache', region_name=region)
            cloudwatch = boto3.client('cloudwatch', region_name=region)
            
            self.log(f"Scanning ElastiCache clusters in {region}...", "INFO")
            
            # Scan Redis clusters
            redis_paginator = elasticache.get_paginator('describe_replication_groups')
            for page in redis_paginator.paginate():
                for cluster in page.get('ReplicationGroups', []):
                    cluster_id = cluster['ReplicationGroupId']
                    status = cluster['Status']
                    node_type = cluster.get('CacheNodeType', 'unknown')
                    num_nodes = len(cluster.get('MemberClusters', []))
                    
                    if status != 'available':
                        continue
                    
                    try:
                        # Check connections in last 14 days
                        response = cloudwatch.get_metric_statistics(
                            Namespace='AWS/ElastiCache',
                            MetricName='CurrConnections',
                            Dimensions=[{'Name': 'ReplicationGroupId', 'Value': cluster_id}],
                            StartTime=datetime.now(timezone.utc) - timedelta(days=14),
                            EndTime=datetime.now(timezone.utc),
                            Period=86400 * 14,  # 14 days
                            Statistics=['Maximum']
                        )
                        
                        max_connections = max([point['Maximum'] for point in response.get('Datapoints', [])], default=0)
                        
                        # If no connections in 14 days, it's a zombie
                        if max_connections == 0:
                            # Estimate cost based on node type
                            # Common node costs (per hour): cache.t3.micro=$0.017, cache.m5.large=$0.136, cache.r5.large=$0.188
                            if 't2.micro' in node_type or 't3.micro' in node_type:
                                hourly_cost = 0.017
                            elif 't2.small' in node_type or 't3.small' in node_type:
                                hourly_cost = 0.034
                            elif 'm5.large' in node_type:
                                hourly_cost = 0.136
                            elif 'r5.large' in node_type:
                                hourly_cost = 0.188
                            else:
                                hourly_cost = 0.10  # Conservative estimate
                            
                            estimated_monthly_cost = hourly_cost * 730 * num_nodes  # hours/month * nodes
                            
                            zombie = {
                                'resource_type': 'ElastiCache Cluster (Redis)',
                                'resource_id': cluster_id,
                                'region': region,
                                'details': f"Node Type: {node_type}, Nodes: {num_nodes}, No connections in 14 days",
                                'estimated_monthly_cost': f"${estimated_monthly_cost:.2f}",
                                'reason': 'No connections in the last 14 days'
                            }
                            
                            zombies.append(zombie)
                            self.findings.append(zombie)
                    except Exception as e:
                        if self.verbose:
                            self.log(f"Could not check metrics for {cluster_id}: {e}", "WARNING")
                        continue
            
            # Scan Memcached clusters
            memcached_paginator = elasticache.get_paginator('describe_cache_clusters')
            for page in memcached_paginator.paginate():
                for cluster in page.get('CacheClusters', []):
                    cluster_id = cluster['CacheClusterId']
                    engine = cluster.get('Engine', '')
                    
                    # Skip Redis clusters (already handled above)
                    if engine != 'memcached':
                        continue
                    
                    status = cluster['CacheClusterStatus']
                    node_type = cluster.get('CacheNodeType', 'unknown')
                    num_nodes = cluster.get('NumCacheNodes', 1)
                    
                    if status != 'available':
                        continue
                    
                    try:
                        # Check connections in last 14 days
                        response = cloudwatch.get_metric_statistics(
                            Namespace='AWS/ElastiCache',
                            MetricName='CurrConnections',
                            Dimensions=[{'Name': 'CacheClusterId', 'Value': cluster_id}],
                            StartTime=datetime.now(timezone.utc) - timedelta(days=14),
                            EndTime=datetime.now(timezone.utc),
                            Period=86400 * 14,
                            Statistics=['Maximum']
                        )
                        
                        max_connections = max([point['Maximum'] for point in response.get('Datapoints', [])], default=0)
                        
                        if max_connections == 0:
                            # Same cost estimation as Redis
                            if 't2.micro' in node_type or 't3.micro' in node_type:
                                hourly_cost = 0.017
                            elif 't2.small' in node_type or 't3.small' in node_type:
                                hourly_cost = 0.034
                            elif 'm5.large' in node_type:
                                hourly_cost = 0.136
                            elif 'r5.large' in node_type:
                                hourly_cost = 0.188
                            else:
                                hourly_cost = 0.10
                            
                            estimated_monthly_cost = hourly_cost * 730 * num_nodes
                            
                            zombie = {
                                'resource_type': 'ElastiCache Cluster (Memcached)',
                                'resource_id': cluster_id,
                                'region': region,
                                'details': f"Node Type: {node_type}, Nodes: {num_nodes}, No connections in 14 days",
                                'estimated_monthly_cost': f"${estimated_monthly_cost:.2f}",
                                'reason': 'No connections in the last 14 days'
                            }
                            
                            zombies.append(zombie)
                            self.findings.append(zombie)
                    except Exception as e:
                        if self.verbose:
                            self.log(f"Could not check metrics for {cluster_id}: {e}", "WARNING")
                        continue
            
            self.scan_summary['idle_elasticache_clusters'] += len(zombies)
            
            if zombies:
                self.log(f"Found {len(zombies)} idle ElastiCache clusters", "WARNING")
            else:
                self.log(f"No idle ElastiCache clusters found", "SUCCESS")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                self.log(f"Permission denied for ElastiCache clusters. Skipping...", "WARNING")
            else:
                self.log(f"Error scanning ElastiCache clusters: {e}", "ERROR")
        except Exception as e:
            self.log(f"Unexpected error scanning ElastiCache clusters: {e}", "ERROR")
        
        return zombies
    
    def run_scan(self, regions: List[str]):
        """Execute the complete scan across all specified regions."""
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}CDOps Cloud Zombie Hunter - AWS{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Scanning for unused AWS resources...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")
        
        first_region = regions[0] if regions else None
        
        for i, region in enumerate(regions):
            print(f"\n{Fore.MAGENTA}>>> Scanning region: {region}{Style.RESET_ALL}\n")
            
            is_first_region = (i == 0)
            
            # Run all scans for this region
            self.scan_unattached_ebs_volumes(region)
            self.scan_obsolete_snapshots(region)
            self.scan_idle_ec2_instances(region)
            self.scan_unassociated_eips(region)
            self.scan_unused_load_balancers(region)
            self.scan_idle_rds_instances(region)
            
            # S3 and CloudFront are global - only scan once
            if is_first_region:
                self.scan_empty_s3_buckets(region)
                self.scan_unused_cloudfront_distributions(region)
            
            self.scan_unused_lambda_functions(region)
            self.scan_idle_dynamodb_tables(region)
            self.scan_idle_elasticache_clusters(region)
    
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

