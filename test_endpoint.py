#!/usr/bin/env python3
"""Test script to verify the generate endpoint is working"""

import requests
import json
import sys

def test_test_endpoint():
    """Test the simple test endpoint"""
    try:
        url = "http://localhost:8001/api/v1/tools/test-endpoint"
        print(f"Testing: {url}")

        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            print("✅ Test endpoint works!")
            return True
        else:
            print("❌ Test endpoint failed")
            return False
    except Exception as e:
        print(f"❌ Error testing endpoint: {e}")
        return False

def test_generate_endpoint():
    """Test the generate endpoint"""
    try:
        url = "http://localhost:8001/api/v1/tools/generate"
        data = {"prompt": "Create a simple test tool"}
        headers = {"Content-Type": "application/json"}

        print(f"Testing: {url}")

        response = requests.post(url, json=data, headers=headers, timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            print("✅ Generate endpoint works!")
            return True
        else:
            print("❌ Generate endpoint failed")
            return False
    except Exception as e:
        print(f"❌ Error testing endpoint: {e}")
        return False

if __name__ == "__main__":
    print("Testing AI Spine Tool Generation Endpoints")
    print("=" * 50)

    # Test simple endpoint first
    test_success = test_test_endpoint()
    print()

    # Test generate endpoint
    generate_success = test_generate_endpoint()
    print()

    if test_success and generate_success:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("💥 Some tests failed!")
        sys.exit(1)