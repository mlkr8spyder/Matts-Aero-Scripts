"""
Round-trip verification for log_parser.

Reads a parsed CSV, reconstructs log lines from the fields,
and compares them against the original text file line-by-line.
"""

from __future__ import annotations

import sys
import argparse
import pandas as pd
from pathlib import Path


def reconstruct_line(row) -> str:
    """Rebuild an original log line from parsed CSV fields."""
    # Time: integer part right-justified in 5 chars, dot, 3 decimal digits
    time_str = f"{row['time_s']:9.3f}"

    # System: padded to 6 chars with trailing spaces
    system_str = f"{row['system']:<6s}"

    return (
        f"<{row['term1']}>"
        f"<{time_str}>"
        f"<{row['logtype']}>"
        f"{row['source']}"
        f":{row['hex']}"
        f":{system_str}"
        f": {row['message']}"
    )


def main():
    parser = argparse.ArgumentParser(description="Verify log parser round-trip accuracy.")
    parser.add_argument("csv_file", help="Path to the parsed CSV")
    parser.add_argument("original_file", help="Path to the original log file")
    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    orig_path = Path(args.original_file)

    if not csv_path.is_file():
        print(f"Error: CSV not found — {csv_path}")
        sys.exit(1)
    if not orig_path.is_file():
        print(f"Error: original file not found — {orig_path}")
        sys.exit(1)

    # Load CSV and original file
    df = pd.read_csv(csv_path)
    with orig_path.open("r", errors="replace") as f:
        orig_lines = f.readlines()

    mismatches = 0
    total = len(df)

    for _, row in df.iterrows():
        line_num = int(row["line_num"])
        original = orig_lines[line_num - 1].rstrip("\n\r")
        reconstructed = reconstruct_line(row)

        if reconstructed != original:
            mismatches += 1
            print(f"--- Line {line_num} ---")
            print(f"  ORIG:  {repr(original)}")
            print(f"  BUILT: {repr(reconstructed)}")

    if mismatches == 0:
        print(f"All {total} lines match perfectly.")
    else:
        print(f"\n{mismatches} / {total} lines differ.")


if __name__ == "__main__":
    main()
