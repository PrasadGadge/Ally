# ==================================================
# Features/calendar_tool.py — Google Calendar via API
# Requires: Google OAuth (run setup_mcp.py once)
# ==================================================

from __future__ import annotations
import datetime
from mcp_bridge import google_get, google_post, is_google_authorized

_CAL_BASE = "https://www.googleapis.com/calendar/v3"


# ─────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────

def _fmt_event(event: dict) -> str:
    summary = event.get("summary", "Untitled")
    start   = event.get("start", {})
    time_str = start.get("dateTime", start.get("date", ""))

    if "T" in time_str:
        dt = datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        time_str = dt.strftime("%I:%M %p")
    else:
        time_str = "All day"

    location = event.get("location", "")
    return f"{time_str} — {summary}" + (f" @ {location}" if location else "")


def _today_range() -> tuple[str, str]:
    now   = datetime.datetime.utcnow()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end   = start + datetime.timedelta(days=1)
    return start.isoformat() + "Z", end.isoformat() + "Z"


def _tomorrow_range() -> tuple[str, str]:
    now   = datetime.datetime.utcnow()
    start = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end   = start + datetime.timedelta(days=1)
    return start.isoformat() + "Z", end.isoformat() + "Z"


def _this_week_range() -> tuple[str, str]:
    now   = datetime.datetime.utcnow()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end   = start + datetime.timedelta(days=7)
    return start.isoformat() + "Z", end.isoformat() + "Z"


# ─────────────────────────────────────────────────
# CALENDAR OPERATIONS
# ─────────────────────────────────────────────────

def get_events(time_min: str, time_max: str,
               max_results: int = 10, calendar_id: str = "primary") -> list[dict]:
    data = google_get(
        f"{_CAL_BASE}/calendars/{calendar_id}/events",
        {
            "timeMin":    time_min,
            "timeMax":    time_max,
            "maxResults": max_results,
            "singleEvents": "true",
            "orderBy":    "startTime",
        }
    )
    return data.get("items", [])


def create_event(title: str, start_dt: str, end_dt: str,
                 description: str = "", location: str = "") -> str:
    """
    Create a calendar event.
    start_dt / end_dt: ISO 8601 strings e.g. "2026-06-01T14:00:00+05:30"
    """
    body = {
        "summary":     title,
        "description": description,
        "location":    location,
        "start":       {"dateTime": start_dt},
        "end":         {"dateTime": end_dt},
    }
    google_post(f"{_CAL_BASE}/calendars/primary/events", body)
    return f"Event '{title}' created."


def get_today_events() -> list[dict]:
    t_min, t_max = _today_range()
    return get_events(t_min, t_max)


def get_tomorrow_events() -> list[dict]:
    t_min, t_max = _tomorrow_range()
    return get_events(t_min, t_max)


def get_week_events() -> list[dict]:
    t_min, t_max = _this_week_range()
    return get_events(t_min, t_max, max_results=20)


# ─────────────────────────────────────────────────
# MAIN HANDLER — called by CalendarTool
# ─────────────────────────────────────────────────

def handle_calendar_request(details: str) -> str:
    if not is_google_authorized():
        return ("Boss, Google Calendar is not connected yet. "
                "Please run  python setup_mcp.py  once to authorize.")

    d = details.lower()

    try:
        # Create event
        if any(w in d for w in ["add event", "create event", "schedule", "book"]):
            return ("Boss, to add a calendar event say: "
                    "add event [title] on [date] at [time]")

        # This week
        if "week" in d or "this week" in d:
            events = get_week_events()
            if not events:
                return "Boss, your calendar is clear this week."
            lines = [_fmt_event(e) for e in events]
            return "This week:\n" + "\n".join(lines)

        # Tomorrow
        if "tomorrow" in d:
            events = get_tomorrow_events()
            if not events:
                return "Boss, nothing scheduled for tomorrow."
            lines = [_fmt_event(e) for e in events]
            return "Tomorrow:\n" + "\n".join(lines)

        # Default: today
        events = get_today_events()
        if not events:
            return "Boss, your calendar is clear today. No events scheduled."

        lines = [_fmt_event(e) for e in events]
        return (f"You have {len(events)} event{'s' if len(events) != 1 else ''} today:\n"
                + "\n".join(lines))

    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Boss, Calendar error: {e}"