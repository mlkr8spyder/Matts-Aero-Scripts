"""
Tests for H-V table generation and interpolation.

Validates:
  - Table structure and completeness
  - Volume monotonicity in tables
  - Max volume matches gross volume
  - Table interpolation accuracy
  - Cross-validation between table lookup and direct volume computation
  - .mat file can be loaded back
"""

import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tank_geometry import build_tank_system, fuel_volume_tilted_rect, IN3_PER_GALLON
from src.hv_table_generator import generate_all_tables, save_tables_mat, save_tables_json
from src.gauging_model import TableInterpolator


def _get_tables():
    """Helper to generate tables (cached-like)."""
    tanks = build_tank_system()
    tables = generate_all_tables(tanks)
    return tanks, tables


def test_table_completeness():
    """Verify all tables are generated for all pitch/roll/tank combos."""
    tanks, tables = _get_tables()

    n_pitch = len(tables['pitch_range'])
    n_roll = len(tables['roll_range'])

    assert n_pitch == 13, f"Expected 13 pitch values, got {n_pitch}"
    assert n_roll == 17, f"Expected 17 roll values, got {n_roll}"

    for tid in range(1, 6):
        assert tid in tables['tanks'], f"Missing tank {tid}"
        tank_tables = tables['tanks'][tid]['tables']
        assert len(tank_tables) == n_pitch, f"T{tid}: wrong number of pitch rows"
        for row in tank_tables:
            assert len(row) == n_roll, f"T{tid}: wrong number of roll columns"

    print("PASS: test_table_completeness")


def test_table_monotonicity():
    """Volume should be monotonically non-decreasing with height in every table."""
    tanks, tables = _get_tables()

    violations = 0
    for tid in range(1, 6):
        tank_tables = tables['tanks'][tid]['tables']
        for i, pitch_row in enumerate(tank_tables):
            for j, table in enumerate(pitch_row):
                vols = table['volumes_in3']
                for k in range(1, len(vols)):
                    if vols[k] < vols[k-1] - 0.1:  # small tolerance for numerical noise
                        violations += 1
                        if violations <= 3:
                            print(f"  WARNING: T{tid} pitch_idx={i} roll_idx={j} "
                                  f"h[{k}]={table['heights_rel'][k]:.1f}: "
                                  f"vol={vols[k]:.0f} < vol={vols[k-1]:.0f}")

    assert violations == 0, f"{violations} monotonicity violations"
    print("PASS: test_table_monotonicity")


def test_table_max_volume():
    """Maximum volume in each table should equal gross volume."""
    tanks, tables = _get_tables()

    for tid in range(1, 6):
        tank = tanks[tid]
        gross = tank.gross_volume_in3

        # Check the level-attitude table
        pi_zero = list(tables['pitch_range']).index(0.0)
        ri_zero = list(tables['roll_range']).index(0.0)
        table = tables['tanks'][tid]['tables'][pi_zero][ri_zero]
        max_vol = max(table['volumes_in3'])

        pct_err = abs(max_vol - gross) / gross * 100
        assert pct_err < 0.5, \
            f"T{tid} max volume {max_vol:.0f} vs gross {gross:.0f} ({pct_err:.2f}% off)"

    print("PASS: test_table_max_volume")


def test_interpolator_at_grid_points():
    """Table interpolator should exactly match table values at grid points."""
    tanks, tables = _get_tables()

    for tid in [1, 3, 5]:  # test a subset
        interp = TableInterpolator(tables, tid)
        pi_idx = 6  # pitch=0
        ri_idx = 8  # roll=0

        table = tables['tanks'][tid]['tables'][pi_idx][ri_idx]
        heights = table['heights_rel']
        volumes = table['volumes_in3']

        # Check a few points
        for k in [0, len(heights)//4, len(heights)//2, 3*len(heights)//4, -1]:
            h = heights[k]
            v_table = volumes[k]
            v_interp = interp.lookup_volume(h, 0.0, 0.0)

            assert abs(v_interp - v_table) < v_table * 0.01 + 1.0, \
                f"T{tid} h={h:.1f}: interp={v_interp:.0f} vs table={v_table:.0f}"

    print("PASS: test_interpolator_at_grid_points")


def test_interpolator_between_attitudes():
    """Interpolator between attitude grid points should give reasonable values."""
    tanks, tables = _get_tables()

    for tid in [1, 3, 5]:
        interp = TableInterpolator(tables, tid)
        tank = tanks[tid]

        # Half-height at pitch=1.5° (between grid points 1° and 2°)
        h_mid = (tank.wl_min + tank.height_wl * 0.5 - tank.probes[0].base_wl) \
                if tank.probes else tank.height_wl * 0.5

        v_at_1 = interp.lookup_volume(h_mid, 1.0, 0.0)
        v_at_2 = interp.lookup_volume(h_mid, 2.0, 0.0)
        v_at_1_5 = interp.lookup_volume(h_mid, 1.5, 0.0)

        # Should be between the two grid values
        v_min = min(v_at_1, v_at_2)
        v_max = max(v_at_1, v_at_2)
        assert v_min - 1.0 <= v_at_1_5 <= v_max + 1.0, \
            f"T{tid}: interp at 1.5° = {v_at_1_5:.0f}, not between {v_min:.0f} and {v_max:.0f}"

    print("PASS: test_interpolator_between_attitudes")


def test_cross_validate_table_vs_direct():
    """
    Compare table-interpolated volume against direct volume computation.
    They should agree closely at grid attitude points.
    """
    tanks, tables = _get_tables()

    max_err_pct = 0.0
    for tid in range(1, 6):
        tank = tanks[tid]
        interp = TableInterpolator(tables, tid)

        for pitch in [0.0, 3.0, -3.0]:
            for roll in [0.0, 4.0, -4.0]:
                # Test at 30%, 50%, 70% fill
                for fill_frac in [0.3, 0.5, 0.7]:
                    fill_wl = tank.wl_min + tank.height_wl * fill_frac

                    # Direct computation
                    v_direct = fuel_volume_tilted_rect(tank, fill_wl, pitch, roll)

                    # Table lookup (need probe-relative height)
                    if tank.probes:
                        probe_base = tank.probes[0].base_wl
                    else:
                        probe_base = tank.wl_min
                    h_rel = fill_wl - probe_base

                    v_table = interp.lookup_volume(h_rel, pitch, roll)

                    if v_direct > 100:  # skip very small volumes
                        err_pct = abs(v_table - v_direct) / v_direct * 100
                        max_err_pct = max(max_err_pct, err_pct)

                        assert err_pct < 2.0, \
                            f"T{tid} pitch={pitch} roll={roll} fill={fill_frac}: " \
                            f"table={v_table:.0f} vs direct={v_direct:.0f} ({err_pct:.2f}%)"

    print(f"PASS: test_cross_validate_table_vs_direct (max err: {max_err_pct:.3f}%)")


def test_mat_file_roundtrip():
    """Save and reload .mat file, verify data integrity."""
    tanks, tables = _get_tables()

    tmp_path = Path(__file__).parent.parent / "data" / "_test_roundtrip.mat"
    save_tables_mat(tables, str(tmp_path))

    from scipy.io import loadmat
    loaded = loadmat(str(tmp_path), squeeze_me=False)

    # Check pitch/roll ranges
    pitch_loaded = loaded['pitch_range'].flatten()
    np.testing.assert_array_almost_equal(pitch_loaded, tables['pitch_range'])

    roll_loaded = loaded['roll_range'].flatten()
    np.testing.assert_array_almost_equal(roll_loaded, tables['roll_range'])

    # Check T3 level-attitude volume data
    t3_vols = loaded['T3_volumes']
    pi_zero = 6
    ri_zero = 8
    vol_array = t3_vols[pi_zero, ri_zero]
    if isinstance(vol_array, np.ndarray) and vol_array.ndim == 2:
        vol_array = vol_array.flatten()

    expected = tables['tanks'][3]['tables'][pi_zero][ri_zero]['volumes_in3']
    np.testing.assert_array_almost_equal(vol_array, expected, decimal=1)

    # Clean up
    tmp_path.unlink()
    print("PASS: test_mat_file_roundtrip")


if __name__ == "__main__":
    tests = [
        test_table_completeness,
        test_table_monotonicity,
        test_table_max_volume,
        test_interpolator_at_grid_points,
        test_interpolator_between_attitudes,
        test_cross_validate_table_vs_direct,
        test_mat_file_roundtrip,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except (AssertionError, AssertionError) as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
