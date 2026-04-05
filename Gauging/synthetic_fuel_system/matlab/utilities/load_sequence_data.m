function [sim_input, metadata] = load_sequence_data(sequence_type, data_dir)
%LOAD_SEQUENCE_DATA Load defuel or refuel sequence data for Simulink.
%
%   [sim_input, metadata] = load_sequence_data('defuel')
%   [sim_input, metadata] = load_sequence_data('refuel', custom_data_dir)
%
%   Loads a .mat sequence file and converts it into Simulink-compatible
%   timeseries objects for use with From Workspace blocks.
%
%   Outputs:
%     sim_input  - struct with timeseries fields:
%                   .time, .pitch, .roll, .dielectric
%                   .fuel_wl_T1 ... .fuel_wl_T5
%                   .probe_T1 ... .probe_T5
%                   .total_true_weight
%     metadata   - struct with sequence info:
%                   .type, .n_samples, .duration_s, .start_weight, .end_weight

if nargin < 2
    % Default: look relative to this file's location
    util_dir = fileparts(mfilename('fullpath'));
    matlab_dir = fileparts(util_dir);
    root_dir = fileparts(matlab_dir);
    data_dir = fullfile(root_dir, 'data');
end

%% Load .mat file
switch lower(sequence_type)
    case 'defuel'
        mat_file = fullfile(data_dir, 'defuel_sequence.mat');
    case 'refuel'
        mat_file = fullfile(data_dir, 'refuel_sequence.mat');
    otherwise
        error('Unknown sequence type: %s (use ''defuel'' or ''refuel'')', sequence_type);
end

if ~exist(mat_file, 'file')
    error('Sequence file not found: %s\nRun python -m src.simulate_sequences first.', mat_file);
end

data = load(mat_file);
n = numel(data.time_s);

fprintf('Loaded %s: %d samples, %.0f seconds\n', sequence_type, n, data.time_s(end));

%% Build timeseries objects
time_vec = data.time_s(:);

sim_input = struct();
sim_input.time   = timeseries(time_vec, time_vec, 'Name', 'time');
sim_input.pitch  = timeseries(data.pitch_deg(:), time_vec, 'Name', 'pitch_deg');
sim_input.roll   = timeseries(data.roll_deg(:), time_vec, 'Name', 'roll_deg');

% Dielectric: use system-measured value (includes drift)
kappa = data.density_system(:) ./ 1.003;  % remove bias to get kappa
% Actually, reverse the density model: kappa = (rho/bias - b) / a
a = 4.667; b = -2.857; bias = 1.003;
kappa = (data.density_system(:) / bias - b) / a;
sim_input.dielectric = timeseries(kappa, time_vec, 'Name', 'dielectric');

% Per-tank data
for t = 1:5
    fuel_wl_name = sprintf('fuel_wl_T%d', t);
    probe_name = sprintf('probe_height_T%d', t);

    sim_input.(sprintf('fuel_wl_T%d', t)) = ...
        timeseries(data.(fuel_wl_name)(:), time_vec, 'Name', fuel_wl_name);
    sim_input.(sprintf('probe_T%d', t)) = ...
        timeseries(data.(probe_name)(:), time_vec, 'Name', probe_name);
end

sim_input.total_true_weight = ...
    timeseries(data.total_true_weight_lb(:), time_vec, 'Name', 'total_true_weight');

%% Metadata
metadata = struct();
metadata.type = sequence_type;
metadata.n_samples = n;
metadata.duration_s = data.time_s(end);
metadata.start_weight = data.total_true_weight_lb(1);
metadata.end_weight = data.total_true_weight_lb(end);
metadata.lab_density = data.density_lab(1);
metadata.dry_weight = data.dry_weight_lb(1);

fprintf('  Weight: %.1f → %.1f lb\n', metadata.start_weight, metadata.end_weight);
fprintf('  Density (lab): %.4f lb/gal\n', metadata.lab_density);

end
