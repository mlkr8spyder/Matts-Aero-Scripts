"""
CSV importers for H-V slice data and calibration test data.

Two main entry points:
  - load_slice_csv / load_slice_directory: import H-V tables from CSV files
    where each file represents one table at one attitude condition.
  - load_test_csv: import calibration test data (defuel/refuel sequences)
    with flexible column name mapping.

CSV formats are intentionally flexible — column names are configurable so
a GPT-4.1 adapter can handle any program's export format.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional
import re

from .base import HVTable, TankData, TestRecord, TestDataset, FuelSystemData


# -------------------------------------------------------------------------
# Slice CSV loading (H-V tables)
# -------------------------------------------------------------------------

def load_slice_csv(filepath: str,
                   height_col: str = "height",
                   volume_col: str = "volume",
                   pitch_deg: float = 0.0,
                   roll_deg: float = 0.0,
                   cg_fs_col: Optional[str] = None,
                   cg_bl_col: Optional[str] = None,
                   cg_wl_col: Optional[str] = None,
                   **read_kwargs) -> HVTable:
    """
    Load a single H-V table from a CSV file.

    Each CSV represents one tank at one attitude condition. The file must
    have at least a height column and a volume column.

    Parameters
    ----------
    filepath : str or Path
        Path to the CSV file.
    height_col, volume_col : str
        Column names for height (inches) and volume (in^3).
    pitch_deg, roll_deg : float
        Attitude for this table (from filename or metadata).
    cg_fs_col, cg_bl_col, cg_wl_col : str, optional
        Column names for CG coordinates, if present.
    **read_kwargs
        Passed to pd.read_csv (e.g., skiprows, delimiter).

    Returns
    -------
    HVTable
    """
    df = pd.read_csv(filepath, **read_kwargs)

    kwargs = {}
    if cg_fs_col and cg_fs_col in df.columns:
        kwargs['cg_fs'] = df[cg_fs_col].values
    if cg_bl_col and cg_bl_col in df.columns:
        kwargs['cg_bl'] = df[cg_bl_col].values
    if cg_wl_col and cg_wl_col in df.columns:
        kwargs['cg_wl'] = df[cg_wl_col].values

    return HVTable(
        heights=df[height_col].values,
        volumes=df[volume_col].values,
        pitch_deg=pitch_deg,
        roll_deg=roll_deg,
        **kwargs,
    )


def load_slice_directory(directory: str,
                         tank_id: str,
                         pattern: str = r".*_p(?P<pitch>[-\d.]+)_r(?P<roll>[-\d.]+)\.csv",
                         height_col: str = "height",
                         volume_col: str = "volume",
                         **read_kwargs) -> TankData:
    """
    Bulk-load H-V tables from a directory of CSV files for one tank.

    Expects filenames that encode the attitude, e.g.:
        T3_p0.0_r0.0.csv, T3_p2.0_r-4.0.csv

    The default pattern extracts pitch and roll from the filename using
    named groups (?P<pitch>...) and (?P<roll>...).

    Parameters
    ----------
    directory : str or Path
        Directory containing the CSV slice files.
    tank_id : str
        Tank identifier for the resulting TankData.
    pattern : str
        Regex pattern with named groups 'pitch' and 'roll'.
    height_col, volume_col : str
        Column names in each CSV.
    **read_kwargs
        Passed to pd.read_csv.

    Returns
    -------
    TankData
    """
    directory = Path(directory)
    regex = re.compile(pattern)
    tables = {}

    for csv_path in sorted(directory.glob("*.csv")):
        match = regex.match(csv_path.name)
        if not match:
            continue

        pitch = float(match.group('pitch'))
        roll = float(match.group('roll'))

        hv = load_slice_csv(
            str(csv_path),
            height_col=height_col,
            volume_col=volume_col,
            pitch_deg=pitch,
            roll_deg=roll,
            **read_kwargs,
        )
        tables[(pitch, roll)] = hv

    return TankData(tank_id=tank_id, tables=tables)


# -------------------------------------------------------------------------
# Test data CSV loading
# -------------------------------------------------------------------------

def load_test_csv(filepath: str,
                  sequence_type: str = "unknown",
                  time_col: str = "time_s",
                  pitch_col: str = "pitch_deg",
                  roll_col: str = "roll_deg",
                  density_col: Optional[str] = "density_system",
                  scale_col: Optional[str] = "scale_gross_weight_lb",
                  dry_weight_col: Optional[str] = "dry_weight_lb",
                  indicated_weight_prefix: str = "indicated_weight_lb_",
                  indicated_volume_prefix: str = "indicated_volume_gal_",
                  tank_ids: Optional[list] = None,
                  **read_kwargs) -> TestDataset:
    """
    Load calibration test data from a CSV file.

    Expects one row per timestep with columns for time, attitude, and
    per-tank indicated weights/volumes. Scale weights are sparse (NaN for
    most rows, actual values at checkpoint times).

    Parameters
    ----------
    filepath : str or Path
        Path to the CSV file.
    sequence_type : str
        "defuel", "refuel", or "level_check".
    time_col, pitch_col, roll_col : str
        Column names for time and attitude.
    density_col : str, optional
        Column name for system density.
    scale_col : str, optional
        Column name for scale gross weight.
    dry_weight_col : str, optional
        Column name for dry weight.
    indicated_weight_prefix : str
        Prefix for per-tank weight columns (e.g., "indicated_weight_lb_T").
    indicated_volume_prefix : str
        Prefix for per-tank volume columns.
    tank_ids : list, optional
        Explicit tank ID list. If None, auto-detected from column names.
    **read_kwargs
        Passed to pd.read_csv.

    Returns
    -------
    TestDataset
    """
    df = pd.read_csv(filepath, **read_kwargs)

    # Auto-detect tank IDs from column names
    if tank_ids is None:
        tank_ids = []
        for col in df.columns:
            if col.startswith(indicated_weight_prefix):
                tid = col[len(indicated_weight_prefix):]
                tank_ids.append(tid)
        tank_ids = sorted(tank_ids)

    records = []
    for _, row in df.iterrows():
        ind_weights = {}
        ind_volumes = {}
        for tid in tank_ids:
            wt_col = f'{indicated_weight_prefix}{tid}'
            vol_col = f'{indicated_volume_prefix}{tid}'
            if wt_col in df.columns:
                ind_weights[tid] = float(row[wt_col])
            if vol_col in df.columns:
                ind_volumes[tid] = float(row[vol_col])

        scale_wt = None
        if scale_col and scale_col in df.columns:
            val = row[scale_col]
            if pd.notna(val):
                scale_wt = float(val)

        dry_wt = None
        if dry_weight_col and dry_weight_col in df.columns:
            val = row[dry_weight_col]
            if pd.notna(val):
                dry_wt = float(val)

        density = None
        if density_col and density_col in df.columns:
            val = row[density_col]
            if pd.notna(val):
                density = float(val)

        records.append(TestRecord(
            time_s=float(row[time_col]),
            pitch_deg=float(row[pitch_col]),
            roll_deg=float(row[roll_col]),
            indicated_weights=ind_weights,
            indicated_volumes=ind_volumes,
            scale_weight_lb=scale_wt,
            dry_weight_lb=dry_wt,
            density_system=density,
        ))

    return TestDataset(
        records=records,
        sequence_type=sequence_type,
        tank_ids=tank_ids,
    )
