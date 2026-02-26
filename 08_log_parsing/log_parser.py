"""
Log file parser — reads structured log lines into a filterable DataFrame and CSV.

Log line format:
    <TERM1><SSSSS.XXX><TYPE>S:HHHH:SYSTEM: message text

Fields:
    term1   — variable-length identifier
    time    — seconds (float), space-padded to fixed width
    logtype — message type tag
    source  — single letter (A or B)
    hex     — 4-digit hex code
    system  — up to 6 chars, space-padded
    message — free-text (some lines indented 7 extra spaces)
"""

import re
import sys
import argparse
import tkinter as tk
from tkinter import filedialog
import pandas as pd
from pathlib import Path

# Regex to match one log line
LINE_PATTERN = re.compile(
    r"<([^>]+)>"        # term1
    r"<([^>]+)>"        # time (raw, may have leading spaces)
    r"<([^>]+)>"        # log type
    r"([AB])"           # source
    r":"
    r"([0-9A-Fa-f]{4})" # hex code (4 hex digits)
    r":"
    r"(.{1,6}?)"        # system (up to 6 chars)
    r"\s*:\s"           # colon-space separator (absorb padding)
    r"(.*)"             # message (rest of line)
)


def parse_line(line: str) -> dict | None:
    """Parse a single log line. Returns a dict of fields or None if no match."""
    m = LINE_PATTERN.match(line)
    if not m:
        return None

    term1, raw_time, logtype, source, hexcode, system, message = m.groups()
    return {
        "term1":   term1.strip(),
        "time_s":  float(raw_time.strip()),
        "logtype": logtype.strip(),
        "source":  source,
        "hex":     hexcode.upper(),
        "system":  system.strip(),
        "message": message.strip(),
    }


def parse_log(filepath: str | Path) -> pd.DataFrame:
    """Parse an entire log file into a DataFrame."""
    filepath = Path(filepath)
    records = []
    skipped = 0

    with filepath.open("r", errors="replace") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.rstrip("\n\r")
            if not line:
                continue
            rec = parse_line(line)
            if rec:
                rec["line_num"] = lineno
                records.append(rec)
            else:
                skipped += 1

    if skipped:
        print(f"Note: {skipped} line(s) did not match the expected format and were skipped.")

    df = pd.DataFrame(records)
    if not df.empty:
        # Reorder columns
        df = df[["line_num", "time_s", "term1", "logtype", "source", "hex", "system", "message"]]
        df.sort_values("time_s", inplace=True, ignore_index=True)
    return df


def filter_df(df: pd.DataFrame,
              system: str | None = None,
              source: str | None = None,
              logtype: str | None = None,
              keyword: str | None = None) -> pd.DataFrame:
    """Return a filtered copy of the DataFrame."""
    out = df.copy()
    if system:
        out = out[out["system"].str.contains(system, case=False, na=False)]
    if source:
        out = out[out["source"] == source.upper()]
    if logtype:
        out = out[out["logtype"].str.contains(logtype, case=False, na=False)]
    if keyword:
        out = out[out["message"].str.contains(keyword, case=False, na=False)]
    return out


def select_file() -> Path | None:
    """Open a file dialog and return the selected path, or None if cancelled."""
    root = tk.Tk()
    root.withdraw()
    filepath = filedialog.askopenfilename(
        title="Select a log file",
        filetypes=[("Text/Log files", "*.txt *.log"), ("All files", "*.*")],
    )
    root.destroy()
    return Path(filepath) if filepath else None


def main():
    parser = argparse.ArgumentParser(description="Parse structured log files into CSV / DataFrame.")
    parser.add_argument("logfile", nargs="?", default=None, help="Path to the log file (opens file picker if omitted)")
    parser.add_argument("-o", "--output", help="Output CSV path (default: <logfile>_parsed.csv)")
    parser.add_argument("--system", help="Filter to a specific system name")
    parser.add_argument("--source", choices=["A", "B"], help="Filter by source (A or B)")
    parser.add_argument("--logtype", help="Filter by log type")
    parser.add_argument("--keyword", help="Filter messages containing this keyword")
    args = parser.parse_args()

    if args.logfile:
        logpath = Path(args.logfile)
    else:
        logpath = select_file()
        if not logpath:
            print("No file selected.")
            sys.exit(0)

    if not logpath.is_file():
        print(f"Error: file not found — {logpath}")
        sys.exit(1)

    # Parse
    df = parse_log(logpath)
    if df.empty:
        print("No matching log lines found.")
        sys.exit(0)
    print(f"Parsed {len(df)} log lines.")

    # Filter
    df_out = filter_df(df, system=args.system, source=args.source,
                       logtype=args.logtype, keyword=args.keyword)
    if len(df_out) < len(df):
        print(f"After filtering: {len(df_out)} lines.")

    # Export CSV
    outpath = Path(args.output) if args.output else logpath.with_name(logpath.stem + "_parsed.csv")
    df_out.to_csv(outpath, index=False)
    print(f"Saved to {outpath}")


if __name__ == "__main__":
    main()
