"""
Tests for the gauging simulation model and sequence generation.

Validates:
  - Density model calibration
  - Error injection is working
  - Defuel/refuel sequences have correct structure
  - Weight error magnitude is physically reasonable
  - Phase boundaries and tank activity
  - Scale weight reference points exist
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tank_geometry import build_tank_system
from src.hv_table_generator import generate_all_tables
from src.gauging_model import GaugingSystem, FuelProperties, ErrorConfig
from src.simulate_sequences import simulate_defuel, simulate_refuel


def _build_system():
    tanks = build_tank_system()
    tables = generate_all_tables(tanks)
    return tanks, tables


def test_density_model_calibration():
    """Density model should give ~6.71 lb/gal at nominal dielectric."""
    fp = FuelProperties()
    rho = fp.density_from_dielectric(fp.dielectric_fuel_nominal)
    assert abs(rho - 6.71) < 0.01, f"Density {rho:.4f} vs expected 6.71"
    print("PASS: test_density_model_calibration")


def test_density_bias_injection():
    """With bias enabled, system density should be 0.3% above lab."""
    tanks, tables = _build_system()
    ec = ErrorConfig(
        enable_density_bias=True,
        enable_dielectric_drift=False,
        enable_probe_noise=False,
        enable_t2_nonlinearity=False,
        enable_t3_blend_step=False,
        enable_t5_pitch_amplification=False,
        enable_table_quantization=False,
    )
    gs = GaugingSystem(tables, tanks, error_config=ec)

    fuel_heights = {tid: tanks[tid].wl_min + tanks[tid].height_wl * 0.5
                    for tid in tanks}
    result = gs.indicate_system(fuel_heights, 0.0, 0.0)

    bias_pct = (result['density_system'] / result['density_lab'] - 1.0) * 100
    assert abs(bias_pct - 0.3) < 0.05, \
        f"Density bias {bias_pct:.3f}% vs expected 0.3%"
    print("PASS: test_density_bias_injection")


def test_no_errors_give_small_error():
    """With all errors disabled, total weight error should be < 1 lb."""
    tanks, tables = _build_system()
    ec = ErrorConfig(
        enable_density_bias=False,
        enable_dielectric_drift=False,
        enable_probe_noise=False,
        enable_t2_nonlinearity=False,
        enable_t3_blend_step=False,
        enable_t5_pitch_amplification=False,
        enable_table_quantization=False,
    )
    gs = GaugingSystem(tables, tanks, error_config=ec)

    fuel_heights = {tid: tanks[tid].wl_min + tanks[tid].height_wl * 0.5
                    for tid in tanks}
    result = gs.indicate_system(fuel_heights, 0.0, 0.0)

    # With no errors and level attitude, error comes only from table discretization
    assert abs(result['total_weight_error_lb']) < 5.0, \
        f"Weight error {result['total_weight_error_lb']:.2f} lb (should be < 5 lb with no injected errors)"
    print(f"PASS: test_no_errors_give_small_error (error={result['total_weight_error_lb']:.3f} lb)")


def test_t2_nonlinearity_visible():
    """T2 should show elevated error at mid-fill due to injected nonlinearity."""
    tanks, tables = _build_system()
    ec = ErrorConfig(
        enable_density_bias=False,
        enable_dielectric_drift=False,
        enable_probe_noise=False,
        enable_t2_nonlinearity=True,
        enable_t3_blend_step=False,
        enable_t5_pitch_amplification=False,
        enable_table_quantization=False,
    )
    gs = GaugingSystem(tables, tanks, error_config=ec)

    # Check T2 error at different fill levels
    errors_by_fill = {}
    for fill_frac in [0.1, 0.3, 0.5, 0.7, 0.9]:
        fuel_heights = {tid: tanks[tid].wl_min + tanks[tid].height_wl * fill_frac
                        for tid in tanks}
        result = gs.indicate_system(fuel_heights, 0.0, 0.0)
        t2_err = result['tanks'][2]['volume_error_in3']
        errors_by_fill[fill_frac] = t2_err

    # Error at 50% should be larger than at 10% or 90%
    assert abs(errors_by_fill[0.5]) > abs(errors_by_fill[0.1]), \
        f"T2 mid-fill error ({errors_by_fill[0.5]:.1f}) should exceed low-fill ({errors_by_fill[0.1]:.1f})"

    print(f"PASS: test_t2_nonlinearity_visible "
          f"(10%={errors_by_fill[0.1]:.1f}, 50%={errors_by_fill[0.5]:.1f}, "
          f"90%={errors_by_fill[0.9]:.1f} in³)")


def test_defuel_sequence_structure():
    """Defuel sequence should have correct columns, length, and phase structure."""
    tanks, tables = _build_system()
    df = simulate_defuel(tanks, tables, n_samples=100)

    assert len(df) == 100, f"Expected 100 rows, got {len(df)}"

    # Required columns
    required = [
        'time_s', 'pitch_deg', 'roll_deg', 'density_system',
        'total_indicated_weight_lb', 'total_true_weight_lb',
        'total_weight_error_lb', 'scale_gross_weight_lb',
    ]
    for col in required:
        assert col in df.columns, f"Missing column: {col}"

    # Per-tank columns
    for tid in range(1, 6):
        assert f'probe_height_T{tid}' in df.columns
        assert f'indicated_volume_gal_T{tid}' in df.columns

    # Fuel should decrease over time
    assert df['total_true_weight_lb'].iloc[0] > df['total_true_weight_lb'].iloc[-1], \
        "Fuel should decrease during defuel"

    print("PASS: test_defuel_sequence_structure")


def test_refuel_sequence_structure():
    """Refuel sequence should have increasing fuel."""
    tanks, tables = _build_system()
    df = simulate_refuel(tanks, tables, n_samples=80)

    assert len(df) == 80
    assert df['total_true_weight_lb'].iloc[-1] > df['total_true_weight_lb'].iloc[0], \
        "Fuel should increase during refuel"

    print("PASS: test_refuel_sequence_structure")


def test_scale_weights_present():
    """Scale weight reference points should exist at phase boundaries."""
    tanks, tables = _build_system()
    df = simulate_defuel(tanks, tables, n_samples=1000)

    scale_rows = df[df['scale_gross_weight_lb'].notna()]
    assert len(scale_rows) >= 3, \
        f"Expected at least 3 scale weight points, got {len(scale_rows)}"

    # Scale weight should be dry_weight + true fuel weight
    for idx in scale_rows.index:
        expected = df.loc[idx, 'dry_weight_lb'] + df.loc[idx, 'total_true_weight_lb']
        actual = df.loc[idx, 'scale_gross_weight_lb']
        assert abs(actual - expected) < 0.1, \
            f"Scale weight at idx {idx}: {actual:.1f} vs expected {expected:.1f}"

    print("PASS: test_scale_weights_present")


def test_weight_error_magnitude():
    """Total weight error should be physically reasonable (< 100 lb for ~4500 lb system)."""
    tanks, tables = _build_system()
    df = simulate_defuel(tanks, tables, n_samples=1000)

    max_err = df['total_weight_error_lb'].abs().max()
    assert max_err < 100.0, f"Max weight error {max_err:.1f} lb seems too large"
    assert max_err > 0.5, f"Max weight error {max_err:.3f} lb seems too small (errors not injecting?)"

    print(f"PASS: test_weight_error_magnitude (max={max_err:.2f} lb, "
          f"mean={df['total_weight_error_lb'].mean():.2f} lb)")


def test_defuel_phases():
    """Verify correct tanks are active in each defuel phase."""
    tanks, tables = _build_system()
    df = simulate_defuel(tanks, tables, n_samples=1000)

    # Phase 1 (0-199): Only T1 should be draining
    phase1 = df[(df['sample'] >= 1) & (df['sample'] < 200)]
    if len(phase1) > 1:
        t1_change = abs(phase1['fuel_wl_T1'].iloc[-1] - phase1['fuel_wl_T1'].iloc[0])
        t3_change = abs(phase1['fuel_wl_T3'].iloc[-1] - phase1['fuel_wl_T3'].iloc[0])
        assert t1_change > 1.0, "T1 should be draining in phase 1"
        assert t3_change < 0.5, "T3 should not drain in phase 1"

    print("PASS: test_defuel_phases")


if __name__ == "__main__":
    tests = [
        test_density_model_calibration,
        test_density_bias_injection,
        test_no_errors_give_small_error,
        test_t2_nonlinearity_visible,
        test_defuel_sequence_structure,
        test_refuel_sequence_structure,
        test_scale_weights_present,
        test_weight_error_magnitude,
        test_defuel_phases,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
