#!/bin/bash
# verify-deployment.sh - Verify Groq deployment is healthy

echo "=============================================="
echo "VEDA AI COACHING - GROQ DEPLOYMENT VERIFICATION"
echo "=============================================="
echo ""

# 1. Docker Compose Status
echo "✓ STEP 1: Docker Compose Status"
echo "---"
docker-compose ps
echo ""

# 2. Health Check Endpoint
echo "✓ STEP 2: Health Check Endpoint"
echo "---"
curl -s http://localhost:8001/health | python3 -m json.tool 2>/dev/null || echo "Could not reach health endpoint"
echo ""

# 3. Groq Connectivity
echo "✓ STEP 3: Groq API Connectivity"
echo "---"
docker-compose logs api | grep -i "groq\|phase 5" | tail -3
echo ""

# 4. User Count
echo "✓ STEP 4: Database - User Count"
echo "---"
docker-compose exec -T postgres psql -U postgres -c "SELECT COUNT(*) as user_count FROM users;" 2>/dev/null
echo ""

# 5. System Resources
echo "✓ STEP 5: System Resources"
echo "---"
echo "Memory Usage:"
docker stats --no-stream --format "{{.Container}}: {{.MemUsage}}" 2>/dev/null | head -5
echo ""

# 6. Final Status
echo "=============================================="
echo "✅ DEPLOYMENT VERIFICATION COMPLETE"
echo "=============================================="
echo ""
echo "Status Summary:"
echo "- All containers should show: Up"
echo "- Health endpoint should return: healthy"
echo "- Groq should show: reachable"
echo "- User count should show: 1 or more"
echo ""
