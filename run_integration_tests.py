#!/usr/bin/env python3
"""
Script to run Cleanvoice SDK integration tests.

This script helps set up and run integration tests against real Cleanvoice API endpoints.
"""

import os
import sys
import subprocess
from pathlib import Path


def check_environment():
    """Check if required environment variables are set."""
    required_vars = ['CLEANVOICE_API_KEY']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   {var}")
        print("\nPlease set these variables before running integration tests:")
        print("   export CLEANVOICE_API_KEY=your-api-key-here")
        print("\nOptional variables:")
        print("   export CLEANVOICE_TEST_AUDIO_URL=https://example.com/test-audio.mp3")
        print("   export CLEANVOICE_BASE_URL=https://api.cleanvoice.ai/v2")
        return False
    
    return True


def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import pytest
        print(f"✅ pytest {pytest.__version__} found")
    except ImportError:
        print("❌ pytest not found. Install with: pip install pytest")
        return False
    
    try:
        import cleanvoice
        print(f"✅ cleanvoice SDK found")
    except ImportError:
        print("❌ cleanvoice SDK not found. Install with: pip install -e .")
        return False
    
    return True


def run_quick_auth_test():
    """Run a quick authentication test before full integration tests."""
    print("\n🔍 Running quick authentication test...")
    
    try:
        from cleanvoice import Cleanvoice
        
        api_key = os.getenv('CLEANVOICE_API_KEY')
        base_url = os.getenv('CLEANVOICE_BASE_URL', 'https://api.cleanvoice.ai/v2')
        
        client = Cleanvoice({
            'api_key': api_key,
            'base_url': base_url
        })
        
        result = client.check_auth()
        print(f"✅ Authentication successful: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        print("Please check your API key and network connection.")
        return False


def run_integration_tests(test_type="all"):
    """Run the integration tests."""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_integration.py",
        "-v",
        "-m", "integration"
    ]
    
    if test_type == "quick":
        # Skip slow tests
        cmd.extend(["-m", "integration and not slow"])
        print("\n🚀 Running quick integration tests (excluding slow tests)...")
    elif test_type == "slow":
        # Only slow tests
        cmd.extend(["-m", "integration and slow"])
        print("\n🐌 Running slow integration tests only...")
    else:
        print("\n🧪 Running all integration tests...")
    
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\n\n⏹️  Tests interrupted by user")
        return False


def main():
    """Main function."""
    print("🧪 Cleanvoice SDK Integration Test Runner")
    print("=" * 45)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Quick auth test
    if not run_quick_auth_test():
        print("\n💡 Tip: Make sure you have a valid API key and internet connection")
        sys.exit(1)
    
    # Parse command line arguments
    test_type = "all"
    if len(sys.argv) > 1:
        if sys.argv[1] in ["quick", "slow", "all"]:
            test_type = sys.argv[1]
        else:
            print(f"Unknown test type: {sys.argv[1]}")
            print("Usage: python run_integration_tests.py [quick|slow|all]")
            sys.exit(1)
    
    # Run tests
    success = run_integration_tests(test_type)
    
    if success:
        print("\n✅ All integration tests passed!")
    else:
        print("\n❌ Some integration tests failed.")
        print("Check the output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()