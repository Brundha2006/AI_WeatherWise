AI WeatherWise API - Daily Automatic WhatsApp Weather Updates
================================================================

இப்போ இருக்குறது: Sign Up-ல "WhatsApp updates" checkbox tick பண்ணி,
Preferred City கொடுத்த users-க்கு, ஒவ்வொரு நாளும் ஒரு fixed நேரத்தில்
(default: காலை 7:00), namma app தானாகவே WhatsApp message அனுப்பும் --
யாரும் login பண்ணி இருக்க வேண்டிய அவசியம் இல்லை, app process run
ஆகிட்டு இருந்தா போதும்.

STEP 1: .env
------------
உங்க old .env-ல இருந்து WEATHER_API_KEY, WHATSAPP_ACCESS_TOKEN,
WHATSAPP_PHONE_NUMBER_ID-ஐ இந்த zip-ஓட .env-ல copy பண்ணுங்க.

Optional (மாத்தணும்னா மட்டும்):
    DAILY_UPDATE_HOUR=7        (24-hour format, default 7 AM)
    DAILY_UPDATE_MINUTE=0

STEP 2: Run
-----------
    pip install -r requirements.txt
    python app.py
Browser: http://127.0.0.1:5000

Terminal-ல இந்த வரி தெரியணும்:
    [SCHEDULER] Daily WhatsApp update scheduled for 07:00 every day.

STEP 3: Test
------------
1. "Sign Up" பண்ணுங்க: Name, Email, Password, WhatsApp number, checkbox
   tick பண்ணி, "Preferred City" (உதா: Musiri) கொடுங்க.
2. Weather Dashboard-க்கு வந்ததும், ஒரு city search பண்ணுங்க -- WhatsApp
   உடனே வரும் (இது "search பண்ணும்போதே" auto-send, முன்பே இருந்தது).
3. **"📤 Send Daily Update Now (Demo)"** button அழுத்துங்க -- இது
   காலை 7 மணி வரைக்கும் காத்திருக்காம, daily broadcast job-ஐ இப்பவே
   trigger பண்ணி, result page-ல யாருக்கு message போச்சுன்னு காட்டும்.
   Mam-கிட்ட demo பண்ண இந்த button-ஐ use பண்ணுங்க.
4. Real-ஆ தினமும் காலை 7 மணிக்கு தானா அனுப்ப வேணும்னா, server-ஐ
   (local-ஆ இருந்தாலும், Render-ல deploy பண்ணினாலும்) continuously
   run ஆகிட்டு இருக்கும் படி வைச்சிருக்கணும்.

NOTE: Existing weather.db இருந்தா, "whatsapp_opt_in" மற்றும்
"preferred_city" columns தானா சேர்த்துக்கொள்ளப்படும்.

⚠️ META-ஓட முக்கிய Limit (code பிரச்சனை இல்ல)
-------------------------------------------------
Development mode-ல, Meta "API Setup -> To -> Manage phone number list"-ல
verify பண்ணின numbers-க்கு மட்டும் (max 5) real message போகும். புது
user sign up பண்ணி, அவங்க number அந்த list-ல இல்லைன்னா, "Skipped" /
"Failed" status-உடன் friendly reason தெரியும், app crash ஆகாது.

ONLINE DEPLOY (Render.com) -- முன்பே கொடுத்த steps அப்படியே
-----------------------------------------------------------------
gunicorn, Procfile already இந்த zip-ல இருக்கு. GitHub repo-ல upload
பண்ணி, Render-ல Web Service create பண்ணி, Environment Variables
(WEATHER_API_KEY, WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID,
FLASK_SECRET_KEY) சேர்த்தா, scheduler server-லேயே run ஆகிட்டு இருக்கும்,
server sleep ஆகாத வரைக்கும்.

STOP SERVER: Ctrl+C
