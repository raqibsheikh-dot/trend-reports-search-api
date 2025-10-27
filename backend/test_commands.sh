#!/bin/bash
# Quick Test Commands for Trend Reports API

set -e

# SECURITY: API key must be provided via environment variable
# Usage: API_KEY=your_key_here ./test_commands.sh [base_url]
# Or: export API_KEY=your_key_here && ./test_commands.sh
API_KEY="${API_KEY:-}"
BASE_URL="${1:-http://localhost:8000}"

# Validate API key is provided
if [ -z "$API_KEY" ]; then
  echo "❌ ERROR: API_KEY environment variable is required"
  echo ""
  echo "Usage:"
  echo "  API_KEY=your_key_here ./test_commands.sh [base_url]"
  echo ""
  echo "Or set it first:"
  echo "  export API_KEY=your_key_here"
  echo "  ./test_commands.sh [base_url]"
  echo ""
  echo "Get your API key from backend/.env file"
  exit 1
fi

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
