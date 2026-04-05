%% setup_project.m
% Creates the MATLAB Project for the Fuel Gauging System.
%
% This script:
%   1. Creates the project root folder structure
%   2. Creates the MATLAB project (.prj)
%   3. Adds all source folders to the project path
%   4. Creates label categories for file classification
%   5. Generates startup.m and shutdown.m hooks
%   6. Creates an empty data dictionary (.sldd)
%
% Prerequisites:
%   - MATLAB R2025b with Simulink
%   - Run from the matlab/ directory (or adjust root_dir below)
%
% After running:
%   - Run build_data_dictionary.m to populate the .sldd
%   - Run build_simulink_model.m to create all .slx files

clear; clc;
fprintf('=== Fuel Gauging System — Project Setup ===\n\n');

%% ========================================================================
%  Configuration
%  ========================================================================

% Project root is the parent of matlab/
script_dir = fileparts(mfilename('fullpath'));
matlab_dir = fileparts(script_dir);  % matlab/
root_dir = fileparts(matlab_dir);    % synthetic_fuel_system/

proj_name = 'FuelGaugingProject';
fprintf('Project root: %s\n', root_dir);

%% ========================================================================
%  Create directory structure (if not exists)
%  ========================================================================

dirs_to_create = {
    fullfile(root_dir, 'data')
    fullfile(matlab_dir, 'models')
    fullfile(matlab_dir, 'scripts')
    fullfile(matlab_dir, 'tests')
    fullfile(matlab_dir, 'utilities')
    fullfile(matlab_dir, 'work')
};

for i = 1:numel(dirs_to_create)
    if ~exist(dirs_to_create{i}, 'dir')
        mkdir(dirs_to_create{i});
        fprintf('  Created: %s\n', dirs_to_create{i});
    end
end

%% ========================================================================
%  Create MATLAB Project
%  ========================================================================

proj_folder = matlab_dir;  % Project lives in matlab/ subfolder
prj_file = fullfile(proj_folder, [proj_name '.prj']);

% Check if project already exists
if exist(prj_file, 'file')
    fprintf('\nProject already exists: %s\n', prj_file);
    fprintf('Opening existing project...\n');
    proj = openProject(proj_folder);
else
    fprintf('\nCreating new project: %s\n', proj_name);
    proj = matlab.project.createProject(proj_folder);
    proj.Name = proj_name;
    proj.Description = ['Fuel Gauging System - Simulink model with 5-tank FQI, ' ...
                        'probe failure detection, and single-point refuel system.'];
end

%% ========================================================================
%  Add folders to project path
%  ========================================================================

% Folders that should be on the MATLAB path when project is open
path_folders = {
    'scripts'
    'utilities'
    'tests'
    'models'
};

for i = 1:numel(path_folders)
    folder_path = fullfile(proj_folder, path_folders{i});
    if exist(folder_path, 'dir')
        try
            addPath(proj, path_folders{i});
            fprintf('  Added to path: %s\n', path_folders{i});
        catch ME
            if ~contains(ME.message, 'already')
                fprintf('  Warning: %s\n', ME.message);
            end
        end
    end
end

%% ========================================================================
%  Add files to project
%  ========================================================================

% Add all MATLAB files in key directories
folders_to_add = {'scripts', 'utilities', 'tests', 'models'};
for i = 1:numel(folders_to_add)
    folder_path = fullfile(proj_folder, folders_to_add{i});
    if exist(folder_path, 'dir')
        try
            addFolderIncludingChildFiles(proj, folders_to_add{i});
            fprintf('  Added folder: %s\n', folders_to_add{i});
        catch ME
            % Folder may already be added
            if ~contains(ME.message, 'already')
                fprintf('  Warning adding %s: %s\n', folders_to_add{i}, ME.message);
            end
        end
    end
end

% Add data directory files (cross-reference to parent)
data_dir = fullfile(root_dir, 'data');
if exist(data_dir, 'dir')
    try
        addReference(proj, data_dir);
        fprintf('  Added data reference: %s\n', data_dir);
    catch ME
        fprintf('  Note (data ref): %s\n', ME.message);
    end
end

%% ========================================================================
%  Create label categories
%  ========================================================================

fprintf('\nSetting up label categories...\n');

% Classification labels
try
    cat1 = addCategory(proj, 'Classification', 'Classify files by purpose');
    addLabel(cat1, 'Design',   'Model and design files');
    addLabel(cat1, 'Test',     'Test and validation files');
    addLabel(cat1, 'Script',   'Setup and utility scripts');
    addLabel(cat1, 'Data',     'Data files and dictionaries');
    addLabel(cat1, 'Utility',  'Helper functions');
    fprintf('  Created Classification labels\n');
catch
    fprintf('  Classification labels already exist\n');
end

% Component labels
try
    cat2 = addCategory(proj, 'Component', 'System component');
    addLabel(cat2, 'ProbeModel',       'Probe measurement models');
    addLabel(cat2, 'FailureDetection', 'Probe failure detection');
    addLabel(cat2, 'Lookup',           'H-V table lookup');
    addLabel(cat2, 'Density',          'Density computation');
    addLabel(cat2, 'Weight',           'Weight summation');
    addLabel(cat2, 'Refuel',           'Refuel system');
    addLabel(cat2, 'TopLevel',         'Top-level integration');
    fprintf('  Created Component labels\n');
catch
    fprintf('  Component labels already exist\n');
end

%% ========================================================================
%  Create startup.m
%  ========================================================================

startup_file = fullfile(proj_folder, 'startup.m');
fid = fopen(startup_file, 'w');
fprintf(fid, '%%%% Project Startup — Fuel Gauging System\n');
fprintf(fid, '%% This script runs automatically when the project opens.\n\n');
fprintf(fid, 'fprintf(''\\n=== Fuel Gauging System Project ===\\n'');\n');
fprintf(fid, 'fprintf(''MATLAB %%s\\n'', version);\n');
fprintf(fid, 'fprintf(''Project root: %%s\\n\\n'', pwd);\n\n');
fprintf(fid, '%% Set Simulation Cache and Code Generation folders to work/\n');
fprintf(fid, 'work_dir = fullfile(pwd, ''work'');\n');
fprintf(fid, 'if ~exist(work_dir, ''dir''), mkdir(work_dir); end\n');
fprintf(fid, 'Simulink.fileGenControl(''set'', ...\n');
fprintf(fid, '    ''CacheFolder'', work_dir, ...\n');
fprintf(fid, '    ''CodeGenFolder'', work_dir);\n\n');
fprintf(fid, '%% Load data dictionary into memory\n');
fprintf(fid, 'dd_file = fullfile(pwd, ''data'', ''FuelGaugingData.sldd'');\n');
fprintf(fid, 'if exist(dd_file, ''file'')\n');
fprintf(fid, '    fprintf(''Data dictionary: %%s\\n'', dd_file);\n');
fprintf(fid, 'else\n');
fprintf(fid, '    fprintf(''WARNING: Data dictionary not found. Run build_data_dictionary.m\\n'');\n');
fprintf(fid, 'end\n\n');
fprintf(fid, 'fprintf(''\\nReady. Run build_simulink_model to create/update models.\\n'');\n');
fclose(fid);
fprintf('  Created: startup.m\n');

%% ========================================================================
%  Create shutdown.m
%  ========================================================================

shutdown_file = fullfile(proj_folder, 'shutdown.m');
fid = fopen(shutdown_file, 'w');
fprintf(fid, '%%%% Project Shutdown — Fuel Gauging System\n');
fprintf(fid, '%% This script runs automatically when the project closes.\n\n');
fprintf(fid, '%% Close any open data dictionaries\n');
fprintf(fid, 'try\n');
fprintf(fid, '    Simulink.data.dictionary.closeAll;\n');
fprintf(fid, 'catch\n');
fprintf(fid, 'end\n\n');
fprintf(fid, '%% Close all open models without saving\n');
fprintf(fid, 'try\n');
fprintf(fid, '    bdclose all;\n');
fprintf(fid, 'catch\n');
fprintf(fid, 'end\n\n');
fprintf(fid, 'fprintf(''Fuel Gauging Project closed.\\n'');\n');
fclose(fid);
fprintf('  Created: shutdown.m\n');

%% ========================================================================
%  Set startup/shutdown hooks
%  ========================================================================

try
    addStartupFile(proj, 'startup.m');
    fprintf('  Registered startup.m\n');
catch
    fprintf('  startup.m already registered\n');
end

try
    addShutdownFile(proj, 'shutdown.m');
    fprintf('  Registered shutdown.m\n');
catch
    fprintf('  shutdown.m already registered\n');
end

%% ========================================================================
%  Create empty data dictionary
%  ========================================================================

dd_folder = fullfile(proj_folder, 'data');
if ~exist(dd_folder, 'dir'), mkdir(dd_folder); end

dd_path = fullfile(dd_folder, 'FuelGaugingData.sldd');
if ~exist(dd_path, 'file')
    dd = Simulink.data.dictionary.create(dd_path);
    saveChanges(dd);
    close(dd);
    fprintf('\n  Created data dictionary: %s\n', dd_path);
else
    fprintf('\n  Data dictionary already exists: %s\n', dd_path);
end

%% ========================================================================
%  Done
%  ========================================================================

fprintf('\n=== Project Setup Complete ===\n');
fprintf('Project: %s\n', proj.Name);
fprintf('Root:    %s\n', proj.RootFolder);
fprintf('\nNext steps:\n');
fprintf('  1. Run: build_data_dictionary   (populate .sldd)\n');
fprintf('  2. Run: build_simulink_model    (create .slx files)\n');
fprintf('  3. Run: validate_model          (verify everything)\n');
