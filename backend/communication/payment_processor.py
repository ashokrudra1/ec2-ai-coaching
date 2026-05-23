"""
Payment Processing Handler
Integrates with Razorpay for seamless payment processing
Handles payment verification and subscription activation
"""
import logging
import os
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session
import hashlib
import hmac

from backend.database import SessionLocal
from backend.models import User, SubscriptionTier
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class PaymentProcessor:
    """
    Handles payment processing with Razorpay
    """

    def __init__(self):
        self.razorpay_key_id = os.getenv("RAZORPAY_KEY_ID")
        self.razorpay_key_secret = os.getenv("RAZORPAY_KEY_SECRET")
        self.webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")

    def create_order(self, amount_inr: float, customer_email: str, plan_name: str) -> Dict:
        """
        Create Razorpay order for payment
        Returns order details including order_id and payment_link
        """
        import razorpay

        try:
            client = razorpay.Client(
                auth=(self.razorpay_key_id, self.razorpay_key_secret)
            )

            amount_paise = int(amount_inr * 100)  # Razorpay uses smallest unit

            order_data = {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"receipt_{int(datetime.now(timezone.utc).timestamp())}",
                "notes": {
                    "plan": plan_name,
                    "email": customer_email,
                },
            }

            order = client.order.create(data=order_data)
            logger.info(f"✅ Order created: {order['id']}")

            return {
                "success": True,
                "order_id": order["id"],
                "amount": amount_inr,
                "currency": "INR",
            }

        except Exception as e:
            logger.error(f"❌ Order creation failed: {e}")
            return {"success": False, "error": str(e)}

    def verify_payment(self, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> Tuple[bool, str]:
        """
        Verify payment signature from Razorpay webhook
        """
        try:
            message = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
            signature = hmac.new(
                self.razorpay_key_secret.encode(),
                message,
                hashlib.sha256
            ).hexdigest()

            if signature == razorpay_signature:
                logger.info(f"✅ Payment verified: {razorpay_payment_id}")
                return True, razorpay_payment_id
            else:
                logger.warning(f"❌ Signature mismatch for payment {razorpay_payment_id}")
                return False, "Invalid signature"

        except Exception as e:
            logger.error(f"❌ Payment verification error: {e}")
            return False, str(e)

    def handle_payment_webhook(self, payload: Dict) -> Dict:
        """
        Handle Razorpay webhook for payment events
        """
        try:
            event = payload.get("event")
            data = payload.get("payload", {}).get("payment", {}).get("entity", {})

            if event == "payment.authorized":
                return self._process_payment_authorized(data)

            elif event == "payment.failed":
                return self._process_payment_failed(data)

            elif event == "payment.captured":
                return self._process_payment_captured(data)

            return {"success": True, "message": "Event noted"}

        except Exception as e:
            logger.error(f"❌ Webhook processing error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    @staticmethod
    def _process_payment_authorized(data: Dict) -> Dict:
        """Handle payment authorized event"""
        logger.info(f"Payment authorized: {data.get('id')}")
        return {"success": True, "action": "authorized"}

    @staticmethod
    def _process_payment_failed(data: Dict) -> Dict:
        """Handle payment failed event"""
        logger.warning(f"Payment failed: {data.get('id')} - {data.get('error_reason')}")
        return {"success": True, "action": "failed"}

    @staticmethod
    def _process_payment_captured(data: Dict) -> Dict:
        """Handle payment captured event - ACTIVATE SUBSCRIPTION"""
        payment_id = data.get("id")
        order_id = data.get("order_id")
        amount = data.get("amount", 0) / 100  # Convert from paise to rupees

        logger.info(f"✅ Payment captured: {payment_id} (Order: {order_id}, Amount: ₹{amount})")

        # TODO: Link this to user registration and activate subscription
        # This requires mapping payment to chat_id/user_id from Redis or temp storage

        return {"success": True, "action": "captured", "payment_id": payment_id}


class SubscriptionManager:
    """
    Manages user subscriptions and expiry
    """

    @staticmethod
    def activate_subscription(db: Session, user_id: int, plan_name: str, payment_id: str) -> Dict:
        """
        Activate subscription for user after successful payment
        """
        try:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return {"success": False, "error": "User not found"}

            tier = db.query(SubscriptionTier).filter_by(name=plan_name).first()
            if not tier:
                return {"success": False, "error": "Plan not found"}

            # Set subscription details
            user.subscription_plan = plan_name
            user.subscription_expiry = datetime.now(timezone.utc) + timedelta(days=30)
            user.payment_status = "active"

            db.commit()

            logger.info(f"✅ Subscription activated for user {user_id}: {plan_name} until {user.subscription_expiry}")

            return {
                "success": True,
                "message": f"Subscription activated: {plan_name}",
                "expiry": user.subscription_expiry.isoformat(),
                "payment_id": payment_id,
            }

        except Exception as e:
            logger.error(f"❌ Subscription activation error: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}

    @staticmethod
    def check_subscription_status(db: Session, user_id: int) -> Dict:
        """
        Check if user's subscription is active
        """
        try:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return {"active": False, "reason": "User not found"}

            if not user.subscription_plan or user.payment_status != "active":
                return {"active": False, "reason": "No active subscription"}

            if user.subscription_expiry and datetime.now(timezone.utc) > user.subscription_expiry:
                return {"active": False, "reason": "Subscription expired"}

            days_left = (user.subscription_expiry - datetime.now(timezone.utc)).days

            return {
                "active": True,
                "plan": user.subscription_plan,
                "expiry": user.subscription_expiry.isoformat(),
                "days_left": days_left,
            }

        except Exception as e:
            logger.error(f"❌ Subscription check error: {e}")
            return {"active": False, "reason": str(e)}

    @staticmethod
    def renew_subscription(db: Session, user_id: int) -> Dict:
        """
        Renew expiring subscription
        """
        try:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return {"success": False, "error": "User not found"}

            user.subscription_expiry = datetime.now(timezone.utc) + timedelta(days=30)
            db.commit()

            logger.info(f"✅ Subscription renewed for user {user_id} until {user.subscription_expiry}")

            return {
                "success": True,
                "message": "Subscription renewed",
                "new_expiry": user.subscription_expiry.isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Renewal error: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
