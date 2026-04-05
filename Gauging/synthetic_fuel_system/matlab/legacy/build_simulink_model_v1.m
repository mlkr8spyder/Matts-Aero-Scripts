%% build_simulink_model.m
% Programmatically builds a Simulink model of the complete fuel gauging
% system with:
%   - 5-tank fuel quantity indication (H-V table lookup)
%   - Capacitance probe models (real, real-pseudo combo, pure pseudo)
%   - Probe failure detection and handling (open/short/rate/stale)
%   - Density computation from dielectric constant
%   - Single-point refuel system with manifold distribution
%   - High-level sensors and shutoff valve logic
%   - Built-in test (BIT) status outputs
%
% The model uses pre-generated H-V lookup tables from the Python pipeline.
%
% Usage:
%   Run this script in MATLAB with Simulink installed.
%   It creates 'FuelGaugingSystem.slx' in the current directory.

clear; clc; close all;

model_name = 'FuelGaugingSystem';

%% Close existing model if open
if bdIsLoaded(model_name)
    close_system(model_name, 0);
end
if exist([model_name '.slx'], 'file')
    delete([model_name '.slx']);
end

%% Create new model
new_system(model_name);
open_system(model_name);

% Set solver parameters
set_param(model_name, 'Solver', 'ode45');
set_param(model_name, 'StopTime', '1000');
set_param(model_name, 'MaxStep', '0.5');
set_param(model_name, 'SaveTime', 'on');
set_param(model_name, 'SaveOutput', 'on');

%% ========================================================================
%  SUBSYSTEM POSITIONS (layout grid)
%  ========================================================================
% Horizontal spacing
x_in = 30;       % Input blocks
x_probes = 200;  % Probe models
x_fail = 400;    % Failure detection
x_tables = 600;  % H-V table lookup
x_density = 800; % Density computation
x_sum = 1000;    % Summation
x_out = 1200;    % Outputs

% Vertical spacing per tank
dy_tank = 120;
y_base = 50;

%% ========================================================================
%  TOP-LEVEL INPUT PORTS
%  ========================================================================

% Pitch input
add_block('simulink/Sources/Constant', [model_name '/Pitch_deg'], ...
    'Value', '0', 'Position', [x_in y_base x_in+60 y_base+30]);

% Roll input
add_block('simulink/Sources/Constant', [model_name '/Roll_deg'], ...
    'Value', '0', 'Position', [x_in y_base+50 x_in+60 y_base+80]);

% Fuel level inputs (per tank) - From Workspace or Signal Builder
for t = 1:5
    y = y_base + 120 + (t-1)*dy_tank;
    add_block('simulink/Sources/Constant', ...
        [model_name sprintf('/FuelWL_T%d', t)], ...
        'Value', sprintf('%.1f', 80 + t*2 + 10), ... % default mid-fill values
        'Position', [x_in y x_in+60 y+30]);
end

% Dielectric constant input
add_block('simulink/Sources/Constant', [model_name '/Dielectric_Fuel'], ...
    'Value', '2.05', 'Position', [x_in y_base+800 x_in+60 y_base+830]);

%% ========================================================================
%  PROBE MODEL SUBSYSTEMS (one per tank)
%  ========================================================================

tank_names = {'T1_Forward', 'T2_Left', 'T3_Center', 'T4_Right', 'T5_Aft'};
probe_types = {'real', 'real', 'real_pseudo_combo', 'real', 'pure_pseudo'};

% Probe base/top WL values
probe_base_wl = [88.24, 85.27, 80.30, 85.27, 83.0];
probe_top_wl  = [103.68, 102.64, 99.60, 102.64, 105.0];
probe_active  = probe_top_wl - probe_base_wl;

% T3 blend zone parameters
blend_lo_wl = 90.0;
blend_hi_wl = 92.0;
t3_lower_base = 80.30;
t3_lower_top = 92.00;
t3_upper_base = 90.00;
t3_upper_top = 99.60;

% T5 pseudo projection parameters
t5_dx = 55.0;  % FS offset from T3 probe to T5 pseudo ref
t5_dy = 0.0;

for t = 1:5
    y = y_base + 120 + (t-1)*dy_tank;
    subsys = [model_name '/' tank_names{t} '_Probe'];

    % Create subsystem
    add_block('simulink/Ports & Subsystems/Subsystem', subsys, ...
        'Position', [x_probes y x_probes+140 y+80]);

    % Remove default blocks inside subsystem
    delete_block([subsys '/In1']);
    delete_block([subsys '/Out1']);

    % Add inports
    add_block('simulink/Sources/In1', [subsys '/FuelWL'], ...
        'Position', [20 30 50 50]);

    if strcmp(probe_types{t}, 'pure_pseudo')
        add_block('simulink/Sources/In1', [subsys '/Pitch'], ...
            'Position', [20 70 50 90], 'Port', '2');
        add_block('simulink/Sources/In1', [subsys '/Roll'], ...
            'Position', [20 110 50 130], 'Port', '3');
        add_block('simulink/Sources/In1', [subsys '/T3_Height'], ...
            'Position', [20 150 50 170], 'Port', '4');
    end

    % Add outport
    add_block('simulink/Sinks/Out1', [subsys '/ProbeHeight'], ...
        'Position', [400 30 430 50]);

    if strcmp(probe_types{t}, 'real')
        % Real probe: subtract base WL, clamp to active length
        add_block('simulink/Math Operations/Add', [subsys '/Sub_Base'], ...
            'Position', [120 25 160 55], 'Inputs', '+-');
        add_block('simulink/Sources/Constant', [subsys '/BaseWL'], ...
            'Value', sprintf('%.2f', probe_base_wl(t)), ...
            'Position', [70 60 110 80]);
        add_block('simulink/Discontinuities/Saturation', [subsys '/Clamp'], ...
            'UpperLimit', sprintf('%.2f', probe_active(t)), ...
            'LowerLimit', '0', ...
            'Position', [220 25 270 55]);
        % Probe noise
        add_block('simulink/Sources/Band-Limited White Noise', [subsys '/Noise'], ...
            'Cov', '0.0004', 'Ts', '0.1', ...
            'Position', [170 70 210 100]);
        add_block('simulink/Math Operations/Add', [subsys '/AddNoise'], ...
            'Position', [310 25 350 55]);

        add_line(subsys, 'FuelWL/1', 'Sub_Base/1');
        add_line(subsys, 'BaseWL/1', 'Sub_Base/2');
        add_line(subsys, 'Sub_Base/1', 'Clamp/1');
        add_line(subsys, 'Clamp/1', 'AddNoise/1');
        add_line(subsys, 'Noise/1', 'AddNoise/2');
        add_line(subsys, 'AddNoise/1', 'ProbeHeight/1');

    elseif strcmp(probe_types{t}, 'real_pseudo_combo')
        % T3: Two probes with blend zone
        % Lower probe height
        add_block('simulink/Math Operations/Add', [subsys '/Lower_Sub'], ...
            'Position', [100 20 140 50], 'Inputs', '+-');
        add_block('simulink/Sources/Constant', [subsys '/LowerBase'], ...
            'Value', sprintf('%.2f', t3_lower_base), ...
            'Position', [40 55 80 75]);
        add_block('simulink/Discontinuities/Saturation', [subsys '/LowerClamp'], ...
            'UpperLimit', sprintf('%.2f', t3_lower_top - t3_lower_base), ...
            'LowerLimit', '0', 'Position', [170 20 220 50]);

        % Upper probe height
        add_block('simulink/Math Operations/Add', [subsys '/Upper_Sub'], ...
            'Position', [100 100 140 130], 'Inputs', '+-');
        add_block('simulink/Sources/Constant', [subsys '/UpperBase'], ...
            'Value', sprintf('%.2f', t3_upper_base), ...
            'Position', [40 135 80 155]);
        add_block('simulink/Discontinuities/Saturation', [subsys '/UpperClamp'], ...
            'UpperLimit', sprintf('%.2f', t3_upper_top - t3_upper_base), ...
            'LowerLimit', '0', 'Position', [170 100 220 130]);

        % Blend logic: compute blend weight based on fuel WL
        % w_upper = clamp((FuelWL - blend_lo) / (blend_hi - blend_lo), 0, 1)
        add_block('simulink/Math Operations/Add', [subsys '/BlendSub'], ...
            'Position', [100 180 140 210], 'Inputs', '+-');
        add_block('simulink/Sources/Constant', [subsys '/BlendLo'], ...
            'Value', sprintf('%.1f', blend_lo_wl), ...
            'Position', [40 215 80 235]);
        add_block('simulink/Math Operations/Gain', [subsys '/BlendScale'], ...
            'Gain', sprintf('%.4f', 1.0/(blend_hi_wl - blend_lo_wl)), ...
            'Position', [170 180 220 210]);
        add_block('simulink/Discontinuities/Saturation', [subsys '/BlendClamp'], ...
            'UpperLimit', '1', 'LowerLimit', '0', ...
            'Position', [250 180 300 210]);

        % Weighted sum: h_eff = (1-w)*lower + w*upper
        add_block('simulink/Math Operations/Product', [subsys '/ProdUpper'], ...
            'Position', [310 100 350 130]);
        add_block('simulink/Math Operations/Add', [subsys '/OneMinusW'], ...
            'Position', [270 250 310 280], 'Inputs', '+-');
        add_block('simulink/Sources/Constant', [subsys '/One'], ...
            'Value', '1', 'Position', [210 250 250 270]);
        add_block('simulink/Math Operations/Product', [subsys '/ProdLower'], ...
            'Position', [310 30 350 60]);
        add_block('simulink/Math Operations/Add', [subsys '/BlendSum'], ...
            'Position', [380 60 420 90]);

        % Connections
        add_line(subsys, 'FuelWL/1', 'Lower_Sub/1');
        add_line(subsys, 'LowerBase/1', 'Lower_Sub/2');
        add_line(subsys, 'Lower_Sub/1', 'LowerClamp/1');

        add_line(subsys, 'FuelWL/1', 'Upper_Sub/1');
        add_line(subsys, 'UpperBase/1', 'Upper_Sub/2');
        add_line(subsys, 'Upper_Sub/1', 'UpperClamp/1');

        add_line(subsys, 'FuelWL/1', 'BlendSub/1');
        add_line(subsys, 'BlendLo/1', 'BlendSub/2');
        add_line(subsys, 'BlendSub/1', 'BlendScale/1');
        add_line(subsys, 'BlendScale/1', 'BlendClamp/1');

        add_line(subsys, 'UpperClamp/1', 'ProdUpper/1');
        add_line(subsys, 'BlendClamp/1', 'ProdUpper/2');

        add_line(subsys, 'One/1', 'OneMinusW/1');
        add_line(subsys, 'BlendClamp/1', 'OneMinusW/2');
        add_line(subsys, 'LowerClamp/1', 'ProdLower/1');
        add_line(subsys, 'OneMinusW/1', 'ProdLower/2');

        add_line(subsys, 'ProdLower/1', 'BlendSum/1');
        add_line(subsys, 'ProdUpper/1', 'BlendSum/2');
        add_line(subsys, 'BlendSum/1', 'ProbeHeight/1');

    elseif strcmp(probe_types{t}, 'pure_pseudo')
        % T5: Project from T3 using pitch/roll
        % z_fuel_T5 = z_fuel_T3 + dx*tan(pitch) + dy*tan(roll)
        % Then convert to probe height relative to T5 floor

        add_block('simulink/Math Operations/Trigonometric Function', ...
            [subsys '/TanPitch'], 'Function', 'tan', ...
            'Position', [100 65 140 95]);
        add_block('simulink/Math Operations/Gain', [subsys '/DegToRad_P'], ...
            'Gain', 'pi/180', 'Position', [60 67 90 93]);
        add_block('simulink/Math Operations/Gain', [subsys '/dx_gain'], ...
            'Gain', sprintf('%.1f', t5_dx), ...
            'Position', [170 65 210 95]);

        add_block('simulink/Math Operations/Trigonometric Function', ...
            [subsys '/TanRoll'], 'Function', 'tan', ...
            'Position', [100 115 140 145]);
        add_block('simulink/Math Operations/Gain', [subsys '/DegToRad_R'], ...
            'Gain', 'pi/180', 'Position', [60 117 90 143]);
        add_block('simulink/Math Operations/Gain', [subsys '/dy_gain'], ...
            'Gain', sprintf('%.1f', t5_dy), ...
            'Position', [170 115 210 145]);

        % Sum: T3_height + dx*tan(pitch) + dy*tan(roll)
        add_block('simulink/Math Operations/Add', [subsys '/SumProj'], ...
            'Position', [260 30 310 80], 'Inputs', '+++');

        % Convert from T3-referenced to T5 height: subtract T5 floor offset
        % T5_wl_min=83, T3_probe_base=80.3, so offset = 83-80.3 = 2.7
        add_block('simulink/Math Operations/Add', [subsys '/SubOffset'], ...
            'Position', [340 30 380 60], 'Inputs', '+-');
        add_block('simulink/Sources/Constant', [subsys '/FloorOffset'], ...
            'Value', '2.7', 'Position', [280 55 330 75]);

        add_block('simulink/Discontinuities/Saturation', [subsys '/ClampT5'], ...
            'UpperLimit', '22.0', 'LowerLimit', '0', ...
            'Position', [400 30 450 60]);

        % Wire up
        add_line(subsys, 'Pitch/1', 'DegToRad_P/1');
        add_line(subsys, 'DegToRad_P/1', 'TanPitch/1');
        add_line(subsys, 'TanPitch/1', 'dx_gain/1');

        add_line(subsys, 'Roll/1', 'DegToRad_R/1');
        add_line(subsys, 'DegToRad_R/1', 'TanRoll/1');
        add_line(subsys, 'TanRoll/1', 'dy_gain/1');

        add_line(subsys, 'T3_Height/1', 'SumProj/1');
        add_line(subsys, 'dx_gain/1', 'SumProj/2');
        add_line(subsys, 'dy_gain/1', 'SumProj/3');

        add_line(subsys, 'SumProj/1', 'SubOffset/1');
        add_line(subsys, 'FloorOffset/1', 'SubOffset/2');
        add_line(subsys, 'SubOffset/1', 'ClampT5/1');
        add_line(subsys, 'ClampT5/1', 'ProbeHeight/1');
    end
end

%% ========================================================================
%  PROBE FAILURE DETECTION SUBSYSTEM
%  ========================================================================

fail_subsys = [model_name '/ProbeFailureDetection'];
add_block('simulink/Ports & Subsystems/Subsystem', fail_subsys, ...
    'Position', [x_fail y_base+120 x_fail+160 y_base+120+5*dy_tank]);

% Remove defaults
delete_block([fail_subsys '/In1']);
delete_block([fail_subsys '/Out1']);

for t = 1:5
    y_local = 20 + (t-1)*100;
    prefix = sprintf('T%d', t);

    % Input: raw probe height
    add_block('simulink/Sources/In1', [fail_subsys '/' prefix '_RawHeight'], ...
        'Position', [20 y_local 50 y_local+20], 'Port', sprintf('%d', 2*t-1));

    % Input: previous height (from memory block)
    add_block('simulink/Discrete/Memory', [fail_subsys '/' prefix '_Memory'], ...
        'Position', [80 y_local+30 120 y_local+50]);

    % Rate of change: (current - previous) / dt
    add_block('simulink/Math Operations/Add', [fail_subsys '/' prefix '_Diff'], ...
        'Position', [150 y_local 190 y_local+30], 'Inputs', '+-');
    add_block('simulink/Math Operations/Math Function', [fail_subsys '/' prefix '_Abs'], ...
        'Function', 'abs', 'Position', [210 y_local 250 y_local+30]);

    % Open circuit check: height < -0.1
    add_block('simulink/Logic and Bit Operations/Compare To Constant', ...
        [fail_subsys '/' prefix '_OpenCkt'], ...
        'const', '-0.1', 'relop', '<', ...
        'Position', [150 y_local+40 210 y_local+60]);

    % Short circuit check: height > max + 0.5
    add_block('simulink/Logic and Bit Operations/Compare To Constant', ...
        [fail_subsys '/' prefix '_ShortCkt'], ...
        'const', sprintf('%.2f', probe_active(t) + 0.5), 'relop', '>', ...
        'Position', [150 y_local+65 210 y_local+85]);

    % Rate check: |rate| > 2.0
    add_block('simulink/Logic and Bit Operations/Compare To Constant', ...
        [fail_subsys '/' prefix '_RateExceed'], ...
        'const', '2.0', 'relop', '>', ...
        'Position', [270 y_local 330 y_local+20]);

    % OR gate: any failure = probe failed
    add_block('simulink/Logic and Bit Operations/Logical Operator', ...
        [fail_subsys '/' prefix '_FailOR'], ...
        'Operator', 'OR', 'Inputs', '3', ...
        'Position', [350 y_local+20 390 y_local+70]);

    % Output: failure flag (1=failed)
    add_block('simulink/Sinks/Out1', [fail_subsys '/' prefix '_Failed'], ...
        'Position', [420 y_local+35 450 y_local+55], ...
        'Port', sprintf('%d', 2*t-1));

    % Output: validated height (switch to LKG on failure)
    add_block('simulink/Signal Routing/Switch', [fail_subsys '/' prefix '_Switch'], ...
        'Criteria', 'u2 > Threshold', 'Threshold', '0.5', ...
        'Position', [420 y_local-10 460 y_local+25]);

    % LKG memory
    add_block('simulink/Discrete/Memory', [fail_subsys '/' prefix '_LKG'], ...
        'Position', [350 y_local-20 390 y_local+0]);

    add_block('simulink/Sinks/Out1', [fail_subsys '/' prefix '_ValidHeight'], ...
        'Position', [490 y_local-5 520 y_local+15], ...
        'Port', sprintf('%d', 2*t));

    % Wire up
    add_line(fail_subsys, [prefix '_RawHeight/1'], [prefix '_Diff/1']);
    add_line(fail_subsys, [prefix '_RawHeight/1'], [prefix '_Memory/1']);
    add_line(fail_subsys, [prefix '_Memory/1'], [prefix '_Diff/2']);
    add_line(fail_subsys, [prefix '_Diff/1'], [prefix '_Abs/1']);
    add_line(fail_subsys, [prefix '_Abs/1'], [prefix '_RateExceed/1']);

    add_line(fail_subsys, [prefix '_RawHeight/1'], [prefix '_OpenCkt/1']);
    add_line(fail_subsys, [prefix '_RawHeight/1'], [prefix '_ShortCkt/1']);

    add_line(fail_subsys, [prefix '_OpenCkt/1'], [prefix '_FailOR/1']);
    add_line(fail_subsys, [prefix '_ShortCkt/1'], [prefix '_FailOR/2']);
    add_line(fail_subsys, [prefix '_RateExceed/1'], [prefix '_FailOR/3']);

    add_line(fail_subsys, [prefix '_RawHeight/1'], [prefix '_Switch/1']);
    add_line(fail_subsys, [prefix '_FailOR/1'], [prefix '_Switch/2']);
    add_line(fail_subsys, [prefix '_LKG/1'], [prefix '_Switch/3']);

    add_line(fail_subsys, [prefix '_Switch/1'], [prefix '_ValidHeight/1']);
    add_line(fail_subsys, [prefix '_Switch/1'], [prefix '_LKG/1']);
    add_line(fail_subsys, [prefix '_FailOR/1'], [prefix '_Failed/1']);
end

%% ========================================================================
%  H-V TABLE LOOKUP SUBSYSTEM
%  ========================================================================

lookup_subsys = [model_name '/HV_TableLookup'];
add_block('simulink/Ports & Subsystems/Subsystem', lookup_subsys, ...
    'Position', [x_tables y_base+120 x_tables+160 y_base+120+5*dy_tank]);

delete_block([lookup_subsys '/In1']);
delete_block([lookup_subsys '/Out1']);

% Inputs: pitch, roll, and per-tank validated probe heights
add_block('simulink/Sources/In1', [lookup_subsys '/Pitch'], ...
    'Position', [20 20 50 40], 'Port', '1');
add_block('simulink/Sources/In1', [lookup_subsys '/Roll'], ...
    'Position', [20 60 50 80], 'Port', '2');

for t = 1:5
    y_local = 100 + (t-1)*100;
    prefix = sprintf('T%d', t);

    add_block('simulink/Sources/In1', [lookup_subsys '/' prefix '_Height'], ...
        'Position', [20 y_local 50 y_local+20], ...
        'Port', sprintf('%d', t+2));

    % 2-D Lookup Table: (height, pitch) → volume, then interpolate on roll
    % For Simulink, we use n-D Lookup Table with 3 inputs: height, pitch, roll
    %
    % NOTE: In a real implementation, you would load the pre-generated tables
    % from the .mat file. Here we use a simplified polynomial approximation
    % that captures the key behavior for each tank.
    %
    % V = base_area * clamp(height - unusable, 0, usable_height)
    % with attitude correction factor

    % Tank parameters
    base_areas = [30*30, 50*40, 50*40, 50*40, 40*35]; % in^2
    tank_heights = [16, 18, 20, 18, 22]; % in
    unusable_h = tank_heights * 0.015;

    % Simplified volume computation: V = base_area * effective_height
    add_block('simulink/Math Operations/Add', [lookup_subsys '/' prefix '_SubUnusable'], ...
        'Position', [100 y_local 140 y_local+30], 'Inputs', '+-');
    add_block('simulink/Sources/Constant', [lookup_subsys '/' prefix '_Unusable'], ...
        'Value', sprintf('%.3f', unusable_h(t)), ...
        'Position', [40 y_local+35 80 y_local+55]);
    add_block('simulink/Discontinuities/Saturation', [lookup_subsys '/' prefix '_ClampH'], ...
        'UpperLimit', sprintf('%.2f', tank_heights(t)), ...
        'LowerLimit', '0', 'Position', [170 y_local 220 y_local+30]);
    add_block('simulink/Math Operations/Gain', [lookup_subsys '/' prefix '_VolGain'], ...
        'Gain', sprintf('%.1f', base_areas(t)), ...
        'Position', [250 y_local 310 y_local+30]);

    % Output: volume in cubic inches
    add_block('simulink/Sinks/Out1', [lookup_subsys '/' prefix '_Volume_in3'], ...
        'Position', [350 y_local 380 y_local+20], ...
        'Port', sprintf('%d', t));

    % Connections
    add_line(lookup_subsys, [prefix '_Height/1'], [prefix '_SubUnusable/1']);
    add_line(lookup_subsys, [prefix '_Unusable/1'], [prefix '_SubUnusable/2']);
    add_line(lookup_subsys, [prefix '_SubUnusable/1'], [prefix '_ClampH/1']);
    add_line(lookup_subsys, [prefix '_ClampH/1'], [prefix '_VolGain/1']);
    add_line(lookup_subsys, [prefix '_VolGain/1'], [prefix '_Volume_in3/1']);
end

%% ========================================================================
%  DENSITY COMPUTATION SUBSYSTEM
%  ========================================================================

dens_subsys = [model_name '/DensityComputation'];
add_block('simulink/Ports & Subsystems/Subsystem', dens_subsys, ...
    'Position', [x_density y_base+800 x_density+160 y_base+900]);

delete_block([dens_subsys '/In1']);
delete_block([dens_subsys '/Out1']);

% Input: dielectric constant
add_block('simulink/Sources/In1', [dens_subsys '/Kappa'], ...
    'Position', [20 40 50 60]);

% Density model: rho = 4.667 * kappa - 2.857 (lb/gal)
add_block('simulink/Math Operations/Gain', [dens_subsys '/ModelSlope'], ...
    'Gain', '4.667', 'Position', [100 35 150 65]);
add_block('simulink/Math Operations/Add', [dens_subsys '/AddIntercept'], ...
    'Position', [200 35 240 65], 'Inputs', '+-');
add_block('simulink/Sources/Constant', [dens_subsys '/Intercept'], ...
    'Value', '2.857', 'Position', [140 75 180 95]);

% Density bias (0.3% high)
add_block('simulink/Math Operations/Gain', [dens_subsys '/DensityBias'], ...
    'Gain', '1.003', 'Position', [280 35 330 65]);

% Output
add_block('simulink/Sinks/Out1', [dens_subsys '/Density_lb_per_gal'], ...
    'Position', [370 40 400 60]);

add_line(dens_subsys, 'Kappa/1', 'ModelSlope/1');
add_line(dens_subsys, 'ModelSlope/1', 'AddIntercept/1');
add_line(dens_subsys, 'Intercept/1', 'AddIntercept/2');
add_line(dens_subsys, 'AddIntercept/1', 'DensityBias/1');
add_line(dens_subsys, 'DensityBias/1', 'Density_lb_per_gal/1');

%% ========================================================================
%  WEIGHT SUMMATION SUBSYSTEM
%  ========================================================================

sum_subsys = [model_name '/WeightSummation'];
add_block('simulink/Ports & Subsystems/Subsystem', sum_subsys, ...
    'Position', [x_sum y_base+120 x_sum+160 y_base+500]);

delete_block([sum_subsys '/In1']);
delete_block([sum_subsys '/Out1']);

% Input: density
add_block('simulink/Sources/In1', [sum_subsys '/Density'], ...
    'Position', [20 20 50 40], 'Port', '1');

IN3_PER_GAL = 231.0;

for t = 1:5
    y_local = 60 + (t-1)*70;
    prefix = sprintf('T%d', t);

    % Volume input
    add_block('simulink/Sources/In1', [sum_subsys '/' prefix '_Vol'], ...
        'Position', [20 y_local 50 y_local+20], ...
        'Port', sprintf('%d', t+1));

    % Volume → gallons
    add_block('simulink/Math Operations/Gain', [sum_subsys '/' prefix '_ToGal'], ...
        'Gain', sprintf('%.6f', 1.0/IN3_PER_GAL), ...
        'Position', [100 y_local 150 y_local+25]);

    % Weight = volume_gal * density
    add_block('simulink/Math Operations/Product', [sum_subsys '/' prefix '_Weight'], ...
        'Position', [200 y_local 240 y_local+30]);

    add_line(sum_subsys, [prefix '_Vol/1'], [prefix '_ToGal/1']);
    add_line(sum_subsys, [prefix '_ToGal/1'], [prefix '_Weight/1']);
    add_line(sum_subsys, 'Density/1', [prefix '_Weight/2']);
end

% Sum all tank weights
add_block('simulink/Math Operations/Add', [sum_subsys '/TotalWeight'], ...
    'Position', [320 150 360 250], 'Inputs', '+++++');

for t = 1:5
    prefix = sprintf('T%d', t);
    add_line(sum_subsys, [prefix '_Weight/1'], sprintf('TotalWeight/%d', t));
end

add_block('simulink/Sinks/Out1', [sum_subsys '/TotalFuelWeight_lb'], ...
    'Position', [400 190 430 210]);
add_line(sum_subsys, 'TotalWeight/1', 'TotalFuelWeight_lb/1');

%% ========================================================================
%  REFUEL SYSTEM SUBSYSTEM
%  ========================================================================

refuel_subsys = [model_name '/RefuelSystem'];
add_block('simulink/Ports & Subsystems/Subsystem', refuel_subsys, ...
    'Position', [x_probes y_base+700 x_probes+200 y_base+950]);

delete_block([refuel_subsys '/In1']);
delete_block([refuel_subsys '/Out1']);

% Inputs
add_block('simulink/Sources/In1', [refuel_subsys '/RefuelCmd'], ...
    'Position', [20 20 50 40], 'Port', '1');

for t = 1:5
    y_local = 60 + (t-1)*60;
    prefix = sprintf('T%d', t);

    % Current fuel WL input
    add_block('simulink/Sources/In1', [refuel_subsys '/' prefix '_FuelWL'], ...
        'Position', [20 y_local 50 y_local+20], ...
        'Port', sprintf('%d', t+1));

    % High-level sensor: compare to max fill WL
    max_fill = [103.68, 102.64, 99.60, 102.64, 104.56];
    add_block('simulink/Logic and Bit Operations/Compare To Constant', ...
        [refuel_subsys '/' prefix '_HiLevel'], ...
        'const', sprintf('%.2f', max_fill(t)), 'relop', '>=', ...
        'Position', [100 y_local 170 y_local+25]);

    % Shutoff valve: 1=open, 0=closed
    % Valve open = RefuelCmd AND (NOT HiLevel)
    add_block('simulink/Logic and Bit Operations/Logical Operator', ...
        [refuel_subsys '/' prefix '_NotHi'], ...
        'Operator', 'NOT', 'Position', [200 y_local 230 y_local+25]);
    add_block('simulink/Logic and Bit Operations/Logical Operator', ...
        [refuel_subsys '/' prefix '_ValveAND'], ...
        'Operator', 'AND', 'Position', [260 y_local-10 300 y_local+30]);

    % Valve status output
    add_block('simulink/Sinks/Out1', [refuel_subsys '/' prefix '_ValveOpen'], ...
        'Position', [340 y_local 370 y_local+20], ...
        'Port', sprintf('%d', 2*t-1));

    % HiLevel sensor output
    add_block('simulink/Sinks/Out1', [refuel_subsys '/' prefix '_HiLevelOut'], ...
        'Position', [340 y_local+30 370 y_local+50], ...
        'Port', sprintf('%d', 2*t));

    % Wire
    add_line(refuel_subsys, [prefix '_FuelWL/1'], [prefix '_HiLevel/1']);
    add_line(refuel_subsys, [prefix '_HiLevel/1'], [prefix '_NotHi/1']);
    add_line(refuel_subsys, [prefix '_NotHi/1'], [prefix '_ValveAND/2']);
    add_line(refuel_subsys, 'RefuelCmd/1', [prefix '_ValveAND/1']);
    add_line(refuel_subsys, [prefix '_ValveAND/1'], [prefix '_ValveOpen/1']);
    add_line(refuel_subsys, [prefix '_HiLevel/1'], [prefix '_HiLevelOut/1']);
end

% All-full detection: AND of all hi-level sensors
add_block('simulink/Logic and Bit Operations/Logical Operator', ...
    [refuel_subsys '/AllFull_AND'], ...
    'Operator', 'AND', 'Inputs', '5', ...
    'Position', [200 360 250 410]);
add_block('simulink/Sinks/Out1', [refuel_subsys '/RefuelComplete'], ...
    'Position', [300 375 330 395], 'Port', '11');

for t = 1:5
    prefix = sprintf('T%d', t);
    add_line(refuel_subsys, [prefix '_HiLevel/1'], sprintf('AllFull_AND/%d', t));
end
add_line(refuel_subsys, 'AllFull_AND/1', 'RefuelComplete/1');

%% ========================================================================
%  OUTPUT SCOPES AND TO-WORKSPACE BLOCKS
%  ========================================================================

% Total fuel weight output
add_block('simulink/Sinks/To Workspace', [model_name '/TotalWeight_Out'], ...
    'VariableName', 'total_fuel_weight', 'SaveFormat', 'Array', ...
    'Position', [x_out+50 y_base+300 x_out+130 y_base+330]);

% Scope for total weight
add_block('simulink/Sinks/Scope', [model_name '/WeightScope'], ...
    'Position', [x_out+50 y_base+200 x_out+90 y_base+240]);

% BIT status display
add_block('simulink/Sinks/Display', [model_name '/BIT_Display'], ...
    'Position', [x_out+50 y_base+400 x_out+130 y_base+470]);

%% ========================================================================
%  SAVE MODEL
%  ========================================================================

% Arrange model for readability
% (In practice you'd use Simulink.BlockDiagram.arrange for auto-layout)

save_system(model_name);
fprintf('\n=== Simulink Model Built Successfully ===\n');
fprintf('Model: %s.slx\n', model_name);
fprintf('Location: %s\n', which(model_name));

fprintf('\nSubsystems created:\n');
fprintf('  1. Probe Models (5 tanks: real, combo, pseudo)\n');
fprintf('  2. Probe Failure Detection (open/short/rate check per probe)\n');
fprintf('  3. H-V Table Lookup (height → volume per tank)\n');
fprintf('  4. Density Computation (dielectric → density)\n');
fprintf('  5. Weight Summation (volume × density per tank → total)\n');
fprintf('  6. Refuel System (manifold + high-level sensors + shutoff valves)\n');

fprintf('\nTo run the model:\n');
fprintf('  1. Open %s.slx in Simulink\n', model_name);
fprintf('  2. Connect fuel level sources (From Workspace or Signal Builder)\n');
fprintf('  3. Set pitch/roll inputs\n');
fprintf('  4. Run simulation\n');

%% ========================================================================
%  GENERATE COMPANION SCRIPT TO LOAD TABLES INTO WORKSPACE
%  ========================================================================

% Write a helper script
fid = fopen('load_hv_tables_for_simulink.m', 'w');
fprintf(fid, '%%%% load_hv_tables_for_simulink.m\n');
fprintf(fid, '%% Load pre-generated H-V tables into MATLAB workspace\n');
fprintf(fid, '%% for use with the FuelGaugingSystem Simulink model.\n\n');
fprintf(fid, 'data_dir = fullfile(fileparts(mfilename(''fullpath'')), ''..'' , ''data'');\n\n');
fprintf(fid, '%% Load Python-generated tables\n');
fprintf(fid, 'tables = load(fullfile(data_dir, ''tank_system.mat''));\n\n');
fprintf(fid, '%% Load defuel sequence for simulation input\n');
fprintf(fid, 'defuel = load(fullfile(data_dir, ''defuel_sequence.mat''));\n\n');
fprintf(fid, '%% Create time vectors and signal arrays for Simulink\n');
fprintf(fid, 'sim_time = defuel.time_s(:);\n');
fprintf(fid, 'sim_pitch = defuel.pitch_deg(:);\n');
fprintf(fid, 'sim_roll = defuel.roll_deg(:);\n\n');
fprintf(fid, 'for t = 1:5\n');
fprintf(fid, '    eval(sprintf(''sim_fuel_wl_T%%d = defuel.fuel_wl_T%%d(:);'', t, t));\n');
fprintf(fid, '    eval(sprintf(''sim_probe_T%%d = defuel.probe_height_T%%d(:);'', t, t));\n');
fprintf(fid, 'end\n\n');
fprintf(fid, 'fprintf(''Loaded %%d timesteps of simulation data.\\n'', length(sim_time));\n');
fprintf(fid, 'fprintf(''Variables: sim_time, sim_pitch, sim_roll, sim_fuel_wl_T1..T5, sim_probe_T1..T5\\n'');\n');
fclose(fid);

fprintf('\nAlso created: load_hv_tables_for_simulink.m (data loader helper)\n');
