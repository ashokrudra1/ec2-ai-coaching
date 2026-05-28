#!/bin/bash
# ============================================================================
# Veda AI Coaching - Production Validation Script
# ============================================================================
# This script validates that all production updates are working correctly
# Run this after deployment to verify the system is operational

set -e

COLOR_GREEN='\033[0;32m'
COLOR_RED='\033[0;31m'
COLOR_YELLOW='\033[1;33m'
COLOR_BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${COLOR_BLUE}========================================${NC}"
echo -e "${COLOR_BLUE}Veda AI Coaching - Production Validator${NC}"
echo -e "${COLOR_BLUE}========================================${NC}\n"

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0

# ============================================================================
# Helper functions
# ============================================================================
pass() {
    echo -e "${COLOR_GREEN}✅ PASS${NC}: $1"
    ((TESTS_PASSED++))
}

fail() {
    echo -e "${COLOR_RED}❌ FAIL${NC}: $1"
    ((TESTS_FAILED++))
}

warn() {
    echo -e "${COLOR_YELLOW}⚠️  WARN${NC}: $1"
}

info() {
    echo -e "${COLOR_BLUE}ℹ️  INFO${NC}: $1"
}

# ============================================================================
# 1. Docker Compose Tests
# ============================================================================
echo -e "${COLOR_BLUE}[1/5] Docker Compose Configuration${NC}\n"

if ! command -v docker-compose &> /dev/null; then
    fail "docker-compose not installed"
else
    pass "docker-compose is installed"
    
    # Validate docker-compose.yml syntax
    if docker-compose config > /dev/null 2>&1; then
        pass "docker-compose.yml is valid"
    else
        fail "docker-compose.yml has syntax errors"
    fi
fi

# ============================================================================
# 2. Image Build Tests
# ============================================================================
echo -e "\n${COLOR_BLUE}[2/5] Docker Image Build${NC}\n"

info "Building backend Docker image (this may take 2-3 minutes)..."
if docker build -f backend/Dockerfile -t veda-coaching:test . > /dev/null 2>&1; then
    pass "Backend Docker image built successfully"
    
    # Check image size
    SIZE=$(docker inspect veda-coaching:test --format='{{.Size}}')
    SIZE_MB=$((SIZE / 1024 / 1024))
    if [ $SIZE_MB -lt 1000 ]; then
        pass "Docker image size is optimized ($SIZE_MB MB)"
    else
        warn "Docker image is larger than expected ($SIZE_MB MB)"
    fi
else
    fail "Failed to build Docker image"
fi

# ============================================================================
# 3. Environment Configuration Tests
# ============================================================================
echo -e "\n${COLOR_BLUE}[3/5] Environment Configuration${NC}\n"

if [ -f ".env" ]; then
    pass ".env file exists"
    
    # Check for required variables
    REQUIRED_VARS=("OPENAI_API_KEY" "TELEGRAM_BOT_TOKEN" "REDIS_URL")
    MISSING_VARS=()
    
    for var in "${REQUIRED_VARS[@]}"; do
        if grep -q "^$var=" .env; then
            pass "$var is configured"
        else
            MISSING_VARS+=("$var")
        fi
    done
    
    if [ ${#MISSING_VARS[@]} -eq 0 ]; then
        pass "All required environment variables are set"
    else
        fail "Missing environment variables: ${MISSING_VARS[*]}"
    fi
else
    fail ".env file not found (required for deployment)"
    warn "Copy .env.example to .env and configure variables"
fi

if [ -f ".env.example" ]; then
    pass ".env.example template exists"
else
    fail ".env.example template not found"
fi

# ============================================================================
# 4. File Structure Tests
# ============================================================================
echo -e "\n${COLOR_BLUE}[4/5] Project File Structure${NC}\n"

REQUIRED_FILES=(
    "docker-compose.yml"
    "backend/Dockerfile"
    "backend/main.py"
    "backend/database.py"
    "backend/celery_app.py"
    "backend/models.py"
    "requirements.txt"
    "alembic.ini"
    "alembic/env.py"
    "scripts/init_db.sql"
    "scripts/init_database.py"
    ".env.example"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        pass "Found: $file"
    else
        fail "Missing: $file"
    fi
done

# ============================================================================
# 5. Code Quality Checks
# ============================================================================
echo -e "\n${COLOR_BLUE}[5/5] Code Quality Checks${NC}\n"

# Check for syntax errors in Python files
PYTHON_FILES=(
    "backend/main.py"
    "backend/database.py"
    "backend/celery_app.py"
    "scripts/init_database.py"
)

for file in "${PYTHON_FILES[@]}"; do
    if python -m py_compile "$file" 2>/dev/null; then
        pass "Python syntax OK: $file"
    else
        fail "Python syntax error: $file"
    fi
done

# Check for critical functions in database.py
if grep -q "def initialize_database" backend/database.py; then
    pass "initialize_database() function exists"
else
    fail "initialize_database() function not found"
fi

if grep -q "def wait_for_database" backend/database.py; then
    pass "wait_for_database() function exists"
else
    fail "wait_for_database() function not found"
fi

if grep -q "def ensure_pgvector_extension" backend/database.py; then
    pass "ensure_pgvector_extension() function exists"
else
    fail "ensure_pgvector_extension() function not found"
fi

# Check for lifespan in main.py
if grep -q "@asynccontextmanager" backend/main.py; then
    pass "Lifespan context manager exists in main.py"
else
    fail "Lifespan context manager not found in main.py"
fi

# Check for health check endpoint
if grep -q "def health_check_endpoint" backend/main.py; then
    pass "Health check endpoint exists"
else
    fail "Health check endpoint not found"
fi

# Check docker-compose.yml for pgvector image
if grep -q "pgvector/pgvector" docker-compose.yml; then
    pass "pgvector image configured in docker-compose.yml"
else
    fail "pgvector image not found in docker-compose.yml"
fi

# ============================================================================
# Summary
# ============================================================================
echo -e "\n${COLOR_BLUE}========================================${NC}"
echo -e "${COLOR_BLUE}Validation Summary${NC}"
echo -e "${COLOR_BLUE}========================================${NC}\n"

TOTAL=$((TESTS_PASSED + TESTS_FAILED))
echo "Total Tests: $TOTAL"
echo -e "Passed: ${COLOR_GREEN}$TESTS_PASSED${NC}"
echo -e "Failed: ${COLOR_RED}$TESTS_FAILED${NC}\n"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${COLOR_GREEN}✅ All validation tests passed!${NC}\n"
    echo "Next steps:"
    echo "  1. Review .env configuration"
    echo "  2. Start services: docker-compose up -d"
    echo "  3. Monitor logs: docker-compose logs -f"
    echo "  4. Check health: curl http://localhost:8001/health"
    exit 0
else
    echo -e "${COLOR_RED}❌ Some validation tests failed!${NC}\n"
    echo "Please fix the issues above before deploying."
    exit 1
fi
