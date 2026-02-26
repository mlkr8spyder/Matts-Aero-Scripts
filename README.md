# Matt's Aerospace Scripts

A comprehensive collection of tools for aerospace fuel tank analysis, including thermal modeling, combustion simulation, fuel property calculations, and data processing utilities.

## Project Overview

This repository contains Python scripts, MATLAB models, and Jupyter notebooks for analyzing:
- Fuel tank thermal behavior and temperature distribution
- Fuel vapor flammability assessment
- Minimum ignition energy (MIE) calculations
- Confined combustion overpressure modeling using Cantera
- Fuel physical properties and state equations
- Aviation fuel tank system analysis

## Folder Structure

### 📊 `01_data_parsing/`
**Utility scripts for extracting and parsing structured data from text files**

- **`logic_parse.py`** - Extracts phrases from text files using regex pattern matching (finds content within brackets)
- **`material_parse.py`** - Parses material property data organized by location and part number
- **`thickness_parse.py`** - Parses thickness measurements associated with part numbers and locations

*Use case*: Preprocessing raw data files into structured formats for analysis.

---

### ⛽ `02_fuel_properties/`
**Fuel characterization and property calculation tools**

- **`fuel_ignition.py`**
  - Cantera-based simulation of fuel ignition under various conditions
  - Parametric study: spark energy (1-100 J), temperature (250-350 K), altitude (0-10,000 m)
  - Computes overpressure and ignition thresholds for n-decane/air mixtures
  - Validates ignition criteria (pressure rise >400 K)

- **`fluid_prop_calc.py`**
  - Tkinter GUI calculator for aviation fuel properties
  - **Tab 1 - Fuel Properties**: Displays density and specific heat capacity for Jet A, Jet A-1, JP-8, AVGAS
  - **Tab 2 - Unit Conversions**:
    - Volumetric flow rate (m³/s ↔ L/min)
    - Density (kg/m³ ↔ g/cm³)
    - K-factor calculation (viscosity-dependent)
    - Head pressure calculation
    - Heat flux calculations

*Use case*: Quick reference and calculations for fuel properties in design or analysis workflows.

---

### 🌡️ `03_thermal_analysis/`
**Thermal modeling and visualization**

- **`python_thermal_plot.py`**
  - Loads temperature/time data from Excel files
  - Plots relationship between fluid temperature and elapsed mission time
  - Extracts last 5 columns (including Lower/Upper Flammability Limits - LFL/UFL)
  - Generates high-resolution PNG and PDF exports with annotations
  - Saves multiple plot formats (raw and publication-quality)

- **`updated_py_thermal_plot.py`** - Enhanced version with improved formatting

- **`matlab_thermal.txt`** - Reference data or notes for MATLAB thermal calculations

*Use case*: Visualizing fuel temperature profiles during flight missions and relating them to flammability margins.

---

### 🧮 `04_matlab_models/`
**MATLAB-based calculations for fuel tank geometry and properties**

- **`fuel_vol_tank_combo.m`**
  - Calculates individual fuel volumes in tank arrays at specified pitch/roll angles
  - Bilinear interpolation of volume-height relationships
  - Handles multiple fuel tank compartments with 3D orientation dependence
  - Functions:
    - `getIndividualFuelVolumesWithAngles()` - Main volume calculation
    - `getInterpolatedFuelHeight()` - Interpolation logic
    - `findInterpolationIndices()` - (referenced, may be in separate file)

- **`fuel_mp_array.m`** - Melting point property array for fuel characterization

- **`fuel_hv_array.m`** - Heat of vaporization property array for fuel

- **`filter_table.m`** - General-purpose table/data filtering function

- **`fuel_puddle_model.m`** - Physics model for fuel pooling behavior (incomplete in current revision)

*Use case*: High-fidelity volume and property calculations that account for aircraft orientation and tank geometry.

---

### 🔧 `05_data_tools/`
**Data processing, filtering, and visualization utilities**

- **`t1_data.py`**
  - Loads resampled CSV time-series data
  - Normalizes time column (relative to first measurement)
  - Applies threshold filtering to parameter columns
  - Exports filtered data to CSV
  - Generates time-series plots with matplotlib

- **`matt_icca_results_tool.py`** (Primary data analysis tool)
  - Tkinter GUI for loading and combining multiple datasets
  - **Data Tab**: Load/add multiple .txt files with automatic column detection
  - **Plot Tab**:
    - Select X and Y columns with custom units
    - Add multiple series to combined plot with dual Y-axes
    - Time range filtering (start/end time)
    - Customizable plot titles and axis labels
    - Save dataframe to Excel and plots as PNG
  - Interpolates non-numeric values automatically
  - Combines multiple datasets while removing duplicates

- **`icca_results_tool.py`** - Similar tool (alternate implementation)

- **`time_scale_functions.py`** - Time-scaling utilities and helper functions for temporal analysis

*Use case*: Processing and visualizing experimental or simulation results with flexible data combination and filtering.

---

### 📓 `06_analysis_notebooks/`
**Jupyter notebooks for exploratory analysis and visualization**

- **`polynomial_plot.ipynb`** - Polynomial fitting and visualization
- **`coordinate_mean.ipynb`** - Coordinate averaging and mean calculation

*Use case*: Interactive exploration of datasets and validation of analysis methods.

---

### 📁 `07_sample_data/`
**Example and test data files**

- **`example.txt`** - Sample thickness/part number data (format: location, part number, thickness)
- **`material.txt`** - Material property reference data (location, part number, material)
- **`icca_results_test.txt`**, **`icca_results_test_2.txt`** - Test datasets for validation
- **`copy_thing.txt`** - Miscellaneous reference data
- **`plot_run_with_events`** - Data from run with events log
- **`matlab_thermal.txt`** - Thermal reference data

*Use case*: Input files for testing parsing and analysis tools; examples of expected data formats.

---

## 📦 Related Projects

### `Fuel_Combustion/` Directory
A comprehensive aircraft bay fuel leak hazard assessment model:

- **`bay_fuel_leak_model.py`** - Advanced combustion modeling for confined fuel vapor explosions
- **`README.md`** - Detailed documentation on:
  - Pool formation dynamics
  - Vapor flammability assessment (altitude-dependent)
  - Minimum ignition energy (MIE) calculations
  - Adiabatic Isochoric Complete Combustion (AICC) overpressure prediction
  - Cantera thermochemistry integration
  - Comparison with Caltech experimental data
  - FAA regulatory context (SFAR 88, AC 25.981-1D)

- **`requirements.txt`** - Python dependencies (Cantera, pandas, matplotlib, numpy)

*Purpose*: Safety-critical hazard assessment for aircraft fuel tank systems per FAA certification guidelines.

---

## Quick Start Guide

### Running Data Analysis Tools
```bash
cd 05_data_tools/
python matt_icca_results_tool.py          # GUI data plotter
python t1_data.py                         # Time-series filtering
```

### Running Fuel Property Calculator
```bash
cd 02_fuel_properties/
python fluid_prop_calc.py                 # Interactive GUI
```

### Running Thermal Analysis
```bash
cd 03_thermal_analysis/
python python_thermal_plot.py             # Load Excel → export plots
```

### Running Combustion Analysis
```bash
cd Fuel_Combustion/
pip install -r requirements.txt
python bay_fuel_leak_model.py             # Generate overpressure analysis
```

### Data Parsing
```bash
cd 01_data_parsing/
python material_parse.py                  # Extract material data
python thickness_parse.py                 # Extract thickness data
```

---

## Dependencies

**Core Requirements:**
- Python 3.8+
- numpy, pandas, matplotlib
- tkinter (usually included with Python)

**Optional (for combustion analysis):**
- Cantera 3.0+ - Thermochemistry and kinetics
- scipy - Scientific computing

**Installation:**
```bash
pip install pandas matplotlib numpy
pip install cantera                       # Optional, for Fuel_Combustion/
```

---

## File Organization Rationale

| Folder | Rationale |
|--------|-----------|
| **01_data_parsing** | Standalone preprocessing tools for raw data extraction |
| **02_fuel_properties** | Focused tools for fuel characterization and property lookup |
| **03_thermal_analysis** | Thermal visualization and temperature-time analysis |
| **04_matlab_models** | Numerical methods requiring MATLAB or MATLAB-compatible Octave |
| **05_data_tools** | High-level data combination, filtering, and visualization GUIs |
| **06_analysis_notebooks** | Interactive exploratory analysis |
| **07_sample_data** | Reference data and test files |
| **Fuel_Combustion** | Specialized hazard assessment (kept separate due to complexity) |

---

## Key Features by Use Case

### "I need to plot my thermal data"
→ Use `03_thermal_analysis/python_thermal_plot.py`

### "I need to combine multiple CSV/TXT files and make a plot"
→ Use `05_data_tools/matt_icca_results_tool.py` (GUI) or `t1_data.py` (script)

### "I need fuel property values (density, viscosity, etc.)"
→ Use `02_fuel_properties/fluid_prop_calc.py`

### "I need to assess ignition hazard in a fuel tank"
→ Use `Fuel_Combustion/bay_fuel_leak_model.py`

### "I need to extract structured data from a text file"
→ Use `01_data_parsing/` tools (material_parse, thickness_parse, logic_parse)

### "I need volume calculations for my fuel tank"
→ Use `04_matlab_models/fuel_vol_tank_combo.m`

---

## Output Formats

- **Plots**: PNG, PDF (matplotlib)
- **Data**: CSV, XLSX (pandas)
- **Notebooks**: Interactive .ipynb format (Jupyter)
- **Models**: MATLAB .m files (compatible with Octave)

---

## Regulatory References

This work aligns with:
- **FAA Advisory Circular 25.981-1D** - Fuel Tank Ignition Source Prevention
- **FAA Special Federal Aviation Regulation (SFAR) 88** - Fuel Tank System Fault Tolerance
- **Caltech Explosion Dynamics Laboratory** - Jet-A vapor explosion testing (TWA Flight 800 investigation)
- **Sandia National Laboratories** - Confined combustion modeling

---

## License & Usage

All tools provided for engineering analysis and design validation. Users are responsible for validating results against applicable regulatory requirements and experimental data before use in certification or safety-critical decisions.

---

## Repository Structure Summary

```
Matts-Aero-Scripts/
├── README.md (this file)
├── 01_data_parsing/
│   ├── logic_parse.py
│   ├── material_parse.py
│   └── thickness_parse.py
├── 02_fuel_properties/
│   ├── fuel_ignition.py
│   └── fluid_prop_calc.py
├── 03_thermal_analysis/
│   ├── python_thermal_plot.py
│   ├── updated_py_thermal_plot.py
│   └── matlab_thermal.txt
├── 04_matlab_models/
│   ├── fuel_vol_tank_combo.m
│   ├── fuel_puddle_model.m
│   ├── fuel_mp_array.m
│   ├── fuel_hv_array.m
│   └── filter_table.m
├── 05_data_tools/
│   ├── t1_data.py
│   ├── matt_icca_results_tool.py
│   ├── icca_results_tool.py
│   └── time_scale_functions.py
├── 06_analysis_notebooks/
│   ├── polynomial_plot.ipynb
│   └── coordinate_mean.ipynb
├── 07_sample_data/
│   ├── example.txt
│   ├── material.txt
│   ├── icca_results_test.txt
│   ├── icca_results_test_2.txt
│   ├── copy_thing.txt
│   ├── matlab_thermal.txt
│   └── plot_run_with_events
└── Fuel_Combustion/
    ├── README.md (detailed technical documentation)
    ├── bay_fuel_leak_model.py
    └── requirements.txt
```

---

**Last Updated**: February 2026

