"""
Interactive probe coverage diagram with per-tank visibility toggles.

Supports all probe types:
  - "real"               : Single capacitance probe
  - "real_pseudo_combo"  : Two real probes with a blend zone (e.g., T3 lower/upper)
  - "pure_pseudo"        : No physical probe; height projected from another tank
  - "multi_probe_pseudo" : Multiple real probes in the same tank whose readings
                           are combined (averaged, blended, or voted) to produce
                           a single pseudo indication. Each probe covers a
                           different region of the tank.

Usage:
    python -m src.probe_coverage_interactive                # interactive window
    python -m src.probe_coverage_interactive --save out.png # save and exit
    python -m src.probe_coverage_interactive --tanks 1 3 5  # show only these tanks
"""

import argparse
import sys
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.widgets import CheckButtons
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.tank_geometry import build_tank_system, Tank, Probe


# ---------------------------------------------------------------------------
# Color palette — cycles for arbitrary number of tanks
# ---------------------------------------------------------------------------
_COLOR_CYCLE = [
    '#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0',
    '#00BCD4', '#FF5722', '#607D8B', '#795548', '#3F51B5',
    '#8BC34A', '#FFEB3B', '#009688', '#F44336', '#CDDC39',
    '#03A9F4', '#FFC107', '#673AB7', '#FF6F00', '#1B5E20',
]

def _tank_color(idx: int) -> str:
    return _COLOR_CYCLE[idx % len(_COLOR_CYCLE)]


# ---------------------------------------------------------------------------
# Probe type labels and indicators
# ---------------------------------------------------------------------------
_PROBE_TYPE_LABELS = {
    'real':               'Real',
    'real_pseudo_combo':  'Combo (blend)',
    'pure_pseudo':        'Pseudo (projected)',
    'multi_probe_pseudo': 'Multi-probe pseudo',
}


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _draw_tank(ax, tank: Tank, x: float, bar_width: float, color: str,
               show_sense_region: bool = True):
    """Draw a single tank column on the probe coverage diagram.

    Renders the tank body, unusable/ullage zones, probe lines, sense regions,
    blend zones, and annotations. For tanks with multiple probes, the probes
    are spread horizontally within the column width.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes for drawing.
    tank : Tank
        Tank geometry and probe definitions.
    x : float
        Horizontal center position for this tank column.
    bar_width : float
        Width of the tank column in axis units.
    color : str
        Tank color (hex string) for the body outline and label.
    show_sense_region : bool
        If True, overlay the electrical sense region on probe lines.
    """

    # Tank body
    ax.bar(x, tank.height_wl, bottom=tank.wl_min, width=bar_width,
           edgecolor=color, facecolor=color, alpha=0.12, linewidth=2,
           zorder=1)

    # Unusable zone (bottom hatch)
    ax.bar(x, tank.unusable_height, bottom=tank.wl_min, width=bar_width,
           edgecolor='none', facecolor='gray', alpha=0.25, hatch='///',
           zorder=2)

    # Ullage zone (top hatch)
    ax.bar(x, tank.ullage_height, bottom=tank.wl_max - tank.ullage_height,
           width=bar_width, edgecolor='none', facecolor='lightcoral',
           alpha=0.25, hatch='\\\\\\', zorder=2)

    # Probes
    n_probes = len(tank.probes)
    # Distribute multiple probes evenly within the tank column.
    # With n probes, they span 50% of the bar width, centered.
    for pi, probe in enumerate(tank.probes):
        if n_probes == 1:
            px = x
        else:
            spread = bar_width * 0.5
            px = x + spread * (pi / (n_probes - 1) - 0.5)

        # Physical envelope (thick black line)
        ax.plot([px, px], [probe.base_wl, probe.top_wl],
                'k-', linewidth=4, solid_capstyle='round', zorder=4)
        ax.plot(px, probe.base_wl, 'ko', markersize=5, zorder=5)
        ax.plot(px, probe.top_wl, 'k^', markersize=5, zorder=5)

        # Sense region (colored overlay on the probe line)
        if show_sense_region and (probe.sense_offset_base > 0 or probe.sense_offset_top > 0):
            ax.plot([px, px], [probe.sense_base_wl, probe.sense_top_wl],
                    color='#1565C0', linewidth=2.5, solid_capstyle='butt',
                    zorder=4, alpha=0.7)

        # Length annotation
        label_x = px + 0.12
        label_y = 0.5 * (probe.base_wl + probe.top_wl)
        length_str = f'{probe.active_length:.1f}"'
        if probe.active_sense_length < probe.active_length and show_sense_region:
            length_str += f'\n({probe.active_sense_length:.1f}" sense)'
        ax.text(label_x, label_y, length_str, fontsize=7, va='center',
                ha='left', zorder=6, color='#333333')

        # Probe name (if more than one)
        if n_probes > 1:
            ax.text(px, probe.top_wl + 0.4, probe.name, fontsize=6,
                    ha='center', va='bottom', color='#555555', rotation=30,
                    zorder=6)

    # Blend zone for combo probes
    if tank.probe_type == 'real_pseudo_combo' and len(tank.probes) >= 2:
        # Detect blend overlap: region where both probes cover
        p_lower = tank.probes[0]
        p_upper = tank.probes[1]
        blend_lo = max(p_lower.base_wl, p_upper.base_wl)
        blend_hi = min(p_lower.top_wl, p_upper.top_wl)
        if blend_hi > blend_lo:
            ax.bar(x, blend_hi - blend_lo, bottom=blend_lo, width=bar_width * 0.9,
                   edgecolor='darkgoldenrod', facecolor='yellow', alpha=0.3,
                   linewidth=1, linestyle='--', zorder=3)
            ax.text(x + bar_width * 0.5, 0.5 * (blend_lo + blend_hi),
                    'Blend\nZone', fontsize=7, va='center', ha='left',
                    color='darkgoldenrod', fontweight='bold', zorder=6)

    # Multi-probe pseudo: draw combination indicator
    if tank.probe_type == 'multi_probe_pseudo' and len(tank.probes) >= 2:
        # Draw a bracket/brace connecting all probes
        probe_tops = [p.top_wl for p in tank.probes]
        probe_bots = [p.base_wl for p in tank.probes]
        mid_wl = 0.5 * (min(probe_bots) + max(probe_tops))
        ax.text(x + bar_width * 0.5, mid_wl, 'Combined\nPseudo', fontsize=7,
                va='center', ha='left', color='#6A1B9A', fontweight='bold',
                zorder=6,
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#E1BEE7',
                          alpha=0.6, edgecolor='#6A1B9A', linewidth=0.8))
        # Coverage spans
        for pi, probe in enumerate(tank.probes):
            if n_probes == 1:
                px = x
            else:
                spread = bar_width * 0.5
                px = x + spread * (pi / (n_probes - 1) - 0.5)
            # Dashed line showing contribution range
            ax.plot([px - 0.05, px + 0.05, px + 0.05, px - 0.05, px - 0.05],
                    [probe.base_wl, probe.base_wl, probe.top_wl, probe.top_wl, probe.base_wl],
                    color='#6A1B9A', linewidth=0.8, linestyle=':', alpha=0.5, zorder=3)

    # Pure pseudo indicator (no probes)
    if tank.probe_type == 'pure_pseudo' and len(tank.probes) == 0:
        ax.text(x, tank.center_wl, 'PSEUDO\n(no probe)', fontsize=9,
                ha='center', va='center', color='red', fontweight='bold',
                zorder=6)

    # Tank label below
    type_label = _PROBE_TYPE_LABELS.get(tank.probe_type, tank.probe_type)
    ax.text(x, tank.wl_min - 1.2, f'T{tank.tank_id}\n{tank.name}',
            ha='center', va='top', fontsize=9, fontweight='bold', color=color,
            zorder=6)
    ax.text(x, tank.wl_min - 3.5, f'WL {tank.wl_min:.0f}-{tank.wl_max:.0f}\n{type_label}',
            ha='center', va='top', fontsize=7, color='#666666', zorder=6)


# ---------------------------------------------------------------------------
# Main interactive plot
# ---------------------------------------------------------------------------

def probe_coverage_interactive(tanks: dict = None,
                               initial_visible: list = None,
                               save_path: str = None,
                               show_sense: bool = True):
    """
    Launch an interactive probe coverage diagram.

    Parameters
    ----------
    tanks : dict
        Dict of {tank_id: Tank}. If None, uses build_tank_system().
    initial_visible : list of int
        Tank IDs to show initially. None = show all.
    save_path : str
        If provided, save the figure and exit without showing.
    show_sense : bool
        If True, overlay the electrical sense region on probe lines.
    """
    if tanks is None:
        tanks = build_tank_system()

    tank_ids = sorted(tanks.keys())
    n_tanks = len(tank_ids)

    if initial_visible is None:
        initial_visible = list(tank_ids)

    # Assign colors
    colors = {tid: _tank_color(i) for i, tid in enumerate(tank_ids)}

    # Compute global WL range for axis limits
    all_wl_min = min(t.wl_min for t in tanks.values()) - 6
    all_wl_max = max(t.wl_max for t in tanks.values()) + 3

    # --- Create figure with space for checkbuttons ---
    fig = plt.figure(figsize=(max(14, 2 + n_tanks * 1.8), 9))

    # Axes: main plot on the left, checkbuttons on the right
    ax_main = fig.add_axes([0.06, 0.08, 0.72, 0.85])
    ax_check = fig.add_axes([0.82, 0.25, 0.16, min(0.5, n_tanks * 0.045 + 0.05)])

    # --- State ---
    visibility = {tid: (tid in initial_visible) for tid in tank_ids}
    bar_width = 0.7

    def _get_visible_ids():
        return [tid for tid in tank_ids if visibility[tid]]

    def _draw():
        ax_main.cla()
        visible = _get_visible_ids()
        n_vis = len(visible)

        if n_vis == 0:
            ax_main.text(0.5, 0.5, 'No tanks selected', transform=ax_main.transAxes,
                         ha='center', va='center', fontsize=14, color='gray')
            ax_main.set_xlim(0, 1)
            ax_main.set_ylim(all_wl_min, all_wl_max)
            fig.canvas.draw_idle()
            return

        # Compute x positions: evenly spaced with padding
        spacing = max(1.0, 7.0 / max(n_vis, 1))
        x_map = {}
        for i, tid in enumerate(visible):
            x_map[tid] = 1.0 + i * spacing

        x_right = x_map[visible[-1]] + spacing * 0.5 + 0.5

        for tid in visible:
            _draw_tank(ax_main, tanks[tid], x_map[tid], bar_width,
                       colors[tid], show_sense_region=show_sense)

        ax_main.set_xlim(0.2, x_right)
        ax_main.set_ylim(all_wl_min, all_wl_max)
        ax_main.set_ylabel('Waterline WL (in)', fontsize=12)
        ax_main.set_title('Probe Coverage vs Tank Height', fontsize=14,
                          fontweight='bold')
        ax_main.set_xticks([])
        ax_main.grid(True, axis='y', alpha=0.3)

        # Legend
        legend_elements = [
            mpatches.Patch(facecolor='gray', alpha=0.25, hatch='///',
                           label='Unusable'),
            mpatches.Patch(facecolor='lightcoral', alpha=0.25, hatch='\\\\\\',
                           label='Ullage'),
            plt.Line2D([0], [0], color='k', linewidth=4, label='Probe (physical)'),
        ]
        if show_sense:
            legend_elements.append(
                plt.Line2D([0], [0], color='#1565C0', linewidth=2.5, alpha=0.7,
                           label='Sense region'))
        # Only show blend zone legend if any visible tank has it
        if any(tanks[tid].probe_type == 'real_pseudo_combo' for tid in visible):
            legend_elements.append(
                mpatches.Patch(facecolor='yellow', alpha=0.3,
                               edgecolor='darkgoldenrod', linestyle='--',
                               label='Blend zone'))
        if any(tanks[tid].probe_type == 'multi_probe_pseudo' for tid in visible):
            legend_elements.append(
                mpatches.Patch(facecolor='#E1BEE7', alpha=0.6,
                               edgecolor='#6A1B9A', label='Multi-probe pseudo'))

        ax_main.legend(handles=legend_elements, loc='upper right', fontsize=8,
                       framealpha=0.9)

        # Summary text
        total_usable = sum(tanks[tid].usable_volume_gal for tid in visible)
        total_gross = sum(tanks[tid].gross_volume_gal for tid in visible)
        summary = (f'Showing {n_vis}/{n_tanks} tanks | '
                   f'Usable: {total_usable:.1f} gal | '
                   f'Gross: {total_gross:.1f} gal')
        ax_main.text(0.01, 0.01, summary, transform=ax_main.transAxes,
                     fontsize=8, va='bottom', color='#444444',
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                               alpha=0.8, edgecolor='#CCCCCC'))

        fig.canvas.draw_idle()

    # --- Checkbuttons ---
    labels = [f'T{tid} {tanks[tid].name}' for tid in tank_ids]
    actives = [visibility[tid] for tid in tank_ids]
    check = CheckButtons(ax_check, labels, actives)

    # Style the checkbutton labels with tank colors
    for i, tid in enumerate(tank_ids):
        check.labels[i].set_fontsize(9)
        check.labels[i].set_color(colors[tid])
        check.labels[i].set_fontweight('bold')

    def _on_toggle(label):
        # Parse tank ID from label "T{id} {name}"
        tid_str = label.split()[0]  # "T1", "T2", etc.
        tid = int(tid_str[1:])
        visibility[tid] = not visibility[tid]
        _draw()

    check.on_clicked(_on_toggle)

    ax_check.set_title('Tanks', fontsize=10, fontweight='bold')

    # Initial draw
    _draw()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved: {save_path}")
        plt.close(fig)
    else:
        plt.show()

    return fig


# ---------------------------------------------------------------------------
# Demo with multi_probe_pseudo example
# ---------------------------------------------------------------------------

def _build_demo_system():
    """Build the standard 5-tank system plus a demo T6 with multi_probe_pseudo."""
    tanks = build_tank_system()

    # Add a demo tank 6 to demonstrate multi_probe_pseudo:
    # Two real probes in the same tank whose readings combine into one indication.
    # This is common in large tanks where a single probe can't span the full height
    # or where redundancy is needed for a pseudo-computed indication.
    t6 = Tank(
        name="Demo Multi",
        tank_id=6,
        fs_min=340.0, fs_max=380.0,
        bl_min=-15.0, bl_max=15.0,
        wl_min=82.0, wl_max=106.0,
        probe_type="multi_probe_pseudo",
        probes=[
            Probe("T6_lower", base_fs=360.0, base_bl=-0.5, base_wl=82.50,
                  top_fs=360.0, top_bl=0.0, top_wl=94.00,
                  sense_offset_base=0.50, sense_offset_top=0.20),
            Probe("T6_upper", base_fs=360.0, base_bl=0.0, base_wl=92.00,
                  top_fs=360.0, top_bl=0.5, top_wl=106.00,
                  sense_offset_base=0.20, sense_offset_top=0.25),
        ],
    )
    tanks[6] = t6
    return tanks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Interactive probe coverage diagram')
    parser.add_argument('--save', type=str, default=None,
                        help='Save to file instead of showing interactively')
    parser.add_argument('--tanks', type=int, nargs='*', default=None,
                        help='Tank IDs to show initially (default: all)')
    parser.add_argument('--no-sense', action='store_true',
                        help='Hide sense region overlay on probes')
    parser.add_argument('--demo', action='store_true',
                        help='Include a demo multi_probe_pseudo tank (T6)')
    args = parser.parse_args()

    if args.demo:
        tanks = _build_demo_system()
    else:
        tanks = build_tank_system()

    probe_coverage_interactive(
        tanks=tanks,
        initial_visible=args.tanks,
        save_path=args.save,
        show_sense=not args.no_sense,
    )
