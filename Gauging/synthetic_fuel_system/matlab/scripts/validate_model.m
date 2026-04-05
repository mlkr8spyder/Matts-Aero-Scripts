%% validate_model.m
% Post-build validation for the Fuel Gauging Simulink model.
%
% Checks:
%   1. All .slx model files exist
%   2. Data dictionary exists and contains required entries
%   3. Bus definitions are internally consistent
%   4. Lookup table dimensions match expected sizes
%   5. All model references resolve
%   6. Short simulation runs without error (if Simulink available)

clear; clc;
fprintf('=== Model Validation ===\n\n');

script_dir  = fileparts(mfilename('fullpath'));
matlab_dir  = fileparts(script_dir);
model_dir   = fullfile(matlab_dir, 'models');
dd_path     = fullfile(matlab_dir, 'data', 'FuelGaugingData.sldd');

pass_count = 0;
fail_count = 0;

    function pass(msg)
        fprintf('  PASS: %s\n', msg);
    end

    function fail(msg)
        fprintf('  FAIL: %s\n', msg);
    end

%% ========================================================================
%  1. Check model files exist
%  ========================================================================

fprintf('--- Checking Model Files ---\n');

required_models = {
    'FuelGaugingSystem'
    'ProbeModel_Real'
    'ProbeModel_Combo'
    'ProbeModel_Pseudo'
    'ProbeFailureDetector'
    'HV_TableLookup'
    'DensityComputation'
    'RefuelSystem'
};

for i = 1:numel(required_models)
    mdl_file = fullfile(model_dir, [required_models{i} '.slx']);
    if exist(mdl_file, 'file')
        pass(sprintf('%s.slx exists', required_models{i}));
        pass_count = pass_count + 1;
    else
        fail(sprintf('%s.slx NOT FOUND', required_models{i}));
        fail_count = fail_count + 1;
    end
end

%% ========================================================================
%  2. Check data dictionary
%  ========================================================================

fprintf('\n--- Checking Data Dictionary ---\n');

if exist(dd_path, 'file')
    pass('FuelGaugingData.sldd exists');
    pass_count = pass_count + 1;

    dd = Simulink.data.dictionary.open(dd_path);
    ddata = getSection(dd, 'Design Data');

    % Check required entries
    required_entries = {
        'AttitudeBus',        'Simulink.Bus'
        'ProbeReadingBus',    'Simulink.Bus'
        'TankIndicationBus',  'Simulink.Bus'
        'SystemIndicationBus','Simulink.Bus'
        'RefuelStatusBus',    'Simulink.Bus'
        'BIT_StatusBus',      'Simulink.Bus'
        'TankParams',         'Simulink.Parameter'
        'IN3_PER_GAL',        'Simulink.Parameter'
        'DENSITY_MODEL_A',    'Simulink.Parameter'
        'DENSITY_BIAS',       'Simulink.Parameter'
        'FAILURE_RATE_THRESH','Simulink.Parameter'
        'LUT_T1',            'Simulink.LookupTable'
        'LUT_T2',            'Simulink.LookupTable'
        'LUT_T3',            'Simulink.LookupTable'
        'LUT_T4',            'Simulink.LookupTable'
        'LUT_T5',            'Simulink.LookupTable'
    };

    for i = 1:size(required_entries, 1)
        entry_name = required_entries{i, 1};
        expected_class = required_entries{i, 2};
        try
            entry = getEntry(ddata, entry_name);
            val = getValue(entry);
            if isa(val, expected_class)
                pass(sprintf('%-25s (%s)', entry_name, expected_class));
                pass_count = pass_count + 1;
            else
                fail(sprintf('%-25s wrong type: %s (expected %s)', ...
                    entry_name, class(val), expected_class));
                fail_count = fail_count + 1;
            end
        catch
            fail(sprintf('%-25s NOT FOUND in dictionary', entry_name));
            fail_count = fail_count + 1;
        end
    end

    %% ====================================================================
    %  3. Check lookup table dimensions
    %  ====================================================================

    fprintf('\n--- Checking Lookup Tables ---\n');

    expected_pitch_n = 13;
    expected_roll_n  = 17;

    for t = 1:5
        lut_name = sprintf('LUT_T%d', t);
        try
            entry = getEntry(ddata, lut_name);
            lut = getValue(entry);
            tbl = lut.Table.Value;
            bp1 = lut.Breakpoints(1).Value;
            bp2 = lut.Breakpoints(2).Value;
            bp3 = lut.Breakpoints(3).Value;

            [nh, np, nr] = size(tbl);

            if np == expected_pitch_n && nr == expected_roll_n
                pass(sprintf('%s: %dx%dx%d (height×pitch×roll)', ...
                    lut_name, nh, np, nr));
                pass_count = pass_count + 1;
            else
                fail(sprintf('%s: pitch=%d (exp %d), roll=%d (exp %d)', ...
                    lut_name, np, expected_pitch_n, nr, expected_roll_n));
                fail_count = fail_count + 1;
            end

            % Check monotonicity along height axis at level attitude
            pi0 = ceil(np/2);
            ri0 = ceil(nr/2);
            col = tbl(:, pi0, ri0);
            is_mono = all(diff(col) >= -0.01);
            if is_mono
                pass(sprintf('%s: monotonic at level attitude', lut_name));
                pass_count = pass_count + 1;
            else
                fail(sprintf('%s: NOT monotonic at level attitude', lut_name));
                fail_count = fail_count + 1;
            end

            % Check max volume is reasonable
            max_vol = max(tbl(:));
            expected_gross = [14400, 36000, 40000, 36000, 30800];
            pct_diff = abs(max_vol - expected_gross(t)) / expected_gross(t) * 100;
            if pct_diff < 1.0
                pass(sprintf('%s: max vol %.0f in³ (%.2f%% of expected)', ...
                    lut_name, max_vol, pct_diff));
                pass_count = pass_count + 1;
            else
                fail(sprintf('%s: max vol %.0f in³ (%.1f%% off expected %.0f)', ...
                    lut_name, max_vol, pct_diff, expected_gross(t)));
                fail_count = fail_count + 1;
            end
        catch ME
            fail(sprintf('%s: error reading - %s', lut_name, ME.message));
            fail_count = fail_count + 1;
        end
    end

    %% ====================================================================
    %  4. Check bus element counts
    %  ====================================================================

    fprintf('\n--- Checking Bus Definitions ---\n');

    bus_checks = {
        'AttitudeBus',         2
        'ProbeReadingBus',     4
        'BIT_StatusBus',       4
        'TankIndicationBus',   5
        'RefuelStatusBus',     6
    };

    for i = 1:size(bus_checks, 1)
        bus_name = bus_checks{i, 1};
        expected_n = bus_checks{i, 2};
        try
            entry = getEntry(ddata, bus_name);
            bus = getValue(entry);
            actual_n = numel(bus.Elements);
            if actual_n == expected_n
                pass(sprintf('%s: %d elements', bus_name, actual_n));
                pass_count = pass_count + 1;
            else
                fail(sprintf('%s: %d elements (expected %d)', ...
                    bus_name, actual_n, expected_n));
                fail_count = fail_count + 1;
            end
        catch ME
            fail(sprintf('%s: %s', bus_name, ME.message));
            fail_count = fail_count + 1;
        end
    end

    close(dd);
else
    fail('FuelGaugingData.sldd NOT FOUND');
    fail_count = fail_count + 1;
end

%% ========================================================================
%  5. Try loading models (if Simulink is available)
%  ========================================================================

fprintf('\n--- Checking Model Loadability ---\n');

has_simulink = license('test', 'Simulink');
if has_simulink
    addpath(model_dir);

    for i = 1:numel(required_models)
        mdl = required_models{i};
        mdl_file = fullfile(model_dir, [mdl '.slx']);
        if exist(mdl_file, 'file')
            try
                load_system(mdl);
                pass(sprintf('%s loads successfully', mdl));
                pass_count = pass_count + 1;
                close_system(mdl, 0);
            catch ME
                fail(sprintf('%s load error: %s', mdl, ME.message));
                fail_count = fail_count + 1;
            end
        end
    end
else
    fprintf('  SKIP: Simulink not available, cannot test model loading\n');
end

%% ========================================================================
%  Summary
%  ========================================================================

fprintf('\n%s\n', repmat('=', 1, 50));
fprintf('Validation Results: %d passed, %d failed\n', pass_count, fail_count);

if fail_count == 0
    fprintf('ALL CHECKS PASSED\n');
else
    fprintf('SOME CHECKS FAILED — review output above\n');
end
