"""
Bridge from the synthetic fuel system (src/) to analysis toolkit containers.

This is the only importer that depends on the src/ package. It converts
the in-memory table and sequence structures into the canonical HVTable,
TankData, TestRecord, etc. containers used by the analysis layer.

Typical usage:
    from analysis.importers.synthetic_bridge import load_synthetic_system

    data = load_synthetic_system()           # tables + defuel + refuel
    data = load_synthetic_system(tables_only=True)  # just H-V tables
"""

import numpy as np
import pandas as pd
from typing import Optional

from .base import HVTable, TankData, TestRecord, TestDataset, FuelSystemData


def _convert_tables(all_tables: dict) -> dict:
    """
    Convert the src/ table dict into {tank_id_str: TankData}.

    The src/ format stores tables as:
        all_tables['tanks'][int_id]['tables'][pitch_idx][roll_idx] -> dict
    with shared pitch_range and roll_range arrays.

    We convert to the canonical format where each TankData holds a dict
    of (pitch, roll) -> HVTable with variable-length arrays.
    """
    pitch_range = np.asarray(all_tables['pitch_range'])
    roll_range = np.asarray(all_tables['roll_range'])
    tanks = {}

    for tid, tdata in all_tables['tanks'].items():
        tank_id = f"T{tid}"
        tables = {}

        for pi, pitch in enumerate(pitch_range):
            for ri, roll in enumerate(roll_range):
                raw = tdata['tables'][pi][ri]
                hv = HVTable(
                    heights=raw['heights_rel'],
                    volumes=raw['volumes_in3'],
                    pitch_deg=float(pitch),
                    roll_deg=float(roll),
                    cg_fs=raw.get('cg_fs'),
                    cg_bl=raw.get('cg_bl'),
                    cg_wl=raw.get('cg_wl'),
                )
                tables[(float(pitch), float(roll))] = hv

        # Collect geometry and probe info as metadata
        meta = {}
        if 'geometry' in tdata:
            meta['geometry'] = tdata['geometry']
        if 'probes' in tdata:
            meta['probes'] = tdata['probes']

        tanks[tank_id] = TankData(
            tank_id=tank_id,
            tables=tables,
            name=tdata.get('name'),
            probe_type=tdata.get('probe_type'),
            metadata=meta,
        )

    return tanks


def _convert_sequence(df: pd.DataFrame, sequence_type: str,
                      tank_ids: list) -> TestDataset:
    """
    Convert a simulation DataFrame into a TestDataset.

    The src/ DataFrames use columns like:
        indicated_weight_lb_T1, indicated_volume_gal_T1, etc.
    """
    records = []
    for _, row in df.iterrows():
        # Per-tank indicated weights and volumes
        ind_weights = {}
        ind_volumes = {}
        meta = {}

        for tid in tank_ids:
            # Strip the "T" prefix to get the numeric suffix used in column names
            num = tid[1:]  # "T3" -> "3"
            wt_col = f'indicated_weight_lb_T{num}'
            vol_col = f'indicated_volume_gal_T{num}'
            if wt_col in row:
                ind_weights[tid] = float(row[wt_col])
            if vol_col in row:
                ind_volumes[tid] = float(row[vol_col])

            # Stash true values and probe heights in metadata for validation
            true_wt_col = f'true_weight_lb_T{num}'
            ph_col = f'probe_height_T{num}'
            if true_wt_col in row:
                meta[f'true_weight_lb_{tid}'] = float(row[true_wt_col])
            if ph_col in row:
                meta[f'probe_height_{tid}'] = float(row[ph_col])

        # Scale weight (NaN -> None)
        scale_wt = row.get('scale_gross_weight_lb')
        if pd.notna(scale_wt):
            scale_wt = float(scale_wt)
        else:
            scale_wt = None

        dry_wt = row.get('dry_weight_lb')
        if pd.notna(dry_wt):
            dry_wt = float(dry_wt)
        else:
            dry_wt = None

        density = row.get('density_system')
        if pd.notna(density):
            density = float(density)
        else:
            density = None

        # Extra metadata
        if 'phase' in row:
            meta['phase'] = int(row['phase'])
        if 'active_tanks' in row:
            meta['active_tanks'] = row['active_tanks']

        records.append(TestRecord(
            time_s=float(row['time_s']),
            pitch_deg=float(row['pitch_deg']),
            roll_deg=float(row['roll_deg']),
            indicated_weights=ind_weights,
            indicated_volumes=ind_volumes,
            scale_weight_lb=scale_wt,
            dry_weight_lb=dry_wt,
            density_system=density,
            metadata=meta,
        ))

    return TestDataset(
        records=records,
        sequence_type=sequence_type,
        tank_ids=tank_ids,
    )


def load_synthetic_system(tables_only: bool = False,
                          n_defuel: int = 1000,
                          n_refuel: int = 800) -> FuelSystemData:
    """
    Build a FuelSystemData from the synthetic fuel system simulation.

    Generates tables and (optionally) defuel/refuel sequences in memory.
    No files need to exist on disk.

    Parameters
    ----------
    tables_only : bool
        If True, skip sequence simulation (faster).
    n_defuel : int
        Number of samples for the defuel sequence.
    n_refuel : int
        Number of samples for the refuel sequence.

    Returns
    -------
    FuelSystemData
        Complete dataset with tanks, tables, and test sequences.
    """
    # Import src/ modules (only dependency on src/)
    from synthetic_fuel_system.src.tank_geometry import build_tank_system
    from synthetic_fuel_system.src.hv_table_generator import generate_all_tables
    from synthetic_fuel_system.src.simulate_sequences import (
        simulate_defuel, simulate_refuel,
    )

    # Build tables
    src_tanks = build_tank_system()
    all_tables = generate_all_tables(src_tanks)
    tanks = _convert_tables(all_tables)
    tank_ids = sorted(tanks.keys())

    # Config from the synthetic system
    config = {
        'dataset_type': 'synthetic',
        'dry_weight_lb': 12000.0,
        'fuel_density_lab_lb_per_gal': 6.71,
        'n_tanks': len(tanks),
    }

    test_data = []
    if not tables_only:
        # Defuel sequence
        df_defuel = simulate_defuel(src_tanks, all_tables, n_samples=n_defuel)
        test_data.append(
            _convert_sequence(df_defuel, 'defuel', tank_ids)
        )

        # Refuel sequence
        df_refuel = simulate_refuel(src_tanks, all_tables, n_samples=n_refuel)
        test_data.append(
            _convert_sequence(df_refuel, 'refuel', tank_ids)
        )

    return FuelSystemData(
        tanks=tanks,
        test_data=test_data,
        config=config,
    )
