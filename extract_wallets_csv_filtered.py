import csv
import os
import sys


def extract_wallet_column_filtered(
	input_csv_path: str,
	output_txt_path: str,
) -> None:
	"""Extract wallet values from CSV to a .txt file if filters match.

	- Column match is case-insensitive; prefers 'Identifier' if present, otherwise 'wallet'.
	- Includes a row only if: Koefficient > 0.5 AND Single buy < 160.
	- Skips rows where required numeric fields are missing or invalid.
	"""

	if not os.path.isfile(input_csv_path):
		raise FileNotFoundError(f"Input CSV not found: {input_csv_path}")

	# Ensure destination directory exists
	os.makedirs(os.path.dirname(output_txt_path), exist_ok=True)

	with open(input_csv_path, mode="r", newline="", encoding="utf-8") as csv_file:
		reader = csv.DictReader(csv_file)
		if reader.fieldnames is None:
			raise ValueError("CSV appears to have no header row (fieldnames are missing).")

		# Build case-insensitive map of headers
		lower_to_actual = {fn.strip().lower(): fn for fn in reader.fieldnames if fn is not None}

		# Resolve wallet column (prefer 'Identifier', else 'wallet')
		target_col = None
		for key in ["identifier", "wallet"]:
			if key in lower_to_actual:
				target_col = lower_to_actual[key]
				break

		if target_col is None:
			raise KeyError(
				"Could not find an 'Identifier' or 'wallet' column in CSV. Columns present: "
				+ ", ".join(reader.fieldnames)
			)

		# Resolve filter columns
		coeff_key = lower_to_actual.get("koefficient")
		single_buy_key = lower_to_actual.get("single buy")
		if coeff_key is None or single_buy_key is None:
			raise KeyError(
				"Required columns missing. Need 'Koefficient' and 'Single buy'. Columns present: "
				+ ", ".join(reader.fieldnames)
			)

		included_count = 0
		row_count = 0
		skipped_invalid_numeric = 0

		with open(output_txt_path, mode="w", encoding="utf-8", newline="") as out_file:
			for row in reader:
				row_count += 1

				# Parse numeric filters
				coeff_raw = row.get(coeff_key, "")
				single_buy_raw = row.get(single_buy_key, "")

				try:
					coeff_val = float(str(coeff_raw).strip())
					single_buy_val = float(str(single_buy_raw).strip())
				except (ValueError, TypeError):
					skipped_invalid_numeric += 1
					continue

				if coeff_val > 0.5 and single_buy_val < 160:
					wallet_value = row.get(target_col, "")
					if wallet_value is None:
						wallet_value = ""
					wallet_value = str(wallet_value).strip()
					if wallet_value:
						out_file.write(wallet_value + "\n")
						included_count += 1

	print(f"Processed {row_count} data rows from CSV (excluding header)")
	print(f"Wrote {included_count} wallet(s) meeting filters to TXT file")
	print(f"Rows skipped due to invalid/missing numeric values: {skipped_invalid_numeric}")


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
	#   python extract_wallets_csv_filtered.py [input_csv] [output_txt]
	# If no arguments are provided, defaults under Dragon/data/Solana/BulkWallet are used.
	if len(sys.argv) >= 2:
		in_path = sys.argv[1]
		out_path = sys.argv[2] if len(sys.argv) >= 3 else os.path.splitext(in_path)[0] + ".txt"
	else:
		in_path, out_path = _default_paths()

	extract_wallet_column_filtered(in_path, out_path)
	print(f"Wrote filtered wallets to: {out_path}")


