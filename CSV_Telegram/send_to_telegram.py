#!/usr/bin/env python3
"""
Sends text message to Telegram bot chat using Pyrogram.
Usage: python send_to_telegram.py <text_to_send>
Or reads from stdin if no args provided.
"""

import sys
import os
from pathlib import Path

try:
    from pyrogram import Client
except ImportError:
    print("ERROR: pyrogram not installed. Run: pip install pyrogram", file=sys.stderr)
    sys.exit(1)

# Configuration file path
SESSION_DIR = Path(__file__).parent / ".telegram_session"
SESSION_DIR.mkdir(exist_ok=True)
SESSION_FILE = SESSION_DIR / "telegram_session"

BOT_USERNAME = "WizVoldemortBot"


def get_text_to_send():
    """Get text from command line args or stdin."""
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:])
    
    # Try reading from stdin (non-blocking)
    import select
    if sys.stdin.isatty():
        return None
    return sys.stdin.read().strip()


def send_to_telegram(text: str):
    """
    Send text message to Telegram bot chat using Pyrogram.
    
    First run will prompt for API credentials:
    - api_id: Get from https://my.telegram.org/apps
    - api_hash: Get from https://my.telegram.org/apps
    - phone_number: Your Telegram phone number
    """
    if not text or not text.strip():
        print("ERROR: No text to send", file=sys.stderr)
        return False
    
    # Check for credentials
    config_file = Path(__file__).parent / "telegram_config.txt"
    
    api_id = None
    api_hash = None
    
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                for line in f:
                    if line.startswith("api_id="):
                        api_id = int(line.split("=", 1)[1].strip())
                    elif line.startswith("api_hash="):
                        api_hash = line.split("=", 1)[1].strip()
        except Exception as e:
            print(f"WARNING: Could not read config: {e}", file=sys.stderr)
    
    if not api_id or not api_hash:
        print("ERROR: Telegram API credentials not found.", file=sys.stderr)
        print("", file=sys.stderr)
        print("Please create telegram_config.txt with:", file=sys.stderr)
        print("  api_id=YOUR_API_ID", file=sys.stderr)
        print("  api_hash=YOUR_API_HASH", file=sys.stderr)
        print("", file=sys.stderr)
        print("Get these from: https://my.telegram.org/apps", file=sys.stderr)
        return False
    
    try:
        # Initialize client
        app = Client(
            "telegram_sender",
            api_id=api_id,
            api_hash=api_hash,
            workdir=str(SESSION_DIR)
        )
        
        with app:
            # Get bot entity
            try:
                bot = app.get_users(BOT_USERNAME)
            except Exception as e:
                print(f"ERROR: Could not find bot {BOT_USERNAME}: {e}", file=sys.stderr)
                return False
            
            # Send message as text
            try:
                sent = app.send_message(bot.id, text)
                print(f"SUCCESS: Message sent to {BOT_USERNAME} (message_id: {sent.id})")
                return True
            except Exception as e:
                print(f"ERROR: Failed to send message: {e}", file=sys.stderr)
                return False
                
    except Exception as e:
        print(f"ERROR: Telegram client error: {e}", file=sys.stderr)
        if "AUTH_KEY_UNREGISTERED" in str(e):
            print("", file=sys.stderr)
            print("Your session expired. Delete .telegram_session/ and run again to re-authenticate.", file=sys.stderr)
        return False


def main():
    """Main entry point."""
    text = get_text_to_send()
    
    if not text:
        print("ERROR: No text provided. Usage: python send_to_telegram.py <text>", file=sys.stderr)
        print("   Or pipe text: echo 'message' | python send_to_telegram.py", file=sys.stderr)
        sys.exit(1)
    
    # Filter out common error messages and commands that shouldn't be sent
    text_lower = text.lower().strip()
    skip_patterns = [
        "pip install",
        "error:",
        "success:",
        "warning:",
        "please create",
        "get these from:",
        "usage: python"
    ]
    
    for pattern in skip_patterns:
        if pattern in text_lower:
            print(f"INFO: Skipping message (contains '{pattern}')", file=sys.stderr)
            sys.exit(0)  # Exit silently, don't send
    
    success = send_to_telegram(text)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()


