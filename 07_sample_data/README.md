# Sample Data & Reference Files

Example and test data files for validating parsing and analysis tools.

## Files

- **example.txt** - Sample thickness/part data
  - Format: location, part number, thickness measurements
  - Use with `thickness_parse.py` to test parsing

- **material.txt** - Material property reference data
  - Format: location, part number, material designation
  - Use with `material_parse.py` to test parsing

- **icca_results_test.txt**, **icca_results_test_2.txt** - Test datasets
  - Sample ICCA (aviation) results for validation
  - Use with `matt_icca_results_tool.py` for GUI testing

- **copy_thing.txt** - Miscellaneous reference data

- **plot_run_with_events** - Data file from a run with event logs
  - Contains time-series data with event markers

- **matlab_thermal.txt** - Thermal reference data or MATLAB-related notes

## Expected Data Formats

### Thickness Data (example.txt)
```
LOCATION_NAME
PN_12345
0.045
PN_12346
0.032
```

### Material Data (material.txt)
```
FUSELAGE
PN_98765
Aluminum_2024
PN_98766
Titanium_Ti6Al4V
```

### ICCA Results (icca_results_test.txt)
```
Time    Temperature    Pressure    FlowRate
0       20.5          101.3       0.0
1       21.2          101.5       1.2
2       22.1          101.7       2.4
```

## Usage

Use these files to:
1. Test parsing tools before processing real data
2. Validate plotting functionality
3. Train new users on expected data formats
4. Create regression tests for code changes

## Note

These are example/test files. Replace with actual project data for real analysis.
