#!/usr/bin/env python3
"""
setup_mcp.py — One-time MCP authorization for Vivie

Run this ONCE before using Gmail or Calendar:
    python setup_mcp.py

What it does:
    1. Opens your browser to Google's consent screen
    2. You click Allow
    3. Paste the code back here
    4. Tokens saved to data/google_tokens.json
    5. Vivie can now access Gmail + Calendar forever
       (tokens auto-refresh — never need to run this again
        unless you revoke access in Google account settings)

Requirements:
    .env must have GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET

How to get those:
    1. Go to console.cloud.google.com
    2. Create a project (or use existing)
    3. APIs & Services → Enable: Gmail API, Google Calendar API
    4. APIs & Services → Credentials → Create OAuth 2.0 Client ID
    5. Application type: Desktop App
    6. Download the JSON — copy client_id and client_secret to .env
"""

import os
import sys
import webbrowser

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"   # "copy-paste" flow — no local server needed


def check_env():
    missing = []
    if not os.getenv("GOOGLE_CLIENT_ID", "").strip():
        missing.append("GOOGLE_CLIENT_ID")
    if not os.getenv("GOOGLE_CLIENT_SECRET", "").strip():
        missing.append("GOOGLE_CLIENT_SECRET")

    if missing:
        print("\n❌ Missing from .env:")
        for k in missing:
            print(f"   {k}=...")
        print("\nFollow the instructions at the top of this file.")
        sys.exit(1)


def setup_google():
    from mcp_bridge import GoogleTokenManager, is_google_authorized

    tm = GoogleTokenManager()

    if is_google_authorized():
        print("✅ Google already authorized. Vivie can access Gmail + Calendar.")
        refresh = input("Re-authorize anyway? (y/n): ").strip().lower()
        if refresh != "y":
            return

    url = tm.get_auth_url(REDIRECT_URI)

    print("\n" + "="*60)
    print("STEP 1: Opening Google authorization in your browser...")
    print("="*60)
    print(f"\nIf it doesn't open automatically, go to:\n{url}\n")

    webbrowser.open(url)

    print("STEP 2: Click 'Allow' on the Google page.")
    print("STEP 3: Copy the authorization code shown on screen.\n")

    code = input("Paste the code here and press Enter: ").strip()

    if not code:
        print("❌ No code entered. Aborted.")
        sys.exit(1)

    try:
        tm.store_from_code(code, REDIRECT_URI)
        print("\n✅ Google authorization complete!")
        print("   Gmail and Calendar are now available to Vivie.")
        print("   You never need to run this again unless you revoke access.")
    except Exception as e:
        print(f"\n❌ Authorization failed: {e}")
        print("   Make sure you copied the full code and try again.")
        sys.exit(1)


def check_github():
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        print("\n✅ GitHub: GITHUB_TOKEN found — ready to use.")
    else:
        print("\n⚠️  GitHub: GITHUB_TOKEN not set.")
        print("   Get one at: github.com/settings/tokens")
        print("   Scopes needed: repo, issues, read:user")
        print("   Add to .env:  GITHUB_TOKEN=ghp_your_token_here")


def main():
    print("\n🔌 Vivie MCP Setup")
    print("="*60)

    check_env()

    print("\n[1/2] Setting up Google (Gmail + Calendar)...")
    setup_google()

    print("\n[2/2] Checking GitHub...")
    check_github()

    print("\n" + "="*60)
    print("Setup complete. Start Vivie normally: python Vivie.py")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()