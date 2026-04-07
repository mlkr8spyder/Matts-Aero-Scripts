# GPT-4.1 Data Adapter Guide

Instructions for using a GPT-4.1 (or equivalent) language model to convert your own aircraft fuel tank data into the formats required by this gauging system tool.

---

## Overview

This tool requires tank geometry, probe placement, and fuel properties in specific formats. If you have this data in other formats (CAD exports, engineering drawings, spreadsheets, or technical manuals), a GPT-4.1 model can help you transform it. This guide provides the exact prompts and format specifications to do so.

---

## Step 1: Prepare Your Source Data

Gather the following information for each tank. It can be in any format (PDF, spreadsheet, text, images of drawings). The minimum required data is:

### Required (per tank)

| Data Item | What It Means | Example |
|-----------|---------------|---------|
| Tank boundaries | Min/max coordinates in 3 axes | FS 195-225, BL -15 to 15, WL 88-104 |
| Probe location | Base and top coordinates (FS, BL, WL) | Base: (210, -0.5, 88.24), Top: (210, 0.5, 103.68) |
| Probe type | Single real, dual combo, or pseudo | "real", "real_pseudo_combo", "pure_pseudo" |
| Tank name/ID | Identifier | "Forward", tank 1 |

### Optional (improves accuracy)

| Data Item | Default If Missing | Example |
|-----------|--------------------|---------|
| Fuel density at reference temp | 6.71 lb/gal (Jet-A at 60 deg F) | 6.71 lb/gal |
| Dielectric constant | 2.05 (Jet-A at 60 deg F) | 2.05 |
| Density model coefficients | a=4.667, b=-2.857 | Calibration curve slope/intercept |
| Sense-point offsets | 0.50" base, 0.25" top | From probe spec sheet |
| Max fill waterline | Probe top WL | From tank placard |
| Ullage/unusable fractions | 2% ullage, 1.5% unusable | From system design doc |
| Attitude range | +/-6 deg pitch, +/-8 deg roll | From aircraft flight envelope |
| Pseudo tank FS/BL offset | (T5 only) | 55.0" FS, 0.0" BL from reference tank |
| Blend zone bounds | (combo probes only) | WL 90.0 to 92.0 |

---

## Step 2: Generate `system_config.yaml`

### Prompt Template

Copy this prompt into GPT-4.1, replacing the bracketed sections with your actual data:

```
I need you to generate a system_config.yaml file for a fuel gauging simulation tool.
The YAML must follow this exact structure. Fill in the values from the data I provide
below. For any parameter I don't provide, use the default values shown.

Here is my tank data:
[PASTE YOUR DATA HERE — any format is fine: table, text, coordinates, etc.]

Here is the required YAML structure with defaults:

---
dataset_type: synthetic
dry_weight_lb: [AIRCRAFT DRY WEIGHT, default: 12000.0]

fuel:
  density_lab_lb_per_gal: [LAB DENSITY, default: 6.71]
  dielectric_nominal: [DIELECTRIC AT REF TEMP, default: 2.05]
  fuel_type: "[FUEL GRADE, default: Jet-A equivalent]"
  density_model_a: [SLOPE of rho=a*kappa+b, default: 4.667]
  density_model_b: [INTERCEPT of rho=a*kappa+b, default: -2.857]
  reference_temp_F: [REF TEMPERATURE, default: 60.0]
  density_temp_coef: [d(rho)/dT, default: -0.0035]
  dielectric_temp_coef: [d(kappa)/dT, default: -0.0011]
  enable_temperature_term: false

structural_fraction: [default: 0.003]
ullage_fraction: [default: 0.02]
unusable_fraction: [default: 0.015]

probe_sense_offsets:
  default_base_in: [default: 0.50]
  default_top_in: [default: 0.25]

tanks:
  T1: {name: [NAME], probe_type: [real/real_pseudo_combo/pure_pseudo],
       floor_wl: [WL_MIN], ceiling_wl: [WL_MAX]}
  T2: {name: [NAME], probe_type: [TYPE], floor_wl: [WL_MIN], ceiling_wl: [WL_MAX]}
  [... repeat for each tank]
  # For combo probe tanks, add: blend_zone_wl: [LOWER_WL, UPPER_WL]
  # For pseudo tanks, add: pseudo_source: T[N], pseudo_dx: [FS_OFFSET], pseudo_dy: [BL_OFFSET]

Rules:
1. All dimensions are in INCHES
2. All densities are in lb/gal (US gallons)
3. Probe types must be exactly: "real", "real_pseudo_combo", or "pure_pseudo"
4. tank names should be short identifiers (Forward, Left, Center, Right, Aft, etc.)
5. Output ONLY the YAML file, no explanation
```

---

## Step 3: Generate `tank_geometry.py` Tank Definitions

If you need to modify the Python `build_tank_system()` function for your own geometry:

### Prompt Template

```
I need you to generate a Python function called build_tank_system() that returns a dict
of Tank objects for my fuel system. Each tank is a rectangular prism.

Here is my tank data:
[PASTE YOUR DATA: tank boundaries, probe locations, probe types]

Use this exact class structure:

    Tank(
        name="[NAME]",
        tank_id=[INT],
        fs_min=[FLOAT], fs_max=[FLOAT],
        bl_min=[FLOAT], bl_max=[FLOAT],
        wl_min=[FLOAT], wl_max=[FLOAT],
        probe_type="[real|real_pseudo_combo|pure_pseudo]",
        probes=[
            Probe(
                "[PROBE_NAME]",
                base_fs=[FLOAT], base_bl=[FLOAT], base_wl=[FLOAT],
                top_fs=[FLOAT], top_bl=[FLOAT], top_wl=[FLOAT],
                sense_offset_base=[DEFAULT 0.50],
                sense_offset_top=[DEFAULT 0.25]
            ),
        ],
    )

For pure_pseudo tanks (no physical probe), leave probes=[] empty.

The function must:
1. Create each Tank with exact coordinate values
2. Return a dict keyed by tank_id (integers starting at 1)
3. Use the Probe and Tank dataclasses from src.tank_geometry

Rules:
- All coordinates are in INCHES
- Coordinate system: FS positive aft, BL positive right, WL positive up
- probe_type must be exactly one of: "real", "real_pseudo_combo", "pure_pseudo"
- sense_offset_base is the distance from probe physical base to lower sense point
- sense_offset_top is the distance from probe physical top to upper sense point
- If I don't provide sense offsets, use 0.50 for base and 0.25 for top
```

---

## Step 4: Convert H-V Table Data

If you have existing height-volume calibration data (from CAD slicing, water calibration, or another tool), convert it to the required .mat format:

### Input Format (what you might have)

Your data might look like any of these:
- CSV/Excel with columns: height, volume (at one attitude)
- Multiple tables at different pitch/roll combinations
- A single level-attitude table
- CAD-exported volume vs. fill height

### Prompt Template

```
I have height-volume calibration data for a fuel tank. Convert it to the format needed
by my gauging tool's .mat file.

Here is my data:
[PASTE: could be a CSV table, a list of (height, volume) pairs, etc.]

The required .mat file format has these variables:
- pitch_range: 1x13 double vector [-6, -5, ..., 5, 6] (degrees)
- roll_range: 1x17 double vector [-8, -7, ..., 7, 8] (degrees)
- T{n}_heights: 13x17 cell array, each cell contains a 1xN double vector of heights
  in inches RELATIVE TO PROBE BASE (not tank floor)
- T{n}_volumes: 13x17 cell array, each cell contains a 1xN double vector of volumes
  in CUBIC INCHES

My tank parameters:
- Tank ID: [N]
- Probe base WL: [VALUE] inches
- Tank floor WL: [VALUE] inches
- Tank ceiling WL: [VALUE] inches

Generate a MATLAB script that:
1. Takes my raw data
2. Converts heights to probe-base-relative if needed (subtract probe_base_wl)
3. Converts volumes to cubic inches if needed (multiply gallons by 231)
4. If I only have level-attitude data, computes tilted-plane volumes for all
   13x17 attitude combinations using numerical integration on a 100x100 grid
5. Saves to .mat with the variable naming convention T{n}_heights, T{n}_volumes
6. Height step should be 0.5 inches
7. Height range should extend 1 inch below tank floor and 1 inch above tank ceiling

Important: if I only provide data at level attitude (pitch=0, roll=0), the script
must compute volumes at all attitudes using the tilted fuel surface equation:
  z_fuel(x,y) = z_ref + (x - x_ref)*tan(pitch) + (y - y_ref)*tan(roll)
where x_ref, y_ref is the probe location (FS, BL).
```

---

## Step 5: Convert Sequence Data (Defuel/Refuel CSVs)

If you have flight test or ground test data to compare against the simulation:

### Required CSV Column Names

The tool expects these exact column names. Your raw data columns must be mapped to them:

```
Required columns (minimum for comparison):
  sample          - integer row index starting at 0
  time_s          - timestamp in seconds
  pitch_deg       - aircraft pitch in degrees (positive = nose up)
  roll_deg        - aircraft roll in degrees (positive = right wing down)

Per-tank (repeat for each tank T1 through T{N}):
  probe_height_T{n}         - raw probe reading in inches
  fuel_wl_T{n}              - fuel surface waterline in inches (if known)
  indicated_volume_gal_T{n} - indicated volume in US gallons
  true_volume_gal_T{n}      - reference/true volume in US gallons (for validation)

System totals:
  density_system  - system-computed density in lb/gal
  total_indicated_weight_lb - total indicated fuel weight in lb
```

### Prompt Template for Column Mapping

```
I have test data in a CSV file with these columns:
[LIST YOUR COLUMN NAMES]

Map them to the standard column names used by my fuel gauging tool.
The target column names are:
  sample, time_s, pitch_deg, roll_deg,
  density_system, density_lab, density_error,
  total_indicated_volume_gal, total_true_volume_gal,
  total_indicated_weight_lb, total_true_weight_lb, total_weight_error_lb,
  probe_height_T{n}, indicated_volume_gal_T{n}, indicated_weight_lb_T{n},
  true_volume_gal_T{n}, true_weight_lb_T{n}, volume_error_in3_T{n}, fuel_wl_T{n}
  (repeated for n = 1 to number_of_tanks)
  phase, active_tanks, scale_gross_weight_lb, dry_weight_lb

Generate a Python script that:
1. Reads my CSV file
2. Renames columns to match the target names
3. Converts units if needed:
   - Volumes: multiply liters by 0.264172 to get gallons
   - Weights: multiply kg by 2.20462 to get lb
   - Heights: multiply mm by 0.03937 to get inches
   - Density: multiply kg/L by 8.345 to get lb/gal
4. Computes any missing derived columns:
   - density_error = density_system - density_lab
   - total_weight_error_lb = total_indicated_weight_lb - total_true_weight_lb
   - volume_error_in3_T{n} = (indicated_volume_gal_T{n} - true_volume_gal_T{n}) * 231
   - indicated_weight_lb_T{n} = indicated_volume_gal_T{n} * density_system
5. Saves the result as a new CSV with the standard column names
6. Also saves a .mat version using scipy.io.savemat

My data's current units are:
[SPECIFY: metric/imperial, what each column represents]
```

---

## Step 6: Validate the Conversion

After generating your config and data files, run these checks:

### Quick Validation Prompt

```
I've converted my fuel tank data to the required format. Help me validate it.

Here are my tank parameters:
[PASTE YOUR system_config.yaml OR tank definitions]

Check these physical sanity constraints:
1. Each tank's gross volume = (fs_max-fs_min) * (bl_max-bl_min) * (wl_max-wl_min)
   and should match the expected gross capacity
2. Usable volume should be ~96.2% of gross (after 2% ullage + 1.5% unusable + 0.3% structural)
3. Probe base WL should be at or slightly above tank floor WL
4. Probe top WL should be at or slightly below tank ceiling WL
5. Probe active length = top_wl - base_wl (should be positive)
6. For combo probes: blend zone must overlap both probes' ranges
7. For pseudo tanks: source tank must exist and offset must be physically reasonable
8. density_model_a * dielectric_nominal + density_model_b should approximately
   equal density_lab_lb_per_gal
9. Total system capacity should match the expected fuel load

Report any values that seem physically unreasonable.
```

---

## Common Conversions

### Units Reference

| From | To | Multiply By |
|------|----|-------------|
| Millimeters | Inches | 0.03937 |
| Centimeters | Inches | 0.3937 |
| Meters | Inches | 39.37 |
| Liters | US Gallons | 0.264172 |
| Liters | Cubic Inches | 61.024 |
| Cubic Meters | Cubic Inches | 61023.7 |
| Kilograms | Pounds | 2.20462 |
| kg/L | lb/gal | 8.345 |
| Radians | Degrees | 57.2958 |
| Celsius | Fahrenheit | C * 9/5 + 32 |

### Coordinate System Mapping

This tool uses the aerospace convention:
- **FS** (Fuselage Station): positive AFT (toward tail)
- **BL** (Buttline): positive RIGHT (starboard)
- **WL** (Waterline): positive UP

If your source data uses a different convention (e.g., X-forward, Y-up), include the mapping in your prompt:

```
My data uses this coordinate system:
  X = [positive direction], corresponds to [FS/BL/WL]
  Y = [positive direction], corresponds to [FS/BL/WL]
  Z = [positive direction], corresponds to [FS/BL/WL]

Sign conventions may need to be flipped: [describe any inversions]
```

---

## Example: Converting a 3-Tank System

Suppose you have a simple 3-tank system from engineering drawings:

```
Tank A (Main): 50x30x15 inches, center at FS 200
Tank B (Left Wing): 60x20x12 inches, at BL -35
Tank C (Right Wing): 60x20x12 inches, at BL +35

Probes:
  Tank A: vertical probe at center, base WL 90, top WL 104
  Tank B: vertical probe at BL -35, base WL 92, top WL 103
  Tank C: same as B but mirrored to BL +35
```

GPT-4.1 prompt:

```
Generate a system_config.yaml for this 3-tank fuel system:

Tank A "Main": FS 175-225, BL -15 to 15, WL 90-105. Real probe.
  Probe at (200, 0, 90.5) to (200, 0.3, 104.2)
Tank B "Left Wing": FS 180-240, BL -45 to -25, WL 92-104. Real probe.
  Probe at (210, -35, 92.3) to (210, -34.8, 103.5)
Tank C "Right Wing": FS 180-240, BL 25 to 45, WL 92-104. Real probe.
  Probe at (210, 35, 92.3) to (210, 34.8, 103.5)

Fuel: Jet-A, density 6.7 lb/gal at 60F, dielectric 2.05
Aircraft dry weight: 8500 lb

Use all other defaults from the template.
```

The GPT model will produce a complete, correctly formatted `system_config.yaml` that you can drop into the `config/` directory.

---

## Tips for Best Results

1. **Be explicit about units** in your prompt. Always state whether your source data is in inches vs. mm, gallons vs. liters, etc.

2. **Provide coordinate system mapping** if your source uses a non-standard convention.

3. **Include probe spec sheets** if available. The sense-point offsets (guard ring + mounting flange dimensions) affect accuracy.

4. **For complex tank shapes** (non-rectangular), you'll need to modify `fuel_volume_tilted_rect()` in `tank_geometry.py` or provide a custom volume integration function. Ask the GPT model to generate a numerical integration function for your specific geometry.

5. **Verify density model calibration**: If you have (dielectric, density) measurement pairs at two or more temperatures, provide them and ask GPT to compute the linear fit coefficients (a, b).

6. **One tank at a time**: For large systems (>5 tanks), process each tank individually to avoid overwhelming the context window.
