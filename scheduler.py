# scheduler.py
# Runs a safe, once-a-day background job that sends a WhatsApp weather
# update to every opted-in user, for their own preferred city.
# Uses APScheduler's BackgroundScheduler -- NOT an uncontrolled infinite loop.

import os
from apscheduler.schedulers.background import BackgroundScheduler

from database import get_opted_in_users
from whatsapp_service import build_whatsapp_message, send_whatsapp_message, is_valid_recipient

DAILY_UPDATE_HOUR = int(os.getenv("DAILY_UPDATE_HOUR", "7"))
DAILY_UPDATE_MINUTE = int(os.getenv("DAILY_UPDATE_MINUTE", "0"))

_scheduler = None  # module-level, so it is only ever created once


def send_daily_weather_updates(get_current_weather):
    """
    Sends one WhatsApp weather update to every opted-in user, using their
    own preferred city. get_current_weather is passed in from app.py to
    avoid a circular import. Returns a list of per-user result dicts.
    """
    results = []
    users = get_opted_in_users()

    for user in users:
        if not is_valid_recipient(user["whatsapp_number"]):
            results.append({"user": user["name"], "status": "skipped", "info": "Invalid WhatsApp number."})
            continue

        weather_data, error = get_current_weather(user["preferred_city"])
        if error or not weather_data:
            results.append({"user": user["name"], "status": "skipped", "info": error or "Weather data unavailable."})
            continue

        message = build_whatsapp_message(weather_data)
        success, info = send_whatsapp_message(message, recipient_number=user["whatsapp_number"])
        results.append({"user": user["name"], "status": "sent" if success else "failed", "info": info})
        print(f"[DAILY UPDATE] {user['name']} ({user['preferred_city']}): {'sent' if success else 'failed'} - {info}")

    return results


def start_scheduler(get_current_weather):
    """
    Starts the background scheduler exactly once per running process.
    Call this once when the Flask app starts.
    """
    global _scheduler
    if _scheduler is not None:
        return  # already running -- avoid starting it twice

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        lambda: send_daily_weather_updates(get_current_weather),
        trigger="cron",
        hour=DAILY_UPDATE_HOUR,
        minute=DAILY_UPDATE_MINUTE,
        id="daily_weather_whatsapp_update",
        replace_existing=True,
    )
    _scheduler.start()
    print(f"[SCHEDULER] Daily WhatsApp update scheduled for {DAILY_UPDATE_HOUR:02d}:{DAILY_UPDATE_MINUTE:02d} every day.")
