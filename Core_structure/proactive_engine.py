# ==================================================
# proactive_engine.py — Vivie Proactive Engine
#
# Fixes in this version:
#  • CRITICAL: reminders now run in a SEPARATE 60s loop.
#    Previously inside the 30-min main loop — any reminder
#    with a 5-min fire window between cycles was silently missed.
#  • Idle detection — skips heavy checks if user hasn't
#    spoken in > 45 min. Won't disturb during sleep hours.
#  • Topic personalization — news topics pulled from
#    recent episodic memory instead of random hardcoded list.
#  • Suggestion dismissal tracking — stops repeating
#    suggestions the user has already heard 3+ times.
#  • Parallel architecture: reminder loop (60s) runs
#    independently of main check loop (30 min).
# ==================================================

import threading
import time
import datetime
import os
import json

from Features.web_search      import search_web
from Features.morning_brief   import morning_brief
from TextToSpeech.Fast_DF_TTS import speak_blocking
from voice_state              import set_speaking, is_speaking


# ─────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────

REMINDER_CHECK_INTERVAL = 60          # seconds — fast loop for reminders
CHECK_INTERVAL          = 30 * 60     # seconds — main loop (battery, news, etc.)
MORNING_HOUR            = 8
MORNING_MINUTE          = 0
BATTERY_THRESHOLD       = 20
MAX_LOOP_ERRORS         = 5
IDLE_THRESHOLD_MIN      = 45          # minutes before we consider user idle
QUIET_HOURS             = (23, 7)     # don't disturb between 11 PM and 7 AM
MAX_SUGGESTION_REPEATS  = 3           # stop suggesting after this many times

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR    = os.path.dirname(BASE_DIR)
SCHEDULE_FILE  = os.path.join(PROJECT_DIR, "schedule.txt")
REMINDERS_FILE = os.path.join(PROJECT_DIR, "data", "reminders.json")


# ─────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────

_state = {
    "morning_brief_done":   False,
    "last_news_update":     None,
    "last_check_date":      None,
    "last_run":             None,
    "last_behavior_check":  None,
    "last_battery_alert":   None,
    "schedule_fired_today": set(),
    "last_user_active":     datetime.datetime.now(),   # updated by main_brain
    "suggestion_counts":    {},                        # track repeated suggestions
    "meetings_notified":    set(),                     # track upcoming meetings
}
_state_lock = threading.Lock()


def mark_user_active():
    """Call this from main_brain whenever user speaks. Enables idle detection."""
    with _state_lock:
        _state["last_user_active"] = datetime.datetime.now()


def _is_user_idle() -> bool:
    """True if user hasn't spoken in > IDLE_THRESHOLD_MIN minutes."""
    with _state_lock:
        last = _state["last_user_active"]
    idle_min = (datetime.datetime.now() - last).total_seconds() / 60
    return idle_min > IDLE_THRESHOLD_MIN


def _is_quiet_hours() -> bool:
    """True between 11 PM and 7 AM — don't disturb."""
    h = datetime.datetime.now().hour
    start, end = QUIET_HOURS
    if start > end:
        return h >= start or h < end
    return start <= h < end


# ─────────────────────────────────────────────────
# SAFE SPEAK
# ─────────────────────────────────────────────────

def _safe_speak(text: str):
    if not text or not text.strip():
        return
    if is_speaking():
        print(f"[ProactiveEngine] Skipping speak — already speaking: {text[:40]}")
        return
    if _is_quiet_hours():
        print(f"[ProactiveEngine] Quiet hours — suppressed: {text[:40]}")
        return
    try:
        set_speaking(True)
        speak_blocking(text, intent="suggestion")
    except Exception as e:
        print(f"[ProactiveEngine] Speak error: {e}")
    finally:
        set_speaking(False)


# ─────────────────────────────────────────────────
# UI UPDATE
# ─────────────────────────────────────────────────

def _update_ui(text: str):
    try:
        from Vivie_UI import emit_to_ui
        now = datetime.datetime.now().strftime("%H:%M:%S")
        emit_to_ui("sig_log", f"[{now}] 💡 {text}")
    except Exception:
        pass


# ─────────────────────────────────────────────────
# DAILY STATE RESET
# ─────────────────────────────────────────────────

def _reset_daily_state_if_needed():
    today = datetime.date.today().isoformat()
    if _state["last_check_date"] != today:
        _state["morning_brief_done"]  = False
        _state["last_news_update"]    = None
        _state["last_check_date"]     = today
        _state["last_battery_alert"]  = None
        _state["schedule_fired_today"] = set()
        _state["suggestion_counts"]   = {}
        _state["meetings_notified"]   = set()
        print("[ProactiveEngine] New day — state reset.")


# ─────────────────────────────────────────────────
# CHECK 1 — MORNING BRIEF
# ─────────────────────────────────────────────────

def _check_morning_brief():
    try:
        now = datetime.datetime.now()
        if (now.hour  == MORNING_HOUR and
            now.minute < 35 and
            not _state["morning_brief_done"] and
            not _is_user_idle()):

            print("[ProactiveEngine] Morning brief...")
            _safe_speak("Good morning Boss. Here is your morning brief.")
            morning_brief()
            _state["morning_brief_done"] = True
            _update_ui("Morning brief delivered.")

    except Exception as e:
        print(f"[ProactiveEngine] Morning brief error: {e}")


# ─────────────────────────────────────────────────
# CHECK 2 — NEWS UPDATES
# Now uses episodic memory for topic personalization
# ─────────────────────────────────────────────────

def _get_personalized_topics() -> list:
    """
    Pull topics from recent episodic memory — what has the user
    actually been asking about? Fall back to curated AI/tech list.
    """
    try:
        from memory_core.episodic_memory import load_episodes
        episodes = load_episodes()
        recent   = episodes[-30:] if len(episodes) >= 30 else episodes

        # Collect user inputs from recent sessions
        raw_topics = []
        for ep in reversed(recent):
            ui = ep.get("user_input", "").lower().strip()
            # Skip noise — greetings, commands, very short inputs
            if len(ui.split()) >= 4 and not any(
                ui.startswith(w) for w in
                ["open ", "close ", "play ", "scroll ", "set alarm",
                 "remind me", "tell me at", "hey", "ok", "yes", "no"]
            ):
                raw_topics.append(ui[:60])
            if len(raw_topics) >= 5:
                break

        if raw_topics:
            search_topics = [f"{t} latest news 2026" for t in raw_topics[:3]]
            return search_topics

    except Exception as e:
        print(f"[ProactiveEngine] Topic personalization error: {e}")

    # Fallback — curated list
    return [
        "artificial intelligence latest 2026",
        "machine learning research breakthroughs",
        "Python programming updates 2026",
        "robotics technology news 2026",
        "deep learning new developments",
    ]


def _check_news_updates():
    try:
        now  = datetime.datetime.now()
        last = _state["last_news_update"]

        if last and (now - last).total_seconds() / 3600 < 2:
            return

        # Skip if user is idle — no point interrupting with news
        if _is_user_idle():
            return

        topics  = _get_personalized_topics()
        import random
        topic   = random.choice(topics)
        results = search_web(topic)

        if results:
            top   = results[0]
            title = top.get("title", "").split(".")[0]
            if title:
                # Dismissal tracking — don't repeat a suggestion too many times
                key   = title[:40]
                count = _state["suggestion_counts"].get(key, 0)
                if count >= MAX_SUGGESTION_REPEATS:
                    return

                msg = (
                    f"Boss, something you might find interesting. "
                    f"{title}. Want me to tell you more?"
                )
                _safe_speak(msg)
                _state["last_news_update"]          = now
                _state["suggestion_counts"][key]    = count + 1
                _update_ui(f"News: {title[:60]}")

    except Exception as e:
        print(f"[ProactiveEngine] News update error: {e}")


# ─────────────────────────────────────────────────
# REMINDERS — FAST LOOP (every 60s)
# CRITICAL FIX: reminders were inside the 30-min loop.
# A reminder set for 3:10 PM with a 5-min fire window
# would be checked at 3:00 PM (missed) then 3:30 PM (expired).
# Now runs in its own 60-second loop — nothing is missed.
# ─────────────────────────────────────────────────

def _load_reminders() -> list:
    if not os.path.exists(REMINDERS_FILE):
        return []
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_reminders(reminders: list):
    try:
        os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ProactiveEngine] Save reminders error: {e}")


def add_reminder(text: str, remind_time: str) -> bool:
    try:
        reminders = _load_reminders()
        reminders.append({
            "text":       text,
            "time":       remind_time,
            "created_at": datetime.datetime.now().isoformat(),
            "done":       False,
        })
        _save_reminders(reminders)
        print(f"[ProactiveEngine] Reminder added: {text} at {remind_time}")
        return True
    except Exception as e:
        print(f"[ProactiveEngine] Add reminder error: {e}")
        return False


def _check_reminders():
    try:
        reminders = _load_reminders()
        if not reminders:
            return

        now     = datetime.datetime.now()
        updated = False

        for reminder in reminders:
            if reminder.get("done"):
                continue

            remind_time_str = reminder.get("time", "")
            if not remind_time_str:
                continue

            try:
                if len(remind_time_str) <= 5:
                    remind_dt = datetime.datetime.strptime(
                        f"{now.date()} {remind_time_str}", "%Y-%m-%d %H:%M"
                    )
                else:
                    remind_dt = datetime.datetime.strptime(
                        remind_time_str, "%Y-%m-%d %H:%M"
                    )

                diff = (now - remind_dt).total_seconds()

                # 5-min window — fires within 60s of reminder time
                if 0 <= diff <= 300:
                    _safe_speak(f"Boss, reminder: {reminder['text']}.")
                    _update_ui(f"Reminder: {reminder['text']}")
                    reminder["done"] = True
                    updated = True
                    print(f"[ProactiveEngine] Reminder fired: {reminder['text']}")

            except ValueError:
                continue

        if updated:
            _save_reminders(reminders)

    except Exception as e:
        print(f"[ProactiveEngine] Reminder check error: {e}")


# ─────────────────────────────────────────────────
# CHECK 6 — UPCOMING MEETINGS & WEATHER (PROACTIVE)
# ─────────────────────────────────────────────────

def _check_upcoming_meetings_and_weather():
    try:
        from Features.calendar_tool import get_today_events
        from Features.weather_system import fetch_weather, user_city, detect_city
        from mcp_bridge import is_google_authorized

        if not is_google_authorized():
            return

        events = get_today_events()
        if not events:
            return

        now = datetime.datetime.now()
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        for event in events:
            start = event.get("start", {})
            time_str = start.get("dateTime", "")
            if not time_str:
                continue
                
            try:
                # ISO parsing handling timezones
                dt = datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            except Exception:
                continue

            diff_minutes = (dt - now_utc).total_seconds() / 60

            # 10 to 20 minute window
            if 10 <= diff_minutes <= 20:
                summary = event.get("summary", "Untitled")
                meeting_id = f"{dt.isoformat()}_{summary}"

                if meeting_id in _state["meetings_notified"]:
                    continue

                _state["meetings_notified"].add(meeting_id)

                if not user_city:
                    detect_city()
                weather = fetch_weather(user_city)

                if weather:
                    temp = weather.get("temp", 0)
                    condition = weather.get("condition", "").lower()

                    weather_warning = ""
                    if "rain" in condition or "shower" in condition:
                        weather_warning = "It is currently raining. Take an umbrella and leave early."
                    elif "snow" in condition:
                        weather_warning = "It is snowing. Please be careful on the roads."
                    elif temp >= 35:
                        weather_warning = "It is extremely hot outside. Stay hydrated."
                    elif temp <= 5:
                        weather_warning = "It is freezing outside. Dress warmly."

                    if weather_warning:
                        msg = f"Boss, you have a meeting called '{summary}' in {int(diff_minutes)} minutes. {weather_warning}"
                        _safe_speak(msg)
                        _update_ui(f"Meeting Alert: {summary}")
                    else:
                        msg = f"Boss, just a heads up, your meeting '{summary}' starts in {int(diff_minutes)} minutes."
                        _safe_speak(msg)
                        _update_ui(f"Meeting Alert: {summary}")

    except Exception as e:
        print(f"[ProactiveEngine] Meeting & Weather check error: {e}")


def _reminder_loop():
    """
    Fast dedicated loop — checks reminders every 60 seconds.
    Completely independent of the 30-min main loop.
    """
    print("[ProactiveEngine] Reminder loop started (60s interval).")
    time.sleep(30)  # small initial delay
    while True:
        try:
            _check_reminders()
            _check_schedule()
            _check_upcoming_meetings_and_weather()
        except Exception as e:
            print(f"[ProactiveEngine] Reminder loop error: {e}")
        time.sleep(REMINDER_CHECK_INTERVAL)


# ─────────────────────────────────────────────────
# CHECK 3 — SCHEDULE
# ─────────────────────────────────────────────────

def _check_schedule():
    try:
        if not os.path.exists(SCHEDULE_FILE):
            return

        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        now  = datetime.datetime.now()
        date = now.date().isoformat()

        if "schedule_fired_today" not in _state:
            _state["schedule_fired_today"] = set()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Format A: YYYY-MM-DD HH:MM | Event
            # Format B (legacy): 12:30PM = Event  (today's date)
            event_dt = None
            event_str = None

            if "|" in line:
                parts = line.split("|", 1)
                if len(parts) < 2:
                    continue
                try:
                    event_dt = datetime.datetime.strptime(parts[0].strip(), "%Y-%m-%d %H:%M")
                    event_str = parts[1].strip()
                except ValueError:
                    continue
            elif "=" in line:
                time_part, event_str = line.split("=", 1)
                time_part = time_part.strip()
                event_str = event_str.strip()
                try:
                    t = datetime.datetime.strptime(time_part, "%I:%M%p")
                    event_dt = datetime.datetime.combine(now.date(), t.time())
                except ValueError:
                    continue
            else:
                continue

            try:
                diff_minutes = (event_dt - now).total_seconds() / 60
                fire_key = f"{date}|{event_str}"

                if fire_key in _state["schedule_fired_today"]:
                    continue

                if 0 <= diff_minutes <= 5:
                    mins = int(diff_minutes)
                    msg = (
                        f"Boss, {event_str} is starting now."
                        if mins <= 1 else
                        f"Boss, {event_str} is coming up in {mins} minutes."
                    )
                    _safe_speak(msg)
                    _update_ui(f"{event_str} in {mins} min")
                    _state["schedule_fired_today"].add(fire_key)

            except ValueError:
                continue

    except Exception as e:
        print(f"[ProactiveEngine] Schedule check error: {e}")


# ─────────────────────────────────────────────────
# CHECK 4 — BATTERY
# ─────────────────────────────────────────────────

def _check_battery():
    try:
        import psutil
        bat = psutil.sensors_battery()
        if not bat:
            return

        pct     = int(bat.percent)
        plugged = bat.power_plugged
        now     = datetime.datetime.now()

        last_alert = _state["last_battery_alert"]
        if last_alert and (now - last_alert).total_seconds() / 3600 < 1:
            return

        if pct <= BATTERY_THRESHOLD and not plugged:
            _safe_speak(f"Boss, battery is at {pct} percent. Please plug in your charger.")
            _state["last_battery_alert"] = now
            _update_ui(f"Battery low: {pct}%")

    except Exception as e:
        print(f"[ProactiveEngine] Battery check error: {e}")


# ─────────────────────────────────────────────────
# CHECK 5 — BEHAVIORAL PATTERNS
# ─────────────────────────────────────────────────

def _check_behavior_patterns():
    try:
        now  = datetime.datetime.now()
        last = _state["last_behavior_check"]

        if last and (now - last).total_seconds() / 3600 < 1:
            return

        if _is_user_idle():
            return

        from Core_structure.behavior_engine import get_suggestions
        suggestions = get_suggestions(top_k=1)

        if not suggestions:
            return

        best = suggestions[0]
        msg  = best.get("message", "")

        if not msg or best.get("confidence", 0) < 0.65:
            return

        # Dismissal tracking
        key   = msg[:40]
        count = _state["suggestion_counts"].get(key, 0)
        if count >= MAX_SUGGESTION_REPEATS:
            return

        _safe_speak(f"Boss, {msg}")
        _update_ui(msg)
        _state["last_behavior_check"]    = now
        _state["suggestion_counts"][key] = count + 1

    except Exception as e:
        print(f"[ProactiveEngine] Behavior check error: {e}")


# ─────────────────────────────────────────────────
# MAIN LOOP (30 min) — heavy checks only
# Reminders/schedule moved to fast 60s loop above
# ─────────────────────────────────────────────────

def _proactive_loop():
    print("[ProactiveEngine] Main background engine started.")
    time.sleep(60)   # let Vivie finish booting

    consecutive_errors = 0

    while True:
        try:
            print("[ProactiveEngine] Running main checks...")

            _reset_daily_state_if_needed()

            _check_morning_brief();    time.sleep(2)
            _check_battery();          time.sleep(2)
            _check_behavior_patterns(); time.sleep(2)

            # News only if user is active and not quiet hours
            if not _is_user_idle() and not _is_quiet_hours():
                _check_news_updates()

            _state["last_run"] = datetime.datetime.now().isoformat()
            consecutive_errors = 0
            print("[ProactiveEngine] Main checks done. Next in 30 min.")

        except Exception as e:
            consecutive_errors += 1
            backoff = min(60 * 60, (2 ** consecutive_errors) * 60)
            print(
                f"[ProactiveEngine] Loop error #{consecutive_errors}: {e} "
                f"— backing off {backoff//60} min"
            )
            time.sleep(backoff)
            continue

        time.sleep(CHECK_INTERVAL)


# ─────────────────────────────────────────────────
# START — launches both loops
# ─────────────────────────────────────────────────

def start_proactive_engine():
    # Fast reminder loop — every 60s
    t1 = threading.Thread(target=_reminder_loop, daemon=True)
    t1.start()

    # Main loop — every 30 min
    t2 = threading.Thread(target=_proactive_loop, daemon=True)
    t2.start()

    print("[ProactiveEngine] Both loops launched.")
