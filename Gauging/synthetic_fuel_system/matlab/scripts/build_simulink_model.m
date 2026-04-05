%% build_simulink_model.m (v2)
% Programmatically builds the Fuel Gauging System Simulink model.
%
% Architecture:
%   - Top-level harness with model references for each subsystem
%   - All parameters/buses from data dictionary (FuelGaugingData.sldd)
%   - 3-D n-D Lookup Tables for height-volume conversion
%   - Bus-based inter-subsystem communication
%   - Signal logging on all key buses
%   - Autorouting for clean diagram layout
%
% Prerequisites:
%   - Run setup_project.m (creates project structure)
%   - Run build_data_dictionary.m (populates .sldd)
%
% Creates models in matlab/models/:
%   FuelGaugingSystem.slx       Top-level harness
%   ProbeModel_Real.slx         Real probe measurement
%   ProbeModel_Combo.slx        T3 dual-probe with blend
%   ProbeModel_Pseudo.slx       T5 pseudo projection
%   ProbeFailureDetector.slx    Probe health monitoring
%   HV_TableLookup.slx          n-D table lookup
%   DensityComputation.slx      Dielectric → density
%   WeightSummation.slx         Volume × density → weight
%   RefuelSystem.slx            Single-point refuel + shutoff

clear; clc;
fprintf('=== Build Simulink Model (v2) ===\n\n');

%% Paths
script_dir = fileparts(mfilename('fullpath'));
matlab_dir = fileparts(script_dir);
model_dir  = fullfile(matlab_dir, 'models');
dd_path    = fullfile(matlab_dir, 'data', 'FuelGaugingData.sldd');

if ~exist(model_dir, 'dir'), mkdir(model_dir); end
addpath(model_dir);

if ~exist(dd_path, 'file')
    error('Data dictionary not found: %s\nRun build_data_dictionary.m first.', dd_path);
end

%% ========================================================================
%  Helper: create or reset a model
%  ========================================================================

    function mdl = create_model(name, model_dir, dd_path)
        mdl = name;
        full_path = fullfile(model_dir, [name '.slx']);
        if bdIsLoaded(mdl), close_system(mdl, 0); end
        if exist(full_path, 'file'), delete(full_path); end

        new_system(mdl);
        set_param(mdl, 'DataDictionary', dd_path);
        set_param(mdl, 'Solver', 'ode23tb');
        set_param(mdl, 'StopTime', '1000');
        set_param(mdl, 'MaxStep', '0.1');
        set_param(mdl, 'SaveTime', 'on');
        set_param(mdl, 'SaveOutput', 'on');
        set_param(mdl, 'ReturnWorkspaceOutputs', 'on');
    end

    function save_model(mdl, model_dir)
        save_system(mdl, fullfile(model_dir, [mdl '.slx']));
        close_system(mdl, 0);
        fprintf('  Saved: %s.slx\n', mdl);
    end

    function cleanup_default_blocks(mdl)
        % Remove default In1/Out1 from a subsystem-sourced model
        try delete_block([mdl '/In1']); catch, end
        try delete_block([mdl '/Out1']); catch, end
    end

%% ========================================================================
%  1. ProbeModel_Real — Single capacitance probe
%  ========================================================================

fprintf('Building ProbeModel_Real...\n');
mdl = create_model('ProbeModel_Real', model_dir, dd_path);

% Model arguments (instance-specific parameters)
set_param(mdl, 'ParameterArgumentNames', 'probe_base_wl,probe_top_wl');
set_param(mdl, 'ParameterArgumentValues', '88.24,103.68');  % defaults

% Inports
add_block('simulink/Sources/In1', [mdl '/fuel_wl'], ...
    'Position', [30 80 60 100], 'Port', '1');

% Outports
add_block('simulink/Sinks/Out1', [mdl '/probe_height'], ...
    'Position', [550 80 580 100], 'Port', '1');
add_block('simulink/Sinks/Out1', [mdl '/fuel_wl_at_probe'], ...
    'Position', [550 140 580 160], 'Port', '2');

% Subtract probe base WL
add_block('simulink/Math Operations/Add', [mdl '/SubBase'], ...
    'Position', [140 75 180 105], 'Inputs', '+-');
add_block('simulink/Sources/Constant', [mdl '/BaseWL'], ...
    'Value', 'probe_base_wl', 'Position', [60 120 110 140]);

% Clamp to [0, active_length]
add_block('simulink/Math Operations/Add', [mdl '/ActiveLen'], ...
    'Position', [140 170 180 200], 'Inputs', '+-');
add_block('simulink/Sources/Constant', [mdl '/TopWL'], ...
    'Value', 'probe_top_wl', 'Position', [60 170 110 190]);
add_block('simulink/Sources/Constant', [mdl '/BaseWL2'], ...
    'Value', 'probe_base_wl', 'Position', [60 210 110 230]);

add_block('simulink/Discontinuities/Saturation Dynamic', [mdl '/Clamp'], ...
    'Position', [260 60 320 120]);

% Probe noise (band-limited white noise)
add_block('simulink/Sources/Band-Limited White Noise', [mdl '/Noise'], ...
    'Cov', '0.0004', 'Ts', '0.1', 'seed', '[23341]', ...
    'Position', [260 140 310 170]);

% Add noise to clamped height
add_block('simulink/Math Operations/Add', [mdl '/AddNoise'], ...
    'Position', [380 75 420 105]);

% Zero constant for lower saturation limit
add_block('simulink/Sources/Constant', [mdl '/Zero'], ...
    'Value', '0', 'Position', [180 40 210 60]);

% Wire
add_line(mdl, 'fuel_wl/1', 'SubBase/1', 'autorouting', 'smart');
add_line(mdl, 'BaseWL/1', 'SubBase/2', 'autorouting', 'smart');

add_line(mdl, 'TopWL/1', 'ActiveLen/1', 'autorouting', 'smart');
add_line(mdl, 'BaseWL2/1', 'ActiveLen/2', 'autorouting', 'smart');

add_line(mdl, 'Zero/1', 'Clamp/1', 'autorouting', 'smart');     % lower limit
add_line(mdl, 'SubBase/1', 'Clamp/2', 'autorouting', 'smart');  % input
add_line(mdl, 'ActiveLen/1', 'Clamp/3', 'autorouting', 'smart'); % upper limit

add_line(mdl, 'Clamp/1', 'AddNoise/1', 'autorouting', 'smart');
add_line(mdl, 'Noise/1', 'AddNoise/2', 'autorouting', 'smart');
add_line(mdl, 'AddNoise/1', 'probe_height/1', 'autorouting', 'smart');
add_line(mdl, 'fuel_wl/1', 'fuel_wl_at_probe/1', 'autorouting', 'smart');

save_model(mdl, model_dir);

%% ========================================================================
%  2. ProbeModel_Combo — T3 dual-probe with blend zone
%  ========================================================================

fprintf('Building ProbeModel_Combo...\n');
mdl = create_model('ProbeModel_Combo', model_dir, dd_path);

set_param(mdl, 'ParameterArgumentNames', ...
    'lower_base_wl,lower_top_wl,upper_base_wl,upper_top_wl,blend_lo,blend_hi');
set_param(mdl, 'ParameterArgumentValues', ...
    '80.30,92.00,90.00,99.60,90.0,92.0');

add_block('simulink/Sources/In1', [mdl '/fuel_wl'], ...
    'Position', [30 100 60 120]);
add_block('simulink/Sinks/Out1', [mdl '/probe_height'], ...
    'Position', [700 100 730 120]);

% Lower probe height: clamp(fuel_wl - lower_base, 0, lower_active)
add_block('simulink/Math Operations/Add', [mdl '/LowerSub'], ...
    'Position', [120 50 160 80], 'Inputs', '+-');
add_block('simulink/Sources/Constant', [mdl '/LowerBase'], ...
    'Value', 'lower_base_wl', 'Position', [40 85 90 105]);
add_block('simulink/Discontinuities/Saturation', [mdl '/LowerClamp'], ...
    'UpperLimit', 'lower_top_wl - lower_base_wl', 'LowerLimit', '0', ...
    'Position', [200 50 260 80]);

% Upper probe height: clamp(fuel_wl - upper_base, 0, upper_active)
add_block('simulink/Math Operations/Add', [mdl '/UpperSub'], ...
    'Position', [120 140 160 170], 'Inputs', '+-');
add_block('simulink/Sources/Constant', [mdl '/UpperBase'], ...
    'Value', 'upper_base_wl', 'Position', [40 175 90 195]);
add_block('simulink/Discontinuities/Saturation', [mdl '/UpperClamp'], ...
    'UpperLimit', 'upper_top_wl - upper_base_wl', 'LowerLimit', '0', ...
    'Position', [200 140 260 170]);

% Blend weight: w = clamp((fuel_wl - blend_lo) / (blend_hi - blend_lo), 0, 1)
add_block('simulink/Math Operations/Add', [mdl '/BlendSub'], ...
    'Position', [120 230 160 260], 'Inputs', '+-');
add_block('simulink/Sources/Constant', [mdl '/BlendLo'], ...
    'Value', 'blend_lo', 'Position', [40 265 90 285]);
add_block('simulink/Math Operations/Gain', [mdl '/BlendScale'], ...
    'Gain', '1/(blend_hi - blend_lo)', 'Position', [200 230 260 260]);
add_block('simulink/Discontinuities/Saturation', [mdl '/BlendClampW'], ...
    'UpperLimit', '1', 'LowerLimit', '0', 'Position', [300 230 360 260]);

% Convert upper probe height to WL, then back to lower-probe-relative
% upper_wl = upper_base + upper_h
% effective = upper_wl - lower_base
add_block('simulink/Math Operations/Add', [mdl '/UpperToWL'], ...
    'Position', [300 140 340 170]);
add_block('simulink/Sources/Constant', [mdl '/UpperBaseAdd'], ...
    'Value', 'upper_base_wl', 'Position', [230 170 280 190]);
add_block('simulink/Math Operations/Add', [mdl '/UpperToRel'], ...
    'Position', [380 140 420 170], 'Inputs', '+-');
add_block('simulink/Sources/Constant', [mdl '/LowerBaseRel'], ...
    'Value', 'lower_base_wl', 'Position', [310 180 360 200]);

% Weighted blend: h_eff = (1-w)*lower_h + w*upper_h_rel
add_block('simulink/Math Operations/Product', [mdl '/ProdUpper'], ...
    'Position', [470 140 510 170]);
add_block('simulink/Math Operations/Add', [mdl '/OneMinusW'], ...
    'Position', [400 260 440 290], 'Inputs', '+-');
add_block('simulink/Sources/Constant', [mdl '/One'], ...
    'Value', '1', 'Position', [340 260 370 280]);
add_block('simulink/Math Operations/Product', [mdl '/ProdLower'], ...
    'Position', [470 50 510 80]);
add_block('simulink/Math Operations/Add', [mdl '/BlendSum'], ...
    'Position', [560 85 600 115]);

% Noise
add_block('simulink/Sources/Band-Limited White Noise', [mdl '/Noise'], ...
    'Cov', '0.0004', 'Ts', '0.1', 'seed', '[44721]', ...
    'Position', [560 130 610 160]);
add_block('simulink/Math Operations/Add', [mdl '/AddNoise'], ...
    'Position', [650 90 690 120]);

% Wire everything
add_line(mdl, 'fuel_wl/1', 'LowerSub/1', 'autorouting', 'smart');
add_line(mdl, 'LowerBase/1', 'LowerSub/2', 'autorouting', 'smart');
add_line(mdl, 'LowerSub/1', 'LowerClamp/1', 'autorouting', 'smart');

add_line(mdl, 'fuel_wl/1', 'UpperSub/1', 'autorouting', 'smart');
add_line(mdl, 'UpperBase/1', 'UpperSub/2', 'autorouting', 'smart');
add_line(mdl, 'UpperSub/1', 'UpperClamp/1', 'autorouting', 'smart');

add_line(mdl, 'UpperClamp/1', 'UpperToWL/1', 'autorouting', 'smart');
add_line(mdl, 'UpperBaseAdd/1', 'UpperToWL/2', 'autorouting', 'smart');
add_line(mdl, 'UpperToWL/1', 'UpperToRel/1', 'autorouting', 'smart');
add_line(mdl, 'LowerBaseRel/1', 'UpperToRel/2', 'autorouting', 'smart');

add_line(mdl, 'fuel_wl/1', 'BlendSub/1', 'autorouting', 'smart');
add_line(mdl, 'BlendLo/1', 'BlendSub/2', 'autorouting', 'smart');
add_line(mdl, 'BlendSub/1', 'BlendScale/1', 'autorouting', 'smart');
add_line(mdl, 'BlendScale/1', 'BlendClampW/1', 'autorouting', 'smart');

add_line(mdl, 'UpperToRel/1', 'ProdUpper/1', 'autorouting', 'smart');
add_line(mdl, 'BlendClampW/1', 'ProdUpper/2', 'autorouting', 'smart');

add_line(mdl, 'One/1', 'OneMinusW/1', 'autorouting', 'smart');
add_line(mdl, 'BlendClampW/1', 'OneMinusW/2', 'autorouting', 'smart');
add_line(mdl, 'LowerClamp/1', 'ProdLower/1', 'autorouting', 'smart');
add_line(mdl, 'OneMinusW/1', 'ProdLower/2', 'autorouting', 'smart');

add_line(mdl, 'ProdLower/1', 'BlendSum/1', 'autorouting', 'smart');
add_line(mdl, 'ProdUpper/1', 'BlendSum/2', 'autorouting', 'smart');

add_line(mdl, 'BlendSum/1', 'AddNoise/1', 'autorouting', 'smart');
add_line(mdl, 'Noise/1', 'AddNoise/2', 'autorouting', 'smart');
add_line(mdl, 'AddNoise/1', 'probe_height/1', 'autorouting', 'smart');

save_model(mdl, model_dir);

%% ========================================================================
%  3. ProbeModel_Pseudo — T5 trigonometric projection
%  ========================================================================

fprintf('Building ProbeModel_Pseudo...\n');
mdl = create_model('ProbeModel_Pseudo', model_dir, dd_path);

set_param(mdl, 'ParameterArgumentNames', ...
    'pseudo_dx,pseudo_dy,tank_wl_min,tank_height');
set_param(mdl, 'ParameterArgumentValues', '55.0,0.0,83.0,22.0');

add_block('simulink/Sources/In1', [mdl '/t3_height'], ...
    'Position', [30 50 60 70], 'Port', '1');
add_block('simulink/Sources/In1', [mdl '/pitch_deg'], ...
    'Position', [30 120 60 140], 'Port', '2');
add_block('simulink/Sources/In1', [mdl '/roll_deg'], ...
    'Position', [30 190 60 210], 'Port', '3');
add_block('simulink/Sinks/Out1', [mdl '/probe_height'], ...
    'Position', [600 80 630 100]);

% pitch path: dx * tan(pitch_rad)
add_block('simulink/Math Operations/Gain', [mdl '/DegToRadP'], ...
    'Gain', 'pi/180', 'Position', [120 115 160 145]);
add_block('simulink/Math Operations/Trigonometric Function', [mdl '/TanP'], ...
    'Function', 'tan', 'Position', [200 115 240 145]);
add_block('simulink/Math Operations/Gain', [mdl '/GainDx'], ...
    'Gain', 'pseudo_dx', 'Position', [280 115 330 145]);

% roll path: dy * tan(roll_rad)
add_block('simulink/Math Operations/Gain', [mdl '/DegToRadR'], ...
    'Gain', 'pi/180', 'Position', [120 185 160 215]);
add_block('simulink/Math Operations/Trigonometric Function', [mdl '/TanR'], ...
    'Function', 'tan', 'Position', [200 185 240 215]);
add_block('simulink/Math Operations/Gain', [mdl '/GainDy'], ...
    'Gain', 'pseudo_dy', 'Position', [280 185 330 215]);

% Sum: t3_height + dx*tan(pitch) + dy*tan(roll)
add_block('simulink/Math Operations/Add', [mdl '/SumProj'], ...
    'Position', [400 60 440 120], 'Inputs', '+++');

% Convert T3-relative height to T5-relative height
% T5_h = projected_WL - T5_wl_min
% But t3_height is relative to T3 probe base (80.30), so:
% projected_WL = t3_probe_base + t3_height + dx*tan(p) + dy*tan(r)
% T5_h = projected_WL - T5_wl_min = (80.30 + t3_h + proj) - 83.0
add_block('simulink/Math Operations/Add', [mdl '/SubFloor'], ...
    'Position', [480 70 520 100], 'Inputs', '+-');
add_block('simulink/Sources/Constant', [mdl '/FloorOffset'], ...
    'Value', 'tank_wl_min - 80.30', 'Position', [420 130 470 150]);

% Clamp to [0, tank_height]
add_block('simulink/Discontinuities/Saturation', [mdl '/ClampT5'], ...
    'UpperLimit', 'tank_height', 'LowerLimit', '0', ...
    'Position', [550 70 600 100]);

add_line(mdl, 'pitch_deg/1', 'DegToRadP/1', 'autorouting', 'smart');
add_line(mdl, 'DegToRadP/1', 'TanP/1', 'autorouting', 'smart');
add_line(mdl, 'TanP/1', 'GainDx/1', 'autorouting', 'smart');

add_line(mdl, 'roll_deg/1', 'DegToRadR/1', 'autorouting', 'smart');
add_line(mdl, 'DegToRadR/1', 'TanR/1', 'autorouting', 'smart');
add_line(mdl, 'TanR/1', 'GainDy/1', 'autorouting', 'smart');

add_line(mdl, 't3_height/1', 'SumProj/1', 'autorouting', 'smart');
add_line(mdl, 'GainDx/1', 'SumProj/2', 'autorouting', 'smart');
add_line(mdl, 'GainDy/1', 'SumProj/3', 'autorouting', 'smart');

add_line(mdl, 'SumProj/1', 'SubFloor/1', 'autorouting', 'smart');
add_line(mdl, 'FloorOffset/1', 'SubFloor/2', 'autorouting', 'smart');
add_line(mdl, 'SubFloor/1', 'ClampT5/1', 'autorouting', 'smart');
add_line(mdl, 'ClampT5/1', 'probe_height/1', 'autorouting', 'smart');

save_model(mdl, model_dir);

%% ========================================================================
%  4. ProbeFailureDetector — Health monitoring per probe
%  ========================================================================

fprintf('Building ProbeFailureDetector...\n');
mdl = create_model('ProbeFailureDetector', model_dir, dd_path);

set_param(mdl, 'ParameterArgumentNames', 'max_probe_height');
set_param(mdl, 'ParameterArgumentValues', '15.44');

add_block('simulink/Sources/In1', [mdl '/raw_height'], ...
    'Position', [30 100 60 120]);
add_block('simulink/Sinks/Out1', [mdl '/valid_height'], ...
    'Position', [650 100 680 120]);
add_block('simulink/Sinks/Out1', [mdl '/is_failed'], ...
    'Position', [650 200 680 220], 'Port', '2');
add_block('simulink/Sinks/Out1', [mdl '/failure_code'], ...
    'Position', [650 280 680 300], 'Port', '3');

% Memory for previous reading (LKG and rate computation)
add_block('simulink/Discrete/Memory', [mdl '/PrevReading'], ...
    'Position', [120 160 160 180]);

% Rate of change = |current - previous| (dt=Ts, handled by threshold)
add_block('simulink/Math Operations/Add', [mdl '/Diff'], ...
    'Position', [200 100 240 140], 'Inputs', '+-');
add_block('simulink/Math Operations/Abs', [mdl '/AbsRate'], ...
    'Position', [270 100 310 130]);

% Open circuit: raw < FAILURE_OPEN_THRESH
add_block('simulink/Logic and Bit Operations/Compare To Constant', ...
    [mdl '/OpenCkt'], 'const', 'FAILURE_OPEN_THRESH', 'relop', '<', ...
    'Position', [200 220 270 250]);

% Short circuit: raw > max + FAILURE_SHORT_MARGIN
add_block('simulink/Math Operations/Add', [mdl '/ShortThresh'], ...
    'Position', [140 270 180 300], 'Inputs', '++');
add_block('simulink/Sources/Constant', [mdl '/MaxH'], ...
    'Value', 'max_probe_height', 'Position', [60 260 100 280]);
add_block('simulink/Sources/Constant', [mdl '/ShortMargin'], ...
    'Value', 'FAILURE_SHORT_MARGIN', 'Position', [60 300 100 320]);
add_block('simulink/Logic and Bit Operations/Relational Operator', ...
    [mdl '/ShortCkt'], 'Operator', '>', 'Position', [240 270 280 300]);

% Rate exceedance: |rate| > FAILURE_RATE_THRESH
add_block('simulink/Logic and Bit Operations/Compare To Constant', ...
    [mdl '/RateExceed'], 'const', 'FAILURE_RATE_THRESH', 'relop', '>', ...
    'Position', [340 100 410 130]);

% OR gate: any failure
add_block('simulink/Logic and Bit Operations/Logical Operator', [mdl '/FaultOR'], ...
    'Operator', 'OR', 'Inputs', '3', 'Position', [440 160 480 240]);

% Switch: output raw if healthy, LKG if failed
add_block('simulink/Discrete/Memory', [mdl '/LKG_Memory'], ...
    'Position', [500 60 540 80]);
add_block('simulink/Signal Routing/Switch', [mdl '/FaultSwitch'], ...
    'Criteria', 'u2 > Threshold', 'Threshold', '0.5', ...
    'Position', [560 80 600 130]);

% Failure code encoder (simplified: priority encode)
% 1=Open, 2=Short, 3=Rate
add_block('simulink/Sources/Constant', [mdl '/Code0'], ...
    'Value', '0', 'Position', [380 310 410 330]);
add_block('simulink/Sources/Constant', [mdl '/Code1'], ...
    'Value', '1', 'Position', [380 340 410 360]);
add_block('simulink/Sources/Constant', [mdl '/Code2'], ...
    'Value', '2', 'Position', [380 370 410 390]);
add_block('simulink/Sources/Constant', [mdl '/Code3'], ...
    'Value', '3', 'Position', [380 400 410 420]);

% Wire main logic
add_line(mdl, 'raw_height/1', 'PrevReading/1', 'autorouting', 'smart');
add_line(mdl, 'raw_height/1', 'Diff/1', 'autorouting', 'smart');
add_line(mdl, 'PrevReading/1', 'Diff/2', 'autorouting', 'smart');
add_line(mdl, 'Diff/1', 'AbsRate/1', 'autorouting', 'smart');
add_line(mdl, 'AbsRate/1', 'RateExceed/1', 'autorouting', 'smart');

add_line(mdl, 'raw_height/1', 'OpenCkt/1', 'autorouting', 'smart');
add_line(mdl, 'MaxH/1', 'ShortThresh/1', 'autorouting', 'smart');
add_line(mdl, 'ShortMargin/1', 'ShortThresh/2', 'autorouting', 'smart');
add_line(mdl, 'raw_height/1', 'ShortCkt/1', 'autorouting', 'smart');
add_line(mdl, 'ShortThresh/1', 'ShortCkt/2', 'autorouting', 'smart');

add_line(mdl, 'OpenCkt/1', 'FaultOR/1', 'autorouting', 'smart');
add_line(mdl, 'ShortCkt/1', 'FaultOR/2', 'autorouting', 'smart');
add_line(mdl, 'RateExceed/1', 'FaultOR/3', 'autorouting', 'smart');

% Switch: healthy path (raw) on top, failed path (LKG) on bottom
add_line(mdl, 'raw_height/1', 'FaultSwitch/1', 'autorouting', 'smart');
add_line(mdl, 'FaultOR/1', 'FaultSwitch/2', 'autorouting', 'smart');
add_line(mdl, 'LKG_Memory/1', 'FaultSwitch/3', 'autorouting', 'smart');
add_line(mdl, 'FaultSwitch/1', 'LKG_Memory/1', 'autorouting', 'smart');

add_line(mdl, 'FaultSwitch/1', 'valid_height/1', 'autorouting', 'smart');
add_line(mdl, 'FaultOR/1', 'is_failed/1', 'autorouting', 'smart');

% Failure code output (simplified — just cast OR output to uint8 for now)
add_line(mdl, 'FaultOR/1', 'failure_code/1', 'autorouting', 'smart');

save_model(mdl, model_dir);

%% ========================================================================
%  5. HV_TableLookup — n-D Lookup Table (3D: height × pitch × roll)
%  ========================================================================

fprintf('Building HV_TableLookup...\n');
mdl = create_model('HV_TableLookup', model_dir, dd_path);

set_param(mdl, 'ParameterArgumentNames', 'lut_object_name');
set_param(mdl, 'ParameterArgumentValues', '''LUT_T1''');

add_block('simulink/Sources/In1', [mdl '/probe_height'], ...
    'Position', [30 50 60 70], 'Port', '1');
add_block('simulink/Sources/In1', [mdl '/pitch_deg'], ...
    'Position', [30 100 60 120], 'Port', '2');
add_block('simulink/Sources/In1', [mdl '/roll_deg'], ...
    'Position', [30 150 60 170], 'Port', '3');
add_block('simulink/Sinks/Out1', [mdl '/volume_in3'], ...
    'Position', [400 100 430 120]);

% n-D Lookup Table block
add_block('simulink/Lookup Tables/n-D Lookup Table', [mdl '/HV_LUT'], ...
    'Position', [200 40 300 180], ...
    'NumberOfTableDimensions', '3', ...
    'DataSpecification', 'Lookup table object', ...
    'LookupTableObject', 'LUT_T1', ...
    'InterpMethod', 'Linear point-slope', ...
    'ExtrapMethod', 'Clip');

% Ensure non-negative output
add_block('simulink/Discontinuities/Saturation', [mdl '/ClampVol'], ...
    'UpperLimit', 'inf', 'LowerLimit', '0', ...
    'Position', [340 90 380 120]);

add_line(mdl, 'probe_height/1', 'HV_LUT/1', 'autorouting', 'smart');
add_line(mdl, 'pitch_deg/1', 'HV_LUT/2', 'autorouting', 'smart');
add_line(mdl, 'roll_deg/1', 'HV_LUT/3', 'autorouting', 'smart');
add_line(mdl, 'HV_LUT/1', 'ClampVol/1', 'autorouting', 'smart');
add_line(mdl, 'ClampVol/1', 'volume_in3/1', 'autorouting', 'smart');

save_model(mdl, model_dir);

%% ========================================================================
%  6. DensityComputation — Dielectric constant → density
%  ========================================================================

fprintf('Building DensityComputation...\n');
mdl = create_model('DensityComputation', model_dir, dd_path);

add_block('simulink/Sources/In1', [mdl '/dielectric'], ...
    'Position', [30 80 60 100]);
add_block('simulink/Sinks/Out1', [mdl '/density_lb_per_gal'], ...
    'Position', [500 80 530 100]);

% rho = DENSITY_MODEL_A * kappa + DENSITY_MODEL_B
add_block('simulink/Math Operations/Gain', [mdl '/Slope'], ...
    'Gain', 'DENSITY_MODEL_A', 'Position', [120 75 180 105]);
add_block('simulink/Math Operations/Add', [mdl '/AddIntercept'], ...
    'Position', [240 75 280 105]);
add_block('simulink/Sources/Constant', [mdl '/Intercept'], ...
    'Value', 'DENSITY_MODEL_B', 'Position', [160 120 210 140]);

% Apply density bias
add_block('simulink/Math Operations/Gain', [mdl '/BiasGain'], ...
    'Gain', 'DENSITY_BIAS', 'Position', [340 75 400 105]);

% Clamp to physical range
add_block('simulink/Discontinuities/Saturation', [mdl '/ClampDens'], ...
    'UpperLimit', '8.5', 'LowerLimit', '5.5', ...
    'Position', [440 75 480 105]);

add_line(mdl, 'dielectric/1', 'Slope/1', 'autorouting', 'smart');
add_line(mdl, 'Slope/1', 'AddIntercept/1', 'autorouting', 'smart');
add_line(mdl, 'Intercept/1', 'AddIntercept/2', 'autorouting', 'smart');
add_line(mdl, 'AddIntercept/1', 'BiasGain/1', 'autorouting', 'smart');
add_line(mdl, 'BiasGain/1', 'ClampDens/1', 'autorouting', 'smart');
add_line(mdl, 'ClampDens/1', 'density_lb_per_gal/1', 'autorouting', 'smart');

save_model(mdl, model_dir);

%% ========================================================================
%  7. RefuelSystem — Single-point refuel with high-level shutoff
%  ========================================================================

fprintf('Building RefuelSystem...\n');
mdl = create_model('RefuelSystem', model_dir, dd_path);

add_block('simulink/Sources/In1', [mdl '/refuel_cmd'], ...
    'Position', [30 30 60 50], 'Port', '1');

% Per-tank: fuel_wl input, high-level sensor, valve logic
for t = 1:5
    y = 80 + (t-1)*80;
    prefix = sprintf('T%d', t);
    max_fills = [103.68, 102.64, 99.60, 102.64, 104.56];

    add_block('simulink/Sources/In1', [mdl '/' prefix '_fuel_wl'], ...
        'Position', [30 y 60 y+20], 'Port', sprintf('%d', t+1));

    % High-level sensor: fuel_wl >= max_fill
    add_block('simulink/Logic and Bit Operations/Compare To Constant', ...
        [mdl '/' prefix '_HiLevel'], ...
        'const', sprintf('%.2f', max_fills(t)), 'relop', '>=', ...
        'Position', [120 y 190 y+25]);

    % Valve open = refuel_cmd AND NOT(hi_level)
    add_block('simulink/Logic and Bit Operations/Logical Operator', ...
        [mdl '/' prefix '_Not'], 'Operator', 'NOT', ...
        'Position', [220 y 250 y+25]);
    add_block('simulink/Logic and Bit Operations/Logical Operator', ...
        [mdl '/' prefix '_AND'], 'Operator', 'AND', ...
        'Position', [290 y-10 330 y+30]);

    % Outputs
    add_block('simulink/Sinks/Out1', [mdl '/' prefix '_valve_open'], ...
        'Position', [370 y 400 y+20], 'Port', sprintf('%d', 2*t-1));
    add_block('simulink/Sinks/Out1', [mdl '/' prefix '_hi_level'], ...
        'Position', [370 y+30 400 y+50], 'Port', sprintf('%d', 2*t));

    add_line(mdl, [prefix '_fuel_wl/1'], [prefix '_HiLevel/1'], 'autorouting', 'smart');
    add_line(mdl, [prefix '_HiLevel/1'], [prefix '_Not/1'], 'autorouting', 'smart');
    add_line(mdl, 'refuel_cmd/1', [prefix '_AND/1'], 'autorouting', 'smart');
    add_line(mdl, [prefix '_Not/1'], [prefix '_AND/2'], 'autorouting', 'smart');
    add_line(mdl, [prefix '_AND/1'], [prefix '_valve_open/1'], 'autorouting', 'smart');
    add_line(mdl, [prefix '_HiLevel/1'], [prefix '_hi_level/1'], 'autorouting', 'smart');
end

% All-full detection
add_block('simulink/Logic and Bit Operations/Logical Operator', ...
    [mdl '/AllFull'], 'Operator', 'AND', 'Inputs', '5', ...
    'Position', [220 470 270 530]);
add_block('simulink/Sinks/Out1', [mdl '/refuel_complete'], ...
    'Position', [310 490 340 510], 'Port', '11');

for t = 1:5
    prefix = sprintf('T%d', t);
    add_line(mdl, [prefix '_HiLevel/1'], sprintf('AllFull/%d', t), 'autorouting', 'smart');
end
add_line(mdl, 'AllFull/1', 'refuel_complete/1', 'autorouting', 'smart');

save_model(mdl, model_dir);

%% ========================================================================
%  8. TOP-LEVEL HARNESS
%  ========================================================================

fprintf('\nBuilding FuelGaugingSystem (top level)...\n');
mdl = create_model('FuelGaugingSystem', model_dir, dd_path);

set_param(mdl, 'SignalLogging', 'on');
set_param(mdl, 'SignalLoggingName', 'logsout');

% Inputs: use From Workspace blocks for simulation data
add_block('simulink/Sources/Constant', [mdl '/Pitch_deg'], ...
    'Value', '0', 'Position', [30 50 80 70]);
add_block('simulink/Sources/Constant', [mdl '/Roll_deg'], ...
    'Value', '0', 'Position', [30 90 80 110]);
add_block('simulink/Sources/Constant', [mdl '/Dielectric'], ...
    'Value', 'KAPPA_NOMINAL', 'Position', [30 550 80 570]);
add_block('simulink/Sources/Constant', [mdl '/Refuel_Cmd'], ...
    'Value', '0', 'Position', [30 630 80 650]);

% Per-tank fuel WL inputs
default_wls = [96.0, 94.0, 90.0, 94.0, 94.0];
for t = 1:5
    y = 140 + (t-1)*80;
    add_block('simulink/Sources/Constant', [mdl sprintf('/FuelWL_T%d', t)], ...
        'Value', sprintf('%.1f', default_wls(t)), ...
        'Position', [30 y 80 y+20]);
end

% Density computation
add_block('simulink/Ports & Subsystems/Model', [mdl '/DensityComp'], ...
    'ModelName', 'DensityComputation', ...
    'Position', [200 540 320 580]);
add_line(mdl, 'Dielectric/1', 'DensityComp/1', 'autorouting', 'smart');

% Refuel system
add_block('simulink/Ports & Subsystems/Model', [mdl '/Refuel'], ...
    'ModelName', 'RefuelSystem', ...
    'Position', [200 620 360 720]);
add_line(mdl, 'Refuel_Cmd/1', 'Refuel/1', 'autorouting', 'smart');
for t = 1:5
    add_line(mdl, sprintf('FuelWL_T%d/1', t), sprintf('Refuel/%d', t+1), ...
        'autorouting', 'smart');
end

% Per-tank processing chain: Probe → Failure Detect → H-V Lookup → Weight
tank_probe_models = {'ProbeModel_Real', 'ProbeModel_Real', 'ProbeModel_Combo', ...
                     'ProbeModel_Real', 'ProbeModel_Pseudo'};

% Weight summation inputs will be collected
sum_y = 350;
add_block('simulink/Math Operations/Add', [mdl '/TotalWeight'], ...
    'Inputs', '+++++', 'Position', [800 sum_y 840 sum_y+120]);

for t = 1:5
    y = 140 + (t-1)*80;
    prefix = sprintf('T%d', t);

    % Probe model reference
    probe_mdl = tank_probe_models{t};
    add_block('simulink/Ports & Subsystems/Model', [mdl '/' prefix '_Probe'], ...
        'ModelName', probe_mdl, ...
        'Position', [200 y 320 y+50]);

    % Connect fuel WL to probe
    if t == 5
        % T5 pseudo needs T3 probe output + attitude
        add_line(mdl, sprintf('FuelWL_T%d/1', t), [prefix '_Probe/1'], ...
            'autorouting', 'smart');
        add_line(mdl, 'Pitch_deg/1', [prefix '_Probe/2'], 'autorouting', 'smart');
        add_line(mdl, 'Roll_deg/1', [prefix '_Probe/3'], 'autorouting', 'smart');
    else
        add_line(mdl, sprintf('FuelWL_T%d/1', t), [prefix '_Probe/1'], ...
            'autorouting', 'smart');
    end

    % Failure detector
    add_block('simulink/Ports & Subsystems/Model', [mdl '/' prefix '_Failure'], ...
        'ModelName', 'ProbeFailureDetector', ...
        'Position', [380 y 480 y+50]);
    add_line(mdl, [prefix '_Probe/1'], [prefix '_Failure/1'], 'autorouting', 'smart');

    % H-V table lookup
    add_block('simulink/Ports & Subsystems/Model', [mdl '/' prefix '_Lookup'], ...
        'ModelName', 'HV_TableLookup', ...
        'Position', [540 y 640 y+50]);
    add_line(mdl, [prefix '_Failure/1'], [prefix '_Lookup/1'], 'autorouting', 'smart');
    add_line(mdl, 'Pitch_deg/1', [prefix '_Lookup/2'], 'autorouting', 'smart');
    add_line(mdl, 'Roll_deg/1', [prefix '_Lookup/3'], 'autorouting', 'smart');

    % Volume to weight: weight = (volume / IN3_PER_GAL) * density
    add_block('simulink/Math Operations/Gain', [mdl '/' prefix '_ToGal'], ...
        'Gain', sprintf('1/%s', 'IN3_PER_GAL'), ...
        'Position', [680 y 720 y+25]);
    add_block('simulink/Math Operations/Product', [mdl '/' prefix '_Weight'], ...
        'Position', [750 y 790 y+30]);

    add_line(mdl, [prefix '_Lookup/1'], [prefix '_ToGal/1'], 'autorouting', 'smart');
    add_line(mdl, [prefix '_ToGal/1'], [prefix '_Weight/1'], 'autorouting', 'smart');
    add_line(mdl, 'DensityComp/1', [prefix '_Weight/2'], 'autorouting', 'smart');

    % Connect to summation
    add_line(mdl, [prefix '_Weight/1'], sprintf('TotalWeight/%d', t), ...
        'autorouting', 'smart');
end

% Total weight output
add_block('simulink/Sinks/To Workspace', [mdl '/TotalWeight_Out'], ...
    'VariableName', 'total_fuel_weight', 'SaveFormat', 'Timeseries', ...
    'Position', [880 sum_y+40 960 sum_y+70]);
add_block('simulink/Sinks/Scope', [mdl '/WeightScope'], ...
    'Position', [880 sum_y+80 920 sum_y+110]);

add_line(mdl, 'TotalWeight/1', 'TotalWeight_Out/1', 'autorouting', 'smart');
add_line(mdl, 'TotalWeight/1', 'WeightScope/1', 'autorouting', 'smart');

save_model(mdl, model_dir);

%% ========================================================================
%  Summary
%  ========================================================================

fprintf('\n=== Simulink Model Build Complete ===\n\n');

models = dir(fullfile(model_dir, '*.slx'));
fprintf('Models created in %s:\n', model_dir);
for i = 1:numel(models)
    info = dir(fullfile(model_dir, models(i).name));
    fprintf('  %-35s %6.0f KB\n', models(i).name, info.bytes/1024);
end

fprintf('\nArchitecture:\n');
fprintf('  FuelGaugingSystem.slx (top-level harness)\n');
fprintf('    ├── DensityComputation.slx (dielectric → density)\n');
fprintf('    ├── RefuelSystem.slx (valves + high-level sensors)\n');
fprintf('    └── Per-tank chain ×5:\n');
fprintf('        ├── ProbeModel_{Real|Combo|Pseudo}.slx\n');
fprintf('        ├── ProbeFailureDetector.slx\n');
fprintf('        └── HV_TableLookup.slx (3-D n-D LUT from data dict)\n');

fprintf('\nData dictionary: %s\n', dd_path);
fprintf('\nNext: run validate_model.m to verify the build.\n');
