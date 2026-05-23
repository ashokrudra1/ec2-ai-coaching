# backend/notifications.py

import os
import logging
import requests

from pathlib import Path
from dotenv import load_dotenv

# ==========================================================
# LOAD ENV
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger(__name__)


# ==========================================================
# TELEGRAM CONFIG
# ==========================================================

def get_bot_token():

    token = os.getenv(
        "TELEGRAM_BOT_TOKEN",
        ""
    ).strip()

    if not token:

        logger.error(
            "❌ TELEGRAM_BOT_TOKEN missing"
        )

        return None

    return token


def get_base_url():

    token = get_bot_token()

    if not token:
        return None

    return f"https://api.telegram.org/bot{token}"


# ==========================================================
# CORE SEND FUNCTION
# ==========================================================

def _send(payload: dict):

    base_url = get_base_url()

    if not base_url:

        logger.error(
            "❌ Telegram base URL generation failed"
        )

        return False

    try:

        telegram_url = f"{base_url}/sendMessage"

        logger.warning(
            f"TELEGRAM URL => {telegram_url}"
        )

        logger.warning(
            f"PAYLOAD => {payload}"
        )

        response = requests.post(
            telegram_url,
            json=payload,
            timeout=15
        )

        logger.warning(
            f"TELEGRAM STATUS => {response.status_code}"
        )

        logger.warning(
            f"TELEGRAM RESPONSE => {response.text}"
        )

        if response.status_code != 200:

            logger.error(
                f"❌ Telegram API error: "
                f"{response.status_code} | "
                f"{response.text}"
            )

            return False

        return True

    except Exception as e:

        logger.exception(
            f"❌ Telegram request failed: {e}"
        )

        return False


# ==========================================================
# SEND TEXT MESSAGE
# ==========================================================

def send_telegram_message(
    text: str,
    chat_id: str
):

    payload = {
        "chat_id": str(chat_id),
        "text": text,
        "parse_mode": "Markdown"
    }

    success = _send(payload)

    if success:

        logger.info(
            f"✅ Message sent to {chat_id}"
        )

    return success


# ==========================================================
# SEND URL BUTTON
# ==========================================================

def send_telegram_url_button(
    text: str,
    button_text: str,
    url: str,
    chat_id: str
):

    payload = {
        "chat_id": str(chat_id),
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [[
                {
                    "text": button_text,
                    "url": url
                }
            ]]
        }
    }

    success = _send(payload)

    if success:

        logger.info(
            f"🔗 URL button sent to {chat_id}"
        )

    return success


# ==========================================================
# SEND CALLBACK BUTTONS
# ==========================================================

def send_telegram_buttons(
    text: str,
    buttons: list,
    chat_id: str
):

    keyboard = []

    for btn in buttons:

        if isinstance(btn, dict):

            keyboard.append([
                {
                    "text": btn["text"],
                    "callback_data": btn["callback_data"]
                }
            ])

        else:

            keyboard.append([
                {
                    "text": btn,
                    "callback_data": btn
                }
            ])

    payload = {
        "chat_id": str(chat_id),
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": keyboard
        }
    }

    success = _send(payload)

    if success:

        logger.info(
            f"🔘 Buttons sent to {chat_id}"
        )

    return success
