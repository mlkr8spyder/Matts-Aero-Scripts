"""
Tests for refuel system, high-level sensors, shutoff valves, and probe failure detection.
"""

import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tank_geometry import build_tank_system
from src.refuel_system import (
    HighLevelSensor, ShutoffValve, RefuelAdapter, RefuelController,
    ProbeHealthMonitor, ProbeFailureManager,
)


def test_high_level_sensor_basic():
    """Sensor should trip when fuel reaches trigger WL and reset below."""
    sensor = HighLevelSensor(tank_id=1, trigger_wl=103.68)

    assert not sensor.update(100.0), "Should not trip at WL 100"
    assert not sensor.update(103.0), "Should not trip at WL 103"
    assert sensor.update(103.68), "Should trip at WL 103.68"
    assert sensor.update(103.5), "Should stay tripped (above reset)"
    assert not sensor.update(103.0), "Should reset below 103.38"

    print("PASS: test_high_level_sensor_basic")


def test_high_level_sensor_hysteresis():
    """Hysteresis should prevent chattering near the trigger point."""
    sensor = HighLevelSensor(tank_id=1, trigger_wl=100.0, hysteresis_in=0.5)

    sensor.update(100.0)  # Trip
    assert sensor.state is True

    # Should NOT reset at 99.6 (within hysteresis band)
    sensor.update(99.6)
    assert sensor.state is True, "Should not reset within hysteresis band"

    # Should reset at 99.4 (below reset_wl = 99.5)
    sensor.update(99.4)
    assert sensor.state is False, "Should reset below reset WL"

    print("PASS: test_high_level_sensor_hysteresis")


def test_high_level_sensor_failure_modes():
    """Test stuck-tripped and stuck-untripped failure modes."""
    # Stuck tripped
    s1 = HighLevelSensor(tank_id=1, trigger_wl=100.0, failed_tripped=True)
    assert s1.update(50.0) is True, "Stuck tripped should always return True"

    # Stuck untripped (dangerous condition)
    s2 = HighLevelSensor(tank_id=1, trigger_wl=100.0, failed_untripped=True)
    assert s2.update(150.0) is False, "Stuck untripped should always return False"

    print("PASS: test_high_level_sensor_failure_modes")


def test_shutoff_valve_dynamics():
    """Valve should close gradually over close_time_s."""
    valve = ShutoffValve(tank_id=1, close_time_s=0.5, open_time_s=0.3)

    assert valve.position == 1.0, "Should start fully open"
    valve.command_close()

    # After 0.25s, should be at ~50%
    pos = valve.update(0.25)
    assert 0.4 < pos < 0.6, f"Position should be ~0.5, got {pos}"

    # After another 0.25s, should be fully closed
    pos = valve.update(0.25)
    assert pos < 0.01, f"Should be closed, got {pos}"

    # Reopen
    valve.command_open()
    pos = valve.update(0.3)
    assert pos > 0.9, f"Should be nearly open, got {pos}"

    print("PASS: test_shutoff_valve_dynamics")


def test_shutoff_valve_failure_modes():
    """Test stuck-open and stuck-closed failures."""
    v1 = ShutoffValve(tank_id=1, failed_open=True)
    v1.command_close()
    assert v1.update(10.0) == 1.0, "Stuck open should stay at 1.0"

    v2 = ShutoffValve(tank_id=1, failed_closed=True)
    v2.command_open()
    assert v2.update(10.0) == 0.0, "Stuck closed should stay at 0.0"

    print("PASS: test_shutoff_valve_failure_modes")


def test_refuel_controller_fills_all_tanks():
    """Full refuel should fill all tanks and trigger all high-level sensors."""
    tanks = build_tank_system()
    controller = RefuelController(tanks)
    controller.start_refuel()

    fuel_wl = {tid: t.wl_min + t.height_wl * 0.10 for tid, t in tanks.items()}

    for step in range(1000):
        result = controller.update(fuel_wl, dt_s=1.0)

        for tid, flow_gal in result['flow_gal'].items():
            tank = tanks[tid]
            dh = flow_gal * 231.0 / tank.base_area
            fuel_wl[tid] = min(fuel_wl[tid] + dh, tank.wl_max)

        if result['is_complete']:
            break

    assert result['is_complete'], "Refuel should complete within 1000 steps"
    assert all(result['sensor_states'].values()), "All sensors should be tripped"
    assert result['total_delivered_gal'] > 400, "Should have delivered > 400 gal"

    print(f"PASS: test_refuel_controller_fills_all_tanks "
          f"(complete at step {step}, {result['total_delivered_gal']:.1f} gal)")


def test_refuel_order():
    """Tanks should fill in order: highest head advantage first."""
    tanks = build_tank_system()
    controller = RefuelController(tanks)
    controller.start_refuel()

    fuel_wl = {tid: t.wl_min + t.height_wl * 0.10 for tid, t in tanks.items()}
    fill_times = {}

    for step in range(1000):
        result = controller.update(fuel_wl, dt_s=1.0)
        for tid, flow_gal in result['flow_gal'].items():
            dh = flow_gal * 231.0 / tanks[tid].base_area
            fuel_wl[tid] = min(fuel_wl[tid] + dh, tanks[tid].wl_max)

        for tid, tripped in result['sensor_states'].items():
            if tripped and tid not in fill_times:
                fill_times[tid] = step

        if result['is_complete']:
            break

    # T1 (highest head) should fill first
    assert fill_times[1] < fill_times[3], \
        f"T1 ({fill_times[1]}s) should fill before T3 ({fill_times[3]}s)"

    # T2 and T4 (symmetric) should fill at similar times
    assert abs(fill_times[2] - fill_times[4]) < 5, \
        f"T2 ({fill_times[2]}s) and T4 ({fill_times[4]}s) should fill at similar times"

    print(f"PASS: test_refuel_order (fill order: {sorted(fill_times.items(), key=lambda x: x[1])})")


def test_probe_health_open_circuit():
    """Open circuit: reading below threshold should trigger failure."""
    mon = ProbeHealthMonitor(tank_id=1, probe_name='test', probe_max_height=15.0)
    mon.check_reading(8.0)  # Normal first reading

    result = mon.check_reading(-0.5)  # Open circuit
    assert not result['is_healthy']
    assert result['failure_mode'] == 'OPEN_CIRCUIT'
    assert result['output_height'] == 8.0  # Should use LKG
    assert result['used_lkg'] is True

    print("PASS: test_probe_health_open_circuit")


def test_probe_health_short_circuit():
    """Short circuit: reading above max + margin should trigger failure."""
    mon = ProbeHealthMonitor(tank_id=1, probe_name='test', probe_max_height=15.0)
    mon.check_reading(8.0)

    result = mon.check_reading(16.0)  # Short circuit (> 15.0 + 0.5)
    assert not result['is_healthy']
    assert result['failure_mode'] == 'SHORT_CIRCUIT'
    assert result['output_height'] == 8.0

    print("PASS: test_probe_health_short_circuit")


def test_probe_health_rate_exceedance():
    """Rate check: sudden jump should trigger failure."""
    mon = ProbeHealthMonitor(tank_id=1, probe_name='test', probe_max_height=15.0)
    mon.check_reading(5.0, dt_s=1.0)

    result = mon.check_reading(10.0, dt_s=1.0)  # 5"/s > 2"/s threshold
    assert not result['is_healthy']
    assert result['failure_mode'] == 'RATE_EXCEEDANCE'

    print("PASS: test_probe_health_rate_exceedance")


def test_probe_health_normal_operation():
    """Normal slow changes should not trigger any failures."""
    mon = ProbeHealthMonitor(tank_id=1, probe_name='test', probe_max_height=15.0)

    for h in np.linspace(0, 14, 100):
        result = mon.check_reading(h, dt_s=1.0)
        assert result['is_healthy'], f"Should be healthy at h={h:.1f}"
        assert not result['used_lkg']

    print("PASS: test_probe_health_normal_operation")


def test_probe_failure_manager_system():
    """ProbeFailureManager should track all probes and report system health."""
    tanks = build_tank_system()
    pfm = ProbeFailureManager(tanks)

    # Normal readings
    readings = {
        (1, 'T1_probe'): 8.0,
        (2, 'T2_probe'): 9.0,
        (3, 'T3_lower'): 5.0,
        (3, 'T3_upper'): 3.0,
        (4, 'T4_probe'): 9.0,
        (5, 'T5_pseudo'): 11.0,
    }
    pfm.check_all(readings)
    health = pfm.system_health_summary()
    assert health['all_healthy'], "All probes should be healthy"
    assert health['total_probes'] == 6, f"Should have 6 probes, got {health['total_probes']}"

    # Inject failure
    readings[(1, 'T1_probe')] = -0.5  # Open circuit
    pfm.check_all(readings)
    health = pfm.system_health_summary()
    assert not health['all_healthy']
    assert health['failed_probes'] == 1

    print("PASS: test_probe_failure_manager_system")


def test_probe_bit():
    """BIT should return correct counters for each failure type."""
    tanks = build_tank_system()
    pfm = ProbeFailureManager(tanks)

    readings = {
        (1, 'T1_probe'): 8.0,
        (2, 'T2_probe'): 9.0,
        (3, 'T3_lower'): 5.0,
        (3, 'T3_upper'): 3.0,
        (4, 'T4_probe'): 9.0,
        (5, 'T5_pseudo'): 11.0,
    }
    pfm.check_all(readings)

    # Two open circuits on T1
    readings[(1, 'T1_probe')] = -0.5
    pfm.check_all(readings)
    pfm.check_all(readings)

    bit = pfm.run_bit()
    t1_bit = [b for b in bit if b['probe_name'] == 'T1_probe'][0]
    assert t1_bit['open_circuit_count'] >= 2, \
        f"Should have >= 2 open circuit events, got {t1_bit['open_circuit_count']}"

    print("PASS: test_probe_bit")


if __name__ == "__main__":
    tests = [
        test_high_level_sensor_basic,
        test_high_level_sensor_hysteresis,
        test_high_level_sensor_failure_modes,
        test_shutoff_valve_dynamics,
        test_shutoff_valve_failure_modes,
        test_refuel_controller_fills_all_tanks,
        test_refuel_order,
        test_probe_health_open_circuit,
        test_probe_health_short_circuit,
        test_probe_health_rate_exceedance,
        test_probe_health_normal_operation,
        test_probe_failure_manager_system,
        test_probe_bit,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
