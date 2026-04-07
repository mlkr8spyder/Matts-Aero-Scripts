"""
Height-Volume (H-V) table generator for the synthetic fuel system.

Generates lookup tables mapping probe height → fuel volume for each tank
across a grid of pitch and roll attitudes. Also computes CG(x,y,z) vs height.

Tables are saved in both .mat (MATLAB) and .json formats.
"""

import numpy as np
import json
from pathlib import Path
from scipy.io import savemat
from typing import Optional

from .tank_geometry import (
    Tank, Probe, build_tank_system, fuel_volume_tilted_rect,
    fuel_height_at_point, wetted_height_on_probe, cg_for_fuel_state,
    IN3_PER_GALLON,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Attitude grid covers the operational envelope for ground and flight conditions.
# Pitch: +/-6 deg spans taxi, takeoff rotation, and climb/descent attitudes.
# Roll: +/-8 deg covers ground turning and moderate flight maneuvering.
# Height step: 0.5" balances table size (~40 points/tank) vs interpolation accuracy.
DEFAULT_PITCH_RANGE = np.arange(-6, 7, 1.0)      # -6 to +6 deg, 1° step
DEFAULT_ROLL_RANGE = np.arange(-8, 9, 1.0)        # -8 to +8 deg, 1° step
DEFAULT_HEIGHT_STEP = 0.5                           # inches between table points


def generate_hv_table_for_tank(tank: Tank, pitch_deg: float, roll_deg: float,
                               height_step: float = DEFAULT_HEIGHT_STEP,
                               ref_fs: Optional[float] = None,
                               ref_bl: Optional[float] = None,
                               debug: bool = False) -> dict:
    """
    Generate a height-vs-volume table for one tank at one attitude.

    The "height" axis is the fuel surface WL at the reference point (probe location
    or tank center). For each height, we compute:
      - Volume (in³ and gallons)
      - CG location (FS, BL, WL)

    Parameters
    ----------
    tank : Tank
    pitch_deg, roll_deg : float
    height_step : float
        Step size in inches for the height axis.
    ref_fs, ref_bl : optional
        Reference point for height measurement. For real probes, this should be
        the probe location. Defaults to tank center.

    Returns
    -------
    dict with keys: heights, volumes_in3, volumes_gal, cg_fs, cg_bl, cg_wl, N
    """
    # Determine reference point
    if ref_fs is None:
        if tank.probes:
            ref_fs = tank.probes[0].center_fs
        else:
            ref_fs = tank.center_fs
    if ref_bl is None:
        if tank.probes:
            ref_bl = tank.probes[0].center_bl
        else:
            ref_bl = tank.center_bl

    # Height range: from tank floor to tank ceiling
    # The height at the reference point ranges based on attitude
    # We sweep the fuel surface WL at the ref point from below tank floor
    # to above tank ceiling
    # Extend height range 1" beyond physical tank bounds to ensure the lookup
    # table covers edge cases where attitude tilts fuel above the ceiling or
    # below the floor at the probe location.
    wl_start = tank.wl_min - 1.0  # slightly below floor
    wl_end = tank.wl_max + 1.0    # slightly above ceiling

    heights_wl = np.arange(wl_start, wl_end + height_step/2, height_step)

    volumes_in3 = []
    cg_fs_list = []
    cg_bl_list = []
    cg_wl_list = []

    for h_wl in heights_wl:
        vol = fuel_volume_tilted_rect(tank, h_wl, pitch_deg, roll_deg,
                                      ref_fs=ref_fs, ref_bl=ref_bl)
        cg = cg_for_fuel_state(tank, h_wl, pitch_deg, roll_deg,
                               ref_fs=ref_fs, ref_bl=ref_bl)

        volumes_in3.append(vol)
        cg_fs_list.append(cg[0])
        cg_bl_list.append(cg[1])
        cg_wl_list.append(cg[2])

    # Convert to probe height (relative to probe base or tank floor)
    # For tanks with probes, height is relative to probe base WL
    if tank.probes:
        probe_base_wl = tank.probes[0].base_wl
    else:
        probe_base_wl = tank.wl_min

    heights_rel = heights_wl - probe_base_wl

    result = {
        'heights_wl': np.array(heights_wl),
        'heights_rel': np.array(heights_rel),
        'volumes_in3': np.array(volumes_in3),
        'volumes_gal': np.array(volumes_in3) / IN3_PER_GALLON,
        'cg_fs': np.array(cg_fs_list),
        'cg_bl': np.array(cg_bl_list),
        'cg_wl': np.array(cg_wl_list),
        'N': len(heights_wl),
        'pitch_deg': pitch_deg,
        'roll_deg': roll_deg,
        'ref_fs': ref_fs,
        'ref_bl': ref_bl,
        'probe_base_wl': probe_base_wl,
    }

    if debug:
        print(f"  T{tank.tank_id} at pitch={pitch_deg:.0f}° roll={roll_deg:.0f}°: "
              f"{result['N']} points, "
              f"vol range [{min(volumes_in3):.0f}, {max(volumes_in3):.0f}] in³")

    return result


def generate_all_tables(tanks: dict = None,
                        pitch_range: np.ndarray = None,
                        roll_range: np.ndarray = None,
                        height_step: float = DEFAULT_HEIGHT_STEP,
                        debug: bool = False) -> dict:
    """
    Generate H-V tables for all tanks across the full attitude grid.

    Returns
    -------
    all_tables : dict
        Nested: all_tables[tank_id][pitch_idx][roll_idx] = table_dict
        Also includes metadata: pitch_range, roll_range, tank_info
    """
    if tanks is None:
        tanks = build_tank_system()
    if pitch_range is None:
        pitch_range = DEFAULT_PITCH_RANGE
    if roll_range is None:
        roll_range = DEFAULT_ROLL_RANGE

    all_tables = {
        'pitch_range': pitch_range,
        'roll_range': roll_range,
        'tanks': {},
    }

    for tid in sorted(tanks.keys()):
        tank = tanks[tid]
        if debug:
            print(f"\nGenerating tables for T{tid} ({tank.name})...")

        tank_tables = []
        for i, pitch in enumerate(pitch_range):
            pitch_row = []
            # tables[pitch_index][roll_index] — row-major: outer loop is pitch
            for j, roll in enumerate(roll_range):
                table = generate_hv_table_for_tank(
                    tank, pitch, roll, height_step, debug=debug
                )
                pitch_row.append(table)
            tank_tables.append(pitch_row)

        all_tables['tanks'][tid] = {
            'name': tank.name,
            'tank_id': tid,
            'probe_type': tank.probe_type,
            'tables': tank_tables,
            'geometry': {
                'fs_min': tank.fs_min, 'fs_max': tank.fs_max,
                'bl_min': tank.bl_min, 'bl_max': tank.bl_max,
                'wl_min': tank.wl_min, 'wl_max': tank.wl_max,
            },
            'probes': [
                {
                    'name': p.name,
                    'base_fs': p.base_fs, 'base_bl': p.base_bl, 'base_wl': p.base_wl,
                    'top_fs': p.top_fs, 'top_bl': p.top_bl, 'top_wl': p.top_wl,
                    'active_length': p.active_length,
                    'tilt_deg': p.tilt_deg,
                }
                for p in tank.probes
            ],
        }

    return all_tables


def save_tables_mat(all_tables: dict, filepath: str, debug: bool = False) -> None:
    """
    Save all H-V tables to a MATLAB .mat file.

    Structure in .mat:
        pitch_range, roll_range (vectors)
        T{n}_heights   — cell array [n_pitch × n_roll] of height vectors
        T{n}_volumes   — cell array [n_pitch × n_roll] of volume vectors (in³)
        T{n}_cg_fs     — cell array [n_pitch × n_roll] of CG-FS vectors
        T{n}_cg_bl     — cell array [n_pitch × n_roll] of CG-BL vectors
        T{n}_cg_wl     — cell array [n_pitch × n_roll] of CG-WL vectors
        T{n}_geometry  — struct with tank bounds
        T{n}_probes    — struct array with probe info
    """
    mat_dict = {
        'pitch_range': all_tables['pitch_range'],
        'roll_range': all_tables['roll_range'],
    }

    for tid, tdata in all_tables['tanks'].items():
        prefix = f'T{tid}'
        tables = tdata['tables']
        n_pitch = len(tables)
        n_roll = len(tables[0])

        # Create object arrays for variable-length tables
        heights_cell = np.empty((n_pitch, n_roll), dtype=object)
        volumes_cell = np.empty((n_pitch, n_roll), dtype=object)
        cg_fs_cell = np.empty((n_pitch, n_roll), dtype=object)
        cg_bl_cell = np.empty((n_pitch, n_roll), dtype=object)
        cg_wl_cell = np.empty((n_pitch, n_roll), dtype=object)

        for i in range(n_pitch):
            for j in range(n_roll):
                t = tables[i][j]
                heights_cell[i, j] = t['heights_rel']
                volumes_cell[i, j] = t['volumes_in3']
                cg_fs_cell[i, j] = t['cg_fs']
                cg_bl_cell[i, j] = t['cg_bl']
                cg_wl_cell[i, j] = t['cg_wl']

        mat_dict[f'{prefix}_heights'] = heights_cell
        mat_dict[f'{prefix}_volumes'] = volumes_cell
        mat_dict[f'{prefix}_cg_fs'] = cg_fs_cell
        mat_dict[f'{prefix}_cg_bl'] = cg_bl_cell
        mat_dict[f'{prefix}_cg_wl'] = cg_wl_cell

        # Geometry as a flat structure
        geo = tdata['geometry']
        mat_dict[f'{prefix}_fs_min'] = geo['fs_min']
        mat_dict[f'{prefix}_fs_max'] = geo['fs_max']
        mat_dict[f'{prefix}_bl_min'] = geo['bl_min']
        mat_dict[f'{prefix}_bl_max'] = geo['bl_max']
        mat_dict[f'{prefix}_wl_min'] = geo['wl_min']
        mat_dict[f'{prefix}_wl_max'] = geo['wl_max']

        # Probe info
        for pi, pinfo in enumerate(tdata['probes']):
            pp = f'{prefix}_probe{pi+1}'
            for key, val in pinfo.items():
                mat_dict[f'{pp}_{key}'] = val

    savemat(filepath, mat_dict, do_compression=True)
    if debug:
        print(f"Saved .mat file: {filepath} ({Path(filepath).stat().st_size / 1024:.0f} KB)")


def save_tables_json(all_tables: dict, filepath: str, debug: bool = False) -> None:
    """Save all H-V tables to a JSON file (Python-friendly format)."""

    def convert(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.float64, np.float32)):
            return float(obj)
        if isinstance(obj, (np.int64, np.int32)):
            return int(obj)
        raise TypeError(f"Cannot serialize {type(obj)}")

    # Build a clean dict
    output = {
        'pitch_range': all_tables['pitch_range'].tolist(),
        'roll_range': all_tables['roll_range'].tolist(),
        'tanks': {},
    }

    for tid, tdata in all_tables['tanks'].items():
        tank_out = {
            'name': tdata['name'],
            'tank_id': tdata['tank_id'],
            'probe_type': tdata['probe_type'],
            'geometry': tdata['geometry'],
            'probes': tdata['probes'],
            'tables': [],
        }

        for i, pitch_row in enumerate(tdata['tables']):
            row_out = []
            for j, table in enumerate(pitch_row):
                t = {
                    'pitch_deg': float(table['pitch_deg']),
                    'roll_deg': float(table['roll_deg']),
                    'N': table['N'],
                    'heights_rel': table['heights_rel'].tolist(),
                    'volumes_in3': table['volumes_in3'].tolist(),
                    'volumes_gal': table['volumes_gal'].tolist(),
                    'cg_fs': [float(x) if not np.isnan(x) else None for x in table['cg_fs']],
                    'cg_bl': [float(x) if not np.isnan(x) else None for x in table['cg_bl']],
                    'cg_wl': [float(x) if not np.isnan(x) else None for x in table['cg_wl']],
                }
                row_out.append(t)
            tank_out['tables'].append(row_out)

        output['tanks'][str(tid)] = tank_out

    with open(filepath, 'w') as f:
        json.dump(output, f, default=convert, indent=2)

    if debug:
        print(f"Saved JSON file: {filepath} ({Path(filepath).stat().st_size / 1024:.0f} KB)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import time

    print("Building tank system...")
    tanks = build_tank_system()

    print("Generating H-V tables...")
    t0 = time.time()
    all_tables = generate_all_tables(tanks, debug=False)
    elapsed = time.time() - t0
    print(f"Generated in {elapsed:.1f}s")

    # Count total tables
    n_pitch = len(all_tables['pitch_range'])
    n_roll = len(all_tables['roll_range'])
    total = 5 * n_pitch * n_roll
    print(f"Total tables: {total} ({n_pitch} pitch × {n_roll} roll × 5 tanks)")

    # Save
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)

    mat_path = data_dir / "tank_system.mat"
    json_path = data_dir / "tank_system.json"

    print(f"Saving .mat → {mat_path}")
    save_tables_mat(all_tables, str(mat_path), debug=True)

    print(f"Saving .json → {json_path}")
    save_tables_json(all_tables, str(json_path), debug=True)

    # Quick validation: check a specific table
    print("\nValidation — T3 at pitch=0°, roll=0°:")
    t3_table = all_tables['tanks'][3]['tables'][6][8]  # pitch=0 is index 6, roll=0 is index 8
    print(f"  N points: {t3_table['N']}")
    print(f"  Height range: {t3_table['heights_rel'][0]:.1f} to {t3_table['heights_rel'][-1]:.1f}")
    print(f"  Volume range: {t3_table['volumes_in3'][0]:.0f} to {t3_table['volumes_in3'][-1]:.0f} in³")
    max_vol_gal = max(t3_table['volumes_gal'])
    print(f"  Max volume: {max_vol_gal:.2f} gal (gross={tanks[3].gross_volume_gal:.2f} gal)")
