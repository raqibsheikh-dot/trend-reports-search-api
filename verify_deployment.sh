#!/bin/bash
# Deployment Verification Script

API_URL="https://trend-reports-api.onrender.com"

echo "Testing deployment..."
echo "Health: $(curl -s -o /dev/null -w "%{http_code}" $API_URL/health)"
echo "Root: $(curl -s -o /dev/null -w "%{http_code}" $API_URL/)"
echo "Docs: $(curl -s -o /dev/null -w "%{http_code}" $API_URL/docs)"
echo "Categories: $(curl -s -o /dev/null -w "%{http_code}" $API_URL/v1/categories)"
