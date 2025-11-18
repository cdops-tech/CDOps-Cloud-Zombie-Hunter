#!/bin/bash

# CDOps Cloud Zombie Hunter - Quick Start Script
# This script helps you get started quickly with the Zombie Hunter

set -e

echo "======================================"
echo "CDOps Cloud Zombie Hunter - Setup"
echo "======================================"
echo ""

# Check Python installation
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✅ Found Python $PYTHON_VERSION"
echo ""

# Check AWS CLI (optional but recommended)
echo "Checking AWS CLI installation..."
if command -v aws &> /dev/null; then
    AWS_VERSION=$(aws --version 2>&1 | cut -d' ' -f1)
    echo "✅ Found $AWS_VERSION"
else
    echo "⚠️  AWS CLI not found (optional, but recommended for credential management)"
fi
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Check AWS credentials
echo "Checking AWS credentials..."
if python3 -c "import boto3; boto3.client('sts').get_caller_identity()" 2>/dev/null; then
    echo "✅ AWS credentials configured and valid"
    ACCOUNT=$(python3 -c "import boto3; print(boto3.client('sts').get_caller_identity()['Account'])")
    echo "   Account ID: $ACCOUNT"
else
    echo "❌ AWS credentials not configured or invalid"
    echo ""
    echo "Please configure your AWS credentials using one of these methods:"
    echo "  1. Run: aws configure"
    echo "  2. Set environment variables:"
    echo "     export AWS_ACCESS_KEY_ID='your-key'"
    echo "     export AWS_SECRET_ACCESS_KEY='your-secret'"
    echo "     export AWS_DEFAULT_REGION='us-east-1'"
    echo ""
    exit 1
fi
echo ""

# Make the script executable
chmod +x zombie_hunter.py

echo "======================================"
echo "✅ Setup Complete!"
echo "======================================"
echo ""
echo "You're ready to hunt zombies! Try these commands:"
echo ""
echo "  # Scan your default region"
echo "  python3 zombie_hunter.py"
echo ""
echo "  # Scan a specific region"
echo "  python3 zombie_hunter.py --region us-west-2"
echo ""
echo "  # Scan all regions (comprehensive)"
echo "  python3 zombie_hunter.py --all-regions"
echo ""
echo "  # Enable verbose output"
echo "  python3 zombie_hunter.py --verbose"
echo ""
echo "For more information, see README.md"
echo ""
