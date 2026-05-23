import requests
import os
import time
from dotenv import load_dotenv

# 1. Load Configuration from .env
load_dotenv("/home/ubuntu/ai-coaching/.env")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DOMAIN = "vedaactivewellness.xyz"

# 2. Namecheap Dynamic DNS Settings
DDNS_PASSWORD = "16c80903b18642389c853301155158e7#" # Found in Namecheap Advanced DNS
HOST = "@"  # Use "@" for root domain

def get_current_ip():
    """Fetches the current public IP of the EC2 instance."""
    try:
        ip = requests.get('https://api.ipify.org', timeout=10).text
        print(f"🌐 Detected Current Public IP: {ip}")
        return ip
    except Exception as e:
        print(f"❌ Could not fetch Public IP: {e}")
        return None

def update_namecheap_dns(current_ip):
    """Updates Namecheap A Record to point to the new IP."""
    print(f"🔄 Updating Namecheap DNS for {DOMAIN}...")
    url = (
        f"https://dynamicdns.park-your-domain.com/update?"
        f"host={HOST}&domain={DOMAIN}&password={DDNS_PASSWORD}&ip={current_ip}"
    )
    try:
        response = requests.get(url, timeout=10)
        if "ErrCount>0" not in response.text:
            print(f"✅ DNS Update Successful: {DOMAIN} -> {current_ip}")
            return True
        else:
            print(f"❌ DNS Update Failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error communicating with Namecheap: {e}")
        return False

def update_telegram_webhook():
    """Registers the webhook with Telegram using the domain name."""
    print(f"🔄 Re-registering Telegram Webhook for {DOMAIN}...")
    webhook_url = f"https://{DOMAIN}/webhook/telegram"
    register_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    
    try:
        response = requests.get(register_url, timeout=10)
        if response.status_code == 200:
            print(f"✅ Telegram Webhook registered to {webhook_url}")
            return True
        else:
            print(f"❌ Failed to register Telegram: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error communicating with Telegram: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Self-Healing Sequence...")
    ip = get_current_ip()
    if ip:
        dns_success = update_namecheap_dns(ip)
        
        # Wait a few seconds for DNS propagation before telling Telegram
        if dns_success:
            print("⏳ Waiting 10 seconds for DNS propagation...")
            time.sleep(10)
            
        update_telegram_webhook()
    print("🏁 Self-Healing Sequence Complete.")
