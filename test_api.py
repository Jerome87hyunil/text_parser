#!/usr/bin/env python3
"""Test script for HWP API deployment"""

import requests
import json

API_URL = "https://hwp-api.onrender.com"

def test_health():
    """Test health endpoint"""
    response = requests.get(f"{API_URL}/health")
    print(f"Health Check: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.status_code == 200

def test_root():
    """Test root endpoint"""
    response = requests.get(f"{API_URL}/")
    print(f"Root Endpoint: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.status_code == 200

def test_text_extraction():
    """Test text extraction without file (should fail gracefully)"""
    response = requests.post(f"{API_URL}/api/v1/extract/hwp-to-text")
    print(f"Text Extraction (no file): {response.status_code}")
    print(f"Response: {response.text}\n")
    return response.status_code == 422  # Expected validation error

def test_docs():
    """Test API documentation"""
    response = requests.get(f"{API_URL}/docs")
    print(f"API Docs: {response.status_code}")
    print(f"Docs available: {response.status_code == 200}\n")
    return response.status_code == 200

def main():
    print("=" * 50)
    print("Testing HWP API Deployment")
    print("=" * 50 + "\n")
    
    tests = [
        ("Health Check", test_health),
        ("Root Endpoint", test_root),
        ("Text Extraction", test_text_extraction),
        ("API Documentation", test_docs),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n--- {name} ---")
        try:
            result = test_func()
            results.append((name, "✅ PASS" if result else "❌ FAIL"))
        except Exception as e:
            print(f"Error: {e}")
            results.append((name, f"❌ ERROR: {e}"))
    
    print("\n" + "=" * 50)
    print("Test Results Summary")
    print("=" * 50)
    for name, result in results:
        print(f"{name}: {result}")
    
    all_passed = all("✅" in result for _, result in results)
    print(f"\nOverall: {'✅ All tests passed!' if all_passed else '⚠️ Some tests failed'}")

if __name__ == "__main__":
    main()