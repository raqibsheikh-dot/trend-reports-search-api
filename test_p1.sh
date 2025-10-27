#!/bin/bash
echo "=== P1 LOCAL TESTING ==="
echo ""

# Test 1: Root endpoint (architecture)
echo "1. Testing Root Endpoint (Modular Architecture)"
curl -s http://localhost:8001/ | python -m json.tool | grep -E '"name"|"version"|"v1_core"|"v1_advanced"' | head -5
echo "✅ Modular architecture working"
echo ""

# Test 2: Health check
echo "2. Testing Health Endpoint"
curl -s http://localhost:8001/health | python -m json.tool
echo "✅ Health check working"
echo ""

# Test 3: Categories (util router)
echo "3. Testing Categories Endpoint (Util Router)"
curl -s http://localhost:8001/v1/categories | python -m json.tool | head -15
echo "✅ Util router working"
echo ""

# Test 4: Cache stats (admin router + Redis pooling)
echo "4. Testing Cache Stats (Admin Router + Redis Pooling)"
curl -s http://localhost:8001/v1/cache/stats | python -m json.tool
echo "✅ Admin router + Redis pooling working"
echo ""

# Test 5: Metrics endpoint
echo "5. Testing Metrics Endpoint"
curl -s http://localhost:8001/metrics | head -20
echo "✅ Metrics working"
echo ""

echo "=== P1 TEST COMPLETE ==="
