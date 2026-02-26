# Thermal Analysis Tools

Tools for analyzing and visualizing fuel thermal behavior during flight missions.

## Files

- **python_thermal_plot.py** - Excel-to-plot conversion utility
  - Loads multi-sheet Excel files
  - Extracts Time (column 1) and last 5 columns (temperature + flammability limits)
  - Creates publication-quality plots with dual axes
  - Exports: PNG (low-res), PNG (300 dpi), PDF
  - Annotates LFL (Lower Flammability Limit) and UFL (Upper Flammability Limit)

- **updated_py_thermal_plot.py** - Enhanced version with improved formatting

- **matlab_thermal.txt** - Reference data or notes for MATLAB thermal calculations

## Usage

```bash
python python_thermal_plot.py
```

Modify these variables in main():
```python
filename = 'example_data.xlsx'        # Excel input file
fig_folder = 'figures'                # Output folder for plots
png_folder = 'exported_pngs'          # High-res PNG folder
```

## Expected Input Format

Excel file with:
- Column 1: `Time` (in seconds)
- Columns 2-12: Temperature data for various compartments
- Column 13: LFL (Lower Flammability Limit)
- Column 14: UFL (Upper Flammability Limit)

## Output

- `plot_[sheetname].png` (regular)
- `plot_[sheetname].png` (300 dpi)
- `plot_[sheetname].pdf`

## Use Case

Visualizing fuel temperature evolution over mission time and relating it to flammability margins for safety assessment.
