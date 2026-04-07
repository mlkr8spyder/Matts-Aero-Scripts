"""
Tank geometry definitions and volume computations for the synthetic 5-tank fuel system.

Coordinate system:
    X (FS) — Fuselage Station, positive aft
    Y (BL) — Buttline, positive right (starboard)
    Z (WL) — Waterline, positive up

All tanks are rectangular prisms. Volume under a tilted fuel plane is computed
analytically for arbitrary pitch and roll attitudes.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
IN3_PER_GALLON = 231.0
ULLAGE_FRACTION = 0.02          # top 2% reserved for thermal expansion
UNUSABLE_FRACTION = 0.015       # bottom 1.5% trapped below sump/probe
STRUCTURAL_FRACTION = 0.003     # ~0.3% of gross displaced by internal hardware
                                # (probes, baffles, pickups, fittings, wiring)


@dataclass
class Probe:
    """A single capacitance probe.

    A real capacitance probe has a *physical* envelope (the mounting hardware
    from base to top) and an *electrical* envelope (the active sensing region
    between the lower and upper guard electrodes). The sense region is
    typically inset from the physical ends by a small amount (end caps,
    mounting flanges, and guard rings). Fuel height reported by the
    electronics is relative to the bottom **sense point**, not the physical
    base of the probe, so the two offsets must be tracked separately.
    """
    name: str
    base_fs: float
    base_bl: float
    base_wl: float
    top_fs: float
    top_bl: float
    top_wl: float

    # Sense-point offsets (inches inset from the physical probe ends along
    # the probe axis). Defaults are zero for backward compatibility.
    sense_offset_base: float = 0.0  # distance from physical base to lower sense point
    sense_offset_top: float = 0.0   # distance from physical top to upper sense point

    @property
    def active_length(self) -> float:
        """Total physical length of the probe envelope (base→top)."""
        return self.top_wl - self.base_wl

    @property
    def sense_base_wl(self) -> float:
        """Waterline of the lower sense point (bottom of the electrical active region)."""
        return self.base_wl + self.sense_offset_base

    @property
    def sense_top_wl(self) -> float:
        """Waterline of the upper sense point (top of the electrical active region)."""
        return self.top_wl - self.sense_offset_top

    @property
    def active_sense_length(self) -> float:
        """Electrical active length — the span over which fuel height is actually sensed."""
        return max(0.0, self.sense_top_wl - self.sense_base_wl)

    @property
    def center_fs(self) -> float:
        return 0.5 * (self.base_fs + self.top_fs)

    @property
    def center_bl(self) -> float:
        return 0.5 * (self.base_bl + self.top_bl)

    @property
    def tilt_deg(self) -> float:
        """Tilt angle from vertical in degrees."""
        dbl = self.top_bl - self.base_bl
        dfs = self.top_fs - self.base_fs
        dh = self.top_wl - self.base_wl
        horiz = np.sqrt(dbl**2 + dfs**2)
        return np.degrees(np.arctan2(horiz, dh))


@dataclass
class Tank:
    """Rectangular prism fuel tank with probe(s)."""
    name: str
    tank_id: int           # 1-5
    fs_min: float
    fs_max: float
    bl_min: float
    bl_max: float
    wl_min: float
    wl_max: float
    probes: list = field(default_factory=list)
    probe_type: str = "real"   # "real", "real_pseudo_combo", "pure_pseudo"

    # --- Pure pseudo projection info (Tank 5) ---
    pseudo_ref_fs: Optional[float] = None
    pseudo_ref_bl: Optional[float] = None
    pseudo_source_tank_id: Optional[int] = None

    @property
    def length_fs(self) -> float:
        return self.fs_max - self.fs_min

    @property
    def width_bl(self) -> float:
        return self.bl_max - self.bl_min

    @property
    def height_wl(self) -> float:
        return self.wl_max - self.wl_min

    @property
    def base_area(self) -> float:
        """Base cross-section area in in²."""
        return self.length_fs * self.width_bl

    @property
    def gross_volume_in3(self) -> float:
        return self.base_area * self.height_wl

    @property
    def gross_volume_gal(self) -> float:
        return self.gross_volume_in3 / IN3_PER_GALLON

    @property
    def ullage_height(self) -> float:
        return self.height_wl * ULLAGE_FRACTION

    @property
    def unusable_height(self) -> float:
        return self.height_wl * UNUSABLE_FRACTION

    @property
    def usable_height(self) -> float:
        return self.height_wl - self.ullage_height - self.unusable_height

    @property
    def usable_volume_gal(self) -> float:
        return self.base_area * self.usable_height / IN3_PER_GALLON

    @property
    def max_fill_wl(self) -> float:
        """Maximum fuel surface WL (below ullage ceiling)."""
        return self.wl_max - self.ullage_height

    @property
    def min_fuel_wl(self) -> float:
        """Minimum indication WL (above unusable zone)."""
        return self.wl_min + self.unusable_height

    @property
    def center_fs(self) -> float:
        return 0.5 * (self.fs_min + self.fs_max)

    @property
    def center_bl(self) -> float:
        return 0.5 * (self.bl_min + self.bl_max)

    @property
    def center_wl(self) -> float:
        return 0.5 * (self.wl_min + self.wl_max)

    def corner_points(self) -> np.ndarray:
        """Return 8 corner points as (8, 3) array [FS, BL, WL]."""
        corners = []
        for fs in [self.fs_min, self.fs_max]:
            for bl in [self.bl_min, self.bl_max]:
                for wl in [self.wl_min, self.wl_max]:
                    corners.append([fs, bl, wl])
        return np.array(corners)


# ---------------------------------------------------------------------------
# Volume computation for tilted rectangular prism
# ---------------------------------------------------------------------------

def fuel_volume_tilted_rect(tank: Tank, fuel_height_at_ref: float,
                            pitch_deg: float, roll_deg: float,
                            ref_fs: Optional[float] = None,
                            ref_bl: Optional[float] = None) -> float:
    """
    Compute fuel volume in a rectangular prism tank given a fuel surface height
    at a reference point and aircraft pitch/roll.

    The fuel surface is a plane. For small angles:
        z_fuel(x, y) = z_ref + (x - x_ref) * tan(pitch) + (y - y_ref) * tan(roll)

    Sign convention:
        Positive pitch (nose up) → fuel moves aft → z increases with FS
        NOTE: FS increases aft, pitch-up means gravity pulls fuel aft,
              so z_fuel increases with FS for positive pitch.
        Positive roll (right wing down) → fuel moves right → z increases with BL

    For a rectangular prism this has an analytical solution via clipping the
    plane against the box and integrating.

    Parameters
    ----------
    tank : Tank
    fuel_height_at_ref : float
        Fuel surface WL at the reference point (typically probe location or tank center).
    pitch_deg : float
        Aircraft pitch in degrees (positive = nose up).
    roll_deg : float
        Aircraft roll in degrees (positive = right wing down).
    ref_fs, ref_bl : float, optional
        Reference point FS/BL. Defaults to tank center.

    Returns
    -------
    volume_in3 : float
        Fuel volume in cubic inches (clamped to [0, gross_volume]).
    """
    if ref_fs is None:
        ref_fs = tank.center_fs
    if ref_bl is None:
        ref_bl = tank.center_bl

    pitch_rad = np.radians(pitch_deg)
    roll_rad = np.radians(roll_deg)

    tan_p = np.tan(pitch_rad)
    tan_r = np.tan(roll_rad)

    Lx = tank.length_fs
    Ly = tank.width_bl

    # Fuel height at each corner of the base rectangle
    # Corner positions relative to reference point
    dx_corners = np.array([tank.fs_min - ref_fs, tank.fs_max - ref_fs])
    dy_corners = np.array([tank.bl_min - ref_bl, tank.bl_max - ref_bl])

    # Fuel surface height at each of the 4 base corners
    z_fuel_corners = []
    for dx in dx_corners:
        for dy in dy_corners:
            z = fuel_height_at_ref + dx * tan_p + dy * tan_r
            z_fuel_corners.append(z)
    z_fuel_corners = np.array(z_fuel_corners)

    # Clip fuel heights to tank bounds
    h_corners = np.clip(z_fuel_corners - tank.wl_min, 0.0, tank.height_wl)

    # For a rectangular base with a planar surface, the volume is the average
    # of the clipped corner heights times the base area — BUT only if the
    # plane doesn't partially intersect the tank floor or ceiling within the
    # base rectangle. For cases where it does, we need a more careful integration.

    # Full analytical approach: integrate over the rectangle
    volume = _integrate_planar_volume(
        tank.wl_min, tank.wl_max,
        tank.fs_min, tank.fs_max,
        tank.bl_min, tank.bl_max,
        fuel_height_at_ref, ref_fs, ref_bl,
        tan_p, tan_r
    )

    return np.clip(volume, 0.0, tank.gross_volume_in3)


def _integrate_planar_volume(wl_min, wl_max, fs_min, fs_max, bl_min, bl_max,
                             z_ref, ref_fs, ref_bl, tan_p, tan_r,
                             nx=100, ny=100) -> float:
    """
    Numerically integrate the volume of fuel in a rectangular box under a tilted
    fuel plane using a fine grid.

    For production use this could be done analytically, but numerical integration
    is more robust for validation and handles all clipping cases cleanly.
    """
    # 100x100 integration grid gives <0.01% volume error for rectangular prisms.
    # Finer grids (200x200) improve accuracy for complex shapes but 4x slower.

    # Create grid of cell centers
    dx = (fs_max - fs_min) / nx
    dy = (bl_max - bl_min) / ny
    cell_area = dx * dy

    fs_centers = np.linspace(fs_min + dx/2, fs_max - dx/2, nx)
    bl_centers = np.linspace(bl_min + dy/2, bl_max - dy/2, ny)

    FS, BL = np.meshgrid(fs_centers, bl_centers, indexing='ij')

    # Fuel surface height at each cell center
    z_fuel = z_ref + (FS - ref_fs) * tan_p + (BL - ref_bl) * tan_r

    # Fuel depth at each cell (clipped to tank height)
    h_fuel = np.clip(z_fuel - wl_min, 0.0, wl_max - wl_min)

    volume = np.sum(h_fuel) * cell_area
    return volume


def fuel_height_at_point(fuel_height_at_ref: float, ref_fs: float, ref_bl: float,
                         point_fs: float, point_bl: float,
                         pitch_deg: float, roll_deg: float) -> float:
    """
    Given fuel surface height at a reference point, compute the fuel surface
    height at another point via the tilted plane equation.
    """
    tan_p = np.tan(np.radians(pitch_deg))
    tan_r = np.tan(np.radians(roll_deg))
    return fuel_height_at_ref + (point_fs - ref_fs) * tan_p + (point_bl - ref_bl) * tan_r


def wetted_height_on_probe(probe: Probe, fuel_surface_wl: float) -> float:
    """
    Compute the wetted height on a probe given the fuel surface WL at the
    probe's location. Returns the wetted length measured from the probe's
    *physical* base along the probe axis (0 to active_length).

    This is the raw geometric wetted length. Real capacitance electronics
    only sense the portion between the lower and upper sense points — see
    :func:`sensed_height_on_probe` for the electrically-reported height.
    """
    # For a nearly-vertical probe, the wetted height is approximately
    # the fuel surface WL minus the probe base WL, projected onto the probe axis.
    raw_wetted = fuel_surface_wl - probe.base_wl
    wetted = np.clip(raw_wetted, 0.0, probe.active_length)
    return wetted


def sensed_height_on_probe(probe: Probe, fuel_surface_wl: float) -> float:
    """
    Compute the height reported by the capacitance electronics for a given
    fuel surface WL at the probe's location.

    The electronics measure wetted capacitance over the active sense region
    (between ``sense_base_wl`` and ``sense_top_wl``) and report that height
    *relative to the lower sense point*. Below the lower sense point the
    reading saturates at 0; above the upper sense point it saturates at
    ``active_sense_length``.

    Returns a value in inches, in the range [0, active_sense_length].
    """
    raw = fuel_surface_wl - probe.sense_base_wl
    return float(np.clip(raw, 0.0, probe.active_sense_length))


def indicated_to_physical_height(probe: Probe, sensed_height: float) -> float:
    """
    Convert a sensed height (measured from the lower sense point) back to a
    height referenced to the probe's physical base.

    This is the inverse of the sense-point offset. H-V tables are built
    against physical base-referenced heights, so the sensed height must be
    shifted up by ``sense_offset_base`` before table lookup.
    """
    return sensed_height + probe.sense_offset_base


def cg_for_fuel_state(tank: Tank, fuel_height_at_ref: float,
                      pitch_deg: float, roll_deg: float,
                      ref_fs: Optional[float] = None,
                      ref_bl: Optional[float] = None) -> tuple:
    """
    Compute CG of the fuel in the tank (FS, BL, WL) for a given fuel state.

    For a rectangular tank with planar fuel surface, this uses numerical integration.

    Returns (cg_fs, cg_bl, cg_wl) or (NaN, NaN, NaN) if tank is empty.
    """
    if ref_fs is None:
        ref_fs = tank.center_fs
    if ref_bl is None:
        ref_bl = tank.center_bl

    tan_p = np.tan(np.radians(pitch_deg))
    tan_r = np.tan(np.radians(roll_deg))

    # 50x50 grid is adequate for CG (moment-weighted average is less
    # sensitive to discretization than total volume integration).
    nx, ny = 50, 50
    dx = tank.length_fs / nx
    dy = tank.width_bl / ny
    cell_area = dx * dy

    fs_centers = np.linspace(tank.fs_min + dx/2, tank.fs_max - dx/2, nx)
    bl_centers = np.linspace(tank.bl_min + dy/2, tank.bl_max - dy/2, ny)
    FS, BL = np.meshgrid(fs_centers, bl_centers, indexing='ij')

    z_fuel = fuel_height_at_ref + (FS - ref_fs) * tan_p + (BL - ref_bl) * tan_r
    h_fuel = np.clip(z_fuel - tank.wl_min, 0.0, tank.height_wl)

    vol_cells = h_fuel * cell_area
    total_vol = np.sum(vol_cells)

    if total_vol < 1e-10:
        return (np.nan, np.nan, np.nan)

    # CG of each rectangular column is at half its fuel depth.
    # This assumes uniform density within the column (no stratification).
    cg_wl_cells = tank.wl_min + h_fuel / 2.0

    cg_fs = np.sum(FS * vol_cells) / total_vol
    cg_bl = np.sum(BL * vol_cells) / total_vol
    cg_wl = np.sum(cg_wl_cells * vol_cells) / total_vol

    return (cg_fs, cg_bl, cg_wl)


# ---------------------------------------------------------------------------
# System definition: 5-tank plus-sign layout
# ---------------------------------------------------------------------------

def build_tank_system() -> dict:
    """
    Build the complete 5-tank synthetic fuel system.

    Returns a dict keyed by tank_id (1-5) containing Tank objects.
    """

    # Typical sense-point insets for a capacitance probe:
    #   - 0.50" at the base for the lower guard ring + mounting flange
    #   - 0.25" at the top for the upper guard ring + end cap
    # These values shift the electrically-sensed region *inside* the
    # physical envelope. Fuel wets the hardware below the lower sense
    # point but is not reported by the electronics.

    # ---- Tank 1: Forward ----
    t1 = Tank(
        name="Forward", tank_id=1,
        fs_min=195.0, fs_max=225.0,
        bl_min=-15.0, bl_max=15.0,
        wl_min=88.0,  wl_max=104.0,
        probe_type="real",
        probes=[
            Probe("T1_probe", base_fs=210.0, base_bl=-0.5, base_wl=88.24,
                  top_fs=210.0, top_bl=0.5, top_wl=103.68,
                  sense_offset_base=0.50, sense_offset_top=0.25),
        ],
    )

    # ---- Tank 2: Left ----
    t2 = Tank(
        name="Left", tank_id=2,
        fs_min=235.0, fs_max=285.0,
        bl_min=-62.0, bl_max=-22.0,
        wl_min=85.0,  wl_max=103.0,
        probe_type="real",
        probes=[
            Probe("T2_probe", base_fs=260.0, base_bl=-42.5, base_wl=85.27,
                  top_fs=260.0, top_bl=-41.5, top_wl=102.64,
                  sense_offset_base=0.50, sense_offset_top=0.25),
        ],
    )

    # ---- Tank 3: Center (Collector) ----
    t3 = Tank(
        name="Center", tank_id=3,
        fs_min=235.0, fs_max=285.0,
        bl_min=-20.0, bl_max=20.0,
        wl_min=80.0,  wl_max=100.0,
        probe_type="real_pseudo_combo",
        probes=[
            Probe("T3_lower", base_fs=260.0, base_bl=-0.5, base_wl=80.30,
                  top_fs=260.0, top_bl=0.0, top_wl=92.00,
                  sense_offset_base=0.50, sense_offset_top=0.20),
            Probe("T3_upper", base_fs=260.0, base_bl=0.0, base_wl=90.00,
                  top_fs=260.0, top_bl=0.5, top_wl=99.60,
                  sense_offset_base=0.20, sense_offset_top=0.25),
        ],
    )

    # ---- Tank 4: Right ----
    t4 = Tank(
        name="Right", tank_id=4,
        fs_min=235.0, fs_max=285.0,
        bl_min=22.0,  bl_max=62.0,
        wl_min=85.0,  wl_max=103.0,
        probe_type="real",
        probes=[
            Probe("T4_probe", base_fs=260.0, base_bl=41.5, base_wl=85.27,
                  top_fs=260.0, top_bl=42.5, top_wl=102.64,
                  sense_offset_base=0.50, sense_offset_top=0.25),
        ],
    )

    # ---- Tank 5: Aft (Pure Pseudo) ----
    t5 = Tank(
        name="Aft", tank_id=5,
        fs_min=295.0, fs_max=335.0,
        bl_min=-17.5, bl_max=17.5,
        wl_min=83.0,  wl_max=105.0,
        probe_type="pure_pseudo",
        probes=[],  # no physical probes
        pseudo_ref_fs=315.0,
        pseudo_ref_bl=0.0,
        pseudo_source_tank_id=3,
    )

    tanks = {t.tank_id: t for t in [t1, t2, t3, t4, t5]}
    return tanks


# ---------------------------------------------------------------------------
# Volume reduction pipeline: CAD → usable fuel
# ---------------------------------------------------------------------------

def volume_reduction_breakdown(tank: Tank,
                               structural_fraction: float = STRUCTURAL_FRACTION,
                               ullage_fraction: float = ULLAGE_FRACTION,
                               unusable_fraction: float = UNUSABLE_FRACTION
                               ) -> dict:
    """
    Compute the full CAD → usable fuel volume reduction pipeline for a tank.

    The raw CAD volume of a fuel tank is never the usable fuel capacity.
    Several physical and operational deductions must be applied in order:

        1. **Raw CAD volume**: the enclosed internal volume of the tank
           envelope as pulled straight from the CAD model (here idealized
           to a rectangular prism).

        2. **Structural / hardware displacement**: volume physically
           occupied inside the tank by probes, baffles, sump pickups,
           boost-pump canisters, fittings, wiring harnesses, and stringer
           stiffeners. This volume cannot hold fuel. Modeled here as a
           fixed fraction of gross (~0.3%).

        3. **Ullage reserve**: the top band of the tank reserved for
           thermal expansion and vent path. Fuel level is not permitted
           above ``wl_max - ullage_height``.

        4. **Unusable fuel**: fuel trapped below the lowest pickup (sump
           or boost-pump inlet). This fuel is physically present but
           cannot be consumed or reliably indicated.

        5. **Usable fuel capacity**: what remains. This is the number
           that appears on placards and in the flight manual.

    Returns
    -------
    dict with (all in³ unless noted):
        gross_cad_in3
        structural_displacement_in3
        after_structural_in3
        ullage_reserve_in3
        unusable_fuel_in3
        usable_in3
        usable_gal
        reduction_pct   — (1 - usable/gross) × 100
    """
    gross = tank.gross_volume_in3
    structural = gross * structural_fraction
    after_structural = gross - structural
    # Ullage and unusable are thin bands at top/bottom; compute on the
    # *original* base area (structural displacement is distributed).
    base_area = tank.base_area
    ullage = base_area * (tank.height_wl * ullage_fraction)
    unusable = base_area * (tank.height_wl * unusable_fraction)
    usable = after_structural - ullage - unusable
    usable = max(0.0, usable)

    return {
        'gross_cad_in3': gross,
        'gross_cad_gal': gross / IN3_PER_GALLON,
        'structural_displacement_in3': structural,
        'structural_displacement_gal': structural / IN3_PER_GALLON,
        'after_structural_in3': after_structural,
        'ullage_reserve_in3': ullage,
        'ullage_reserve_gal': ullage / IN3_PER_GALLON,
        'unusable_fuel_in3': unusable,
        'unusable_fuel_gal': unusable / IN3_PER_GALLON,
        'usable_in3': usable,
        'usable_gal': usable / IN3_PER_GALLON,
        'reduction_pct': (1.0 - usable / gross) * 100.0 if gross > 0 else 0.0,
    }


def print_volume_reduction_report(tanks: dict) -> None:
    """Print a per-tank CAD → usable volume reduction table."""
    print(f"{'Tank':<18} {'Gross':>10} {'Struct':>10} {'Ullage':>10} "
          f"{'Unusable':>10} {'Usable':>10} {'Red%':>7}")
    print(f"{'':<18} {'(gal)':>10} {'(gal)':>10} {'(gal)':>10} "
          f"{'(gal)':>10} {'(gal)':>10} {'':>7}")
    print("-" * 82)
    totals = {'gross': 0.0, 'struct': 0.0, 'ullage': 0.0,
              'unusable': 0.0, 'usable': 0.0}
    for tid in sorted(tanks.keys()):
        t = tanks[tid]
        b = volume_reduction_breakdown(t)
        print(f"T{t.tank_id} {t.name:<13} "
              f"{b['gross_cad_gal']:>10.2f} "
              f"{b['structural_displacement_gal']:>10.2f} "
              f"{b['ullage_reserve_gal']:>10.2f} "
              f"{b['unusable_fuel_gal']:>10.2f} "
              f"{b['usable_gal']:>10.2f} "
              f"{b['reduction_pct']:>6.2f}%")
        totals['gross'] += b['gross_cad_gal']
        totals['struct'] += b['structural_displacement_gal']
        totals['ullage'] += b['ullage_reserve_gal']
        totals['unusable'] += b['unusable_fuel_gal']
        totals['usable'] += b['usable_gal']
    print("-" * 82)
    red_pct = (1.0 - totals['usable'] / totals['gross']) * 100.0
    print(f"{'TOTAL':<18} {totals['gross']:>10.2f} {totals['struct']:>10.2f} "
          f"{totals['ullage']:>10.2f} {totals['unusable']:>10.2f} "
          f"{totals['usable']:>10.2f} {red_pct:>6.2f}%")


def print_system_summary(tanks: dict) -> None:
    """Print a summary table of the tank system."""
    print(f"{'Tank':<20} {'Gross(gal)':>10} {'Usable(gal)':>12} {'Floor WL':>10} "
          f"{'Height':>8} {'Probe Type':<20}")
    print("-" * 85)
    total_gross = 0.0
    total_usable = 0.0
    for tid in sorted(tanks.keys()):
        t = tanks[tid]
        total_gross += t.gross_volume_gal
        total_usable += t.usable_volume_gal
        print(f"T{t.tank_id} {t.name:<15} {t.gross_volume_gal:>10.2f} "
              f"{t.usable_volume_gal:>12.2f} {t.wl_min:>10.1f} "
              f"{t.height_wl:>8.1f} {t.probe_type:<20}")
    print("-" * 85)
    print(f"{'TOTAL':<20} {total_gross:>10.2f} {total_usable:>12.2f}")


if __name__ == "__main__":
    tanks = build_tank_system()
    print_system_summary(tanks)

    # Quick volume sanity check at level attitude
    print("\nVolume check at 0° pitch, 0° roll (fuel at max fill):")
    for tid in sorted(tanks.keys()):
        t = tanks[tid]
        vol = fuel_volume_tilted_rect(t, t.max_fill_wl, 0.0, 0.0)
        expected = t.base_area * (t.max_fill_wl - t.wl_min)
        print(f"  T{tid} {t.name}: computed={vol:.1f} in³, "
              f"expected={expected:.1f} in³, diff={abs(vol-expected):.2f} in³")
