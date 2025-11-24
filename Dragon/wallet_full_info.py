import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .wallet import BulkWalletChecker, globalRatelimitEvent


API_URL_TEMPLATE = (
    "http://172.86.110.62:1337/defi/quotation/v1/smartmoney/sol/walletNew/{wallet}?period=7d"
)


def read_wallets_from_source(source: str) -> List[str]:
    if os.path.exists(source):
        with open(source, "r", encoding="utf-8") as infile:
            return [line.strip() for line in infile if line.strip()]

    if "," in source:
        return [w.strip() for w in source.split(",") if w.strip()]

    return [source.strip()]


def flatten(nested: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    items: List[Tuple[str, Any]] = []
    for key, value in nested.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            items.extend(flatten(value, new_key, sep=sep).items())
        else:
            items.append((new_key, value))
    return dict(items)


class WalletFullFetcher:
    def __init__(self, use_proxies: bool = False):
        self.base = BulkWalletChecker()
        self.use_proxies = use_proxies

    def _prepare(self):
        self.base.randomise()
        proxy = self.base.getNextProxy() if self.use_proxies else None
        self.base.configureProxy(proxy)

    def fetch_one(self, wallet: str) -> Optional[Dict[str, Any]]:
        url = API_URL_TEMPLATE.format(wallet=wallet)
        while True:
            try:
                if globalRatelimitEvent.is_set():
                    globalRatelimitEvent.wait()

                self._prepare()
                response = self.base.sendRequest.get(url, headers=self.base.headers)

                if response.status_code == 429:
                    globalRatelimitEvent.set()
                    time.sleep(7.5)
                    globalRatelimitEvent.clear()
                    continue

                if response.status_code == 200:
                    payload = response.json()
                    if payload.get("msg") == "success":
                        data = payload.get("data", {})
                        # Return raw data with the wallet id included for reference
                        return {"wallet": wallet, **data}
                    return None
            except Exception:
                # Reuse the same backoff as wallet.py
                time.sleep(7.5)

    def fetch_many(self, wallets: Iterable[str], threads: int = 8) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=threads) as executor:
            future_map = {executor.submit(self.fetch_one, w): w for w in wallets}
            for future in as_completed(future_map):
                data = future.result()
                if data is not None:
                    results.append(data)
        return results


def write_jsonl(path: str, records: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as outfile:
        for rec in records:
            outfile.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_csv(path: str, records: List[Dict[str, Any]]) -> None:
    if not records:
        return
    try:
        import csv
    except ImportError:
        raise RuntimeError("csv module missing in stdlib environment")

    # Flatten records to build a stable header (union of keys)
    flattened: List[Dict[str, Any]] = [flatten(r) for r in records]
    header_keys: List[str] = sorted({k for r in flattened for k in r.keys()})

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(header_keys)
        for rec in flattened:
            writer.writerow([rec.get(k, "") for k in header_keys])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch full wallet analytics data (raw) for one or more wallets. "
            "Input can be a single wallet, a comma-separated list, or a file path."
        )
    )
    parser.add_argument(
        "source",
        help=(
            "Wallet source: a wallet address, comma-separated list, or a file path "
            "containing one wallet per line."
        ),
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=8,
        help="Number of concurrent threads for fetching",
    )
    parser.add_argument(
        "--use-proxies",
        action="store_true",
        help="Enable rotating proxies as configured under Dragon/data/Proxies/proxies.txt",
    )
    parser.add_argument(
        "--out-jsonl",
        default=(
            "Dragon/data/Solana/BulkWallet/wallets_full_raw.jsonl"
        ),
        help="Path to write JSONL output (one JSON per line)",
    )
    parser.add_argument(
        "--out-csv",
        default="",
        help="Optional path to also write a flattened CSV (dot-notated keys)",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print fetched records to stdout (JSON lines)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON when using --print",
    )
    parser.add_argument(
        "--no-file",
        action="store_true",
        help="Do not write any files; only print to stdout if --print is set",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    wallets = read_wallets_from_source(args.source)
    fetcher = WalletFullFetcher(use_proxies=args.use_proxies)
    results = fetcher.fetch_many(wallets, threads=args.threads)

    # Optional print to console
    if args.print:
        if args.pretty:
            for rec in results:
                print(json.dumps(rec, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            for rec in results:
                print(json.dumps(rec, ensure_ascii=False))

    # File outputs unless suppressed
    if not args.no_file:
        write_jsonl(args.out_jsonl, results)
        if args.out_csv:
            write_csv(args.out_csv, results)
        print(
            f"[🐲] Saved {len(results)} records to {args.out_jsonl}"
            + (f" and CSV to {args.out_csv}" if args.out_csv else "")
        )


if __name__ == "__main__":
    main()


