"""
Residual computation and error statistics for gauging analysis.

Compares indicated (gauging system) values against reference (scale)
values to compute residuals, error statistics, and binned breakdowns.

The scale provides sparse checkpoints (only at weigh events), so indicated
values at non-checkpoint times are compared against linearly interpolated
scale fuel weights.

Usage:
    from analysis.comparison import compute_residuals, compute_error_statistics

    residuals = compute_residuals(test_dataset)
    stats = compute_error_statistics(residuals)
"""

import numpy as np
from typing import Optional

from .importers.base import TestDataset


def compute_residuals(dataset: TestDataset,
                      interpolate_scale: bool = True) -> dict:
    """
    Compute indicated-minus-actual residuals for a test sequence.

    At scale checkpoint times, the reference weight is:
        actual_fuel = scale_gross_weight - dry_weight

    Between checkpoints, the reference is linearly interpolated if
    ``interpolate_scale`` is True, otherwise only checkpoint rows are
    included.

    Parameters
    ----------
    dataset : TestDataset
        Must have at least 2 scale checkpoints for interpolation.
    interpolate_scale : bool
        If True, interpolate scale fuel weight for all timesteps.

    Returns
    -------
    dict with:
        time_s : np.ndarray — timestamps
        pitch_deg : np.ndarray
        roll_deg : np.ndarray
        indicated_total_lb : np.ndarray — total indicated fuel weight
        actual_total_lb : np.ndarray — reference fuel weight (from scale)
        residual_total_lb : np.ndarray — indicated minus actual
        indicated_per_tank : dict of {tank_id: np.ndarray}
        density_system : np.ndarray — system-reported density
        metadata : dict — per-record metadata lists
    """
    records = dataset.records
    n = len(records)

    # Extract scale checkpoints
    cp_times = []
    cp_fuel_wts = []
    for r in records:
        if r.scale_weight_lb is not None and r.dry_weight_lb is not None:
            cp_times.append(r.time_s)
            cp_fuel_wts.append(r.scale_weight_lb - r.dry_weight_lb)

    cp_times = np.array(cp_times)
    cp_fuel_wts = np.array(cp_fuel_wts)

    if len(cp_times) < 2 and interpolate_scale:
        interpolate_scale = False

    # Build arrays
    time_s = np.array([r.time_s for r in records])
    pitch_deg = np.array([r.pitch_deg for r in records])
    roll_deg = np.array([r.roll_deg for r in records])
    density_system = np.array([
        r.density_system if r.density_system is not None else np.nan
        for r in records
    ])

    indicated_total = np.array([r.total_indicated_weight for r in records])

    # Per-tank indicated weights
    tank_ids = dataset.tank_ids
    indicated_per_tank = {}
    for tid in tank_ids:
        indicated_per_tank[tid] = np.array([
            r.indicated_weights.get(tid, 0.0) for r in records
        ])

    # Compute actual (reference) fuel weight
    if interpolate_scale:
        actual_total = np.interp(time_s, cp_times, cp_fuel_wts)
    else:
        # Only checkpoint rows
        actual_total = np.full(n, np.nan)
        for r in records:
            if r.scale_weight_lb is not None and r.dry_weight_lb is not None:
                idx = int(r.time_s)  # assumes time_s is sample index
                if 0 <= idx < n:
                    actual_total[idx] = r.scale_weight_lb - r.dry_weight_lb

    residual_total = indicated_total - actual_total

    return {
        'time_s': time_s,
        'pitch_deg': pitch_deg,
        'roll_deg': roll_deg,
        'indicated_total_lb': indicated_total,
        'actual_total_lb': actual_total,
        'residual_total_lb': residual_total,
        'indicated_per_tank': indicated_per_tank,
        'density_system': density_system,
        'tank_ids': tank_ids,
    }


def compute_error_statistics(residuals: dict,
                             n_bins: int = 10) -> dict:
    """
    Compute summary statistics and binned error breakdowns.

    Parameters
    ----------
    residuals : dict
        Output from compute_residuals().
    n_bins : int
        Number of fuel level bins for the binned breakdown.

    Returns
    -------
    dict with:
        mean_error_lb : float
        std_error_lb : float
        max_error_lb : float — max absolute error
        rms_error_lb : float
        percentiles : dict — {50, 90, 95, 99} percentiles of abs error
        binned : dict — fuel-level-binned statistics
            bin_edges : np.ndarray (n_bins+1 edges)
            bin_centers : np.ndarray
            bin_mean : np.ndarray
            bin_std : np.ndarray
            bin_max : np.ndarray
            bin_count : np.ndarray
    """
    residual = residuals['residual_total_lb']
    actual = residuals['actual_total_lb']

    # Filter out NaN
    valid = ~np.isnan(residual) & ~np.isnan(actual)
    r = residual[valid]
    a = actual[valid]

    abs_r = np.abs(r)

    stats = {
        'mean_error_lb': float(np.mean(r)),
        'std_error_lb': float(np.std(r)),
        'max_error_lb': float(np.max(abs_r)) if len(abs_r) > 0 else 0.0,
        'rms_error_lb': float(np.sqrt(np.mean(r ** 2))),
        'percentiles': {
            50: float(np.percentile(abs_r, 50)),
            90: float(np.percentile(abs_r, 90)),
            95: float(np.percentile(abs_r, 95)),
            99: float(np.percentile(abs_r, 99)),
        },
    }

    # Binned breakdown by fuel level
    if len(a) > 0:
        bin_edges = np.linspace(a.min(), a.max(), n_bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        bin_mean = np.zeros(n_bins)
        bin_std = np.zeros(n_bins)
        bin_max = np.zeros(n_bins)
        bin_count = np.zeros(n_bins, dtype=int)

        bin_idx = np.digitize(a, bin_edges) - 1
        bin_idx = np.clip(bin_idx, 0, n_bins - 1)

        for b in range(n_bins):
            mask = bin_idx == b
            if np.any(mask):
                bin_r = r[mask]
                bin_mean[b] = np.mean(bin_r)
                bin_std[b] = np.std(bin_r)
                bin_max[b] = np.max(np.abs(bin_r))
                bin_count[b] = int(np.sum(mask))

        stats['binned'] = {
            'bin_edges': bin_edges,
            'bin_centers': bin_centers,
            'bin_mean': bin_mean,
            'bin_std': bin_std,
            'bin_max': bin_max,
            'bin_count': bin_count,
        }
    else:
        stats['binned'] = None

    return stats
