# Claude Code Prompt — Fuel Gauging Error Analysis Toolset

## Instructions

Read the file `fuel_gauging_error_context.md` in this project directory before doing anything. That file describes the full system architecture, data pipeline, probe types, and analysis objectives. Everything below assumes you have internalized that context.

You are building a Python-based analysis toolset for decomposing fuel quantity indication error in an aircraft fuel gauging system. The user has recorded flight and ground data and wants to identify which tanks, probe regions, attitude conditions, and system parameters contribute most to the total gauging error.

**Work in phases. Complete each phase fully, test it, and confirm with the user before moving on.**

---

## Phase 1: Data Ingestion and Structuring

### Task 1.1: Data Loader

Build a data loader module (`src/data_loader.py`) that:
- Loads `.mat` files using `scipy.io.loadmat` (handle both v5 and v7.3/HDF5 formats — use `h5py` as fallback)
- Accepts a configuration YAML file that maps the user's variable names to standardized internal names (since the real variable names are CUI-sensitive, the user will provide this mapping)
- Outputs a single pandas DataFrame per dataset where each row is one timestamp and columns are:
  - `timestamp` (seconds or datetime)
  - `pitch_deg`, `roll_deg`
  - `probe_height_T{n}` for each tank's raw probe height(s)
  - `indicated_volume_T{n}` for each tank's indicated volume
  - `indicated_weight_T{n}` for each tank's indicated weight (if available)
  - `density_system` — system-computed fuel density
  - `total_indicated_fuel_weight` — sum of all tank weights
  - `scale_gross_weight` — scale-measured gross weight (NaN where not available)
  - `dry_weight` — aircraft dry weight (can be a constant provided in config)

### Task 1.2: Error Computation

Add an error computation module (`src/error_compute.py`) that:
- Computes `total_fuel_error = total_indicated_fuel_weight - (scale_gross_weight - dry_weight)` at every row where scale weight is available
- For defuel/refuel sequences where scale weight is only at endpoints, interpolates or propagates the error using cumulative fuel removed/added if a flow measurement column is available
- Computes `density_error = density_system - density_lab` when lab density is provided in config
- Computes `density_attributable_weight_error` = total indicated volume × (density_system - density_lab) to isolate how much of the total error comes from density alone
- Computes `volume_attributable_error = total_fuel_error - density_attributable_weight_error`
- Adds all computed columns to the DataFrame

### Task 1.3: Dataset Registry

Build a dataset registry (`src/dataset_registry.py`) that:
- Tracks multiple loaded datasets (defuel, refuel, mission snapshots) by name
- Stores metadata per dataset: type (defuel/refuel/mission), lab density (if available), dry weight, date, notes
- Provides methods to retrieve, combine, or filter datasets for analysis

**Deliverables for Phase 1:** Working data loader tested on a synthetic `.mat` file you generate, error columns computed correctly, registry storing multiple datasets. Create a `tests/test_phase1.py` with unit tests.

---

## Phase 2: Statistical Analysis and Visualization

### Task 2.1: Correlation Analysis (`src/analysis/correlation.py`)

- Compute Pearson and Spearman correlation between `total_fuel_error` and every numeric column in the DataFrame
- Compute correlations for `volume_attributable_error` separately (after removing density contribution)
- Generate a correlation heatmap (seaborn) showing all feature correlations with error
- Compute rolling correlations (windowed) to see if relationships change over the defuel/refuel sequence
- Flag features with |correlation| > 0.5 as candidates for deeper investigation

### Task 2.2: Time Series Error Visualization (`src/analysis/timeseries.py`)

- Plot total error vs. time with each tank's indicated volume overlaid (dual y-axis)
- Plot each tank's probe height vs. time, color-coded by instantaneous total error magnitude
- Plot error rate of change (dError/dt) vs. time — spikes here indicate moments where error is actively growing
- For defuel/refuel: plot error vs. total fuel remaining (instead of time) so fill/drain sequences can be directly compared
- Mark transition points where tanks start/stop contributing (user will specify fill/drain order in config)

### Task 2.3: Attitude Dependency (`src/analysis/attitude.py`)

- 2D scatter: pitch vs. error, roll vs. error
- Heatmap: pitch × roll grid, colored by mean error in each bin
- Compare error distributions at different attitude conditions using violin plots
- Test for statistically significant attitude effects using ANOVA or Kruskal-Wallis

### Task 2.4: Probe Region Analysis (`src/analysis/probe_regions.py`)

- For each tank, bin error by probe height percentile (0-10%, 10-20%, ..., 90-100%)
- Identify height ranges where error is systematically higher
- For real-pseudo tanks: specifically isolate the overlap/blend region and compare error inside vs. outside the blend zone
- For pseudo-projected tanks: compute the sensitivity of error to attitude and compare it to real-probe tanks

**Deliverables for Phase 2:** All plots saved to `outputs/figures/`. A summary statistics report saved to `outputs/reports/phase2_summary.md`. All analysis functions callable independently on any dataset from the registry.

---

## Phase 3: Machine Learning Error Decomposition

### Task 3.1: Feature Engineering (`src/ml/features.py`)

Build a feature engineering pipeline that, from the base DataFrame, computes:
- Rate of change of each probe height (dh/dt)
- Rate of change of each tank's indicated volume (dV/dt)
- Which tanks are "active" (|dV/dt| > threshold) — binary flags
- Probe height as a percentage of total probe range (normalized)
- For real-pseudo tanks: a flag indicating the probe is in the blend/overlap zone
- For pseudo tanks: the magnitude of the trigonometric projection correction (attitude-dependent term)
- Interaction features: pitch × probe_height, roll × probe_height for each tank
- Lagged features: error at t-1, t-2 (to capture hysteresis or lag effects)
- Delta features: indicated_volume(t) - indicated_volume(t-1) per tank

### Task 3.2: Random Forest / Gradient Boosting (`src/ml/tree_models.py`)

- Train a Random Forest regressor to predict `total_fuel_error` from all engineered features
- Train a Gradient Boosting regressor (XGBoost or LightGBM) on the same task
- Use TimeSeriesSplit cross-validation (do NOT randomly shuffle time series data)
- Extract and plot feature importances from both models
- Compute permutation importances as a robustness check
- Generate a ranked list of the top 15 features driving error prediction
- Repeat all of the above for `volume_attributable_error` (density-removed)

### Task 3.3: SHAP Analysis (`src/ml/shap_analysis.py`)

- Compute SHAP values for the best-performing tree model
- Generate SHAP summary plot (beeswarm) showing feature impact direction and magnitude
- Generate SHAP dependence plots for the top 5 features
- Generate SHAP interaction plots for the top feature pairs
- Save SHAP values to a DataFrame for downstream use

### Task 3.4: Neural Network Approach (`src/ml/neural_net.py`)

- Build a small feedforward neural network (PyTorch or TensorFlow) to predict error
- Architecture: input → 64 → 32 → 16 → 1, with ReLU activations and batch normalization
- Train with early stopping on a validation split (time-ordered, not random)
- After training, use integrated gradients or gradient × input attribution to identify which features the network relies on
- Compare the neural network's feature attributions to the tree model's SHAP results — agreement between methods strengthens confidence in the finding

### Task 3.5: Change-Point Detection (`src/ml/changepoints.py`)

- Apply change-point detection (ruptures library or PELT algorithm) to the error time series
- At each detected change point, report which tank probe heights were near transition points (near 0%, near 100%, in blend zones)
- Correlate change points with tank activation/deactivation events

**Deliverables for Phase 3:** All models saved to `outputs/models/`. Feature importance rankings, SHAP plots, and neural network attributions saved to `outputs/figures/`. A Phase 3 report comparing findings across methods saved to `outputs/reports/phase3_summary.md`.

---

## Phase 4: Per-Tank Error Contribution Estimation

This is the hardest part because individual tank weights are not measured. Use indirect methods:

### Task 4.1: Marginal Contribution Analysis (`src/analysis/tank_contribution.py`)

- During defuel/refuel, identify time windows where only one tank's level is changing (single-tank-active windows). In these windows, the change in total error is attributable to that tank alone.
- Compute per-tank error contribution rates (dError/dVolume_tank) during single-tank-active windows
- If no pure single-tank windows exist, use the SHAP values from Phase 3 to estimate each tank's marginal contribution to total error

### Task 4.2: Synthetic Perturbation Analysis (`src/analysis/perturbation.py`)

- Using the trained ML models, perturb one tank's probe height by ±1% while holding all others constant
- Record the change in predicted error — this gives a sensitivity measure per tank
- Sweep perturbations across the full probe height range to build a sensitivity profile per tank
- Generate a sensitivity heatmap: tank × probe_height_region → error_sensitivity

### Task 4.3: Residual Structure Analysis (`src/analysis/residuals.py`)

- After the ML model predicts error, examine the residuals (actual - predicted)
- If residuals show structure (not white noise), there are error sources the model hasn't captured
- Plot residuals vs. each feature to find remaining unexplained patterns
- Apply FFT to residuals to check for periodic error components (could indicate table quantization effects)

**Deliverables for Phase 4:** Per-tank error contribution estimates with confidence bounds. Sensitivity profiles per tank. Residual analysis report. All saved to `outputs/reports/phase4_summary.md`.

---

## Phase 5: Dashboard and Reporting

### Task 5.1: Interactive Dashboard (`src/dashboard/app.py`)

Build a Streamlit or Panel dashboard with tabs:
- **Overview:** Total error vs. time/fuel level, dataset selector
- **Correlation:** Interactive heatmap, click a feature to see its scatter vs. error
- **Tank Drill-Down:** Select a tank, see its probe height, indicated volume, error contribution, and SHAP values over time
- **ML Results:** Feature importance rankings, SHAP beeswarm, model performance metrics
- **Attitude:** Pitch/roll error heatmaps

### Task 5.2: Final Report Generator (`src/reporting/generate_report.py`)

Generate a markdown report that summarizes:
- Total error statistics per dataset
- Top error-contributing features (consensus across methods)
- Per-tank error contribution estimates
- Recommended investigation priorities (which tanks/probe regions/conditions to examine first)
- Density error vs. volume error breakdown

---

## Project Structure

```
fuel_error_analysis/
├── config/
│   ├── dataset_config_template.yaml    # Template for users to map variable names
│   └── example_config.yaml             # Example with synthetic data
├── src/
│   ├── data_loader.py
│   ├── error_compute.py
│   ├── dataset_registry.py
│   ├── analysis/
│   │   ├── correlation.py
│   │   ├── timeseries.py
│   │   ├── attitude.py
│   │   ├── probe_regions.py
│   │   ├── tank_contribution.py
│   │   ├── perturbation.py
│   │   └── residuals.py
│   ├── ml/
│   │   ├── features.py
│   │   ├── tree_models.py
│   │   ├── shap_analysis.py
│   │   ├── neural_net.py
│   │   └── changepoints.py
│   ├── dashboard/
│   │   └── app.py
│   └── reporting/
│       └── generate_report.py
├── tests/
│   ├── test_phase1.py
│   ├── test_phase2.py
│   └── test_phase3.py
├── outputs/
│   ├── figures/
│   ├── models/
│   └── reports/
├── data/                               # User places .mat files here
├── requirements.txt
└── README.md
```

## Dependencies

```
numpy
pandas
scipy
h5py
matplotlib
seaborn
scikit-learn
xgboost
shap
torch
ruptures
streamlit
pyyaml
```

## Critical Reminders

- Do NOT assume specific tank names, probe locations, waterlines, or geometry values. Everything comes from the user's data and config file.
- Time series data must NEVER be randomly shuffled for train/test splits. Always use time-ordered splits.
- The user's data is CUI. Do not hardcode any real values. The config YAML is the abstraction layer.
- Generate synthetic test data that mimics the structure (multiple tanks, probe heights, attitudes, error patterns) so every module can be tested before real data is loaded.
- All analysis functions should work on any dataset from the registry without modification.
- Visualizations should be publication-quality with clear labels, units, and legends.
