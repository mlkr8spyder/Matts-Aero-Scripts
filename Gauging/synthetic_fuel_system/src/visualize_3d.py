"""
3D visualization tool for the synthetic 5-tank fuel system.

Renders tanks as transparent rectangular prisms in aircraft coordinates,
with probes, fuel levels, blend zones, pseudo projection lines, gravity
transfer paths, and high-level sensor positions.

Usage:
    python -m src.visualize_3d                    # Static views (saved to plots/)
    python -m src.visualize_3d --interactive       # Interactive matplotlib window
    python -m src.visualize_3d --animate           # Animated defuel sequence
    python -m src.visualize_3d --fill 0.6          # Show at 60% fill
    python -m src.visualize_3d --pitch 3 --roll -2 # Show at specific attitude
"""

import argparse
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tank_geometry import (
    build_tank_system, fuel_volume_tilted_rect,
    fuel_height_at_point, IN3_PER_GALLON,
)


# ---------------------------------------------------------------------------
# Colors and style
# ---------------------------------------------------------------------------
TANK_COLORS = {
    1: (0.129, 0.588, 0.953, 0.12),   # blue
    2: (0.298, 0.686, 0.314, 0.12),   # green
    3: (1.000, 0.596, 0.000, 0.12),   # orange
    4: (0.914, 0.118, 0.388, 0.12),   # pink
    5: (0.612, 0.153, 0.690, 0.12),   # purple
}
TANK_EDGE_COLORS = {
    1: (0.129, 0.588, 0.953, 0.6),
    2: (0.298, 0.686, 0.314, 0.6),
    3: (1.000, 0.596, 0.000, 0.6),
    4: (0.914, 0.118, 0.388, 0.6),
    5: (0.612, 0.153, 0.690, 0.6),
}
FUEL_COLORS = {
    1: (0.129, 0.588, 0.953, 0.35),
    2: (0.298, 0.686, 0.314, 0.35),
    3: (1.000, 0.750, 0.200, 0.35),
    4: (0.914, 0.300, 0.500, 0.35),
    5: (0.612, 0.300, 0.750, 0.35),
}
TANK_NAMES = {1: 'T1 Forward', 2: 'T2 Left', 3: 'T3 Center', 4: 'T4 Right', 5: 'T5 Aft'}
PLOT_DIR = Path(__file__).parent.parent / "plots"


# ---------------------------------------------------------------------------
# 3D drawing primitives
# ---------------------------------------------------------------------------

def _box_faces(x0, x1, y0, y1, z0, z1):
    """Return the 6 faces of a rectangular box as vertex lists for Poly3DCollection."""
    # Each face is 4 vertices: [x, y, z]
    verts = [
        # Bottom (z=z0)
        [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0]],
        # Top (z=z1)
        [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]],
        # Front (x=x0)
        [[x0, y0, z0], [x0, y1, z0], [x0, y1, z1], [x0, y0, z1]],
        # Back (x=x1)
        [[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]],
        # Left (y=y0)
        [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]],
        # Right (y=y1)
        [[x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]],
    ]
    return verts


def _fuel_surface_verts(tank, fuel_wl_at_center, pitch_deg, roll_deg):
    """
    Compute the fuel volume shape inside a tank for a tilted fuel plane.
    Returns a list of face vertex lists representing the fuel body.

    For a rectangular tank with a planar fuel surface, the fuel body is a
    truncated prism — the base, up to 4 side faces clipped by the fuel plane,
    and the fuel surface itself.
    """
    tan_p = np.tan(np.radians(pitch_deg))
    tan_r = np.tan(np.radians(roll_deg))

    fs_min, fs_max = tank.fs_min, tank.fs_max
    bl_min, bl_max = tank.bl_min, tank.bl_max
    wl_min, wl_max = tank.wl_min, tank.wl_max
    ref_fs, ref_bl = tank.center_fs, tank.center_bl

    # Fuel surface WL at each corner of the base rectangle
    corners_fs = [fs_min, fs_max, fs_max, fs_min]
    corners_bl = [bl_min, bl_min, bl_max, bl_max]

    z_fuel = []
    for fs, bl in zip(corners_fs, corners_bl):
        z = fuel_wl_at_center + (fs - ref_fs) * tan_p + (bl - ref_bl) * tan_r
        z = np.clip(z, wl_min, wl_max)
        z_fuel.append(z)

    # Skip if completely empty or full
    if all(z <= wl_min + 0.01 for z in z_fuel):
        return []
    if all(z >= wl_max - 0.01 for z in z_fuel):
        return _box_faces(fs_min, fs_max, bl_min, bl_max, wl_min, wl_max)

    faces = []

    # Bottom face
    faces.append([
        [fs_min, bl_min, wl_min], [fs_max, bl_min, wl_min],
        [fs_max, bl_max, wl_min], [fs_min, bl_max, wl_min]
    ])

    # Top face (fuel surface — tilted)
    faces.append([
        [fs_min, bl_min, z_fuel[0]], [fs_max, bl_min, z_fuel[1]],
        [fs_max, bl_max, z_fuel[2]], [fs_min, bl_max, z_fuel[3]]
    ])

    # Four side faces (from floor to fuel surface)
    # Front face (fs=fs_min)
    faces.append([
        [fs_min, bl_min, wl_min], [fs_min, bl_max, wl_min],
        [fs_min, bl_max, z_fuel[3]], [fs_min, bl_min, z_fuel[0]]
    ])
    # Back face (fs=fs_max)
    faces.append([
        [fs_max, bl_min, wl_min], [fs_max, bl_max, wl_min],
        [fs_max, bl_max, z_fuel[2]], [fs_max, bl_min, z_fuel[1]]
    ])
    # Left face (bl=bl_min)
    faces.append([
        [fs_min, bl_min, wl_min], [fs_max, bl_min, wl_min],
        [fs_max, bl_min, z_fuel[1]], [fs_min, bl_min, z_fuel[0]]
    ])
    # Right face (bl=bl_max)
    faces.append([
        [fs_min, bl_max, wl_min], [fs_max, bl_max, wl_min],
        [fs_max, bl_max, z_fuel[2]], [fs_min, bl_max, z_fuel[3]]
    ])

    return faces


# ---------------------------------------------------------------------------
# Main 3D scene builder
# ---------------------------------------------------------------------------

def draw_tank_system(ax, tanks, fill_fractions=None, pitch_deg=0.0, roll_deg=0.0,
                     show_probes=True, show_fuel=True, show_labels=True,
                     show_blend_zone=True, show_pseudo_projection=True,
                     show_gravity_arrows=True, show_high_level_sensors=True,
                     show_unusable_zone=False):
    """
    Draw the complete 5-tank fuel system on a 3D matplotlib axes.

    Parameters
    ----------
    ax : Axes3D
    tanks : dict of Tank objects
    fill_fractions : dict {tank_id: fraction 0-1}, default 0.7
    pitch_deg, roll_deg : float, aircraft attitude
    show_* : bool, toggle visual elements
    """
    if fill_fractions is None:
        fill_fractions = {tid: 0.7 for tid in tanks}

    for tid, tank in tanks.items():
        color = TANK_COLORS[tid]
        edge_color = TANK_EDGE_COLORS[tid]
        fuel_color = FUEL_COLORS[tid]

        # --- Tank wireframe ---
        box = _box_faces(tank.fs_min, tank.fs_max,
                         tank.bl_min, tank.bl_max,
                         tank.wl_min, tank.wl_max)
        tank_poly = Poly3DCollection(box, alpha=color[3],
                                     facecolor=color[:3],
                                     edgecolor=edge_color[:3],
                                     linewidth=0.8)
        ax.add_collection3d(tank_poly)

        # --- Fuel volume ---
        if show_fuel and fill_fractions.get(tid, 0) > 0.001:
            fill = fill_fractions[tid]
            fuel_wl = tank.wl_min + tank.height_wl * fill
            fuel_faces = _fuel_surface_verts(tank, fuel_wl, pitch_deg, roll_deg)
            if fuel_faces:
                fuel_poly = Poly3DCollection(fuel_faces, alpha=fuel_color[3],
                                             facecolor=fuel_color[:3],
                                             edgecolor=fuel_color[:3],
                                             linewidth=0.3)
                ax.add_collection3d(fuel_poly)

        # --- Unusable fuel zone ---
        if show_unusable_zone:
            u_wl = tank.wl_min + tank.unusable_height
            unusable = _box_faces(tank.fs_min, tank.fs_max,
                                  tank.bl_min, tank.bl_max,
                                  tank.wl_min, u_wl)
            unusable_poly = Poly3DCollection(unusable, alpha=0.15,
                                             facecolor=(0.5, 0.5, 0.5),
                                             edgecolor=(0.5, 0.5, 0.5),
                                             linewidth=0.3)
            ax.add_collection3d(unusable_poly)

        # --- Probes ---
        if show_probes:
            for probe in tank.probes:
                ax.plot([probe.base_fs, probe.top_fs],
                        [probe.base_bl, probe.top_bl],
                        [probe.base_wl, probe.top_wl],
                        color='black', linewidth=3, solid_capstyle='round',
                        zorder=10)
                # Probe base marker
                ax.scatter([probe.base_fs], [probe.base_bl], [probe.base_wl],
                           color='black', s=30, zorder=11)
                # Probe top marker
                ax.scatter([probe.top_fs], [probe.top_bl], [probe.top_wl],
                           color='black', s=30, marker='^', zorder=11)

        # --- T3 blend zone ---
        if show_blend_zone and tank.probe_type == 'real_pseudo_combo':
            blend_lo, blend_hi = 90.0, 92.0
            blend = _box_faces(tank.fs_min, tank.fs_max,
                               tank.bl_min, tank.bl_max,
                               blend_lo, blend_hi)
            blend_poly = Poly3DCollection(blend, alpha=0.2,
                                          facecolor=(1.0, 1.0, 0.0),
                                          edgecolor=(0.8, 0.8, 0.0),
                                          linewidth=0.5)
            ax.add_collection3d(blend_poly)

        # --- High-level sensors ---
        if show_high_level_sensors:
            hl_wl = tank.max_fill_wl  # sensor at max fill (ullage boundary)
            # Draw as a small disk/marker at tank center, high level
            ax.scatter([tank.center_fs], [tank.center_bl], [hl_wl],
                       color='red', s=60, marker='D', zorder=12,
                       edgecolors='darkred', linewidths=1.0)

        # --- Labels ---
        if show_labels:
            ax.text(tank.center_fs, tank.center_bl, tank.wl_max + 1.5,
                    f'T{tid}\n{tank.name}',
                    ha='center', va='bottom', fontsize=8, fontweight='bold',
                    color=edge_color[:3])

    # --- T5 pseudo projection line ---
    if show_pseudo_projection:
        t3 = tanks[3]
        t5 = tanks[5]
        # Line from T3 probe center to T5 pseudo reference
        ax.plot([t3.center_fs, t5.pseudo_ref_fs],
                [t3.center_bl, t5.pseudo_ref_bl],
                [t3.center_wl, t5.center_wl],
                'r--', linewidth=1.5, alpha=0.6, zorder=5)
        ax.text(0.5*(t3.center_fs + t5.pseudo_ref_fs),
                0.5*(t3.center_bl + t5.pseudo_ref_bl),
                0.5*(t3.center_wl + t5.center_wl) + 2,
                'Pseudo\nprojection', fontsize=7, color='red',
                ha='center', va='bottom')

    # --- Gravity transfer arrows ---
    if show_gravity_arrows:
        t3 = tanks[3]
        for tid in [1, 2, 4, 5]:
            src = tanks[tid]
            # Arrow from source tank bottom to T3
            mid_fs = 0.5 * (src.center_fs + t3.center_fs)
            mid_bl = 0.5 * (src.center_bl + t3.center_bl)
            ax.plot([src.center_fs, t3.center_fs],
                    [src.center_bl, t3.center_bl],
                    [src.wl_min, t3.wl_min + 2],
                    color='gray', linewidth=1.0, alpha=0.4,
                    linestyle=':', zorder=3)


def setup_3d_axes(ax, title='Synthetic 5-Tank Fuel System'):
    """Configure 3D axes with proper labels and limits."""
    ax.set_xlabel('FS (in) — Aft →', fontsize=10)
    ax.set_ylabel('BL (in) — Right →', fontsize=10)
    ax.set_zlabel('WL (in) — Up →', fontsize=10)
    ax.set_title(title, fontsize=13, fontweight='bold')

    # Set consistent limits
    ax.set_xlim(180, 350)
    ax.set_ylim(-75, 75)
    ax.set_zlim(75, 112)

    # Better viewing angle
    ax.view_init(elev=25, azim=-60)

    # Reduce pane opacity
    ax.xaxis.pane.set_alpha(0.1)
    ax.yaxis.pane.set_alpha(0.1)
    ax.zaxis.pane.set_alpha(0.1)


# ---------------------------------------------------------------------------
# Multi-view rendering
# ---------------------------------------------------------------------------

def render_static_views(tanks=None, fill_fractions=None,
                        pitch_deg=0.0, roll_deg=0.0, save=True):
    """Render 4 views: 3D perspective, top, front, side."""
    if tanks is None:
        tanks = build_tank_system()
    if fill_fractions is None:
        fill_fractions = {tid: 0.7 for tid in tanks}

    fig = plt.figure(figsize=(20, 16))

    view_configs = [
        (221, 25, -60, '3D Perspective'),
        (222, 90, -90, 'Plan View (Top Down)'),
        (223, 0, 0, 'Front View (Looking Aft)'),
        (224, 0, -90, 'Side View (Looking from Right)'),
    ]

    for subplot, elev, azim, title in view_configs:
        ax = fig.add_subplot(subplot, projection='3d')
        draw_tank_system(ax, tanks, fill_fractions, pitch_deg, roll_deg,
                         show_labels=(subplot == 221),
                         show_gravity_arrows=(subplot == 221),
                         show_pseudo_projection=(subplot == 221))
        setup_3d_axes(ax, title)
        ax.view_init(elev=elev, azim=azim)

    fill_pct = {tid: f'{v*100:.0f}%' for tid, v in fill_fractions.items()}
    fig.suptitle(f'Tank System — Fill: {fill_pct}  |  Pitch: {pitch_deg:.1f}°  Roll: {roll_deg:.1f}°',
                 fontsize=14, fontweight='bold', y=0.98)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    if save:
        out = PLOT_DIR / '09_3d_tank_views.png'
        fig.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"Saved: {out}")
    return fig


def render_fill_sequence(tanks=None, n_frames=6, save=True):
    """Show the tank system at multiple fill levels in a single figure."""
    if tanks is None:
        tanks = build_tank_system()

    fill_levels = np.linspace(0.1, 0.95, n_frames)

    fig = plt.figure(figsize=(24, 10))
    for i, fill in enumerate(fill_levels):
        ax = fig.add_subplot(1, n_frames, i+1, projection='3d')
        fill_fracs = {tid: fill for tid in tanks}
        draw_tank_system(ax, tanks, fill_fracs, 0.0, 0.0,
                         show_labels=False, show_gravity_arrows=False,
                         show_pseudo_projection=False,
                         show_high_level_sensors=(fill > 0.9))
        setup_3d_axes(ax, f'{fill*100:.0f}% Fill')
        ax.view_init(elev=20, azim=-55)

    fig.suptitle('Tank Fill Levels — Empty to Full', fontsize=16, fontweight='bold')
    plt.tight_layout()
    if save:
        out = PLOT_DIR / '10_3d_fill_sequence.png'
        fig.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"Saved: {out}")
    return fig


def render_attitude_comparison(tanks=None, save=True):
    """Show tanks at different attitudes: level, pitched, rolled, combined."""
    if tanks is None:
        tanks = build_tank_system()

    fill_fracs = {tid: 0.5 for tid in tanks}

    attitudes = [
        (0, 0, 'Level (0°/0°)'),
        (5, 0, 'Nose Up 5°'),
        (0, 6, 'Right Wing Down 6°'),
        (4, -5, 'Nose Up 4° + Left Roll 5°'),
    ]

    fig = plt.figure(figsize=(22, 12))
    for i, (pitch, roll, title) in enumerate(attitudes):
        ax = fig.add_subplot(2, 2, i+1, projection='3d')
        draw_tank_system(ax, tanks, fill_fracs, pitch, roll,
                         show_labels=(i == 0), show_gravity_arrows=False,
                         show_pseudo_projection=False)
        setup_3d_axes(ax, title)
        ax.view_init(elev=20, azim=-55)

    fig.suptitle('Fuel Distribution at 50% Fill — Attitude Effects',
                 fontsize=16, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    if save:
        out = PLOT_DIR / '11_3d_attitude_comparison.png'
        fig.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"Saved: {out}")
    return fig


def render_refuel_system_diagram(tanks=None, save=True):
    """
    3D view highlighting the refuel system components:
    single-point adapter, manifold lines, distribution valves, high-level sensors.
    """
    if tanks is None:
        tanks = build_tank_system()

    fig = plt.figure(figsize=(16, 12))
    ax = fig.add_subplot(111, projection='3d')

    fill_fracs = {tid: 0.85 for tid in tanks}
    draw_tank_system(ax, tanks, fill_fracs, 0.0, 0.0,
                     show_gravity_arrows=False,
                     show_pseudo_projection=False,
                     show_high_level_sensors=True)

    # Single-point refuel adapter location (underside of center tank, forward)
    spra_fs, spra_bl, spra_wl = 240.0, 0.0, 78.0
    ax.scatter([spra_fs], [spra_bl], [spra_wl],
               color='green', s=200, marker='s', zorder=15,
               edgecolors='darkgreen', linewidths=2)
    ax.text(spra_fs, spra_bl - 5, spra_wl - 2,
            'Single-Point\nRefuel Adapter', fontsize=9, color='green',
            ha='center', va='top', fontweight='bold')

    # Manifold lines from adapter to each tank
    for tid, tank in tanks.items():
        # Line from adapter to tank bottom center
        target_fs = tank.center_fs
        target_bl = tank.center_bl
        target_wl = tank.wl_min

        # Route through a manifold point below the tanks
        mid_wl = 78.0
        ax.plot([spra_fs, target_fs], [spra_bl, target_bl],
                [mid_wl, mid_wl], color='green', linewidth=2, alpha=0.5)
        ax.plot([target_fs, target_fs], [target_bl, target_bl],
                [mid_wl, target_wl], color='green', linewidth=2, alpha=0.5)

        # Shutoff valve symbol (small marker on the vertical line)
        valve_wl = 0.5 * (mid_wl + target_wl)
        ax.scatter([target_fs], [target_bl], [valve_wl],
                   color='lime', s=40, marker='>', zorder=13,
                   edgecolors='darkgreen', linewidths=1)

    # Legend text
    ax.text(340, -70, 108,
            'Legend:\n'
            '■ Single-point refuel adapter\n'
            '◆ High-level sensor\n'
            '► Shutoff valve\n'
            '— Refuel manifold',
            fontsize=8, color='black',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    setup_3d_axes(ax, 'Refuel System — Single-Point Configuration')
    ax.view_init(elev=30, azim=-50)
    ax.set_zlim(72, 112)

    plt.tight_layout()
    if save:
        out = PLOT_DIR / '12_3d_refuel_system.png'
        fig.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"Saved: {out}")
    return fig


def render_probe_detail(tanks=None, save=True):
    """Close-up 3D view of Tank 3 showing the two-probe blend zone."""
    if tanks is None:
        tanks = build_tank_system()

    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection='3d')

    t3 = tanks[3]

    # Draw just T3 larger
    box = _box_faces(t3.fs_min, t3.fs_max, t3.bl_min, t3.bl_max,
                     t3.wl_min, t3.wl_max)
    tank_poly = Poly3DCollection(box, alpha=0.08,
                                 facecolor=TANK_COLORS[3][:3],
                                 edgecolor=TANK_EDGE_COLORS[3][:3],
                                 linewidth=1.5)
    ax.add_collection3d(tank_poly)

    # Fuel at 55% (in the blend zone)
    fuel_wl = t3.wl_min + t3.height_wl * 0.55  # WL 91 — in blend zone
    fuel_faces = _fuel_surface_verts(t3, fuel_wl, 0, 0)
    if fuel_faces:
        fuel_poly = Poly3DCollection(fuel_faces, alpha=0.25,
                                     facecolor=(0.3, 0.6, 1.0),
                                     edgecolor=(0.3, 0.6, 1.0),
                                     linewidth=0.3)
        ax.add_collection3d(fuel_poly)

    # Blend zone highlight
    blend = _box_faces(t3.fs_min, t3.fs_max, t3.bl_min, t3.bl_max, 90.0, 92.0)
    blend_poly = Poly3DCollection(blend, alpha=0.25,
                                  facecolor=(1.0, 1.0, 0.0),
                                  edgecolor=(0.8, 0.7, 0.0),
                                  linewidth=1.0)
    ax.add_collection3d(blend_poly)

    # Lower probe (thick)
    lower = t3.probes[0]
    ax.plot([lower.base_fs, lower.top_fs],
            [lower.base_bl, lower.top_bl],
            [lower.base_wl, lower.top_wl],
            color='blue', linewidth=5, solid_capstyle='round', zorder=10)
    ax.text(lower.top_fs + 3, lower.top_bl, lower.top_wl,
            f'Lower Probe\n{lower.active_length:.1f}"', fontsize=9,
            color='blue', fontweight='bold')

    # Upper probe (thick)
    upper = t3.probes[1]
    ax.plot([upper.base_fs, upper.top_fs],
            [upper.base_bl, upper.top_bl],
            [upper.base_wl, upper.top_wl],
            color='red', linewidth=5, solid_capstyle='round', zorder=10)
    ax.text(upper.top_fs + 3, upper.top_bl, upper.top_wl,
            f'Upper Probe\n{upper.active_length:.1f}"', fontsize=9,
            color='red', fontweight='bold')

    # Annotations
    ax.text(t3.fs_max + 2, t3.center_bl, 91.0,
            'Blend Zone\nWL 90–92', fontsize=10, color='goldenrod',
            fontweight='bold', ha='left')

    # Unusable zone
    u_wl = t3.wl_min + t3.unusable_height
    ax.plot([t3.fs_min, t3.fs_max], [t3.bl_min, t3.bl_min],
            [u_wl, u_wl], 'k--', linewidth=0.8, alpha=0.5)
    ax.text(t3.fs_min - 2, t3.bl_min, u_wl,
            f'Unusable\nWL {u_wl:.1f}', fontsize=7, color='gray', ha='right')

    # Ullage boundary
    ull_wl = t3.max_fill_wl
    ax.plot([t3.fs_min, t3.fs_max], [t3.bl_min, t3.bl_min],
            [ull_wl, ull_wl], 'r--', linewidth=0.8, alpha=0.5)
    ax.text(t3.fs_min - 2, t3.bl_min, ull_wl,
            f'Max Fill\nWL {ull_wl:.1f}', fontsize=7, color='red', ha='right')

    # High-level sensor
    ax.scatter([t3.center_fs], [t3.center_bl], [ull_wl],
               color='red', s=100, marker='D', zorder=12,
               edgecolors='darkred', linewidths=1.5)
    ax.text(t3.center_fs + 5, t3.center_bl, ull_wl + 0.5,
            'High-Level\nSensor', fontsize=8, color='darkred')

    ax.set_xlabel('FS (in)')
    ax.set_ylabel('BL (in)')
    ax.set_zlabel('WL (in)')
    ax.set_title('Tank 3 (Center) — Dual-Probe Blend Zone Detail',
                 fontsize=14, fontweight='bold')
    ax.set_xlim(230, 295)
    ax.set_ylim(-25, 25)
    ax.set_zlim(78, 102)
    ax.view_init(elev=20, azim=-45)

    plt.tight_layout()
    if save:
        out = PLOT_DIR / '13_3d_probe_detail.png'
        fig.savefig(out, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"Saved: {out}")
    return fig


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='3D Tank Visualization')
    parser.add_argument('--interactive', action='store_true',
                        help='Show interactive matplotlib window')
    parser.add_argument('--fill', type=float, default=0.7,
                        help='Fill fraction 0-1 (default 0.7)')
    parser.add_argument('--pitch', type=float, default=0.0)
    parser.add_argument('--roll', type=float, default=0.0)
    parser.add_argument('--animate', action='store_true',
                        help='Animate defuel sequence')
    args = parser.parse_args()

    if not args.interactive:
        matplotlib.use('Agg')

    tanks = build_tank_system()
    fill_fracs = {tid: args.fill for tid in tanks}

    PLOT_DIR.mkdir(exist_ok=True)

    print("Generating 3D visualizations...")
    render_static_views(tanks, fill_fracs, args.pitch, args.roll, save=True)
    render_fill_sequence(tanks, save=True)
    render_attitude_comparison(tanks, save=True)
    render_refuel_system_diagram(tanks, save=True)
    render_probe_detail(tanks, save=True)

    if args.interactive:
        fig = plt.figure(figsize=(14, 10))
        ax = fig.add_subplot(111, projection='3d')
        draw_tank_system(ax, tanks, fill_fracs, args.pitch, args.roll)
        setup_3d_axes(ax)
        plt.show()

    print("Done.")


if __name__ == "__main__":
    main()
