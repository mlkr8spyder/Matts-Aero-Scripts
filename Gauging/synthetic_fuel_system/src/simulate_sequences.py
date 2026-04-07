"""
Simulate defuel and refuel sequences for the synthetic fuel system.

Generates time-history datasets with:
  - Continuous probe heights for all tanks
  - Pitch/roll attitude (slowly varying)
  - Per-tank indicated volumes and weights
  - System-computed density
  - Total indicated fuel weight
  - Scale reference weights (at start/end points)
  - Known error contributions for validation

Defuel order: T1 (forward) first, then T2+T4 simultaneously, then T5, then T3
Refuel order: T3 first, then T5, then T2+T4 simultaneously, then T1 last
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.io import savemat

from .tank_geometry import build_tank_system, fuel_volume_tilted_rect, IN3_PER_GALLON
from .hv_table_generator import generate_all_tables
from .gauging_model import GaugingSystem, FuelProperties, ErrorConfig


def _attitude_profile(n_samples: int, rng: np.random.Generator,
                      pitch_mean: float = 0.0, roll_mean: float = 0.0,
                      pitch_var: float = 1.5, roll_var: float = 2.0) -> tuple:
    """
    Generate a slowly-varying attitude profile.
    Simulates ground operations with gentle pitch/roll variations.
    """
    # First-order exponential low-pass filter with mean reversion.
    # alpha = 0.005 gives time constant tau = 1/alpha = 200 samples (~200s).
    # This produces slowly-varying attitude that mimics ground operations
    # (taxi, fuel truck loading) with occasional gentle excursions.
    dt = 1.0  # seconds per sample

    # Pitch: slow wander
    pitch_noise = rng.normal(0, 0.02, n_samples)
    pitch = np.zeros(n_samples)
    pitch[0] = pitch_mean
    for i in range(1, n_samples):
        pitch[i] = 0.995 * pitch[i-1] + pitch_noise[i] + 0.005 * (pitch_mean - pitch[i-1])
    pitch = np.clip(pitch, -6, 6)

    # Roll: slightly more variable
    roll_noise = rng.normal(0, 0.03, n_samples)
    roll = np.zeros(n_samples)
    roll[0] = roll_mean
    for i in range(1, n_samples):
        roll[i] = 0.993 * roll[i-1] + roll_noise[i] + 0.007 * (roll_mean - roll[i-1])
    roll = np.clip(roll, -8, 8)

    return pitch, roll


def simulate_defuel(tanks: dict = None, all_tables: dict = None,
                    n_samples: int = 1000, seed: int = 42,
                    debug: bool = False) -> pd.DataFrame:
    """
    Simulate a complete defuel sequence.

    Defuel order:
      Phase 1 (samples 0-200):   T1 drains (forward tank, smallest)
      Phase 2 (samples 200-550): T2 + T4 drain simultaneously
      Phase 3 (samples 550-750): T5 drains
      Phase 4 (samples 750-1000): T3 drains (center collector, last)

    All tanks start at max fill (98% = below ullage).
    """
    if tanks is None:
        tanks = build_tank_system()
    if all_tables is None:
        all_tables = generate_all_tables(tanks)

    rng = np.random.default_rng(seed)
    error_config = ErrorConfig()
    gs = GaugingSystem(all_tables, tanks, error_config=error_config)

    # Attitude profile
    pitch, roll = _attitude_profile(n_samples, rng, pitch_mean=0.3, roll_mean=-0.2)

    # Initialize fuel levels (WL at tank center) — start at max fill
    fuel_wl = {}
    for tid, tank in tanks.items():
        fuel_wl[tid] = tank.max_fill_wl

    # Defuel rates (WL drop per sample)
    # T1: 16" usable height over 200 samples = 0.078"/sample
    # T2/T4: 18" usable height over 350 samples = 0.050"/sample
    # T5: 22" usable height over 200 samples = 0.107"/sample
    # T3: 20" usable height over 250 samples = 0.078"/sample

    records = []
    phase_boundaries = [0, 200, 550, 750, n_samples]
    active_tanks_per_phase = [
        [1],      # Phase 1: T1 only
        [2, 4],   # Phase 2: T2 + T4
        [5],      # Phase 3: T5
        [3],      # Phase 4: T3
    ]
    # Drain rates chosen so each tank empties over its assigned phase duration.
    # Rate = usable_height / phase_samples. For example:
    #   T1: 16" usable / 200 samples = 0.078"/sample
    #   T2: 18" usable / 350 samples = 0.050"/sample (shared phase with T4)
    drain_rates = {
        1: 0.078,
        2: 0.050,
        3: 0.078,
        4: 0.050,
        5: 0.107,
    }

    for i in range(n_samples):
        # Determine which phase we're in
        phase = 0
        for p in range(len(phase_boundaries) - 1):
            if phase_boundaries[p] <= i < phase_boundaries[p + 1]:
                phase = p
                break

        # Drain active tanks
        for tid in active_tanks_per_phase[phase]:
            tank = tanks[tid]
            fuel_wl[tid] -= drain_rates[tid]
            # Clamp to unusable fuel level
            fuel_wl[tid] = max(fuel_wl[tid], tank.min_fuel_wl)

        # Run gauging system
        result = gs.indicate_system(fuel_wl, pitch[i], roll[i], sample_idx=i)

        # Build record
        row = {
            'sample': i,
            'time_s': float(i),
            'pitch_deg': pitch[i],
            'roll_deg': roll[i],
            'density_system': result['density_system'],
            'density_lab': result['density_lab'],
            'density_error': result['density_error'],
            'total_indicated_volume_gal': result['total_indicated_volume_gal'],
            'total_true_volume_gal': result['total_true_volume_gal'],
            'total_indicated_weight_lb': result['total_indicated_weight_lb'],
            'total_true_weight_lb': result['total_true_weight_lb'],
            'total_weight_error_lb': result['total_weight_error_lb'],
        }

        # Per-tank data
        for tid in sorted(tanks.keys()):
            tr = result['tanks'][tid]
            row[f'probe_height_T{tid}'] = tr['probe_height_raw']
            row[f'indicated_volume_gal_T{tid}'] = tr['indicated_volume_gal']
            row[f'indicated_weight_lb_T{tid}'] = tr['indicated_weight_lb']
            row[f'true_volume_gal_T{tid}'] = tr['true_volume_gal']
            row[f'true_weight_lb_T{tid}'] = tr['true_weight_lb']
            row[f'volume_error_in3_T{tid}'] = tr['volume_error_in3']
            row[f'fuel_wl_T{tid}'] = fuel_wl[tid]

        # Phase marker
        row['phase'] = phase + 1
        row['active_tanks'] = str(active_tanks_per_phase[phase])

        records.append(row)

    df = pd.DataFrame(records)

    # Simulate scale checkpoints at phase boundaries.
    # In real operations, the aircraft is weighed at the start, end, and at
    # key transition points during a calibration defuel/refuel.
    df['scale_gross_weight_lb'] = np.nan
    dry_weight = 12000.0  # synthetic dry weight

    # Scale reading at start
    df.loc[0, 'scale_gross_weight_lb'] = dry_weight + df.loc[0, 'total_true_weight_lb']
    # Scale reading at end
    df.loc[n_samples-1, 'scale_gross_weight_lb'] = dry_weight + df.loc[n_samples-1, 'total_true_weight_lb']
    # A few intermediate scale readings
    for idx in [200, 550, 750]:
        if idx < n_samples:
            df.loc[idx, 'scale_gross_weight_lb'] = dry_weight + df.loc[idx, 'total_true_weight_lb']

    df['dry_weight_lb'] = dry_weight

    if debug:
        print(f"Defuel simulation: {n_samples} samples")
        print(f"  Start weight: {df['total_true_weight_lb'].iloc[0]:.1f} lb")
        print(f"  End weight: {df['total_true_weight_lb'].iloc[-1]:.1f} lb")
        print(f"  Max error: {df['total_weight_error_lb'].abs().max():.2f} lb")
        print(f"  Mean error: {df['total_weight_error_lb'].mean():.2f} lb")

    return df


def simulate_refuel(tanks: dict = None, all_tables: dict = None,
                    n_samples: int = 800, seed: int = 123,
                    debug: bool = False) -> pd.DataFrame:
    """
    Simulate a complete refuel sequence.

    Refuel order (reverse of defuel):
      Phase 1 (samples 0-250):   T3 fills (center collector first)
      Phase 2 (samples 250-450): T5 fills
      Phase 3 (samples 450-700): T2 + T4 fill simultaneously
      Phase 4 (samples 700-800): T1 fills (forward tank, last)
    """
    if tanks is None:
        tanks = build_tank_system()
    if all_tables is None:
        all_tables = generate_all_tables(tanks)

    rng = np.random.default_rng(seed)
    error_config = ErrorConfig()
    gs = GaugingSystem(all_tables, tanks, error_config=error_config)

    pitch, roll = _attitude_profile(n_samples, rng, pitch_mean=-0.1, roll_mean=0.3)

    # Initialize at empty (unusable fuel level)
    fuel_wl = {}
    for tid, tank in tanks.items():
        fuel_wl[tid] = tank.min_fuel_wl

    fill_rates = {
        1: 0.155,
        2: 0.070,
        3: 0.078,
        4: 0.070,
        5: 0.107,
    }

    phase_boundaries = [0, 250, 450, 700, n_samples]
    active_tanks_per_phase = [
        [3],      # Phase 1: T3 only
        [5],      # Phase 2: T5
        [2, 4],   # Phase 3: T2 + T4
        [1],      # Phase 4: T1
    ]

    records = []
    for i in range(n_samples):
        phase = 0
        for p in range(len(phase_boundaries) - 1):
            if phase_boundaries[p] <= i < phase_boundaries[p + 1]:
                phase = p
                break

        for tid in active_tanks_per_phase[phase]:
            tank = tanks[tid]
            fuel_wl[tid] += fill_rates[tid]
            fuel_wl[tid] = min(fuel_wl[tid], tank.max_fill_wl)

        result = gs.indicate_system(fuel_wl, pitch[i], roll[i], sample_idx=i)

        row = {
            'sample': i,
            'time_s': float(i),
            'pitch_deg': pitch[i],
            'roll_deg': roll[i],
            'density_system': result['density_system'],
            'density_lab': result['density_lab'],
            'density_error': result['density_error'],
            'total_indicated_volume_gal': result['total_indicated_volume_gal'],
            'total_true_volume_gal': result['total_true_volume_gal'],
            'total_indicated_weight_lb': result['total_indicated_weight_lb'],
            'total_true_weight_lb': result['total_true_weight_lb'],
            'total_weight_error_lb': result['total_weight_error_lb'],
        }

        for tid in sorted(tanks.keys()):
            tr = result['tanks'][tid]
            row[f'probe_height_T{tid}'] = tr['probe_height_raw']
            row[f'indicated_volume_gal_T{tid}'] = tr['indicated_volume_gal']
            row[f'indicated_weight_lb_T{tid}'] = tr['indicated_weight_lb']
            row[f'true_volume_gal_T{tid}'] = tr['true_volume_gal']
            row[f'true_weight_lb_T{tid}'] = tr['true_weight_lb']
            row[f'volume_error_in3_T{tid}'] = tr['volume_error_in3']
            row[f'fuel_wl_T{tid}'] = fuel_wl[tid]

        row['phase'] = phase + 1
        row['active_tanks'] = str(active_tanks_per_phase[phase])
        records.append(row)

    df = pd.DataFrame(records)

    dry_weight = 12000.0
    df['scale_gross_weight_lb'] = np.nan
    df.loc[0, 'scale_gross_weight_lb'] = dry_weight + df.loc[0, 'total_true_weight_lb']
    df.loc[n_samples-1, 'scale_gross_weight_lb'] = dry_weight + df.loc[n_samples-1, 'total_true_weight_lb']
    for idx in [250, 450, 700]:
        if idx < n_samples:
            df.loc[idx, 'scale_gross_weight_lb'] = dry_weight + df.loc[idx, 'total_true_weight_lb']
    df['dry_weight_lb'] = dry_weight

    if debug:
        print(f"Refuel simulation: {n_samples} samples")
        print(f"  Start weight: {df['total_true_weight_lb'].iloc[0]:.1f} lb")
        print(f"  End weight: {df['total_true_weight_lb'].iloc[-1]:.1f} lb")
        print(f"  Max error: {df['total_weight_error_lb'].abs().max():.2f} lb")
        print(f"  Mean error: {df['total_weight_error_lb'].mean():.2f} lb")

    return df


def save_sequence_mat(df: pd.DataFrame, filepath: str, debug: bool = False) -> None:
    """Save a sequence DataFrame to MATLAB .mat format."""
    mat_dict = {}
    for col in df.columns:
        if df[col].dtype == object:
            # String columns — save as cell array
            mat_dict[col] = np.array(df[col].values, dtype=object)
        else:
            mat_dict[col] = df[col].values.astype(float)

    savemat(filepath, mat_dict, do_compression=True)
    if debug:
        size_kb = Path(filepath).stat().st_size / 1024
        print(f"Saved: {filepath} ({size_kb:.0f} KB, {len(df)} rows, {len(df.columns)} cols)")


# ---------------------------------------------------------------------------
# Main — generate and save all sequences
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import time

    print("Building system and tables...")
    tanks = build_tank_system()
    t0 = time.time()
    all_tables = generate_all_tables(tanks)
    print(f"Tables generated in {time.time()-t0:.1f}s")

    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)

    # Defuel
    print("\nSimulating defuel sequence...")
    df_defuel = simulate_defuel(tanks, all_tables, n_samples=1000, debug=True)
    defuel_path = data_dir / "defuel_sequence.mat"
    save_sequence_mat(df_defuel, str(defuel_path), debug=True)
    df_defuel.to_csv(data_dir / "defuel_sequence.csv", index=False)

    # Refuel
    print("\nSimulating refuel sequence...")
    df_refuel = simulate_refuel(tanks, all_tables, n_samples=800, debug=True)
    refuel_path = data_dir / "refuel_sequence.mat"
    save_sequence_mat(df_refuel, str(refuel_path), debug=True)
    df_refuel.to_csv(data_dir / "refuel_sequence.csv", index=False)

    print("\nDone. Files saved to data/")
