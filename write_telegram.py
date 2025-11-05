import asyncio
import os
import re
import glob
import csv
import pandas as pd
import msvcrt
from telethon import TelegramClient, events
from telethon.errors import ApiIdInvalidError
from openpyxl import load_workbook

# ─── CONFIG ────────────────────────────────────────────────────────────────
API_ID = 25588027
API_HASH = '1fad35a5f1147daebece6314b896fe94'
BOT_TOKEN        = ""

# Resolve data directory relative to this script to avoid hardcoded paths
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
DATA_DIR         = os.path.join(BASE_DIR, "Dragon", "data", "Solana", "BulkWallet")
WALLET_FILE_NAME = "wallets_1.txt"
WALLET_CSV_NAME  = "wallets_1.csv"

OUTPUT_FILE      = os.path.join(DATA_DIR, "results.xlsx")
MIN_TRADED       = 100
MIN_WINRATE      = 35
RESPONSE_TIMEOUT = 9
DELAY_BETWEEN    = 5
BATCH_SIZE       = 10
BOT_USERNAME     = "WizVoldemortBot"
# ────────────────────────────────────────────────────────────────────────────

def flush_to_excel(batch):
    """Append a batch of dicts to OUTPUT_FILE (creating it if missing)."""
    if not batch:
        return
    df = pd.DataFrame(batch)
    if os.path.exists(OUTPUT_FILE):
        wb = load_workbook(OUTPUT_FILE)
        ws = wb.active
        for row in df.itertuples(index=False, name=None):
            ws.append(row)
        wb.save(OUTPUT_FILE)
        print(f"  ↳ Flushed {len(df)} rows (append).")
    else:
        df.to_excel(OUTPUT_FILE, index=False)
        print(f"  ↳ Flushed {len(df)} rows (new file).")

async def send_and_collect():
    # 1) login
    if BOT_TOKEN:
        client = TelegramClient("bot_session", API_ID, API_HASH) \
                    .start(bot_token=BOT_TOKEN)
    else:
        client = TelegramClient("user_session", API_ID, API_HASH)
        await client.start()
    await client.connect()

    # 2) global queue + handler for all bot messages
    message_queue: asyncio.Queue = asyncio.Queue()

    @client.on(events.NewMessage(from_users=BOT_USERNAME))
    async def catch_bot(event):
        await message_queue.put(event.message)

    # 3) load all wallets: prefer CSV (Identifier/wallet column), fallback to TXT
    wallets = []
    wallets_csv_path = os.path.join(DATA_DIR, WALLET_CSV_NAME)
    wallets_txt_path = os.path.join(DATA_DIR, WALLET_FILE_NAME)

    if os.path.isfile(wallets_csv_path):
        try:
            with open(wallets_csv_path, mode="r", newline="", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                if reader.fieldnames is None:
                    raise ValueError("CSV has no header row.")
                lower_to_actual = {fn.strip().lower(): fn for fn in reader.fieldnames if fn is not None}
                target_col = None
                for key in ("identifier", "wallet"):
                    if key in lower_to_actual:
                        target_col = lower_to_actual[key]
                        break
                if target_col is None:
                    raise KeyError("CSV missing 'Identifier' or 'wallet' column.")
                for row in reader:
                    value = row.get(target_col, "")
                    if value is None:
                        continue
                    value = str(value).strip()
                    if value:
                        wallets.append(value)
            print(f"Loaded {len(wallets)} wallets from CSV: {wallets_csv_path}")
        except Exception as e:
            print(f"Failed to read CSV, falling back to TXT. Reason: {e}")

    if not wallets and os.path.isfile(wallets_txt_path):
        with open(wallets_txt_path, "r", encoding="utf-8") as f:
            wallets = [l.strip() for l in f if l.strip()]
        print(f"Loaded {len(wallets)} wallets from TXT: {wallets_txt_path}")

    if not wallets:
        print("No wallets loaded. Ensure wallets_1.csv or wallets_1.txt exists and is valid.")
        return

    # 4) regex patterns
    pattern = re.compile(
        r"PNL:\s*\*\*\$?(-?\d+\.?\d*)\*\*\s*"
        r"Winrate:\s*\*\*(\d+\.?\d*)%\*\*\s*"
        r"Traded:\s*\*\*(\d+\.?\d*)\*\*\s*"
        r"Single Buy:\s*\*\*\$?(\d+\.?\d*)\*\*",
        re.S
    )
    first_token_pattern = re.compile(
        r"\[\$.*?\]\(.*?\):\s*\$?(-?\d+\.?\d*)([KM]?)",
        re.IGNORECASE
    )
    wallet_reply_pattern = re.compile(r"`?([A-Za-z0-9]{30,})`?\s*\(Tap to copy\)")

    # 5) pause/resume control
    paused = asyncio.Event()
    paused.set()
    async def control_loop():
        print(">> Press 'P' to pause, 'R' to resume (non-blocking).")
        try:
            while True:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch().upper()
                    if ch == 'P' and paused.is_set():
                        paused.clear()
                        print("** Paused. **")
                    elif ch == 'R' and not paused.is_set():
                        paused.set()
                        print("** Resumed. **")
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            return

    control_task = asyncio.create_task(control_loop())

    batch = []
    studied = 0

    # 6) main loop
    truncate_marker = "(PNL does not include Priority Fee)"
    for idx, orig_wallet in enumerate(wallets):
        await paused.wait()
        studied += 1

        print(f">>> Sending row {idx}: '{orig_wallet}'")
        await client.send_message(BOT_USERNAME, orig_wallet)

        # a) wait for first reply up to RESPONSE_TIMEOUT
        try:
            first_msg = await asyncio.wait_for(message_queue.get(), timeout=RESPONSE_TIMEOUT)
            replies = [first_msg]
            # Start DELAY_BETWEEN window immediately after first response
            end_time = asyncio.get_event_loop().time() + DELAY_BETWEEN
            while True:
                remaining = end_time - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    more_msg = await asyncio.wait_for(message_queue.get(), timeout=remaining)
                    replies.append(more_msg)
                except asyncio.TimeoutError:
                    break
        except asyncio.TimeoutError:
            replies = []

        if not replies:
            print(f"<<< No reply for row {idx} within {RESPONSE_TIMEOUT}s, saving to wallets1.txt and skipping.\n")
            # Save wallets with no reply
            no_reply_path = os.path.join(DATA_DIR, "wallets_1.txt")
            with open(no_reply_path, "a", encoding="utf-8") as f:
                f.write(orig_wallet + "\n")
            continue
        else:
            # b) process each reply collected during the delay window
            for num, resp in enumerate(replies, start=1):
                process_list = [(resp, "")]
                for msg_obj, prefix in process_list:
                    text = msg_obj.text or ""
                    if truncate_marker in text:
                        display_text = text.split(truncate_marker)[0] + truncate_marker
                    else:
                        display_text = text

                    print(f"<<< {prefix}Reply {num}/{len(replies)} for row {idx}: {display_text!r}")

                    m_addr = wallet_reply_pattern.search(text)
                    wallet = m_addr.group(1) if m_addr else orig_wallet
                    if m_addr:
                        print(f"<<< {prefix}Extracted wallet: {wallet}")
                    else:
                        print(f"<<< {prefix}Using original wallet: {wallet}")

                    m = pattern.search(text)
                    if not m:
                        print(f"<<< {prefix}Couldn't parse metrics, skipping.\n")
                        continue

                    pnl_val        = float(m.group(1))
                    winrate_val    = float(m.group(2))
                    traded_val     = float(m.group(3))
                    single_buy_val = float(m.group(4))

                    first_profit_val = None
                    m2 = first_token_pattern.search(text)
                    if m2:
                        num_    = float(m2.group(1))
                        suffix  = m2.group(2).upper()
                        mult    = 1_000 if suffix == 'K' else 1_000_000 if suffix=='M' else 1
                        first_profit_val = num_ * mult

                    # filters
                    if traded_val < MIN_TRADED:
                        print(f"<<< {prefix}Skipping: traded {traded_val} < {MIN_TRADED}.\n")
                    elif winrate_val <= MIN_WINRATE:
                        print(f"<<< {prefix}Skipping: winrate {winrate_val}% ≤ {MIN_WINRATE}%.\n")
                    elif pnl_val * 10 < traded_val * single_buy_val:
                        print(f"<<< {prefix}Skipping: pnl*10 < traded*single_buy.\n")
                    elif pnl_val > traded_val * single_buy_val:
                        print(f"<<< {prefix}Skipping: pnl < traded*single_buy.\n")
                    elif first_profit_val is not None and first_profit_val > 0.5 * pnl_val:
                        print(f"<<< {prefix}Skipping: first-token profit too large.\n")
                    else:
                        batch.append({
                            "wallet":     wallet,
                            "pnl":        pnl_val,
                            "winrate":    winrate_val,
                            "traded":     traded_val,
                            "single_buy": single_buy_val
                        })
                        print(f"<<< {prefix}Accepted.\n")

        # flush batch every BATCH_SIZE
        if studied % BATCH_SIZE == 0:
            flush_to_excel(batch)
            batch.clear()

    # 7) cleanup
    control_task.cancel()
    await client.disconnect()

    # 8) final flush
    if batch:
        flush_to_excel(batch)


def main():
    try:
        asyncio.run(send_and_collect())
    except ApiIdInvalidError:
        print("Error: Invalid API_ID / API_HASH (or BOT_TOKEN). Please check your credentials.")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
