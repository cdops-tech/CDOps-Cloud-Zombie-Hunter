"""
Abstract base class for cloud providers.

All cloud provider implementations (AWS, Azure, GCP) must inherit from this class
and implement the required methods.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class CloudProvider(ABC):
    """
    Abstract base class for cloud zombie hunters.
    
    Each cloud provider (AWS, Azure, GCP) implements this interface to provide
    consistent scanning capabilities across different cloud platforms.
    """
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the cloud provider scanner.
        
        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self.findings = []
        self.scan_summary = {}
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Return the name of the cloud provider.
        
        Returns:
            Provider name (e.g., 'AWS', 'Azure', 'GCP')
        """
        pass
    
    @abstractmethod
    def validate_credentials(self) -> bool:
        """
        Validate cloud provider credentials.
        
        Returns:
            True if credentials are valid, False otherwise
        """
        pass
    
    @abstractmethod
    def get_available_regions(self) -> List[str]:
        """
        Get list of available regions for this cloud provider.
        
        Returns:
            List of region identifiers
        """
        pass
    
    @abstractmethod
    def run_scan(self):
        """
        Execute the complete scan across all specified regions.
        
        This method orchestrates all individual resource scans and populates
        self.findings and self.scan_summary.
        """
        pass
    
    def log(self, message: str, level: str = "INFO"):
        """
        Print log messages with proper formatting.
        
        Args:
            message: Log message to display
            level: Log level (INFO, WARNING, ERROR, SUCCESS)
        """
        from colorama import Fore, Style
        
        colors = {
            "INFO": Fore.CYAN,
            "WARNING": Fore.YELLOW,
            "ERROR": Fore.RED,
            "SUCCESS": Fore.GREEN
        }
        
        color = colors.get(level, Fore.WHITE)
        
        # Always show scanning progress and results
        if self.verbose or level in ["WARNING", "ERROR", "SUCCESS"] or "Scanning for" in message or "⏭️" in message:
            print(f"{color}[{level}]{Style.RESET_ALL} {message}")
    
    def get_findings(self) -> List[Dict[str, Any]]:
        """
        Get all findings from the scan.
        
        Returns:
            List of zombie resource findings
        """
        return self.findings
    
    def get_summary(self) -> Dict[str, int]:
        """
        Get summary statistics from the scan.
        
        Returns:
            Dictionary mapping resource types to counts
        """
        return self.scan_summary
    
    def calculate_total_savings(self) -> float:
        """
        Calculate total estimated monthly savings from all zombie resources.
        
        Returns:
            Total estimated monthly cost savings in USD
        """
        total_savings = 0.0
        
        for finding in self.findings:
            if 'estimated_monthly_cost' in finding:
                cost_str = finding['estimated_monthly_cost']
                try:
                    cost_value = float(cost_str.replace('$', '').replace(',', ''))
                    total_savings += cost_value
                except (ValueError, AttributeError):
                    pass
        
        return total_savings
