# Simulink Model Schema — Fuel Gauging System

**Target Platform:** MATLAB R2025b with Simulink, Stateflow (optional)

---

## 1. Project Structure

The MATLAB Project (`.prj`) organizes all files with managed paths, labels, and startup/shutdown hooks.

```
FuelGaugingProject/
│
├── FuelGaugingProject.prj            ← MATLAB Project file
│
├── startup.m                         ← Runs on project open
├── shutdown.m                        ← Runs on project close
│
├── data/
│   ├── FuelGaugingData.sldd          ← Simulink Data Dictionary (single source of truth)
│   ├── tank_system.mat               ← H-V tables from Python pipeline
│   ├── tank_system_matlab.mat        ← H-V tables from MATLAB pipeline
│   ├── defuel_sequence.mat           ← Simulated defuel time history
│   └── refuel_sequence.mat           ← Simulated refuel time history
│
├── models/
│   ├── FuelGaugingSystem.slx         ← Top-level model (harness)
│   ├── ProbeModel_Real.slx           ← Referenced model: real probe
│   ├── ProbeModel_Combo.slx          ← Referenced model: T3 combo probe
│   ├── ProbeModel_Pseudo.slx         ← Referenced model: T5 pseudo probe
│   ├── ProbeFailureDetector.slx      ← Referenced model: failure detection
│   ├── HV_TableLookup.slx            ← Referenced model: height → volume
│   ├── DensityComputation.slx        ← Referenced model: dielectric → density
│   ├── WeightSummation.slx           ← Referenced model: volume × density → weight
│   └── RefuelSystem.slx              ← Referenced model: refuel + shutoff logic
│
├── scripts/
│   ├── setup_project.m               ← Creates project and data dictionary
│   ├── build_data_dictionary.m       ← Populates .sldd with all parameters
│   ├── build_simulink_model.m        ← Programmatic model construction
│   ├── run_defuel_simulation.m       ← Run defuel scenario
│   ├── run_refuel_simulation.m       ← Run refuel scenario
│   ├── validate_model.m             ← Post-build validation checks
│   └── generate_hv_tables.m         ← H-V table generation (MATLAB)
│
├── tests/
│   ├── cross_validate.m             ← Python vs MATLAB table comparison
│   └── test_model_build.m           ← Verify model builds and simulates
│
├── utilities/
│   └── load_sequence_data.m         ← Helper to load .mat sequences into timeseries
│
└── work/                            ← Simulation artifacts (slprj cache, generated code)
```

### Project Labels

| Category | Labels | Applied To |
|----------|--------|-----------|
| `Classification` | `Design`, `Test`, `Script`, `Data`, `Utility` | All files |
| `Component` | `ProbeModel`, `FailureDetection`, `Lookup`, `Density`, `Weight`, `Refuel` | Model files |

---

## 2. Data Dictionary (`FuelGaugingData.sldd`)

All parameters, bus definitions, and lookup table objects reside in the data dictionary — nothing in the base workspace during simulation. This ensures reproducibility and prevents workspace pollution.

### 2.1 Bus Definitions

```
ProbeReadingBus
├── probe_height         double (1×1)    [in]    Wetted height on probe
├── fuel_wl              double (1×1)    [in]    Fuel surface waterline
├── is_valid             boolean (1×1)           True if reading passed health checks
└── failure_code         uint8 (1×1)             0=OK, 1=OpenCkt, 2=ShortCkt, 3=RateExceed, 4=Stale

TankIndicationBus
├── volume_in3           double (1×1)    [in³]   Indicated volume from H-V table
├── volume_gal           double (1×1)    [gal]   Volume in gallons
├── weight_lb            double (1×1)    [lb]    Indicated weight (vol × density)
├── probe_data           Bus: ProbeReadingBus    Probe measurement details
└── tank_id              uint8 (1×1)             Tank identifier 1-5

SystemIndicationBus
├── total_weight_lb      double (1×1)    [lb]    Sum of all tank weights
├── total_volume_gal     double (1×1)    [gal]   Sum of all tank volumes
├── density_system       double (1×1)    [lb/gal] System-computed density
├── tank                 Bus: TankIndicationBus (1×5)  Per-tank indication
└── bit_status           Bus: BIT_StatusBus      Built-in test status

BIT_StatusBus
├── all_probes_healthy   boolean (1×1)
├── num_failed_probes    uint8 (1×1)
├── failure_flags        boolean (1×5)           Per-tank failure flag
└── failure_codes        uint8 (1×5)             Per-tank failure code

RefuelStatusBus
├── is_active            boolean (1×1)           Refuel in progress
├── is_complete          boolean (1×1)           All tanks full
├── valve_positions      double (1×5)            Per-tank valve position [0-1]
├── hi_level_states      boolean (1×5)           Per-tank high-level sensor
├── flow_rates_gpm       double (1×5)            Per-tank flow rate
└── total_delivered_gal  double (1×1)            Cumulative fuel delivered

AttitudeBus
├── pitch_deg            double (1×1)    [deg]   Aircraft pitch
└── roll_deg             double (1×1)    [deg]   Aircraft roll
```

### 2.2 Simulink.Parameter Objects

| Parameter Name | Value | Type | Description |
|---------------|-------|------|-------------|
| `ULLAGE_FRAC` | 0.02 | double | Ullage expansion reserve fraction |
| `UNUSABLE_FRAC` | 0.015 | double | Unusable fuel fraction |
| `IN3_PER_GAL` | 231.0 | double | Cubic inches per US gallon |
| `DENSITY_MODEL_A` | 4.667 | double | Density model slope [lb/gal per κ] |
| `DENSITY_MODEL_B` | -2.857 | double | Density model intercept [lb/gal] |
| `DENSITY_BIAS` | 1.003 | double | Density bias multiplier (0.3% high) |
| `KAPPA_NOMINAL` | 2.05 | double | Nominal fuel dielectric constant |
| `DENSITY_LAB` | 6.71 | double | Lab-measured density [lb/gal] |
| `PROBE_NOISE_STD` | 0.02 | double | Probe measurement noise σ [in] |
| `SUPPLY_PRESSURE_PSI` | 55.0 | double | Refuel supply pressure |
| `MANIFOLD_WL` | 78.0 | double | Manifold elevation [in WL] |
| `MAX_FLOW_GPM` | 60.0 | double | Max total refuel flow rate |
| `VALVE_CLOSE_TIME` | 0.5 | double | Shutoff valve close time [s] |
| `VALVE_OPEN_TIME` | 0.3 | double | Shutoff valve open time [s] |
| `VALVE_CAPACITY_GPM` | 15.0 | double | Per-valve max flow rate |
| `FAILURE_OPEN_THRESH` | -0.1 | double | Open circuit threshold [in] |
| `FAILURE_SHORT_MARGIN` | 0.5 | double | Short circuit margin above max [in] |
| `FAILURE_RATE_THRESH` | 2.0 | double | Rate exceedance threshold [in/s] |
| `BLEND_LO_WL` | 90.0 | double | T3 blend zone lower bound [WL] |
| `BLEND_HI_WL` | 92.0 | double | T3 blend zone upper bound [WL] |

### 2.3 Per-Tank Parameter Structures

Stored as `Simulink.Parameter` with struct values:

```matlab
TankParams(1).name       = 'Forward';
TankParams(1).fs_min     = 195.0;    TankParams(1).fs_max     = 225.0;
TankParams(1).bl_min     = -15.0;    TankParams(1).bl_max     = 15.0;
TankParams(1).wl_min     = 88.0;     TankParams(1).wl_max     = 104.0;
TankParams(1).base_area  = 900.0;    % in² (30 × 30)
TankParams(1).height     = 16.0;
TankParams(1).probe_base = 88.24;    TankParams(1).probe_top  = 103.68;
TankParams(1).max_fill   = 103.68;   % wl_max - ullage

TankParams(2).name       = 'Left';
TankParams(2).fs_min     = 235.0;    TankParams(2).fs_max     = 285.0;
TankParams(2).bl_min     = -62.0;    TankParams(2).bl_max     = -22.0;
TankParams(2).wl_min     = 85.0;     TankParams(2).wl_max     = 103.0;
TankParams(2).base_area  = 2000.0;   % in² (50 × 40)
TankParams(2).height     = 18.0;
TankParams(2).probe_base = 85.27;    TankParams(2).probe_top  = 102.64;
TankParams(2).max_fill   = 102.64;

TankParams(3).name       = 'Center';
TankParams(3).fs_min     = 235.0;    TankParams(3).fs_max     = 285.0;
TankParams(3).bl_min     = -20.0;    TankParams(3).bl_max     = 20.0;
TankParams(3).wl_min     = 80.0;     TankParams(3).wl_max     = 100.0;
TankParams(3).base_area  = 2000.0;   % in² (50 × 40)
TankParams(3).height     = 20.0;
TankParams(3).lower_base = 80.30;    TankParams(3).lower_top  = 92.00;
TankParams(3).upper_base = 90.00;    TankParams(3).upper_top  = 99.60;
TankParams(3).max_fill   = 99.60;

TankParams(4).name       = 'Right';
TankParams(4).fs_min     = 235.0;    TankParams(4).fs_max     = 285.0;
TankParams(4).bl_min     = 22.0;     TankParams(4).bl_max     = 62.0;
TankParams(4).wl_min     = 85.0;     TankParams(4).wl_max     = 103.0;
TankParams(4).base_area  = 2000.0;
TankParams(4).height     = 18.0;
TankParams(4).probe_base = 85.27;    TankParams(4).probe_top  = 102.64;
TankParams(4).max_fill   = 102.64;

TankParams(5).name       = 'Aft';
TankParams(5).fs_min     = 295.0;    TankParams(5).fs_max     = 335.0;
TankParams(5).bl_min     = -17.5;    TankParams(5).bl_max     = 17.5;
TankParams(5).wl_min     = 83.0;     TankParams(5).wl_max     = 105.0;
TankParams(5).base_area  = 1400.0;   % in² (40 × 35)
TankParams(5).height     = 22.0;
TankParams(5).pseudo_dx  = 55.0;     TankParams(5).pseudo_dy  = 0.0;
TankParams(5).max_fill   = 104.56;
```

### 2.4 Simulink.LookupTable Objects

One `Simulink.LookupTable` per tank, using 3-D interpolation (height × pitch × roll → volume).

```matlab
% Structure for each tank's LUT:
LUT_T{n} = Simulink.LookupTable;
LUT_T{n}.Table.Value     = <3D array: n_height × n_pitch × n_roll>
LUT_T{n}.Breakpoints(1)  = <height vector relative to probe base> [in]
LUT_T{n}.Breakpoints(2)  = <pitch vector> [deg]
LUT_T{n}.Breakpoints(3)  = <roll vector> [deg]
LUT_T{n}.StructTypeInfo.Name = sprintf('LUT_T%d_Type', n);
```

Breakpoint sizes per tank:

| Tank | Height Points | Pitch Points | Roll Points | Total Entries |
|------|--------------|-------------|------------|---------------|
| T1 | 37 | 13 | 17 | 8,177 |
| T2 | 39 | 13 | 17 | 8,619 |
| T3 | 45 | 13 | 17 | 9,945 |
| T4 | 39 | 13 | 17 | 8,619 |
| T5 | 49 | 13 | 17 | 10,829 |

Total data: ~46,189 double values (~360 KB) in the data dictionary.

---

## 3. Model Reference Hierarchy

```
FuelGaugingSystem.slx  (top-level harness)
│
├── ProbeModel_Real.slx ×3         (T1, T2, T4 — same model, different params)
│   Inputs:  fuel_wl, attitude (Bus: AttitudeBus)
│   Outputs: probe_reading (Bus: ProbeReadingBus)
│   Params:  probe_base_wl, probe_top_wl, probe_ref_fs, probe_ref_bl
│
├── ProbeModel_Combo.slx ×1        (T3)
│   Inputs:  fuel_wl, attitude (Bus: AttitudeBus)
│   Outputs: probe_reading (Bus: ProbeReadingBus)
│   Params:  lower_base, lower_top, upper_base, upper_top, blend_lo, blend_hi
│
├── ProbeModel_Pseudo.slx ×1       (T5)
│   Inputs:  fuel_wl_local, t3_probe_reading (Bus: ProbeReadingBus), attitude
│   Outputs: probe_reading (Bus: ProbeReadingBus)
│   Params:  pseudo_dx, pseudo_dy, tank_wl_min, tank_wl_max
│
├── ProbeFailureDetector.slx ×5    (one per tank — same model, different params)
│   Inputs:  raw_reading (Bus: ProbeReadingBus)
│   Outputs: validated_reading (Bus: ProbeReadingBus)
│   Params:  open_thresh, short_thresh, rate_thresh, max_height
│
├── HV_TableLookup.slx ×5          (one per tank — same model, different LUT)
│   Inputs:  probe_height [in], pitch [deg], roll [deg]
│   Outputs: volume_in3 [in³]
│   Params:  LUT_T{n} (Simulink.LookupTable from data dictionary)
│
├── DensityComputation.slx ×1
│   Inputs:  dielectric_constant [κ]
│   Outputs: density_lb_per_gal [lb/gal]
│   Params:  DENSITY_MODEL_A, DENSITY_MODEL_B, DENSITY_BIAS
│
├── WeightSummation.slx ×1
│   Inputs:  volume_in3[5], density [lb/gal]
│   Outputs: system_indication (Bus: SystemIndicationBus)
│
└── RefuelSystem.slx ×1
    Inputs:  refuel_cmd [bool], fuel_wl[5], attitude
    Outputs: refuel_status (Bus: RefuelStatusBus)
    Params:  SUPPLY_PRESSURE_PSI, MANIFOLD_WL, VALVE_CAPACITY_GPM, TankParams
```

### Model Reference Instance Mapping

The top-level model instantiates each referenced model with instance-specific parameters using Model block `ParameterArgumentValues`:

| Instance Block | Referenced Model | Parameter Overrides |
|---------------|-----------------|-------------------|
| `T1_Probe` | `ProbeModel_Real` | `probe_base_wl=88.24, probe_top_wl=103.68` |
| `T2_Probe` | `ProbeModel_Real` | `probe_base_wl=85.27, probe_top_wl=102.64` |
| `T3_Probe` | `ProbeModel_Combo` | `lower_base=80.30, lower_top=92.00, ...` |
| `T4_Probe` | `ProbeModel_Real` | `probe_base_wl=85.27, probe_top_wl=102.64` |
| `T5_Probe` | `ProbeModel_Pseudo` | `pseudo_dx=55.0, pseudo_dy=0.0` |
| `T1_Failure` ... `T5_Failure` | `ProbeFailureDetector` | `max_height` per tank |
| `T1_Lookup` ... `T5_Lookup` | `HV_TableLookup` | `LUT_T{n}` object per tank |

---

## 4. Signal Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FuelGaugingSystem (Top Level)                       │
│                                                                             │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────────┐ │
│  │ FuelWL   │────▶│ ProbeModel   │────▶│ FailureDetect│────▶│ HV_Table  │ │
│  │ Inputs   │     │ (×5 inst.)   │     │ (×5 inst.)   │     │ (×5 inst.)│ │
│  │ (From WS)│     │              │     │              │     │           │ │
│  └──────────┘     │  ProbeReading│     │  ProbeReading│     │ vol_in3   │ │
│                   │  Bus out     │     │  Bus out     │     │ out       │ │
│  ┌──────────┐     └──────────────┘     └──────────────┘     └─────┬─────┘ │
│  │ Attitude │──┐                                                   │       │
│  │ (pitch,  │  │  ┌──────────────┐     ┌──────────────┐          │       │
│  │  roll)   │  └─▶│ Pseudo Proj  │     │ Density      │     ┌────▼─────┐ │
│  └──────────┘     │ (T5 only)    │     │ Computation  │────▶│ Weight   │ │
│                   └──────────────┘     └──────────────┘     │ Summation│ │
│  ┌──────────┐                                                │          │ │
│  │Dielectric│──────────────────────────────────────────────▶│          │ │
│  │ Input    │                                                └────┬─────┘ │
│  └──────────┘                                                     │       │
│                                                              ┌────▼─────┐ │
│  ┌──────────┐     ┌──────────────┐                          │ System   │ │
│  │ Refuel   │────▶│ RefuelSystem │                          │ Indicat. │ │
│  │ Command  │     │ (valves,HLS) │                          │ Bus Out  │ │
│  └──────────┘     └──────────────┘                          └──────────┘ │
│                                                                           │
│                   ┌──────────────┐                                       │
│                   │ Signal       │  ← Logs: all bus signals, error,      │
│                   │ Logging      │     per-tank weights, refuel status    │
│                   └──────────────┘                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. n-D Lookup Table Configuration

Each tank's H-V relationship is stored as a 3-D lookup table (height × pitch × roll → volume_in3).

### Block Configuration

```matlab
% In HV_TableLookup.slx:
%
% Block: 'HV_TableLookup/nD_Lookup'
% Type:  'simulink/Lookup Tables/n-D Lookup Table'
%
% Parameters:
%   NumberOfTableDimensions = '3'
%   DataSpecification       = 'Lookup table object'
%   LookupTableObject       = 'LUT_Tn'   ← model argument, resolved from data dict
%   InterpMethod            = 'Linear point-slope'
%   ExtrapMethod            = 'Clip'
%   DiagnosticForOutOfRangeInput = 'None'
```

### Data Flow Inside HV_TableLookup.slx

```
Inport: probe_height [in]  ──┐
Inport: pitch_deg    [deg] ──┼──▶ [n-D Lookup Table] ──▶ volume_in3 [in³] ──▶ Outport
Inport: roll_deg     [deg] ──┘
                                   ↑
                              LUT_Tn (from data dict)
```

### Table Data Format

The 3-D table array is organized as: `table(i_height, i_pitch, i_roll) = volume_in3`

- **Dimension 1 (height):** Probe height relative to probe base, 0.5" steps.
  Range varies per tank (from -1" below probe base to 1" above probe top).
- **Dimension 2 (pitch):** -6° to +6°, 1° steps (13 breakpoints).
- **Dimension 3 (roll):** -8° to +8°, 1° steps (17 breakpoints).

---

## 6. Probe Failure Detection Logic

### State Machine (per probe)

```
                ┌──────────────┐
                │   HEALTHY    │
                │              │
         ┌──────│ output = raw │──────┐
         │      │ LKG = raw    │      │
         │      └──────────────┘      │
         │             │              │
    [reset after N     │ [open_ckt    │ [short_ckt
     good readings]    │  OR rate_exc │  detected]
         │             │  OR stale]   │
         │      ┌──────▼──────┐       │
         │      │   FAILED    │       │
         └──────│              │◄─────┘
                │ output = LKG │
                │ code = type  │
                └──────────────┘
```

### Detection Thresholds

| Check | Condition | Latching |
|-------|-----------|----------|
| Open Circuit | `h < FAILURE_OPEN_THRESH` (-0.1") | Immediate |
| Short Circuit | `h > active_length + FAILURE_SHORT_MARGIN` (+0.5") | Immediate |
| Rate Exceedance | `|h(k) - h(k-1)| / dt > FAILURE_RATE_THRESH` (2.0 in/s) | Immediate |
| Stale Data | `|h(k) - h(k-1)| < 0.01` for `> 30s` | Time-delayed |

### Implementation Blocks

```
[Raw Height] ──┬──▶ [Compare < -0.1]    ──▶ open_fault  ──┐
               │                                           │
               ├──▶ [Compare > max+0.5] ──▶ short_fault ──┤
               │                                           ├──▶ [OR] ──▶ fault_flag
               ├──▶ [|Δh/Δt| > 2.0]    ──▶ rate_fault  ──┤
               │                                           │
               └──▶ [Stale Counter]     ──▶ stale_fault ──┘
                                                           │
[Raw Height] ──▶ [Switch] ◄── fault_flag                   │
                    │                                      │
               [LKG Memory] ◄──────────────────────────────┘
                    │
                    ▼
              [Validated Height]
```

---

## 7. Refuel System Logic

### Valve State Machine (per tank)

```
             refuel_cmd = 1
                  │
                  ▼
          ┌───────────────┐
          │  VALVE OPEN   │
          │  (filling)    │
          │               │
          │ flow = f(ΔP)  │
          └───────┬───────┘
                  │
           hi_level_sensor = 1
                  │
                  ▼
          ┌───────────────┐
          │ VALVE CLOSING │  ← 0.5s ramp-down
          │  (position    │
          │   ramping)    │
          └───────┬───────┘
                  │
            position = 0
                  │
                  ▼
          ┌───────────────┐
          │ VALVE CLOSED  │
          │  (latched)    │
          └───────────────┘
```

### Flow Distribution Model

```
For each tank t with valve open:
  h_above = max(0, fuel_wl(t) - MANIFOLD_WL)
  P_head  = 0.036 × density × h_above
  P_net   = max(0, SUPPLY_PRESSURE - P_head)
  k       = VALVE_CAPACITY / SUPPLY_PRESSURE
  Q_t     = valve_position(t) × k × P_net

If sum(Q) > MAX_FLOW_GPM:
  scale all flows by MAX_FLOW_GPM / sum(Q)
```

---

## 8. Signal Logging Strategy

### Logged Signals

| Signal Name | Source | Type | Rate |
|-------------|--------|------|------|
| `attitude` | Top-level input | AttitudeBus | Ts |
| `probe_raw_T{1-5}` | ProbeModel outputs | ProbeReadingBus | Ts |
| `probe_valid_T{1-5}` | FailureDetector outputs | ProbeReadingBus | Ts |
| `volume_T{1-5}` | HV_TableLookup outputs | double | Ts |
| `system_indication` | WeightSummation output | SystemIndicationBus | Ts |
| `refuel_status` | RefuelSystem output | RefuelStatusBus | Ts |
| `total_error` | Error computation | double | Ts |

### Configuration

```matlab
set_param('FuelGaugingSystem', ...
    'SignalLogging',     'on', ...
    'SignalLoggingName', 'logsout', ...
    'ReturnWorkspaceOutputs', 'on', ...
    'ReturnWorkspaceOutputsName', 'simout');
```

All logged signals are extracted post-simulation via:
```matlab
out = sim('FuelGaugingSystem');
logsout = out.logsout;
total_wt = logsout.getElement('system_indication').Values.total_weight_lb;
```

---

## 9. Simulation Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Solver | `ode23tb` | Stiff-capable, good for valve dynamics |
| Max Step Size | `0.1` s | Captures valve close transient (0.5s) |
| Stop Time | From data | Matches sequence length |
| Signal Logging | On | `logsout` variable |
| Data Import | `From Workspace` | Loads from `Simulink.SimulationData.Dataset` |
| Data Dictionary | `FuelGaugingData.sldd` | All parameters/buses |

---

## 10. Setup Sequence (Quick Reference)

```matlab
%% 1. Create project and data dictionary
setup_project;              % Creates .prj, folders, paths, labels

%% 2. Generate H-V tables (if not already done)
generate_hv_tables;         % Produces tank_system_matlab.mat

%% 3. Populate data dictionary
build_data_dictionary;      % Buses, params, LUT objects → .sldd

%% 4. Build Simulink models
build_simulink_model;       % Creates all .slx files

%% 5. Validate
validate_model;             % Checks build, buses, runs test sim

%% 6. Run scenarios
run_defuel_simulation;      % Loads defuel data, runs sim, plots
run_refuel_simulation;      % Loads refuel data, runs sim, plots
```
