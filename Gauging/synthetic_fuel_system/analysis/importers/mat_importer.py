"""
MM1D .mat struct importer for real aircraft H-V table data.

Handles two common .mat layouts:
  1. Flat: T1_heights, T1_volumes, pitch_range, roll_range (one variable per field)
  2. Nested struct: Tanks.T1.heights, Tanks.T1.volumes (MATLAB struct-of-structs)

Both layouts store cell arrays of variable-length vectors for the H-V data
at each attitude grid point. scipy.io loads these as object arrays containing
1-D numpy arrays of different lengths — this is the MM1D pattern.

Key name customization:
  All field names (heights, volumes, pitch, roll, cg) are configurable via
  kwargs so that a GPT-4.1 adapter can map any program's naming convention.

Usage:
    from analysis.importers.mat_importer import load_mat_tables

    # Flat layout with default key names
    data = load_mat_tables("tank_system.mat")

    # Custom key names for a specific program
    data = load_mat_tables("program_x.mat",
                           heights_key="H", volumes_key="V",
                           pitch_key="alpha", roll_key="phi")
"""

import numpy as np
from pathlib import Path
from scipy.io import loadmat
from typing import Optional

from .base import HVTable, TankData, FuelSystemData


def _extract_array(val):
    """
    Unwrap a MATLAB scalar or array from scipy.io's nested containers.

    scipy.io wraps scalars in 1x1 arrays and strings in arrays of arrays.
    This recursively unwraps to get the inner value.
    """
    while isinstance(val, np.ndarray):
        if val.dtype == object and val.size == 1:
            val = val.flat[0]
        elif val.size == 1 and val.dtype != object:
            return float(val.flat[0])
        else:
            break
    return val


def _detect_layout(mat: dict) -> str:
    """
    Detect whether the .mat file uses flat or nested struct layout.

    Flat: keys like 'T1_heights', 'pitch_range'
    Nested: a top-level 'Tanks' struct containing per-tank sub-structs
    """
    user_keys = [k for k in mat.keys() if not k.startswith('__')]

    # Check for nested struct
    for key in user_keys:
        val = mat[key]
        if hasattr(val, 'dtype') and val.dtype.names is not None:
            return 'nested'

    # Check for flat pattern
    for key in user_keys:
        if '_heights' in key or '_volumes' in key or '_Heights' in key:
            return 'flat'

    return 'flat'


def _load_flat(mat: dict,
               tank_prefix: str = "T",
               heights_key: str = "heights",
               volumes_key: str = "volumes",
               pitch_key: str = "pitch_range",
               roll_key: str = "roll_range",
               cg_fs_key: Optional[str] = "cg_fs",
               cg_bl_key: Optional[str] = "cg_bl",
               cg_wl_key: Optional[str] = "cg_wl") -> FuelSystemData:
    """
    Load from flat layout: T1_heights, T1_volumes, pitch_range, roll_range.

    Each Tn_heights and Tn_volumes is a cell array (object array) of shape
    [n_pitch x n_roll], where each cell contains a 1-D vector.
    """
    pitch_range = np.asarray(mat[pitch_key]).flatten()
    roll_range = np.asarray(mat[roll_key]).flatten()

    # Find all tank prefixes
    user_keys = [k for k in mat.keys() if not k.startswith('__')]
    tank_ids = set()
    for key in user_keys:
        # Match patterns like "T1_heights" or "LH_FWD_heights"
        if key.endswith(f'_{heights_key}'):
            tid = key[:-len(f'_{heights_key}')]
            tank_ids.add(tid)

    tanks = {}
    for tid in sorted(tank_ids):
        h_cell = mat[f'{tid}_{heights_key}']
        v_cell = mat[f'{tid}_{volumes_key}']

        # Load optional CG arrays
        cg_fs_cell = mat.get(f'{tid}_{cg_fs_key}') if cg_fs_key else None
        cg_bl_cell = mat.get(f'{tid}_{cg_bl_key}') if cg_bl_key else None
        cg_wl_cell = mat.get(f'{tid}_{cg_wl_key}') if cg_wl_key else None

        tables = {}
        for pi, pitch in enumerate(pitch_range):
            for ri, roll in enumerate(roll_range):
                h_vec = _extract_array(h_cell[pi, ri])
                v_vec = _extract_array(v_cell[pi, ri])

                kwargs = {}
                if cg_fs_cell is not None:
                    kwargs['cg_fs'] = _extract_array(cg_fs_cell[pi, ri])
                if cg_bl_cell is not None:
                    kwargs['cg_bl'] = _extract_array(cg_bl_cell[pi, ri])
                if cg_wl_cell is not None:
                    kwargs['cg_wl'] = _extract_array(cg_wl_cell[pi, ri])

                tables[(float(pitch), float(roll))] = HVTable(
                    heights=np.asarray(h_vec).flatten(),
                    volumes=np.asarray(v_vec).flatten(),
                    pitch_deg=float(pitch),
                    roll_deg=float(roll),
                    **kwargs,
                )

        # Load optional geometry metadata
        meta = {}
        for suffix in ['fs_min', 'fs_max', 'bl_min', 'bl_max', 'wl_min', 'wl_max']:
            geo_key = f'{tid}_{suffix}'
            if geo_key in mat:
                if 'geometry' not in meta:
                    meta['geometry'] = {}
                meta['geometry'][suffix] = float(_extract_array(mat[geo_key]))

        tanks[tid] = TankData(
            tank_id=tid,
            tables=tables,
            metadata=meta,
        )

    return FuelSystemData(tanks=tanks)


def _load_nested(mat: dict,
                 struct_key: str = "Tanks",
                 heights_field: str = "heights",
                 volumes_field: str = "volumes",
                 pitch_key: str = "pitch_range",
                 roll_key: str = "roll_range") -> FuelSystemData:
    """
    Load from nested struct layout: Tanks.T1.heights, Tanks.T1.volumes.

    The top-level struct has fields for each tank, each of which is a struct
    containing cell arrays for heights, volumes, etc.
    """
    pitch_range = np.asarray(mat[pitch_key]).flatten()
    roll_range = np.asarray(mat[roll_key]).flatten()

    # Navigate to the Tanks struct
    tanks_struct = _extract_array(mat[struct_key])

    tanks = {}
    for field_name in tanks_struct.dtype.names:
        tank_struct = _extract_array(tanks_struct[field_name])
        if not hasattr(tank_struct, 'dtype') or tank_struct.dtype.names is None:
            continue

        tid = field_name
        h_cell = _extract_array(tank_struct[heights_field])
        v_cell = _extract_array(tank_struct[volumes_field])

        tables = {}
        for pi, pitch in enumerate(pitch_range):
            for ri, roll in enumerate(roll_range):
                h_vec = _extract_array(h_cell[pi, ri])
                v_vec = _extract_array(v_cell[pi, ri])

                tables[(float(pitch), float(roll))] = HVTable(
                    heights=np.asarray(h_vec).flatten(),
                    volumes=np.asarray(v_vec).flatten(),
                    pitch_deg=float(pitch),
                    roll_deg=float(roll),
                )

        # Pull optional name/probe_type fields
        name = None
        if 'name' in (tank_struct.dtype.names or []):
            name = str(_extract_array(tank_struct['name']))

        tanks[tid] = TankData(
            tank_id=tid,
            tables=tables,
            name=name,
        )

    return FuelSystemData(tanks=tanks)


def load_mat_tables(filepath: str,
                    layout: Optional[str] = None,
                    **kwargs) -> FuelSystemData:
    """
    Load H-V tables from a .mat file into canonical containers.

    Auto-detects flat vs nested layout unless ``layout`` is specified.

    Parameters
    ----------
    filepath : str or Path
        Path to the .mat file.
    layout : str, optional
        Force "flat" or "nested" layout detection. Auto-detects if None.
    **kwargs
        Passed through to the layout-specific loader. Use these to customize
        key/field names for your program's .mat convention:
          - heights_key, volumes_key, pitch_key, roll_key (flat)
          - struct_key, heights_field, volumes_field (nested)

    Returns
    -------
    FuelSystemData
        Populated with TankData containing HVTable entries.
    """
    filepath = str(Path(filepath).expanduser())
    mat = loadmat(filepath, squeeze_me=False)

    if layout is None:
        layout = _detect_layout(mat)

    if layout == 'flat':
        return _load_flat(mat, **kwargs)
    elif layout == 'nested':
        return _load_nested(mat, **kwargs)
    else:
        raise ValueError(f"Unknown layout: {layout!r}. Use 'flat' or 'nested'.")
