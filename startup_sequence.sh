#!/bin/bash

# 1. Update Namecheap DNS
echo "🔄 Updating Namecheap DNS..."
# Use your working curl command from earlier
curl -s "https://dynamicdns.park-your-domain.com/update?host=@&domain=vedaactivewellness.xyz&password=16c80903b18642389c853301155158e7&ip=$(curl -s https://ifconfig.me)"

# 2. WAIT - This is the secret sauce. Give DNS 60 seconds to spread.
echo "⏳ Waiting 60 seconds for DNS propagation..."
sleep 60

# 3. Force Refresh Telegram Webhook
echo "🔄 Refreshing Telegram Webhook..."
# Delete first to force a fresh DNS lookup
# ... (Namecheap update part stays the same) ...

# 3. Force Refresh Telegram Webhook
echo "🔄 Refreshing Telegram Webhook..."
# Get current IP specifically for this command
CURRENT_IP=$(curl -s https://ifconfig.me)

# Delete first to clear the cache
curl -s "https://api.telegram.org/bot8477752920:AAHUGd8yI3o7FJ7pGrqrChWFEIBzEKdrgaQ/deleteWebhook"
sleep 2

# SET WEBHOOK using the Domain, but also tell Telegram the IP explicitly!
# This "ip_address" parameter is the secret to bypassing DNS lag.
curl -s "https://api.telegram.org/bot8477752920:AAHUGd8yI3o7FJ7pGrqrChWFEIBzEKdrgaQ/setWebhook?url=https://vedaactivewellness.xyz/webhook/telegram&ip_address=$CURRENT_IP"

echo "✅ Telegram now knows we are at $CURRENT_IP"

echo "✅ Startup Sequence Complete!"
