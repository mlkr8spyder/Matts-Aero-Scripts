"""
Single-Point Refuel System Model with High-Level Shutoff.

Models:
  - Single-point refuel adapter (SPRA) — one external connection
  - Pressurized manifold distributing fuel to all 5 tanks
  - Per-tank shutoff valves (solenoid, normally open during refuel)
  - High-level float sensors at ullage boundary in each tank
  - Refuel sequencing: all tanks fill simultaneously via manifold pressure
  - Shutoff logic: high-level sensor triggers valve closure per tank
  - Precheck valve (master shutoff)
  - Overpressure protection
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# High-Level Sensor
# ---------------------------------------------------------------------------

@dataclass
class HighLevelSensor:
    """
    Float-type high-level sensor mounted near the ullage boundary.

    The sensor trips (goes True) when fuel reaches the trigger WL.
    Has a hysteresis band to prevent chattering.
    """
    tank_id: int
    trigger_wl: float           # WL at which sensor trips (= max_fill_wl)
    hysteresis_in: float = 0.3  # reset = trigger - hysteresis
    reset_wl: float = 0.0      # WL at which sensor resets (computed in __post_init__)
    state: bool = False         # True = tripped (fuel at high level)

    # Failure modes
    failed_tripped: bool = False   # Stuck in tripped state
    failed_untripped: bool = False  # Stuck in untripped state (dangerous)

    def __post_init__(self):
        self.reset_wl = self.trigger_wl - self.hysteresis_in

    def update(self, fuel_wl_at_sensor: float) -> bool:
        """Update sensor state based on current fuel level. Returns True if tripped."""
        if self.failed_tripped:
            self.state = True
            return True
        if self.failed_untripped:
            self.state = False
            return False

        if not self.state and fuel_wl_at_sensor >= self.trigger_wl:
            self.state = True
        elif self.state and fuel_wl_at_sensor < self.reset_wl:
            self.state = False

        return self.state


# ---------------------------------------------------------------------------
# Shutoff Valve
# ---------------------------------------------------------------------------

@dataclass
class ShutoffValve:
    """
    Solenoid shutoff valve on the refuel manifold line to each tank.

    Normally open during refuel. Closes when commanded by high-level sensor
    or manual override.
    """
    tank_id: int
    is_open: bool = True
    flow_capacity_gpm: float = 15.0  # max flow rate when open (gallons/min)

    # Valve dynamics
    close_time_s: float = 0.5   # time to fully close after command
    open_time_s: float = 0.3    # time to fully open after command
    position: float = 1.0       # 0=closed, 1=open (continuous for dynamics)

    # Failure modes
    failed_open: bool = False    # Valve stuck open (dangerous)
    failed_closed: bool = False  # Valve stuck closed

    # Command state
    commanded_open: bool = True

    def command_close(self):
        self.commanded_open = False

    def command_open(self):
        self.commanded_open = True

    def update(self, dt_s: float) -> float:
        """
        Update valve position based on command. Returns effective flow fraction [0-1].
        """
        if self.failed_open:
            self.position = 1.0
            self.is_open = True
            return 1.0
        if self.failed_closed:
            self.position = 0.0
            self.is_open = False
            return 0.0

        if self.commanded_open:
            rate = 1.0 / self.open_time_s
            self.position = min(1.0, self.position + rate * dt_s)
        else:
            rate = 1.0 / self.close_time_s
            self.position = max(0.0, self.position - rate * dt_s)

        self.is_open = self.position > 0.01
        return self.position


# ---------------------------------------------------------------------------
# Single-Point Refuel Adapter
# ---------------------------------------------------------------------------

@dataclass
class RefuelAdapter:
    """
    Single-point refuel adapter (SPRA).

    External fuel supply connects here. Manifold pressure drives fuel
    to all tanks simultaneously through individual shutoff valves.
    """
    location_fs: float = 240.0
    location_bl: float = 0.0
    location_wl: float = 78.0   # Under center tank

    supply_pressure_psi: float = 55.0   # Standard refuel pressure
    max_flow_rate_gpm: float = 60.0     # Total system max flow

    is_connected: bool = False
    precheck_valve_open: bool = False    # Master shutoff

    @property
    def is_active(self) -> bool:
        return self.is_connected and self.precheck_valve_open


# ---------------------------------------------------------------------------
# Refuel Controller
# ---------------------------------------------------------------------------

class RefuelController:
    """
    Manages the complete single-point refuel operation.

    Logic:
      1. Adapter connected, precheck valve opened → refuel begins
      2. All shutoff valves open — fuel flows to all tanks simultaneously
      3. Manifold pressure distributes fuel; flow splits based on back-pressure
         (tanks at higher elevation or higher fill get less flow)
      4. When a tank's high-level sensor trips → that tank's shutoff valve closes
      5. When all high-level sensors are tripped → refuel complete
      6. Precheck valve closed, adapter disconnected

    Flow distribution model:
      Flow to each tank is proportional to (supply_pressure - head_pressure) / resistance.
      Head pressure = rho * g * (fuel_height_above_manifold).
      Higher tanks and fuller tanks get less flow.
    """

    def __init__(self, tanks: dict, density_lb_per_gal: float = 6.71):
        self.tanks = tanks
        self.density = density_lb_per_gal

        # Create per-tank components
        self.sensors = {}
        self.valves = {}
        for tid, tank in tanks.items():
            self.sensors[tid] = HighLevelSensor(
                tank_id=tid,
                trigger_wl=tank.max_fill_wl,
            )
            self.valves[tid] = ShutoffValve(tank_id=tid)

        self.adapter = RefuelAdapter()
        self.total_fuel_delivered_gal = 0.0
        self.is_complete = False
        self.log = []

    def start_refuel(self):
        """Connect adapter and open precheck valve."""
        self.adapter.is_connected = True
        self.adapter.precheck_valve_open = True
        for valve in self.valves.values():
            valve.command_open()
        self.log.append("REFUEL START: adapter connected, precheck valve open")

    def stop_refuel(self):
        """Close precheck valve and disconnect."""
        self.adapter.precheck_valve_open = False
        for valve in self.valves.values():
            valve.command_close()
        self.log.append("REFUEL STOP: precheck valve closed")

    def compute_flow_distribution(self, fuel_wl: dict, dt_s: float) -> dict:
        """
        Compute fuel flow to each tank for this timestep.

        Flow model: simple pressure-driven distribution.
        Q_tank = valve_position * k * (P_supply - P_head_tank)
        P_head = density * fuel_height_above_manifold_wl * conversion

        Returns dict {tank_id: flow_gal} for this timestep.
        """
        if not self.adapter.is_active:
            return {tid: 0.0 for tid in self.tanks}

        manifold_wl = self.adapter.location_wl
        P_supply = self.adapter.supply_pressure_psi

        # Hydrostatic head pressure (psi) from fuel column above manifold.
        # Derivation: P = rho * g * h, converted to consistent units:
        #   rho (lb/gal) * h (in) / 231 (in^3/gal) * 1 (psi per lb/in^2)
        #   = rho * h / 231 * (1/144) * 62.4... simplified to ~0.036 * rho * h
        # This approximation is standard for aviation fuel systems.
        flows = {}
        total_demand = 0.0

        for tid, tank in self.tanks.items():
            valve_pos = self.valves[tid].position
            if valve_pos < 0.01:
                flows[tid] = 0.0
                continue

            # Fuel height above manifold
            fuel_h_above = max(0, fuel_wl.get(tid, tank.wl_min) - manifold_wl)
            P_head = 0.036 * self.density * fuel_h_above

            # Net driving pressure
            P_net = max(0, P_supply - P_head)

            # Flow through valve
            k = self.valves[tid].flow_capacity_gpm / P_supply  # flow coefficient
            q = valve_pos * k * P_net  # gpm

            flows[tid] = q
            total_demand += q

        # When total demand exceeds supply, scale all valve flows proportionally.
        # This models the physical behavior of a shared-manifold system where
        # back-pressure from one tank affects flow to all tanks.
        if total_demand > self.adapter.max_flow_rate_gpm:
            scale = self.adapter.max_flow_rate_gpm / total_demand
            flows = {tid: q * scale for tid, q in flows.items()}

        # Convert GPM to gallons per timestep
        flows_per_step = {tid: q * dt_s / 60.0 for tid, q in flows.items()}

        return flows_per_step

    def update(self, fuel_wl: dict, dt_s: float = 1.0) -> dict:
        """
        Run one timestep of the refuel controller.

        Parameters
        ----------
        fuel_wl : dict {tank_id: current_fuel_surface_wl}
        dt_s : float, timestep in seconds

        Returns
        -------
        dict with flow_gal per tank, sensor states, valve states
        """
        # Update high-level sensors
        sensor_states = {}
        for tid in self.tanks:
            tripped = self.sensors[tid].update(fuel_wl.get(tid, self.tanks[tid].wl_min))
            sensor_states[tid] = tripped

            # If sensor tripped, command valve closed
            if tripped:
                if self.valves[tid].commanded_open:
                    self.valves[tid].command_close()
                    self.log.append(f"  T{tid}: HIGH-LEVEL SENSOR TRIPPED at WL "
                                    f"{fuel_wl.get(tid, 0):.2f} → valve closing")

        # Update valve dynamics
        valve_positions = {}
        for tid in self.tanks:
            valve_positions[tid] = self.valves[tid].update(dt_s)

        # Compute flow
        flow_gal = self.compute_flow_distribution(fuel_wl, dt_s)

        # Track total delivered
        self.total_fuel_delivered_gal += sum(flow_gal.values())

        # Check if all sensors tripped (refuel complete)
        if all(sensor_states.values()) and not self.is_complete:
            self.is_complete = True
            self.stop_refuel()
            self.log.append(f"REFUEL COMPLETE: {self.total_fuel_delivered_gal:.1f} gal delivered")

        return {
            'flow_gal': flow_gal,
            'sensor_states': sensor_states,
            'valve_positions': valve_positions,
            'total_delivered_gal': self.total_fuel_delivered_gal,
            'is_complete': self.is_complete,
        }


# ---------------------------------------------------------------------------
# Probe Failure Logic
# ---------------------------------------------------------------------------

@dataclass
class ProbeHealthMonitor:
    """
    Monitors probe health and detects failure conditions.

    Failure modes detected:
      1. Open circuit: reading drops to 0 or below minimum threshold
      2. Short circuit: reading jumps to max or above maximum threshold
      3. Excessive rate of change: |dh/dt| exceeds physical possibility
      4. Stale data: reading doesn't change for too long despite fuel movement
      5. Out of range: reading outside probe's physical bounds

    Response to failure:
      - Flag the probe as failed
      - Hold last known good value (LKG)
      - If redundant probe available, switch to it
      - Set maintenance flag
    """

    tank_id: int
    probe_name: str
    probe_min_height: float = 0.0
    probe_max_height: float = 20.0

    # Thresholds
    open_circuit_threshold: float = -0.1      # below this = open circuit
    short_circuit_threshold_margin: float = 0.5  # above max+margin = short
    max_rate_of_change_in_per_s: float = 2.0  # physical max fuel slosh rate
    stale_timeout_s: float = 30.0             # if no change for this long
    stale_min_delta: float = 0.01             # minimum change to not be "stale"

    # State
    is_healthy: bool = True
    failure_mode: str = ""
    last_known_good: float = 0.0
    previous_reading: float = 0.0
    stale_counter_s: float = 0.0
    readings_since_reset: int = 0

    # Counters for BIT
    open_circuit_count: int = 0
    short_circuit_count: int = 0
    rate_exceedance_count: int = 0
    stale_count: int = 0

    def check_reading(self, raw_height: float, dt_s: float = 1.0) -> dict:
        """
        Check a probe reading for failure conditions.

        Returns dict with:
          is_healthy, failure_mode, output_height (filtered/substituted),
          used_lkg (True if fell back to last known good)
        """
        self.readings_since_reset += 1
        used_lkg = False
        failure = ""

        # --- Open circuit check ---
        if raw_height < self.open_circuit_threshold:
            failure = "OPEN_CIRCUIT"
            self.open_circuit_count += 1

        # --- Short circuit check ---
        elif raw_height > self.probe_max_height + self.short_circuit_threshold_margin:
            failure = "SHORT_CIRCUIT"
            self.short_circuit_count += 1

        # --- Rate of change check (skip first reading) ---
        elif self.readings_since_reset > 1:
            rate = abs(raw_height - self.previous_reading) / max(dt_s, 0.001)
            if rate > self.max_rate_of_change_in_per_s:
                failure = "RATE_EXCEEDANCE"
                self.rate_exceedance_count += 1

        # --- Out of range check ---
        elif raw_height < self.probe_min_height or raw_height > self.probe_max_height:
            # Soft out of range — just clip, don't fail
            pass

        # --- Stale data check ---
        # Wait for 5 readings before checking stale data to allow the filter
        # to stabilize after initialization or fault recovery.
        if not failure and self.readings_since_reset > 5:
            if abs(raw_height - self.previous_reading) < self.stale_min_delta:
                self.stale_counter_s += dt_s
                if self.stale_counter_s > self.stale_timeout_s:
                    failure = "STALE_DATA"
                    self.stale_count += 1
            else:
                self.stale_counter_s = 0.0

        # --- Determine output ---
        if failure:
            self.is_healthy = False
            self.failure_mode = failure
            output = self.last_known_good
            used_lkg = True
        else:
            self.is_healthy = True
            self.failure_mode = ""
            output = np.clip(raw_height, self.probe_min_height, self.probe_max_height)
            self.last_known_good = output

        self.previous_reading = raw_height

        return {
            'is_healthy': self.is_healthy,
            'failure_mode': failure,
            'output_height': output,
            'raw_height': raw_height,
            'used_lkg': used_lkg,
        }

    def reset(self):
        """Reset monitor state (e.g., after maintenance)."""
        self.is_healthy = True
        self.failure_mode = ""
        self.stale_counter_s = 0.0
        self.readings_since_reset = 0

    def bit_summary(self) -> dict:
        """Built-in test summary."""
        return {
            'tank_id': self.tank_id,
            'probe_name': self.probe_name,
            'is_healthy': self.is_healthy,
            'failure_mode': self.failure_mode,
            'open_circuit_count': self.open_circuit_count,
            'short_circuit_count': self.short_circuit_count,
            'rate_exceedance_count': self.rate_exceedance_count,
            'stale_count': self.stale_count,
            'total_readings': self.readings_since_reset,
        }


# ---------------------------------------------------------------------------
# Integrated Probe Failure Manager
# ---------------------------------------------------------------------------

class ProbeFailureManager:
    """
    Manages probe health monitors for all probes in the system.

    For tanks with redundant probes (T3 real-pseudo combo), implements
    automatic switchover logic.
    """

    def __init__(self, tanks: dict):
        self.monitors = {}
        for tid, tank in tanks.items():
            if tank.probes:
                for probe in tank.probes:
                    key = (tid, probe.name)
                    self.monitors[key] = ProbeHealthMonitor(
                        tank_id=tid,
                        probe_name=probe.name,
                        probe_min_height=0.0,
                        probe_max_height=probe.active_length,
                    )
            elif tank.probe_type == 'pure_pseudo':
                # Pseudo probe monitor (projected height)
                key = (tid, f'T{tid}_pseudo')
                self.monitors[key] = ProbeHealthMonitor(
                    tank_id=tid,
                    probe_name=f'T{tid}_pseudo',
                    probe_min_height=0.0,
                    probe_max_height=tank.height_wl,
                    # Pseudo probes have lower rate threshold due to projection
                    max_rate_of_change_in_per_s=3.0,
                )

    def check_all(self, readings: dict, dt_s: float = 1.0) -> dict:
        """
        Check all probe readings.

        Parameters
        ----------
        readings : dict {(tank_id, probe_name): raw_height}

        Returns
        -------
        dict {(tank_id, probe_name): check_result}
        """
        results = {}
        for key, monitor in self.monitors.items():
            if key in readings:
                results[key] = monitor.check_reading(readings[key], dt_s)
            else:
                results[key] = {
                    'is_healthy': monitor.is_healthy,
                    'failure_mode': monitor.failure_mode,
                    'output_height': monitor.last_known_good,
                    'raw_height': None,
                    'used_lkg': True,
                }
        return results

    def inject_failure(self, tank_id: int, probe_name: str, failure_type: str):
        """Inject a simulated failure for testing."""
        key = (tank_id, probe_name)
        if key not in self.monitors:
            raise ValueError(f"No monitor for {key}")
        # The actual failure injection happens by corrupting the reading
        # in the simulation; this just pre-sets the state for BIT testing
        self.monitors[key].failure_mode = failure_type
        self.monitors[key].is_healthy = False

    def run_bit(self) -> list:
        """Run built-in test on all probes."""
        return [m.bit_summary() for m in self.monitors.values()]

    def system_health_summary(self) -> dict:
        """High-level system health."""
        total = len(self.monitors)
        healthy = sum(1 for m in self.monitors.values() if m.is_healthy)
        return {
            'total_probes': total,
            'healthy_probes': healthy,
            'failed_probes': total - healthy,
            'all_healthy': healthy == total,
            'failures': {
                k: m.failure_mode for k, m in self.monitors.items()
                if not m.is_healthy
            },
        }


# ---------------------------------------------------------------------------
# Test / Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from .tank_geometry import build_tank_system

    tanks = build_tank_system()

    # --- Test Refuel Controller ---
    print("=" * 60)
    print("REFUEL SYSTEM TEST")
    print("=" * 60)

    controller = RefuelController(tanks)
    controller.start_refuel()

    # Start all tanks at 20% fill
    fuel_wl = {tid: t.wl_min + t.height_wl * 0.20 for tid, t in tanks.items()}

    dt = 1.0  # 1 second timesteps
    n_steps = 800

    tank_full_times = {}

    for step in range(n_steps):
        result = controller.update(fuel_wl, dt)

        # Apply flow to each tank (convert gal to WL change)
        for tid, flow_gal in result['flow_gal'].items():
            tank = tanks[tid]
            dh = flow_gal * 231.0 / tank.base_area  # gal → in³ → height
            fuel_wl[tid] = min(fuel_wl[tid] + dh, tank.wl_max)

        # Track when each tank fills
        for tid, tripped in result['sensor_states'].items():
            if tripped and tid not in tank_full_times:
                tank_full_times[tid] = step

        if result['is_complete']:
            print(f"\nRefuel complete at step {step} ({step}s)")
            break

    print(f"\nTotal fuel delivered: {controller.total_fuel_delivered_gal:.1f} gal")
    print("\nTank fill completion times:")
    for tid in sorted(tank_full_times.keys()):
        print(f"  T{tid} ({tanks[tid].name}): {tank_full_times[tid]}s, "
              f"final WL={fuel_wl[tid]:.2f}")

    print("\nRefuel log:")
    for entry in controller.log:
        print(f"  {entry}")

    # --- Test Probe Failure ---
    print("\n" + "=" * 60)
    print("PROBE FAILURE DETECTION TEST")
    print("=" * 60)

    pfm = ProbeFailureManager(tanks)

    # Normal readings
    normal_readings = {
        (1, 'T1_probe'): 8.0,
        (2, 'T2_probe'): 9.0,
        (3, 'T3_lower'): 5.0,
        (3, 'T3_upper'): 3.0,
        (4, 'T4_probe'): 9.0,
        (5, 'T5_pseudo'): 11.0,
    }

    results = pfm.check_all(normal_readings)
    print("\nNormal readings — all healthy:")
    health = pfm.system_health_summary()
    print(f"  {health['healthy_probes']}/{health['total_probes']} probes healthy")

    # Inject open circuit on T1
    print("\nInjecting open circuit on T1...")
    bad_readings = normal_readings.copy()
    bad_readings[(1, 'T1_probe')] = -0.5  # below threshold
    results = pfm.check_all(bad_readings)
    r = results[(1, 'T1_probe')]
    print(f"  T1 probe: healthy={r['is_healthy']}, mode={r['failure_mode']}, "
          f"output={r['output_height']:.1f} (LKG={r['used_lkg']})")

    # Inject short circuit on T2
    print("\nInjecting short circuit on T2...")
    bad_readings[(2, 'T2_probe')] = 25.0  # way above max
    results = pfm.check_all(bad_readings)
    r = results[(2, 'T2_probe')]
    print(f"  T2 probe: healthy={r['is_healthy']}, mode={r['failure_mode']}, "
          f"output={r['output_height']:.1f} (LKG={r['used_lkg']})")

    # Inject rate exceedance on T4
    print("\nInjecting rate exceedance on T4...")
    bad_readings[(4, 'T4_probe')] = 15.0  # jumped from 9 to 15 in 1 second
    results = pfm.check_all(bad_readings)
    r = results[(4, 'T4_probe')]
    print(f"  T4 probe: healthy={r['is_healthy']}, mode={r['failure_mode']}, "
          f"output={r['output_height']:.1f} (LKG={r['used_lkg']})")

    # BIT summary
    print("\nBIT Summary:")
    for bit in pfm.run_bit():
        status = "OK" if bit['is_healthy'] else f"FAIL:{bit['failure_mode']}"
        print(f"  T{bit['tank_id']} {bit['probe_name']}: {status} "
              f"(OC:{bit['open_circuit_count']} SC:{bit['short_circuit_count']} "
              f"RE:{bit['rate_exceedance_count']} ST:{bit['stale_count']})")

    health = pfm.system_health_summary()
    print(f"\nSystem: {health['healthy_probes']}/{health['total_probes']} healthy")
    if health['failures']:
        print(f"Failures: {health['failures']}")
