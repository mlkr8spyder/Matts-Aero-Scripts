function [fuelDataArray, unique_pitch, unique_roll, unique_vol] = setupFuelDataArray(filename)
    % Read the CSV file
    data = readtable(filename);
    
    % Extract unique pitch, roll, and volume values
    unique_pitch = unique(data.pitch);
    unique_roll = unique(data.roll);
    unique_vol = unique(data.vol);
    
    % Initialize a 3D cell array to store mass properties based on pitch, roll, and volume
    fuelDataArray = cell(length(unique_pitch), length(unique_roll), length(unique_vol));
    
    % Populate the 3D cell array with mass properties
    for i = 1:height(data)
        % Get the current pitch, roll, and volume indices
        pitch_idx = find(unique_pitch == data.pitch(i));
        roll_idx = find(unique_roll == data.roll(i));
        vol_idx = find(unique_vol == data.vol(i));
        
        % Store mass properties in the corresponding cell
        fuelDataArray{pitch_idx, roll_idx, vol_idx} = data{i, 4:end}; % Store from cgx onwards
    end
end

function outputValues = getInterpolatedMassProperties(fuelDataArray, pitch, roll, volume, unique_pitch, unique_roll, unique_vol)
    % Find nearest indices and interpolation weights for pitch
    [pitch_idx1, pitch_idx2, pitch_weight] = findInterpolationIndices(unique_pitch, pitch);
    
    % Find nearest indices and interpolation weights for roll
    [roll_idx1, roll_idx2, roll_weight] = findInterpolationIndices(unique_roll, roll);
    
    % Find nearest indices and interpolation weights for volume
    [vol_idx1, vol_idx2, vol_weight] = findInterpolationIndices(unique_vol, volume);
    
    % Interpolate in all three dimensions
    values_111 = cell2mat(fuelDataArray{pitch_idx1, roll_idx1, vol_idx1});
    values_211 = cell2mat(fuelDataArray{pitch_idx2, roll_idx1, vol_idx1});
    values_121 = cell2mat(fuelDataArray{pitch_idx1, roll_idx2, vol_idx1});
    values_221 = cell2mat(fuelDataArray{pitch_idx2, roll_idx2, vol_idx1});
    values_112 = cell2mat(fuelDataArray{pitch_idx1, roll_idx1, vol_idx2});
    values_212 = cell2mat(fuelDataArray{pitch_idx2, roll_idx1, vol_idx2});
    values_122 = cell2mat(fuelDataArray{pitch_idx1, roll_idx2, vol_idx2});
    values_222 = cell2mat(fuelDataArray{pitch_idx2, roll_idx2, vol_idx2});
    
    % Trilinear interpolation
    outputValues = ...
        values_111 * (1 - pitch_weight) * (1 - roll_weight) * (1 - vol_weight) + ...
        values_211 * pitch_weight * (1 - roll_weight) * (1 - vol_weight) + ...
        values_121 * (1 - pitch_weight) * roll_weight * (1 - vol_weight) + ...
        values_221 * pitch_weight * roll_weight * (1 - vol_weight) + ...
        values_112 * (1 - pitch_weight) * (1 - roll_weight) * vol_weight + ...
        values_212 * pitch_weight * (1 - roll_weight) * vol_weight + ...
        values_122 * (1 - pitch_weight) * roll_weight * vol_weight + ...
        values_222 * pitch_weight * roll_weight * vol_weight;
end

function [idx1, idx2, weight] = findInterpolationIndices(values, target)
    % Locate indices and weight for interpolation
    idx1 = find(values <= target, 1, 'last');
    idx2 = find(values >= target, 1, 'first');
    
    % Ensure indices are valid
    if isempty(idx1) || isempty(idx2)
        error('Input value is out of bounds for interpolation.');
    end
    
    % Calculate interpolation weight
    if idx1 == idx2
        weight = 0; % Target is exactly on a value
    else
        weight = (target - values(idx1)) / (values(idx2) - values(idx1));
    end
end
