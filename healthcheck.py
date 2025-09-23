#!/usr/bin/env python3
"""
Simple health check script for Railway deployment
"""
import urllib.request
import os
import sys

def main():
    """Check if the health endpoint is responding"""
    port = os.getenv("PORT", "8000")
    url = f"http://localhost:{port}/health"

    try:
        response = urllib.request.urlopen(url, timeout=5)
        if response.status == 200:
            print("Health check passed")
            sys.exit(0)
        else:
            print(f"Health check failed: HTTP {response.status}")
            sys.exit(1)
    except Exception as e:
        print(f"Health check failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()