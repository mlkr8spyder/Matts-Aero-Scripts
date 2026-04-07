"""
Static HTML dashboard generator for fuel gauging analysis.

Generates a single self-contained HTML file with 4 interactive views
powered by Plotly.js (loaded from CDN — no server required). All data
is embedded as JSON in <script> tags.

Views:
  1. H-V Curve Explorer — tank dropdown + pitch/roll sliders
  2. Error Analysis — residual timeseries, error vs fuel level, attitude heatmap
  3. Probe Coverage — tank layout with probe positions
  4. Weight Comparison — indicated vs scale overlay with residual subplot

Usage:
    from analysis.dashboard import generate_dashboard
    from analysis.importers.synthetic_bridge import load_synthetic_system
    from analysis.comparison import compute_residuals

    data = load_synthetic_system()
    residuals = compute_residuals(data.test_data[0])
    generate_dashboard(data, residuals, "dashboard.html")
"""

import json
import numpy as np
from pathlib import Path
from typing import Optional

from .importers.base import FuelSystemData


def _np_to_list(obj):
    """JSON serializer for numpy types."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.float64, np.float32, np.floating)):
        return float(obj)
    if isinstance(obj, (np.int64, np.int32, np.integer)):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    raise TypeError(f"Cannot serialize {type(obj)}")


def _prepare_hv_data(system_data: FuelSystemData,
                     max_attitudes: int = 50) -> dict:
    """
    Prepare H-V table data for the dashboard, subsampling attitudes
    to keep file size reasonable.
    """
    hv_data = {}
    for tid, tank in system_data.tanks.items():
        attitudes = tank.attitudes
        # Subsample if too many attitudes
        if len(attitudes) > max_attitudes:
            step = max(1, len(attitudes) // max_attitudes)
            attitudes = attitudes[::step]

        tables = []
        for (p, r) in attitudes:
            t = tank.tables[(p, r)]
            tables.append({
                'pitch': p,
                'roll': r,
                'heights': t.heights.tolist(),
                'volumes': t.volumes.tolist(),
            })

        hv_data[tid] = {
            'name': tank.name or tid,
            'probe_type': tank.probe_type or 'unknown',
            'max_volume': tank.max_volume,
            'tables': tables,
            'pitches': sorted(set(p for p, r in attitudes)),
            'rolls': sorted(set(r for p, r in attitudes)),
        }

    return hv_data


def _prepare_residuals_data(residuals: dict) -> dict:
    """Prepare residual data for the dashboard."""
    if residuals is None:
        return None

    # Subsample for large datasets (keep every Nth point for plotting)
    n = len(residuals['time_s'])
    step = max(1, n // 2000)

    data = {
        'time_s': residuals['time_s'][::step].tolist(),
        'indicated_lb': residuals['indicated_total_lb'][::step].tolist(),
        'actual_lb': residuals['actual_total_lb'][::step].tolist(),
        'residual_lb': residuals['residual_total_lb'][::step].tolist(),
        'pitch_deg': residuals['pitch_deg'][::step].tolist(),
        'roll_deg': residuals['roll_deg'][::step].tolist(),
    }

    if 'density_system' in residuals:
        data['density'] = residuals['density_system'][::step].tolist()

    # Per-tank data
    if 'indicated_per_tank' in residuals:
        data['per_tank'] = {}
        for tid, arr in residuals['indicated_per_tank'].items():
            data['per_tank'][tid] = arr[::step].tolist()

    return data


def _prepare_tank_layout(system_data: FuelSystemData) -> list:
    """Prepare tank geometry/probe info for the coverage view."""
    layout = []
    for tid, tank in system_data.tanks.items():
        geo = tank.metadata.get('geometry', {})
        probes = tank.metadata.get('probes', [])

        layout.append({
            'id': tid,
            'name': tank.name or tid,
            'probe_type': tank.probe_type or 'unknown',
            'geometry': geo,
            'probes': probes,
        })

    return layout


def generate_dashboard(system_data: FuelSystemData,
                       residuals: Optional[dict] = None,
                       output_path: str = "dashboard.html",
                       title: str = "Fuel Gauging Analysis Dashboard",
                       max_attitudes: int = 50) -> str:
    """
    Generate a single-file HTML dashboard with embedded data and Plotly.js.

    Parameters
    ----------
    system_data : FuelSystemData
        H-V tables and tank info.
    residuals : dict, optional
        Output from comparison.compute_residuals(). If None, views 2 and 4
        show placeholder messages.
    output_path : str
        Where to write the HTML file.
    title : str
        Page title.
    max_attitudes : int
        Maximum number of attitude conditions to include per tank in the
        H-V explorer. Subsamples uniformly if exceeded.

    Returns
    -------
    str : absolute path to the generated file.
    """
    hv_data = _prepare_hv_data(system_data, max_attitudes=max_attitudes)
    res_data = _prepare_residuals_data(residuals)
    tank_layout = _prepare_tank_layout(system_data)

    hv_json = json.dumps(hv_data, default=_np_to_list)
    res_json = json.dumps(res_data, default=_np_to_list)
    layout_json = json.dumps(tank_layout, default=_np_to_list)

    html = _TEMPLATE.replace('__HV_DATA__', hv_json)
    html = html.replace('__RESIDUALS_DATA__', res_json)
    html = html.replace('__TANK_LAYOUT__', layout_json)
    html = html.replace('__TITLE__', title)

    out = Path(output_path).resolve()
    out.write_text(html, encoding='utf-8')
    return str(out)


# ---------------------------------------------------------------------------
# HTML template with embedded JavaScript
# ---------------------------------------------------------------------------

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f5f5f5; color: #333; }
  .header { background: #1a237e; color: white; padding: 16px 24px;
            display: flex; align-items: center; gap: 16px; }
  .header h1 { font-size: 20px; font-weight: 500; }
  .tabs { display: flex; gap: 4px; background: #e8eaf6; padding: 8px 24px 0; }
  .tab { padding: 10px 20px; cursor: pointer; border-radius: 6px 6px 0 0;
         background: transparent; border: none; font-size: 14px; color: #555;
         transition: background 0.2s; }
  .tab:hover { background: #c5cae9; }
  .tab.active { background: white; color: #1a237e; font-weight: 600; }
  .view { display: none; padding: 24px; }
  .view.active { display: block; }
  .card { background: white; border-radius: 8px; padding: 20px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; }
  .card h3 { margin-bottom: 12px; color: #1a237e; font-size: 16px; }
  .controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
              margin-bottom: 16px; }
  .controls label { font-size: 13px; color: #666; }
  .controls select, .controls input[type=range] { font-size: 13px; }
  .plot-container { width: 100%; min-height: 400px; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  .stat-box { display: inline-block; background: #e8eaf6; border-radius: 6px;
              padding: 8px 16px; margin: 4px; }
  .stat-box .label { font-size: 11px; color: #666; }
  .stat-box .value { font-size: 18px; font-weight: 600; color: #1a237e; }
  .tank-svg { border: 1px solid #ddd; border-radius: 4px; }
  .no-data { text-align: center; padding: 60px; color: #999; font-size: 16px; }
  @media (max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }
</style>
</head>
<body>

<div class="header">
  <h1>__TITLE__</h1>
</div>

<div class="tabs">
  <button class="tab active" onclick="showView(0)">H-V Explorer</button>
  <button class="tab" onclick="showView(1)">Error Analysis</button>
  <button class="tab" onclick="showView(2)">Probe Coverage</button>
  <button class="tab" onclick="showView(3)">Weight Comparison</button>
</div>

<!-- View 1: H-V Curve Explorer -->
<div class="view active" id="view-0">
  <div class="card">
    <h3>Height-Volume Curve Explorer</h3>
    <div class="controls">
      <label>Tank: <select id="hv-tank" onchange="updateHV()"></select></label>
      <label>Pitch: <span id="hv-pitch-val">0</span>&deg;
        <input type="range" id="hv-pitch" min="0" max="0" value="0" oninput="updateHV()">
      </label>
      <label>Roll: <span id="hv-roll-val">0</span>&deg;
        <input type="range" id="hv-roll" min="0" max="0" value="0" oninput="updateHV()">
      </label>
    </div>
    <div id="hv-plot" class="plot-container"></div>
  </div>
</div>

<!-- View 2: Error Analysis -->
<div class="view" id="view-1">
  <div id="error-content"></div>
</div>

<!-- View 3: Probe Coverage -->
<div class="view" id="view-2">
  <div class="card">
    <h3>Tank Layout &amp; Probe Coverage</h3>
    <div id="coverage-plot" class="plot-container"></div>
  </div>
</div>

<!-- View 4: Weight Comparison -->
<div class="view" id="view-3">
  <div id="weight-content"></div>
</div>

<script>
// Embedded data
const hvData = __HV_DATA__;
const resData = __RESIDUALS_DATA__;
const tankLayout = __TANK_LAYOUT__;

// Tab switching
function showView(idx) {
  document.querySelectorAll('.view').forEach((v, i) => {
    v.classList.toggle('active', i === idx);
  });
  document.querySelectorAll('.tab').forEach((t, i) => {
    t.classList.toggle('active', i === idx);
  });
  // Trigger resize for plotly
  setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
}

// ---- View 1: H-V Explorer ----
function initHV() {
  const sel = document.getElementById('hv-tank');
  Object.keys(hvData).sort().forEach(tid => {
    const opt = document.createElement('option');
    opt.value = tid;
    opt.textContent = tid + (hvData[tid].name ? ' (' + hvData[tid].name + ')' : '');
    sel.appendChild(opt);
  });
  updateHVSliders();
  updateHV();
}

function updateHVSliders() {
  const tid = document.getElementById('hv-tank').value;
  if (!tid || !hvData[tid]) return;
  const d = hvData[tid];

  const ps = document.getElementById('hv-pitch');
  ps.min = 0; ps.max = d.pitches.length - 1;
  ps.value = Math.floor(d.pitches.length / 2);

  const rs = document.getElementById('hv-roll');
  rs.min = 0; rs.max = d.rolls.length - 1;
  rs.value = Math.floor(d.rolls.length / 2);
}

document.getElementById('hv-tank').addEventListener('change', () => {
  updateHVSliders();
  updateHV();
});

function updateHV() {
  const tid = document.getElementById('hv-tank').value;
  if (!tid || !hvData[tid]) return;
  const d = hvData[tid];

  const pi = parseInt(document.getElementById('hv-pitch').value);
  const ri = parseInt(document.getElementById('hv-roll').value);
  const pitch = d.pitches[pi] || 0;
  const roll = d.rolls[ri] || 0;

  document.getElementById('hv-pitch-val').textContent = pitch.toFixed(1);
  document.getElementById('hv-roll-val').textContent = roll.toFixed(1);

  // Find closest table
  let best = null, bestDist = Infinity;
  d.tables.forEach(t => {
    const dist = Math.abs(t.pitch - pitch) + Math.abs(t.roll - roll);
    if (dist < bestDist) { bestDist = dist; best = t; }
  });

  if (!best) return;

  const trace = {
    x: best.heights, y: best.volumes,
    type: 'scatter', mode: 'lines+markers',
    name: `${tid} at ${pitch.toFixed(0)}°/${roll.toFixed(0)}°`,
    line: { width: 2 }, marker: { size: 4 }
  };

  const layout = {
    title: `${tid} (${d.name}) — Pitch ${pitch.toFixed(1)}° / Roll ${roll.toFixed(1)}°`,
    xaxis: { title: 'Height (in)' },
    yaxis: { title: 'Volume (in³)' },
    margin: { t: 40 },
    height: 450,
  };

  Plotly.react('hv-plot', [trace], layout, { responsive: true });
}

// ---- View 2: Error Analysis ----
function initError() {
  const container = document.getElementById('error-content');
  if (!resData) {
    container.innerHTML = '<div class="no-data">No test data loaded. Provide residuals to see error analysis.</div>';
    return;
  }

  container.innerHTML = `
    <div class="grid-2">
      <div class="card"><h3>Residual Timeseries</h3><div id="err-ts" class="plot-container"></div></div>
      <div class="card"><h3>Error vs Fuel Level</h3><div id="err-level" class="plot-container"></div></div>
    </div>
    <div class="card"><h3>Attitude Sensitivity</h3><div id="err-att" class="plot-container"></div></div>
  `;

  // Residual timeseries
  Plotly.newPlot('err-ts', [{
    x: resData.time_s, y: resData.residual_lb,
    type: 'scatter', mode: 'lines', name: 'Residual',
    line: { width: 1, color: '#e53935' }
  }, {
    x: resData.time_s, y: resData.residual_lb.map(() => 0),
    type: 'scatter', mode: 'lines', name: 'Zero',
    line: { width: 1, color: '#999', dash: 'dash' }
  }], {
    xaxis: { title: 'Time (s)' },
    yaxis: { title: 'Error (lb)' },
    margin: { t: 10 }, height: 350, showlegend: false,
  }, { responsive: true });

  // Error vs fuel level
  Plotly.newPlot('err-level', [{
    x: resData.actual_lb, y: resData.residual_lb,
    type: 'scatter', mode: 'markers', name: 'Error vs Level',
    marker: { size: 3, color: '#1565c0', opacity: 0.5 }
  }], {
    xaxis: { title: 'Actual Fuel Weight (lb)' },
    yaxis: { title: 'Error (lb)' },
    margin: { t: 10 }, height: 350,
  }, { responsive: true });

  // Attitude heatmap
  const pitches = resData.pitch_deg;
  const rolls = resData.roll_deg;
  const errors = resData.residual_lb.map(Math.abs);

  Plotly.newPlot('err-att', [{
    x: rolls, y: pitches, z: errors,
    type: 'scatter', mode: 'markers',
    marker: { size: 4, color: errors, colorscale: 'YlOrRd', showscale: true,
              colorbar: { title: '|Error| (lb)' } }
  }], {
    xaxis: { title: 'Roll (deg)' },
    yaxis: { title: 'Pitch (deg)' },
    margin: { t: 10 }, height: 400,
  }, { responsive: true });
}

// ---- View 3: Probe Coverage ----
function initCoverage() {
  if (!tankLayout || tankLayout.length === 0) {
    document.getElementById('coverage-plot').innerHTML =
      '<div class="no-data">No tank layout data available.</div>';
    return;
  }

  const colors = ['#2196F3','#4CAF50','#FF9800','#E91E63','#9C27B0',
                   '#00BCD4','#FF5722','#607D8B','#795548','#3F51B5'];
  const shapes = [];
  const annotations = [];

  // Determine bounds
  let allFs = [], allBl = [];
  tankLayout.forEach(t => {
    const g = t.geometry;
    if (g.fs_min !== undefined) {
      allFs.push(g.fs_min, g.fs_max);
      allBl.push(g.bl_min, g.bl_max);
    }
  });

  if (allFs.length === 0) {
    document.getElementById('coverage-plot').innerHTML =
      '<div class="no-data">No geometry data in tank metadata. Load from .mat or synthetic bridge.</div>';
    return;
  }

  const traces = [];
  tankLayout.forEach((t, i) => {
    const g = t.geometry;
    if (g.fs_min === undefined) return;
    const color = colors[i % colors.length];

    // Tank outline (top-down view: FS vs BL)
    traces.push({
      x: [g.bl_min, g.bl_max, g.bl_max, g.bl_min, g.bl_min],
      y: [g.fs_min, g.fs_min, g.fs_max, g.fs_max, g.fs_min],
      type: 'scatter', mode: 'lines', name: t.id + ' outline',
      line: { color: color, width: 2 },
      fill: 'toself', fillcolor: color + '20',
      showlegend: true,
    });

    // Probe positions
    (t.probes || []).forEach((p, pi) => {
      traces.push({
        x: [p.base_bl], y: [p.base_fs],
        type: 'scatter', mode: 'markers',
        name: p.name || `${t.id} probe ${pi+1}`,
        marker: { size: 10, color: color, symbol: 'diamond' },
        showlegend: false,
      });
    });

    // Tank label
    annotations.push({
      x: (g.bl_min + g.bl_max) / 2,
      y: (g.fs_min + g.fs_max) / 2,
      text: `<b>${t.id}</b><br>${t.name}`,
      showarrow: false,
      font: { size: 11, color: color },
    });
  });

  Plotly.newPlot('coverage-plot', traces, {
    xaxis: { title: 'Butt Line (in)', scaleanchor: 'y' },
    yaxis: { title: 'Fuselage Station (in)' },
    annotations: annotations,
    height: 500, margin: { t: 10 },
    legend: { orientation: 'h', y: -0.15 },
  }, { responsive: true });
}

// ---- View 4: Weight Comparison ----
function initWeight() {
  const container = document.getElementById('weight-content');
  if (!resData) {
    container.innerHTML = '<div class="no-data">No test data loaded. Provide residuals to see weight comparison.</div>';
    return;
  }

  // Compute stats
  const residuals = resData.residual_lb.filter(v => !isNaN(v));
  const mean = residuals.reduce((a,b) => a+b, 0) / residuals.length;
  const rms = Math.sqrt(residuals.reduce((a,b) => a + b*b, 0) / residuals.length);
  const maxAbs = Math.max(...residuals.map(Math.abs));

  container.innerHTML = `
    <div class="card">
      <h3>Summary Statistics</h3>
      <div class="stat-box"><div class="label">Mean Error</div><div class="value">${mean.toFixed(2)} lb</div></div>
      <div class="stat-box"><div class="label">RMS Error</div><div class="value">${rms.toFixed(2)} lb</div></div>
      <div class="stat-box"><div class="label">Max |Error|</div><div class="value">${maxAbs.toFixed(2)} lb</div></div>
      <div class="stat-box"><div class="label">Samples</div><div class="value">${resData.time_s.length}</div></div>
    </div>
    <div class="card">
      <h3>Indicated vs Actual Weight</h3>
      <div id="wt-overlay" class="plot-container"></div>
    </div>
    <div class="card">
      <h3>Per-Tank Indicated Weight</h3>
      <div id="wt-pertank" class="plot-container"></div>
    </div>
  `;

  // Weight overlay with residual subplot
  const overlayTraces = [
    { x: resData.time_s, y: resData.indicated_lb, type: 'scatter', mode: 'lines',
      name: 'Indicated', line: { color: '#1565c0', width: 1.5 }, yaxis: 'y' },
    { x: resData.time_s, y: resData.actual_lb, type: 'scatter', mode: 'lines',
      name: 'Actual (scale)', line: { color: '#2e7d32', width: 1.5 }, yaxis: 'y' },
    { x: resData.time_s, y: resData.residual_lb, type: 'scatter', mode: 'lines',
      name: 'Residual', line: { color: '#e53935', width: 1 }, yaxis: 'y2' },
  ];

  Plotly.newPlot('wt-overlay', overlayTraces, {
    grid: { rows: 2, columns: 1, pattern: 'independent', roworder: 'top to bottom' },
    yaxis: { title: 'Weight (lb)', domain: [0.35, 1] },
    yaxis2: { title: 'Error (lb)', domain: [0, 0.25] },
    xaxis: { title: '' }, xaxis2: { title: 'Time (s)' },
    height: 500, margin: { t: 10 },
    legend: { orientation: 'h', y: -0.05 },
  }, { responsive: true });

  // Per-tank breakdown
  if (resData.per_tank) {
    const tankTraces = [];
    const tankColors = ['#2196F3','#4CAF50','#FF9800','#E91E63','#9C27B0'];
    const tids = Object.keys(resData.per_tank).sort();
    tids.forEach((tid, i) => {
      tankTraces.push({
        x: resData.time_s, y: resData.per_tank[tid],
        type: 'scatter', mode: 'lines',
        name: tid, line: { width: 1.5, color: tankColors[i % tankColors.length] },
        stackgroup: 'one',
      });
    });

    Plotly.newPlot('wt-pertank', tankTraces, {
      xaxis: { title: 'Time (s)' },
      yaxis: { title: 'Indicated Weight (lb)' },
      height: 400, margin: { t: 10 },
    }, { responsive: true });
  }
}

// Initialize all views
window.addEventListener('load', () => {
  initHV();
  initError();
  initCoverage();
  initWeight();
});
</script>
</body>
</html>
"""
