# Fuel Properties Tools

Tools for fuel characterization, property calculation, and ignition assessment.

## Files

- **fuel_ignition.py** - Cantera-based spark ignition energy simulation
  - Tests multiple temperatures, altitudes, and spark energies
  - Computes overpressure and ignition thresholds
  - Uses n-decane/air mixture at constant volume
  - Outputs: spark energy vs overpressure curves

- **fluid_prop_calc.py** - Interactive GUI calculator for aviation fuel properties
  - Jet A, Jet A-1, JP-8, AVGAS fuel types
  - Property lookups: density, specific heat capacity
  - Unit conversions: flow rate, density
  - K-factor calculation
  - Head pressure calculations
  - Heat flux calculations

## Running the GUI

```bash
python fluid_prop_calc.py
```

## Dependencies

- Python 3.8+
- tkinter (usually included)
- cantera (for fuel_ignition.py)
- numpy, pandas, matplotlib (for fuel_ignition.py)

## Use Case

Quick reference for fuel properties during design and analysis workflows; ignition assessment under various flight conditions.
