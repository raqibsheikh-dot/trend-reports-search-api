"""
Test script for Trend Reports API
Tests both local and production endpoints
"""

import requests
import os
from dotenv import load_dotenv
import sys
from typing import Optional

load_dotenv()

# Configuration
API_KEY = os.getenv("API_KEY", "your_secure_api_key_here")
LOCAL_URL = "http://localhost:8000"
PROD_URL = os.getenv("PROD_URL", "")  # Set this to your production URL


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")


def print_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")


def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.RESET}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")


def test_health(base_url: str) -> bool:
    """Test the /health endpoint"""
    try:
        response = requests.get(f"{base_url}/health", timeout=10)

        if response.status_code == 200:
            data = response.json()
            print_success(f"Health check passed")
            print(f"  Status: {data.get('status')}")
            print(f"  Documents: {data.get('documents')}")
            print(f"  Model: {data.get('model')}")
            print(f"  Version: {data.get('version')}")
            return True
        else:
            print_error(f"Health check failed: HTTP {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print_error("Connection failed - is the server running?")
        return False
    except Exception as e:
        print_error(f"Health check error: {str(e)}")
        return False


def test_search(base_url: str, api_key: str, query: str = "AI trends in advertising", top_k: int = 3) -> bool:
    """Test the /search endpoint"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "query": query,
            "top_k": top_k
        }

        print_info(f"Searching: '{query}' (top_k={top_k})")
        response = requests.post(
            f"{base_url}/search",
            json=payload,
            headers=headers,
            timeout=30
        )

        if response.status_code == 200:
            results = response.json()
            print_success(f"Search successful - {len(results)} results")

            for i, result in enumerate(results, 1):
                print(f"\n  Result {i}:")
                print(f"    Source: {result['source']}")
                print(f"    Page: {result['page']}")
                print(f"    Relevance: {result['relevance_score']:.3f}")
                print(f"    Content: {result['content'][:100]}...")

            return True

        elif response.status_code == 401:
            print_error("Authentication failed - check your API_KEY")
            return False
        elif response.status_code == 400:
            print_error(f"Bad request: {response.json().get('detail')}")
            return False
        else:
            print_error(f"Search failed: HTTP {response.status_code}")
            print(f"  Response: {response.text}")
            return False

    except Exception as e:
        print_error(f"Search error: {str(e)}")
        return False


def test_auth_failure(base_url: str) -> bool:
    """Test that authentication is working by trying with wrong key"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer wrong_key"
        }

        payload = {"query": "test", "top_k": 1}

        response = requests.post(
            f"{base_url}/search",
            json=payload,
            headers=headers,
            timeout=10
        )

        if response.status_code == 401:
            print_success("Authentication properly rejects invalid keys")
            return True
        else:
            print_error(f"Authentication test failed - expected 401, got {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Auth test error: {str(e)}")
        return False


def test_invalid_query(base_url: str, api_key: str) -> bool:
    """Test that API properly handles invalid queries"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        # Test empty query
        payload = {"query": "", "top_k": 5}

        response = requests.post(
            f"{base_url}/search",
            json=payload,
            headers=headers,
            timeout=10
        )

        if response.status_code == 400:
            print_success("Empty query properly rejected")
            return True
        else:
            print_error(f"Invalid query test failed - expected 400, got {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Invalid query test error: {str(e)}")
        return False


def run_test_suite(base_url: str, api_key: str, label: str):
    """Run all tests for a given endpoint"""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}Testing {label}: {base_url}{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")

    tests = [
        ("Health Check", lambda: test_health(base_url)),
        ("Authentication Failure", lambda: test_auth_failure(base_url)),
        ("Invalid Query Handling", lambda: test_invalid_query(base_url, api_key)),
        ("Search - AI Trends", lambda: test_search(base_url, api_key, "AI trends in advertising", 3)),
        ("Search - Social Media", lambda: test_search(base_url, api_key, "social media strategies", 2)),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n{Colors.BOLD}Test: {test_name}{Colors.RESET}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print_error(f"Test crashed: {str(e)}")
            results.append((test_name, False))

    # Summary
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}Test Summary for {label}{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if success else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"  {status} - {test_name}")

    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.RESET}")

    if passed == total:
        print_success(f"All tests passed for {label}!")
        return True
    else:
        print_warning(f"{total - passed} test(s) failed for {label}")
        return False


def main():
    """Main test runner"""
    print(f"{Colors.BOLD}Trend Reports API - Test Suite{Colors.RESET}")

    # Determine which tests to run
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        mode = "local"

    if mode == "local":
        print_info("Testing LOCAL endpoint")
        success = run_test_suite(LOCAL_URL, API_KEY, "Local Development")
        sys.exit(0 if success else 1)

    elif mode == "prod" or mode == "production":
        if not PROD_URL:
            print_error("PROD_URL not set in .env file")
            print("  Add: PROD_URL=https://your-app.railway.app")
            sys.exit(1)

        print_info("Testing PRODUCTION endpoint")
        success = run_test_suite(PROD_URL, API_KEY, "Production")
        sys.exit(0 if success else 1)

    elif mode == "both":
        print_info("Testing BOTH local and production endpoints")
        local_success = run_test_suite(LOCAL_URL, API_KEY, "Local Development")

        if PROD_URL:
            prod_success = run_test_suite(PROD_URL, API_KEY, "Production")
        else:
            print_warning("PROD_URL not set - skipping production tests")
            prod_success = True

        sys.exit(0 if (local_success and prod_success) else 1)

    else:
        print_error(f"Unknown mode: {mode}")
        print("Usage: python test_api.py [local|prod|both]")
        sys.exit(1)


if __name__ == "__main__":
    main()
