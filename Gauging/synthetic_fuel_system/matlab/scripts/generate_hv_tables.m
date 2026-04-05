%% generate_hv_tables.m
% MATLAB implementation of height-volume table generation for the synthetic
% 5-tank fuel system. Cross-validates against the Python implementation.
%
% All tanks are rectangular prisms. Volume under a tilted fuel plane is
% computed numerically on a fine grid.
%
% Coordinate system:
%   X (FS) - Fuselage Station, positive aft
%   Y (BL) - Buttline, positive right
%   Z (WL) - Waterline, positive up

clear; clc;
fprintf('=== MATLAB H-V Table Generator ===\n\n');

%% Tank Definitions
% Each tank: [fs_min, fs_max, bl_min, bl_max, wl_min, wl_max]
tank_data = struct();

tank_data(1).name = 'Forward';
tank_data(1).id = 1;
tank_data(1).fs = [195.0, 225.0];
tank_data(1).bl = [-15.0, 15.0];
tank_data(1).wl = [88.0, 104.0];
tank_data(1).probe_base_wl = 88.24;
tank_data(1).probe_ref_fs = 210.0;
tank_data(1).probe_ref_bl = 0.0;

tank_data(2).name = 'Left';
tank_data(2).id = 2;
tank_data(2).fs = [235.0, 285.0];
tank_data(2).bl = [-62.0, -22.0];
tank_data(2).wl = [85.0, 103.0];
tank_data(2).probe_base_wl = 85.27;
tank_data(2).probe_ref_fs = 260.0;
tank_data(2).probe_ref_bl = -42.0;

tank_data(3).name = 'Center';
tank_data(3).id = 3;
tank_data(3).fs = [235.0, 285.0];
tank_data(3).bl = [-20.0, 20.0];
tank_data(3).wl = [80.0, 100.0];
tank_data(3).probe_base_wl = 80.30;  % lower probe base
tank_data(3).probe_ref_fs = 260.0;
tank_data(3).probe_ref_bl = -0.25;

tank_data(4).name = 'Right';
tank_data(4).id = 4;
tank_data(4).fs = [235.0, 285.0];
tank_data(4).bl = [22.0, 62.0];
tank_data(4).wl = [85.0, 103.0];
tank_data(4).probe_base_wl = 85.27;
tank_data(4).probe_ref_fs = 260.0;
tank_data(4).probe_ref_bl = 42.0;

tank_data(5).name = 'Aft';
tank_data(5).id = 5;
tank_data(5).fs = [295.0, 335.0];
tank_data(5).bl = [-17.5, 17.5];
tank_data(5).wl = [83.0, 105.0];
tank_data(5).probe_base_wl = 83.0;  % pseudo, uses tank floor
tank_data(5).probe_ref_fs = 315.0;
tank_data(5).probe_ref_bl = 0.0;

%% Attitude grid
pitch_range = -6:1:6;    % degrees
roll_range = -8:1:8;     % degrees
height_step = 0.5;       % inches

n_pitch = length(pitch_range);
n_roll = length(roll_range);

fprintf('Attitude grid: %d pitch x %d roll = %d conditions\n', ...
    n_pitch, n_roll, n_pitch * n_roll);

%% Generate tables for each tank
IN3_PER_GAL = 231.0;
nx = 100;  % grid resolution for numerical integration
ny = 100;

results = struct();

for t = 1:5
    tk = tank_data(t);
    fprintf('\nGenerating T%d (%s)...\n', tk.id, tk.name);

    Lx = tk.fs(2) - tk.fs(1);
    Ly = tk.bl(2) - tk.bl(1);
    Lz = tk.wl(2) - tk.wl(1);
    gross_vol = Lx * Ly * Lz;

    fprintf('  Dimensions: %.0f x %.0f x %.0f in, gross=%.0f in3 (%.1f gal)\n', ...
        Lx, Ly, Lz, gross_vol, gross_vol/IN3_PER_GAL);

    % Height range for table
    wl_start = tk.wl(1) - 1.0;
    wl_end = tk.wl(2) + 1.0;
    heights_wl = wl_start:height_step:wl_end;
    n_heights = length(heights_wl);

    % Create cell arrays for variable-length tables
    heights_cell = cell(n_pitch, n_roll);
    volumes_cell = cell(n_pitch, n_roll);

    % Grid for numerical integration
    dx = Lx / nx;
    dy = Ly / ny;
    cell_area = dx * dy;
    fs_centers = linspace(tk.fs(1) + dx/2, tk.fs(2) - dx/2, nx);
    bl_centers = linspace(tk.bl(1) + dy/2, tk.bl(2) - dy/2, ny);
    [FS, BL] = meshgrid(fs_centers, bl_centers);  % ny x nx

    for pi = 1:n_pitch
        for ri = 1:n_roll
            pitch = pitch_range(pi);
            roll_val = roll_range(ri);

            tan_p = tand(pitch);
            tan_r = tand(roll_val);

            ref_fs = tk.probe_ref_fs;
            ref_bl = tk.probe_ref_bl;

            vols = zeros(n_heights, 1);

            for hi = 1:n_heights
                z_ref = heights_wl(hi);

                % Fuel surface height at each grid cell
                z_fuel = z_ref + (FS - ref_fs) * tan_p + (BL - ref_bl) * tan_r;

                % Fuel depth (clipped to tank height)
                h_fuel = max(0, min(z_fuel - tk.wl(1), Lz));

                % Volume = sum of column volumes
                vols(hi) = sum(h_fuel(:)) * cell_area;
            end

            % Store as relative height (from probe base)
            heights_rel = heights_wl - tk.probe_base_wl;

            heights_cell{pi, ri} = heights_rel(:)';
            volumes_cell{pi, ri} = vols(:)';
        end
    end

    % Store in results
    results(t).name = tk.name;
    results(t).id = tk.id;
    results(t).heights = heights_cell;
    results(t).volumes = volumes_cell;
    results(t).gross_vol_in3 = gross_vol;

    fprintf('  Generated %d tables, %d height points each\n', ...
        n_pitch * n_roll, n_heights);
end

%% Save to .mat file
output_dir = fullfile(fileparts(mfilename('fullpath')), '..', 'data');
if ~exist(output_dir, 'dir')
    mkdir(output_dir);
end

save_data = struct();
save_data.pitch_range = pitch_range;
save_data.roll_range = roll_range;

for t = 1:5
    prefix = sprintf('T%d', results(t).id);
    save_data.([prefix '_heights']) = results(t).heights;
    save_data.([prefix '_volumes']) = results(t).volumes;
    save_data.([prefix '_gross_vol_in3']) = results(t).gross_vol_in3;
    save_data.([prefix '_name']) = results(t).name;
end

mat_path = fullfile(output_dir, 'tank_system_matlab.mat');
save(mat_path, '-struct', 'save_data');
fprintf('\nSaved: %s\n', mat_path);

%% Validation: compare level-attitude volumes to expected
fprintf('\n=== Validation at 0 deg pitch, 0 deg roll ===\n');
pi_zero = find(pitch_range == 0);
ri_zero = find(roll_range == 0);

for t = 1:5
    tk = tank_data(t);
    vols = results(t).volumes{pi_zero, ri_zero};
    max_vol = max(vols);
    expected = (tk.fs(2)-tk.fs(1)) * (tk.bl(2)-tk.bl(1)) * (tk.wl(2)-tk.wl(1));
    pct_err = abs(max_vol - expected) / expected * 100;
    fprintf('T%d %8s: max_vol=%.0f in3, expected=%.0f in3, err=%.3f%%\n', ...
        tk.id, tk.name, max_vol, expected, pct_err);
end

fprintf('\nDone.\n');
