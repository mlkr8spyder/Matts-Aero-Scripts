import cantera as ct
import numpy as np
import matplotlib.pyplot as plt

# =============== PARAMETERS ================
mechanism = 'nDodecane_Reitz.yaml'  # Or another mechanism if needed
fuel = 'C10H22'
phi = 1.0                # Stoichiometric mixture
volume = 1e-3            # Reactor volume in m^3 (1 liter)

# Spark energies to test (in Joules)
spark_energies = np.linspace(1, 100, 10)  # 1 to 100 J, 10 points

# Initial temperatures (K)
temperatures = [250, 300, 350]  # Example: cold to warm

# Altitudes and corresponding initial pressures (Pa)
# 0 m (sea level), 5,000 m, 10,000 m
altitudes = [0, 5000, 10000]  # in meters
pressures = [101325, 54019, 26436]  # Standard atmospheric pressures at those altitudes (approximate)

# =============== SIMULATION ================
results = []

for T in temperatures:
    for P, altitude in zip(pressures, altitudes):
        for spark in spark_energies:
            # Set up the gas object
            gas = ct.Solution(mechanism)
            gas.set_equivalence_ratio(phi, fuel, 'O2:1, N2:3.76')
            gas.TP = T, P
            
            # Create the constant-volume reactor
            reactor = ct.IdealGasReactor(gas)
            reactor.volume = volume

            # Save initial pressure for later
            P_initial = reactor.thermo.P

            # --- SPARK: Add energy to the mixture ---
            # Add spark energy (J) as internal energy
            mass = reactor.thermo.mass  # kg
            delta_u = spark / mass      # J/kg
            # Raise internal energy by increasing T accordingly
            cv = reactor.thermo.cv_mass # J/kg-K
            T_new = reactor.T + delta_u / cv
            reactor.thermo.TP = T_new, reactor.thermo.P

            # --- Simulate the reactor for up to 20 ms or until ignition ---
            sim = ct.ReactorNet([reactor])
            time = 0.0
            dt = 1e-5
            t_end = 0.02  # 20 ms

            max_pressure = reactor.thermo.P
            while time < t_end:
                time = sim.step()
                max_pressure = max(max_pressure, reactor.thermo.P)
                # Optional: break early if you see a huge pressure rise (ignition)
                if reactor.T > T + 400:  # crude ignition test (ΔT > 400K)
                    break

            overpressure = max_pressure - P_initial
            results.append({
                'T': T,
                'altitude': altitude,
                'P_init': P,
                'spark_energy': spark,
                'overpressure': overpressure,
                'ignited': reactor.T > T + 400
            })
            print(f"T={T}K, Alt={altitude}m, P0={P/1000:.1f}kPa, Spark={spark:.1f}J -> Overpressure={overpressure/1000:.1f}kPa, Ignited={reactor.T > T + 400}")

# =============== POST-PROCESSING ================

import pandas as pd
df = pd.DataFrame(results)

# Plot an example: Overpressure vs Spark Energy at one T and altitude
for T in temperatures:
    for altitude in altitudes:
        subset = df[(df['T'] == T) & (df['altitude'] == altitude)]
        if len(subset) > 0:
            plt.plot(subset['spark_energy'], subset['overpressure']/1000, label=f"{T}K, {altitude}m")

plt.xlabel('Spark Energy [J]')
plt.ylabel('Overpressure [kPa]')
plt.legend()
plt.title('Overpressure vs Spark Energy\n(n-decane/air, constant volume)')
plt.show()