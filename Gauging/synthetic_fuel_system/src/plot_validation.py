"""
Validation plots for the synthetic fuel system.

Generates publication-quality figures:
  1. Tank layout (plan view and side view)
  2. H-V curves at multiple attitudes
  3. Probe coverage diagram
  4. Defuel error time history
  5. Per-tank error decomposition
  6. Attitude dependency heatmap
  7. Density error isolation
  8. Hysteresis comparison (defuel vs refuel)
"""

import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tank_geometry import build_tank_system, IN3_PER_GALLON
from src.hv_table_generator import generate_all_tables


PLOT_DIR = Path(__file__).parent.parent / "plots"
PLOT_DIR.mkdir(exist_ok=True)

# Per-tank colors matched to the interactive probe coverage tool's palette.
TANK_COLORS = {1: '#2196F3', 2: '#4CAF50', 3: '#FF9800', 4: '#E91E63', 5: '#9C27B0'}
TANK_NAMES = {1: 'T1 Forward', 2: 'T2 Left', 3: 'T3 Center', 4: 'T4 Right', 5: 'T5 Aft'}


def plot_tank_layout():
    """Plot plan view (top-down) and side view of the 5-tank system."""
    tanks = build_tank_system()

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))

    # --- Plan view (FS vs BL) ---
    ax = axes[0]
    ax.set_title('Plan View (Top Down)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Buttline BL (in) — Right +')
    ax.set_ylabel('Fuselage Station FS (in) — Aft +')

    for tid, tank in tanks.items():
        rect = mpatches.Rectangle(
            (tank.bl_min, tank.fs_min),
            tank.width_bl, tank.length_fs,
            linewidth=2, edgecolor=TANK_COLORS[tid],
            facecolor=TANK_COLORS[tid], alpha=0.3
        )
        ax.add_patch(rect)
        ax.text(tank.center_bl, tank.center_fs, f'T{tid}\n{tank.name}',
                ha='center', va='center', fontsize=10, fontweight='bold',
                color=TANK_COLORS[tid])

        # Plot probes
        for probe in tank.probes:
            ax.plot(probe.center_bl, probe.center_fs, 'k^', markersize=8)

    # T5 pseudo reference
    t5 = tanks[5]
    ax.plot(t5.pseudo_ref_bl, t5.pseudo_ref_fs, 'rx', markersize=10, markeredgewidth=2)
    ax.annotate('T5 pseudo\nref point', (t5.pseudo_ref_bl, t5.pseudo_ref_fs),
                textcoords="offset points", xytext=(15, 0), fontsize=8,
                arrowprops=dict(arrowstyle='->', color='red'))

    ax.set_xlim(-75, 75)
    ax.set_ylim(180, 350)
    ax.invert_yaxis()  # FS increases downward in plan view
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    # --- Side view (FS vs WL) ---
    ax = axes[1]
    ax.set_title('Side View (Looking from Left)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Fuselage Station FS (in) — Aft +')
    ax.set_ylabel('Waterline WL (in) — Up +')

    for tid, tank in tanks.items():
        rect = mpatches.Rectangle(
            (tank.fs_min, tank.wl_min),
            tank.length_fs, tank.height_wl,
            linewidth=2, edgecolor=TANK_COLORS[tid],
            facecolor=TANK_COLORS[tid], alpha=0.3
        )
        ax.add_patch(rect)
        ax.text(tank.center_fs, tank.center_wl, f'T{tid}',
                ha='center', va='center', fontsize=11, fontweight='bold',
                color=TANK_COLORS[tid])

        # Probes as vertical lines
        for probe in tank.probes:
            ax.plot([probe.base_fs, probe.top_fs],
                    [probe.base_wl, probe.top_wl],
                    'k-', linewidth=3, solid_capstyle='round')

    # Gravity transfer arrows
    for tid in [1, 2, 4, 5]:
        src = tanks[tid]
        dst = tanks[3]
        ax.annotate('', xy=(dst.center_fs, dst.wl_min + dst.height_wl * 0.8),
                    xytext=(src.center_fs, src.wl_min + 2),
                    arrowprops=dict(arrowstyle='->', color='gray', lw=1.5,
                                    connectionstyle='arc3,rad=0.2'))

    ax.set_xlim(180, 350)
    ax.set_ylim(75, 110)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    # Add legend for head heights
    head_text = "Gravity head above T3 (WL 80):\n"
    for tid in [1, 2, 4, 5]:
        head = tanks[tid].wl_min - tanks[3].wl_min
        head_text += f"  T{tid}: {head:.0f}\"\n"
    ax.text(0.02, 0.02, head_text, transform=ax.transAxes,
            fontsize=8, verticalalignment='bottom',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    plt.tight_layout()
    fig.savefig(PLOT_DIR / '01_tank_layout.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print("Saved: 01_tank_layout.png")


def plot_hv_curves():
    """Plot H-V curves at multiple attitudes for each tank."""
    tanks = build_tank_system()
    tables = generate_all_tables(tanks)

    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes_flat = axes.flatten()

    pitch_range = tables['pitch_range']
    roll_range = tables['roll_range']
    pi_zero = list(pitch_range).index(0.0)
    ri_zero = list(roll_range).index(0.0)

    # Sample 6 representative attitudes to show H-V curve sensitivity:
    # level, +/- pitch, +/- roll, and one combined case.
    attitudes = [
        (0, 0, 'Level (0°/0°)', 'k', '-'),
        (3, 0, 'Pitch +3°', '#E91E63', '--'),
        (-3, 0, 'Pitch -3°', '#2196F3', '--'),
        (0, 5, 'Roll +5°', '#4CAF50', ':'),
        (0, -5, 'Roll -5°', '#FF9800', ':'),
        (3, 5, 'P+3° R+5°', '#9C27B0', '-.'),
    ]

    for idx, tid in enumerate(sorted(tanks.keys())):
        ax = axes_flat[idx]
        tank = tanks[tid]

        for pitch, roll, label, color, ls in attitudes:
            pi = list(pitch_range).index(float(pitch))
            ri = list(roll_range).index(float(roll))
            t = tables['tanks'][tid]['tables'][pi][ri]

            # Convert to gallons, filter to valid range
            mask = (np.array(t['volumes_in3']) > 0) | (np.array(t['heights_rel']) > -0.5)
            heights = np.array(t['heights_rel'])[mask]
            vols_gal = np.array(t['volumes_gal'])[mask]

            ax.plot(heights, vols_gal, color=color, linestyle=ls,
                    linewidth=1.5, label=label)

        ax.set_title(f'T{tid} — {tank.name} ({tank.probe_type})', fontweight='bold')
        ax.set_xlabel('Probe Height (in)')
        ax.set_ylabel('Volume (gal)')
        ax.grid(True, alpha=0.3)

        # Mark usable range
        ax.axhline(tank.usable_volume_gal, color='gray', ls='--', alpha=0.5, lw=0.8)
        ax.axhline(tank.gross_volume_gal, color='red', ls='--', alpha=0.5, lw=0.8)

        if idx == 0:
            ax.legend(fontsize=7, loc='upper left')

    # Hide unused subplot
    axes_flat[5].set_visible(False)

    fig.suptitle('Height-Volume Curves at Multiple Attitudes', fontsize=16, fontweight='bold')
    plt.tight_layout()
    fig.savefig(PLOT_DIR / '02_hv_curves.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print("Saved: 02_hv_curves.png")


def plot_probe_coverage():
    """Diagram showing probe height ranges vs tank height ranges."""
    tanks = build_tank_system()

    fig, ax = plt.subplots(figsize=(12, 8))

    x_positions = {1: 1, 2: 2, 3: 3.5, 4: 5, 5: 6}
    bar_width = 0.6

    for tid, tank in tanks.items():
        x = x_positions[tid]

        # Tank outline
        ax.bar(x, tank.height_wl, bottom=tank.wl_min, width=bar_width,
               edgecolor=TANK_COLORS[tid], facecolor=TANK_COLORS[tid],
               alpha=0.15, linewidth=2)

        # Unusable zone (hatched)
        ax.bar(x, tank.unusable_height, bottom=tank.wl_min, width=bar_width,
               edgecolor='none', facecolor='gray', alpha=0.3, hatch='///')

        # Ullage zone (hatched)
        ax.bar(x, tank.ullage_height, bottom=tank.wl_max - tank.ullage_height,
               width=bar_width, edgecolor='none', facecolor='lightcoral',
               alpha=0.3, hatch='\\\\\\')

        # Probes
        probe_x_offset = 0.0
        for pi, probe in enumerate(tank.probes):
            px = x + 0.15 * (pi - 0.5 * (len(tank.probes) - 1))
            ax.plot([px, px], [probe.base_wl, probe.top_wl],
                    'k-', linewidth=4, solid_capstyle='round')
            ax.plot(px, probe.base_wl, 'ko', markersize=6)
            ax.plot(px, probe.top_wl, 'k^', markersize=6)
            ax.text(px + 0.15, 0.5*(probe.base_wl + probe.top_wl),
                    f'{probe.active_length:.1f}"',
                    fontsize=7, va='center')

        # T3 blend zone
        if tank.probe_type == 'real_pseudo_combo':
            ax.axhspan(90.0, 92.0, xmin=(x-0.3)/7, xmax=(x+0.3)/7,
                       color='yellow', alpha=0.3)
            ax.text(x + 0.45, 91.0, 'Blend\nZone', fontsize=7, va='center',
                    color='darkgoldenrod', fontweight='bold')

        # T5 pseudo indicator
        if tank.probe_type == 'pure_pseudo':
            ax.text(x, tank.center_wl, 'PSEUDO\n(no probe)', fontsize=8,
                    ha='center', va='center', color='red', fontweight='bold')

        # Label
        ax.text(x, tank.wl_min - 1.5, f'T{tid}\n{tank.name}\nWL {tank.wl_min}',
                ha='center', va='top', fontsize=9, fontweight='bold',
                color=TANK_COLORS[tid])

    ax.set_ylabel('Waterline WL (in)', fontsize=12)
    ax.set_title('Probe Coverage vs Tank Height', fontsize=14, fontweight='bold')
    ax.set_xlim(0.2, 7)
    ax.set_ylim(75, 110)
    ax.set_xticks([])
    ax.grid(True, axis='y', alpha=0.3)

    # Legend
    legend_elements = [
        mpatches.Patch(facecolor='gray', alpha=0.3, hatch='///', label='Unusable (1.5%)'),
        mpatches.Patch(facecolor='lightcoral', alpha=0.3, hatch='\\\\\\', label='Ullage (2%)'),
        plt.Line2D([0], [0], color='k', linewidth=4, label='Probe'),
        mpatches.Patch(facecolor='yellow', alpha=0.3, label='Blend zone'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=9)

    plt.tight_layout()
    fig.savefig(PLOT_DIR / '03_probe_coverage.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print("Saved: 03_probe_coverage.png")


def plot_defuel_error_timeseries(df: pd.DataFrame):
    """Plot defuel error vs time with per-tank volumes."""
    fig = plt.figure(figsize=(16, 14))
    gs = GridSpec(4, 1, height_ratios=[2, 1.5, 1, 1], hspace=0.3)

    # Panel 1: Total error vs time
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(df['time_s'], df['total_weight_error_lb'], 'k-', linewidth=1, alpha=0.8)
    ax1.fill_between(df['time_s'], df['total_weight_error_lb'], alpha=0.2, color='red')
    ax1.set_ylabel('Total Weight Error (lb)', fontsize=11)
    ax1.set_title('Defuel Sequence — Error Analysis', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)

    # Phase boundaries match the defuel sequence defined in simulate_sequences.py.
    # If the defuel phase timing changes, update these markers accordingly.
    for x_val, label in [(0, 'T1'), (200, 'T2+T4'), (550, 'T5'), (750, 'T3')]:
        if x_val < len(df):
            ax1.axvline(x_val, color='gray', ls='--', alpha=0.5)
            ax1.text(x_val + 5, ax1.get_ylim()[1] * 0.9, label,
                    fontsize=9, color='gray')

    # Panel 2: Per-tank volumes
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    for tid in range(1, 6):
        ax2.plot(df['time_s'], df[f'indicated_volume_gal_T{tid}'],
                color=TANK_COLORS[tid], linewidth=1.5, label=TANK_NAMES[tid])
    ax2.set_ylabel('Indicated Volume (gal)', fontsize=11)
    ax2.legend(loc='upper right', fontsize=8, ncol=3)
    ax2.grid(True, alpha=0.3)

    # Panel 3: Per-tank volume errors
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    for tid in range(1, 6):
        ax3.plot(df['time_s'], df[f'volume_error_in3_T{tid}'],
                color=TANK_COLORS[tid], linewidth=1, alpha=0.8)
    ax3.set_ylabel('Volume Error (in³)', fontsize=11)
    ax3.grid(True, alpha=0.3)

    # Panel 4: Pitch and roll
    ax4 = fig.add_subplot(gs[3], sharex=ax1)
    ax4.plot(df['time_s'], df['pitch_deg'], 'b-', linewidth=0.8, label='Pitch', alpha=0.7)
    ax4.plot(df['time_s'], df['roll_deg'], 'r-', linewidth=0.8, label='Roll', alpha=0.7)
    ax4.set_ylabel('Attitude (deg)', fontsize=11)
    ax4.set_xlabel('Time (s)', fontsize=11)
    ax4.legend(loc='upper right', fontsize=8)
    ax4.grid(True, alpha=0.3)

    fig.savefig(PLOT_DIR / '04_defuel_error_timeseries.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print("Saved: 04_defuel_error_timeseries.png")


def plot_error_vs_fuel_level(df_defuel: pd.DataFrame, df_refuel: pd.DataFrame):
    """Compare defuel and refuel errors vs total fuel level (hysteresis check)."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Left: Error vs fuel remaining
    ax = axes[0]
    ax.scatter(df_defuel['total_true_volume_gal'], df_defuel['total_weight_error_lb'],
              s=5, alpha=0.5, c='blue', label='Defuel')
    ax.scatter(df_refuel['total_true_volume_gal'], df_refuel['total_weight_error_lb'],
              s=5, alpha=0.5, c='red', label='Refuel')
    ax.set_xlabel('Total True Fuel Volume (gal)', fontsize=11)
    ax.set_ylabel('Total Weight Error (lb)', fontsize=11)
    ax.set_title('Error vs Fuel Level — Hysteresis Check', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    # Right: Error vs fuel level, colored by phase
    ax = axes[1]
    for phase_val in df_defuel['phase'].unique():
        mask = df_defuel['phase'] == phase_val
        phase_colors = {1: '#2196F3', 2: '#4CAF50', 3: '#9C27B0', 4: '#FF9800'}
        phase_labels = {1: 'Ph1: T1', 2: 'Ph2: T2+T4', 3: 'Ph3: T5', 4: 'Ph4: T3'}
        ax.scatter(df_defuel.loc[mask, 'total_true_volume_gal'],
                  df_defuel.loc[mask, 'total_weight_error_lb'],
                  s=8, alpha=0.6, c=phase_colors.get(phase_val, 'gray'),
                  label=phase_labels.get(phase_val, f'Ph{phase_val}'))
    ax.set_xlabel('Total True Fuel Volume (gal)', fontsize=11)
    ax.set_ylabel('Total Weight Error (lb)', fontsize=11)
    ax.set_title('Defuel Error by Phase (Active Tank)', fontsize=13, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(PLOT_DIR / '05_error_vs_fuel_level.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print("Saved: 05_error_vs_fuel_level.png")


def plot_attitude_heatmap(df: pd.DataFrame):
    """Heatmap of mean error vs pitch and roll bins."""
    fig, ax = plt.subplots(figsize=(10, 8))

    # Bin pitch and roll
    pitch_bins = np.arange(-4, 5, 1)
    roll_bins = np.arange(-5, 6, 1)

    df_copy = df.copy()
    df_copy['pitch_bin'] = pd.cut(df_copy['pitch_deg'], bins=np.arange(-4.5, 5.5, 1),
                                   labels=pitch_bins)
    df_copy['roll_bin'] = pd.cut(df_copy['roll_deg'], bins=np.arange(-5.5, 6.5, 1),
                                  labels=roll_bins)

    heatmap_data = df_copy.groupby(['pitch_bin', 'roll_bin'], observed=False)[
        'total_weight_error_lb'].mean().unstack()

    im = ax.imshow(heatmap_data.values, aspect='auto', cmap='RdBu_r',
                   origin='lower',
                   extent=[roll_bins[0]-0.5, roll_bins[-1]+0.5,
                           pitch_bins[0]-0.5, pitch_bins[-1]+0.5])

    ax.set_xlabel('Roll (deg)', fontsize=12)
    ax.set_ylabel('Pitch (deg)', fontsize=12)
    ax.set_title('Mean Weight Error vs Attitude', fontsize=14, fontweight='bold')
    plt.colorbar(im, ax=ax, label='Mean Error (lb)')
    ax.grid(True, alpha=0.2)

    plt.tight_layout()
    fig.savefig(PLOT_DIR / '06_attitude_heatmap.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print("Saved: 06_attitude_heatmap.png")


def plot_density_error(df: pd.DataFrame):
    """Isolate density contribution to total error."""
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # Density error over time
    ax = axes[0]
    ax.plot(df['time_s'], df['density_system'], 'b-', linewidth=1, label='System density')
    ax.axhline(df['density_lab'].iloc[0], color='r', ls='--', label='Lab density')
    ax.set_ylabel('Density (lb/gal)', fontsize=11)
    ax.set_title('Density Error Decomposition', fontsize=14, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Density-attributable vs volume-attributable weight error
    ax = axes[1]
    density_wt_error = df['total_indicated_volume_gal'] * df['density_error']
    vol_wt_error = df['total_weight_error_lb'] - density_wt_error

    ax.plot(df['time_s'], df['total_weight_error_lb'], 'k-', linewidth=1.5,
            label='Total error', alpha=0.8)
    ax.plot(df['time_s'], density_wt_error, 'r-', linewidth=1,
            label='Density contribution', alpha=0.7)
    ax.plot(df['time_s'], vol_wt_error, 'b-', linewidth=1,
            label='Volume contribution', alpha=0.7)
    ax.set_ylabel('Weight Error (lb)', fontsize=11)
    ax.set_xlabel('Time (s)', fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(PLOT_DIR / '07_density_error.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print("Saved: 07_density_error.png")


def plot_per_tank_error_bars(df: pd.DataFrame):
    """Bar chart of mean absolute volume error per tank."""
    fig, ax = plt.subplots(figsize=(10, 6))

    tank_ids = range(1, 6)
    means = []
    stds = []
    colors = []

    for tid in tank_ids:
        col = f'volume_error_in3_T{tid}'
        means.append(df[col].abs().mean())
        stds.append(df[col].abs().std())
        colors.append(TANK_COLORS[tid])

    x = np.arange(len(tank_ids))
    bars = ax.bar(x, means, yerr=stds, capsize=5, color=colors, alpha=0.7,
                  edgecolor='black', linewidth=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels([TANK_NAMES[tid] for tid in tank_ids])
    ax.set_ylabel('Mean |Volume Error| (in³)', fontsize=11)
    ax.set_title('Per-Tank Mean Absolute Volume Error', fontsize=14, fontweight='bold')
    ax.grid(True, axis='y', alpha=0.3)

    # Annotate with error source
    annotations = {
        1: 'Real probe\n(noise only)',
        2: 'Real probe\n+ nonlinearity',
        3: 'Real-pseudo\n+ blend step',
        4: 'Real probe\n(noise only)',
        5: 'Pure pseudo\n+ pitch amp.',
    }
    for i, tid in enumerate(tank_ids):
        ax.text(i, means[i] + stds[i] + 5, annotations[tid],
                ha='center', va='bottom', fontsize=8, color='gray')

    plt.tight_layout()
    fig.savefig(PLOT_DIR / '08_per_tank_error.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print("Saved: 08_per_tank_error.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from src.simulate_sequences import simulate_defuel, simulate_refuel

    print("Building system and generating tables...")
    tanks = build_tank_system()
    all_tables = generate_all_tables(tanks)

    print("\nGenerating simulations...")
    df_defuel = simulate_defuel(tanks, all_tables, n_samples=1000)
    df_refuel = simulate_refuel(tanks, all_tables, n_samples=800)

    print(f"\nGenerating plots → {PLOT_DIR}/")
    plot_tank_layout()
    plot_hv_curves()
    plot_probe_coverage()
    plot_defuel_error_timeseries(df_defuel)
    plot_error_vs_fuel_level(df_defuel, df_refuel)
    plot_attitude_heatmap(df_defuel)
    plot_density_error(df_defuel)
    plot_per_tank_error_bars(df_defuel)

    print(f"\nAll plots saved to: {PLOT_DIR}/")
