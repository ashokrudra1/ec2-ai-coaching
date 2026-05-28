#!/bin/bash
# scripts/reset-users.sh
# Delete all existing users and reset to clean state

set -e

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${YELLOW}⚠️  WARNING: This will DELETE all users and reset the system!${NC}"
echo ""
read -p "Are you sure? Type 'YES' to confirm: " confirm

if [ "$confirm" != "YES" ]; then
    echo "Cancelled."
    exit 0
fi

echo -e "${RED}Deleting all users...${NC}"

# Option 1: Delete all users (keeps table structure)
docker-compose exec -T postgres psql -U postgres << EOF
-- Delete all data from users table
TRUNCATE TABLE users CASCADE;

-- Reset sequence for ID auto-increment
ALTER SEQUENCE users_id_seq RESTART WITH 1;

-- Verify deletion
SELECT COUNT(*) as user_count FROM users;
EOF

echo -e "${GREEN}✅ All users deleted!${NC}"
echo ""
echo "Database is now clean. You can:"
echo "  1. Send /start to your Telegram bot to register a new user"
echo "  2. Verify: docker-compose exec -T postgres psql -U postgres -c \"SELECT * FROM users;\""
echo ""
