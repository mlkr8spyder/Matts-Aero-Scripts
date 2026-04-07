# Synthetic Fuel System — Design Document

## Purpose

This document defines a simplified but physically representative 5-tank aircraft fuel system used to generate synthetic test data for validating fuel gauging error analysis tools. Every dimension, coordinate, and parameter is intentionally synthetic — no CUI data is present.

---

## Aircraft Coordinate System

All coordinates use standard aircraft body axes:

| Axis | Name             | Positive Direction | Units  |
|------|------------------|--------------------|--------|
| X    | Fuselage Station (FS) | Aft               | inches |
| Y    | Buttline (BL)    | Right (starboard)  | inches |
| Z    | Waterline (WL)   | Up                 | inches |

Origin: Nose datum (FS 0), aircraft centerline (BL 0), arbitrary waterline datum.

---

## Tank Layout — Plus Sign Configuration

```
            ┌─────────────┐
            │   TANK 1    │
            │  (Forward)  │
            └──────┬──────┘
                   │
    ┌──────────┐ ┌─┴────────┐ ┌──────────┐
    │  TANK 2  │ │  TANK 3  │ │  TANK 4  │
    │  (Left)  │ │ (Center) │ │ (Right)  │
    └──────────┘ └─┬────────┘ └──────────┘
                   │
            ┌──────┴──────┐
            │   TANK 5    │
            │   (Aft)     │
            └─────────────┘
```

**Design rationale for the plus-sign layout:**

1. The three lateral tanks (T2, T3, T4) span the aircraft width, making them sensitive to roll attitude.
2. The forward (T1) and aft (T5) tanks add pitch sensitivity.
3. Tank 3 (Center) is the collector — lowest elevation — all other tanks gravity-feed into it.
4. Different tank elevations create natural head-height differences for gravity transfer.

---

## Tank Definitions

All tanks are rectangular prisms defined by their min/max coordinates.

### Tank 1 — Forward

| Parameter | Value |
|-----------|-------|
| FS range  | 195.0 → 225.0 (30.0" long) |
| BL range  | -15.0 → 15.0 (30.0" wide) |
| WL range  | 88.0 → 104.0 (16.0" tall) |
| Gross volume | 14,400 in³ (62.34 gal) |
| Floor elevation | WL 88.0 |
| Head above T3 floor | 8.0" |

**Corner points (FS, BL, WL):**
```
Bottom face:                    Top face:
(195, -15, 88)  (195, 15, 88)  (195, -15, 104)  (195, 15, 104)
(225, -15, 88)  (225, 15, 88)  (225, -15, 104)  (225, 15, 104)
```

### Tank 2 — Left

| Parameter | Value |
|-----------|-------|
| FS range  | 235.0 → 285.0 (50.0" long) |
| BL range  | -62.0 → -22.0 (40.0" wide) |
| WL range  | 85.0 → 103.0 (18.0" tall) |
| Gross volume | 36,000 in³ (155.84 gal) |
| Floor elevation | WL 85.0 |
| Head above T3 floor | 5.0" |

**Corner points (FS, BL, WL):**
```
Bottom face:                        Top face:
(235, -62, 85)  (235, -22, 85)     (235, -62, 103)  (235, -22, 103)
(285, -62, 85)  (285, -22, 85)     (285, -62, 103)  (285, -22, 103)
```

### Tank 3 — Center (Collector)

| Parameter | Value |
|-----------|-------|
| FS range  | 235.0 → 285.0 (50.0" long) |
| BL range  | -20.0 → 20.0 (40.0" wide) |
| WL range  | 80.0 → 100.0 (20.0" tall) |
| Gross volume | 40,000 in³ (173.16 gal) |
| Floor elevation | WL 80.0 (lowest — collector) |
| Role | Collector tank, gravity-fed from all others |

**Corner points (FS, BL, WL):**
```
Bottom face:                        Top face:
(235, -20, 80)  (235, 20, 80)     (235, -20, 100)  (235, 20, 100)
(285, -20, 80)  (285, 20, 80)     (285, -20, 100)  (285, 20, 100)
```

### Tank 4 — Right

| Parameter | Value |
|-----------|-------|
| FS range  | 235.0 → 285.0 (50.0" long) |
| BL range  | 22.0 → 62.0 (40.0" wide) |
| WL range  | 85.0 → 103.0 (18.0" tall) |
| Gross volume | 36,000 in³ (155.84 gal) |
| Floor elevation | WL 85.0 |
| Head above T3 floor | 5.0" |

**Corner points (FS, BL, WL):**
```
Bottom face:                       Top face:
(235, 22, 85)  (235, 62, 85)     (235, 22, 103)  (235, 62, 103)
(285, 22, 85)  (285, 62, 85)     (285, 22, 103)  (285, 62, 103)
```

### Tank 5 — Aft

| Parameter | Value |
|-----------|-------|
| FS range  | 295.0 → 335.0 (40.0" long) |
| BL range  | -17.5 → 17.5 (35.0" wide) |
| WL range  | 83.0 → 105.0 (22.0" tall) |
| Gross volume | 30,800 in³ (133.33 gal) |
| Floor elevation | WL 83.0 |
| Head above T3 floor | 3.0" |

**Corner points (FS, BL, WL):**
```
Bottom face:                          Top face:
(295, -17.5, 83)  (295, 17.5, 83)   (295, -17.5, 105)  (295, 17.5, 105)
(335, -17.5, 83)  (335, 17.5, 83)   (335, -17.5, 105)  (335, 17.5, 105)
```

---

## Volume Summary

| Tank | Gross CAD (in³) | Gross (gal) | Structural (gal) | Ullage (gal) | Unusable (gal) | Usable (gal) | Reduction |
|------|----------------:|------------:|------------------:|-------------:|---------------:|--------------:|----------:|
| T1 — Forward | 14,400 | 62.34 | 0.19 | 1.25 | 0.94 | 59.96 | 3.82% |
| T2 — Left | 36,000 | 155.84 | 0.47 | 3.12 | 2.34 | 149.92 | 3.80% |
| T3 — Center | 40,000 | 173.16 | 0.52 | 3.46 | 2.60 | 166.58 | 3.80% |
| T4 — Right | 36,000 | 155.84 | 0.47 | 3.12 | 2.34 | 149.92 | 3.80% |
| T5 — Aft | 30,800 | 133.33 | 0.40 | 2.67 | 2.00 | 128.27 | 3.80% |
| **Total** | **157,200** | **680.52** | **2.04** | **13.61** | **10.21** | **654.65** | **3.80%** |

The usable volume is derived from the gross CAD volume through four successive reduction stages:

- **Structural displacement (~0.3%):** Volume occupied by internal hardware (probes, baffles, sump pickups, boost-pump canisters, wiring). Distributed throughout the tank. Controlled by `STRUCTURAL_FRACTION = 0.003` in `tank_geometry.py`.
- **Ullage expansion reserve (2.0%):** Top band reserved for thermal expansion and venting. The max fill waterline is `wl_max - (height × 0.02)`. Fuel level cannot exceed this boundary under normal operations.
- **Unusable fuel (1.5%):** Fuel trapped below the lowest pickup. Present but not consumable or reliably indicated. The unusable zone spans from the tank floor to `wl_min + (height × 0.015)`.

The `volume_reduction_breakdown()` function in `tank_geometry.py` computes all four stages and returns the per-tank and total pipeline values shown above.

---

## Gravity Transfer Architecture

```
  T1 (WL 88) ──┐
                │  gravity
  T2 (WL 85) ──┼──→ T3 (WL 80)  ──→  Engine feed
                │
  T4 (WL 85) ──┤
                │
  T5 (WL 83) ──┘
```

All auxiliary tanks feed into Tank 3 via gravity. The head height differential drives flow:

| From | To | Head Difference | Relative Flow Rate |
|------|-----|----------------|--------------------|
| T1 → T3 | Forward to Center | 8.0" | Fastest |
| T2 → T3 | Left to Center    | 5.0" | Medium |
| T4 → T3 | Right to Center   | 5.0" | Medium |
| T5 → T3 | Aft to Center     | 3.0" | Slowest |

Transfer begins when the receiving port in T3 is uncovered (fuel level drops below the port elevation). Transfer stops when the source tank is empty to its unusable fuel level.

---

## Capacitance Probe Placement

### Probe Type Summary

| Tank | Probe Type | Physical Probes | Notes |
|------|-----------|----------------|-------|
| T1 — Forward | Real | 1 | Single probe, slight diagonal mount |
| T2 — Left    | Real | 1 | Single probe, slight diagonal mount |
| T3 — Center  | Real-Pseudo Combination | 2 (upper + lower) | Overlap blend zone |
| T4 — Right   | Real | 1 | Single probe, slight diagonal mount |
| T5 — Aft     | Pure Pseudo | 0 | Projected from T3 probes |

### Unified Probe Location Table

| Probe | Tank | Physical Base (FS, BL, WL) | Physical Top (FS, BL, WL) | Phys. Length | Sense Base WL | Sense Top WL | Sense Length | Tilt |
|-------|------|---------------------------|---------------------------|-------------:|--------------:|-------------:|-------------:|-----:|
| T1_probe | T1 — Forward | (210.0, -0.5, 88.24) | (210.0, 0.5, 103.68) | 15.44" | 88.74 | 103.43 | 14.69" | 3.71° |
| T2_probe | T2 — Left | (260.0, -42.5, 85.27) | (260.0, -41.5, 102.64) | 17.37" | 85.77 | 102.39 | 16.62" | 3.30° |
| T3_lower | T3 — Center | (260.0, -0.5, 80.30) | (260.0, 0.0, 92.00) | 11.70" | 80.80 | 91.80 | 11.00" | 2.45° |
| T3_upper | T3 — Center | (260.0, 0.0, 90.00) | (260.0, 0.5, 99.60) | 9.60" | 90.20 | 99.35 | 9.15" | 2.98° |
| T4_probe | T4 — Right | (260.0, 41.5, 85.27) | (260.0, 42.5, 102.64) | 17.37" | 85.77 | 102.39 | 16.62" | 3.30° |

### Sense-Point Offsets

A physical capacitance probe is longer than its electrically active sensing region. The sense electrodes do not extend all the way to the mechanical mounting flanges — there is a dead zone at each end where the probe body exists but no capacitance measurement occurs. The **sense-point offsets** define the distance from each physical end of the probe to the start of the active sensing region:

- **Base offset (`sense_offset_base`):** Distance from the physical base to the lower sense point. Default: 0.50".
- **Top offset (`sense_offset_top`):** Distance from the physical top to the upper sense point. Default: 0.25".

The capacitance electronics report fuel height relative to the lower sense point, not the physical base of the probe. This means the indicated height range is shorter than the physical probe length by the sum of both offsets. The `sensed_height_on_probe()` function converts a physical waterline to the height that the electronics would report, and `indicated_to_physical_height()` reverses the conversion.

Non-default offsets are used on the T3 probes to account for their closer spacing in the blend zone:
- T3_lower uses `sense_offset_top = 0.20"` (reduced from 0.25" to maximize coverage approaching the blend zone)
- T3_upper uses `sense_offset_base = 0.20"` (reduced from 0.50" to start sensing closer to the blend zone entry)

### Probe Placement Rationale

Probes are mounted near the lateral and longitudinal center of each tank to minimize attitude sensitivity. A slight diagonal mount (tilted ~1-2° from vertical) improves measurement resolution and helps shed condensation. Probes extend from just above the unusable fuel zone to just below the ullage reserve ceiling.

### Tank 1 — Forward: Single Real Probe

| Parameter | Value |
|-----------|-------|
| Mount base (FS, BL, WL) | (210.0, -0.5, 88.24) |
| Mount top (FS, BL, WL)  | (210.0, 0.5, 103.68) |
| Active length | 15.44" |
| Sense offsets | base 0.50", top 0.25" |
| Sense length | 14.69" (WL 88.74 → 103.43) |
| Tilt | 3.71° |
| Height range | WL 88.24 → 103.68 |
| Unusable zone | WL 88.0 → 88.24 (0.24" = 1.5% of 16") |
| Ullage zone   | WL 103.68 → 104.0 (0.32" = 2% of 16") |

### Tank 2 — Left: Single Real Probe

| Parameter | Value |
|-----------|-------|
| Mount base (FS, BL, WL) | (260.0, -42.5, 85.27) |
| Mount top (FS, BL, WL)  | (260.0, -41.5, 102.64) |
| Active length | 17.37" |
| Sense offsets | base 0.50", top 0.25" |
| Sense length | 16.62" (WL 85.77 → 102.39) |
| Tilt | 3.30° |
| Height range | WL 85.27 → 102.64 |
| Unusable zone | WL 85.0 → 85.27 (0.27" = 1.5% of 18") |
| Ullage zone   | WL 102.64 → 103.0 (0.36" = 2% of 18") |

### Tank 3 — Center: Real-Pseudo Combination (Two Probes)

**Lower Probe:**

| Parameter | Value |
|-----------|-------|
| Mount base (FS, BL, WL) | (260.0, -0.5, 80.30) |
| Mount top (FS, BL, WL)  | (260.0, 0.0, 92.00) |
| Active length | 11.70" |
| Sense offsets | base 0.50", top 0.20" |
| Sense length | 11.00" (WL 80.80 → 91.80) |
| Tilt | 2.45° |
| Height range | WL 80.30 → 92.00 |

**Upper Probe:**

| Parameter | Value |
|-----------|-------|
| Mount base (FS, BL, WL) | (260.0, 0.0, 90.00) |
| Mount top (FS, BL, WL)  | (260.0, 0.5, 99.60) |
| Active length | 9.60" |
| Sense offsets | base 0.20", top 0.25" |
| Sense length | 9.15" (WL 90.20 → 99.35) |
| Tilt | 2.98° |
| Height range | WL 90.00 → 99.60 |

**Blend Zone:** WL 90.00 → 92.00 (2.0" overlap)
- Below WL 90.0: lower probe only
- WL 90.0 → 92.0: linear blend (weight transitions from lower to upper)
- Above WL 92.0: upper probe only

**Blend formula:**
```
w_upper = (h - 90.0) / (92.0 - 90.0)   # 0 at WL 90, 1 at WL 92
w_lower = 1 - w_upper
h_effective = w_lower * h_lower + w_upper * h_upper
```

### Tank 4 — Right: Single Real Probe

| Parameter | Value |
|-----------|-------|
| Mount base (FS, BL, WL) | (260.0, 41.5, 85.27) |
| Mount top (FS, BL, WL)  | (260.0, 42.5, 102.64) |
| Active length | 17.37" |
| Sense offsets | base 0.50", top 0.25" |
| Sense length | 16.62" (WL 85.77 → 102.39) |
| Tilt | 3.30° |
| Height range | WL 85.27 → 102.64 |

### Tank 5 — Aft: Pure Pseudo Probe

| Parameter | Value |
|-----------|-------|
| Physical probes | None |
| Reference location (FS, BL, WL) | (315.0, 0.0, —) |
| Source probes | T3 lower and upper (blended) |
| dx from T3 probe | +55.0" (aft) |
| dy from T3 probe | 0.0" |
| Projection formula | `z_fuel_T5 = z_fuel_T3 + dx * tan(pitch) + dy * tan(roll)` |
| Valid height range | WL 83.0 → 105.0 (clamped to tank bounds) |

**Pseudo probe error sources:** The projection accuracy degrades with increasing pitch angle because the `tan(pitch)` term amplifies with the large dx offset (55"). Roll has minimal effect due to dy ≈ 0.

---

## Fuel Properties (Synthetic Reference Values)

| Property | Value | Notes |
|----------|-------|-------|
| Fuel type | Jet-A equivalent | Generic kerosene properties |
| Nominal density | 6.71 lb/gal (0.803 kg/L) | At 60°F reference |
| Lab-measured density | 6.71 lb/gal | Ground truth for density error analysis |
| Dielectric constant (dry air) | 1.0 | Reference |
| Dielectric constant (Jet-A) | 2.05 | Nominal at 60°F |
| Density-dielectric model | ρ = 4.667 × κ_fuel - 2.857 | Linear model in lb/gal; calibrated so ρ(2.05) = 6.71 lb/gal |

### Temperature Compensation Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Reference temperature | 60°F | Calibration baseline |
| dρ/dT | -0.0035 lb/gal/°F | Jet-A thermal expansion coefficient |
| dκ/dT | -0.0011 /°F | Dielectric temperature coefficient |

These coefficients are defined in the `FuelProperties` dataclass (`density_temp_coef` and `dielectric_temp_coef`). Temperature compensation is controlled by the `enable_temperature_term` flag. When disabled (the default), temperature effects are assumed to be implicitly captured through the dielectric measurement itself.

### Density-Dielectric Relationship

Capacitance probes measure the dielectric constant of the fluid between their electrodes. Because both density and dielectric constant are functions of molecular packing, there is a strong linear relationship between them for a given fuel type. The gauging system exploits this to infer fuel density from the measured dielectric constant without requiring a separate densitometer.

The linear model used in this system is:

```
ρ = 4.667 × κ - 2.857    [lb/gal]
```

This model is calibrated at two points spanning the expected Jet-A property range:

| Calibration Point | Dielectric (κ) | Density (ρ) |
|-------------------|----------------:|--------------:|
| Nominal (60°F) | 2.05 | 6.71 lb/gal |
| Light fuel / warm | 1.90 | 6.01 lb/gal |

Temperature is implicitly handled when the dielectric measurement already carries temperature information — as fuel warms, both κ and ρ decrease together, and the linear model tracks this movement along the calibration line. An explicit temperature correction term is needed only when the dielectric measurement is stale or comes from a reference source at a different temperature than the fuel being measured. The `enable_temperature_term` flag in `FuelProperties` controls whether the explicit correction `dρ/dT × (T - T_ref)` is applied.

---

## Attitude Envelope

The H-V tables are generated across this attitude grid:

| Parameter | Range | Step | Count |
|-----------|-------|------|-------|
| Pitch | -6° to +6° | 1° | 13 |
| Roll  | -8° to +8° | 1° | 17 |
| **Total table combinations** | | | **221 per tank** |

Positive pitch = nose up (fuel moves aft).
Positive roll = right wing down (fuel moves to starboard/right).

---

## Known Error Sources (Embedded in Synthetic Data)

These error patterns are deliberately injected so the analysis tools can be validated:

1. **Density bias:** System-computed density is 0.3% high (systematic offset)
2. **Probe nonlinearity:** T2 left probe has a ±0.15" height error that peaks at 40-60% fill (simulating probe contamination)
3. **Blend zone discontinuity:** T3 has a 0.08" step error at the blend transition boundaries (WL 90 and 92)
4. **Attitude-correlated error:** T5 pseudo projection has amplified error at pitch > 3° due to the large dx offset
5. **Table quantization:** H-V tables use 0.5" height steps; interpolation between steps introduces up to 0.2% volume error
6. **Temperature drift:** A slow dielectric drift of ±0.5% over the defuel sequence simulating temperature change

---

## File Outputs

| File | Format | Contents |
|------|--------|----------|
| `data/tank_system.mat` | MATLAB v5 | All H-V tables, probe definitions, tank geometry |
| `data/tank_system.json` | JSON | Same data in Python-friendly format |
| `data/defuel_sequence.mat` | MATLAB v5 | Simulated defuel time history (1000 samples, 51 columns) |
| `data/defuel_sequence.csv` | CSV | Same data in CSV format for non-MATLAB workflows |
| `data/refuel_sequence.mat` | MATLAB v5 | Simulated refuel time history (800 samples, 51 columns) |
| `data/refuel_sequence.csv` | CSV | Same data in CSV format |
| `config/system_config.yaml` | YAML | Variable name mappings, tank metadata, and injected error catalog |

---

## Single-Point Refuel System

### Architecture

```
External Fuel Supply
        │
        ▼
┌──────────────────┐
│  Single-Point    │  Location: FS 240, BL 0, WL 78
│  Refuel Adapter  │  Supply pressure: 55 psi
│  (SPRA)          │  Max flow: 60 GPM total
└────────┬─────────┘
         │
    Precheck Valve (master shutoff)
         │
    ┌────┴────────────────────────────┐
    │        MANIFOLD (WL 78)        │
    ├──────┬──────┬──────┬───────────┤
    │      │      │      │           │
   SOV1   SOV2   SOV3   SOV4       SOV5
    │      │      │      │           │
   [T1]   [T2]   [T3]   [T4]       [T5]
    │      │      │      │           │
   HLS1   HLS2   HLS3   HLS4      HLS5
```

- **SOV** = Solenoid Shutoff Valve (normally open during refuel)
- **HLS** = High-Level Sensor (float-type, trips at ullage boundary)

### Flow Distribution Model

Flow to each tank is pressure-driven:
```
Q_tank = valve_position × k × (P_supply - P_head)
P_head = 0.036 × density × fuel_height_above_manifold
```

Tanks at higher elevation (T1 at WL 88) have less back-pressure than
the manifold, so they fill faster. Tank 3 (WL 80, below the manifold)
fills slowest because it has the highest back-pressure.

### Fill Completion Order (from simulation)

All tanks fill simultaneously via the pressurized manifold. Tanks reach their
high-level sensor at different times based on back-pressure and volume:

| Order | Tank | HLS Trip Time | Reason |
|-------|------|---------------|--------|
| 1st | T1 Forward | ~280s | Smallest tank + highest elevation = least back-pressure |
| 2nd | T5 Aft | ~550s | Moderate elevation, medium volume |
| 3rd | T2 Left | ~636s | Medium elevation, large volume |
| 3rd | T4 Right | ~636s | Symmetric with T2 |
| 4th | T3 Center | ~690s | Lowest elevation (WL 80) = highest back-pressure, fills last |

Note: The `system_config.yaml` field `refuel.fill_order` describes the sequence
in which tanks are *prioritized* during a sequenced refuel (T3 first as collector),
which is distinct from the simultaneous-fill completion order above.

### High-Level Sensors

| Parameter | Value |
|-----------|-------|
| Type | Float switch |
| Trigger WL | Tank max_fill_wl (= wl_max - ullage_height) |
| Hysteresis | 0.3" (reset at trigger - 0.3") |
| Response | Trips → commands shutoff valve closed |
| Failure modes | Stuck tripped, stuck untripped |

### Shutoff Valves

| Parameter | Value |
|-----------|-------|
| Type | Solenoid, normally open |
| Close time | 0.5 seconds |
| Open time | 0.3 seconds |
| Flow capacity | 15 GPM per valve |
| Failure modes | Stuck open, stuck closed |

---

## Probe Failure Detection (BIT)

### Failure Modes Detected

| Mode | Condition | Response |
|------|-----------|----------|
| Open Circuit | Reading < -0.1" | Use last known good (LKG) |
| Short Circuit | Reading > max_height + 0.5" | Use LKG |
| Rate Exceedance | |dh/dt| > 2.0 in/s | Use LKG |
| Stale Data | |Δh| < 0.01" for > 30s | Flag warning |
| Out of Range | Reading outside [0, active_length] | Clip to bounds |

### Redundancy Strategy

| Tank | Primary | Backup | Failure Fallback |
|------|---------|--------|------------------|
| T1 | T1_probe | None | Hold LKG |
| T2 | T2_probe | None | Hold LKG |
| T3 | T3_lower + T3_upper (blended) | Either probe alone | Use surviving probe |
| T4 | T4_probe | None | Hold LKG |
| T5 | T3 projection (pseudo) | None | Hold LKG |

---

## Simulink Model Architecture

The Simulink model is built programmatically via MATLAB scripts in `matlab/scripts/`.
It uses a MATLAB Project (`.prj`) for path management and a Simulink Data Dictionary
(`.sldd`) as the single source of truth for all parameters, bus definitions, and
lookup table objects. See `docs/simulink_model_schema.md` for the full schema and
`docs/simulink_setup_instructions.md` for step-by-step setup.

### Model Hierarchy

The top-level model `FuelGaugingSystem.slx` references 8 child models:

| Referenced Model | Instances | Purpose |
|-----------------|-----------|---------|
| `ProbeModel_Real.slx` | 3 (T1, T2, T4) | Capacitance probe: `h = clamp(fuel_WL - base_WL, 0, active_len) + noise` |
| `ProbeModel_Combo.slx` | 1 (T3) | Dual-probe blend: linear weight transition in WL 90-92 |
| `ProbeModel_Pseudo.slx` | 1 (T5) | Trigonometric projection: `z_T5 = z_T3 + dx×tan(pitch) + dy×tan(roll)` |
| `ProbeFailureDetector.slx` | 5 | Open/short circuit, rate exceedance, stale data detection with LKG fallback |
| `HV_TableLookup.slx` | 5 | 3-D n-D Lookup Table (height × pitch × roll → volume) from data dictionary |
| `DensityComputation.slx` | 1 | `ρ = 4.667×κ - 2.857` with 0.3% bias |
| `WeightSummation.slx` | 1 | Per-tank `weight = volume/231 × density`, sum to total |
| `RefuelSystem.slx` | 1 | High-level sensors, shutoff valve logic, all-full detection |

### Data Dictionary (`FuelGaugingData.sldd`)

All model parameters are stored in the data dictionary — nothing in the base workspace:

- **6 bus definitions:** AttitudeBus, ProbeReadingBus, TankIndicationBus, SystemIndicationBus, BIT_StatusBus, RefuelStatusBus
- **24 Simulink.Parameter objects:** thresholds, physical constants, calibration values
- **5 Simulink.LookupTable objects:** 3-D H-V tables (~46K data points total)
- **TankParams structure:** per-tank geometry, probe bounds, max fill waterlines

### Running the Simulink Model

```matlab
cd('path/to/Gauging/synthetic_fuel_system/matlab')

% 1. Create project structure and data dictionary
run('scripts/setup_project.m')
run('scripts/build_data_dictionary.m')

% 2. Build all Simulink models
run('scripts/build_simulink_model.m')

% 3. Validate the build
run('scripts/validate_model.m')

% 4. Load simulation data and run
[sim_data, meta] = load_sequence_data('defuel');
out = sim('FuelGaugingSystem');
```

### Standalone MATLAB Validation

For environments without Simulink, `matlab/scripts/gauging_system_standalone.m`
implements the same gauging, refuel, and probe failure logic as pure MATLAB code
and generates comparison plots.

---

## Complete File Inventory

### Python Source (`src/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Package initialization |
| `tank_geometry.py` | Tank definitions (5 rectangular prisms), volume computation for tilted planes, CG calculation, probe models with sense-point offsets, volume reduction breakdown |
| `hv_table_generator.py` | Generates 1,105 H-V lookup tables (13 pitch × 17 roll × 5 tanks) with CG data; saves to `.mat` and `.json` |
| `gauging_model.py` | Full capacitance gauging simulation chain with 7 configurable error sources; table interpolation engine |
| `simulate_sequences.py` | Generates defuel (1000 samples) and refuel (800 samples) time history datasets with phased tank drain/fill |
| `refuel_system.py` | Single-point refuel controller, high-level sensors, shutoff valves, probe failure detection (BIT) |
| `visualize_3d.py` | 3D matplotlib visualization: 4-view layout, fill sequence, attitude comparison, refuel diagram, probe detail |
| `plot_validation.py` | 8 publication-quality 2D analysis plots (error timeseries, correlation, attitude heatmap, density decomposition) |

### MATLAB — Project Scripts (`matlab/scripts/`)

| File | Purpose |
|------|---------|
| `setup_project.m` | Creates MATLAB project (`.prj`), directory structure, path management, startup/shutdown hooks, empty `.sldd` |
| `build_data_dictionary.m` | Populates `.sldd` with bus definitions, parameters, tank structures, and 3-D lookup table objects |
| `build_simulink_model.m` | Programmatically builds 8 referenced `.slx` models with data dictionary bindings and signal logging |
| `validate_model.m` | Post-build validation: checks all files exist, dictionary is complete, LUT dimensions correct, buses resolve |
| `generate_hv_tables.m` | Standalone MATLAB H-V table generation (100×100 grid integration) |
| `gauging_system_standalone.m` | Full gauging + refuel + probe failure system in pure MATLAB (no Simulink required) |

### MATLAB — Tests and Utilities (`matlab/tests/`, `matlab/utilities/`)

| File | Purpose |
|------|---------|
| `tests/cross_validate.m` | Compares Python-generated vs MATLAB-generated H-V tables (pass if < 1% error) |
| `utilities/load_sequence_data.m` | Loads `.mat` sequence files into timeseries objects for Simulink `From Workspace` blocks |

### MATLAB — Legacy (`matlab/legacy/`)

| File | Purpose |
|------|---------|
| `build_simulink_model_v1.m` | Original monolithic model builder (superseded by v2 in `scripts/`) |

### Python Tests (`tests/`)

| File | Tests | Status |
|------|-------|--------|
| `test_geometry.py` | 10 | All pass |
| `test_tables.py` | 7 | All pass |
| `test_gauging.py` | 9 | All pass |
| `test_refuel_and_probes.py` | 13 | All pass |
| **Total** | **39** | **All pass** |

### Generated Data (`data/`)

| File | Format | Size | Contents |
|------|--------|------|----------|
| `tank_system.mat` | MATLAB v5 | ~586 KB | All H-V tables for 5 tanks (1,105 tables) |
| `tank_system.json` | JSON | ~9 MB | Same data in Python-friendly format |
| `defuel_sequence.mat` | MATLAB v5 | ~226 KB | 1000-sample defuel time history, 51 columns |
| `defuel_sequence.csv` | CSV | — | Same data in CSV format |
| `refuel_sequence.mat` | MATLAB v5 | ~181 KB | 800-sample refuel time history, 51 columns |
| `refuel_sequence.csv` | CSV | — | Same data in CSV format |

### Configuration (`config/`)

| File | Purpose |
|------|---------|
| `system_config.yaml` | Tank metadata, column name mappings, drain/fill sequences, injected error catalog. Note: the structural fraction (`STRUCTURAL_FRACTION = 0.003`) is defined in `tank_geometry.py` rather than in the YAML config, as it is a geometric property of the tank model. |

### Generated Plots (`plots/`)

| File | Content |
|------|---------|
| `01_tank_layout.png` | Plan view + side view of 5-tank layout with probes and gravity arrows |
| `02_hv_curves.png` | H-V curves at 6 attitude conditions per tank |
| `03_probe_coverage.png` | Probe height ranges vs tank heights with unusable/ullage zones |
| `04_defuel_error_timeseries.png` | 4-panel: error, per-tank volumes, per-tank errors, attitude |
| `05_error_vs_fuel_level.png` | Hysteresis comparison (defuel vs refuel) + phase-colored scatter |
| `06_attitude_heatmap.png` | Mean weight error vs pitch/roll bins |
| `07_density_error.png` | Density error decomposition: total vs density contribution vs volume contribution |
| `08_per_tank_error.png` | Bar chart of mean absolute volume error per tank with error source annotations |
| `09_3d_tank_views.png` | 4-view 3D rendering (perspective, top, front, side) |
| `10_3d_fill_sequence.png` | 6-frame fill level progression (10% → 95%) |
| `11_3d_attitude_comparison.png` | Fuel surface shape at 4 different attitude conditions |
| `12_3d_refuel_system.png` | 3D view with refuel manifold, adapter, valves, and high-level sensors |
| `13_3d_probe_detail.png` | T3 close-up: lower/upper probes, blend zone, high-level sensor |

### Other Root Files

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies: numpy, pandas, scipy, h5py, matplotlib, seaborn, pyyaml |

---

## Related Documentation

| Document | Location | Contents |
|----------|----------|----------|
| This file | `docs/fuel_system_description.md` | System design, tank geometry, probe placement, error sources, file inventory |
| Simulink Schema | `docs/simulink_model_schema.md` | Bus definitions, data dictionary contents, model reference hierarchy, signal logging |
| Simulink Setup | `docs/simulink_setup_instructions.md` | Step-by-step MATLAB R2025b setup, troubleshooting, architecture rationale |
| CAD-to-Gauging Walkthrough | `docs/cad_to_gauging_walkthrough.md` | Step-by-step guide from CAD model to validated gauging software |
| Project Context | `Gauging/fuel-error-context.md` | Broader fuel gauging error analysis objectives and methodology |
| Analysis Prompt | `Gauging/claude-code-prompt.md` | 5-phase analysis toolset specification (future work) |
