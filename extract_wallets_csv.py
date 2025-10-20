import csv
import os
import sys


def extract_wallet_column(
	input_csv_path: str,
	output_txt_path: str,

) -> None:
	"""Extract the 'wallet' column from a CSV and write it line-by-line to a .txt file.

	- Column match is case-insensitive; prefers 'Identifier' if present, otherwise 'wallet'.
	- Writes each wallet value on its own line with no extra whitespace.
	"""

	if not os.path.isfile(input_csv_path):
		raise FileNotFoundError(f"Input CSV not found: {input_csv_path}")

	# Ensure destination directory exists
	os.makedirs(os.path.dirname(output_txt_path), exist_ok=True)

	with open(input_csv_path, mode="r", newline="", encoding="utf-8") as csv_file:
		reader = csv.DictReader(csv_file)
		if reader.fieldnames is None:
			raise ValueError("CSV appears to have no header row (fieldnames are missing).")

		# Find target column (case-insensitive): prefer 'Identifier', else 'wallet'
		target_col = None
		preferred = ["identifier", "wallet"]
		lower_to_actual = {fn.strip().lower(): fn for fn in reader.fieldnames if fn is not None}
		for key in preferred:
			if key in lower_to_actual:
				target_col = lower_to_actual[key]
				break

		if target_col is None:
			raise KeyError(
				"Could not find an 'Identifier' or 'wallet' column in CSV. Columns present: "
				+ ", ".join(reader.fieldnames)
			)

		with open(output_txt_path, mode="w", encoding="utf-8", newline="") as out_file:
			for row in reader:
				value = row.get(target_col, "")
				if value is None:
					value = ""
				value = str(value).strip()
				if value:
					out_file.write(value + "\n")


def _default_paths() -> tuple[str, str]:
	# Defaults relative to repository root
	input_csv = os.path.join(
		"Dragon",
		"data",
		"Solana",
		"BulkWallet",
		"wallets_1.csv",
	)
	output_txt = os.path.join(
		"Dragon",
		"data",
		"Solana",
		"BulkWallet",
		"wallets_1.txt",
	)
	return input_csv, output_txt


if __name__ == "__main__":
	# Usage:
	#   python extract_wallets_csv.py [input_csv] [output_txt]
	# If no arguments are provided, defaults under Dragon/data/Solana/BulkWallet are used.
	if len(sys.argv) >= 2:
		in_path = sys.argv[1]
		out_path = sys.argv[2] if len(sys.argv) >= 3 else os.path.splitext(in_path)[0] + ".txt"
	else:
		in_path, out_path = _default_paths()

	extract_wallet_column(in_path, out_path)
	print(f"Wrote wallet column to: {out_path}")


