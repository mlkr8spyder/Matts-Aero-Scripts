"""
Capacitance-based fuel gauging simulation model.

Models the full measurement chain:
  Physical fuel → Probe capacitance → Height reading → Table lookup → Volume →
  Density × Volume → Weight

Includes configurable error injection at each stage for validation testing.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from .tank_geometry import (
    Tank, Probe, build_tank_system, fuel_volume_tilted_rect,
    fuel_height_at_point, wetted_height_on_probe, IN3_PER_GALLON,
)


# ---------------------------------------------------------------------------
# Fuel properties
# ---------------------------------------------------------------------------

@dataclass
class FuelProperties:
    """
    Fuel dielectric and density properties, with optional temperature
    compensation.

    Physical background
    -------------------
    In a capacitance fuel gauging system, the capacitance of a wetted probe
    is proportional to the dielectric constant (κ) of the fuel. The
    electronics measure κ directly on a compensator element. The density
    (ρ) of the fuel is not measured directly — instead it is *inferred*
    from κ via a calibrated relationship:

        ρ(κ) = a · κ + b    [lb/gal]        (1)

    This works because both κ and ρ of a hydrocarbon fuel track with
    temperature and composition in a consistent, monotonic way: denser
    fuel has more polarizable molecules per unit volume, giving a higher
    κ. The linear coefficients (a, b) are determined by calibrating
    against two or more (κ, ρ) reference points for the target fuel grade.

    Temperature compensation
    ------------------------
    Both κ and ρ decrease as temperature rises (the fuel expands). For
    Jet-A:

        dρ/dT ≈ -0.0035 lb/gal per °F
        dκ/dT ≈ -0.0011 per °F

    If the measured κ carries temperature information already (same
    element, same fuel bath), equation (1) *implicitly* compensates for
    temperature. However, some systems publish a temperature-explicit
    model:

        ρ(κ, T) = a · κ + b + c · (T - T_ref)    (2)

    with c small and near-zero if (a, b) were calibrated against κ over
    temperature. This class supports both forms — set
    ``enable_temperature_term`` to include the explicit c term.
    """
    density_lab_lb_per_gal: float = 6.71        # Lab-measured ground truth
    dielectric_air: float = 1.0
    dielectric_fuel_nominal: float = 2.05       # Jet-A at 60°F

    # Density-dielectric linear model: rho(lb/gal) = a * kappa + b
    # Calibrated so that rho(2.05) = 6.71 lb/gal, rho(1.90) = 6.01 lb/gal
    density_model_a: float = 4.667              # slope (lb/gal per unit kappa)
    density_model_b: float = -2.857             # intercept (lb/gal)

    # Temperature compensation (optional explicit term)
    reference_temp_F: float = 60.0              # reference temperature for calibration
    density_temp_coef: float = -0.0035          # dρ/dT (lb/gal per °F)
    dielectric_temp_coef: float = -0.0011       # dκ/dT (per °F)
    enable_temperature_term: bool = False       # add explicit c·(T-Tref) term

    def density_from_dielectric(self, kappa: float,
                                temperature_F: Optional[float] = None) -> float:
        """
        Compute fuel density from the measured dielectric constant.

        Parameters
        ----------
        kappa : float
            Dielectric constant as measured by the compensator element.
        temperature_F : float, optional
            Fuel temperature in °F. Only used when
            ``enable_temperature_term`` is True; otherwise κ is assumed to
            already carry the temperature information.

        Returns
        -------
        density : float
            Density in lb/gal.
        """
        rho = self.density_model_a * kappa + self.density_model_b
        if self.enable_temperature_term and temperature_F is not None:
            rho += self.density_temp_coef * (temperature_F - self.reference_temp_F)
        return rho

    def dielectric_at_temperature(self, kappa_ref: float,
                                  temperature_F: float) -> float:
        """
        Predict the dielectric constant at a given temperature, starting
        from a reference value at ``reference_temp_F``. Useful for
        generating synthetic sensor readings.
        """
        return kappa_ref + self.dielectric_temp_coef * (temperature_F - self.reference_temp_F)

    def density_at_temperature(self, rho_ref: float,
                               temperature_F: float) -> float:
        """
        Predict the true fuel density at a given temperature, starting
        from a reference value at ``reference_temp_F``.
        """
        return rho_ref + self.density_temp_coef * (temperature_F - self.reference_temp_F)

    @property
    def density_nominal(self) -> float:
        return self.density_from_dielectric(self.dielectric_fuel_nominal)


# ---------------------------------------------------------------------------
# Error injection configuration
# ---------------------------------------------------------------------------

@dataclass
class ErrorConfig:
    """Configuration for injected error sources."""
    # Density bias: system reports density this fraction higher than truth
    density_bias_fraction: float = 0.003        # 0.3% high

    # Dielectric temperature drift: sinusoidal drift in dielectric constant
    dielectric_drift_amplitude: float = 0.005   # ±0.5% of nominal kappa
    dielectric_drift_period_samples: int = 500  # period in sample counts

    # Per-tank probe height errors
    # T2 nonlinearity: parabolic error peaking at 40-60% fill
    t2_probe_nonlin_amplitude: float = 0.15     # ±0.15 inches at peak

    # T3 blend zone step error
    t3_blend_step_error: float = 0.08           # inches discontinuity

    # T5 pseudo projection amplified error at high pitch
    t5_pitch_error_gain: float = 0.02           # extra inches per degree above 3°

    # Table quantization (H-V table step artifacts)
    table_quantization_noise_in3: float = 0.002  # fraction of max volume

    # General probe measurement noise (random, per reading)
    probe_noise_std_in: float = 0.02            # inches, 1-sigma

    # Enable/disable individual errors
    enable_density_bias: bool = True
    enable_dielectric_drift: bool = True
    enable_t2_nonlinearity: bool = True
    enable_t3_blend_step: bool = True
    enable_t5_pitch_amplification: bool = True
    enable_table_quantization: bool = True
    enable_probe_noise: bool = True


# ---------------------------------------------------------------------------
# Table interpolation engine
# ---------------------------------------------------------------------------

class TableInterpolator:
    """
    Bilinear interpolation across pitch/roll, linear in height.

    Given a set of H-V tables indexed by (pitch, roll), interpolates:
    1. Find the 4 surrounding tables for the given pitch/roll
    2. Bilinear blend the tables
    3. Linear interpolation on height within the blended table
    """

    def __init__(self, all_tables: dict, tank_id: int):
        self.pitch_range = np.array(all_tables['pitch_range'])
        self.roll_range = np.array(all_tables['roll_range'])
        self.tank_data = all_tables['tanks'][tank_id]
        self.tables = self.tank_data['tables']

    def lookup_volume(self, height_rel: float, pitch_deg: float,
                      roll_deg: float) -> float:
        """
        Look up volume for a given probe height and attitude.

        Parameters
        ----------
        height_rel : float
            Probe height relative to probe base (inches).
        pitch_deg, roll_deg : float
            Aircraft attitude.

        Returns
        -------
        volume_in3 : float
        """
        # Find surrounding pitch indices
        pi_lo, pi_hi, pw = self._interp_weights(self.pitch_range, pitch_deg)
        ri_lo, ri_hi, rw = self._interp_weights(self.roll_range, roll_deg)

        # Get volumes from 4 surrounding tables
        v00 = self._table_height_lookup(pi_lo, ri_lo, height_rel)
        v01 = self._table_height_lookup(pi_lo, ri_hi, height_rel)
        v10 = self._table_height_lookup(pi_hi, ri_lo, height_rel)
        v11 = self._table_height_lookup(pi_hi, ri_hi, height_rel)

        # Bilinear interpolation
        v0 = v00 * (1 - rw) + v01 * rw
        v1 = v10 * (1 - rw) + v11 * rw
        volume = v0 * (1 - pw) + v1 * pw

        return max(0.0, volume)

    def _interp_weights(self, axis: np.ndarray, value: float):
        """Find bracketing indices and interpolation weight."""
        value = np.clip(value, axis[0], axis[-1])
        idx = np.searchsorted(axis, value, side='right') - 1
        idx = np.clip(idx, 0, len(axis) - 2)
        lo = idx
        hi = idx + 1
        span = axis[hi] - axis[lo]
        if span < 1e-12:
            w = 0.0
        else:
            w = (value - axis[lo]) / span
        return lo, hi, w

    def _table_height_lookup(self, pi: int, ri: int, height_rel: float) -> float:
        """Linear interpolation on height within one table."""
        table = self.tables[pi][ri]
        heights = table['heights_rel']
        volumes = table['volumes_in3']

        if height_rel <= heights[0]:
            return volumes[0]
        if height_rel >= heights[-1]:
            return volumes[-1]

        idx = np.searchsorted(heights, height_rel, side='right') - 1
        idx = np.clip(idx, 0, len(heights) - 2)

        h_lo, h_hi = heights[idx], heights[idx + 1]
        v_lo, v_hi = volumes[idx], volumes[idx + 1]

        if abs(h_hi - h_lo) < 1e-12:
            return v_lo

        t = (height_rel - h_lo) / (h_hi - h_lo)
        return v_lo + t * (v_hi - v_lo)


# ---------------------------------------------------------------------------
# Gauging system model
# ---------------------------------------------------------------------------

class GaugingSystem:
    """
    Full capacitance-based fuel quantity indication system.

    Models the measurement chain from true fuel state to indicated weight,
    with configurable error injection.
    """

    def __init__(self, all_tables: dict, tanks: dict = None,
                 fuel_props: FuelProperties = None,
                 error_config: ErrorConfig = None):
        if tanks is None:
            tanks = build_tank_system()
        if fuel_props is None:
            fuel_props = FuelProperties()
        if error_config is None:
            error_config = ErrorConfig()

        self.tanks = tanks
        self.fuel_props = fuel_props
        self.error_config = error_config
        self.interpolators = {
            tid: TableInterpolator(all_tables, tid) for tid in tanks.keys()
        }
        self._sample_counter = 0
        self._rng = np.random.default_rng(42)

    def indicate_single_tank(self, tank_id: int,
                             true_fuel_height_at_ref: float,
                             pitch_deg: float, roll_deg: float) -> dict:
        """
        Simulate the full gauging measurement for one tank.

        Parameters
        ----------
        tank_id : int
        true_fuel_height_at_ref : float
            True fuel surface WL at the tank's reference point (probe location).
        pitch_deg, roll_deg : float

        Returns
        -------
        dict with:
            probe_height_raw : raw probe reading (inches, relative)
            probe_height_corrected : after error injection
            indicated_volume_in3 : volume from table lookup
            indicated_volume_gal : gallons
            true_volume_in3 : actual volume (for comparison)
            errors : dict of individual error contributions
        """
        tank = self.tanks[tank_id]
        ec = self.error_config
        errors = {}

        # Step 1: True volume (ground truth)
        true_vol = fuel_volume_tilted_rect(
            tank, true_fuel_height_at_ref, pitch_deg, roll_deg
        )

        # Step 2: True probe height reading
        if tank.probe_type == "real":
            probe = tank.probes[0]
            fuel_wl_at_probe = fuel_height_at_point(
                true_fuel_height_at_ref, tank.center_fs, tank.center_bl,
                probe.center_fs, probe.center_bl, pitch_deg, roll_deg
            )
            raw_height = wetted_height_on_probe(probe, fuel_wl_at_probe)

        elif tank.probe_type == "real_pseudo_combo":
            # Tank 3: two probes with blend
            lower = tank.probes[0]
            upper = tank.probes[1]

            fuel_wl_at_lower = fuel_height_at_point(
                true_fuel_height_at_ref, tank.center_fs, tank.center_bl,
                lower.center_fs, lower.center_bl, pitch_deg, roll_deg
            )
            fuel_wl_at_upper = fuel_height_at_point(
                true_fuel_height_at_ref, tank.center_fs, tank.center_bl,
                upper.center_fs, upper.center_bl, pitch_deg, roll_deg
            )

            h_lower = wetted_height_on_probe(lower, fuel_wl_at_lower)
            h_upper = wetted_height_on_probe(upper, fuel_wl_at_upper)

            # Convert to WL for blending
            wl_lower = lower.base_wl + h_lower
            wl_upper = upper.base_wl + h_upper

            # Blend zone: WL 90 to 92
            blend_lo = 90.0
            blend_hi = 92.0

            if fuel_wl_at_lower < blend_lo:
                # Below blend zone — use lower probe only
                raw_height = h_lower
                # Height relative to lower probe base
            elif fuel_wl_at_lower > blend_hi:
                # Above blend zone — use upper probe only
                # Convert to height relative to lower probe base for table lookup
                raw_height = wl_upper - lower.base_wl
            else:
                # In blend zone
                w_upper = (fuel_wl_at_lower - blend_lo) / (blend_hi - blend_lo)
                w_lower = 1.0 - w_upper
                blended_wl = w_lower * wl_lower + w_upper * wl_upper
                raw_height = blended_wl - lower.base_wl

                # Inject blend step error
                if ec.enable_t3_blend_step:
                    # Step error at blend boundaries
                    blend_frac = (fuel_wl_at_lower - blend_lo) / (blend_hi - blend_lo)
                    step = ec.t3_blend_step_error * np.sin(np.pi * blend_frac)
                    raw_height += step
                    errors['blend_step'] = step

        elif tank.probe_type == "pure_pseudo":
            # Tank 5: project from source tank (Tank 3) probes
            source_tank = self.tanks[tank.pseudo_source_tank_id]
            dx = tank.pseudo_ref_fs - source_tank.center_fs
            dy = tank.pseudo_ref_bl - source_tank.center_bl

            # Project fuel plane to pseudo location
            projected_wl = true_fuel_height_at_ref + \
                dx * np.tan(np.radians(pitch_deg)) + \
                dy * np.tan(np.radians(roll_deg))

            # Clamp to tank bounds
            projected_wl = np.clip(projected_wl, tank.wl_min, tank.wl_max)
            raw_height = projected_wl - tank.wl_min

            # Inject pitch-amplified error for T5
            if ec.enable_t5_pitch_amplification and abs(pitch_deg) > 3.0:
                extra = ec.t5_pitch_error_gain * (abs(pitch_deg) - 3.0) * np.sign(pitch_deg)
                raw_height += extra * dx * 0.01  # scale by distance
                errors['pitch_amplification'] = extra * dx * 0.01

        else:
            raw_height = 0.0

        # Step 3: Add probe measurement noise
        noise = 0.0
        if ec.enable_probe_noise:
            noise = self._rng.normal(0, ec.probe_noise_std_in)
            raw_height += noise
            errors['probe_noise'] = noise

        # Step 4: Tank-specific probe errors
        if tank_id == 2 and ec.enable_t2_nonlinearity:
            # Parabolic error peaking at 40-60% fill
            fill_frac = raw_height / max(tank.probes[0].active_length, 0.1)
            fill_frac = np.clip(fill_frac, 0, 1)
            nonlin = ec.t2_probe_nonlin_amplitude * \
                     (-4.0 * (fill_frac - 0.5)**2 + 1.0)
            # Peak at fill_frac=0.5, zero at 0 and 1
            nonlin = max(nonlin, 0.0)  # only positive errors at peak region
            raw_height += nonlin
            errors['t2_nonlinearity'] = nonlin

        # Ensure non-negative
        raw_height = max(0.0, raw_height)

        # Step 5: Table lookup for volume
        interp = self.interpolators[tank_id]
        indicated_vol_in3 = interp.lookup_volume(raw_height, pitch_deg, roll_deg)

        # Step 6: Add table quantization noise
        if ec.enable_table_quantization:
            quant_noise = self._rng.uniform(-1, 1) * \
                          ec.table_quantization_noise_in3 * tank.gross_volume_in3
            indicated_vol_in3 += quant_noise
            indicated_vol_in3 = max(0.0, indicated_vol_in3)
            errors['table_quantization'] = quant_noise

        return {
            'probe_height_raw': raw_height,
            'indicated_volume_in3': indicated_vol_in3,
            'indicated_volume_gal': indicated_vol_in3 / IN3_PER_GALLON,
            'true_volume_in3': true_vol,
            'true_volume_gal': true_vol / IN3_PER_GALLON,
            'volume_error_in3': indicated_vol_in3 - true_vol,
            'errors': errors,
        }

    def indicate_system(self, fuel_heights: dict,
                        pitch_deg: float, roll_deg: float,
                        sample_idx: int = 0) -> dict:
        """
        Compute full system indication for all tanks.

        Parameters
        ----------
        fuel_heights : dict
            {tank_id: fuel_surface_wl_at_ref} for each tank.
        pitch_deg, roll_deg : float
        sample_idx : int
            Sample counter for time-varying errors (dielectric drift).

        Returns
        -------
        dict with per-tank results and system totals.
        """
        ec = self.error_config
        fp = self.fuel_props
        self._sample_counter = sample_idx

        # Compute system density with errors
        kappa_true = fp.dielectric_fuel_nominal
        kappa_system = kappa_true

        # Dielectric drift
        drift = 0.0
        if ec.enable_dielectric_drift:
            phase = 2.0 * np.pi * sample_idx / ec.dielectric_drift_period_samples
            drift = ec.dielectric_drift_amplitude * np.sin(phase)
            kappa_system += drift

        density_system = fp.density_from_dielectric(kappa_system)

        # Density bias
        if ec.enable_density_bias:
            density_system *= (1.0 + ec.density_bias_fraction)

        density_lab = fp.density_lab_lb_per_gal

        # Per-tank indication
        tank_results = {}
        total_indicated_vol_gal = 0.0
        total_true_vol_gal = 0.0

        for tid in sorted(self.tanks.keys()):
            if tid in fuel_heights:
                result = self.indicate_single_tank(
                    tid, fuel_heights[tid], pitch_deg, roll_deg
                )
            else:
                result = {
                    'probe_height_raw': 0.0,
                    'indicated_volume_in3': 0.0,
                    'indicated_volume_gal': 0.0,
                    'true_volume_in3': 0.0,
                    'true_volume_gal': 0.0,
                    'volume_error_in3': 0.0,
                    'errors': {},
                }

            # Compute indicated weight = indicated_volume_gal × density_system
            result['indicated_weight_lb'] = result['indicated_volume_gal'] * density_system
            result['true_weight_lb'] = result['true_volume_gal'] * density_lab

            total_indicated_vol_gal += result['indicated_volume_gal']
            total_true_vol_gal += result['true_volume_gal']

            tank_results[tid] = result

        total_indicated_weight = total_indicated_vol_gal * density_system
        total_true_weight = total_true_vol_gal * density_lab

        return {
            'tanks': tank_results,
            'density_system': density_system,
            'density_lab': density_lab,
            'density_error': density_system - density_lab,
            'dielectric_drift': drift,
            'total_indicated_volume_gal': total_indicated_vol_gal,
            'total_true_volume_gal': total_true_vol_gal,
            'total_indicated_weight_lb': total_indicated_weight,
            'total_true_weight_lb': total_true_weight,
            'total_weight_error_lb': total_indicated_weight - total_true_weight,
            'pitch_deg': pitch_deg,
            'roll_deg': roll_deg,
        }


if __name__ == "__main__":
    from .hv_table_generator import generate_all_tables

    print("Building system...")
    tanks = build_tank_system()
    all_tables = generate_all_tables(tanks)

    print("Creating gauging system...")
    gs = GaugingSystem(all_tables, tanks)

    # Test at level, half-full
    fuel_heights = {}
    for tid, tank in tanks.items():
        fuel_heights[tid] = tank.wl_min + tank.height_wl * 0.5  # 50% fill

    result = gs.indicate_system(fuel_heights, pitch_deg=0.0, roll_deg=0.0)

    print(f"\nSystem at 50% fill, level attitude:")
    print(f"  Density: system={result['density_system']:.4f}, "
          f"lab={result['density_lab']:.4f}, "
          f"error={result['density_error']:.4f} lb/gal")
    print(f"  Total volume: indicated={result['total_indicated_volume_gal']:.2f}, "
          f"true={result['total_true_volume_gal']:.2f} gal")
    print(f"  Total weight: indicated={result['total_indicated_weight_lb']:.2f}, "
          f"true={result['total_true_weight_lb']:.2f} lb")
    print(f"  Weight error: {result['total_weight_error_lb']:.2f} lb")

    print(f"\nPer-tank breakdown:")
    for tid in sorted(result['tanks'].keys()):
        tr = result['tanks'][tid]
        print(f"  T{tid}: vol_err={tr['volume_error_in3']:.1f} in³, "
              f"wt_err={tr['indicated_weight_lb'] - tr['true_weight_lb']:.2f} lb, "
              f"errors={list(tr['errors'].keys())}")
