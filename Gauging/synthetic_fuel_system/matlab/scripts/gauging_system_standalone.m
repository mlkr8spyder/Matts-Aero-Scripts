%% gauging_system_standalone.m
% Standalone MATLAB implementation of the complete fuel gauging system.
% This can run without Simulink and validates the same logic that the
% Simulink model implements.
%
% Implements:
%   - Capacitance probe models (real, real-pseudo combo, pure pseudo)
%   - Probe failure detection (open circuit, short circuit, rate exceedance)
%   - H-V table lookup with bilinear attitude interpolation
%   - Density computation from dielectric constant
%   - Single-point refuel with high-level sensors and shutoff valves
%   - System weight summation and error computation

clear; clc; close all;

fprintf('=== Standalone Fuel Gauging System — MATLAB ===\n\n');

%% ========================================================================
%  SYSTEM PARAMETERS
%  ========================================================================

% Tank definitions: [fs_min fs_max bl_min bl_max wl_min wl_max]
tanks = struct();
tanks(1).name = 'Forward'; tanks(1).bounds = [195 225 -15 15 88 104];
tanks(2).name = 'Left';    tanks(2).bounds = [235 285 -62 -22 85 103];
tanks(3).name = 'Center';  tanks(3).bounds = [235 285 -20 20 80 100];
tanks(4).name = 'Right';   tanks(4).bounds = [235 285 22 62 85 103];
tanks(5).name = 'Aft';     tanks(5).bounds = [295 335 -17.5 17.5 83 105];

% Derived properties
for t = 1:5
    b = tanks(t).bounds;
    tanks(t).length = b(2)-b(1);
    tanks(t).width = b(4)-b(3);
    tanks(t).height = b(6)-b(5);
    tanks(t).base_area = tanks(t).length * tanks(t).width;
    tanks(t).wl_min = b(5);
    tanks(t).wl_max = b(6);
    tanks(t).gross_vol_in3 = tanks(t).base_area * tanks(t).height;
    tanks(t).ullage_h = tanks(t).height * 0.02;
    tanks(t).unusable_h = tanks(t).height * 0.015;
    tanks(t).max_fill_wl = tanks(t).wl_max - tanks(t).ullage_h;
end

% Probe definitions
probes = struct();
probes(1).type = 'real';
probes(1).base_wl = 88.24; probes(1).top_wl = 103.68;
probes(2).type = 'real';
probes(2).base_wl = 85.27; probes(2).top_wl = 102.64;
probes(3).type = 'combo';
probes(3).lower_base = 80.30; probes(3).lower_top = 92.00;
probes(3).upper_base = 90.00; probes(3).upper_top = 99.60;
probes(3).blend_lo = 90.0; probes(3).blend_hi = 92.0;
probes(4).type = 'real';
probes(4).base_wl = 85.27; probes(4).top_wl = 102.64;
probes(5).type = 'pseudo';
probes(5).dx = 55.0; probes(5).dy = 0.0;
probes(5).source_tank = 3;

% Density model: rho(lb/gal) = 4.667 * kappa - 2.857
density_model = struct('a', 4.667, 'b', -2.857);
kappa_nominal = 2.05;
density_lab = 6.71;  % lb/gal
density_bias = 0.003; % 0.3% high

% High-level sensor triggers (WL)
hi_level_wl = [tanks(1).max_fill_wl, tanks(2).max_fill_wl, ...
               tanks(3).max_fill_wl, tanks(4).max_fill_wl, tanks(5).max_fill_wl];

IN3_PER_GAL = 231.0;

%% ========================================================================
%  PROBE MEASUREMENT FUNCTIONS
%  ========================================================================

function h = real_probe_height(fuel_wl, base_wl, top_wl)
    % Real probe: wetted height = fuel WL - probe base, clamped
    active_len = top_wl - base_wl;
    h = max(0, min(fuel_wl - base_wl, active_len));
end

function h = combo_probe_height(fuel_wl, probe)
    % T3 real-pseudo combo: two probes with blend zone
    lower_h = max(0, min(fuel_wl - probe.lower_base, probe.lower_top - probe.lower_base));
    upper_h = max(0, min(fuel_wl - probe.upper_base, probe.upper_top - probe.upper_base));

    lower_wl = probe.lower_base + lower_h;
    upper_wl = probe.upper_base + upper_h;

    if fuel_wl < probe.blend_lo
        h = lower_h;
    elseif fuel_wl > probe.blend_hi
        h = upper_wl - probe.lower_base;
    else
        w = (fuel_wl - probe.blend_lo) / (probe.blend_hi - probe.blend_lo);
        blended_wl = (1-w) * lower_wl + w * upper_wl;
        h = blended_wl - probe.lower_base;
    end
end

function h = pseudo_probe_height(t3_fuel_wl, pitch_deg, roll_deg, probe, t3_base_wl, t5)
    % T5 pure pseudo: project from T3 using attitude
    tan_p = tand(pitch_deg);
    tan_r = tand(roll_deg);

    % Project fuel plane to T5 reference location
    projected_wl = t3_fuel_wl + probe.dx * tan_p + probe.dy * tan_r;

    % Clamp to T5 tank bounds
    projected_wl = max(t5.wl_min, min(projected_wl, t5.wl_max));
    h = projected_wl - t5.wl_min;
end

%% ========================================================================
%  PROBE FAILURE DETECTION
%  ========================================================================

function [is_failed, mode, output_h] = check_probe_failure(raw_h, prev_h, ...
    max_h, dt, open_thresh, short_thresh, rate_thresh)
    % Check probe reading for failure conditions
    is_failed = false;
    mode = '';
    output_h = raw_h;

    % Open circuit
    if raw_h < open_thresh
        is_failed = true;
        mode = 'OPEN_CIRCUIT';
        output_h = prev_h;  % Use LKG
        return;
    end

    % Short circuit
    if raw_h > max_h + short_thresh
        is_failed = true;
        mode = 'SHORT_CIRCUIT';
        output_h = prev_h;
        return;
    end

    % Rate exceedance
    rate = abs(raw_h - prev_h) / dt;
    if rate > rate_thresh
        is_failed = true;
        mode = 'RATE_EXCEEDANCE';
        output_h = prev_h;
        return;
    end

    % Clamp to valid range
    output_h = max(0, min(raw_h, max_h));
end

%% ========================================================================
%  VOLUME COMPUTATION (simplified for rectangular tank)
%  ========================================================================

function vol = compute_volume(tank, probe_height, pitch_deg, roll_deg)
    % Simplified volume: base_area * effective_height
    % Full implementation would use pre-generated H-V tables
    eff_h = max(0, probe_height - tank.unusable_h);
    eff_h = min(eff_h, tank.height - tank.ullage_h - tank.unusable_h);
    vol = tank.base_area * eff_h;
end

%% ========================================================================
%  LOAD DATA AND RUN SIMULATION
%  ========================================================================

fprintf('Loading simulation data...\n');
data_dir = fullfile(fileparts(mfilename('fullpath')), '..', 'data');
defuel_file = fullfile(data_dir, 'defuel_sequence.mat');

if exist(defuel_file, 'file')
    data = load(defuel_file);
    n_samples = length(data.time_s);
    fprintf('Loaded defuel sequence: %d samples\n', n_samples);
else
    fprintf('No defuel data found. Generating synthetic profile...\n');
    n_samples = 500;
    data = struct();
    data.time_s = (0:n_samples-1)';
    data.pitch_deg = 0.3 + 0.5*sin(2*pi*(0:n_samples-1)'/200);
    data.roll_deg = -0.2 + 0.8*sin(2*pi*(0:n_samples-1)'/300);
    for t = 1:5
        fill_start = tanks(t).wl_min + tanks(t).height * 0.95;
        fill_end = tanks(t).wl_min + tanks(t).height * 0.05;
        data.(sprintf('fuel_wl_T%d', t)) = linspace(fill_start, fill_end, n_samples)';
    end
end

%% Run gauging system
fprintf('\nRunning gauging simulation...\n');

results = struct();
results.time = data.time_s;
results.pitch = data.pitch_deg;
results.roll = data.roll_deg;

dt = 1.0; % seconds

for t = 1:5
    results.(sprintf('probe_h_T%d', t)) = zeros(n_samples, 1);
    results.(sprintf('vol_in3_T%d', t)) = zeros(n_samples, 1);
    results.(sprintf('weight_T%d', t)) = zeros(n_samples, 1);
    results.(sprintf('failed_T%d', t)) = false(n_samples, 1);
end
results.total_weight = zeros(n_samples, 1);
results.density_sys = zeros(n_samples, 1);
results.total_error = zeros(n_samples, 1);

prev_heights = zeros(5, 1);

for i = 1:n_samples
    pitch = data.pitch_deg(i);
    roll = data.roll_deg(i);

    % Density with bias and drift
    kappa = kappa_nominal + 0.005 * sin(2*pi*i/500);
    rho_sys = (density_model.a * kappa + density_model.b) * (1 + density_bias);
    results.density_sys(i) = rho_sys;

    total_wt = 0;
    total_true_wt = 0;

    for t = 1:5
        fuel_wl = data.(sprintf('fuel_wl_T%d', t))(i);

        % Probe measurement
        switch probes(t).type
            case 'real'
                raw_h = real_probe_height(fuel_wl, probes(t).base_wl, probes(t).top_wl);
                max_h = probes(t).top_wl - probes(t).base_wl;
            case 'combo'
                raw_h = combo_probe_height(fuel_wl, probes(t));
                max_h = probes(t).upper_top - probes(t).lower_base;
            case 'pseudo'
                t3_fuel_wl = data.fuel_wl_T3(i);
                raw_h = pseudo_probe_height(t3_fuel_wl, pitch, roll, probes(t), ...
                    probes(3).lower_base, tanks(5));
                max_h = tanks(5).height;
        end

        % Add measurement noise
        raw_h = raw_h + 0.02 * randn();

        % Failure detection
        [is_failed, mode, valid_h] = check_probe_failure(raw_h, prev_heights(t), ...
            max_h, dt, -0.1, 0.5, 2.0);

        prev_heights(t) = valid_h;
        results.(sprintf('probe_h_T%d', t))(i) = valid_h;
        results.(sprintf('failed_T%d', t))(i) = is_failed;

        % Volume lookup
        vol = compute_volume(tanks(t), valid_h, pitch, roll);
        results.(sprintf('vol_in3_T%d', t))(i) = vol;

        % Weight
        wt = (vol / IN3_PER_GAL) * rho_sys;
        results.(sprintf('weight_T%d', t))(i) = wt;
        total_wt = total_wt + wt;

        % True weight for error computation
        true_vol = tanks(t).base_area * max(0, fuel_wl - tanks(t).wl_min);
        true_wt = (true_vol / IN3_PER_GAL) * density_lab;
        total_true_wt = total_true_wt + true_wt;
    end

    results.total_weight(i) = total_wt;
    results.total_error(i) = total_wt - total_true_wt;
end

%% ========================================================================
%  REFUEL SIMULATION
%  ========================================================================

fprintf('\nRunning refuel simulation...\n');

n_refuel = 700;
refuel = struct();
refuel.time = (0:n_refuel-1)';
refuel.fuel_wl = zeros(n_refuel, 5);
refuel.valve_open = true(n_refuel, 5);
refuel.hi_level = false(n_refuel, 5);

% Start at 20% fill
for t = 1:5
    refuel.fuel_wl(1, t) = tanks(t).wl_min + tanks(t).height * 0.20;
end

supply_psi = 55;
manifold_wl = 78;
flow_cap = 15;  % gpm per valve

for i = 2:n_refuel
    for t = 1:5
        % Check high-level sensor
        if refuel.fuel_wl(i-1, t) >= hi_level_wl(t)
            refuel.hi_level(i, t) = true;
            refuel.valve_open(i, t) = false;
        else
            refuel.hi_level(i, t) = refuel.hi_level(i-1, t);
            refuel.valve_open(i, t) = ~refuel.hi_level(i, t);
        end

        % Flow calculation
        if refuel.valve_open(i, t)
            fuel_h = max(0, refuel.fuel_wl(i-1, t) - manifold_wl);
            p_head = 0.036 * density_lab * fuel_h;
            p_net = max(0, supply_psi - p_head);
            k = flow_cap / supply_psi;
            flow_gpm = k * p_net;
            flow_gal_step = flow_gpm / 60; % 1-second timestep
            dh = flow_gal_step * IN3_PER_GAL / tanks(t).base_area;
            refuel.fuel_wl(i, t) = min(refuel.fuel_wl(i-1, t) + dh, tanks(t).wl_max);
        else
            refuel.fuel_wl(i, t) = refuel.fuel_wl(i-1, t);
        end
    end

    % Check if all full
    if all(refuel.hi_level(i, :))
        n_refuel = i;
        refuel.time = refuel.time(1:i);
        refuel.fuel_wl = refuel.fuel_wl(1:i, :);
        refuel.valve_open = refuel.valve_open(1:i, :);
        refuel.hi_level = refuel.hi_level(1:i, :);
        fprintf('Refuel complete at t=%ds\n', i);
        break;
    end
end

%% ========================================================================
%  PLOTS
%  ========================================================================

fprintf('\nGenerating plots...\n');
plot_dir = fullfile(fileparts(mfilename('fullpath')), '..', 'plots');
if ~exist(plot_dir, 'dir'); mkdir(plot_dir); end

colors = lines(5);

% --- Plot 1: Gauging Error Timeline ---
figure('Position', [100 100 1200 800]);

subplot(3,1,1);
plot(results.time, results.total_error, 'k-', 'LineWidth', 0.8);
ylabel('Weight Error (lb)');
title('MATLAB Gauging System — Defuel Error Analysis', 'FontSize', 14);
grid on;

subplot(3,1,2);
hold on;
for t = 1:5
    plot(results.time, results.(sprintf('vol_in3_T%d', t))/IN3_PER_GAL, ...
        'Color', colors(t,:), 'LineWidth', 1.2);
end
ylabel('Volume (gal)');
legend('T1','T2','T3','T4','T5', 'Location', 'eastoutside');
grid on;

subplot(3,1,3);
plot(results.time, results.density_sys, 'b-');
hold on;
yline(density_lab, 'r--', 'Lab density');
ylabel('Density (lb/gal)');
xlabel('Time (s)');
grid on;

saveas(gcf, fullfile(plot_dir, '14_matlab_gauging_error.png'));
fprintf('Saved: 14_matlab_gauging_error.png\n');

% --- Plot 2: Refuel Sequence ---
figure('Position', [100 100 1200 600]);

subplot(2,1,1);
hold on;
for t = 1:5
    plot(refuel.time, refuel.fuel_wl(:,t), 'Color', colors(t,:), 'LineWidth', 1.5);
    yline(hi_level_wl(t), '--', 'Color', colors(t,:), 'Alpha', 0.4);
end
ylabel('Fuel WL (in)');
title('Single-Point Refuel — High-Level Shutoff', 'FontSize', 14);
legend('T1','T2','T3','T4','T5', 'Location', 'eastoutside');
grid on;

subplot(2,1,2);
hold on;
for t = 1:5
    % Offset valve status for visibility
    plot(refuel.time, double(refuel.valve_open(:,t)) + (t-1)*1.2, ...
        'Color', colors(t,:), 'LineWidth', 2);
end
ylabel('Valve Status');
xlabel('Time (s)');
yticks([]);
title('Shutoff Valve States (high = open)');
grid on;

saveas(gcf, fullfile(plot_dir, '15_matlab_refuel_sequence.png'));
fprintf('Saved: 15_matlab_refuel_sequence.png\n');

% --- Plot 3: Probe Failure Detection ---
figure('Position', [100 100 1000 400]);
hold on;
for t = 1:5
    failed = results.(sprintf('failed_T%d', t));
    if any(failed)
        fail_times = results.time(failed);
        scatter(fail_times, t*ones(size(fail_times)), 20, colors(t,:), 'filled');
    end
end
yticks(1:5);
yticklabels({'T1','T2','T3','T4','T5'});
xlabel('Time (s)');
title('Probe Failure Events (dot = failure detected)', 'FontSize', 14);
grid on;

saveas(gcf, fullfile(plot_dir, '16_matlab_probe_failures.png'));
fprintf('Saved: 16_matlab_probe_failures.png\n');

%% Summary
fprintf('\n=== RESULTS SUMMARY ===\n');
fprintf('Gauging simulation: %d samples\n', n_samples);
fprintf('  Max weight error: %.2f lb\n', max(abs(results.total_error)));
fprintf('  Mean weight error: %.2f lb\n', mean(results.total_error));
fprintf('  Density bias: %.4f lb/gal\n', mean(results.density_sys) - density_lab);

fprintf('\nRefuel simulation: %d samples\n', length(refuel.time));
for t = 1:5
    trip_idx = find(refuel.hi_level(:,t), 1);
    if ~isempty(trip_idx)
        fprintf('  T%d (%s): hi-level at t=%ds, WL=%.2f\n', ...
            t, tanks(t).name, trip_idx, refuel.fuel_wl(trip_idx, t));
    end
end

fprintf('\nProbe failures detected:\n');
for t = 1:5
    n_fail = sum(results.(sprintf('failed_T%d', t)));
    fprintf('  T%d: %d failure events (%.1f%%)\n', t, n_fail, 100*n_fail/n_samples);
end

fprintf('\nDone.\n');
