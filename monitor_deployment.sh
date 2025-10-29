#!/bin/bash
# Monitor Render Deployment Status

API_URL="https://trend-reports-api.onrender.com"
MAX_ATTEMPTS=30  # 30 attempts = 10 minutes (20 sec intervals)
ATTEMPT=0

echo "🔄 Monitoring Render Deployment..."
echo "URL: $API_URL"
echo "Started at: $(date)"
echo ""

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    ATTEMPT=$((ATTEMPT + 1))
    
    # Test health endpoint
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health" 2>/dev/null)
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo ""
        echo "✅ DEPLOYMENT SUCCESSFUL!"
        echo "Completed at: $(date)"
        echo ""
        echo "Testing endpoints..."
        echo "-------------------"
        
        # Test multiple endpoints
        echo "Health: $(curl -s -o /dev/null -w "%{http_code}" $API_URL/health)"
        echo "Root: $(curl -s -o /dev/null -w "%{http_code}" $API_URL/)"
        echo "Categories: $(curl -s -o /dev/null -w "%{http_code}" $API_URL/v1/categories)"
        echo "Docs: $(curl -s -o /dev/null -w "%{http_code}" $API_URL/docs)"
        
        echo ""
        echo "Health Response:"
        curl -s "$API_URL/health" | python -m json.tool 2>/dev/null || curl -s "$API_URL/health"
        
        exit 0
    elif [ "$HTTP_CODE" = "404" ]; then
        printf "\r⏳ Attempt $ATTEMPT/$MAX_ATTEMPTS - Building... (404 - service not ready)"
    elif [ "$HTTP_CODE" = "502" ] || [ "$HTTP_CODE" = "503" ]; then
        printf "\r⏳ Attempt $ATTEMPT/$MAX_ATTEMPTS - Starting... ($HTTP_CODE - service starting)"
    else
        printf "\r⏳ Attempt $ATTEMPT/$MAX_ATTEMPTS - Status: $HTTP_CODE"
    fi
    
    sleep 20
done

echo ""
echo "⚠️  Deployment taking longer than expected (10+ minutes)"
echo "Check Render dashboard: https://dashboard.render.com"
echo "Service name: trend-reports-api"
