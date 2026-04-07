# Data Schema Reference

Complete specification of every data file produced and consumed by the synthetic fuel system pipeline.

---

## 1. Configuration Input: `config/system_config.yaml`

Central parameter file consumed by the Python pipeline. All physical constants, tank definitions, probe offsets, error injection parameters, and sequence timing are defined here.

### Top-Level Keys

| Key | Type | Description |
|-----|------|-------------|
| `dataset_type` | string | `"synthetic"` for this project |
| `dry_weight_lb` | float | Aircraft dry weight for gross weight calculation |
| `fuel` | dict | Fuel physical properties (see below) |
| `structural_fraction` | float | Fraction of gross volume displaced by internal hardware (0.003 = 0.3%) |
| `ullage_fraction` | float | Fraction of tank height reserved for thermal expansion (0.02 = 2%) |
| `unusable_fraction` | float | Fraction of tank height below sump pickup (0.015 = 1.5%) |
| `probe_sense_offsets` | dict | Default sense-point insets (inches) |
| `tanks` | dict | Per-tank definitions (T1-T5) |
| `defuel` | dict | Defuel sequence timing |
| `refuel` | dict | Refuel sequence timing |
| `refuel_system` | dict | Refuel hardware parameters |
| `probe_failure` | dict | Failure detection thresholds |
| `injected_errors` | dict | Error source magnitudes for validation |

### `fuel` Section

| Key | Type | Unit | Description |
|-----|------|------|-------------|
| `density_lab_lb_per_gal` | float | lb/gal | Lab-measured density at reference temp |
| `dielectric_nominal` | float | dimensionless | Dielectric constant (kappa) at 60 deg F |
| `fuel_type` | string | | Fuel grade identifier |
| `density_model_a` | float | lb/gal per unit kappa | Slope of linear density model |
| `density_model_b` | float | lb/gal | Intercept of linear density model |
| `reference_temp_F` | float | deg F | Calibration reference temperature |
| `density_temp_coef` | float | lb/gal per deg F | d(rho)/dT coefficient |
| `dielectric_temp_coef` | float | per deg F | d(kappa)/dT coefficient |
| `enable_temperature_term` | bool | | Include explicit temperature term in density model |

### `tanks` Section (per tank)

| Key | Type | Unit | Description |
|-----|------|------|-------------|
| `name` | string | | Human-readable tank name |
| `probe_type` | string | | `"real"`, `"real_pseudo_combo"`, or `"pure_pseudo"` |
| `floor_wl` | float | in | Tank floor waterline |
| `ceiling_wl` | float | in | Tank ceiling waterline |
| `blend_zone_wl` | list[float] | in | (T3 only) Lower and upper WL of blend transition |
| `pseudo_source` | string | | (T5 only) Source tank for projection |
| `pseudo_dx` | float | in | (T5 only) FS offset from source tank |
| `pseudo_dy` | float | in | (T5 only) BL offset from source tank |

---

## 2. H-V Table Data

### 2a. `data/tank_system.json`

Human-readable JSON containing all 1,105 height-volume tables (5 tanks x 13 pitch x 17 roll).

```json
{
  "pitch_range": [-6.0, -5.0, ..., 5.0, 6.0],     // 13 values, degrees
  "roll_range": [-8.0, -7.0, ..., 7.0, 8.0],       // 17 values, degrees
  "tanks": {
    "1": {
      "name": "Forward",
      "tank_id": 1,
      "probe_type": "real",
      "geometry": {
        "fs_min": 195.0,    // Fuselage station bounds (inches)
        "fs_max": 225.0,
        "bl_min": -15.0,    // Buttline bounds (inches)
        "bl_max": 15.0,
        "wl_min": 88.0,     // Waterline bounds (inches)
        "wl_max": 104.0
      },
      "probes": [
        {
          "name": "T1_probe",
          "base_fs": 210.0,        // Probe physical base (FS, BL, WL) in inches
          "base_bl": -0.5,
          "base_wl": 88.24,
          "top_fs": 210.0,         // Probe physical top (FS, BL, WL) in inches
          "top_bl": 0.5,
          "top_wl": 103.68,
          "active_length": 15.44,  // Physical length in inches (top_wl - base_wl)
          "tilt_deg": 3.706        // Tilt from vertical in degrees
        }
      ],
      "tables": [
        [                          // tables[pitch_idx][roll_idx]
          {
            "pitch_deg": -6.0,
            "roll_deg": -8.0,
            "N": 37,              // Number of height breakpoints
            "heights_rel": [...],  // Height relative to probe base (inches)
            "volumes_in3": [...],  // Fuel volume at each height (cubic inches)
            "volumes_gal": [...],  // Fuel volume at each height (US gallons)
            "cg_fs": [...],        // CG fuselage station at each height (inches)
            "cg_bl": [...],        // CG buttline at each height (inches)
            "cg_wl": [...]         // CG waterline at each height (inches)
          }
          // ... 16 more roll entries
        ]
        // ... 12 more pitch entries
      ]
    }
    // ... tanks "2" through "5"
  }
}
```

**Key detail**: `heights_rel` is measured **relative to the probe base WL**, not the tank floor. For T1, a `heights_rel` value of 0.0 corresponds to WL 88.24. Negative values represent fuel below the probe base. The range extends 1" below the tank floor and 1" above the tank ceiling.

**CG values**: `cg_fs`, `cg_bl`, `cg_wl` may contain `null` for zero-fuel entries where CG is undefined.

### 2b. `data/tank_system.mat`

MATLAB-format version of the same data. Variables in the .mat file:

| Variable | Size | Type | Description |
|----------|------|------|-------------|
| `pitch_range` | 1x13 | double | Pitch breakpoints in degrees |
| `roll_range` | 1x17 | double | Roll breakpoints in degrees |
| `T{n}_heights` | 13x17 | cell | Cell array of height vectors (inches, relative to probe base) |
| `T{n}_volumes` | 13x17 | cell | Cell array of volume vectors (cubic inches) |
| `T{n}_cg_fs` | 13x17 | cell | Cell array of CG-FS vectors (inches) |
| `T{n}_cg_bl` | 13x17 | cell | Cell array of CG-BL vectors (inches) |
| `T{n}_cg_wl` | 13x17 | cell | Cell array of CG-WL vectors (inches) |
| `T{n}_fs_min`, `T{n}_fs_max` | scalar | double | Tank FS bounds |
| `T{n}_bl_min`, `T{n}_bl_max` | scalar | double | Tank BL bounds |
| `T{n}_wl_min`, `T{n}_wl_max` | scalar | double | Tank WL bounds |
| `T{n}_probe1_name` | string | char | Probe name |
| `T{n}_probe1_base_wl` | scalar | double | Probe base WL (inches) |
| `T{n}_probe1_top_wl` | scalar | double | Probe top WL (inches) |
| `T{n}_probe1_active_length` | scalar | double | Probe length (inches) |
| `T{n}_probe1_tilt_deg` | scalar | double | Probe tilt from vertical (degrees) |

Each cell `T{n}_heights{pi, ri}` contains a 1xN vector where N is the number of height breakpoints (typically 37-49 depending on tank height). The cell indexing is `{pitch_index, roll_index}` where pitch_index=1 corresponds to -6 deg and roll_index=1 corresponds to -8 deg.

---

## 3. Simulation Sequences

### 3a. `data/defuel_sequence.csv` (1000 rows, 51 columns)

Time-history data from a complete defuel simulation. One row per 1-second time step.

#### Global Columns

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `sample` | int | | Sample index (0 to 999) |
| `time_s` | float | s | Simulation time |
| `pitch_deg` | float | deg | Aircraft pitch angle (positive = nose up) |
| `roll_deg` | float | deg | Aircraft roll angle (positive = right wing down) |
| `density_system` | float | lb/gal | System-computed density (from dielectric, includes bias + drift) |
| `density_lab` | float | lb/gal | True lab density (ground truth) |
| `density_error` | float | lb/gal | density_system - density_lab |
| `total_indicated_volume_gal` | float | gal | Sum of all tank indicated volumes |
| `total_true_volume_gal` | float | gal | Sum of all tank true volumes |
| `total_indicated_weight_lb` | float | lb | Total indicated fuel weight |
| `total_true_weight_lb` | float | lb | Total true fuel weight |
| `total_weight_error_lb` | float | lb | indicated - true weight |
| `phase` | int | | Drain phase (1-4, see below) |
| `active_tanks` | string | | Python list of tank IDs being drained |
| `scale_gross_weight_lb` | float | lb | Scale reading at checkpoints (NaN between checkpoints) |
| `dry_weight_lb` | float | lb | Aircraft dry weight (constant 12000) |

#### Per-Tank Columns (repeated for T1 through T5)

| Column Pattern | Type | Unit | Description |
|---------------|------|------|-------------|
| `probe_height_T{n}` | float | in | Raw probe height reading (before failure detection) |
| `indicated_volume_gal_T{n}` | float | gal | Volume from H-V table lookup |
| `indicated_weight_lb_T{n}` | float | lb | indicated_volume x system_density |
| `true_volume_gal_T{n}` | float | gal | True volume computed from geometry |
| `true_weight_lb_T{n}` | float | lb | true_volume x lab_density |
| `volume_error_in3_T{n}` | float | in^3 | indicated - true volume in cubic inches |
| `fuel_wl_T{n}` | float | in | True fuel surface waterline at tank reference point |

#### Defuel Phases

| Phase | Samples | Active Tanks | Description |
|-------|---------|--------------|-------------|
| 1 | 0-199 | T1 | Forward tank drains first (smallest, highest) |
| 2 | 200-549 | T2, T4 | Wing tanks drain simultaneously |
| 3 | 550-749 | T5 | Aft tank drains |
| 4 | 750-999 | T3 | Center collector drains last |

#### Scale Weight Checkpoints

Scale readings (`scale_gross_weight_lb`) are recorded at samples 0, 200, 550, 750, and 999. All other rows contain NaN. To compute fuel weight from scale: `fuel_weight = scale_gross_weight_lb - dry_weight_lb`.

### 3b. `data/refuel_sequence.csv` (800 rows, 51 columns)

Same column structure as defuel. Fill order is reversed:

| Phase | Samples | Active Tanks | Description |
|-------|---------|--------------|-------------|
| 1 | 0-249 | T3 | Center collector fills first |
| 2 | 250-449 | T5 | Aft tank fills |
| 3 | 450-699 | T2, T4 | Wing tanks fill simultaneously |
| 4 | 700-799 | T1 | Forward tank fills last |

Scale checkpoints at samples 0, 250, 450, 700, and 799.

### 3c. `data/defuel_sequence.mat` and `data/refuel_sequence.mat`

MATLAB-format versions. Each CSV column becomes a MATLAB variable of the same name containing a 1xN double vector. String columns (`active_tanks`) are stored as cell arrays.

---

## 4. Simulink Data Dictionary: `matlab/data/FuelGaugingData.sldd`

The data dictionary is generated by `run_full_build.m` and contains:

### Bus Definitions (6)

| Bus Name | Elements | Description |
|----------|----------|-------------|
| `AttitudeBus` | pitch_deg (deg), roll_deg (deg) | Aircraft attitude |
| `ProbeReadingBus` | probe_height (in), fuel_wl (in), is_valid (bool), failure_code (uint8) | Single probe output |
| `BIT_StatusBus` | all_probes_healthy (bool), num_failed_probes (uint8), failure_flags (bool[5]), failure_codes (uint8[5]) | System health |
| `TankIndicationBus` | volume_in3 (in^3), volume_gal (gal), weight_lb (lb), probe_data (ProbeReadingBus), tank_id (uint8) | Per-tank indication |
| `SystemIndicationBus` | total_weight_lb (lb), total_volume_gal (gal), density_system (lb/gal), bit_status (BIT_StatusBus) | System totals |
| `RefuelStatusBus` | is_active (bool), is_complete (bool), valve_positions (double[5]), hi_level_states (bool[5]), flow_rates_gpm (gal/min[5]), total_delivered_gal (gal) | Refuel status |

### Parameters (24)

All stored as `Simulink.Parameter` with `DataType = 'double'`. See `config/system_config.yaml` for values and descriptions.

### Lookup Tables (5)

| Object | Dimensions | Breakpoints | Description |
|--------|-----------|-------------|-------------|
| `LUT_T1` | 37 x 13 x 17 | height x pitch x roll | T1 Forward H-V table |
| `LUT_T2` | 41 x 13 x 17 | height x pitch x roll | T2 Left H-V table |
| `LUT_T3` | 45 x 13 x 17 | height x pitch x roll | T3 Center H-V table |
| `LUT_T4` | 41 x 13 x 17 | height x pitch x roll | T4 Right H-V table |
| `LUT_T5` | 49 x 13 x 17 | height x pitch x roll | T5 Aft H-V table |

Table values are in cubic inches. Breakpoints:
- **Height**: inches relative to probe base WL (0.5" step, extends 1" beyond tank bounds)
- **Pitch**: -6 to +6 degrees in 1-degree steps (13 values)
- **Roll**: -8 to +8 degrees in 1-degree steps (17 values)

Interpolation: linear point-slope. Extrapolation: clip.

### Tank Parameters

`TankParams` is a 1x5 struct array with fields:

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `name` | char | | Tank name |
| `tank_id` | uint8 | | Tank ID (1-5) |
| `fs_min`, `fs_max` | double | in | FS bounds |
| `bl_min`, `bl_max` | double | in | BL bounds |
| `wl_min`, `wl_max` | double | in | WL bounds |
| `base_area` | double | in^2 | Tank floor area (length x width) |
| `height` | double | in | Tank height (wl_max - wl_min) |
| `probe_base`, `probe_top` | double | in | Probe base/top waterline |
| `lower_base`, `lower_top` | double | in | (T3 only) Lower probe bounds; NaN for other tanks |
| `upper_base`, `upper_top` | double | in | (T3 only) Upper probe bounds; NaN for other tanks |
| `max_fill` | double | in | Maximum fill waterline |
| `probe_type` | uint8 | | 1=real, 2=combo, 3=pseudo |

---

## 5. Plots: `plots/`

Generated by `src/plot_validation.py` and `src/visualize_3d.py`:

| File | Description |
|------|-------------|
| `01_tank_layout.png` | Plan view and side view of all 5 tanks with probes |
| `02_hv_curves.png` | H-V curves at 6 attitudes per tank |
| `03_probe_coverage.png` | Probe height ranges vs tank height ranges |
| `04_defuel_error_timeseries.png` | 4-panel defuel error analysis |
| `05_error_vs_fuel_level.png` | Hysteresis check (defuel vs refuel error) |
| `06_attitude_heatmap.png` | Mean error vs pitch/roll heatmap |
| `07_density_error.png` | Density vs volume error decomposition |
| `08_per_tank_error.png` | Per-tank mean absolute volume error bar chart |
| `09_3d_tank_views.png` | 3D rendered views of all tanks |
| `10_3d_fill_sequence.png` | 3D fill level animation frames |
| `11_3d_attitude_comparison.png` | 3D views at different attitudes |
| `12_3d_refuel_system.png` | 3D view with refuel adapter and manifold |
| `13_3d_probe_detail.png` | 3D close-up of probes with sense regions |

---

## 6. Units Convention

All data files use these units consistently:

| Quantity | Unit | Notes |
|----------|------|-------|
| Length/position | inches (in) | FS, BL, WL, probe heights |
| Volume | cubic inches (in^3) | Internal; divide by 231 for gallons |
| Volume (display) | US gallons (gal) | 1 gal = 231 in^3 |
| Weight | pounds (lb) | Fuel weight = volume_gal x density_lb_per_gal |
| Density | lb/gal | Pounds per US gallon |
| Angle | degrees (deg) | Pitch and roll |
| Temperature | degrees Fahrenheit (deg F) | Optional temperature compensation |
| Time | seconds (s) | Simulation time |
| Flow rate | gal/min (GPM) | Refuel system |
| Pressure | psi | Refuel supply pressure |
| Dielectric | dimensionless | Capacitance ratio (kappa) |
