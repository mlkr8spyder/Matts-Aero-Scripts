"""
Canonical data containers for the gauging analysis toolkit.

All importers convert their source format into these containers, providing
a uniform interface for the analysis and visualization layers.

Design notes:
  - Tank IDs are strings to support real naming like "LH_FWD_AUX".
  - H-V tables are variable-length arrays — no forcing onto a common grid.
  - Attitude keys are (pitch, roll) tuples to support irregular grids.
  - CG arrays are optional since not all programs track them.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HVTable:
    """
    A single height-vs-volume lookup table at one attitude condition.

    Each table has its own height breakpoints (variable-length), matching
    the MM1D convention where different attitudes can have different numbers
    of points.

    Attributes
    ----------
    heights : np.ndarray
        Height breakpoints in inches, relative to probe base or tank floor.
        Monotonically increasing.
    volumes : np.ndarray
        Volume at each height breakpoint, in cubic inches.
    pitch_deg : float
        Pitch attitude for this table (positive = nose up).
    roll_deg : float
        Roll attitude for this table (positive = right wing down).
    cg_fs : np.ndarray, optional
        CG fuselage station at each height breakpoint.
    cg_bl : np.ndarray, optional
        CG butt line at each height breakpoint.
    cg_wl : np.ndarray, optional
        CG water line at each height breakpoint.
    """
    heights: np.ndarray
    volumes: np.ndarray
    pitch_deg: float
    roll_deg: float
    cg_fs: Optional[np.ndarray] = None
    cg_bl: Optional[np.ndarray] = None
    cg_wl: Optional[np.ndarray] = None

    def __post_init__(self):
        self.heights = np.asarray(self.heights, dtype=float)
        self.volumes = np.asarray(self.volumes, dtype=float)
        if len(self.heights) != len(self.volumes):
            raise ValueError(
                f"heights ({len(self.heights)}) and volumes ({len(self.volumes)}) "
                f"must have the same length"
            )
        if self.cg_fs is not None:
            self.cg_fs = np.asarray(self.cg_fs, dtype=float)
        if self.cg_bl is not None:
            self.cg_bl = np.asarray(self.cg_bl, dtype=float)
        if self.cg_wl is not None:
            self.cg_wl = np.asarray(self.cg_wl, dtype=float)

    @property
    def n_points(self) -> int:
        return len(self.heights)

    @property
    def max_volume(self) -> float:
        return float(self.volumes[-1]) if len(self.volumes) > 0 else 0.0

    @property
    def height_range(self) -> tuple:
        """(min_height, max_height) in inches."""
        if len(self.heights) == 0:
            return (0.0, 0.0)
        return (float(self.heights[0]), float(self.heights[-1]))


@dataclass
class TankData:
    """
    All H-V tables for a single tank across multiple attitudes.

    Attributes
    ----------
    tank_id : str
        Tank identifier (e.g., "T3", "LH_FWD_AUX").
    tables : dict
        Mapping of (pitch_deg, roll_deg) -> HVTable. Supports irregular
        attitude grids — not all tanks need the same set of attitudes.
    name : str, optional
        Human-readable tank name (e.g., "Center", "Left Hand Forward Aux").
    probe_type : str, optional
        Probe configuration type (e.g., "real", "real_pseudo_combo").
    metadata : dict
        Arbitrary metadata (geometry bounds, probe info, program-specific).
    """
    tank_id: str
    tables: dict = field(default_factory=dict)
    name: Optional[str] = None
    probe_type: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @property
    def attitudes(self) -> list:
        """List of (pitch, roll) tuples with available tables."""
        return sorted(self.tables.keys())

    @property
    def pitch_values(self) -> np.ndarray:
        """Sorted unique pitch values across all tables."""
        return np.array(sorted(set(p for p, r in self.tables.keys())))

    @property
    def roll_values(self) -> np.ndarray:
        """Sorted unique roll values across all tables."""
        return np.array(sorted(set(r for p, r in self.tables.keys())))

    @property
    def n_attitudes(self) -> int:
        return len(self.tables)

    def get_table(self, pitch_deg: float, roll_deg: float) -> Optional[HVTable]:
        """Look up the table at an exact attitude, or None if not found."""
        return self.tables.get((pitch_deg, roll_deg))

    @property
    def max_volume(self) -> float:
        """Maximum volume across all attitudes (useful for normalization)."""
        if not self.tables:
            return 0.0
        return max(t.max_volume for t in self.tables.values())


@dataclass
class TestRecord:
    """
    A single timestamped measurement from a calibration test.

    Attributes
    ----------
    time_s : float
        Timestamp in seconds from sequence start.
    pitch_deg : float
        Aircraft pitch at this reading.
    roll_deg : float
        Aircraft roll at this reading.
    indicated_weights : dict
        {tank_id: indicated_weight_lb} from the gauging system.
    indicated_volumes : dict
        {tank_id: indicated_volume_gal} from the gauging system.
    scale_weight_lb : float, optional
        Scale-measured gross weight (only at checkpoint times).
    dry_weight_lb : float, optional
        Aircraft dry weight (for computing fuel-only from scale).
    density_system : float, optional
        System-reported fuel density (lb/gal).
    metadata : dict
        Extra fields (phase, active_tanks, per-tank probe heights, etc.).
    """
    time_s: float
    pitch_deg: float
    roll_deg: float
    indicated_weights: dict = field(default_factory=dict)
    indicated_volumes: dict = field(default_factory=dict)
    scale_weight_lb: Optional[float] = None
    dry_weight_lb: Optional[float] = None
    density_system: Optional[float] = None
    metadata: dict = field(default_factory=dict)

    @property
    def total_indicated_weight(self) -> float:
        return sum(self.indicated_weights.values())

    @property
    def scale_fuel_weight(self) -> Optional[float]:
        """Fuel weight derived from scale reading minus dry weight."""
        if self.scale_weight_lb is not None and self.dry_weight_lb is not None:
            return self.scale_weight_lb - self.dry_weight_lb
        return None


@dataclass
class TestDataset:
    """
    A collection of test records from a calibration sequence.

    Attributes
    ----------
    records : list of TestRecord
        Time-ordered measurement records.
    sequence_type : str
        "defuel", "refuel", or "level_check".
    tank_ids : list of str
        Tank IDs present in this dataset.
    metadata : dict
        Sequence-level metadata (test date, aircraft, config, etc.).
    """
    records: list = field(default_factory=list)
    sequence_type: str = "unknown"
    tank_ids: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def n_records(self) -> int:
        return len(self.records)

    @property
    def time_range(self) -> tuple:
        """(start_time_s, end_time_s)."""
        if not self.records:
            return (0.0, 0.0)
        return (self.records[0].time_s, self.records[-1].time_s)

    @property
    def scale_checkpoints(self) -> list:
        """Records that have scale weight readings."""
        return [r for r in self.records if r.scale_weight_lb is not None]


@dataclass
class FuelSystemData:
    """
    Top-level container holding everything needed for analysis.

    Combines H-V table data for all tanks with optional test sequence data.

    Attributes
    ----------
    tanks : dict
        {tank_id: TankData} for all tanks in the system.
    test_data : list of TestDataset
        Calibration test sequences (defuel, refuel, etc.).
    config : dict
        System configuration (fuel properties, column maps, etc.).
    """
    tanks: dict = field(default_factory=dict)
    test_data: list = field(default_factory=list)
    config: dict = field(default_factory=dict)

    @property
    def tank_ids(self) -> list:
        """Sorted list of tank IDs."""
        return sorted(self.tanks.keys())

    @property
    def n_tanks(self) -> int:
        return len(self.tanks)

    def get_tank(self, tank_id: str) -> Optional[TankData]:
        return self.tanks.get(tank_id)
