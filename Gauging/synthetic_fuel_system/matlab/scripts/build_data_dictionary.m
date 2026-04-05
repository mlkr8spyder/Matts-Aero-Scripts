%% build_data_dictionary.m
% Populates the Simulink Data Dictionary (FuelGaugingData.sldd) with:
%   - Bus object definitions (ProbeReadingBus, TankIndicationBus, etc.)
%   - Simulink.Parameter objects (thresholds, physical constants)
%   - Simulink.LookupTable objects (3-D H-V tables per tank)
%   - Tank parameter structures
%
% Prerequisites:
%   - Run setup_project.m first (creates .sldd)
%   - H-V table data in data/tank_system.mat (from Python or MATLAB pipeline)
%
% The data dictionary is the SINGLE SOURCE OF TRUTH for all model parameters.
% Nothing should be loaded into the base workspace during simulation.

clear; clc;
fprintf('=== Build Data Dictionary ===\n\n');

%% ========================================================================
%  Locate files
%  ========================================================================

script_dir  = fileparts(mfilename('fullpath'));
matlab_dir  = fileparts(script_dir);
root_dir    = fileparts(matlab_dir);
data_dir    = fullfile(root_dir, 'data');
dd_dir      = fullfile(matlab_dir, 'data');

dd_path = fullfile(dd_dir, 'FuelGaugingData.sldd');
if ~exist(dd_path, 'file')
    error('Data dictionary not found: %s\nRun setup_project.m first.', dd_path);
end

% Open data dictionary
dd = Simulink.data.dictionary.open(dd_path);
ddata = getSection(dd, 'Design Data');

fprintf('Data dictionary: %s\n\n', dd_path);

%% ========================================================================
%  1. BUS DEFINITIONS
%  ========================================================================

fprintf('--- Creating Bus Definitions ---\n');

% ---- AttitudeBus ----
elems = [];
e = Simulink.BusElement; e.Name = 'pitch_deg'; e.DataType = 'double';
e.Unit = 'deg'; e.Description = 'Aircraft pitch angle';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'roll_deg'; e.DataType = 'double';
e.Unit = 'deg'; e.Description = 'Aircraft roll angle';
elems = [elems; e];

bus = Simulink.Bus;
bus.Description = 'Aircraft attitude';
bus.Elements = elems;
addOrUpdate(ddata, 'AttitudeBus', bus);
fprintf('  AttitudeBus\n');

% ---- ProbeReadingBus ----
elems = [];
e = Simulink.BusElement; e.Name = 'probe_height'; e.DataType = 'double';
e.Unit = 'in'; e.Description = 'Wetted height on probe';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'fuel_wl'; e.DataType = 'double';
e.Unit = 'in'; e.Description = 'Fuel surface waterline at probe';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'is_valid'; e.DataType = 'boolean';
e.Description = 'True if reading passed health checks';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'failure_code'; e.DataType = 'uint8';
e.Description = '0=OK, 1=OpenCkt, 2=ShortCkt, 3=RateExceed, 4=Stale';
elems = [elems; e];

bus = Simulink.Bus;
bus.Description = 'Single probe measurement output';
bus.Elements = elems;
addOrUpdate(ddata, 'ProbeReadingBus', bus);
fprintf('  ProbeReadingBus\n');

% ---- BIT_StatusBus ----
elems = [];
e = Simulink.BusElement; e.Name = 'all_probes_healthy'; e.DataType = 'boolean';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'num_failed_probes'; e.DataType = 'uint8';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'failure_flags'; e.DataType = 'boolean';
e.Dimensions = 5;
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'failure_codes'; e.DataType = 'uint8';
e.Dimensions = 5;
elems = [elems; e];

bus = Simulink.Bus;
bus.Description = 'Built-in test status for all probes';
bus.Elements = elems;
addOrUpdate(ddata, 'BIT_StatusBus', bus);
fprintf('  BIT_StatusBus\n');

% ---- TankIndicationBus ----
elems = [];
e = Simulink.BusElement; e.Name = 'volume_in3'; e.DataType = 'double';
e.Unit = 'in^3';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'volume_gal'; e.DataType = 'double';
e.Unit = 'gal';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'weight_lb'; e.DataType = 'double';
e.Unit = 'lb';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'probe_data'; e.DataType = 'Bus: ProbeReadingBus';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'tank_id'; e.DataType = 'uint8';
elems = [elems; e];

bus = Simulink.Bus;
bus.Description = 'Per-tank fuel quantity indication';
bus.Elements = elems;
addOrUpdate(ddata, 'TankIndicationBus', bus);
fprintf('  TankIndicationBus\n');

% ---- SystemIndicationBus ----
elems = [];
e = Simulink.BusElement; e.Name = 'total_weight_lb'; e.DataType = 'double';
e.Unit = 'lb';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'total_volume_gal'; e.DataType = 'double';
e.Unit = 'gal';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'density_system'; e.DataType = 'double';
e.Unit = 'lb/gal';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'bit_status';
e.DataType = 'Bus: BIT_StatusBus';
elems = [elems; e];

bus = Simulink.Bus;
bus.Description = 'Complete system fuel quantity indication';
bus.Elements = elems;
addOrUpdate(ddata, 'SystemIndicationBus', bus);
fprintf('  SystemIndicationBus\n');

% ---- RefuelStatusBus ----
elems = [];
e = Simulink.BusElement; e.Name = 'is_active'; e.DataType = 'boolean';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'is_complete'; e.DataType = 'boolean';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'valve_positions'; e.DataType = 'double';
e.Dimensions = 5;
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'hi_level_states'; e.DataType = 'boolean';
e.Dimensions = 5;
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'flow_rates_gpm'; e.DataType = 'double';
e.Dimensions = 5; e.Unit = 'gal/min';
elems = [elems; e];
e = Simulink.BusElement; e.Name = 'total_delivered_gal'; e.DataType = 'double';
e.Unit = 'gal';
elems = [elems; e];

bus = Simulink.Bus;
bus.Description = 'Single-point refuel system status';
bus.Elements = elems;
addOrUpdate(ddata, 'RefuelStatusBus', bus);
fprintf('  RefuelStatusBus\n');

%% ========================================================================
%  2. SYSTEM PARAMETERS
%  ========================================================================

fprintf('\n--- Creating System Parameters ---\n');

params = {
    % Name                     Value    Unit        Description
    'IN3_PER_GAL',             231.0,   'in^3/gal', 'Cubic inches per US gallon'
    'ULLAGE_FRAC',             0.02,    '',         'Ullage expansion reserve fraction'
    'UNUSABLE_FRAC',           0.015,   '',         'Unusable fuel fraction'
    'DENSITY_MODEL_A',         4.667,   'lb/(gal)', 'Density model slope'
    'DENSITY_MODEL_B',         -2.857,  'lb/gal',   'Density model intercept'
    'DENSITY_BIAS',            1.003,   '',         'Density bias multiplier (0.3%% high)'
    'KAPPA_NOMINAL',           2.05,    '',         'Nominal fuel dielectric constant'
    'DENSITY_LAB',             6.71,    'lb/gal',   'Lab-measured fuel density'
    'PROBE_NOISE_STD',         0.02,    'in',       'Probe measurement noise sigma'
    'SUPPLY_PRESSURE_PSI',     55.0,    'psi',      'Refuel supply pressure'
    'MANIFOLD_WL',             78.0,    'in',       'Refuel manifold waterline'
    'MAX_FLOW_GPM',            60.0,    'gal/min',  'Max total refuel flow rate'
    'VALVE_CAPACITY_GPM',      15.0,    'gal/min',  'Per-valve max flow rate'
    'VALVE_CLOSE_TIME',        0.5,     's',        'Shutoff valve close time'
    'VALVE_OPEN_TIME',         0.3,     's',        'Shutoff valve open time'
    'FAILURE_OPEN_THRESH',     -0.1,    'in',       'Open circuit threshold'
    'FAILURE_SHORT_MARGIN',    0.5,     'in',       'Short circuit margin above max'
    'FAILURE_RATE_THRESH',     2.0,     'in/s',     'Rate exceedance threshold'
    'FAILURE_STALE_TIMEOUT',   30.0,    's',        'Stale data timeout'
    'FAILURE_STALE_DELTA',     0.01,    'in',       'Stale data minimum change'
    'BLEND_LO_WL',             90.0,    'in',       'T3 blend zone lower bound'
    'BLEND_HI_WL',             92.0,    'in',       'T3 blend zone upper bound'
    'PSEUDO_DX',               55.0,    'in',       'T5 pseudo FS offset from T3'
    'PSEUDO_DY',               0.0,     'in',       'T5 pseudo BL offset from T3'
};

for i = 1:size(params, 1)
    p = Simulink.Parameter;
    p.Value = params{i, 2};
    p.DataType = 'double';
    p.Unit = params{i, 3};
    p.Description = params{i, 4};
    p.CoderInfo.StorageClass = 'Auto';
    addOrUpdate(ddata, params{i, 1}, p);
end
fprintf('  Created %d parameters\n', size(params, 1));

%% ========================================================================
%  3. TANK PARAMETER STRUCTURES
%  ========================================================================

fprintf('\n--- Creating Tank Parameter Structures ---\n');

% Tank definitions
TankParams = struct();

TankParams(1).name       = 'Forward';
TankParams(1).tank_id    = uint8(1);
TankParams(1).fs_min     = 195.0;  TankParams(1).fs_max     = 225.0;
TankParams(1).bl_min     = -15.0;  TankParams(1).bl_max     = 15.0;
TankParams(1).wl_min     = 88.0;   TankParams(1).wl_max     = 104.0;
TankParams(1).base_area  = 900.0;
TankParams(1).height     = 16.0;
TankParams(1).probe_base = 88.24;  TankParams(1).probe_top  = 103.68;
TankParams(1).max_fill   = 103.68;
TankParams(1).probe_type = uint8(1);  % 1=real, 2=combo, 3=pseudo

TankParams(2).name       = 'Left';
TankParams(2).tank_id    = uint8(2);
TankParams(2).fs_min     = 235.0;  TankParams(2).fs_max     = 285.0;
TankParams(2).bl_min     = -62.0;  TankParams(2).bl_max     = -22.0;
TankParams(2).wl_min     = 85.0;   TankParams(2).wl_max     = 103.0;
TankParams(2).base_area  = 2000.0;
TankParams(2).height     = 18.0;
TankParams(2).probe_base = 85.27;  TankParams(2).probe_top  = 102.64;
TankParams(2).max_fill   = 102.64;
TankParams(2).probe_type = uint8(1);

TankParams(3).name       = 'Center';
TankParams(3).tank_id    = uint8(3);
TankParams(3).fs_min     = 235.0;  TankParams(3).fs_max     = 285.0;
TankParams(3).bl_min     = -20.0;  TankParams(3).bl_max     = 20.0;
TankParams(3).wl_min     = 80.0;   TankParams(3).wl_max     = 100.0;
TankParams(3).base_area  = 2000.0;
TankParams(3).height     = 20.0;
TankParams(3).probe_base = 80.30;
TankParams(3).probe_top  = 99.60;
TankParams(3).lower_base = 80.30;  TankParams(3).lower_top  = 92.00;
TankParams(3).upper_base = 90.00;  TankParams(3).upper_top  = 99.60;
TankParams(3).max_fill   = 99.60;
TankParams(3).probe_type = uint8(2);

TankParams(4).name       = 'Right';
TankParams(4).tank_id    = uint8(4);
TankParams(4).fs_min     = 235.0;  TankParams(4).fs_max     = 285.0;
TankParams(4).bl_min     = 22.0;   TankParams(4).bl_max     = 62.0;
TankParams(4).wl_min     = 85.0;   TankParams(4).wl_max     = 103.0;
TankParams(4).base_area  = 2000.0;
TankParams(4).height     = 18.0;
TankParams(4).probe_base = 85.27;  TankParams(4).probe_top  = 102.64;
TankParams(4).max_fill   = 102.64;
TankParams(4).probe_type = uint8(1);

TankParams(5).name       = 'Aft';
TankParams(5).tank_id    = uint8(5);
TankParams(5).fs_min     = 295.0;  TankParams(5).fs_max     = 335.0;
TankParams(5).bl_min     = -17.5;  TankParams(5).bl_max     = 17.5;
TankParams(5).wl_min     = 83.0;   TankParams(5).wl_max     = 105.0;
TankParams(5).base_area  = 1400.0;
TankParams(5).height     = 22.0;
TankParams(5).probe_base = 83.0;   TankParams(5).probe_top  = 105.0;
TankParams(5).max_fill   = 104.56;
TankParams(5).probe_type = uint8(3);

% Store as a Simulink.Parameter
tp = Simulink.Parameter;
tp.Value = TankParams;
tp.Description = 'Per-tank geometric and probe parameters (1x5 struct array)';
addOrUpdate(ddata, 'TankParams', tp);
fprintf('  Created TankParams (5 tanks)\n');

%% ========================================================================
%  4. LOOKUP TABLE OBJECTS (3-D: height × pitch × roll → volume)
%  ========================================================================

fprintf('\n--- Creating Lookup Table Objects ---\n');

% Load H-V table data (prefer Python-generated, fall back to MATLAB-generated)
hv_file_py = fullfile(data_dir, 'tank_system.mat');
hv_file_ml = fullfile(data_dir, 'tank_system_matlab.mat');

if exist(hv_file_py, 'file')
    hv_data = load(hv_file_py);
    fprintf('  Loaded H-V data from: %s\n', hv_file_py);
elseif exist(hv_file_ml, 'file')
    hv_data = load(hv_file_ml);
    fprintf('  Loaded H-V data from: %s\n', hv_file_ml);
else
    error(['H-V table data not found.\n' ...
           'Run generate_hv_tables.m or python -m src.hv_table_generator first.']);
end

pitch_bp = hv_data.pitch_range(:)';  % 1×13
roll_bp  = hv_data.roll_range(:)';   % 1×17

for t = 1:5
    prefix = sprintf('T%d', t);
    heights_cell = hv_data.([prefix '_heights']);
    volumes_cell = hv_data.([prefix '_volumes']);

    n_pitch = numel(pitch_bp);
    n_roll  = numel(roll_bp);

    % Determine height breakpoints from the level-attitude table (pitch=0, roll=0)
    pi0 = find(pitch_bp == 0);
    ri0 = find(roll_bp == 0);
    ref_heights = heights_cell{pi0, ri0};
    ref_heights = ref_heights(:)';
    n_h = numel(ref_heights);

    % Build 3-D table array: (n_h × n_pitch × n_roll)
    table_3d = zeros(n_h, n_pitch, n_roll);

    for pi = 1:n_pitch
        for ri = 1:n_roll
            h_raw = heights_cell{pi, ri}; h_raw = h_raw(:)';
            v_raw = volumes_cell{pi, ri}; v_raw = v_raw(:)';

            % Interpolate onto common height breakpoints
            % (tables may have slightly different lengths at extreme attitudes)
            if numel(h_raw) == n_h && all(abs(h_raw - ref_heights) < 0.01)
                % Heights match exactly — use directly
                table_3d(:, pi, ri) = v_raw;
            else
                % Interpolate onto reference height grid
                table_3d(:, pi, ri) = interp1(h_raw, v_raw, ref_heights, ...
                    'linear', 'extrap');
            end
        end
    end

    % Ensure monotonicity (clamp any numerical artifacts)
    for pi = 1:n_pitch
        for ri = 1:n_roll
            col = table_3d(:, pi, ri);
            for k = 2:n_h
                if col(k) < col(k-1)
                    col(k) = col(k-1);
                end
            end
            table_3d(:, pi, ri) = col;
        end
    end

    % Clamp negative volumes to zero
    table_3d = max(0, table_3d);

    % Create Simulink.LookupTable object
    lut = Simulink.LookupTable;
    lut.Table.Value = table_3d;
    lut.Table.DataType = 'double';
    lut.Breakpoints(1).Value = ref_heights;
    lut.Breakpoints(1).DataType = 'double';
    lut.Breakpoints(2).Value = pitch_bp;
    lut.Breakpoints(2).DataType = 'double';
    lut.Breakpoints(3).Value = roll_bp;
    lut.Breakpoints(3).DataType = 'double';
    lut.StructTypeInfo.Name = sprintf('LUT_%s_Type', prefix);

    lut_name = sprintf('LUT_%s', prefix);
    addOrUpdate(ddata, lut_name, lut);

    fprintf('  %s: %d×%d×%d = %d entries (height range: [%.1f, %.1f])\n', ...
        lut_name, n_h, n_pitch, n_roll, numel(table_3d), ...
        ref_heights(1), ref_heights(end));
end

%% ========================================================================
%  5. SAVE AND REPORT
%  ========================================================================

fprintf('\n--- Saving Data Dictionary ---\n');
saveChanges(dd);

% Report contents
all_entries = find(ddata);
fprintf('\nData dictionary contents (%d entries):\n', numel(all_entries));
fprintf('  %-30s %-30s\n', 'Name', 'Class');
fprintf('  %s\n', repmat('-', 1, 60));
for i = 1:numel(all_entries)
    val = getValue(all_entries(i));
    fprintf('  %-30s %-30s\n', all_entries(i).Name, class(val));
end

close(dd);

fprintf('\n=== Data Dictionary Build Complete ===\n');
fprintf('File: %s\n', dd_path);
fprintf('Run build_simulink_model.m next.\n');

%% ========================================================================
%  Helper function: add or update a dictionary entry
%  ========================================================================

function addOrUpdate(section, name, value)
    try
        entry = getEntry(section, name);
        setValue(entry, value);
    catch
        addEntry(section, name, value);
    end
end
