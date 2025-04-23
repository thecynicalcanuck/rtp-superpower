#!/usr/bin/env python3
import requests
import time
import os

# ----------------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------------

WEBHOOK_URL = "https://discord.com/api/webhooks/"
STATUS_URL = ""

UPDATE_INTERVAL = 60  # seconds between checks

# If set, the script will store the message ID here so it reuses the same Discord message.
MESSAGE_ID_FILE = "/mnt/user/appdata/discord_status_message_id.txt"

# ----------------------------------------------------------------------------

def fetch_status():
    """
    Fetch the status page and determine the current state:
      - "online"      (green) for "All services are online"
      - "maintenance" (blue) for "Ongoing maintenance"
      - "down"        (red) for all other cases (or error)
      
    Returns a tuple: (status_text, status_state)
    """
    try:
        resp = requests.get(STATUS_URL, timeout=10)
        resp.raise_for_status()
        html = resp.text

        if "Ongoing maintenance" in html:
            return ("We are currently undergoing maintenance.", "maintenance")
        elif "All services are online" in html:
            return ("All services are online.", "online")
        else:
            return ("Some services may be down or the status page changed.", "down")
    except Exception as e:
        return (f"Error fetching status page: {e}", "down")

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
    """Save the Discord message ID to a file so we can re-use it on restarts."""
    if MESSAGE_ID_FILE:
        try:
            with open(MESSAGE_ID_FILE, "w") as f:
                f.write(msg_id)
        except Exception as ex:
            print(f"[DEBUG] Error writing MESSAGE_ID_FILE: {ex}")

def main():
    message_id = read_message_id()

    # Map each status state to an embed color (decimal).
    color_map = {
        "online":      0x2ECC71,  # Green
        "maintenance": 0x3498DB,  # Blue
        "down":        0xE74C3C,  # Red
    }

    while True:
        status_text, status_state = fetch_status()
        embed_color = color_map.get(status_state, 0xE74C3C)  # Default to red

        # Append a clickable link to the status page in the description.
        # Markdown link format: [link text](URL)
        full_description = f"{status_text}\n\n[Click here for full status details]({STATUS_URL})"

        # Build the payload with an explicit empty "content" field to show only the embed.
        payload = {
            "content": "",
            "embeds": [
                {
                    "title": "Hoist & Torque Status",
                    "description": full_description,
                    "url": STATUS_URL,  # Title is clickable as well.
                    "color": embed_color,
                    "footer": {
                        "text": "Updated every 60s"
                    }
                }
            ]
        }

        # Create or edit the Discord message.
        if message_id is None:
            create_url = WEBHOOK_URL + "?wait=true"
            resp = requests.post(create_url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                message_id = data.get("id")
                write_message_id(message_id)
                print(f"[INFO] Created new Discord message (ID={message_id}).")
            else:
                print(f"[ERROR] Failed to create message: HTTP {resp.status_code} - {resp.text}")
        else:
            edit_url = f"{WEBHOOK_URL}/messages/{message_id}"
            resp = requests.patch(edit_url, json=payload)
            if resp.status_code in (200, 204):
                print(f"[INFO] Updated existing message (ID={message_id}).")
            else:
                print(f"[ERROR] Failed to edit message (ID={message_id}): HTTP {resp.status_code} - {resp.text}")

        # Wait for the next update
        time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    main()
