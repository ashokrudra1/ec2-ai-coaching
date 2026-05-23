# backend/communication/proactive_notifications.py
from backend.notifications import send_telegram_message

class ProactiveNotifier:

    @staticmethod
    def evaluate(user, athlete_state):
        alerts = []

        if athlete_state["injury_risk"] == "High":
            alerts.append(
                "🚨 *CRITICAL SAFETY WARNING:* Ashok, your training workload is spiking too fast (ACWR is in the danger zone). "
                "I am preemptively scaling back your training intensity today to avoid a tendon flare-up. Stay safe, let's play the long game."
            )

        if athlete_state["recovery_score"] < 50:
            alerts.append(
                "⚠️ *RECOVERY WARNING:* Your physiological recovery score has dropped below 50%. "
                "Ensure you prioritize sleep and focus on hydration tonight. Do not attempt hard intervals today."
            )

        for alert in alerts:
            try:
                send_telegram_message(alert, user.telegram_chat_id)
            except Exception as e:
                print(f"Failed to send proactive message: {str(e)}")
