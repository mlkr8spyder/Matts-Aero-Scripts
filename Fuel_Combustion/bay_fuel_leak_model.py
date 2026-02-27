#!/usr/bin/env python3
"""
Bay Fuel Leak Model — Pool Formation, Vapor Concentration, Flammability,
and Confined Combustion Overpressure Analysis

Models fuel leaking into an adjacent bay with a drain hole. Computes the
transient pool buildup, equilibrium vapor-air mixture properties,
flammability assessment, MIE check, and — if the mixture is flammable —
the Adiabatic Isochoric Complete Combustion (AICC) overpressure using
Cantera with both n-dodecane and multi-component surrogate mechanisms.

Converted from MATLAB bay_fuel_leak_model.m with Cantera combustion added.

Usage:
    python bay_fuel_leak_model.py

Dependencies:
    numpy, scipy, matplotlib, cantera

Author:  [Your Name]
Date:    2026-02-24
"""

import numpy as np
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import warnings
import sys
import os

# ── Optional Cantera import ──────────────────────────────────────────────
try:
    import cantera as ct
    HAS_CANTERA = True
except ImportError:
    HAS_CANTERA = False
    warnings.warn(
        "Cantera not installed. Combustion overpressure analysis will be "
        "skipped. Install with: pip install cantera"
    )


# =========================================================================
#  PHYSICAL CONSTANTS
# =========================================================================
R_U     = 8.314          # Universal gas constant [J/(mol·K)]
G       = 9.80665        # Gravitational acceleration [m/s²]
P0      = 101325.0       # Sea-level standard pressure [Pa]
T0_STD  = 288.15         # Sea-level standard temperature [K]
L_RATE  = 0.0065         # ISA temperature lapse rate [K/m]
M_AIR   = 0.02897        # Molar mass of dry air [kg/mol]


# =========================================================================
#  FUEL PROPERTY FUNCTIONS  (USER-REPLACEABLE)
# =========================================================================
# Replace these with your own correlations.  All take temperature T [K].

# Molar mass of fuel vapor [kg/mol]
# Jet-A ≈ C₁₂H₂₃, MW ≈ 167 g/mol
M_FUEL = 0.167

def true_vapor_pressure(T):
    """True vapor pressure of Jet-A [Pa].  Antoine-type placeholder."""
    return np.exp(22.30 - 5765.0 / (T - 27.0))

def liquid_fuel_density(T):
    """Liquid Jet-A density [kg/m³].  Linear fit placeholder."""
    return 840.0 - 0.68 * (T - 273.15)

def liquid_fuel_viscosity(T):
    """Dynamic viscosity of liquid Jet-A [Pa·s]."""
    return 1.2e-3 * np.ones_like(np.atleast_1d(T)).squeeze()

def vapor_diffusivity(T, P):
    """Binary diffusion coefficient of fuel vapor in air [m²/s]."""
    return 6.0e-6 * (T / 298.0) ** 1.75 * (P0 / P)


# =========================================================================
#  ATMOSPHERIC MODEL
# =========================================================================
def ambient_pressure(h):
    """ISA ambient pressure [Pa] at altitude h [m]."""
    return P0 * (1.0 - L_RATE * h / T0_STD) ** (G / (287.058 * L_RATE))


# =========================================================================
#  MIE MODEL
# =========================================================================
# Stoichiometric volume fraction for C₁₂H₂₃ in air:
#   C₁₂H₂₃ + 17.75(O₂ + 3.76 N₂) → products
#   x_stoich = 1 / (1 + 17.75 × 4.76) ≈ 0.0118
X_STOICH = 0.0118
MIE_MIN_MJ = 0.25   # MIE at stoichiometric [mJ]

def mie_parabolic(x_fuel, lel, uel):
    """
    Approximate MIE [mJ] via log-parabolic model centred on stoichiometric.
    Returns np.inf outside the flammable range.
    """
    if x_fuel < lel or x_fuel > uel:
        return np.inf
    k = np.log10(100.0) / (X_STOICH - lel) ** 2
    log_mie = np.log10(MIE_MIN_MJ) + k * (x_fuel - X_STOICH) ** 2
    return 10.0 ** log_mie


# =========================================================================
#  FUEL VOLUME FOR FLAMMABILITY
# =========================================================================
def fuel_volume_for_flammability(T_C, alt_m, V_bay,
                                  LEL_SL_pct=0.6, UEL_SL_pct=4.7):
    """
    Compute the volume of liquid fuel that must fully evaporate into a sealed
    bay to bring the vapor concentration to the LEL and UEL boundaries.

    This gives the minimum liquid fuel volume to create a flammable mixture
    and the maximum before exceeding the upper limit.

    Parameters
    ----------
    T_C        : float — bay temperature [°C]
    alt_m      : float — altitude [m]
    V_bay      : float — total bay volume [m³]
    LEL_SL_pct : float — lower explosive limit at sea level [vol %]
    UEL_SL_pct : float — upper explosive limit at sea level [vol %]

    Returns
    -------
    dict with keys:
        T_K, P_amb, rho_liq, LEL_alt, UEL_alt,
        n_fuel_LEL, m_fuel_LEL, V_liq_LEL_mL,
        n_fuel_UEL, m_fuel_UEL, V_liq_UEL_mL,
        n_fuel_stoich, m_fuel_stoich, V_liq_stoich_mL
    """
    T_K    = T_C + 273.15
    P_amb  = ambient_pressure(alt_m)
    rho_liq = liquid_fuel_density(T_K)

    # Altitude-corrected flammability limits (constant partial-pressure model)
    LEL_alt = (LEL_SL_pct / 100.0) * P0 / P_amb
    UEL_alt = (UEL_SL_pct / 100.0) * P0 / P_amb

    results = {
        'T_K': T_K, 'T_C': T_C, 'alt_m': alt_m,
        'P_amb': P_amb, 'rho_liq': rho_liq,
        'LEL_alt': LEL_alt, 'UEL_alt': UEL_alt,
    }

    # For each threshold (LEL, stoichiometric, UEL), compute the liquid fuel
    # volume whose complete evaporation yields that mole fraction.
    #
    # In a sealed bay of volume V_bay at pressure P_amb and temperature T:
    #   n_total = P_amb * V_bay / (R_U * T)     (total moles of gas)
    #   X_fuel  = n_fuel / n_total
    #   => n_fuel = X_fuel * n_total
    #   => m_fuel = n_fuel * M_FUEL
    #   => V_liquid = m_fuel / rho_liq
    #
    # Note: this is conservative (upper bound) because it assumes the gas
    # volume equals V_bay.  In reality the liquid pool occupies some volume,
    # but the pool volume is negligible compared to the bay for these
    # concentrations.

    n_total = P_amb * V_bay / (R_U * T_K)

    for tag, X_target in [('LEL', LEL_alt), ('stoich', X_STOICH),
                           ('UEL', UEL_alt)]:
        n_fuel  = X_target * n_total
        m_fuel  = n_fuel * M_FUEL
        V_liq   = m_fuel / rho_liq
        results[f'n_fuel_{tag}']      = n_fuel
        results[f'm_fuel_{tag}']      = m_fuel
        results[f'V_liq_{tag}_mL']    = V_liq * 1e6   # m³ → mL
        results[f'V_liq_{tag}_L']     = V_liq * 1e3   # m³ → L

    return results


# =========================================================================
#  BAY ODE SYSTEM
# =========================================================================
def bay_ode(t, y, params):
    """
    Governing ODEs for pool volume and vapor mass in the bay.

    State vector:
        y[0] = V_pool  [m³]  — liquid pool volume
        y[1] = m_vap   [kg]  — fuel vapor mass in bay gas space

    Returns dy/dt.
    """
    Q_leak   = params['Q_leak']
    Cd       = params['Cd_drain']
    A_drain  = params['A_drain']
    A_floor  = params['A_floor']
    bay_h    = params['bay_height']
    k_m      = params['k_m']
    C_sat    = params['C_sat']
    rho_liq  = params['rho_liq']
    V_bay    = params['V_bay']
    Q_vent   = params['Q_vent']

    V_pool = max(y[0], 0.0)
    m_vap  = max(y[1], 0.0)

    h_pool = V_pool / A_floor
    V_gas  = max(V_bay - V_pool, 1e-12)
    C_bay  = m_vap / V_gas

    # Drain outflow — sharp-edged orifice
    Q_drain = Cd * A_drain * np.sqrt(2.0 * G * max(h_pool, 0.0)) if A_drain > 0 else 0.0

    # Evaporation
    mdot_evap = k_m * A_floor * max(C_sat - C_bay, 0.0) if V_pool > 0 else 0.0

    # Ventilation loss
    mdot_vent = Q_vent * C_bay

    dVpool_dt = Q_leak - Q_drain - mdot_evap / rho_liq
    if V_pool <= 0 and dVpool_dt < 0:
        dVpool_dt = 0.0
    if h_pool >= bay_h and dVpool_dt > 0:
        dVpool_dt = 0.0

    dm_vap_dt = mdot_evap - mdot_vent

    return [dVpool_dt, dm_vap_dt]


def overflow_event(t, y, params):
    """Event function: triggers when pool depth reaches bay height."""
    return params['bay_height'] - y[0] / params['A_floor']

overflow_event.terminal = True
overflow_event.direction = -1


# =========================================================================
#  CANTERA AICC COMBUSTION
# =========================================================================
def run_aicc_ndodecane(T1, P1, phi):
    """
    AICC calculation using the bundled nDodecane_Reitz mechanism.
    n-Dodecane (NC12H26) as single-component Jet-A surrogate.

    Returns dict with T2, P2, pressure ratio, overpressure, and product
    species mole fractions.  Returns None if Cantera unavailable.
    """
    if not HAS_CANTERA:
        return None

    gas = ct.Solution('nDodecane_Reitz.yaml', 'nDodecane_IG')
    gas.TP = T1, P1
    gas.set_equivalence_ratio(phi, 'NC12H26', 'O2:1.0, N2:3.76')

    T1_actual = gas.T
    P1_actual = gas.P
    rho1 = gas.density_mass
    X_react = dict(zip(gas.species_names, gas.X))

    gas.equilibrate('UV')  # constant internal energy + volume → AICC

    T2, P2 = gas.T, gas.P
    products = {name: gas.X[i] for i, name in enumerate(gas.species_names)
                if gas.X[i] > 1e-4}

    return {
        'mechanism': 'nDodecane_Reitz (100 species, 432 reactions)',
        'fuel_species': 'NC12H26 (n-dodecane, C₁₂H₂₆)',
        'T1': T1_actual, 'P1': P1_actual, 'rho1': rho1,
        'T2': T2, 'P2': P2,
        'pressure_ratio': P2 / P1_actual,
        'overpressure_Pa': P2 - P1_actual,
        'overpressure_psi': (P2 - P1_actual) / 6894.76,
        'products': products,
    }


def run_aicc_multicomponent(T1, P1, phi, mech_file=None):
    """
    AICC calculation using a multi-component Jet-A surrogate.

    If no external mechanism file is provided, falls back to nDodecane_Reitz
    with a blended fuel definition (n-dodecane + toluene + iso-octane) to
    approximate a multi-component surrogate within the bundled mechanism's
    species list.

    For full-fidelity multi-component surrogate work, provide a converted
    YAML mechanism (e.g., JetSurF 2.0 or Narayanaswamy) via mech_file.

    Returns dict or None.
    """
    if not HAS_CANTERA:
        return None

    if mech_file and os.path.isfile(mech_file):
        gas = ct.Solution(mech_file)
        fuel_str = 'NC12H26:0.60, C6H5CH3:0.20, IC8H18:0.20'
        fuel_label = f'Multi-component surrogate ({mech_file})'
    else:
        # Use bundled mechanism with available species approximation.
        # nDodecane_Reitz contains NC12H26, A1 (benzene), and smaller
        # aromatics but not toluene or iso-octane directly.  We use
        # pure n-dodecane as the effective surrogate in this fallback.
        gas = ct.Solution('nDodecane_Reitz.yaml', 'nDodecane_IG')
        # Check what species are available for blending
        available = gas.species_names
        if 'C6H5CH3' in available and 'IC8H18' in available:
            fuel_str = 'NC12H26:0.60, C6H5CH3:0.20, IC8H18:0.20'
            fuel_label = ('Multi-component surrogate '
                          '(60% n-dodecane, 20% toluene, 20% iso-octane)')
        else:
            # Fallback: pure n-dodecane (identical to single-component)
            fuel_str = 'NC12H26:1.0'
            fuel_label = ('n-Dodecane only (multi-component species '
                          'not in bundled mechanism; provide external '
                          'YAML for full surrogate)')

    gas.TP = T1, P1
    gas.set_equivalence_ratio(phi, fuel_str, 'O2:1.0, N2:3.76')

    T1_actual = gas.T
    P1_actual = gas.P

    gas.equilibrate('UV')

    T2, P2 = gas.T, gas.P
    products = {name: gas.X[i] for i, name in enumerate(gas.species_names)
                if gas.X[i] > 1e-4}

    return {
        'mechanism': fuel_label,
        'fuel_species': fuel_str,
        'T1': T1_actual, 'P1': P1_actual,
        'T2': T2, 'P2': P2,
        'pressure_ratio': P2 / P1_actual,
        'overpressure_Pa': P2 - P1_actual,
        'overpressure_psi': (P2 - P1_actual) / 6894.76,
        'products': products,
    }


def run_aicc_sweep(T1, P1, phi_range):
    """
    Sweep equivalence ratio and return AICC pressure ratio arrays for
    both mechanisms.  Used for the comparison plot.
    """
    if not HAS_CANTERA:
        return None, None

    n = len(phi_range)
    ratio_ndod = np.zeros(n)
    ratio_multi = np.zeros(n)

    for i, phi in enumerate(phi_range):
        r1 = run_aicc_ndodecane(T1, P1, phi)
        r2 = run_aicc_multicomponent(T1, P1, phi)
        ratio_ndod[i] = r1['pressure_ratio'] if r1 else np.nan
        ratio_multi[i] = r2['pressure_ratio'] if r2 else np.nan

    return ratio_ndod, ratio_multi


def compute_impulse(P_peak, P_init, V_bay, bay_length):
    """
    Estimate the pressure impulse from a confined deflagration using
    a triangular pulse approximation.

    The deflagration pressure rise time is estimated from the bay
    characteristic length and a representative turbulent flame speed.
    The decay time uses the acoustic timescale in the hot products.

    Parameters
    ----------
    P_peak : float — peak pressure [Pa]
    P_init : float — initial pressure [Pa]
    V_bay  : float — bay volume [m³]
    bay_length : float — characteristic bay length [m]

    Returns dict with impulse and timing estimates.
    """
    delta_P = P_peak - P_init

    # Flame speed estimates
    S_L = 0.45          # laminar burning velocity [m/s] (Jet-A, stoich)
    expansion = 7.0     # density ratio across flame
    S_turb = S_L * expansion  # effective turbulent deflagration speed

    # Pressure rise time ~ time for flame to traverse bay
    t_rise = bay_length / S_turb   # [s]

    # Acoustic decay timescale in hot products
    gamma_prod = 1.24
    T_prod = 2600.0  # approximate AICC temperature [K]
    MW_prod = 0.028  # approximate product MW [kg/mol]
    c_prod = np.sqrt(gamma_prod * R_U * T_prod / MW_prod)
    t_acoustic = bay_length / c_prod

    # Triangular pulse: I = 0.5 × ΔP × t_duration
    t_duration = t_rise + 3.0 * t_acoustic  # rise + ring-down
    impulse = 0.5 * delta_P * t_duration    # [Pa·s]

    return {
        'delta_P_bar': delta_P / 1e5,
        'delta_P_psi': delta_P / 6894.76,
        't_rise_ms': t_rise * 1000.0,
        't_acoustic_ms': t_acoustic * 1000.0,
        't_duration_ms': t_duration * 1000.0,
        'impulse_Pa_s': impulse,
        'impulse_psi_ms': impulse / 6894.76 * 1000.0,
        'flame_speed_m_s': S_turb,
        'sound_speed_m_s': c_prod,
    }


# =========================================================================
#  EXPERIMENTAL COMPARISON DATA
# =========================================================================
# Peak pressure ratios from Caltech EDL experiments (Shepherd et al.,
# FM97-5, FM98-6) at 0.585 bar, various temperatures.  These represent
# measured DEFLAGRATION overpressure in the HYJET vessel.
CALTECH_EXPERIMENTAL = {
    'description': (
        'Caltech EDL Jet A explosion experiments (Shepherd et al., '
        'GALCIT FM97-5 / FM98-6, NTSB Exhibits 20D/20O). '
        'Conducted at 0.585 bar (14,000 ft equivalent) in 1.18 m³ HYJET vessel.'
    ),
    # Approximate equivalence ratios and measured P2/P1
    'phi':      np.array([0.65, 0.75, 0.85, 1.0,  1.1,  1.2]),
    'P2_P1':    np.array([3.6,  4.8,  5.9,  7.2,  7.0,  6.2]),
    'T_init_C': np.array([35,   40,   45,   55,   60,   65]),
    'P_init_bar': 0.585,
    'notes': (
        'Values are approximate reads from published figures. '
        'Exact data points should be digitised from the original reports.'
    ),
}


# =========================================================================
#  MAIN ANALYSIS
# =========================================================================
def main():
    # ── USER INPUTS ──────────────────────────────────────────────────────

    # Bay geometry
    bay_length = 1.0        # [m]
    bay_width  = 0.5        # [m]
    bay_height = 0.4        # [m]

    # Drain geometry
    D_drain    = 0.010      # Drain hole diameter [m]
    Cd_drain   = 0.61       # Orifice discharge coefficient

    # Fuel leak rate
    Q_leak_mL_min = 50.0    # [mL/min]

    # Environmental conditions
    T_bay_C   = 40.0        # Bay temperature [°C]
    alt_ft    = 35000.0     # Altitude [ft]

    # Ventilation
    Q_vent_Lpm = 0.0        # Fresh-air ventilation [L/min] (0 = sealed)

    # Spark / ignition source
    E_spark_mJ = 0.25       # Credible spark energy [mJ]

    # Flammability limits at sea level [vol %]
    LEL_SL_pct = 0.6
    UEL_SL_pct = 4.7

    # Simulation time
    t_end = 3600.0          # [s] (1 hour)

    # Cantera: external mechanism file for multi-component surrogate
    # Set to path of your YAML file, or None to use bundled mechanism.
    MULTI_MECH_FILE = None

    # ── UNIT CONVERSIONS ─────────────────────────────────────────────────
    T_bay     = T_bay_C + 273.15
    alt       = alt_ft / 3.28084
    A_floor   = bay_length * bay_width
    V_bay     = A_floor * bay_height
    A_drain   = np.pi / 4.0 * D_drain ** 2
    Q_leak    = Q_leak_mL_min * 1e-6 / 60.0       # [m³/s]
    Q_vent    = Q_vent_Lpm * 1e-3 / 60.0           # [m³/s]
    P_amb     = ambient_pressure(alt)
    rho_liq   = liquid_fuel_density(T_bay)
    mdot_leak = Q_leak * rho_liq

    Pv        = min(true_vapor_pressure(T_bay), P_amb)
    D_va      = vapor_diffusivity(T_bay, P_amb)
    rho_air   = (P_amb * M_AIR) / (R_U * T_bay)
    C_sat     = (Pv * M_FUEL) / (R_U * T_bay)

    # ── MASS TRANSFER COEFFICIENT ────────────────────────────────────────
    L_char = A_floor / (2.0 * (bay_length + bay_width))
    nu_air = 1.5e-5 * (T_bay / 293.0) ** 1.5 * (P0 / P_amb)
    Sc     = nu_air / D_va
    delta_rho = (M_FUEL - M_AIR) / M_AIR * (Pv / P_amb)
    Gr_m   = G * abs(delta_rho) * L_char ** 3 / nu_air ** 2
    Ra_m   = Gr_m * Sc
    Sh     = 0.15 * Ra_m ** (1.0 / 3.0) if Ra_m > 1e7 else 0.54 * Ra_m ** 0.25
    k_m    = Sh * D_va / L_char

    # ── STEADY-STATE POOL (ANALYTICAL, DRAIN ONLY) ───────────────────────
    if D_drain > 0:
        h_pool_ss = (Q_leak / (Cd_drain * A_drain)) ** 2 / (2.0 * G)
        V_pool_ss = A_floor * h_pool_ss
    else:
        h_pool_ss = np.inf
        V_pool_ss = np.inf

    # ── PRINT INPUT SUMMARY ──────────────────────────────────────────────
    sep = '=' * 56
    print(sep)
    print('  BAY FUEL LEAK ANALYSIS')
    print(sep)
    print(f'  Bay dimensions     : {bay_length:.2f} × {bay_width:.2f} × '
          f'{bay_height:.2f} m  ({V_bay * 1000:.1f} L)')
    print(f'  Drain diameter     : {D_drain * 1000:.1f} mm')
    print(f'  Leak rate          : {Q_leak_mL_min:.1f} mL/min '
          f'({mdot_leak * 1000:.2f} g/s)')
    print(f'  Temperature        : {T_bay_C:.1f} °C')
    print(f'  Altitude           : {alt_ft:.0f} ft')
    print(f'  Ambient pressure   : {P_amb:.0f} Pa ({P_amb / 6894.76:.2f} psi)')
    print(f'  Vapor pressure     : {Pv:.2f} Pa')
    print(f'  Ventilation        : {Q_vent_Lpm:.1f} L/min')
    print(f'  Cantera available  : {HAS_CANTERA}')
    print(sep)

    # ── TRANSIENT ODE SIMULATION ─────────────────────────────────────────
    params = {
        'Q_leak': Q_leak, 'Cd_drain': Cd_drain, 'A_drain': A_drain,
        'A_floor': A_floor, 'bay_height': bay_height, 'k_m': k_m,
        'C_sat': C_sat, 'rho_liq': rho_liq, 'V_bay': V_bay,
        'Q_vent': Q_vent,
    }

    sol = solve_ivp(
        fun=lambda t, y: bay_ode(t, y, params),
        t_span=(0, t_end),
        y0=[0.0, 0.0],
        method='RK45',
        max_step=1.0,
        rtol=1e-8, atol=1e-12,
        events=lambda t, y: overflow_event(t, y, params),
    )

    t = sol.t
    V_pool = np.maximum(sol.y[0], 0.0)
    m_vap  = np.maximum(sol.y[1], 0.0)

    # ── DERIVED TIME HISTORIES ───────────────────────────────────────────
    h_pool  = V_pool / A_floor
    V_gas   = V_bay - V_pool
    C_bay   = m_vap / np.maximum(V_gas, 1e-12)
    n_vap   = m_vap / M_FUEL
    n_air   = (P_amb * V_gas / (R_U * T_bay)) - n_vap
    X_fuel  = n_vap / (n_vap + n_air)
    Y_fuel  = (X_fuel * M_FUEL) / (X_fuel * M_FUEL + (1.0 - X_fuel) * M_AIR)
    FAR     = (X_fuel * M_FUEL) / ((1.0 - X_fuel) * M_AIR)

    Q_drain_t   = Cd_drain * A_drain * np.sqrt(2.0 * G * np.maximum(h_pool, 0.0))
    mdot_evap_t = k_m * A_floor * np.maximum(C_sat - C_bay, 0.0)
    mdot_evap_t[V_pool <= 0] = 0.0

    # Altitude-corrected flammability limits
    LEL_alt = (LEL_SL_pct / 100.0) * P0 / P_amb
    UEL_alt = (UEL_SL_pct / 100.0) * P0 / P_amb

    # MIE time history
    MIE_t = np.array([mie_parabolic(x, LEL_alt, UEL_alt) for x in X_fuel])

    # ── STEADY-STATE SUMMARY ─────────────────────────────────────────────
    X_ss = X_fuel[-1]
    Y_ss = Y_fuel[-1]
    MIE_ss = mie_parabolic(X_ss, LEL_alt, UEL_alt)

    if X_ss >= LEL_alt and X_ss <= UEL_alt:
        flam_str = 'YES — FLAMMABLE'
    elif X_ss < LEL_alt:
        flam_str = 'No — below LEL (too lean)'
    else:
        flam_str = 'No — above UEL (too rich)'

    print()
    print(sep)
    print('  STEADY-STATE RESULTS')
    print(sep)
    print(f'  Pool depth          : {h_pool[-1] * 1000:.2f} mm')
    print(f'  Pool volume         : {V_pool[-1] * 1e6:.2f} mL')
    print(f'  Pool mass           : {V_pool[-1] * rho_liq * 1000:.2f} g')
    print(f'  Drain outflow       : {Q_drain_t[-1] * 1e6 * 60:.2f} mL/min')
    print(f'  Evaporation rate    : {mdot_evap_t[-1] * 1000 * 60:.4f} g/min')
    print(f'  ---')
    print(f'  Vapor vol fraction  : {X_ss * 100:.4f} %')
    print(f'  Vapor mass fraction : {Y_ss * 100:.4f} %')
    print(f'  Vapor density       : {C_bay[-1] * 1000:.4f} g/m³')
    print(f'  Fuel-air ratio      : {FAR[-1]:.6f}')
    print(f'  ---')
    print(f'  LEL (alt-corrected) : {LEL_alt * 100:.4f} %')
    print(f'  UEL (alt-corrected) : {UEL_alt * 100:.4f} %')
    print(f'  Flammable?          : {flam_str}')
    print(f'  ---')
    print(f'  MIE at this conc    : {MIE_ss:.3f} mJ')
    print(f'  Spark energy        : {E_spark_mJ:.3f} mJ')
    if np.isfinite(MIE_ss) and E_spark_mJ >= MIE_ss:
        print(f'  Ignitable?          : YES — spark can ignite')
    elif np.isfinite(MIE_ss):
        print(f'  Ignitable?          : No — need ≥ {MIE_ss:.3f} mJ')
    else:
        print(f'  Ignitable?          : N/A — mixture not flammable')
    print(sep)

    # =====================================================================
    #  FUEL VOLUME REQUIRED FOR FLAMMABLE MIXTURE (35 °C, 100 m)
    # =====================================================================
    fv_T_C  = 35.0    # [°C]
    fv_alt  = 100.0   # [m]
    fv = fuel_volume_for_flammability(fv_T_C, fv_alt, V_bay,
                                       LEL_SL_pct, UEL_SL_pct)

    print()
    print(sep)
    print('  FUEL VOLUME FOR FLAMMABLE MIXTURE')
    print(f'  Conditions: {fv_T_C:.0f} °C, {fv_alt:.0f} m altitude')
    print(sep)
    print(f'  Ambient pressure    : {fv["P_amb"]:.0f} Pa '
          f'({fv["P_amb"] / 6894.76:.2f} psi)')
    print(f'  Liquid fuel density : {fv["rho_liq"]:.1f} kg/m³')
    print(f'  Bay volume          : {V_bay * 1000:.1f} L')
    print(f'  LEL (alt-corrected) : {fv["LEL_alt"] * 100:.4f} %')
    print(f'  UEL (alt-corrected) : {fv["UEL_alt"] * 100:.4f} %')
    print(f'  ---')
    print(f'  Liquid fuel to reach LEL          : {fv["V_liq_LEL_mL"]:.3f} mL '
          f'({fv["m_fuel_LEL"] * 1000:.3f} g)')
    print(f'  Liquid fuel to reach stoichiometric: {fv["V_liq_stoich_mL"]:.3f} mL '
          f'({fv["m_fuel_stoich"] * 1000:.3f} g)')
    print(f'  Liquid fuel to reach UEL          : {fv["V_liq_UEL_mL"]:.3f} mL '
          f'({fv["m_fuel_UEL"] * 1000:.3f} g)')
    print(f'  ---')
    print(f'  Flammable range: {fv["V_liq_LEL_mL"]:.3f} – '
          f'{fv["V_liq_UEL_mL"]:.3f} mL of liquid fuel')
    print(f'  NOTE: Assumes complete evaporation of the liquid into')
    print(f'        a sealed bay with no ventilation or drainage.')
    print(sep)

    # =====================================================================
    #  CANTERA AICC COMBUSTION ANALYSIS
    # =====================================================================
    if HAS_CANTERA:
        print()
        print(sep)
        print('  CANTERA AICC COMBUSTION OVERPRESSURE')
        print(sep)

        # Use the steady-state bay conditions as the pre-ignition state
        phi_bay = X_ss / X_STOICH  # approximate equivalence ratio

        # ── Stoichiometric reference case (Jet-A1 example) ───────────
        print('\n  ── Stoichiometric Reference Case (φ = 1.0) ──')
        r_stoich_1 = run_aicc_ndodecane(T_bay, P_amb, 1.0)
        r_stoich_2 = run_aicc_multicomponent(T_bay, P_amb, 1.0, MULTI_MECH_FILE)

        for label, r in [('n-Dodecane', r_stoich_1),
                         ('Multi-component', r_stoich_2)]:
            if r is None:
                continue
            print(f'\n  [{label}]  {r["mechanism"]}')
            print(f'    Initial : T = {r["T1"]:.1f} K, P = {r["P1"] / 1e5:.4f} bar')
            print(f'    AICC    : T = {r["T2"]:.1f} K, P = {r["P2"] / 1e5:.4f} bar')
            print(f'    P₂/P₁   = {r["pressure_ratio"]:.3f}')
            print(f'    ΔP      = {r["overpressure_Pa"] / 1e5:.3f} bar '
                  f'({r["overpressure_psi"]:.1f} psi)')
            print(f'    Major products (X > 0.01%):')
            for sp, xf in sorted(r['products'].items(), key=lambda x: -x[1]):
                if xf > 1e-3:
                    print(f'      {sp:12s}: {xf:.6f}')

        # ── Actual bay conditions ────────────────────────────────────
        if X_ss >= LEL_alt and X_ss <= UEL_alt:
            print(f'\n  ── Bay Conditions (φ ≈ {phi_bay:.3f}) ──')
            r_bay_1 = run_aicc_ndodecane(T_bay, P_amb, phi_bay)
            r_bay_2 = run_aicc_multicomponent(T_bay, P_amb, phi_bay,
                                               MULTI_MECH_FILE)

            for label, r in [('n-Dodecane', r_bay_1),
                             ('Multi-component', r_bay_2)]:
                if r is None:
                    continue
                print(f'\n  [{label}]')
                print(f'    AICC    : T = {r["T2"]:.1f} K, '
                      f'P = {r["P2"] / 1e5:.4f} bar')
                print(f'    P₂/P₁   = {r["pressure_ratio"]:.3f}')
                print(f'    ΔP      = {r["overpressure_Pa"] / 1e5:.3f} bar '
                      f'({r["overpressure_psi"]:.1f} psi)')

            # Impulse estimate
            r_imp = r_bay_1 or r_bay_2
            if r_imp:
                imp = compute_impulse(r_imp['P2'], r_imp['P1'],
                                      V_bay, bay_length)
                print(f'\n  ── Impulse Estimate (triangular pulse) ──')
                print(f'    Flame speed      : {imp["flame_speed_m_s"]:.1f} m/s')
                print(f'    Rise time        : {imp["t_rise_ms"]:.1f} ms')
                print(f'    Acoustic time    : {imp["t_acoustic_ms"]:.2f} ms')
                print(f'    Pulse duration   : {imp["t_duration_ms"]:.1f} ms')
                print(f'    Impulse          : {imp["impulse_Pa_s"]:.1f} Pa·s '
                      f'({imp["impulse_psi_ms"]:.1f} psi·ms)')
        else:
            print(f'\n  Bay mixture (φ ≈ {phi_bay:.3f}) is outside flammable '
                  f'range.  No combustion analysis performed for bay conditions.')

        # ── Experimental comparison ──────────────────────────────────
        print(f'\n  ── Comparison with Caltech Experimental Data ──')
        print(f'  {CALTECH_EXPERIMENTAL["description"]}')
        print(f'  NOTE: {CALTECH_EXPERIMENTAL["notes"]}')

        # Run AICC at experimental conditions (0.585 bar, varied φ)
        P_exp = CALTECH_EXPERIMENTAL['P_init_bar'] * 1e5
        phi_exp = CALTECH_EXPERIMENTAL['phi']
        T_exp_arr = CALTECH_EXPERIMENTAL['T_init_C'] + 273.15

        print(f'\n  {"φ":>6s}  {"T_init":>7s}  {"Exp P₂/P₁":>10s}  '
              f'{"AICC P₂/P₁":>11s}  {"AICC/Exp":>9s}')
        print(f'  {"-" * 50}')

        for phi_e, T_e, exp_ratio in zip(phi_exp, T_exp_arr,
                                          CALTECH_EXPERIMENTAL['P2_P1']):
            r_e = run_aicc_ndodecane(T_e, P_exp, phi_e)
            if r_e:
                aicc_ratio = r_e['pressure_ratio']
                over_pred = aicc_ratio / exp_ratio
                print(f'  {phi_e:6.2f}  {T_e - 273.15:6.1f}°C  '
                      f'{exp_ratio:10.2f}  {aicc_ratio:11.3f}  '
                      f'{over_pred:9.2f}×')

        # ── Equivalence ratio sweep ──────────────────────────────────
        print('\n  Running φ sweep for plot...')
        phi_sweep = np.linspace(0.5, 2.0, 31)
        ratio_nd, ratio_mc = run_aicc_sweep(T_bay, P_amb, phi_sweep)

        # ── Conservatism notes ───────────────────────────────────────
        print(f'\n  ── Notes on Conservatism ──')
        print(f'  1. AICC assumes ZERO heat loss to bay walls, structure,')
        print(f'     and equipment.  Real explosions lose 10-20% of energy')
        print(f'     to walls (Shepherd FM97-5: measured ≈ 80-90% of AICC')
        print(f'     near stoichiometric).')
        print(f'  2. AICC assumes COMPLETE combustion.  Lean mixtures show')
        print(f'     significant unburned fuel; correction factor 0.5-0.95.')
        print(f'  3. AICC assumes UNIFORM mixture.  Real bay has vapor')
        print(f'     stratification; local φ varies with height.')
        print(f'  4. AICC assumes INSTANTANEOUS combustion.  Real deflagration')
        print(f'     takes O(100 ms); venting can relieve pressure if bay is')
        print(f'     not fully sealed.')
        print(f'  5. Model uses n-dodecane as Jet-A surrogate.  Real Jet-A')
        print(f'     has aromatics and cycloparaffins that slightly alter')
        print(f'     equilibrium products and adiabatic flame temperature.')
        print(f'  6. Impulse uses triangular-pulse approximation; actual')
        print(f'     pressure-time history depends on flame acceleration,')
        print(f'     turbulence, and bay geometry.')
        print(sep)

    # =====================================================================
    #  PLOTTING
    # =====================================================================
    t_min = t / 60.0

    # ── Figure 1: Pool Buildup ───────────────────────────────────────
    fig1, axes1 = plt.subplots(2, 2, figsize=(14, 10))
    fig1.suptitle('Pool Buildup', fontsize=14, fontweight='bold')

    ax = axes1[0, 0]
    ax.plot(t_min, h_pool * 1000, 'b-', linewidth=2)
    if np.isfinite(h_pool_ss):
        ax.axhline(h_pool_ss * 1000, color='r', ls='--', lw=1.5,
                    label='Steady state')
        ax.legend()
    ax.set_xlabel('Time [min]')
    ax.set_ylabel('Pool Depth [mm]')
    ax.set_title('Liquid Pool Depth')
    ax.grid(True, alpha=0.3)

    ax = axes1[0, 1]
    ax.plot(t_min, V_pool * 1e6, 'b-', linewidth=2)
    if np.isfinite(V_pool_ss):
        ax.axhline(V_pool_ss * 1e6, color='r', ls='--', lw=1.5,
                    label='Steady state')
        ax.legend()
    ax.set_xlabel('Time [min]')
    ax.set_ylabel('Pool Volume [mL]')
    ax.set_title('Liquid Pool Volume')
    ax.grid(True, alpha=0.3)

    ax = axes1[1, 0]
    ax.plot(t_min, Q_drain_t * 1e6 * 60, 'r-', lw=1.5, label='Drain out')
    ax.plot(t_min, mdot_evap_t / rho_liq * 1e6 * 60, 'g-', lw=1.5,
            label='Evaporated')
    ax.axhline(Q_leak * 1e6 * 60, color='b', ls='--', lw=1.5, label='Leak in')
    ax.set_xlabel('Time [min]')
    ax.set_ylabel('Flow Rate [mL/min]')
    ax.set_title('Flow Balance')
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes1[1, 1]
    m_drained = np.cumsum(np.diff(t, prepend=0) * Q_drain_t * rho_liq) * 1000
    m_evap_cum = np.cumsum(np.diff(t, prepend=0) * mdot_evap_t) * 1000
    m_leaked  = mdot_leak * t * 1000
    m_pool_g  = V_pool * rho_liq * 1000
    ax.plot(t_min, m_leaked, 'b-', lw=1.5, label='Total leaked')
    ax.plot(t_min, m_pool_g, 'k-', lw=2, label='In pool')
    ax.plot(t_min, m_drained, 'r-', lw=1.5, label='Drained')
    ax.plot(t_min, m_evap_cum, 'g-', lw=1.5, label='Evaporated')
    ax.set_xlabel('Time [min]')
    ax.set_ylabel('Mass [g]')
    ax.set_title('Cumulative Mass Accounting')
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig1.tight_layout()

    # ── Figure 2: Vapor Concentration & Flammability ─────────────────
    fig2, axes2 = plt.subplots(2, 2, figsize=(14, 10))
    fig2.suptitle('Bay Vapor Concentration', fontsize=14, fontweight='bold')

    ax = axes2[0, 0]
    ax.plot(t_min, X_fuel * 100, 'b-', linewidth=2)
    ax.axhline(LEL_alt * 100, color='r', ls='--', lw=1.5)
    ax.axhline(UEL_alt * 100, color='r', ls='--', lw=1.5)
    ax.axhspan(LEL_alt * 100, UEL_alt * 100, alpha=0.08, color='r')
    ax.text(t_min[-1] * 0.02, LEL_alt * 100 * 1.05, 'LEL', color='r', fontsize=9)
    ax.text(t_min[-1] * 0.02, UEL_alt * 100 * 1.05, 'UEL', color='r', fontsize=9)
    ax.set_xlabel('Time [min]')
    ax.set_ylabel('Fuel Vapor [vol %]')
    ax.set_title('Volume Fraction in Bay')
    ax.grid(True, alpha=0.3)

    ax = axes2[0, 1]
    ax.plot(t_min, C_bay * 1000, 'b-', linewidth=2)
    ax.axhline(C_sat * 1000, color='k', ls='--', lw=1.5, label='Saturation')
    ax.set_xlabel('Time [min]')
    ax.set_ylabel('Vapor Concentration [g/m³]')
    ax.set_title('Mass Concentration in Bay')
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes2[1, 0]
    ax.plot(t_min, Y_fuel * 100, 'b-', linewidth=2)
    ax.set_xlabel('Time [min]')
    ax.set_ylabel('Mass Fraction [%]')
    ax.set_title('Vapor Mass Fraction')
    ax.grid(True, alpha=0.3)

    ax = axes2[1, 1]
    ax.plot(t_min, FAR, 'b-', linewidth=2)
    FAR_stoich = (X_STOICH * M_FUEL) / ((1 - X_STOICH) * M_AIR)
    ax.axhline(FAR_stoich, color='k', ls='--', lw=1, label='Stoichiometric')
    ax.set_xlabel('Time [min]')
    ax.set_ylabel('Fuel-to-Air Ratio [kg/kg]')
    ax.set_title('Fuel-to-Air Ratio')
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig2.tight_layout()

    # ── Figure 3: MIE Assessment ─────────────────────────────────────
    fig3, axes3 = plt.subplots(1, 2, figsize=(13, 5))
    fig3.suptitle('Minimum Ignition Energy Assessment',
                  fontsize=14, fontweight='bold')

    ax = axes3[0]
    x_plot = np.linspace(LEL_alt * 0.5, UEL_alt * 1.5, 500)
    mie_curve = np.array([mie_parabolic(x, LEL_alt, UEL_alt) for x in x_plot])
    mie_finite = np.isfinite(mie_curve)
    ax.semilogy(x_plot[mie_finite] * 100, mie_curve[mie_finite],
                'k-', linewidth=2, label='MIE(x)')
    ax.axhline(E_spark_mJ, color='r', ls='--', lw=2,
               label=f'Spark = {E_spark_mJ:.2f} mJ')
    ax.axvline(LEL_alt * 100, color='b', ls='--', lw=1, label='LEL')
    ax.axvline(UEL_alt * 100, color='b', ls='--', lw=1, label='UEL')
    ax.set_xlabel('Fuel Vapor Volume Fraction [%]')
    ax.set_ylabel('MIE [mJ]')
    ax.set_title('MIE vs Concentration')
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes3[1]
    mie_finite_t = np.isfinite(MIE_t)
    if np.any(mie_finite_t):
        ax.semilogy(t_min[mie_finite_t], MIE_t[mie_finite_t],
                     'b-', linewidth=2, label='MIE at bay conc.')
    ax.axhline(E_spark_mJ, color='r', ls='--', lw=2,
               label=f'Spark = {E_spark_mJ:.2f} mJ')
    ax.set_xlabel('Time [min]')
    ax.set_ylabel('MIE [mJ]')
    ax.set_title('MIE vs Time')
    ax.legend()
    ax.grid(True, alpha=0.3)

    ignitible = (MIE_t <= E_spark_mJ) & (X_fuel >= LEL_alt) & (X_fuel <= UEL_alt)
    if np.any(ignitible):
        t_ign = t_min[np.argmax(ignitible)]
        ax.axvline(t_ign, color='m', lw=2, label=f'Ignitable @ {t_ign:.1f} min')
        ax.legend()

    fig3.tight_layout()

    # ── Figure 4: AICC Equivalence Ratio Sweep + Experimental ────────
    if HAS_CANTERA:
        fig4, ax4 = plt.subplots(figsize=(10, 7))
        fig4.suptitle('AICC Overpressure vs Equivalence Ratio',
                      fontsize=14, fontweight='bold')

        if ratio_nd is not None:
            ax4.plot(phi_sweep, ratio_nd, 'b-', lw=2,
                     label='AICC — n-Dodecane (Reitz)')
        if ratio_mc is not None:
            ax4.plot(phi_sweep, ratio_mc, 'g--', lw=2,
                     label='AICC — Multi-component surrogate')

        # Overlay experimental data
        ax4.plot(CALTECH_EXPERIMENTAL['phi'], CALTECH_EXPERIMENTAL['P2_P1'],
                 'rs', markersize=10, markerfacecolor='none', markeredgewidth=2,
                 label='Caltech Experimental (0.585 bar)')

        # 85% correction line
        if ratio_nd is not None:
            ax4.plot(phi_sweep, ratio_nd * 0.85, 'b:', lw=1.5, alpha=0.6,
                     label='AICC × 0.85 (heat loss correction)')

        if X_ss >= LEL_alt:
            ax4.axvline(phi_bay, color='orange', ls='-.', lw=2,
                        label=f'Bay conditions (φ ≈ {phi_bay:.2f})')

        ax4.set_xlabel('Equivalence Ratio φ')
        ax4.set_ylabel('Pressure Ratio P₂/P₁')
        ax4.legend(fontsize=9)
        ax4.grid(True, alpha=0.3)
        ax4.set_xlim(0.4, 2.1)
        ax4.set_ylim(0, 12)

        # Annotation for conservatism
        ax4.annotate(
            'AICC overpredicts by\n10–20% near stoich.\n(Shepherd et al.)',
            xy=(1.0, ratio_nd[np.argmin(np.abs(phi_sweep - 1.0))] if ratio_nd is not None else 9),
            xytext=(1.4, 10.5),
            fontsize=9, ha='center',
            arrowprops=dict(arrowstyle='->', color='gray'),
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow',
                      alpha=0.8),
        )

        fig4.tight_layout()

    # ── Figure 5: Parametric — Leak Rate Sweep ───────────────────────
    Q_sweep = np.linspace(5, 200, 50)
    h_ss_sw = np.zeros_like(Q_sweep)
    X_ss_sw = np.zeros_like(Q_sweep)
    t_flam_sw = np.full_like(Q_sweep, np.nan)

    for i, q_ml in enumerate(Q_sweep):
        ql = q_ml * 1e-6 / 60.0
        if D_drain > 0:
            h_ss_sw[i] = (ql / (Cd_drain * A_drain)) ** 2 / (2.0 * G)

        p_i = dict(params)
        p_i['Q_leak'] = ql
        sol_i = solve_ivp(
            fun=lambda t, y, p=p_i: bay_ode(t, y, p),
            t_span=(0, t_end), y0=[0.0, 0.0],
            method='RK45', max_step=5.0, rtol=1e-6, atol=1e-10,
        )
        V_g = V_bay - np.maximum(sol_i.y[0], 0.0)
        nv = np.maximum(sol_i.y[1], 0.0) / M_FUEL
        na = (P_amb * V_g / (R_U * T_bay)) - nv
        X_i = nv / (nv + na)
        X_ss_sw[i] = X_i[-1]
        idx = np.argmax(X_i >= LEL_alt)
        if X_i[idx] >= LEL_alt:
            t_flam_sw[i] = sol_i.t[idx] / 60.0

    fig5, axes5 = plt.subplots(1, 3, figsize=(16, 5))
    fig5.suptitle(f'Parametric: Leak Rate Sweep (T={T_bay_C:.0f}°C, '
                  f'Alt={alt_ft:.0f}ft, Drain={D_drain * 1000:.1f}mm)',
                  fontsize=13, fontweight='bold')

    axes5[0].plot(Q_sweep, h_ss_sw * 1000, 'b-', lw=2)
    axes5[0].set_xlabel('Leak Rate [mL/min]')
    axes5[0].set_ylabel('SS Pool Depth [mm]')
    axes5[0].set_title('Steady-State Pool Depth')
    axes5[0].grid(True, alpha=0.3)

    axes5[1].plot(Q_sweep, X_ss_sw * 100, 'b-', lw=2)
    axes5[1].axhline(LEL_alt * 100, color='r', ls='--', lw=1.5, label='LEL')
    axes5[1].axhline(UEL_alt * 100, color='r', ls='--', lw=1.5, label='UEL')
    axes5[1].set_xlabel('Leak Rate [mL/min]')
    axes5[1].set_ylabel('SS Volume Fraction [%]')
    axes5[1].set_title('Steady-State Vapor Concentration')
    axes5[1].legend()
    axes5[1].grid(True, alpha=0.3)

    axes5[2].plot(Q_sweep, t_flam_sw, 'r-', lw=2)
    axes5[2].set_xlabel('Leak Rate [mL/min]')
    axes5[2].set_ylabel('Time to LEL [min]')
    axes5[2].set_title('Time to Reach Flammable Mixture')
    axes5[2].grid(True, alpha=0.3)

    fig5.tight_layout()

    # ── Save all figures ─────────────────────────────────────────────
    fig1.savefig('fig1_pool_buildup.png', dpi=150, bbox_inches='tight')
    fig2.savefig('fig2_vapor_concentration.png', dpi=150, bbox_inches='tight')
    fig3.savefig('fig3_mie_assessment.png', dpi=150, bbox_inches='tight')
    if HAS_CANTERA:
        fig4.savefig('fig4_aicc_comparison.png', dpi=150, bbox_inches='tight')
    fig5.savefig('fig5_leak_rate_parametric.png', dpi=150, bbox_inches='tight')

    print('\nFigures saved to current directory.')
    plt.show()


if __name__ == '__main__':
    main()
