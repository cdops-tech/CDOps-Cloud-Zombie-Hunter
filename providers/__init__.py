"""
Cloud provider modules for CDOps Zombie Hunter.

This package contains provider-specific implementations for scanning
zombie resources across different cloud platforms.
"""

from .base import CloudProvider

__all__ = ['CloudProvider']
