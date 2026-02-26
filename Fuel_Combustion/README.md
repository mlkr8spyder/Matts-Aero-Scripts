# Bay Fuel Leak Model — Pool Formation, Vapor Flammability, and Confined Combustion Overpressure

A Python model for evaluating the hazard posed by jet fuel leaking into a poorly ventilated aircraft bay. The tool computes transient liquid pool accumulation, equilibrium vapor-air mixture properties, flammability margins, minimum ignition energy assessment, and — when the mixture is flammable — the peak overpressure from an Adiabatic Isochoric Complete Combustion (AICC) event using Cantera thermochemistry.

The model is intentionally conservative: every simplification drives the predicted overpressure upward, producing an upper-bound estimate suitable for safety certification and hazard assessment per the philosophy of FAA Advisory Circular 25.981-1D and SFAR 88.

---

## Table of Contents

1. [Physical Scenario](#1-physical-scenario)
2. [Governing Equations — Pool and Vapor Dynamics](#2-governing-equations--pool-and-vapor-dynamics)
3. [Flammability Assessment](#3-flammability-assessment)
4. [Minimum Ignition Energy](#4-minimum-ignition-energy)
5. [Combustion Overpressure — AICC Theory](#5-combustion-overpressure--aicc-theory)
6. [Cantera Implementation](#6-cantera-implementation)
7. [Comparison with Experimental Data](#7-comparison-with-experimental-data)
8. [Sources of Conservatism](#8-sources-of-conservatism)
9. [Installation and Usage](#9-installation-and-usage)
10. [References](#10-references)

---

## 1. Physical Scenario

Fuel leaks through a boundary — a cracked seal, failed fitting, or damaged conduit — into an adjacent aircraft bay of known geometry. The bay floor contains a drain orifice that removes some fuel, but at low pool depths the drain cannot keep pace with the inflow, so a liquid pool accumulates. Fuel evaporates from the pool surface into the bay air volume, and the resulting vapor-air mixture may enter the flammable range. If an ignition source of sufficient energy is present (electrical arcing, static discharge, hot surface), a confined deflagration can occur, producing a rapid pressure rise that may exceed the structural capacity of the bay.

The model answers four questions in sequence: how large does the pool get, what vapor concentration results, is the mixture flammable and ignitable, and if so, what is the worst-case overpressure?

### Geometry and Coordinate System

The bay is modelled as a rectangular prismatic volume with floor area $A_\text{floor} = L \times W$ and height $H$. The total bay volume is $V_\text{bay} = A_\text{floor} \times H$. The gas-phase (ullage) volume available for the vapor-air mixture is:

$$V_\text{gas}(t) = V_\text{bay} - V_\text{pool}(t)$$

The drain is modelled as a sharp-edged orifice of diameter $D_d$ located at the lowest point of the bay floor.

---

## 2. Governing Equations — Pool and Vapor Dynamics

### 2.1 Pool Volume Balance

The liquid pool volume evolves according to:

$$\frac{dV_\text{pool}}{dt} = Q_\text{leak} - Q_\text{drain}(h) - \frac{\dot{m}_\text{evap}}{\rho_\text{liq}(T)}$$

where $Q_\text{leak}$ is the volumetric leak rate into the bay [m³/s], $Q_\text{drain}$ is the volumetric outflow through the drain, $\dot{m}_\text{evap}$ is the evaporative mass flux from the pool surface [kg/s], and $\rho_\text{liq}(T)$ is the temperature-dependent liquid fuel density.

### 2.2 Drain Outflow — Orifice Model

The drain outflow is governed by the Torricelli equation for a sharp-edged orifice under hydrostatic head:

$$Q_\text{drain} = C_d \, A_d \, \sqrt{2 \, g \, h_\text{pool}}$$

where $C_d \approx 0.61$ is the discharge coefficient for a sharp-edged orifice, $A_d = \pi D_d^2 / 4$ is the orifice cross-sectional area, and $h_\text{pool} = V_\text{pool} / A_\text{floor}$ is the pool depth assuming a flat, level floor with the pool covering the entire floor area. At steady state ($dV_\text{pool}/dt = 0$, neglecting evaporation), the equilibrium pool depth is:

$$h_\text{pool,ss} = \frac{1}{2g} \left( \frac{Q_\text{leak}}{C_d \, A_d} \right)^2$$

This expression provides an analytical conservative upper bound on pool depth.

### 2.3 Evaporation — Convective Mass Transfer Model

The evaporative mass flux from the pool surface is driven by the concentration difference between the saturated vapor layer at the liquid surface and the bulk bay atmosphere:

$$\dot{m}_\text{evap} = k_m \, A_\text{pool} \, (C_\text{sat} - C_\text{bay})$$

where $k_m$ is the convective mass transfer coefficient [m/s], $A_\text{pool}$ is the wetted surface area (equal to $A_\text{floor}$ once the pool covers the floor), and $C_\text{sat}$ and $C_\text{bay}$ are the fuel vapor mass concentrations [kg/m³] at the liquid surface and in the bulk gas, respectively.

The saturation concentration at the pool surface follows from the ideal gas law applied to the fuel vapor at its true vapor pressure:

$$C_\text{sat} = \frac{P_\text{vap}(T) \, M_\text{fuel}}{R_u \, T}$$

where $P_\text{vap}(T)$ is the true vapor pressure of the fuel at temperature $T$, $M_\text{fuel}$ is the fuel molar mass (0.167 kg/mol for Jet-A approximated as C₁₂H₂₃), and $R_u = 8.314$ J/(mol·K).

### 2.4 Mass Transfer Coefficient

For a quiescent bay with no forced airflow, natural-convection mass transfer from a horizontal surface is characterised by the Sherwood number correlation:

$$\text{Sh} = \begin{cases} 0.54 \, \text{Ra}_m^{1/4} & \text{Ra}_m < 10^7 \quad \text{(laminar)} \\ 0.15 \, \text{Ra}_m^{1/3} & \text{Ra}_m \geq 10^7 \quad \text{(turbulent)} \end{cases}$$

where the mass-transfer Rayleigh number is $\text{Ra}_m = \text{Gr}_m \cdot \text{Sc}$, the mass-transfer Grashof number is:

$$\text{Gr}_m = \frac{g \, |\Delta\rho / \rho| \, L_c^3}{\nu_\text{air}^2}$$

and the Schmidt number is $\text{Sc} = \nu_\text{air} / D_\text{AB}$. Here $L_c = A_\text{floor} / P_\text{floor}$ is the characteristic length (area divided by perimeter), $\nu_\text{air}$ is the kinematic viscosity of air, and $D_\text{AB}$ is the binary diffusion coefficient of fuel vapor in air. The mass transfer coefficient is then $k_m = \text{Sh} \cdot D_\text{AB} / L_c$.

Note that fuel vapor ($M_\text{fuel} \approx 167$ g/mol) is substantially heavier than air ($M_\text{air} \approx 29$ g/mol), which creates a stably stratified layer near the pool surface. This suppresses natural convection and makes the laminar correlation more likely to apply in practice. The model is therefore conservative in its evaporation rate estimate when forced convection (from adjacent equipment fans, airflow through gaps, etc.) is not modelled.

### 2.5 Vapor Mass Balance

The fuel vapor mass in the bay gas space evolves as:

$$\frac{dm_\text{vap}}{dt} = \dot{m}_\text{evap} - \dot{m}_\text{vent}$$

where $\dot{m}_\text{vent} = Q_\text{vent} \cdot C_\text{bay}$ is the vapor mass removed by ventilation (if any), with $Q_\text{vent}$ being the volumetric fresh-air exchange rate.

### 2.6 Vapor Volume Fraction

The bulk vapor concentration is $C_\text{bay} = m_\text{vap} / V_\text{gas}$. The mole (volume) fraction of fuel vapor in the bay atmosphere is computed from the total molar inventory:

$$X_\text{fuel} = \frac{n_\text{vap}}{n_\text{vap} + n_\text{air}} = \frac{m_\text{vap}/M_\text{fuel}}{m_\text{vap}/M_\text{fuel} + (P_\text{amb} \, V_\text{gas})/(R_u \, T) - m_\text{vap}/M_\text{fuel}}$$

The corresponding mass fraction and fuel-to-air ratio are:

$$Y_\text{fuel} = \frac{X_\text{fuel} \, M_\text{fuel}}{X_\text{fuel} \, M_\text{fuel} + (1 - X_\text{fuel}) \, M_\text{air}}$$

$$\text{FAR} = \frac{X_\text{fuel} \, M_\text{fuel}}{(1 - X_\text{fuel}) \, M_\text{air}}$$

### 2.7 Atmospheric Model

The ambient pressure at altitude $h$ follows the International Standard Atmosphere (ISA) barometric formula:

$$P_\text{amb}(h) = P_0 \left(1 - \frac{L \, h}{T_0}\right)^{g / (R_\text{air} \, L)}$$

with $P_0 = 101{,}325$ Pa, $T_0 = 288.15$ K, $L = 0.0065$ K/m, $g = 9.80665$ m/s², $R_\text{air} = 287.058$ J/(kg·K), and the exponent $g/(R_\text{air} L) \approx 5.256$.

---

## 3. Flammability Assessment

### 3.1 Sea-Level Limits

Jet-A has published volumetric flammability limits at standard conditions (Zabetakis, 1965; Nestor, 1967):

$$\text{LEL}_\text{SL} \approx 0.6\% \quad\text{(by volume)}$$
$$\text{UEL}_\text{SL} \approx 4.7\% \quad\text{(by volume)}$$

The flash point of Jet-A is specified as ≥ 38 °C (100 °F) per ASTM D1655; typical production values are 45–48 °C. The auto-ignition temperature is approximately 210 °C (410 °F).

### 3.2 Altitude Correction

At reduced pressure, the flammable range widens. The model uses the constant-partial-pressure approximation, which is conservative: the LEL and UEL expressed as partial pressures of fuel vapor are approximately invariant with total pressure. The altitude-corrected volume-fraction limits are therefore:

$$\text{LEL}_\text{alt} = \frac{\text{LEL}_\text{SL}}{100} \cdot \frac{P_0}{P_\text{amb}(h)}$$

$$\text{UEL}_\text{alt} = \frac{\text{UEL}_\text{SL}}{100} \cdot \frac{P_0}{P_\text{amb}(h)}$$

This means the flammable range expressed in volume fraction expands at altitude, and a lower fuel temperature is sufficient to produce a flammable mixture — a dual effect that increases hazard during cruise.

### 3.3 Temperature Dependence (Burgess–Wheeler Law)

The temperature dependence of flammability limits follows the modified Burgess–Wheeler law (Zabetakis, 1965):

$$L_T = L_{25} \left[ 1 - \frac{0.75}{\Delta H_c} (T - 25) \right]$$

where $L_T$ is the flammability limit (vol %) at temperature $T$ [°C], $L_{25}$ is the limit at 25 °C, and $\Delta H_c$ is the net heat of combustion in kcal/mol. This predicts the LEL decreases by approximately 8% per 100 °C increase in temperature. Nestor (1967) tabulated the flammability limit temperatures for Jet-A across altitude:

| Altitude (kft) | Pressure (psia) | Lower Limit Temp (°C) | Upper Limit Temp (°C) |
|---|---|---|---|
| 0 | 14.7 | 35.0 | 85.0 |
| 10 | 10.4 | 28.6 | 74.1 |
| 20 | 6.9 | 22.1 | 63.2 |
| 30 | 4.3 | 15.7 | 52.3 |
| 40 | 2.6 | 9.2 | 41.4 |

---

## 4. Minimum Ignition Energy

### 4.1 Concentration Dependence

The minimum ignition energy (MIE) for hydrocarbon-air mixtures follows a characteristic U-shaped curve as a function of equivalence ratio. The minimum occurs at slightly fuel-rich conditions (φ ≈ 1.0–1.2) and rises steeply toward both the lean and rich limits. For Jet-A at stoichiometric conditions, the MIE is approximately 0.25 mJ (Lewis and von Elbe, 1987; Kuchta, 1985), consistent with the general observation that most hydrocarbon-air mixtures share a similar minimum MIE near stoichiometric.

The model uses a log-parabolic approximation:

$$\log_{10}(\text{MIE}) = \log_{10}(\text{MIE}_\text{min}) + k \, (X_\text{fuel} - X_\text{stoich})^2$$

where $k$ is calibrated so that $\text{MIE} \approx 100 \times \text{MIE}_\text{min}$ at the lean limit, reflecting the sharp rise observed in experimental data. Outside the flammable range, MIE is treated as infinite.

### 4.2 Temperature and Pressure Dependence

Caltech measurements (Shepherd et al., GALCIT FM97-9; Bane et al., 2011) demonstrated the extreme sensitivity of Jet-A ignition to temperature:

| Jet-A Temperature | Approximate MIE | Regime |
|---|---|---|
| 25 °C | > 100 J | Non-ignitable by small sparks |
| 40 °C | Order of Joules | Near lean limit |
| 55 °C | ~40 mJ | Moderately ignitable |
| 60 °C | < 1 mJ | Easily ignitable |

MIE scales approximately as $\text{MIE} \propto P^{-n}$ where $n \approx 2$ for quiescent stoichiometric mixtures. At cruise altitude (~0.23 atm), MIE is therefore significantly higher than at sea level. The standard design threshold for aircraft fuel tank electrical safety is 200 µJ (0.2 mJ); all potential ignition sources must produce less than this energy.

### 4.3 Ignition Assessment

The mixture is assessed as ignitable if and only if: (a) the vapor volume fraction falls within the flammable range $\text{LEL}_\text{alt} \leq X_\text{fuel} \leq \text{UEL}_\text{alt}$, and (b) the credible spark energy exceeds the MIE at the local concentration: $E_\text{spark} \geq \text{MIE}(X_\text{fuel})$.

---

## 5. Combustion Overpressure — AICC Theory

### 5.1 The AICC Model

If ignition occurs, the model computes the peak overpressure using the Adiabatic Isochoric Complete Combustion (AICC) assumption. This treats the bay as a perfectly rigid, thermally insulated vessel in which the fuel-air mixture burns to chemical equilibrium at constant volume. The AICC pressure is the thermodynamic maximum overpressure achievable by a deflagration and serves as a conservative upper bound for safety analysis.

The AICC calculation enforces conservation of internal energy and volume:

$$U_1 = U_2 \qquad \text{and} \qquad V_1 = V_2$$

where state 1 is the unburned reactant mixture and state 2 is the equilibrium product mixture. Since no work is done ($W = 0$) and no heat is lost ($Q = 0$), the first law reduces to $\Delta U = 0$. The system finds the equilibrium temperature $T_2$ and composition at which the total internal energy of the products (including dissociation) equals that of the reactants.

### 5.2 Pressure Ratio Derivation

For an ideal gas mixture, the equation of state gives:

$$P_2 V = n_2 R_u T_2 \qquad \text{and} \qquad P_1 V = n_1 R_u T_1$$

Dividing:

$$\frac{P_2}{P_1} = \frac{n_2}{n_1} \cdot \frac{T_2}{T_1}$$

For n-dodecane (C₁₂H₂₆) at stoichiometric:

$$\text{C}_{12}\text{H}_{26} + 18.5(\text{O}_2 + 3.76\,\text{N}_2) \longrightarrow 12\,\text{CO}_2 + 13\,\text{H}_2\text{O} + 69.56\,\text{N}_2$$

The reactant moles (per mole of fuel, including N₂) total $n_1 = 1 + 18.5 + 69.56 = 89.06$, and the product moles total $n_2 = 12 + 13 + 69.56 = 94.56$. The mole-change ratio is $n_2/n_1 = 1.062$. With a typical AICC temperature of $T_2 \approx 2{,}800$ K from $T_1 = 298$ K:

$$\frac{P_2}{P_1} \approx 1.062 \times \frac{2800}{298} \approx 10.0$$

Equilibrium dissociation (formation of CO, OH, H, O, NO at high temperatures) reduces $T_2$ and thus the ratio, yielding the commonly observed AICC value of $P_2/P_1 \approx 8\text{–}9.3$ for stoichiometric kerosene-air.

For Jet-A approximated as C₁₂H₂₃:

$$\text{C}_{12}\text{H}_{23} + 17.75(\text{O}_2 + 3.76\,\text{N}_2) \longrightarrow 12\,\text{CO}_2 + 11.5\,\text{H}_2\text{O} + 66.74\,\text{N}_2$$

The stoichiometric fuel-to-air mass ratio is 0.0685, giving an air-to-fuel ratio of 14.59:1. The stoichiometric volume fraction is $X_\text{stoich} = 1/(1 + 17.75 \times 4.76) \approx 0.0118$ (1.18%).

### 5.3 Adiabatic Flame Temperature

| Condition | Without Dissociation | With Equilibrium Dissociation |
|---|---|---|
| Constant-pressure (HP) | ~2,250–2,300 K | ~2,100–2,150 K |
| Constant-volume (UV) | ~2,700–2,900 K | ~2,400–2,600 K |

The constant-volume temperature exceeds the constant-pressure value by approximately 20–25% because no expansion work ($P \, dV$) is performed. This higher temperature drives the larger pressure ratio in confined scenarios.

### 5.4 Why Deflagration, Not Detonation

The AICC model assumes deflagration (subsonic flame propagation), not detonation (supersonic shock-coupled combustion). This is the physically correct model for spark ignition in an aircraft bay for five reasons:

First, direct detonation initiation requires concentrated energy of order $10^4$–$10^5$ J, whereas a spark delivers millijoules. Second, kerosene vapor has a detonation cell size of $\lambda \approx 60$ mm, requiring substantial confinement and obstacle-driven flame acceleration for deflagration-to-detonation transition (DDT). Third, the laminar burning velocity of Jet-A is only 0.4–0.5 m/s, far below the Chapman–Jouguet detonation velocity of ~1,800 m/s. Fourth, aircraft bays are partially confined with gaps and vents that prevent the sustained pressure buildup required for DDT. Fifth, bays lack the repeated obstacles with blockage ratios exceeding 30% that are required for turbulence-driven flame acceleration.

Chapman–Jouguet detonation would produce $P_\text{CJ}/P_1 \approx 15$–20 (with reflected pressures of 30–60×), but this regime is not credible for the spark-ignition scenario considered here.

### 5.5 Impulse Estimation

The pressure-time history of a confined deflagration is approximated as a triangular pulse:

$$P(t) = P_\text{peak} \left(1 - \frac{t}{t_d}\right)$$

The total impulse is:

$$I = \frac{1}{2} \, \Delta P \, t_d$$

The pressure rise time is estimated from the flame traversal time $t_\text{rise} \approx L / S_f$, where $S_f$ is the effective flame speed (laminar burning velocity $S_L$ multiplied by the expansion ratio across the flame, typically $S_f \approx 7 \times 0.45 \approx 3.15$ m/s). The acoustic decay timescale is $t_\text{acoustic} = L / c_\text{prod}$, where $c_\text{prod} = \sqrt{\gamma_\text{prod} R_u T_\text{prod} / M_\text{prod}}$ is the sound speed in the hot products.

---

## 6. Cantera Implementation

### 6.1 Mechanism Selection

The script supports two Cantera mechanisms, compared side by side:

**n-Dodecane (nDodecane_Reitz)** — Bundled with Cantera, zero setup. Contains 100 species and 432 reactions covering both low- and high-temperature n-dodecane (NC12H26) oxidation, including PAH species. Developed by Wang, Ra, Jia, and Reitz (*Fuel* 136, 2014, pp. 25–36). This is a single-component Jet-A surrogate.

**Multi-component surrogate** — When an external YAML mechanism file is provided (e.g., JetSurF 2.0 with 348 species/2,163 reactions, or the Narayanaswamy mechanism with 255 species/2,289 reactions), the script sets up a blended fuel of 60 mol% n-dodecane, 20 mol% toluene, and 20 mol% iso-octane, better representing the paraffinic/aromatic/naphthenic character of real Jet-A (POSF-10325: ~52.7% paraffins, ~16.5% aromatics, ~30.8% naphthenes). If no external file is provided, the script falls back to the bundled mechanism with pure n-dodecane and flags this limitation.

Mechanism files in CHEMKIN format can be converted with:

```bash
python -m cantera.ck2yaml --input=mech.txt --thermo=therm.dat --transport=tran.dat
```

### 6.2 AICC Equilibrium Call

The core Cantera calculation is:

```python
gas = ct.Solution('nDodecane_Reitz.yaml', 'nDodecane_IG')
gas.TP = T1, P1
gas.set_equivalence_ratio(phi, 'NC12H26', 'O2:1.0, N2:3.76')
gas.equilibrate('UV')   # constant internal energy + volume → AICC
P2, T2 = gas.P, gas.T
```

The `equilibrate('UV')` call finds the chemical equilibrium state that minimises the Gibbs function subject to the constraints of fixed internal energy and specific volume. Cantera uses an element-potential method (Villars–Cruise–Smith algorithm) that handles hundreds of species and automatically accounts for dissociation, ionisation, and condensed-phase formation.

### 6.3 Equivalence Ratio Sweep

The script sweeps φ from 0.5 to 2.0 and plots the AICC pressure ratio for both mechanisms, overlaid with the Caltech experimental data and an 85% correction factor (see Section 8).

---

## 7. Comparison with Experimental Data

### 7.1 Caltech Explosion Dynamics Laboratory

Following the TWA Flight 800 disaster (17 July 1996), the NTSB sponsored Prof. Joseph E. Shepherd's group at the California Institute of Technology to conduct the definitive experimental programme on Jet-A vapor explosions. The centre wing fuel tank of TWA 800 contained approximately 50 gallons of residual Jet-A; heat from adjacent air conditioning packs raised the fuel temperature into the flammable range, and an ignition event — attributed to a short circuit in the fuel quantity indication system wiring — initiated a deflagration that caused in-flight structural failure at ~13,800 ft.

The key experimental facility was the 1.18 m³ HYJET vessel, operated at 0.585 bar (simulating 14,000 ft) with Jet-A heated to various temperatures. Published measurements include:

| Equivalence Ratio φ | T_init (°C) | Measured P₂/P₁ |
|---|---|---|
| ~0.65 | 35 | ~3.6 |
| ~0.75 | 40 | ~4.8 |
| ~0.85 | 45 | ~5.9 |
| ~1.0 | 55 | ~7.2 |
| ~1.1 | 60 | ~7.0 |
| ~1.2 | 65 | ~6.2 |

These values are approximate readings from the published figures in GALCIT reports FM97-5 and FM98-6. The peak measured overpressure under optimal conditions was approximately 4 bar (60 psi) absolute, corresponding to $P_2/P_1 \approx 7.2$ near stoichiometric at 0.585 bar.

### 7.2 AICC vs. Experiment

The Sandia National Laboratories combustion model (SAND98-2043, Baer and Gross, 1998) directly compared AICC equilibrium predictions against the Caltech data. The findings were:

Near stoichiometric mixtures: measured values reach 80–90% of the AICC prediction. The AICC overpredicts by 10–20%, attributable to heat loss to vessel walls and incomplete mixing.

Lean mixtures (near flammability limit): measured values fall to 50–70% of AICC due to proportionally greater heat losses and significant incomplete combustion (unburned fuel pockets).

The script overlays the experimental data on the AICC equivalence-ratio sweep plot to visualise this discrepancy directly.

### 7.3 FAA Regulatory Context

FAA report DOT/FAA/AR-98/26 documented that heated centre wing tanks contain a flammable fuel-air mixture approximately 30% of total flight time. This finding, combined with the TWA 800 investigation, drove the promulgation of SFAR 88 (fuel tank system fault tolerance evaluation, 2001) and 14 CFR 25.981 Amendment 25-102 (fuel tank ignition prevention). The Fuel Tank Flammability Reduction rule requires nitrogen-enriched air inerting systems on transport-category aircraft to maintain oxygen concentration below the Limiting Oxygen Concentration (LOC) of approximately 12% at sea level, increasing to ~14.5% at 40,000 ft (DOT/FAA/AR-04/8).

---

## 8. Sources of Conservatism

Every modelling choice in the AICC framework drives the predicted overpressure upward relative to reality. The following conservatisms are inherent in the model and should be understood when interpreting results:

**Zero heat loss.** The AICC model assumes perfectly adiabatic walls. In reality, the bay structure, equipment, wiring, and adjacent bays absorb heat during the combustion event. Based on the Caltech experimental programme, this reduces peak pressure by 10–20% near stoichiometric conditions. For engineering use, multiplying the AICC result by 0.85 provides a reasonable best-estimate correction for near-stoichiometric mixtures.

**Complete combustion.** AICC assumes all fuel reacts to equilibrium products. In lean mixtures (φ < 0.8), significant unburned fuel remains, and measured pressures can be 30–50% below AICC. The correction is concentration-dependent and ranges from 0.50 at the lean limit to 0.95 near stoichiometric.

**Uniform mixture.** The model assumes the entire bay gas volume is at the computed average concentration. In reality, fuel vapor is 5.8× heavier than air and stratifies, producing a concentration gradient. The local equivalence ratio near the ignition source may differ substantially from the well-mixed average. This can be either conservative or non-conservative depending on the ignition location.

**Instantaneous combustion.** AICC does not model the finite flame propagation time. A real deflagration in a 1 m bay takes on the order of 100–300 ms, during which pressure can be partially relieved through any vents, gaps, or structural compliance. The AICC peak is only achieved if the bay is perfectly sealed for the duration of the event.

**Single-component surrogate.** The n-dodecane surrogate has a higher hydrogen-to-carbon ratio (H/C = 2.17) than real Jet-A (H/C ≈ 1.94), which affects the equilibrium product distribution and adiabatic flame temperature. However, the effect on peak pressure ratio is small — typically less than 3%.

**No radiative heat loss.** At AICC temperatures of 2,400–2,600 K, radiative emission (primarily from CO₂ and H₂O bands, and any soot) removes energy from the products. This is not accounted for in the equilibrium calculation.

**Static initial conditions.** The model does not account for fuel sloshing, tank pressurisation transients, or dynamic leak rates that vary with altitude and aircraft manoeuvres. The user-specified leak rate is treated as constant.

---

## 9. Installation and Usage

### 9.1 Requirements

Python 3.9 or later is required. Install dependencies:

```bash
pip install -r requirements.txt
```

Cantera installation follows the official guide at https://cantera.org/install/. On most platforms:

```bash
pip install cantera
```

If Cantera is not installed, the script will still run and produce all pool, vapor, and flammability results, but will skip the combustion overpressure analysis.

### 9.2 Configuration

All user inputs are defined at the top of the `main()` function in `bay_fuel_leak_model.py`:

```python
bay_length = 1.0        # [m]
bay_width  = 0.5        # [m]
bay_height = 0.4        # [m]
D_drain    = 0.010      # Drain hole diameter [m]
Q_leak_mL_min = 50.0    # Leak rate [mL/min]
T_bay_C   = 40.0        # Bay temperature [°C]
alt_ft    = 35000.0     # Altitude [ft]
E_spark_mJ = 0.25       # Spark energy [mJ]
```

Fuel property functions are defined as standalone Python functions near the top of the file. Replace the placeholder Antoine-type vapor pressure correlation, liquid density, viscosity, and diffusivity functions with your own experimentally validated correlations.

To use a multi-component surrogate mechanism, set `MULTI_MECH_FILE` to the path of your converted YAML file (e.g., JetSurF 2.0 or Narayanaswamy mechanism).

### 9.3 Running

```bash
python bay_fuel_leak_model.py
```

The script produces console output with all computed quantities and saves five PNG figures to the working directory.

### 9.4 Output Figures

1. **fig1_pool_buildup.png** — Pool depth, volume, flow balance, and cumulative mass accounting vs. time.
2. **fig2_vapor_concentration.png** — Volume fraction, mass concentration, mass fraction, and fuel-to-air ratio vs. time with flammability limits.
3. **fig3_mie_assessment.png** — MIE vs. concentration curve and MIE vs. time with spark energy threshold.
4. **fig4_aicc_comparison.png** — AICC pressure ratio vs. equivalence ratio for both mechanisms, overlaid with Caltech experimental data and the 85% heat-loss correction.
5. **fig5_leak_rate_parametric.png** — Parametric sweep of leak rate showing effect on pool depth, vapor concentration, and time to reach LEL.

---

## 10. References

### Regulatory Documents

FAA (2008). Advisory Circular AC 25.981-1D, "Fuel Tank Ignition Source Prevention Guidelines." Federal Aviation Administration.

FAA (2008). Advisory Circular AC 25.981-2A, "Fuel Tank Flammability Reduction Means." Federal Aviation Administration.

FAA (2010). Advisory Circular AC 120-98A, "Fuel Tank Flammability Reduction (FTFR) Rule." Federal Aviation Administration.

FAA (2001). Special Federal Aviation Regulation No. 88, "Fuel Tank System Fault Tolerance Evaluation Requirements." 14 CFR Part 21, 66 FR 23086.

ECFR. 14 CFR Part 25, Appendix N, "Fuel Tank Flammability Exposure and Reliability Analysis."

### Caltech Explosion Dynamics Laboratory

Shepherd, J.E., Krok, J.C., and Lee, J.J. (1997). "Jet A Explosion Experiments: Laboratory Testing." GALCIT Report FM97-5, California Institute of Technology. NTSB Exhibit 20D. DOI: 10.7907/86gm-wr43.

Shepherd, J.E., Krok, J.C., and Lee, J.J. (1999). "Spark Ignition Energy Measurements in Jet A." GALCIT Report FM97-9, California Institute of Technology. NTSB Exhibit 20T. DOI: 10.7907/sf5x-p228.

Shepherd, J.E. et al. (1998). "Results of 1/4-Scale Experiments, Vapor Simulant and Liquid Jet A Tests." GALCIT Report FM98-6, California Institute of Technology. NTSB Exhibit 20O. DOI: 10.7907/22et-fz32.

Nuyt, C.D., Shepherd, J.E., and Lee, J.J. (2000). "Flash Point and Chemical Composition of Aviation Kerosene (Jet A)." GALCIT Report FM99-4, California Institute of Technology.

Bane, S.P.M., Ziegler, J.L., and Shepherd, J.E. (2011). "Experimental Investigation of Spark Ignition Energy in Kerosene, Hexane, and Hydrogen." *Journal of Loss Prevention in the Process Industries*, 26(2), pp. 290–294.

### Sandia National Laboratories

Baer, M.R. and Gross, R.J. (1998). "A Combustion Model for the TWA 800 Center-Wing Fuel Tank Explosion." SAND98-2043, Sandia National Laboratories.

Baer, M.R. and Gross, R.J. (2000). "Extended Modeling Studies of the TWA 800 CWT Explosion." SAND2000-0445, Sandia National Laboratories.

### FAA Technical Reports

Fuel Flammability Task Group (1998). "A Review of the Flammability Hazard of Jet A Fuel Vapor in Civil Transport Aircraft Fuel Tanks." DOT/FAA/AR-98/26. Available: https://www.fire.tc.faa.gov/pdf/ar98-26.pdf

Summer, S.M. (2004). "Limiting Oxygen Concentration Required to Inert Jet Fuel Vapors at Reduced Fuel Tank Pressures." DOT/FAA/AR-04/8.

### Flammability and Ignition

Zabetakis, M.G. (1965). *Flammability Characteristics of Combustible Gases and Vapors*. Bureau of Mines Bulletin 627, Pittsburgh, PA.

Nestor, L. (1967). "Investigation of Turbine Fuel Flammability Within Aircraft Fuel Tanks." Final Report DS-67-7, Naval Air Propulsion Test Center.

Lewis, B. and von Elbe, G. (1987). *Combustion, Flames and Explosions of Gases*, 3rd edition. Academic Press, New York. ISBN 978-0124467514.

Kuchta, J.M. (1985). *Investigation of Fire and Explosion Accidents in the Chemical, Mining, and Fuel-Related Industries — A Manual*. Bureau of Mines Bulletin 680. NTIS PB87113940.

Coward, H.F. and Jones, G.W. (1952). "Limits of Flammability of Gases and Vapors." Bureau of Mines Bulletin 503.

### Cantera

Goodwin, D.G., Moffat, H.K., Schoegl, I., Speth, R.L., and Weber, B.W. (2025). *Cantera: An Object-oriented Software Toolkit for Chemical Kinetics, Thermodynamics, and Transport Processes*. Version 3.2.0. https://www.cantera.org. DOI: 10.5281/zenodo.17620923.

### Kinetic Mechanisms

Wang, H., Ra, Y., Jia, M., and Reitz, R.D. (2014). "Development of a reduced n-dodecane-PAH mechanism and its application for n-dodecane soot predictions." *Fuel*, 136, pp. 25–36.

Wang, H. et al. (2010). JetSurF 2.0: A Jet Surrogate Fuel Model. Available: https://web.stanford.edu/group/haiwanglab/JetSurF/JetSurF2.0/

Narayanaswamy, K., Pepiot, P., and Pitsch, H. (2014). "A chemical mechanism for low to high temperature oxidation of n-dodecane as a component of transportation fuel surrogates." *Combustion and Flame*, 161(4), pp. 866–884.

CRECK Modeling Group (2020). Detailed Kinetic Mechanisms. Politecnico di Milano. Available: https://www.creckmodeling.polimi.it/menu-kinetics/menu-kinetics-detailed-mechanisms/

Westbrook, C.K. et al. (2009). "A comprehensive detailed chemical kinetic reaction mechanism for combustion of n-alkane hydrocarbons from n-octane to n-hexadecane." *Combustion and Flame*, 156(1), pp. 181–199.

---

## License

This tool is provided for engineering analysis and hazard assessment. The user is responsible for validating all results against applicable regulatory requirements and experimental data before use in certification or safety-critical decisions.
