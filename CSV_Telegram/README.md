# CSV Middle-Click to Telegram

Automatically copy CSV cell values and send them to Telegram bot by middle-clicking.

## Quick Start

### 1. Install Dependencies
```bash
pip install pyrogram pandas openpyxl fake-useragent tls-client
```

### 2. Configure Telegram
- Get API credentials from https://my.telegram.org/apps
- Add to `telegram_config.txt`:
  ```
  api_id=YOUR_API_ID
  api_hash=YOUR_API_HASH
  ```

### 3. First-Time Setup
Run once to authenticate:
```bash
python send_to_telegram.py "test message"
```
Enter your phone number and verification code when prompted.

### 4. Run the Script
Double-click `copy_csv_middle_click_v2.ahk` to start (requires AutoHotkey v2).

## How to Use

1. Open any CSV file in:
   - Excel
   - Notepad / Notepad++
   - VS Code
   - Any program with ".csv" in the window title

2. **Middle-click** (mouse scroll button) on any cell
   - Cell value is copied
   - Automatically sent to @WizVoldemortBot in Telegram
   - Tooltip shows "Copied: [value]"

3. **Shift + Middle-click** = bypass (normal middle-click behavior)

## Files

- `copy_csv_middle_click_v2.ahk` - Main AutoHotkey script
- `send_to_telegram.py` - Python script that sends to Telegram
- `telegram_config.txt` - Your Telegram API credentials

## Notes

- Works in background - script stays running until you exit it
- Non-blocking - each copy sends immediately without delay
- Only sends text messages (no images)

