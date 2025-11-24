#!/usr/bin/env python3
"""
CDOps Cloud Zombie Hunter - Multi-Cloud Cost Optimization Tool.

A production-grade CLI tool that scans multiple cloud providers for zombie resources
(unused or orphaned infrastructure) that generate unnecessary costs.

Version: 4.0.0 (Multi-Cloud Architecture)
Author: CDOps Tech
Email: contact@cdops.tech
License: MIT
Repository: https://github.com/cdops-tech/CDOps-Cloud-Zombie-Hunter
"""

import sys
import argparse
from typing import Optional

# Dependency checks
try:
    import boto3
    from colorama import init, Fore, Style
    from tabulate import tabulate
except ImportError as e:
    print(f"ERROR: Missing required dependency: {e}")
    print("\nPlease install dependencies:")
    print("  pip install -r requirements.txt")
    sys.exit(1)

# Initialize colorama
init(autoreset=True)

# Import providers
try:
    from providers.aws import AWSProvider
    from providers.azure import AzureProvider
    from providers.gcp import GCPProvider
except ImportError as e:
    print(f"{Fore.RED}ERROR: Failed to import providers: {e}{Style.RESET_ALL}")
    sys.exit(1)

# Import utilities
try:
    from utils.reporting import print_summary, export_to_csv, print_footer, generate_default_filename
except ImportError as e:
    print(f"{Fore.RED}ERROR: Failed to import utilities: {e}{Style.RESET_ALL}")
    sys.exit(1)


def print_banner():
    """Display the tool banner."""
    banner = f"""{Fore.CYAN}
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║          🔍  CDOps Cloud Zombie Hunter v4.0                      ║
║                                                                   ║
║          Hunt Down Cost Zombies Across Multiple Clouds            ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
{Style.RESET_ALL}"""
    print(banner)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='CDOps Cloud Zombie Hunter - Multi-Cloud Cost Optimization Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan AWS in a specific region
  python zombie_hunter.py --cloud aws --region us-east-1
  
  # Scan AWS in all regions
  python zombie_hunter.py --cloud aws --all-regions
  
  # Scan Azure in a specific region
  python zombie_hunter.py --cloud azure --region eastus
  
  # Export results to CSV
  python zombie_hunter.py --cloud aws --region us-west-2 --output report.csv

For more information, visit: https://github.com/cdops-tech/CDOps-Cloud-Zombie-Hunter
        """
    )
    
    parser.add_argument(
        '--cloud',
        type=str,
        choices=['aws', 'azure', 'gcp'],
        default='aws',
        help='Cloud provider to scan (default: aws)'
    )
    
    parser.add_argument(
        '--region',
        type=str,
        help='Specific region to scan (e.g., us-east-1 for AWS, eastus for Azure)'
    )
    
    parser.add_argument(
        '--all-regions',
        action='store_true',
        help='Scan all available regions for the cloud provider'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='Export results to CSV file (e.g., report.csv)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='CDOps Cloud Zombie Hunter v4.0.0'
    )
    
    return parser.parse_args()


def main():
    """Main entry point for the zombie hunter."""
    print_banner()
    args = parse_arguments()
    
    # Initialize the appropriate provider
    if args.cloud == 'aws':
        print(f"{Fore.CYAN}🔧 Initializing AWS Provider...{Style.RESET_ALL}\n")
        provider = AWSProvider()
    elif args.cloud == 'azure':
        print(f"{Fore.CYAN}🔧 Initializing Azure Provider...{Style.RESET_ALL}\n")
        provider = AzureProvider()
    elif args.cloud == 'gcp':
        print(f"{Fore.CYAN}🔧 Initializing GCP Provider...{Style.RESET_ALL}\n")
        provider = GCPProvider()
    else:
        print(f"{Fore.RED}ERROR: Unknown cloud provider: {args.cloud}{Style.RESET_ALL}")
        sys.exit(1)
    
    # Validate credentials
    if not provider.validate_credentials():
        print(f"\n{Fore.RED}❌ Credential validation failed. Please configure your credentials.{Style.RESET_ALL}")
        sys.exit(1)
    
    # Determine regions to scan
    regions = []
    if args.all_regions:
        print(f"{Fore.CYAN}📍 Fetching all available regions...{Style.RESET_ALL}")
        regions = provider.get_available_regions()
        if not regions:
            print(f"{Fore.RED}ERROR: Failed to retrieve regions{Style.RESET_ALL}")
            sys.exit(1)
        print(f"{Fore.GREEN}✅ Found {len(regions)} regions{Style.RESET_ALL}\n")
    elif args.region:
        regions = [args.region]
        print(f"{Fore.CYAN}📍 Scanning region: {args.region}{Style.RESET_ALL}\n")
    else:
        print(f"{Fore.RED}ERROR: Please specify --region or --all-regions{Style.RESET_ALL}")
        sys.exit(1)
    
    # Run the scan
    print(f"{Fore.CYAN}🚀 Starting zombie resource scan...{Style.RESET_ALL}\n")
    provider.run_scan(regions)
    
    # Get results
    findings = provider.get_findings()
    summary = provider.get_summary()
    total_savings = provider.calculate_total_savings()
    
    # Display summary
    print_summary(provider.get_provider_name(), summary, total_savings)
    
    # Export to CSV if requested
    if args.output:
        export_to_csv(findings, args.output, total_savings)
        print(f"\n{Fore.GREEN}✅ Results exported to: {args.output}{Style.RESET_ALL}")
    else:
        # Generate default filename
        default_filename = generate_default_filename(provider.get_provider_name())
        export_to_csv(findings, default_filename, total_savings)
        print(f"\n{Fore.GREEN}✅ Results exported to: {default_filename}{Style.RESET_ALL}")
    
    # Print footer
    print_footer()
    
    # Exit with appropriate code
    total_zombies = sum(summary.values())
    if total_zombies > 0:
        print(f"\n{Fore.YELLOW}⚠️  Found {total_zombies} zombie resources. Review and take action!{Style.RESET_ALL}")
        sys.exit(0)
    else:
        print(f"\n{Fore.GREEN}🎉 No zombie resources found. Your cloud is clean!{Style.RESET_ALL}")
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}⚠️  Scan interrupted by user{Style.RESET_ALL}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Fore.RED}❌ Fatal error: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
