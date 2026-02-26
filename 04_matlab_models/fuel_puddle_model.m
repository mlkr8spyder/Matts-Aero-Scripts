%% ========================================================================
%  SIMPLE FUEL PUDDLE — VAPOR CONCENTRATION & FLAMMABILITY
%  ========================================================================
%  Given a puddle of liquid fuel in a closed bay, computes the equilibrium
%  vapor-air mixture properties and flammability at a specified temperature
%  and altitude.
%
%  INPUTS:  Temperature, altitude, bay volume, liquid fuel volume
%  OUTPUTS: Volume fraction, mass fraction, mass concentration,
%           fuel-air ratio, flammability verdict, MIE check
%
%  Author:  Claude (Anthropic)
%  Date:    2026-02-23
%  ========================================================================

clear; clc; close all;

%% ======================= USER INPUTS ====================================

T_C       = 40;          % Bay temperature [°C]
alt_ft    = 35000;       % Altitude [ft]
V_bay_L   = 200;         % Total bay volume [liters]
V_fuel_mL = 500;         % Liquid fuel volume [mL]

% — Spark source —
E_spark_mJ = 0.25;       % Credible spark energy [mJ]

% — Flammability limits at sea level (volume %) —
LEL_vol_pct_SL = 0.6;
UEL_vol_pct_SL = 4.7;

% — Fuel molecular properties —
M_fuel = 0.167;          % Molar mass [kg/mol]  (Jet-A ~ C12H23)
M_air  = 0.02897;        % Molar mass of air [kg/mol]

%% ============ FUEL PROPERTY FUNCTIONS (USER-DEFINED) ====================
%  Replace these with your own correlations.  T is in [K].

% True Vapor Pressure [Pa]
P_vap = @(T) exp(22.30 - 5765 ./ (T - 27.0));

% Liquid fuel density [kg/m^3]
rho_fuel_liq = @(T) 840 - 0.68 * (T - 273.15);

%% ======================= CONSTANTS ======================================

R_u    = 8.314;          % Universal gas constant [J/(mol*K)]
g      = 9.80665;        % [m/s^2]
P0     = 101325;         % Sea-level pressure [Pa]
T0_std = 288.15;         % Sea-level std temperature [K]
L_rate = 0.0065;         % Lapse rate [K/m]

%% ======================= UNIT CONVERSIONS ===============================

T       = T_C + 273.15;                    % [K]
alt     = alt_ft / 3.28084;                % [m]
V_bay   = V_bay_L * 1e-3;                  % [m^3]
V_fuel  = V_fuel_mL * 1e-6;               % [m^3]

%% ======================= CALCULATIONS ===================================

% — Ambient pressure at altitude —
P_amb = P0 * (1 - L_rate * alt / T0_std)^(g / (287.058 * L_rate));

% — Vapor pressure —
Pv = P_vap(T);

% — Mass-balance iteration —
%     Some liquid evaporates into the ullage, reducing liquid volume.
%     Iterate to find the equilibrium split.
%
%     Total fuel mass is conserved:
%       m_total = rho_liq * V_fuel_init
%       m_total = rho_liq * V_liq + (Pv * M_fuel)/(R_u * T) * V_gas
%       V_gas   = V_bay - V_liq

rho_liq  = rho_fuel_liq(T);
m_total  = rho_liq * V_fuel;       % total fuel mass [kg]
C_sat    = (Pv * M_fuel) / (R_u * T);  % saturation vapor density [kg/m^3]

V_liq = V_fuel;  % initial guess
all_evaporated = false;
for iter = 1:200
V_gas   = V_bay - V_liq;
m_vap   = C_sat * V_gas;
m_liq   = m_total - m_vap;

```
if m_liq <= 0
    % All fuel evaporated — vapor is sub-saturated
    all_evaporated = true;
    V_liq = 0;
    V_gas = V_bay;
    % Actual vapor pressure is less than saturation
    m_vap = m_total;
    break;
end

V_liq_new = m_liq / rho_liq;
if abs(V_liq_new - V_liq) < 1e-14
    break;
end
V_liq = V_liq_new;
```

end

% — Vapor partial pressure —
if all_evaporated
% Sub-saturated: back-calculate actual partial pressure
Pv_actual = (m_vap / M_fuel) * R_u * T / V_gas;
else
Pv_actual = Pv;
end

% Clamp: vapor pressure cannot exceed ambient
Pv_actual = min(Pv_actual, P_amb);

% — Mole / volume fraction —
X_fuel = Pv_actual / P_amb;

% — Mass fraction —
Y_fuel = (X_fuel * M_fuel) / (X_fuel * M_fuel + (1 - X_fuel) * M_air);

% — Mass concentration [kg/m^3] —
rho_vap = (Pv_actual * M_fuel) / (R_u * T);

% — Fuel-to-air ratio —
FAR = (X_fuel * M_fuel) / ((1 - X_fuel) * M_air);

% — Altitude-corrected flammability limits —
LEL_alt = LEL_vol_pct_SL / 100 * P0 / P_amb;   % vol fraction
UEL_alt = UEL_vol_pct_SL / 100 * P0 / P_amb;

% — Flammability verdict —
if X_fuel >= LEL_alt && X_fuel <= UEL_alt
flam_str = ‘YES — FLAMMABLE’;
elseif X_fuel < LEL_alt
flam_str = ‘No — below LEL (too lean)’;
else
flam_str = ‘No — above UEL (too rich)’;
end

% — MIE estimate —
x_stoich   = 0.0118;     % stoich vol fraction for C12H23
MIE_min_mJ = 0.25;       % MIE at stoichiometric [mJ]

if X_fuel >= LEL_alt && X_fuel <= UEL_alt
k_mie = log10(100) / (x_stoich - LEL_alt)^2;
MIE   = 10^(log10(MIE_min_mJ) + k_mie * (X_fuel - x_stoich)^2);
else
MIE = Inf;
end

if isfinite(MIE) && E_spark_mJ >= MIE
ign_str = ‘YES — spark can ignite’;
elseif isfinite(MIE)
ign_str = sprintf(‘No — need >= %.3f mJ’, MIE);
else
ign_str = ‘N/A — mixture not flammable’;
end

%% ======================= PRINT RESULTS ==================================

fprintf(’================================================\n’);
fprintf(’  FUEL PUDDLE EQUILIBRIUM — RESULTS\n’);
fprintf(’================================================\n’);
fprintf(’  INPUTS\n’);
fprintf(’    Temperature       : %.1f °C\n’, T_C);
fprintf(’    Altitude          : %.0f ft\n’, alt_ft);
fprintf(’    Bay volume        : %.1f L\n’, V_bay_L);
fprintf(’    Fuel volume (init): %.1f mL\n’, V_fuel_mL);
fprintf(’————————————————\n’);
fprintf(’  ATMOSPHERE\n’);
fprintf(’    Ambient pressure  : %.0f Pa  (%.2f psi)\n’, P_amb, P_amb/6894.76);
fprintf(’    Vapor pressure    : %.2f Pa\n’, Pv);
if all_evaporated
fprintf(’    *** All liquid evaporated — sub-saturated ***\n’);
fprintf(’    Actual Pv in bay  : %.2f Pa\n’, Pv_actual);
end
fprintf(’————————————————\n’);
fprintf(’  LIQUID POOL\n’);
fprintf(’    Initial volume    : %.2f mL\n’, V_fuel_mL);
fprintf(’    Final volume      : %.2f mL\n’, V_liq*1e6);
fprintf(’    Evaporated        : %.4f mL  (%.4f g)\n’, …
(V_fuel - V_liq)*1e6, m_vap*1000);
fprintf(’    Liquid remaining  : %.2f g\n’, max(m_total - m_vap,0)*1000);
fprintf(’————————————————\n’);
fprintf(’  VAPOR-AIR MIXTURE\n’);
fprintf(’    Volume fraction   : %.4f %%\n’, X_fuel*100);
fprintf(’    Mass fraction     : %.4f %%\n’, Y_fuel*100);
fprintf(’    Vapor density     : %.4f g/m^3\n’, rho_vap*1000);
fprintf(’    Fuel-air ratio    : %.6f kg/kg\n’, FAR);
fprintf(’————————————————\n’);
fprintf(’  FLAMMABILITY\n’);
fprintf(’    LEL (alt-corr)    : %.4f %%\n’, LEL_alt*100);
fprintf(’    UEL (alt-corr)    : %.4f %%\n’, UEL_alt*100);
fprintf(’    Flammable?        : %s\n’, flam_str);
if X_fuel < LEL_alt
fprintf(’    Margin to LEL     : %.4f %%  (%.1fx below)\n’, …
(LEL_alt - X_fuel)*100, LEL_alt/max(X_fuel,eps));
end
fprintf(’————————————————\n’);
fprintf(’  IGNITION\n’);
fprintf(’    MIE at this conc  : %.3f mJ\n’, MIE);
fprintf(’    Spark energy      : %.3f mJ\n’, E_spark_mJ);
fprintf(’    Ignitable?        : %s\n’, ign_str);
fprintf(’================================================\n’);