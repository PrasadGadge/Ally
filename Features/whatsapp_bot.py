import time
import json
import os
from TextToSpeech.Fast_DF_TTS import speak, speak_blocking
from os import getcwd

try:
    import pywhatkit as kit
    _HAS_PYWHATKIT = True
except Exception:
    kit = None
    _HAS_PYWHATKIT = False

# ==============================
# 📂 File Paths
# ==============================
base_path = getcwd()
input_file = os.path.join(base_path, "input.txt")
contact_file = os.path.join(base_path, "contacts.json")

# ==============================
# 📥 Load Contacts
# ==============================
def load_contacts():
    try:
        with open(contact_file, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as e:
        print("Contact loading error:", e)
        speak("Unable to load contact dataset.")
        return {}

# ==============================
# 🧹 Clear Input File
# ==============================
def clear_file():
    with open(input_file, "w", encoding="utf-8") as file:
        file.truncate(0)

# ==============================
# 🔍 Find Contact
# ==============================
def find_contact(name, contacts):
    name = name.lower().strip()
    for contact_name in contacts:
        if contact_name.lower() in name:
            return contacts[contact_name]
    return None

# ==============================
# 💬 Send WhatsApp Message
# ==============================
def send_whatsapp(contact_number, message):
    try:
        if not _HAS_PYWHATKIT:
            speak("WhatsApp integration is unavailable right now.")
            print("pywhatkit not available; skipping WhatsApp send.")
            return
        speak("Sending message now.")

        # Small delay for system stability
        time.sleep(2)

        kit.sendwhatmsg_instantly(
            contact_number,
            message,
            wait_time=25,      # Give WhatsApp enough time to load
            tab_close=True,
            close_time=5
        )

        speak("Message sent successfully.")
        print("Message sent to:", contact_number)

    except Exception as e:
        print("Sending failed:", e)
        speak("Failed to send message.")

# ==============================
# 🚀 Main Function
# FIX 1: now accepts optional `details` arg so tool_router.execute("send_whatsapp", details)
#         doesn't raise TypeError (was: 0 positional args, got 1).
# ==============================
# 🚀 Main Function
# FIX: completely replaced input.txt polling with voice_dialog queue.
# input.txt never existed at runtime → infinite FileNotFoundError loop.
# Now uses the same voice pipeline as the rest of Vivie.
# ==============================
def send_msg(details=None):
    import queue as _queue
    import voice_dialog

    contacts = load_contacts()
    if not contacts:
        speak_blocking("Boss, no contacts loaded. Please check the contacts file.")
        return

    # Activate dialog mode — listen_loop will now route voice to dialog queue
    voice_dialog.activate()

    speak_blocking("Who do you want to send the message to? Say the name.")

    contact_number = None

    try:
        # ── Step 1: get contact name ──────────────────────────────
        while True:
            try:
                raw = voice_dialog.get(timeout=20)
            except _queue.Empty:
                speak_blocking("No response received. Cancelling WhatsApp.")
                return

            text = raw.lower().strip()
            print(f"[WhatsApp] Heard: {text}")

            if any(w in text for w in ["cancel", "stop", "exit", "never mind"]):
                speak_blocking("Cancelled. Returning to normal.")
                return

            # Strip filler phrases user might say
            name = (text
                    .replace("send to", "")
                    .replace("send message to", "")
                    .replace("contact", "")
                    .strip())

            if not name:
                speak_blocking("I didn't catch the name. Please say the contact name.")
                continue

            contact_number = find_contact(name, contacts)

            if not contact_number:
                speak_blocking(f"Contact {name} not found. Please try again or say cancel.")
                continue

            speak_blocking(f"Got it. What is the message for {name}?")
            break

        # ── Step 2: get message text ──────────────────────────────
        while True:
            try:
                raw = voice_dialog.get(timeout=20)
            except _queue.Empty:
                speak_blocking("No message received. Cancelling.")
                return

            text = raw.lower().strip()
            print(f"[WhatsApp] Message heard: {text}")

            if any(w in text for w in ["cancel", "stop", "exit", "never mind"]):
                speak_blocking("Cancelled. Returning to normal.")
                return

            # Strip "message is" prefix if user says it
            message = text.replace("message is", "").strip()

            if not message:
                speak_blocking("Message was empty. Please say the message again.")
                continue

            send_whatsapp(contact_number, message)
            speak_blocking("Message sent successfully, Boss.")
            break

    finally:
        # Always deactivate — even if exception raised
        voice_dialog.deactivate()
