# ==================================================
# Features/gmail_tool.py — Gmail via Google API
# Requires: Google OAuth (run setup_mcp.py once)
# ==================================================

from __future__ import annotations
import base64
import re
from mcp_bridge import google_get, google_post, is_google_authorized

_GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


# ─────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────

def _decode_body(payload: dict) -> str:
    """Extract plain text body from a Gmail message payload."""
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    data = payload.get("body", {}).get("data", "")
    if data:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    return ""


def _get_header(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


# ─────────────────────────────────────────────────
# GMAIL OPERATIONS
# ─────────────────────────────────────────────────

def get_unread_emails(max_results: int = 5) -> list[dict]:
    """Return latest unread emails as list of dicts."""
    data    = google_get(f"{_GMAIL_BASE}/messages",
                         {"labelIds": "UNREAD", "maxResults": max_results})
    msgs    = data.get("messages", [])
    results = []

    for msg in msgs:
        detail = google_get(f"{_GMAIL_BASE}/messages/{msg['id']}",
                            {"format": "metadata",
                             "metadataHeaders": ["Subject", "From", "Date"]})
        headers = detail.get("payload", {}).get("headers", [])
        results.append({
            "id":      msg["id"],
            "subject": _get_header(headers, "Subject") or "(no subject)",
            "from":    _get_header(headers, "From"),
            "date":    _get_header(headers, "Date"),
            "snippet": detail.get("snippet", ""),
        })

    return results


def read_email_by_index(emails: list[dict], index: int) -> str:
    """Fetch and return the full body of email at given index (0-based)."""
    if not 0 <= index < len(emails):
        return "Invalid email number."

    email_id = emails[index]["id"]
    detail   = google_get(f"{_GMAIL_BASE}/messages/{email_id}", {"format": "full"})
    payload  = detail.get("payload", {})
    body     = _decode_body(payload) or _strip_html(detail.get("snippet", ""))

    headers  = payload.get("headers", [])
    subject  = _get_header(headers, "Subject")
    sender   = _get_header(headers, "From")

    return f"From: {sender}\nSubject: {subject}\n\n{body[:1000]}"


def send_email(to: str, subject: str, body: str) -> str:
    """Send a plain-text email."""
    import email.mime.text
    msg    = email.mime.text.MIMEText(body)
    msg["to"]      = to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    google_post(f"{_GMAIL_BASE}/messages/send", {"raw": raw})
    return f"Email sent to {to}."


def search_emails(query: str, max_results: int = 5) -> list[dict]:
    """Search emails by Gmail query string (e.g. 'from:boss@mit.edu')."""
    data  = google_get(f"{_GMAIL_BASE}/messages",
                       {"q": query, "maxResults": max_results})
    msgs  = data.get("messages", [])
    results = []

    for msg in msgs:
        detail = google_get(f"{_GMAIL_BASE}/messages/{msg['id']}",
                            {"format": "metadata",
                             "metadataHeaders": ["Subject", "From", "Date"]})
        headers = detail.get("payload", {}).get("headers", [])
        results.append({
            "id":      msg["id"],
            "subject": _get_header(headers, "Subject") or "(no subject)",
            "from":    _get_header(headers, "From"),
            "snippet": detail.get("snippet", ""),
        })

    return results


# ─────────────────────────────────────────────────
# MAIN HANDLER — called by GmailTool
# ─────────────────────────────────────────────────

def handle_gmail_request(details: str) -> str:
    if not is_google_authorized():
        return ("Boss, Gmail is not connected yet. "
                "Please run  python setup_mcp.py  once to authorize.")

    d = details.lower()

    try:
        # Send email
        if any(w in d for w in ["send email", "send an email", "email to"]):
            return ("Boss, who should I send the email to, and what's the message? "
                    "Please type: send email to [address] subject [subject] message [body]")

        # Search
        if "from" in d or "search" in d or "find email" in d:
            query = details.replace("search", "").replace("find email", "").strip()
            emails = search_emails(query)
            if not emails:
                return "No emails matched that search."
            lines = [f"{i+1}. {e['subject']} — from {e['from']}"
                     for i, e in enumerate(emails)]
            return "Here are the matching emails:\n" + "\n".join(lines)

        # Read email number
        import re
        m = re.search(r'\b(\d+)\b', details)
        if m and any(w in d for w in ["read", "open", "show me"]):
            idx    = int(m.group(1)) - 1
            emails = get_unread_emails(10)
            return read_email_by_index(emails, idx)

        # Default: show unread
        emails = get_unread_emails(5)
        if not emails:
            return "Boss, your inbox is clear — no unread emails."

        lines = [f"{i+1}. {e['subject']} — from {e['from'].split('<')[0].strip()} ({e['snippet'][:60]}...)"
                 for i, e in enumerate(emails)]
        return ("You have {} unread email{}:\n".format(
            len(emails), "s" if len(emails) != 1 else "") +
            "\n".join(lines))

    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Boss, Gmail error: {e}"