# FIX: was using non-blocking speak() throughout.
# All three speak() calls fired simultaneously → voices overlapping.
# Now uses speak_blocking() so each line waits to finish before the next.

from Features.weather_system         import speak_weather
from Features.check_internet_speed   import get_internet_speed
from Features.web_search             import search_web
from TextToSpeech.Fast_DF_TTS        import speak_blocking


def morning_brief():

    speak_blocking("Good morning Boss. Here is your daily briefing.")

    # Weather — speak_weather() calls speak() internally;
    # it's a long blocking call so this naturally serialises.
    speak_weather()

    # Internet speed
    speed = get_internet_speed()
    speak_blocking(f"Your internet speed is {speed} megabits per second.")

    # Top news headline
    results = search_web("latest world news")
    if results:
        headline = results[0].get("title", "")
        if headline:
            speak_blocking(f"Today's top headline: {headline}")
