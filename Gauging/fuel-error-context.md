# Fuel Gauging Error Analysis — Project Context

## Purpose

This document provides all background context needed to build an advanced error decomposition and analysis toolset for aircraft fuel quantity indication. The goal is to identify where gauging error originates by analyzing recorded flight/ground data against known scale weights, using statistical methods and machine learning to find patterns invisible to manual inspection.

---

## System Overview

### What the Fuel Gauging System Does

The aircraft has multiple fuel tanks. Each tank's fuel quantity is determined by capacitance probes that measure the wetted height of fuel on the probe. That height, combined with aircraft pitch and roll attitude, is used to look up a volume from pre-computed tables. Volume is converted to weight using a density value computed from the measured dielectric constant of the fuel. All tank weights are summed to produce total indicated fuel quantity.

### The Measurement Chain (Error Propagation Path)

Each step in this chain can introduce error:

1. **Physical fuel state** — True volume/weight in each tank, governed by gravity, pitch, and roll.
2. **Probe measurement** — Capacitance probes output a wetted height. Error sources: probe accuracy, installation tolerances, dielectric properties, contamination.
3. **Probe-to-effective-height logic** — For tanks with multiple probes or no probes, raw readings are combined or projected to produce an effective height. This is where pseudo probe math occurs. Error sources: projection assumptions, attitude measurement accuracy, blending logic in overlap regions.
4. **Height-to-volume table lookup** — The effective height plus pitch/roll selects an interpolation point in pre-computed tables derived from NX CAD geometry. Error sources: table discretization, interpolation method, variable-length table handling, possible errors in the software team's table conversion code.
5. **Volume-to-weight conversion** — Volume × density = weight. Density is computed from the dielectric constant by the system. Error source: dielectric-to-density model accuracy.
6. **Summation** — All tank weights sum to total indicated fuel. The total is compared against scale-measured gross weight minus known dry weight.

### Three Probe Types

**Real probe:** A single physical capacitance probe directly in the tank. Height measurement maps directly to a height-vs-volume lookup table indexed by pitch and roll.

**Real-Pseudo combination:** Two physical probes (upper and lower) with overlapping vertical coverage. Their readings are blended in the overlap zone using a linear weighted average, producing a single "pseudo probe" effective height that spans the full tank height range. The blend transitions from the lower probe to the upper probe as fuel rises through the overlap region.

**Pure Pseudo probe:** No physical probe exists in the tank. The system takes readings from real probes in an adjacent/connected tank and projects the fuel plane to the pseudo probe's location using trigonometric projection:

```
z_fuel_at_pseudo = z_fuel_at_real_probe + dx * tan(pitch) + dy * tan(roll)
```

Where dx and dy are the spatial offsets between the real probe location and the pseudo probe location. The projected fuel height is then clamped to the pseudo probe's valid range and used for table lookup.

### Table Structure

Each tank has a cell array of height-vs-volume lookup tables indexed by pitch and roll attitude. Key characteristics:
- Multiple pitch angles × multiple roll angles = one table per attitude combination
- The number of data points (N) in each table varies per attitude condition (variable-length)
- Tables also contain CG (center of gravity) data: cg_x, cg_y, cg_z as functions of height
- Bilinear interpolation is used across pitch/roll, then linear interpolation on height within the blended table
- Tables are stored in MM1D format (Multi-1D lookup) in MATLAB files

### Known Uncertainty in the Table Pipeline

The NX CAD volumes are assumed correct (geometry was properly sliced). However, the conversion from the original Excel-format tables to the MM1D computer-readable format was done by the software team using their own code. This conversion is a potential error source — the analyst does not have full visibility into what that code does and whether it correctly handles variable-length tables, index ordering, or interpolation boundaries.

---

## Available Data

### Dataset A — Defuel Sequence
- Time history of continuous defueling
- Many timestamped rows as fuel is removed
- Contains: all probe heights, pitch, roll, each tank's indicated volume, system-computed density, total indicated fuel weight
- Independent reference: cumulative fuel removed (by scale or meter)
- Lab-tested fuel density sample available for comparison

### Dataset B — Refuel Sequence
- Time history of continuous refueling
- Same data fields as defuel but in reverse (tanks filling)
- Different tanks fill at different rates depending on fuel distribution system
- Lab-tested fuel density sample available

### Dataset C — Mission Snapshots
- Before/after pairs: aircraft weighed before mission, gauging data captured at power-on; weighed after mission, gauging data captured before power-down
- Multiple mission days available
- Real-world pitch/roll conditions during mission
- Lower time resolution than defuel/refuel but real operational conditions

### What CAN Be Observed Per Timestamp Row
- Raw probe heights (effectively continuous, limited only by data recording frequency)
- Pitch and roll attitude
- Computed pseudo probe heights (from the system)
- Each tank's indicated volume
- System-computed fuel density
- Total indicated fuel weight
- Scale-measured gross weight (at specific points)

### What CANNOT Be Directly Observed
- True fuel weight in each individual tank (no individual tank scale measurements)
- The internal state of the computer's table interpolation

---

## Analysis Objectives

### Primary Goal
Decompose the total fuel quantity indication error (indicated total vs. scale-measured total) into contributions from individual tanks, probe regions, attitude conditions, density computation, and table lookup behavior.

### Specific Questions to Answer
1. Which tanks contribute most to total error? (Without individual tank ground truth, this requires indirect methods)
2. Are there specific probe height ranges where error spikes? (Suggesting table issues or probe nonlinearity)
3. Does error correlate with attitude (pitch/roll)? (Suggesting table interpolation issues or projection errors)
4. Does the dielectric-to-density conversion introduce systematic bias? (Compare system density to lab density)
5. Are there error patterns during probe transitions — e.g., when a real-pseudo tank transitions from lower to upper probe in the blend zone?
6. Do pseudo-projected tanks show higher error sensitivity to attitude than real-probe tanks?
7. Are there hysteresis effects (different error during fill vs. drain at the same fuel level)?

### Methods to Employ
- **Correlation analysis:** Pearson/Spearman correlation between total error and every available feature (each probe height, each tank quantity, pitch, roll, density, rate of change of each probe)
- **Sliding window analysis:** Compute error statistics in moving windows along the defuel/refuel timeline to see where error grows or shifts
- **Feature importance (Random Forest / Gradient Boosting):** Train a model to predict total error from all available features; extract feature importances to identify which inputs most strongly predict error
- **Neural network regression:** Train a network to predict error from inputs; use SHAP or gradient-based attribution to identify which features drive predictions
- **Residual analysis:** After removing known/modeled error sources, examine what structure remains in the residuals
- **Change-point detection:** Identify moments in the defuel/refuel where error behavior changes abruptly — correlate with tank transitions
- **Sensitivity analysis:** Perturb individual inputs (one probe height, one attitude angle) and observe the effect on predicted error
- **Density error isolation:** Compare system-computed density to lab-measured density; compute the fuel weight error attributable solely to density error vs. volume error

---

## Key Considerations

- All tank names, probe locations, waterlines, and geometry values in this project are sanitized. Do not assume specific numbers from any prior modeling work — use only what the user provides in the actual data files.
- The user will specify tank fill/drain order and tank identities when providing CUI data.
- The analysis code should be written in Python (preferred for ML/data science tooling) but the user's source data is in MATLAB format (.mat files). The code should handle loading .mat files.
- Visualizations are critical — the user needs to see error evolution over time, correlation heatmaps, feature importance plots, and per-tank error contribution estimates.
- The tools should be modular so the user can point them at different datasets (defuel, refuel, mission snapshots) without restructuring code.
