# ==================================================
# mcp_bridge.py — Vivie MCP Integration Layer
#
# Handles:
#   • Google OAuth token management (Gmail + Calendar)
#   • GitHub API authentication
#   • Base HTTP helpers for all MCP-connected services
#   • Token refresh + persistence
#
# First run: execute  python setup_mcp.py  to authorize Google.
# GitHub: just add GITHUB_TOKEN to .env — no OAuth needed.
# ==================================================

from __future__ import annotations

import os
import json
import time
import threading
import requests
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────
_BASE        = Path(__file__).parent
_TOKEN_FILE  = _BASE / "data" / "google_tokens.json"
_TOKEN_LOCK  = threading.Lock()

# ── Google OAuth endpoints ────────────────────────────────────────────────
_GOOGLE_TOKEN_URL    = "https://oauth2.googleapis.com/token"
_GOOGLE_AUTH_URL     = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_REVOKE_URL   = "https://oauth2.googleapis.com/revoke"

# ── Required Google scopes ────────────────────────────────────────────────
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


# ─────────────────────────────────────────────────
# GOOGLE TOKEN MANAGER
# ─────────────────────────────────────────────────

class GoogleTokenManager:
    """
    Manages Google OAuth access + refresh tokens.
    Tokens persisted to data/google_tokens.json.
    Auto-refreshes when expired.
    """

    def __init__(self):
        self._tokens: dict = {}
        self._load()

    def _load(self):
        if _TOKEN_FILE.exists():
            try:
                with open(_TOKEN_FILE, "r", encoding="utf-8") as f:
                    self._tokens = json.load(f)
            except Exception:
                self._tokens = {}

    def _save(self):
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(self._tokens, f, indent=2)

    def is_authorized(self) -> bool:
        return bool(self._tokens.get("refresh_token"))

    def _is_expired(self) -> bool:
        expires_at = self._tokens.get("expires_at", 0)
        return time.time() >= (expires_at - 60)

    def get_access_token(self) -> str | None:
        with _TOKEN_LOCK:
            if not self.is_authorized():
                return None
            if self._is_expired():
                self._refresh()
            return self._tokens.get("access_token")

    def _refresh(self):
        client_id     = os.getenv("GOOGLE_CLIENT_ID", "")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
        refresh_token = self._tokens.get("refresh_token", "")

        if not all([client_id, client_secret, refresh_token]):
            print("[MCPBridge] Missing Google credentials — run setup_mcp.py")
            return

        try:
            resp = requests.post(_GOOGLE_TOKEN_URL, data={
                "client_id":     client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type":    "refresh_token",
            }, timeout=10)
            data = resp.json()
            if "access_token" in data:
                self._tokens["access_token"] = data["access_token"]
                self._tokens["expires_at"]   = time.time() + data.get("expires_in", 3600)
                self._save()
                print("[MCPBridge] Google token refreshed.")
            else:
                print(f"[MCPBridge] Token refresh failed: {data.get('error')}")
        except Exception as e:
            print(f"[MCPBridge] Token refresh error: {e}")

    def store_from_code(self, code: str, redirect_uri: str):
        """Exchange auth code for tokens. Called by setup_mcp.py."""
        client_id     = os.getenv("GOOGLE_CLIENT_ID", "")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")

        resp = requests.post(_GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     client_id,
            "client_secret": client_secret,
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
        }, timeout=10)
        data = resp.json()

        if "access_token" not in data:
            raise RuntimeError(f"Auth failed: {data.get('error_description', data)}")

        self._tokens = {
            "access_token":  data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "expires_at":    time.time() + data.get("expires_in", 3600),
            "token_type":    data.get("token_type", "Bearer"),
        }
        self._save()
        print("[MCPBridge] Google tokens saved.")

    def get_auth_url(self, redirect_uri: str) -> str:
        client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        scope     = " ".join(GOOGLE_SCOPES)
        return (
            f"{_GOOGLE_AUTH_URL}"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope={requests.utils.quote(scope)}"
            f"&access_type=offline"
            f"&prompt=consent"
        )


# ── Singleton token manager ───────────────────────
_google_tokens = GoogleTokenManager()


# ─────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────

def google_headers() -> dict | None:
    """Returns Authorization headers for Google API calls, or None if not authorized."""
    token = _google_tokens.get_access_token()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def github_headers() -> dict | None:
    """Returns Authorization headers for GitHub API calls."""
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        return None
    return {
        "Authorization": f"token {token}",
        "Accept":        "application/vnd.github.v3+json",
    }


def is_google_authorized() -> bool:
    return _google_tokens.is_authorized()


def is_github_authorized() -> bool:
    return bool(os.getenv("GITHUB_TOKEN", "").strip())


def google_get(url: str, params: dict = None) -> dict:
    """Authenticated GET to a Google API endpoint."""
    headers = google_headers()
    if not headers:
        raise PermissionError("Google not authorized — run setup_mcp.py first.")
    resp = requests.get(url, headers=headers, params=params or {}, timeout=12)
    resp.raise_for_status()
    return resp.json()


def google_post(url: str, body: dict) -> dict:
    """Authenticated POST to a Google API endpoint."""
    headers = google_headers()
    if not headers:
        raise PermissionError("Google not authorized — run setup_mcp.py first.")
    resp = requests.post(url, headers=headers, json=body, timeout=12)
    resp.raise_for_status()
    return resp.json()


def github_get(url: str, params: dict = None) -> dict | list:
    """Authenticated GET to a GitHub API endpoint."""
    headers = github_headers()
    if not headers:
        raise PermissionError("GITHUB_TOKEN not set in .env")
    resp = requests.get(url, headers=headers, params=params or {}, timeout=12)
    resp.raise_for_status()
    return resp.json()


def github_post(url: str, body: dict) -> dict:
    """Authenticated POST to a GitHub API endpoint."""
    headers = github_headers()
    if not headers:
        raise PermissionError("GITHUB_TOKEN not set in .env")
    resp = requests.post(url, headers=headers, json=body, timeout=12)
    resp.raise_for_status()
    return resp.json()