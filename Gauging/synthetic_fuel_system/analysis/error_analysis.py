"""
Error decomposition and sensitivity analysis for fuel gauging systems.

Breaks down total gauging error into:
  - Density error contribution (wrong density applied to correct volume)
  - Volume error contribution (correct density applied to wrong volume)
  - Attitude sensitivity (how error varies with pitch/roll)
  - Fuel level sensitivity (how error varies with fuel quantity)

Usage:
    from analysis.error_analysis import (
        decompose_errors,
        attitude_sensitivity,
        fuel_level_sensitivity,
    )

    decomp = decompose_errors(residuals, density_lab=6.71)
    att_sens = attitude_sensitivity(residuals, pitch_bins=12, roll_bins=16)
    level_sens = fuel_level_sensitivity(residuals, n_bins=20)
"""

import numpy as np
from typing import Optional


def decompose_errors(residuals: dict,
                     density_lab: float = 6.71) -> dict:
    """
    Decompose total weight error into density and volume contributions.

    Total error = indicated_weight - actual_weight

    We can split this approximately:
        weight_error ≈ density_error_contribution + volume_error_contribution

    Where:
        density_error_contribution = (density_system - density_lab) * actual_volume_gal
        volume_error_contribution  = density_lab * (indicated_volume - actual_volume)_gal

    Since we don't always have per-tank actual volumes, we estimate
    actual_volume from actual_weight / density_lab.

    Parameters
    ----------
    residuals : dict
        Output from comparison.compute_residuals().
    density_lab : float
        True (lab-measured) fuel density in lb/gal.

    Returns
    -------
    dict with:
        density_error_lb : np.ndarray
            Weight error attributable to density measurement error.
        volume_error_lb : np.ndarray
            Weight error attributable to volume measurement error.
        total_error_lb : np.ndarray
            Total residual (sum of the two should approximate this).
        density_fraction : float
            Fraction of total RMS error from density.
        volume_fraction : float
            Fraction of total RMS error from volume.
        density_system : np.ndarray
    """
    indicated = residuals['indicated_total_lb']
    actual = residuals['actual_total_lb']
    density_sys = residuals['density_system']
    total_error = residuals['residual_total_lb']

    # Estimate actual volume from scale weight
    actual_volume_gal = actual / density_lab

    # Density contribution: if we had the right volume but wrong density
    density_error = (density_sys - density_lab) * actual_volume_gal

    # Volume contribution: everything else
    volume_error = total_error - density_error

    # RMS contributions
    valid = ~np.isnan(total_error) & ~np.isnan(density_error)
    if np.any(valid):
        rms_total = np.sqrt(np.mean(total_error[valid] ** 2))
        rms_density = np.sqrt(np.mean(density_error[valid] ** 2))
        rms_volume = np.sqrt(np.mean(volume_error[valid] ** 2))

        if rms_total > 0:
            # Use variance decomposition for fractions
            density_frac = rms_density ** 2 / (rms_density ** 2 + rms_volume ** 2)
            volume_frac = 1.0 - density_frac
        else:
            density_frac = 0.0
            volume_frac = 0.0
    else:
        density_frac = 0.0
        volume_frac = 0.0

    return {
        'density_error_lb': density_error,
        'volume_error_lb': volume_error,
        'total_error_lb': total_error,
        'density_fraction': density_frac,
        'volume_fraction': volume_frac,
        'density_system': density_sys,
    }


def attitude_sensitivity(residuals: dict,
                          pitch_bins: int = 12,
                          roll_bins: int = 16) -> dict:
    """
    Compute error statistics binned by pitch and roll attitude.

    Produces a 2D grid of mean absolute error indexed by (pitch, roll),
    suitable for heatmap visualization.

    Parameters
    ----------
    residuals : dict
        Output from comparison.compute_residuals().
    pitch_bins, roll_bins : int
        Number of bins for each axis.

    Returns
    -------
    dict with:
        pitch_edges : np.ndarray (pitch_bins+1)
        roll_edges : np.ndarray (roll_bins+1)
        pitch_centers : np.ndarray
        roll_centers : np.ndarray
        mean_abs_error : np.ndarray [pitch_bins x roll_bins]
            Mean absolute error in each bin. NaN where no data.
        count : np.ndarray [pitch_bins x roll_bins]
            Sample count in each bin.
        max_abs_error : np.ndarray [pitch_bins x roll_bins]
    """
    pitch = residuals['pitch_deg']
    roll = residuals['roll_deg']
    error = residuals['residual_total_lb']

    valid = ~np.isnan(error)
    pitch = pitch[valid]
    roll = roll[valid]
    error = error[valid]

    pitch_edges = np.linspace(pitch.min(), pitch.max(), pitch_bins + 1)
    roll_edges = np.linspace(roll.min(), roll.max(), roll_bins + 1)
    pitch_centers = (pitch_edges[:-1] + pitch_edges[1:]) / 2
    roll_centers = (roll_edges[:-1] + roll_edges[1:]) / 2

    mean_abs = np.full((pitch_bins, roll_bins), np.nan)
    max_abs = np.full((pitch_bins, roll_bins), np.nan)
    count = np.zeros((pitch_bins, roll_bins), dtype=int)

    pi_idx = np.digitize(pitch, pitch_edges) - 1
    ri_idx = np.digitize(roll, roll_edges) - 1
    pi_idx = np.clip(pi_idx, 0, pitch_bins - 1)
    ri_idx = np.clip(ri_idx, 0, roll_bins - 1)

    for pi in range(pitch_bins):
        for ri in range(roll_bins):
            mask = (pi_idx == pi) & (ri_idx == ri)
            if np.any(mask):
                bin_err = np.abs(error[mask])
                mean_abs[pi, ri] = np.mean(bin_err)
                max_abs[pi, ri] = np.max(bin_err)
                count[pi, ri] = int(np.sum(mask))

    return {
        'pitch_edges': pitch_edges,
        'roll_edges': roll_edges,
        'pitch_centers': pitch_centers,
        'roll_centers': roll_centers,
        'mean_abs_error': mean_abs,
        'max_abs_error': max_abs,
        'count': count,
    }


def fuel_level_sensitivity(residuals: dict,
                           n_bins: int = 20,
                           normalize: bool = False) -> dict:
    """
    Compute error statistics binned by fuel level.

    Parameters
    ----------
    residuals : dict
        Output from comparison.compute_residuals().
    n_bins : int
        Number of fuel level bins.
    normalize : bool
        If True, express error as percentage of fuel weight at each level.

    Returns
    -------
    dict with:
        bin_edges : np.ndarray
        bin_centers : np.ndarray
        mean_error : np.ndarray — signed mean error in each bin
        std_error : np.ndarray
        mean_abs_error : np.ndarray
        max_abs_error : np.ndarray
        count : np.ndarray
        normalized : bool — whether values are in percent
    """
    actual = residuals['actual_total_lb']
    error = residuals['residual_total_lb']

    valid = ~np.isnan(actual) & ~np.isnan(error)
    a = actual[valid]
    e = error[valid]

    bin_edges = np.linspace(a.min(), a.max(), n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    bin_idx = np.clip(np.digitize(a, bin_edges) - 1, 0, n_bins - 1)

    mean_err = np.zeros(n_bins)
    std_err = np.zeros(n_bins)
    mean_abs = np.zeros(n_bins)
    max_abs = np.zeros(n_bins)
    count = np.zeros(n_bins, dtype=int)

    for b in range(n_bins):
        mask = bin_idx == b
        if np.any(mask):
            bin_e = e[mask]
            mean_err[b] = np.mean(bin_e)
            std_err[b] = np.std(bin_e)
            mean_abs[b] = np.mean(np.abs(bin_e))
            max_abs[b] = np.max(np.abs(bin_e))
            count[b] = int(np.sum(mask))

            if normalize and bin_centers[b] > 0:
                mean_err[b] = mean_err[b] / bin_centers[b] * 100
                std_err[b] = std_err[b] / bin_centers[b] * 100
                mean_abs[b] = mean_abs[b] / bin_centers[b] * 100
                max_abs[b] = max_abs[b] / bin_centers[b] * 100

    return {
        'bin_edges': bin_edges,
        'bin_centers': bin_centers,
        'mean_error': mean_err,
        'std_error': std_err,
        'mean_abs_error': mean_abs,
        'max_abs_error': max_abs,
        'count': count,
        'normalized': normalize,
    }
