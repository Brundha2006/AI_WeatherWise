# app.py
# AI WeatherWise API - Flask application
# Current Weather + Rain Info + 7-Day Forecast (One Call API 3.0) + WhatsApp Weather Update

import os
from datetime import datetime, timedelta
from functools import wraps

import requests
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

from database import (
    init_db, add_search, get_all_history, clear_history,
    create_user, get_user_by_email, get_user_by_id
)
from whatsapp_service import build_whatsapp_message, send_whatsapp_message, is_valid_recipient
from scheduler import start_scheduler, send_daily_weather_updates

load_dotenv()

API_KEY = os.getenv("WEATHER_API_KEY")
CURRENT_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

init_db()


def current_user():
    """Returns the logged-in user's dict, or None."""
    user_id = session.get("user_id")
    return get_user_by_id(user_id) if user_id else None


def login_required(view):
    """Redirects to the login page if no one is logged in."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

FRIENDLY_ERROR = "Unable to fetch weather data. Please check your city name or try again."


def get_weather_analysis(temp, condition, wind_speed):
    """Builds a simple, safe, non-medical weather summary and outdoor suggestion."""
    condition_lower = condition.lower()

    if temp <= 15:
        temp_comment = "It is quite cold."
    elif temp <= 25:
        temp_comment = "The temperature is pleasant."
    elif temp <= 35:
        temp_comment = "It is warm."
    else:
        temp_comment = "It is very hot."

    if "rain" in condition_lower or "storm" in condition_lower or "thunder" in condition_lower:
        outdoor = "Not suitable for outdoor activity right now. Carry an umbrella if you go out."
    elif "snow" in condition_lower:
        outdoor = "Outdoor activity may be difficult due to snow. Dress warmly if you go out."
    elif temp > 35:
        outdoor = "Outdoor activity is not advisable due to high heat. Stay hydrated."
    elif "clear" in condition_lower or "clouds" in condition_lower:
        outdoor = "Good weather for normal outdoor activity."
    else:
        outdoor = "Weather conditions are moderate. Outdoor activity should be fine."

    wind_comment = ""
    if wind_speed > 10:
        wind_comment = " Wind speed is high, so be careful if you're outside."

    return f"{temp_comment} Current condition: {condition}. {outdoor}{wind_comment}"


def get_rain_analysis(rain_mm, condition, forecast):
    """Generates a simple rain status message from real API values only."""
    condition_lower = condition.lower()

    if rain_mm is not None or any(w in condition_lower for w in ["rain", "drizzle", "thunderstorm"]):
        return "Rain is currently reported in this location."

    if forecast:
        today_pop = forecast[0]["rain_chance"]
        if today_pop >= 50:
            return "Rain is possible during the forecast period."
        elif today_pop > 0:
            return "Low chance of rain is expected."

    return "No rain is currently reported."


def format_time(unix_ts, tz_offset_seconds):
    """Converts a UTC unix timestamp to a local HH:MM AM/PM string using the city's UTC offset."""
    try:
        local_dt = datetime.utcfromtimestamp(unix_ts) + timedelta(seconds=tz_offset_seconds)
        return local_dt.strftime("%I:%M %p")
    except Exception:
        return "N/A"


def get_current_weather(city):
    """
    Fetches current weather (including rain, if reported) for a city.
    Returns (weather_dict, error_message). Only one of them will be set.
    """
    try:
        params = {"q": city, "appid": API_KEY, "units": "metric"}
        response = requests.get(CURRENT_WEATHER_URL, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            tz_offset = data.get("timezone", 0)

            rain_field = data.get("rain")
            rain_mm = None
            if rain_field:
                rain_mm = rain_field.get("1h", rain_field.get("3h"))

            weather_data = {
                "city": data["name"],
                "temperature": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "condition": data["weather"][0]["description"].title(),
                "humidity": data["main"]["humidity"],
                "wind_speed": data["wind"]["speed"],
                "pressure": data["main"]["pressure"],
                "visibility": data.get("visibility", "N/A"),
                "icon": data["weather"][0]["icon"],
                "sunrise": format_time(data["sys"]["sunrise"], tz_offset),
                "sunset": format_time(data["sys"]["sunset"], tz_offset),
                "rain_mm": rain_mm,
                "lat": data["coord"]["lat"],
                "lon": data["coord"]["lon"],
                "tz_offset": tz_offset,
            }
            return weather_data, None

        elif response.status_code == 404:
            return None, "City not found. Please check the spelling and try again."
        elif response.status_code == 401:
            return None, "Invalid API key. Please check your .env file."
        else:
            return None, FRIENDLY_ERROR

    except requests.exceptions.ConnectionError:
        return None, "No internet connection. Please check your network and try again."
    except requests.exceptions.Timeout:
        return None, "The request timed out. Please try again."
    except (KeyError, ValueError, TypeError):
        return None, "Unexpected weather data received. Please try again."
    except Exception:
        return None, FRIENDLY_ERROR


def get_seven_day_forecast(lat, lon, tz_offset):
    """
    Fetches a true daily forecast (with rain probability/amount) and hourly
    rain probability (Morning/Afternoon/Evening/Night for today) using One Call API 3.0.
    Returns (forecast_list, hourly_rain_dict). Both are empty if the forecast
    cannot be fetched -- current weather still displays fine.
    """
    forecast_list = []
    hourly_rain = {}

    try:
        params = {
            "lat": lat,
            "lon": lon,
            "appid": API_KEY,
            "units": "metric",
            "exclude": "minutely,alerts,current"
        }
        response = requests.get(ONECALL_URL, params=params, timeout=10)

        if response.status_code != 200:
            return [], {}

        data = response.json()
        daily = data.get("daily", [])
        hourly = data.get("hourly", [])

        day_labels = ["Today", "Tomorrow", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7"]

        for i, day in enumerate(daily[:7]):
            local_dt = datetime.utcfromtimestamp(day["dt"]) + timedelta(seconds=tz_offset)
            rain_amount = day.get("rain")
            forecast_list.append({
                "label": day_labels[i] if i < len(day_labels) else local_dt.strftime("%a"),
                "date": local_dt.strftime("%d %b"),
                "condition": day["weather"][0]["description"].title(),
                "icon": day["weather"][0]["icon"],
                "min_temp": round(day["temp"]["min"], 1),
                "max_temp": round(day["temp"]["max"], 1),
                "humidity": day.get("humidity", "N/A"),
                "rain_chance": round(day.get("pop", 0) * 100),
                "rain_amount": round(rain_amount, 1) if rain_amount is not None else None
            })

        buckets = {"Morning": [], "Afternoon": [], "Evening": [], "Night": []}
        today_date = None

        for entry in hourly:
            local_dt = datetime.utcfromtimestamp(entry["dt"]) + timedelta(seconds=tz_offset)
            date_str = local_dt.strftime("%Y-%m-%d")

            if today_date is None:
                today_date = date_str
            if date_str != today_date:
                break

            hour = local_dt.hour
            pop_pct = round(entry.get("pop", 0) * 100)

            if 6 <= hour < 12:
                buckets["Morning"].append(pop_pct)
            elif 12 <= hour < 17:
                buckets["Afternoon"].append(pop_pct)
            elif 17 <= hour < 21:
                buckets["Evening"].append(pop_pct)
            else:
                buckets["Night"].append(pop_pct)

        for part, values in buckets.items():
            if values:
                hourly_rain[part] = max(values)

    except Exception:
        return [], {}

    return forecast_list, hourly_rain


def build_dashboard(city, save_history):
    """
    Collects everything the weather dashboard needs for one city.
    Used by both the Search/Refresh route and the WhatsApp route,
    so the dashboard always looks the same.
    """
    context = {
        "weather": None,
        "error": None,
        "analysis": None,
        "rain_analysis": None,
        "forecast": [],
        "hourly_rain": {},
        "wa_success": None,
        "wa_error": None,
    }

    weather_data, error = get_current_weather(city)
    context["error"] = error

    if weather_data:
        context["weather"] = weather_data
        context["analysis"] = get_weather_analysis(
            weather_data["temperature"],
            weather_data["condition"],
            weather_data["wind_speed"]
        )

        if save_history:
            try:
                add_search(
                    weather_data["city"],
                    weather_data["temperature"],
                    weather_data["condition"],
                    weather_data["humidity"],
                    weather_data["wind_speed"]
                )
            except Exception:
                pass  # history saving should never block showing weather

        forecast_data, hourly_rain = get_seven_day_forecast(
            weather_data["lat"],
            weather_data["lon"],
            weather_data["tz_offset"]
        )
        context["forecast"] = forecast_data
        context["hourly_rain"] = hourly_rain
        context["rain_analysis"] = get_rain_analysis(
            weather_data["rain_mm"],
            weather_data["condition"],
            forecast_data
        )

    return context


@app.route("/")
def home():
    return render_template("home.html", user=current_user())


@app.route("/weather", methods=["GET", "POST"])
def weather():
    context = {
        "weather": None, "error": None, "analysis": None, "rain_analysis": None,
        "forecast": [], "hourly_rain": {}, "wa_success": None, "wa_error": None,
    }
    user = current_user()

    if request.method == "POST":
        city = request.form.get("city", "").strip()

        if not city:
            context["error"] = "Please enter a city name."
        else:
            context = build_dashboard(city, save_history=True)

            # Opted-in, logged-in users get the WhatsApp update automatically -
            # no separate button click needed.
            if context["weather"] and user and user["whatsapp_opt_in"]:
                if is_valid_recipient(user["whatsapp_number"]):
                    message = build_whatsapp_message(context["weather"])
                    success, info = send_whatsapp_message(message, recipient_number=user["whatsapp_number"])
                    context["wa_success"] = info if success else None
                    context["wa_error"] = None if success else info
                else:
                    context["wa_error"] = "Your saved WhatsApp number looks invalid. Please update it from Sign Up again."

    context["user"] = user
    return render_template("weather.html", **context)


@app.route("/send_whatsapp", methods=["POST"])
@login_required
def send_whatsapp():
    city = request.form.get("city", "").strip()
    user = current_user()

    if not city:
        context = {
            "weather": None, "error": "Please search a city first.", "analysis": None,
            "rain_analysis": None, "forecast": [], "hourly_rain": {},
            "wa_success": None, "wa_error": None, "user": user,
        }
        return render_template("weather.html", **context)

    context = build_dashboard(city, save_history=False)
    context["user"] = user

    if context["weather"]:
        recipient_number = user["whatsapp_number"]
        if not is_valid_recipient(recipient_number):
            context["wa_error"] = "Your saved WhatsApp number looks invalid. Please update it from Sign Up again."
        else:
            message = build_whatsapp_message(context["weather"])
            success, info = send_whatsapp_message(message, recipient_number=recipient_number)

            if success:
                context["wa_success"] = info
            else:
                context["wa_error"] = info

    return render_template("weather.html", **context)


@app.route("/history")
def history():
    try:
        records = get_all_history()
    except Exception:
        records = []
    return render_template("history.html", records=records, user=current_user())


@app.route("/clear_history", methods=["POST"])
def clear_history_route():
    clear_history()
    return redirect(url_for("history"))


@app.route("/about")
def about():
    return render_template("about.html", user=current_user())


# ---------------- Account routes ----------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        whatsapp_number = request.form.get("whatsapp_number", "").strip()
        preferred_city = request.form.get("preferred_city", "").strip()
        whatsapp_opt_in = 1 if request.form.get("whatsapp_opt_in") else 0

        if not name or not email or not password or not whatsapp_number:
            error = "Please fill in all fields."
        elif not is_valid_recipient(whatsapp_number):
            error = "Please enter a valid WhatsApp number with country code (e.g. 919876543210)."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif whatsapp_opt_in and not preferred_city:
            error = "Please enter a preferred city for your daily WhatsApp update."
        else:
            try:
                password_hash = generate_password_hash(password)
                create_user(name, email, password_hash, whatsapp_number, whatsapp_opt_in, preferred_city or None)
                user = get_user_by_email(email)
                session["user_id"] = user["id"]
                return redirect(url_for("weather"))
            except Exception:
                error = "An account with this email already exists. Please log in instead."

    return render_template("signup.html", error=error, user=current_user())


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            next_page = request.args.get("next")
            return redirect(next_page or url_for("weather"))
        else:
            error = "Incorrect email or password. Please try again."

    return render_template("login.html", error=error, user=current_user())


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("home"))


@app.route("/send_daily_updates_now", methods=["POST"])
@login_required
def send_daily_updates_now():
    """
    Demo-only button: triggers the same daily broadcast job immediately,
    instead of waiting for the scheduled time, so it can be shown live.
    """
    results = send_daily_weather_updates(get_current_weather)
    return render_template("daily_update_results.html", results=results, user=current_user())


# Start the once-a-day WhatsApp broadcast job. This runs at module load time
# so it starts for both "python app.py" (below) and a production server such
# as gunicorn (which imports this file directly and never reaches __main__).
start_scheduler(get_current_weather)


if __name__ == "__main__":
    # use_reloader=False avoids Flask's debug auto-reloader starting a second
    # copy of the process (which would start the scheduler twice).
    app.run(debug=True, use_reloader=False)
