import csv
import os
import sys


def clear_csv_data(input_csv_path: str) -> None:
    """Clear all data rows from a CSV file, keeping only the header row.
    
    - Preserves the original header row
    - Removes all data rows
    """
    
    if not os.path.isfile(input_csv_path):
        raise FileNotFoundError(f"Input CSV not found: {input_csv_path}")
    
    # Read the header to preserve it
    with open(input_csv_path, mode="r", newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        header = next(reader, None)
        if header is None:
            raise ValueError("CSV appears to have no header row.")
    
    # Write back only the header
    with open(input_csv_path, mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(header)
    
    print(f"Cleared all data from: {input_csv_path}")


def _default_path() -> str:
    # Default path relative to repository root
    return os.path.join(
        "Dragon",
        "data",
        "Solana",
        "BulkWallet",
        "wallets_1.csv",
    )


if __name__ == "__main__":
    # Usage:
    #   python clear_csv.py [input_csv]
    # If no argument is provided, defaults to Dragon/data/Solana/BulkWallet/wallets_1.csv
    if len(sys.argv) >= 2:
        in_path = sys.argv[1]
    else:
        in_path = _default_path()
    
    clear_csv_data(in_path)
