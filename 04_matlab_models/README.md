# MATLAB Models

High-fidelity MATLAB models for fuel tank geometry, volume calculations, and property arrays.

## Files

- **fuel_vol_tank_combo.m** - **Main volume calculation function**
  - Calculates individual fuel volumes in multi-compartment tanks
  - Handles pitch and roll angle dependencies (3D orientation)
  - Uses bilinear interpolation for smooth volume transitions
  - Functions:
    - `getIndividualFuelVolumesWithAngles()` - Main entry point
    - `getInterpolatedFuelHeight()` - Interpolates fuel height data
  - Input: fuel height arrays, pitch, roll, combined fuel height
  - Output: Individual volumes for each tank compartment

- **fuel_puddle_model.m** - Physics model for fuel pooling behavior
  - Incomplete/in-development
  - Intended for modeling fuel accumulation on aircraft bay floors

- **fuel_mp_array.m** - Melting point property array
  - Lookup table for fuel melting point across temperatures/conditions

- **fuel_hv_array.m** - Heat of vaporization property array
  - Lookup table for enthalpy of vaporization

- **filter_table.m** - General-purpose table filtering function
  - Utility for filtering/selecting rows from data tables

## Usage

```matlab
% Example: Calculate volumes with pitch and roll
pitch = 5;      % degrees
roll = -3;      % degrees
fuel_height = 0.2;  % meters

volumes = getIndividualFuelVolumesWithAngles(...
    fuelHeightArray, unique_pitch, unique_roll, ...
    pitch, roll, fuel_height);
```

## Compatibility

- MATLAB R2016b+
- GNU Octave (with minor modifications)

## Use Case

Precise fuel tank volume calculations accounting for aircraft attitude (pitch/roll angles) during flight; critical for fuel quantity indication systems and hazard assessment.
