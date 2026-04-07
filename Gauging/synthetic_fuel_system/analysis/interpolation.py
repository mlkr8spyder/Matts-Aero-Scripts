"""
Variable-length H-V table interpolator.

Performs bilinear interpolation across pitch/roll attitudes, then linear
interpolation on height within the blended result. Unlike the src/
TableInterpolator which uses a regular grid with indexed access, this
interpolator works with the canonical TankData container where tables
are stored as a dict of (pitch, roll) -> HVTable with variable-length
height arrays.

Each table uses np.interp on its own breakpoints, so tables at different
attitudes can have different numbers of points (the MM1D convention).

Usage:
    from analysis.interpolation import HVInterpolator

    interp = HVInterpolator(tank_data)
    volume = interp.lookup(height=5.0, pitch_deg=1.5, roll_deg=-2.0)
"""

import numpy as np
from typing import Optional

from .importers.base import TankData, HVTable


class HVInterpolator:
    """
    Bilinear pitch/roll + linear height interpolator for variable-length
    H-V tables.

    For a query at (pitch, roll, height):
      1. Find the 4 surrounding tables on the pitch/roll grid.
      2. Interpolate each table's H-V curve at the query height using
         np.interp (each table has its own breakpoints).
      3. Bilinear-blend the 4 volume results.

    Supports irregular attitude grids — the pitch and roll axes are
    extracted from the available table keys.
    """

    def __init__(self, tank_data: TankData):
        """
        Parameters
        ----------
        tank_data : TankData
            Must have at least one table. Pitch and roll axes are
            extracted from the table keys.
        """
        self.tank_data = tank_data
        self._pitch_axis = tank_data.pitch_values
        self._roll_axis = tank_data.roll_values

        if len(self._pitch_axis) == 0 or len(self._roll_axis) == 0:
            raise ValueError(f"Tank {tank_data.tank_id} has no tables to interpolate")

        # Build a lookup grid: (pitch, roll) -> HVTable
        # For missing grid points, store None (sparse grids)
        self._grid = {}
        for (p, r), table in tank_data.tables.items():
            self._grid[(p, r)] = table

    def lookup(self, height: float, pitch_deg: float, roll_deg: float) -> float:
        """
        Interpolate volume for a given probe height and attitude.

        Parameters
        ----------
        height : float
            Probe height in inches (relative to probe base).
        pitch_deg : float
            Aircraft pitch in degrees.
        roll_deg : float
            Aircraft roll in degrees.

        Returns
        -------
        volume : float
            Interpolated volume in cubic inches.
        """
        # Find surrounding pitch/roll indices and weights
        pi_lo, pi_hi, pw = self._bracket(self._pitch_axis, pitch_deg)
        ri_lo, ri_hi, rw = self._bracket(self._roll_axis, roll_deg)

        p_lo = self._pitch_axis[pi_lo]
        p_hi = self._pitch_axis[pi_hi]
        r_lo = self._roll_axis[ri_lo]
        r_hi = self._roll_axis[ri_hi]

        # Interpolate height on each of the 4 corner tables
        v00 = self._height_lookup(p_lo, r_lo, height)
        v01 = self._height_lookup(p_lo, r_hi, height)
        v10 = self._height_lookup(p_hi, r_lo, height)
        v11 = self._height_lookup(p_hi, r_hi, height)

        # Bilinear blend
        v0 = v00 * (1 - rw) + v01 * rw
        v1 = v10 * (1 - rw) + v11 * rw
        volume = v0 * (1 - pw) + v1 * pw

        return max(0.0, volume)

    def lookup_batch(self, heights: np.ndarray, pitch_deg: np.ndarray,
                     roll_deg: np.ndarray) -> np.ndarray:
        """
        Vectorized lookup for arrays of (height, pitch, roll).

        Parameters
        ----------
        heights, pitch_deg, roll_deg : np.ndarray
            Equal-length arrays of query points.

        Returns
        -------
        volumes : np.ndarray
            Interpolated volumes in cubic inches.
        """
        n = len(heights)
        volumes = np.empty(n)
        for i in range(n):
            volumes[i] = self.lookup(heights[i], pitch_deg[i], roll_deg[i])
        return volumes

    def _height_lookup(self, pitch: float, roll: float, height: float) -> float:
        """
        Linearly interpolate volume from height on a single table.

        Uses np.interp with clamp-to-boundary behavior (no extrapolation),
        matching the Simulink LUT configuration.
        """
        table = self._grid.get((pitch, roll))
        if table is None:
            # Sparse grid — find nearest available table
            table = self._nearest_table(pitch, roll)
            if table is None:
                return 0.0

        # np.interp clamps to the first/last value outside the range
        return float(np.interp(height, table.heights, table.volumes))

    def _nearest_table(self, pitch: float, roll: float) -> Optional[HVTable]:
        """Fall back to the nearest available table for sparse grids."""
        best_dist = float('inf')
        best_table = None
        for (p, r), table in self._grid.items():
            dist = (p - pitch) ** 2 + (r - roll) ** 2
            if dist < best_dist:
                best_dist = dist
                best_table = table
        return best_table

    @staticmethod
    def _bracket(axis: np.ndarray, value: float):
        """
        Find the bracketing indices and fractional weight on a sorted axis.

        Returns (lo_idx, hi_idx, weight) where weight=0 means exactly on
        lo, weight=1 means exactly on hi.
        """
        value = np.clip(value, axis[0], axis[-1])
        idx = np.searchsorted(axis, value, side='right') - 1
        idx = np.clip(idx, 0, len(axis) - 2)
        lo = int(idx)
        hi = lo + 1
        span = axis[hi] - axis[lo]
        if span < 1e-12:
            w = 0.0
        else:
            w = (value - axis[lo]) / span
        return lo, hi, float(w)
