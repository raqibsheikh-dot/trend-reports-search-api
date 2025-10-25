#!/bin/bash
# Quick Test Commands for Trend Reports API

set -e

API_KEY="s1RVpbfkU6NhaCOvw4v_PX7vmoFb9O3YOOBIKXbd-lk"
BASE_URL="${1:-http://localhost:8000}"

echo "============================================================"
echo "Testing Trend Reports API"
echo "Base URL: $BASE_URL"
echo "============================================================"
echo ""

# Test 1: Health Check
echo "Test 1: Health Check"
echo "-------------------"
curl -s "$BASE_URL/health" | python -m json.tool
echo ""
echo ""

# Test 2: Search - AI Trends
echo "Test 2: Search - AI Trends in Advertising"
echo "-------------------------------------------"
curl -s -X POST "$BASE_URL/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "query": "AI trends in advertising",
    "top_k": 3
  }' | python -m json.tool
echo ""
echo ""

# Test 3: Search - Social Media
echo "Test 3: Search - TikTok Strategies"
echo "-----------------------------------"
curl -s -X POST "$BASE_URL/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "query": "TikTok and short-form video strategies",
    "top_k": 2
  }' | python -m json.tool
echo ""
echo ""

# Test 4: Search - Consumer Behavior
echo "Test 4: Search - Consumer Trends 2025"
echo "--------------------------------------"
curl -s -X POST "$BASE_URL/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "query": "consumer behavior trends 2025",
    "top_k": 3
  }' | python -m json.tool
echo ""
echo ""

# Test 5: Invalid API Key (should fail)
echo "Test 5: Invalid API Key (should return 401)"
echo "--------------------------------------------"
curl -s -X POST "$BASE_URL/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid_key" \
  -d '{
    "query": "test",
    "top_k": 1
  }' | python -m json.tool || echo "Expected failure - invalid key rejected ✓"
echo ""
echo ""

echo "============================================================"
echo "All tests complete!"
echo "============================================================"
