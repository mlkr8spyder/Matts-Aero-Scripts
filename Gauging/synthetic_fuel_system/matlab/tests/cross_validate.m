%% cross_validate.m
% Cross-validate MATLAB-generated H-V tables against Python-generated ones.
% Loads both .mat files and compares volumes at matching attitude conditions.

clear; clc;
fprintf('=== Cross-Validation: MATLAB vs Python H-V Tables ===\n\n');

data_dir = fullfile(fileparts(mfilename('fullpath')), '..', 'data');

%% Load Python-generated tables
py_file = fullfile(data_dir, 'tank_system.mat');
if ~exist(py_file, 'file')
    error('Python .mat file not found: %s\nRun: python -m src.hv_table_generator', py_file);
end
py = load(py_file);

%% Load MATLAB-generated tables
ml_file = fullfile(data_dir, 'tank_system_matlab.mat');
if ~exist(ml_file, 'file')
    error('MATLAB .mat file not found: %s\nRun generate_hv_tables.m first', ml_file);
end
ml = load(ml_file);

%% Compare pitch/roll ranges
assert(isequal(py.pitch_range(:)', ml.pitch_range(:)'), 'Pitch range mismatch');
assert(isequal(py.roll_range(:)', ml.roll_range(:)'), 'Roll range mismatch');
fprintf('Pitch/roll ranges match.\n');

n_pitch = length(py.pitch_range);
n_roll = length(py.roll_range);

%% Compare volumes for each tank at each attitude
max_err_pct = 0;
total_comparisons = 0;

for t = 1:5
    prefix = sprintf('T%d', t);
    py_vols = py.([prefix '_volumes']);
    ml_vols = ml.([prefix '_volumes']);

    tank_max_err = 0;

    for pi = 1:n_pitch
        for ri = 1:n_roll
            v_py = py_vols{pi, ri};
            v_ml = ml_vols{pi, ri};

            % Flatten
            v_py = v_py(:)';
            v_ml = v_ml(:)';

            % Compare at matching heights (they may have different lengths)
            n = min(length(v_py), length(v_ml));

            % Find max volume for normalization
            v_max = max(max(v_py), max(v_ml));
            if v_max < 1
                continue;
            end

            % Compare point by point
            for k = 1:n
                if v_py(k) > 10 && v_ml(k) > 10  % skip near-zero
                    err_pct = abs(v_py(k) - v_ml(k)) / v_max * 100;
                    tank_max_err = max(tank_max_err, err_pct);
                    max_err_pct = max(max_err_pct, err_pct);
                    total_comparisons = total_comparisons + 1;
                end
            end
        end
    end

    fprintf('T%d %8s: max volume error = %.4f%%\n', t, ml.([prefix '_name']), tank_max_err);
end

fprintf('\nTotal comparisons: %d\n', total_comparisons);
fprintf('Maximum error across all tanks/attitudes: %.4f%%\n', max_err_pct);

if max_err_pct < 1.0
    fprintf('\nPASS: MATLAB and Python tables agree within 1%%\n');
else
    fprintf('\nWARNING: Tables differ by more than 1%%. Investigate.\n');
end

%% Verify level-attitude gross volumes
fprintf('\n--- Level-Attitude Gross Volume Check ---\n');
pi_zero = find(py.pitch_range == 0);
ri_zero = find(py.roll_range == 0);

expected_gross = [14400, 36000, 40000, 36000, 30800];  % in^3

for t = 1:5
    prefix = sprintf('T%d', t);
    v_py = py.([prefix '_volumes']){pi_zero, ri_zero};
    v_ml = ml.([prefix '_volumes']){pi_zero, ri_zero};

    fprintf('T%d: Python max=%.0f, MATLAB max=%.0f, expected=%.0f in^3\n', ...
        t, max(v_py), max(v_ml), expected_gross(t));
end

fprintf('\nDone.\n');
