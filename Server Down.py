#!/usr/bin/env python3
import requests
import os

# ----------------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------------

# Your Discord webhook URL
WEBHOOK_URL = "https://discord.com/api/webhooks/"
# This script does NOT use a status URL since we are manually marking the server offline.
# Set the message ID file path as before (to edit the same message).
MESSAGE_ID_FILE = "/mnt/user/appdata/discord_status_message_id.txt"

# ----------------------------------------------------------------------------
def read_message_id():
    """Read a previously stored Discord message ID from file (if available)."""
    if MESSAGE_ID_FILE and os.path.exists(MESSAGE_ID_FILE):
        try:
            with open(MESSAGE_ID_FILE, "r") as f:
                return f.read().strip()
        except Exception as ex:
            print(f"[DEBUG] Error reading MESSAGE_ID_FILE: {ex}")
    return None

def write_message_id(msg_id):
    """Save the message ID to file so we can re-use it on restarts."""
    if MESSAGE_ID_FILE:
        try:
            with open(MESSAGE_ID_FILE, "w") as f:
                f.write(msg_id)
        except Exception as ex:
            print(f"[DEBUG] Error writing MESSAGE_ID_FILE: {ex}")

def main():
    # This script runs once to signal that the server is going offline.
    message_id = read_message_id()

    # Define the final embed data.
    # Here, we use a dark red color to indicate shutdown.
    final_payload = {
        "content": "",  # Ensure we only show the embed
        "embeds": [
            {
                "title": "Server Shutting Down",
                "description": "The array is going offline. The system is shutting down for maintenance. We'll be back soon.",
                "color": 0xE74C3C,  # Red color
                "footer": {"text": "This is the final update before shutdown."}
            }
        ]
    }

    # If we have a stored message, update that message.
    if message_id:
        edit_url = f"{WEBHOOK_URL}/messages/{message_id}"
        resp = requests.patch(edit_url, json=final_payload)
        if resp.status_code in (200, 204):
            print(f"[INFO] Successfully updated the existing message (ID={message_id}).")
        else:
            print(f"[ERROR] Failed to update message (ID={message_id}): HTTP {resp.status_code} - {resp.text}")
    else:
        # Otherwise, create a new message (using ?wait=true to get the message object)
        create_url = WEBHOOK_URL + "?wait=true"
        resp = requests.post(create_url, json=final_payload)
        if resp.status_code == 200:
            data = resp.json()
            message_id = data.get("id")
            write_message_id(message_id)
            print(f"[INFO] Created a new message for shutdown notification (ID={message_id}).")
        else:
            print(f"[ERROR] Failed to create shutdown message: HTTP {resp.status_code} - {resp.text}")

    # Exit immediately after updating the message.
    print("[INFO] Script completed; server is now marked as going offline.")

if __name__ == "__main__":
    main()
