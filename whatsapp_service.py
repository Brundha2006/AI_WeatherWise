# whatsapp_service.py
# Sends the weather update through the official Meta WhatsApp Cloud API.
# Credentials are read from environment variables (.env file) - never hard-coded.

import os
import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH_API_VERSION = "v23.0"

NOT_CONFIGURED_MESSAGE = "⚠️ WhatsApp API is not configured."


def build_whatsapp_message(weather):
    """Builds the WhatsApp text from REAL weather data."""
    lines = [
        "🌦️ AI WeatherWise - Daily Update",
        "",
        f"📍 City: {weather['city']}",
        f"🌡️ Temperature: {weather['temperature']}°C",
        f"☁️ Condition: {weather['condition']}",
        f"💧 Humidity: {weather['humidity']}%",
        f"💨 Wind Speed: {weather['wind_speed']} m/s",
        "",
        "Stay safe and have a nice day! 😊",
    ]
    return "\n".join(lines)


def _clean(value):
    """Returns the value without spaces, or '' if missing / still a placeholder."""
    if not value:
        return ""
    value = value.strip()
    if value.upper().startswith("YOUR_"):
        return ""
    return value


def is_valid_recipient(number):
    """Basic check: after removing spaces/+, should be 10-15 digits (country code + number)."""
    digits = "".join(ch for ch in (number or "") if ch.isdigit())
    return 10 <= len(digits) <= 15


def send_whatsapp_message(message, recipient_number=None):
    """
    Sends a text message using WhatsApp Cloud API.
    recipient_number: the WhatsApp number (with country code) typed by the user on the
    dashboard. If not given, falls back to WHATSAPP_RECIPIENT_NUMBER in .env (optional).
    Returns (success: bool, info: str). Never raises an exception.
    success is True ONLY when Meta's API really accepts the message.
    """
    access_token = _clean(os.getenv("WHATSAPP_ACCESS_TOKEN"))
    phone_number_id = _clean(os.getenv("WHATSAPP_PHONE_NUMBER_ID"))
    recipient = _clean(recipient_number) or _clean(os.getenv("WHATSAPP_RECIPIENT_NUMBER"))

    if not access_token:
        print("[WHATSAPP] WHATSAPP_ACCESS_TOKEN is missing in .env")
        return False, NOT_CONFIGURED_MESSAGE
    if not phone_number_id:
        print("[WHATSAPP] WHATSAPP_PHONE_NUMBER_ID is missing in .env")
        return False, NOT_CONFIGURED_MESSAGE
    if not recipient:
        return False, "Please enter a WhatsApp number to send the update to."
    if not is_valid_recipient(recipient):
        return False, "Please enter a valid WhatsApp number with country code (e.g. 919876543210)."

    # WhatsApp API wants digits only (country code + number, no +, no spaces)
    recipient = "".join(ch for ch in recipient if ch.isdigit())

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {"preview_url": False, "body": message},
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)

        if response.status_code == 200:
            data = response.json()
            if data.get("messages"):
                return True, "✅ WhatsApp weather update sent successfully!"
            return False, "WhatsApp did not confirm the message. Please try again."

        try:
            error = response.json().get("error", {})
        except ValueError:
            error = {}

        code = error.get("code")
        print(f"[WHATSAPP ERROR] HTTP {response.status_code} | Code: {code} | Message: {error.get('message')}")

        if code == 190 or response.status_code == 401:
            return False, "WhatsApp access token is invalid or expired. Please generate a new token."
        if code == 131047:
            return False, ("The 24-hour chat window is closed. Send 'Hi' from your WhatsApp "
                           "to the WhatsApp test number, then click the button again.")
        if code == 131030:
            return False, ("This number is not yet allowed to receive messages from this app "
                           "(add it in Meta API Setup -> 'To' -> Manage phone number list).")
        if code == 100:
            return False, "Phone number ID or recipient number looks incorrect. Please check your .env file."
        return False, "WhatsApp API returned an error. Please try again."

    except requests.exceptions.ConnectionError:
        return False, "No internet connection. Please check your network and try again."
    except requests.exceptions.Timeout:
        return False, "The WhatsApp request timed out. Please try again."
    except Exception:
        return False, "Unable to send the WhatsApp message. Please try again."
