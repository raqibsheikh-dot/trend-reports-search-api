#!/bin/bash
# Deployment Verification Script for Trend Intelligence Platform
# Usage: ./verify_deployment.sh <BACKEND_URL> <API_KEY>

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check arguments
if [ "$#" -ne 2 ]; then
    echo -e "${RED}Usage: $0 <BACKEND_URL> <API_KEY>${NC}"
    echo -e "${YELLOW}Example: $0 https://trend-reports-api.onrender.com your_api_key${NC}"
    exit 1
fi

BACKEND_URL=$1
API_KEY=$2

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Trend Intelligence Platform - Deployment Verification      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to print test results
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ $2${NC}"
    else
        echo -e "${RED}✗ $2${NC}"
        echo -e "${YELLOW}  Error: $3${NC}"
    fi
}

# Test 1: Health Check
echo -e "${BLUE}[1/6] Testing Health Endpoint...${NC}"
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${BACKEND_URL}/health")
if [ "$HEALTH_RESPONSE" = "200" ]; then
    HEALTH_DATA=$(curl -s "${BACKEND_URL}/health")
    DOCS=$(echo $HEALTH_DATA | grep -o '"documents":[0-9]*' | cut -d':' -f2)
    STATUS=$(echo $HEALTH_DATA | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

    print_result 0 "Health endpoint responding"
    echo -e "  Status: ${GREEN}${STATUS}${NC}"
    echo -e "  Documents: ${GREEN}${DOCS}${NC}"

    if [ "$DOCS" != "6109" ]; then
        echo -e "${YELLOW}  ⚠️  Warning: Expected 6109 documents, got ${DOCS}${NC}"
        echo -e "${YELLOW}     ChromaDB data may not be uploaded yet${NC}"
    fi
else
    print_result 1 "Health endpoint responding" "HTTP ${HEALTH_RESPONSE}"
fi
echo ""

# Test 2: Simple Search
echo -e "${BLUE}[2/6] Testing Simple Search...${NC}"
SEARCH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${BACKEND_URL}/search" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${API_KEY}" \
    -d '{"query": "AI trends", "top_k": 3}')

if [ "$SEARCH_RESPONSE" = "200" ]; then
    print_result 0 "Simple search endpoint working"
else
    print_result 1 "Simple search endpoint" "HTTP ${SEARCH_RESPONSE}"
fi
echo ""

# Test 3: Advanced Search
echo -e "${BLUE}[3/6] Testing Advanced Search...${NC}"
ADV_SEARCH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${BACKEND_URL}/search/advanced" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${API_KEY}" \
    -d '{
        "query": "AI marketing",
        "query_type": "multi_dimensional",
        "dimensions": ["AI", "personalization"],
        "top_k": 3
    }')

if [ "$ADV_SEARCH_RESPONSE" = "200" ]; then
    print_result 0 "Advanced search endpoint working"
else
    print_result 1 "Advanced search endpoint" "HTTP ${ADV_SEARCH_RESPONSE}"
fi
echo ""

# Test 4: Synthesis
echo -e "${BLUE}[4/6] Testing Synthesis Endpoint...${NC}"
SYN_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${BACKEND_URL}/search/synthesized" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${API_KEY}" \
    -d '{"query": "customer experience", "top_k": 10}')

if [ "$SYN_RESPONSE" = "200" ]; then
    print_result 0 "Synthesis endpoint working"
elif [ "$SYN_RESPONSE" = "500" ]; then
    print_result 1 "Synthesis endpoint" "LLM API key may not be configured"
else
    print_result 1 "Synthesis endpoint" "HTTP ${SYN_RESPONSE}"
fi
echo ""

# Test 5: Structured Report
echo -e "${BLUE}[5/6] Testing Structured Report Endpoint...${NC}"
STRUCT_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${BACKEND_URL}/search/structured" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${API_KEY}" \
    -d '{"query": "Gen Z shopping", "top_k": 10}')

if [ "$STRUCT_RESPONSE" = "200" ]; then
    print_result 0 "Structured report endpoint working"
elif [ "$STRUCT_RESPONSE" = "500" ]; then
    print_result 1 "Structured report endpoint" "LLM API key may not be configured"
else
    print_result 1 "Structured report endpoint" "HTTP ${STRUCT_RESPONSE}"
fi
echo ""

# Test 6: Categories
echo -e "${BLUE}[6/6] Testing Categories Endpoint...${NC}"
CAT_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${BACKEND_URL}/categories")

if [ "$CAT_RESPONSE" = "200" ]; then
    CATEGORIES=$(curl -s "${BACKEND_URL}/categories" | grep -o '"categories":\[[^]]*\]' | grep -o '"[^"]*"' | wc -l)
    print_result 0 "Categories endpoint working"
    echo -e "  Categories available: ${GREEN}$((CATEGORIES - 1))${NC}"
else
    print_result 1 "Categories endpoint" "HTTP ${CAT_RESPONSE}"
fi
echo ""

# Summary
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Verification Complete                                       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Final recommendations
if [ "$DOCS" = "6109" ] && [ "$SEARCH_RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓ Core functionality verified - Deployment successful!${NC}"
else
    echo -e "${YELLOW}⚠️  Some issues detected - Review errors above${NC}"
fi

if [ "$SYN_RESPONSE" != "200" ] || [ "$STRUCT_RESPONSE" != "200" ]; then
    echo -e "${YELLOW}⚠️  LLM-powered features may need API key configuration${NC}"
    echo -e "${YELLOW}   Add ANTHROPIC_API_KEY or OPENAI_API_KEY in Render Dashboard${NC}"
fi

echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo -e "  1. Test frontend: ${BACKEND_URL/api/frontend}"
echo -e "  2. Configure Custom GPT (optional)"
echo -e "  3. Share with team"
echo ""
