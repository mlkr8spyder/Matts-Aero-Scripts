# CAD to Gauging Software: Full Engineering Walkthrough

This document covers the complete process of turning CAD geometry of fuel tanks into a functioning capacitance-based fuel quantity indication (FQIS) system. It is written for the synthetic 5-tank fuel system (plus-sign layout, rectangular prism tanks) but the principles and pitfalls apply directly to production aircraft programs.

The coordinate system throughout is:

- **FS** (Fuselage Station) -- positive aft
- **BL** (Buttline) -- positive right (starboard)
- **WL** (Waterline) -- positive up

Source code references are in `src/tank_geometry.py`, `src/hv_table_generator.py`, `src/gauging_model.py`, and `src/refuel_system.py`.

---

## Step 1: CAD Geometry Extraction

### What the gauging system needs from CAD

A fuel quantity system does not need the full CAD model of the airframe. It needs the **internal wetted boundary** of each fuel tank -- the surface that fuel can actually contact. Everything else (external skin mold lines, structural flanges outside the sealed volume, access panels) is irrelevant.

From that wetted boundary, the gauging engineer extracts:

1. **Tank envelope** -- the bounding volume. For simple shapes this is a bounding box defined by six limits. For real tanks it is a triangulated surface mesh (STL) or a STEP/IGES solid.
2. **Corner points** -- for a rectangular prism, these are the 8 vertices of the box. For complex geometry, discrete point clouds or mesh vertices serve the same role.
3. **Internal obstructions** -- ribs, spars, baffles, stringers, pump canisters, and other hardware that physically occupies space inside the tank.
4. **Reference datums** -- FS, BL, and WL of the tank boundaries, probe mount locations, sump locations, and vent outlets.

### This project's simplification

All five tanks are modeled as rectangular prisms. Each tank is defined by six coordinates:

```
(fs_min, fs_max, bl_min, bl_max, wl_min, wl_max)
```

The 8 corner points are the Cartesian product of the three axis pairs:

```python
for fs in [fs_min, fs_max]:
    for bl in [bl_min, bl_max]:
        for wl in [wl_min, wl_max]:
            corners.append([fs, bl, wl])
```

This yields an (8, 3) array in `Tank.corner_points()`.

### Real-world nuance

Production fuel tanks are rarely box-shaped. A wing tank follows compound-curved skin panels, interrupted by spar webs, rib bays, and stringer runouts. The internal volume must be captured by one of:

- **Surface mesh** (STL/OBJ) -- triangulated representation of the inner mold line. Volume is computed via the divergence theorem (sum of signed tetrahedral volumes formed by each triangle and the origin).
- **Volumetric decomposition** -- the tank is sliced into horizontal layers (constant-WL planes) and the cross-sectional area at each layer is integrated. This is the basis of most H-V table generation tools.
- **CAD solid query** -- CATIA, NX, or CREO can report enclosed volume directly, but this black-box number is insufficient for gauging because the system needs volume *as a function of height*, not a single scalar.

The rectangular prism model captures the essential workflow (envelope to volume to table) without the geometric complexity. Every formula and pipeline stage described below applies identically to complex geometry; only the volume integration kernel changes.

---

## Step 2: Volume Reduction Pipeline -- CAD to Usable Capacity

The raw enclosed volume of a fuel tank is never the number that goes on the placard. Several physical and operational deductions must be applied in sequence. Getting this pipeline wrong means either under-fueling the aircraft (lost range) or over-fueling it (structural overload or vent overflow).

### Stage 1: Raw CAD Volume

For a rectangular prism:

```
V_gross = L x W x H
```

where L = fs_max - fs_min, W = bl_max - bl_min, H = wl_max - wl_min. The result is in cubic inches. Divide by 231 to get US gallons.

For a triangulated mesh, the enclosed volume is:

```
V = (1/6) * sum_over_triangles( v0 . (v1 x v2) )
```

where v0, v1, v2 are the vertex position vectors of each triangle (with consistent outward-facing normals).

### Stage 2: Structural Displacement (~0.3%)

Inside every fuel tank there is hardware that physically displaces fuel:

- Capacitance probes and their mounting brackets
- Anti-slosh baffles (perforated sheet metal or stamped ribs)
- Boost-pump canisters and ejector assemblies
- Plumbing fittings (tees, elbows, check valves, drain valves)
- Wiring harnesses (level sensors, temperature sensors, bonding straps)
- Stringer stiffeners that protrude into the tank volume

These items are present in the CAD model of the tank interior but are not fuel. Their total displaced volume is typically 0.2--0.5% of gross, modeled here as 0.3%.

```
V_structural = V_gross x 0.003
```

### Stage 3: Ullage Reserve (2.0%)

The top band of the tank is reserved for two purposes:

1. **Thermal expansion** -- fuel expands as it warms (Jet-A volumetric expansion coefficient is approximately 0.00045 per degree F). An aircraft fueled at -20F on a cold ramp and then sitting on hot tarmac at +120F can see fuel volume increase by 5--7%. The ullage band absorbs this expansion without venting overboard.
2. **Vent path** -- the fuel vent system requires an air gap at the top of the tank to function. If fuel contacts the vent outlet, liquid fuel can be pushed overboard through the vent mast.

The ullage height is:

```
ullage_height = H x 0.02
max_fill_wl = wl_max - ullage_height
```

The ullage volume is:

```
V_ullage = base_area x ullage_height
```

where `base_area = L x W` for a rectangular tank.

### Stage 4: Unusable Fuel (1.5%)

Fuel below the lowest sump pickup or boost-pump inlet cannot be delivered to the engine. It is physically present in the tank but is not consumable. This includes:

- Fuel trapped below the sump floor
- Fuel in corners and low points that the pickup geometry cannot reach
- Fuel that drains below the minimum pump NPSH level

The unusable height is:

```
unusable_height = H x 0.015
min_fuel_wl = wl_min + unusable_height
```

The unusable volume is:

```
V_unusable = base_area x unusable_height
```

### Stage 5: Usable Capacity

What remains after all three deductions is the usable fuel -- the number on the placard:

```
V_usable = V_gross - V_structural - V_ullage - V_unusable
```

### Reduction Summary Table

| Stage | Formula | T1 (gal) | T3 (gal) | Notes |
|-------|---------|----------|----------|-------|
| Gross CAD | L x W x H / 231 | 62.34 | 173.16 | Raw envelope volume |
| - Structural | x 0.003 | -0.19 | -0.52 | Internal hardware |
| - Ullage | base_area x h x 0.02 / 231 | -1.25 | -3.46 | Thermal expansion |
| - Unusable | base_area x h x 0.015 / 231 | -0.94 | -2.60 | Below pickup |
| **Usable** | | **59.96** | **166.58** | Placard capacity |

The total reduction is approximately 3.5% of gross. This may seem small, but on a 600-gallon system it represents over 20 gallons -- enough fuel for 15 minutes of flight in a light turboprop.

---

## Step 3: Attitude Modeling -- Tilted Fuel Plane

### Why the fuel surface tilts

Fuel is a liquid. When the aircraft pitches or rolls, the fuel surface remains perpendicular to the local gravity vector (ignoring dynamic slosh). Relative to the aircraft body frame, this means the fuel surface is a tilted plane.

If the fuel surface is level at some reference point (x_ref, y_ref) with height z_ref, the fuel surface WL at any other point (x, y) is:

```
z_fuel(x, y) = z_ref + (x - x_ref) * tan(pitch) + (y - y_ref) * tan(roll)
```

### Sign convention

The sign convention in this system is:

- **Positive pitch** = nose up. Gravity pulls fuel aft. The fuel surface rises with increasing FS (aft). Therefore `z_fuel` increases with FS for positive pitch, consistent with `(x - x_ref) * tan(pitch)` since FS increases aft.
- **Positive roll** = right wing down. Gravity pulls fuel to starboard. The fuel surface rises with increasing BL (right). Therefore `z_fuel` increases with BL for positive roll.

These conventions must be consistent between geometry code, table generation, and the onboard gauging computer. A sign error here produces a gauging error that doubles with attitude magnitude, and it will not be caught by level-attitude testing.

### Numerical integration

For a rectangular tank with a planar fuel surface, the volume under the tilted plane can in principle be computed analytically. However, the analytical solution becomes piecewise when the fuel plane clips the tank floor or ceiling within the base rectangle -- a common situation at large attitudes in tall, narrow tanks.

This project uses numerical integration on a 100 x 100 grid of cell centers:

```python
fs_centers = linspace(fs_min + dx/2, fs_max - dx/2, 100)
bl_centers = linspace(bl_min + dy/2, bl_max - dy/2, 100)
cell_area = dx * dy

for each (fs, bl) cell center:
    z_fuel = z_ref + (fs - ref_fs) * tan(pitch) + (bl - ref_bl) * tan(roll)
    h_fuel = clip(z_fuel - wl_min, 0, tank_height)
    volume += h_fuel * cell_area
```

This 10,000-cell grid handles all clipping cases (partial floor contact, partial ceiling contact, diagonal clipping across corners) without any special-case geometry code. The numerical error is well below 0.1% of gross volume.

### Why analytical is hard

The fully analytical solution for a rectangular prism with a clipped tilted plane requires identifying which edges of the base rectangle the fuel surface intersects, computing intersection points, and integrating piecewise-linear depth over the resulting polygon. There are up to 9 distinct topological cases (plane entirely below floor, entirely above ceiling, clipping one edge, clipping two adjacent edges, clipping two opposite edges, etc.). The numerical approach is simpler, less error-prone, and fast enough for offline table generation.

### CG computation

The center of gravity of the fuel is computed at the same time as the volume, using moment-weighted integration over the same grid:

```
CG_fs = sum(fs_i * vol_i) / sum(vol_i)
CG_bl = sum(bl_i * vol_i) / sum(vol_i)
CG_wl = sum((wl_min + h_i/2) * vol_i) / sum(vol_i)
```

where `vol_i = h_fuel_i * cell_area` and `h_i/2` approximates the centroid height of each rectangular column of fuel. The CG is needed for aircraft weight-and-balance calculations during fuel burn scheduling.

---

## Step 4: Probe Selection and Placement

### Probe Types

The system uses three distinct probe strategies, each with different accuracy, cost, and installation characteristics.

#### Real Probes (T1, T2, T4)

A real capacitance probe is a physical sensor installed inside the fuel tank. It consists of two coaxial electrodes -- an inner tube and an outer tube -- separated by a controlled annular gap. Fuel fills this gap from the bottom as the tank level rises.

The capacitance of the probe is:

```
C = 2 * pi * epsilon_0 * kappa * L_wetted / ln(r_outer / r_inner)
```

where `kappa` is the dielectric constant of the medium filling the gap (air above the fuel surface, fuel below it) and `L_wetted` is the length of probe immersed in fuel. The electronics measure the change in capacitance as fuel level changes:

```
delta_C proportional to L_wetted * (kappa_fuel - kappa_air)
```

Since `kappa_fuel` for Jet-A is approximately 2.05 and `kappa_air` is 1.0, the capacitance roughly doubles when the probe goes from dry to wet, giving strong signal-to-noise ratio.

In this system, real probes are mounted near the tank center (FS/BL) to minimize sensitivity to attitude. The probe is oriented nearly vertical but with a slight diagonal tilt of 3--4 degrees. This tilt serves two purposes:

1. **Resolution improvement** -- a tilted probe integrates fuel level over a small FS/BL span, averaging out local surface ripples from slosh.
2. **Condensation shedding** -- water droplets from condensation run off the tilted electrode surfaces rather than pooling and corrupting the dielectric measurement.

#### Real-Pseudo Combination (T3)

Tank 3 (Center/Collector) is 20 inches tall -- too tall for a single capacitance probe to maintain adequate resolution across the full range. A 20-inch probe with 0.02-inch measurement noise has a noise-to-span ratio of 0.1%, which is marginal. Two shorter probes provide better linearity and lower noise-to-span.

The two probes are:

- **T3_lower**: WL 80.30 to 92.00 (11.70 inches physical)
- **T3_upper**: WL 90.00 to 99.60 (9.60 inches physical)

The probes overlap in the WL 90.00 to 92.00 range. In this **blend zone**, both probes are wet and their readings are combined with a linear weight transition:

```
w_upper = (h - 90.0) / (92.0 - 90.0)
w_lower = 1.0 - w_upper
blended_wl = w_lower * wl_lower + w_upper * wl_upper
```

Below WL 90.0, only the lower probe is active. Above WL 92.0, only the upper probe is active.

The blend zone introduces a small **step error** (modeled as 0.08 inches) at the transition boundaries. This occurs because the two probes have slightly different gain calibrations, mounting tolerances, and thermal characteristics. The step error follows a sinusoidal profile across the blend zone, peaking at the center:

```
step = 0.08 * sin(pi * blend_fraction)
```

This is an inherent disadvantage of multi-probe blending and must be budgeted in the system accuracy analysis.

#### Pure Pseudo Probes (T5)

Tank 5 (Aft) has no physical probe installed. Instead, the fuel surface height in T5 is **projected** from the T3 (Center) measurement using the tilted-plane equation and the known geometric offset between the two tanks:

```
z_T5 = z_T3 + dx * tan(pitch) + dy * tan(roll)
```

where `dx = +55 inches` (T5 reference FS 315.0 minus T3 center FS 260.0) and `dy = 0` (both tanks are on centerline).

This approach is used when probe installation in a tank is impractical (access difficulty, structural interference) or weight-prohibitive (every probe adds ~0.5 lb with harness and connector). The penalty is degraded accuracy:

- At level attitude the projection is exact (both tanks share the same fuel plane).
- At pitch, the `tan(pitch)` amplifies the 55-inch FS offset. At 6 degrees pitch, `55 * tan(6) = 5.78 inches` of projected height offset. Any error in the pitch measurement or in the T3 height reading is multiplied by this lever arm.
- The projection assumes T5 is connected to the same fuel body as T3. If the interconnect between T3 and T5 is blocked by a check valve or if fuel has separated due to prolonged attitude, the projection is invalid.

### Probe Placement Rationale

Probes are placed according to three constraints:

1. **Near tank center** (FS and BL). A probe at the geometric center of the base rectangle experiences zero first-order attitude error: the fuel surface tilts symmetrically around the center, so the height at the center equals the average height across the tank. Moving the probe off-center introduces a bias proportional to the offset times `tan(attitude)`.

2. **Above the unusable zone**. The probe base WL is set above `wl_min + unusable_height`. There is no value in sensing fuel below the pickup level, and immersing the probe base in permanently-wet unusable fuel corrupts the dry reference capacitance.

3. **Below the ullage ceiling**. The probe top WL is set below `wl_max - ullage_height`. Fuel should never reach the ullage zone during normal operations, so probe sensing range above it is wasted.

---

## Step 5: Sense-Point Offsets

This is one of the most commonly overlooked details in fuel gauging integration and a frequent source of systematic height bias.

### Physical vs. Electrical Envelope

A capacitance probe has a **physical envelope** (the metal tube assembly from mounting flange to end cap) and an **electrical envelope** (the region where capacitance is actually measured). These are not the same.

At the **bottom** of the probe, the lower guard ring and mounting flange occupy the first 0.50 inches (typical). This region is structurally necessary but electrically inactive -- fuel wets it, but the electronics do not sense it.

At the **top** of the probe, the upper guard ring and end cap occupy the last 0.25 inches (typical). Again, structurally necessary but electrically inactive.

The active sensing region (where capacitance changes are measured and reported) is therefore:

```
sense_base_wl = base_wl + sense_offset_base
sense_top_wl  = top_wl  - sense_offset_top
active_sense_length = sense_top_wl - sense_base_wl
```

### Why This Matters

The capacitance electronics report fuel height **relative to the lower sense point**, not relative to the physical probe base. When the electronics report "0.0 inches," it means fuel is at or below WL = sense_base_wl. When they report the maximum value (active_sense_length), fuel is at or above sense_top_wl.

For H-V table lookup, the height must be referenced to the **physical** probe base (which is the datum used during table generation). The conversion is:

```
physical_height = sensed_height + sense_offset_base
```

Failure to apply this offset introduces a systematic bias equal to sense_offset_base (0.50 inches typical). On a 15-inch probe, 0.50 inches corresponds to 3.3% of span. At a density of 6.71 lb/gal, this can produce a weight error of several pounds per tank -- enough to trip a tolerance limit during acceptance testing.

### Complete Probe Table

| Probe | Physical Base WL | Sense Base WL | Physical Top WL | Sense Top WL | Phys Length | Sense Length | Base Offset | Top Offset |
|-------|-----------------|---------------|-----------------|--------------|-------------|--------------|-------------|------------|
| T1_probe | 88.24 | 88.74 | 103.68 | 103.43 | 15.44" | 14.69" | 0.50" | 0.25" |
| T2_probe | 85.27 | 85.77 | 102.64 | 102.39 | 17.37" | 16.62" | 0.50" | 0.25" |
| T3_lower | 80.30 | 80.80 | 92.00 | 91.80 | 11.70" | 11.00" | 0.50" | 0.20" |
| T3_upper | 90.00 | 90.20 | 99.60 | 99.35 | 9.60" | 9.15" | 0.20" | 0.25" |
| T4_probe | 85.27 | 85.77 | 102.64 | 102.39 | 17.37" | 16.62" | 0.50" | 0.25" |

Note: T5 has no physical probe (pure pseudo). Its height is projected from T3.

The T3_upper probe has a smaller base offset (0.20") because it uses a compact mounting design to fit within the blend overlap zone. The T3_lower probe has a smaller top offset (0.20") for the same reason.

---

## Step 6: Height-Volume (H-V) Table Generation

### What an H-V Table Is

An H-V table is a lookup table that maps **fuel height at the probe location** to **fuel volume in the tank** for a specific aircraft attitude (pitch, roll). It is the core data product of the gauging system -- without it, a height measurement is meaningless.

Each table is a one-dimensional function: height (inches, relative to probe base) on the input axis, volume (cubic inches or gallons) on the output axis. For a rectangular tank at level attitude, this function is linear (V = base_area * h). At non-zero attitudes, the function becomes nonlinear due to the tilted fuel plane clipping the tank floor or ceiling.

### Attitude Grid

The system generates tables across a grid of attitudes:

- **Pitch**: -6 to +6 degrees in 1-degree steps = 13 values
- **Roll**: -8 to +8 degrees in 1-degree steps = 17 values
- **Total**: 13 x 17 = 221 tables per tank
- **5 tanks**: 221 x 5 = **1,105 tables total**

The pitch range of +/-6 degrees covers normal flight attitudes including climb, descent, and approach. The roll range of +/-8 degrees covers coordinated turns and crosswind corrections. Larger attitudes (steep turns, unusual attitudes) fall outside the table range and are handled by clamping to the boundary tables.

### Height Axis

For each table, the height axis runs from slightly below the tank floor to slightly above the tank ceiling, in 0.5-inch steps:

```
wl_start = wl_min - 1.0
wl_end   = wl_max + 1.0
heights_wl = arange(wl_start, wl_end + step/2, 0.5)
heights_rel = heights_wl - probe_base_wl
```

The 1-inch margin beyond the tank bounds ensures that the table covers the full range of fuel levels even when attitude shifts the fuel surface above or below the nominal tank envelope at the probe location.

### Generation Process

For each (pitch, roll, height) combination:

1. Call the tilted-plane volume integration (`fuel_volume_tilted_rect`) with the fuel surface at the specified WL at the probe reference point.
2. Call the CG computation (`cg_for_fuel_state`) for the same state.
3. Store height (relative to probe base), volume (in cubic inches and gallons), and CG (FS, BL, WL).

### Table Storage

Each table is stored as a dictionary:

```python
{
    'heights_rel': array,    # height relative to probe base (inches)
    'volumes_in3': array,    # volume (cubic inches)
    'volumes_gal': array,    # volume (gallons)
    'cg_fs': array,          # CG fuselage station
    'cg_bl': array,          # CG buttline
    'cg_wl': array,          # CG waterline
    'pitch_deg': float,
    'roll_deg': float,
    'N': int                 # number of data points
}
```

The tables are nested in the structure:

```
all_tables['tanks'][tank_id]['tables'][pitch_idx][roll_idx]
```

### Output Formats

Tables are saved in two formats:

- **.mat** (MATLAB) -- for integration with Simulink models and MATLAB-based gauging computers. Uses cell arrays to handle variable-length height vectors.
- **.json** (Python) -- for Python-based simulation and validation. Human-readable, version-controllable.

Across 5 tanks, 1,105 tables, and approximately 42 height points per table, the total data volume is approximately 46,000 data points.

---

## Step 7: The Measurement Chain -- Capacitance to Weight

The full signal chain from physical fuel state to displayed weight has 9 stages. Each stage introduces potential error. Understanding this chain end-to-end is necessary for budgeting system accuracy.

### Stage 1: Fuel Surface

The true fuel surface in the tank is a plane (in steady state) defined by the total fuel volume, the tank geometry, and the aircraft attitude. This is the physical ground truth.

### Stage 2: Fuel Surface at Probe

The tilted plane is evaluated at the probe's (FS, BL) location to determine the fuel surface WL at the probe:

```
z_fuel_at_probe = z_ref + (probe_fs - ref_fs) * tan(pitch) + (probe_bl - ref_bl) * tan(roll)
```

For a probe at tank center, this equals z_ref. For an off-center probe, the attitude introduces a height offset.

### Stage 3: Wetted Height

The raw wetted height on the probe is the fuel surface WL minus the probe base WL, clamped to the physical probe bounds:

```
wetted_height = clip(z_fuel_at_probe - base_wl, 0, active_length)
```

This is a geometric quantity -- the actual length of probe immersed in fuel.

### Stage 4: Sensed Height

The electronics only measure the portion of wetted height within the active sense region. The sensed height is:

```
sensed_height = clip(z_fuel_at_probe - sense_base_wl, 0, active_sense_length)
```

This is what the probe electronics actually report.

### Stage 5: Corrected Height

The sensed height must be converted back to physical-base-referenced height for table lookup:

```
corrected_height = sensed_height + sense_offset_base
```

### Stage 6: Table Lookup

The corrected height, along with the current pitch and roll, is used to look up volume from the H-V tables. The lookup uses:

1. **Bilinear interpolation** across pitch and roll -- find the four surrounding tables in the attitude grid and blend them.
2. **Linear interpolation** on height within each blended table -- find the two bracketing height entries and interpolate.

The result is volume in cubic inches.

### Stage 7: Volume to Gallons

```
volume_gal = volume_in3 / 231
```

### Stage 8: Density from Dielectric

The fuel density is not measured directly. Instead, a compensator element on the probe measures the dielectric constant of the fuel, and density is computed from a calibrated linear model:

```
rho = a * kappa + b    [lb/gal]
```

See Step 8 below for the full derivation.

### Stage 9: Weight

```
weight_lb = volume_gal * rho_lb_per_gal
```

This is the number displayed to the flight crew.

---

## Step 8: Density from Dielectric Constant

### Physical Basis

The dielectric constant (kappa) of a hydrocarbon fuel is a measure of its molecular polarizability per unit volume. Denser fuel has more molecules per unit volume, each contributing to the dielectric response. Both kappa and density (rho) decrease as temperature increases (the fuel expands), and both track with fuel composition (aromatic content, carbon chain length).

The result is a strong, monotonic, nearly linear correlation between kappa and rho for a given fuel grade. This is what makes capacitance gauging viable -- the same sensor that measures fuel level also provides the information needed to convert volume to weight.

### Linear Model

The density-dielectric relationship is modeled as:

```
rho(kappa) = a * kappa + b    [lb/gal]
```

### Calibration

The coefficients (a, b) are determined from two reference points. For this system:

- Point 1: kappa = 2.05, rho = 6.71 lb/gal (Jet-A at 60 deg F)
- Point 2: kappa = 1.90, rho = 6.01 lb/gal (Jet-A at ~130 deg F)

Solving the linear system:

```
6.71 = a * 2.05 + b
6.01 = a * 1.90 + b

a = (6.71 - 6.01) / (2.05 - 1.90) = 0.70 / 0.15 = 4.667 lb/gal per unit kappa
b = 6.71 - 4.667 * 2.05 = 6.71 - 9.567 = -2.857 lb/gal
```

### Temperature Effects

Temperature affects both properties:

- `d(rho)/dT = -0.0035 lb/gal per deg F`
- `d(kappa)/dT = -0.0011 per deg F`

### Implicit vs. Explicit Temperature Compensation

If the compensator element measuring kappa is immersed in the same fuel at the same temperature as the fuel being gauged, the temperature effect is already captured. As the fuel warms, kappa drops, the model computes a lower rho, and the indicated weight decreases -- exactly matching the real expansion. No explicit temperature term is needed.

An explicit temperature term is only needed when the kappa measurement and the fuel volume come from different thermal environments -- for example, if a single compensator in one tank is used to estimate density for a different tank at a different temperature. In that case:

```
rho(kappa, T) = a * kappa + b + c * (T - T_ref)
```

with `c` being small and application-specific. This system does not use the explicit temperature term by default (`enable_temperature_term = False`).

---

## Step 9: Error Sources and Injection

The simulation injects 7 distinct error sources to exercise the full measurement chain. Each source models a real physical or algorithmic phenomenon.

### 1. Density Bias (0.3%)

A systematic offset in the density model, representing the difference between laboratory-calibrated density and the field-installed compensator reading. Causes:

- Compensator electrode contamination (fuel varnish buildup)
- Lab calibration drift over time
- Fuel grade variation (Jet-A vs. JP-8 have slightly different kappa-rho slopes)

Effect: all weight indications are biased by the same fraction. A 0.3% bias on a 3,000 lb fuel load is 9 lb.

### 2. Probe Nonlinearity (T2, +/-0.15 inches)

Parabolic height error on the T2 probe, peaking in the 40--60% fill range. This models:

- Electrode straightness tolerance (bowing of the inner or outer tube)
- Non-uniform annular gap due to manufacturing variation
- Fringe-field effects at probe mid-span

The error profile is:

```
nonlin = 0.15 * (-4 * (fill_frac - 0.5)^2 + 1.0)
```

This gives zero error at empty and full, maximum positive error at 50% fill.

### 3. Blend Step Error (T3, 0.08 inches)

A height discontinuity at the T3 blend zone transitions (WL 90--92). This models the gain mismatch between the lower and upper probes. The step follows a sinusoidal profile:

```
step = 0.08 * sin(pi * blend_fraction)
```

The error peaks at the center of the blend zone and is zero at the boundaries.

### 4. Pitch-Amplified Projection Error (T5, 0.02 inches/degree above 3 degrees)

For the pure pseudo probe on T5, pitch angles above 3 degrees introduce an additional height error proportional to the pitch excess and the FS offset. This models:

- Attitude sensor accuracy degradation at larger angles
- Non-planarity of the fuel surface at high pitch (dynamic slosh effects)
- Interconnect flow restriction between T3 and T5

```
extra_error = 0.02 * (|pitch| - 3.0) * sign(pitch) * dx * 0.01
```

### 5. Table Quantization (0.2% of gross volume)

The H-V table has finite height steps (0.5 inches). Between table entries, linear interpolation introduces a quantization error. This is modeled as uniform random noise:

```
quant_noise = uniform(-1, 1) * 0.002 * V_gross
```

In practice, this error can be reduced by using finer table steps (0.25 inches) at the cost of larger table storage.

### 6. Probe Noise (0.02 inches, 1-sigma)

Random electrical measurement noise on each probe reading. This represents:

- Analog-to-digital converter quantization
- Electromagnetic interference (EMI) from nearby avionics
- Fuel surface ripple from vibration (slosh noise)

```
noise = normal(0, 0.02)    [inches]
```

### 7. Dielectric Drift (+/-0.5% kappa, 500-sample period)

A slow sinusoidal drift in the dielectric constant measurement, representing temperature cycling during flight (climb into cold air, descent into warm air):

```
drift = 0.005 * sin(2 * pi * sample_idx / 500)
kappa_measured = kappa_true + drift
```

This produces a time-varying density error that affects all tanks simultaneously.

---

## Step 10: Probe Failure Detection and Built-In Test (BIT)

### Failure Modes

The system monitors 5 failure conditions on each probe:

1. **Open circuit** -- the probe reading drops below -0.1 inches (a physical impossibility). Indicates a broken wire, corroded connector, or failed electronics channel. The probe is reporting zero or negative capacitance.

2. **Short circuit** -- the probe reading exceeds the physical maximum by more than 0.5 inches. Indicates a shorted electrode (fuel contamination bridging the gap, mechanical damage collapsing the annular space, or a failed signal conditioner railing to full scale).

3. **Rate exceedance** -- the absolute change in reading exceeds 2.0 inches per second. Fuel cannot physically slosh this fast in a tank of this size. Indicates an intermittent electrical connection or a digital data corruption.

4. **Stale data** -- the reading does not change by more than 0.01 inches for 30 seconds. If the aircraft is in any dynamic condition (climb, descent, turns, fuel burn), the probe should show some change. A frozen reading indicates a stuck relay, a halted processor, or a broken feedback loop.

5. **Out of range** -- the reading falls outside the probe's physical bounds [0, active_length]. This is a soft fault; the reading is clipped rather than rejected, unless it significantly exceeds bounds.

### Detection Thresholds

| Mode | Threshold | Response |
|------|-----------|----------|
| Open circuit | reading < -0.1" | Flag, hold LKG |
| Short circuit | reading > max + 0.5" | Flag, hold LKG |
| Rate exceedance | \|dh/dt\| > 2.0"/s | Flag, hold LKG |
| Stale data | \|delta\| < 0.01" for 30s | Flag, hold LKG |
| Out of range | outside [0, active_length] | Clip (soft) |

### Response: Last Known Good (LKG) Fallback

When a failure is detected, the system:

1. Flags the probe as unhealthy and records the failure mode.
2. Substitutes the **last known good** (LKG) reading -- the most recent reading that passed all health checks.
3. Sets a maintenance flag for the crew.
4. Continues to monitor the raw reading; if it returns to a valid range, the probe is restored to healthy status.

LKG is a reasonable short-term fallback because fuel quantity changes slowly (typical burn rate is 0.5--2.0 gal/min). A stale LKG value will drift from truth at the burn rate, introducing an error of roughly 1--4 lb per minute. This is acceptable for the time it takes the crew to diagnose and respond.

### T3 Redundancy

Tank 3 has two physical probes (lower and upper). If one fails:

- The remaining probe covers its portion of the tank height accurately.
- The failed probe's contribution to the blend zone is replaced by extrapolation from the healthy probe.
- The blend step error is eliminated (single-probe mode has no blending), but the sensed range is reduced.

This built-in redundancy is one of the advantages of the real-pseudo combination architecture.

---

## Step 11: Validation Strategy

### No-Error Baseline Comparison

The first validation step is to disable all error injection and compare the gauging model output against the analytical geometry:

- At level attitude (pitch=0, roll=0), the volume for a rectangular tank at height h is exactly `base_area * h`. The H-V table output should match this to within the numerical integration tolerance (~0.05%).
- At non-zero attitudes, the tilted-plane numerical integration should match an independent analytical calculation for the cases where the plane does not clip the floor or ceiling.

### Volume Monotonicity

For every table at every attitude, volume must be a non-decreasing function of height. A non-monotonic table indicates a bug in the integration or the table generation. The check is:

```
for each table:
    assert all(diff(volumes) >= 0)
```

This should hold even when the fuel plane clips the tank boundaries, because adding fuel always increases volume.

### Error Injection Magnitude Verification

Each injected error source has a known configured magnitude. The validation checks:

- Density bias: measured density / true density - 1.0 should equal the configured bias fraction (0.003).
- T2 nonlinearity: at 50% fill, the height error should be approximately 0.15 inches.
- T3 blend step: at the center of the blend zone, the height error should be approximately 0.08 inches.
- T5 pitch amplification: at 6 degrees pitch, the extra error should be approximately 0.02 * (6 - 3) * 55 * 0.01 = 0.033 inches.
- Probe noise: over many samples, the standard deviation of the noise contribution should converge to 0.02 inches.
- Dielectric drift: the amplitude of the sinusoidal component should be 0.005 in kappa units.

### Scale Weight Checkpoints

At key phase boundaries (empty, 25% fill, 50% fill, 75% fill, full), compare the indicated total system weight against the true weight:

- At level attitude with no errors, they should match exactly.
- With all errors enabled, the total weight error should remain within the system accuracy budget (typically +/-2% of reading or +/-1% of full scale, whichever is greater).

### Cross-Validation: Python vs. MATLAB

The H-V tables are generated in Python and saved in both .json and .mat formats. The MATLAB/Simulink implementation loads the .mat tables and runs the same measurement chain. Cross-validation confirms:

- Table values are identical (bit-for-bit after accounting for floating-point format differences).
- Table interpolation produces the same volume for the same (height, pitch, roll) inputs.
- The full measurement chain (capacitance to weight) produces the same indicated weight within rounding tolerance.

Discrepancies between the two implementations are almost always caused by differences in interpolation boundary handling (how each language handles extrapolation beyond the table range) or by inconsistent sign conventions in the attitude model.
