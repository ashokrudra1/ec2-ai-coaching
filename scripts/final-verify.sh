#!/bin/bash
# FINAL DEPLOYMENT VERIFICATION FOR GROQ PRODUCTION
# Run this on EC2 to verify everything is working

echo "========================================================================"
echo "VEDA AI COACHING - GROQ PRODUCTION DEPLOYMENT VERIFICATION"
echo "========================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Step 1: Check Groq configuration
echo -e "${GREEN}✓ STEP 1: Verify Groq Configuration${NC}"
echo "---"
echo "OPENAI_API_KEY:"
cat .env | grep "^OPENAI_API_KEY" | sed 's/=.*/=gsk_****/'
echo ""
echo "OPENAI_BASE_URL:"
cat .env | grep "^OPENAI_BASE_URL"
echo ""

# Step 2: Restart API container
echo -e "${GREEN}✓ STEP 2: Restart API Container${NC}"
echo "---"
docker-compose restart api
echo "Waiting 15 seconds for API to boot..."
sleep 15
echo ""

# Step 3: Check container status
echo -e "${GREEN}✓ STEP 3: Check Container Status${NC}"
echo "---"
docker-compose ps
echo ""

# Step 4: Check API health
echo -e "${GREEN}✓ STEP 4: Check API Health Endpoint${NC}"
echo "---"
HEALTH=$(curl -s http://localhost:8001/health)
echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
echo ""

# Step 5: Check logs for Groq
echo -e "${GREEN}✓ STEP 5: Check Groq Connectivity in Logs${NC}"
echo "---"
docker-compose logs api | grep -i "groq\|llm\|phase 5" | tail -10
echo ""

# Step 6: Count users in database
echo -e "${GREEN}✓ STEP 6: Database Status${NC}"
echo "---"
docker-compose exec -T postgres psql -U postgres -c "SELECT COUNT(*) as users FROM users;" 2>/dev/null || echo "Could not query database"
echo ""

# Step 7: Test Groq API directly
echo -e "${GREEN}✓ STEP 7: Test Groq API Connectivity${NC}"
echo "---"
GROQ_KEY=$(cat .env | grep "^OPENAI_API_KEY" | cut -d= -f2)
if [ -z "$GROQ_KEY" ]; then
    echo -e "${RED}ERROR: OPENAI_API_KEY not set${NC}"
else
    echo "Testing Groq API models endpoint..."
    curl -s https://api.groq.com/openai/v1/models \
      -H "Authorization: Bearer $GROQ_KEY" \
      -H "Content-Type: application/json" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Models available: {len(data.get(\"data\", []))}'); print('Status: OK' if 'data' in data else 'Status: FAILED')" 2>/dev/null || echo "Groq API test failed - key may be invalid"
fi
echo ""

# Step 8: Final status
echo "========================================================================"
echo "DEPLOYMENT VERIFICATION COMPLETE"
echo "========================================================================"
echo ""
echo "CHECKLIST:"
echo "  [✓] Groq configuration present"
echo "  [✓] API container restarted"
echo "  [?] API health check - check output above"
echo "  [?] Groq connectivity - check output above"
echo ""
echo "If Groq shows HTTP 401:"
echo "  1. Verify your Groq API key is valid (gsk_...)"
echo "  2. Check it has credits/quota available"
echo "  3. Regenerate key at https://console.groq.com if needed"
echo "  4. Update .env and restart again"
echo ""
echo "If everything shows HEALTHY:"
echo "  ✅ Your system is PRODUCTION READY!"
echo "  Test: Send /start to Telegram bot"
echo ""
