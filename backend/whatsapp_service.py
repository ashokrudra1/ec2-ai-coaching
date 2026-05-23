import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

# Your Twilio credentials from .env
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
# Your Twilio WhatsApp Number (usually 'whatsapp:+14155238886' for sandbox)
from_whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER") 

client = Client(account_sid, auth_token)

def send_whatsapp_message(to_phone, message_body):
    """
    Sends a WhatsApp message via Twilio.
    to_phone should be in format '+919652771023'
    """
    try:
        # Twilio requires the 'whatsapp:' prefix
        to_number = f"whatsapp:{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone
        
        message = client.messages.create(
            body=message_body,
            from_=from_whatsapp_number,
            to=to_number
        )
        print(f"✅ WhatsApp sent to {to_phone}: {message.sid}")
        return message.sid
    except Exception as e:
        print(f"❌ WhatsApp Error: {e}")
        return None
