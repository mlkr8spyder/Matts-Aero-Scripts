# Data Analysis & Visualization Tools

High-level tools for combining, filtering, and visualizing experimental or simulation data.

## Files

- **matt_icca_results_tool.py** - **Primary data analysis GUI** ⭐
  - Multi-tab Tkinter interface for data combination and plotting
  - **Data Tab**:
    - Load `.txt` files with whitespace delimiters
    - Add multiple datasets automatically (removes duplicate columns)
    - Auto-interpolation of non-numeric values
    - Save combined dataframe to Excel
  - **Plot Tab**:
    - Select X and Y columns from loaded data
    - Add multiple series to single plot
    - Customizable axis labels and units
    - Time range filtering (start/end time)
    - Dual Y-axis support (secondary axis for different units)
    - Save plots as PNG with 300 dpi
    - Rename plot title and axis labels on-the-fly

- **icca_results_tool.py** - Alternative data plotting tool (similar functionality)

- **t1_data.py** - Time-series data filtering script
  - Loads CSV with time and parameter columns
  - Normalizes time (relative to first measurement)
  - Applies threshold filtering
  - Exports filtered data to CSV
  - Generates matplotlib plots

- **time_scale_functions.py** - Time-scaling utilities
  - Helper functions for temporal analysis
  - Extensions/enhancements for time-based calculations

## Running the GUI Tool

```bash
python matt_icca_results_tool.py
```

## Input Data Format

Plain text files with whitespace-delimited columns:
```
Time   Temp1   Temp2   Temp3   Pressure
0.0    20.5    21.2    19.8    101.3
1.0    21.3    22.1    20.5    101.5
2.0    22.1    22.9    21.2    101.7
```

## Workflow Example

1. Load first dataset (e.g., `test_run_1.txt`)
2. Add second dataset (e.g., `test_run_2.txt`) - auto-removes duplicate columns
3. Select X column (`Time`) and first Y column (`Temp1`)
4. Add to plot with units
5. Select `Temp2` with different units, add to plot (creates dual Y-axis)
6. Set time range (start: 10s, end: 100s)
7. Generate plot
8. Save as PNG or export dataframe to Excel

## Features

- Automatic handling of missing/non-numeric data
- Dual Y-axis plots with different units
- Real-time column selection from loaded data
- Flexible renaming of plot elements
- High-resolution PNG export

## Use Case

Interactive exploration and comparison of experimental test runs or simulation outputs; combining data from multiple sources into publication-quality plots.
