"""
Reporting utilities for zombie resource findings.

Handles CSV export and console summary display.
"""

import csv
from datetime import datetime
from typing import List, Dict, Any
from colorama import Fore, Style
from tabulate import tabulate


def print_summary(provider_name: str, scan_summary: Dict[str, int], total_savings: float):
    """
    Print a formatted summary of findings to the console.
    
    Args:
        provider_name: Name of the cloud provider (AWS, Azure, GCP)
        scan_summary: Dictionary mapping resource types to counts
        total_savings: Total estimated monthly savings
    """
    print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}SCAN SUMMARY - {provider_name}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")
    
    # Prepare summary table
    summary_data = [[k.replace('_', ' ').title(), v] for k, v in scan_summary.items()]
    
    print(tabulate(summary_data, headers=['Resource Type', 'Count'], tablefmt='grid'))
    
    total_zombies = sum(scan_summary.values())
    
    if total_zombies > 0:
        print(f"\n{Fore.RED}⚠️  Total Zombie Resources Found: {total_zombies}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}💰 Estimated Monthly Savings: ${total_savings:.2f}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}💵 Estimated Annual Savings: ${total_savings * 12:.2f}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}These resources may be costing you money unnecessarily.{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.GREEN}✅ No zombie resources found! Your {provider_name} environment looks clean.{Style.RESET_ALL}")


def export_to_csv(findings: List[Dict[str, Any]], filename: str, total_savings: float) -> bool:
    """
    Export findings to a CSV file with a summary row at the end.
    
    Args:
        findings: List of zombie resource findings
        filename: Output CSV filename
        total_savings: Total estimated monthly savings
        
    Returns:
        True if export was successful, False otherwise
    """
    if not findings:
        print(f"{Fore.YELLOW}No findings to export.{Style.RESET_ALL}")
        return False
    
    try:
        # Get all unique keys from all findings
        fieldnames = set()
        for finding in findings:
            fieldnames.update(finding.keys())
        
        fieldnames = sorted(list(fieldnames))
        
        total_zombies = len(findings)
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(findings)
            
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
        
        print(f"\n{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Report exported to: {filename}")
        print(f"📄 Full report saved: {filename}")
        print(f"💰 Total estimated monthly savings: ${total_savings:.2f}")
        
        return True
        
    except Exception as e:
        print(f"{Fore.RED}Error exporting to CSV: {e}{Style.RESET_ALL}")
        return False


def print_footer():
    """Print the marketing footer with CDOps contact information."""
    print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✅ Scan Complete!{Style.RESET_ALL}\n")
    print("If you need help safely analyzing or cleaning up these resources,")
    print("contact the CDOps Tech SRE Team:\n")
    print(f"📧 Email: {Fore.CYAN}contact@cdops.tech{Style.RESET_ALL}")
    print(f"🌐 Web: {Fore.CYAN}https://cdops.tech{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")


def generate_default_filename(provider_name: str) -> str:
    """
    Generate a default timestamped filename for CSV export.
    
    Args:
        provider_name: Name of the cloud provider
        
    Returns:
        Timestamped filename
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    provider_lower = provider_name.lower()
    return f"cdops_zombie_report_{provider_lower}_{timestamp}.csv"
