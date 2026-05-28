#!/bin/bash
# scripts/production-validation.sh
# Complete production readiness validation

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0
WARNINGS=0

pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

echo "=========================================="
echo "Production Readiness Validation"
echo "=========================================="
echo ""

# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================
echo "📋 ENVIRONMENT CONFIGURATION"
echo "---"

if [ -f ".env" ]; then
    pass ".env file exists"
    
    # Check required variables
    REQUIRED_VARS=(
        "DATABASE_URL"
        "REDIS_URL"
        "POSTGRES_PASSWORD"
        "OPENAI_API_KEY"
        "TELEGRAM_BOT_TOKEN"
        "STRAVA_CLIENT_ID"
        "STRAVA_CLIENT_SECRET"
        "ADMIN_API_KEY"
        "ENVIRONMENT"
        "DOMAIN"
    )
    
    for var in "${REQUIRED_VARS[@]}"; do
        if grep -q "^${var}=" .env; then
            value=$(grep "^${var}=" .env | cut -d= -f2)
            if [ -z "$value" ] || [ "$value" = "REDACTED" ]; then
                fail "${var} is empty or redacted"
            else
                pass "${var} is configured"
            fi
        else
            fail "${var} is missing from .env"
        fi
    done
else
    fail ".env file not found"
fi

echo ""

# ============================================================================
# DOCKER CONFIGURATION
# ============================================================================
echo "🐳 DOCKER CONFIGURATION"
echo "---"

if command -v docker &> /dev/null; then
    pass "Docker is installed"
else
    fail "Docker is not installed"
fi

if command -v docker-compose &> /dev/null; then
    pass "Docker Compose is installed"
else
    fail "Docker Compose is not installed"
fi

# Validate docker-compose.yml
if docker-compose config > /dev/null 2>&1; then
    pass "docker-compose.yml is valid"
else
    fail "docker-compose.yml has errors"
fi

# Check if services are running
RUNNING_SERVICES=$(docker-compose ps -q 2>/dev/null | wc -l)
if [ "$RUNNING_SERVICES" -ge 5 ]; then
    pass "All services are running ($RUNNING_SERVICES containers)"
else
    warn "Only $RUNNING_SERVICES services running (expected 6+)"
fi

echo ""

# ============================================================================
# CONNECTIVITY TESTS
# ============================================================================
echo "🌐 CONNECTIVITY TESTS"
echo "---"

# Test API
if curl -s http://localhost:8001/ping &>/dev/null; then
    pass "API is responding"
else
    fail "API is not responding"
fi

# Test PostgreSQL
if docker-compose exec -T postgres psql -U postgres -c "SELECT 1" &>/dev/null; then
    pass "PostgreSQL is accessible"
else
    fail "PostgreSQL is not accessible"
fi

# Test Redis
if docker-compose exec -T redis redis-cli ping &>/dev/null; then
    pass "Redis is accessible"
else
    fail "Redis is not accessible"
fi

# Test pgvector extension
PGVECTOR_EXISTS=$(docker-compose exec -T postgres psql -U postgres -c "SELECT 1 FROM pg_extension WHERE extname = 'pgvector';" 2>/dev/null | grep -c "1")
if [ "$PGVECTOR_EXISTS" -gt 0 ]; then
    pass "pgvector extension is installed"
else
    fail "pgvector extension is not installed"
fi

# Test database tables
TABLES_COUNT=$(docker-compose exec -T postgres psql -U postgres -c "\dt" 2>/dev/null | tail -n 1 | awk '{print $1}')
if [ "$TABLES_COUNT" -gt 0 ]; then
    pass "Database tables exist ($TABLES_COUNT tables)"
else
    fail "No database tables found"
fi

echo ""

# ============================================================================
# HEALTH CHECKS
# ============================================================================
echo "🩺 HEALTH CHECKS"
echo "---"

HEALTH_RESPONSE=$(curl -s http://localhost:8001/health)

if echo "$HEALTH_RESPONSE" | jq -e '.status' > /dev/null 2>&1; then
    STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.status')
    if [ "$STATUS" = "healthy" ]; then
        pass "Application health is healthy"
    else
        fail "Application health is $STATUS"
    fi
else
    fail "Could not fetch health status"
fi

# Check components
for component in postgres redis celery_workers database_tables openai; do
    COMP_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r ".components.$component.status" 2>/dev/null)
    if [ "$COMP_STATUS" = "healthy" ]; then
        pass "$component component is healthy"
    elif [ -z "$COMP_STATUS" ]; then
        warn "$component component status unknown"
    else
        warn "$component component status: $COMP_STATUS"
    fi
done

echo ""

# ============================================================================
# SECURITY CHECKS
# ============================================================================
echo "🔒 SECURITY CHECKS"
echo "---"

# Check if .env is in .gitignore
if grep -q "^.env$" .gitignore 2>/dev/null; then
    pass ".env is in .gitignore"
else
    fail ".env is NOT in .gitignore"
fi

# Check .env permissions
if [ -f ".env" ]; then
    PERMS=$(stat -c %a .env 2>/dev/null || stat -f %OLp .env 2>/dev/null || echo "unknown")
    if [ "$PERMS" = "600" ] || [ "$PERMS" = "640" ]; then
        pass ".env permissions are restrictive ($PERMS)"
    else
        warn ".env permissions are too permissive ($PERMS)"
    fi
fi

# Check for hardcoded secrets
if grep -r "sk-\|Bearer\|password=" backend/ --include="*.py" 2>/dev/null | grep -v "__pycache__" | grep -v ".pyc"; then
    fail "Hardcoded secrets detected in code"
else
    pass "No hardcoded secrets found in code"
fi

# Check rate limiting
if grep -q "slowapi" requirements.txt; then
    pass "Rate limiting dependency (slowapi) installed"
else
    fail "Rate limiting dependency (slowapi) not found"
fi

echo ""

# ============================================================================
# BACKUP & RECOVERY
# ============================================================================
echo "💾 BACKUP & RECOVERY"
echo "---"

if [ -f "scripts/backup-to-s3.sh" ]; then
    pass "Backup script exists"
else
    fail "Backup script not found"
fi

if [ -f "scripts/restore-from-s3.sh" ]; then
    pass "Restore script exists"
else
    fail "Restore script not found"
fi

# Check if AWS CLI is installed
if command -v aws &> /dev/null; then
    pass "AWS CLI is installed"
else
    warn "AWS CLI not installed (required for S3 backups)"
fi

echo ""

# ============================================================================
# MONITORING & LOGGING
# ============================================================================
echo "📊 MONITORING & LOGGING"
echo "---"

if [ -f "scripts/setup-cloudwatch-monitoring.sh" ]; then
    pass "CloudWatch setup script exists"
else
    warn "CloudWatch setup script not found"
fi

if [ -f "backend/config/cloudwatch_config.py" ]; then
    pass "CloudWatch config module exists"
else
    warn "CloudWatch config module not found"
fi

# Check log configuration
if grep -q "setup_production_logging" backend/main.py; then
    pass "Production logging is configured"
else
    fail "Production logging not configured"
fi

echo ""

# ============================================================================
# DOCUMENTATION
# ============================================================================
echo "📚 DOCUMENTATION"
echo "---"

DOCS=(
    "EC2-DEPLOYMENT-COMPLETE.md"
    "INCIDENT_RESPONSE_RUNBOOK.md"
    "PRODUCTION_SETUP.md"
    "DEPLOYMENT_READY.md"
)

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        pass "$doc exists"
    else
        warn "$doc not found"
    fi
done

echo ""

# ============================================================================
# PRODUCTION DEPLOYMENT CHECKLIST
# ============================================================================
echo "✅ PRODUCTION DEPLOYMENT CHECKLIST"
echo "---"

CHECKS=(
    ".env configured with all secrets:false"
    "Docker images built successfully:false"
    "All containers running and healthy:false"
    "Health endpoint returns healthy:false"
    "Rate limiting configured:false"
    "Database migrations completed:false"
    "pgvector extension installed:false"
    "Celery workers processing tasks:false"
    "SSL/TLS certificate valid:false"
    "Backup script tested:false"
    "CloudWatch alarms configured:false"
    "Security hardening applied:false"
    "DNS records configured:false"
    "Load test baseline established:false"
    "Incident response runbook reviewed:false"
)

for check in "${CHECKS[@]}"; do
    item=${check%:*}
    status=${check#*:}
    if [ "$status" = "false" ]; then
        warn "[ ] $item"
    else
        pass "[x] $item"
    fi
done

echo ""

# ============================================================================
# SUMMARY
# ============================================================================
echo "=========================================="
echo "VALIDATION SUMMARY"
echo "=========================================="
echo -e "${GREEN}Passed:${NC} $PASSED"
echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
echo -e "${RED}Failed:${NC} $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ PRODUCTION READY${NC}"
    exit 0
elif [ $FAILED -lt 5 ]; then
    echo -e "${YELLOW}⚠ PRODUCTION READY WITH MINOR ISSUES${NC}"
    echo "Address warnings before deployment"
    exit 0
else
    echo -e "${RED}✗ NOT PRODUCTION READY${NC}"
    echo "Fix failures before deployment"
    exit 1
fi
