function [fuelHeightArray, unique_gallons, unique_pitch, unique_roll] = setupFuelHeightArray(filename)
    % Read the CSV file
    data = readtable(filename);
    
    % Extract unique values for gallons, pitch, and roll
    unique_gallons = unique(data.gallons);
    unique_pitch = unique(data.Pitch);
    unique_roll = unique(data.Roll);
    
    % Initialize a 3D cell array to store probe height and ZE values
    fuelHeightArray = cell(length(unique_gallons), length(unique_pitch), length(unique_roll));
    
    % Populate the 3D cell array with probe height and ZE values
    for i = 1:height(data)
        % Get the current indices for gallons, pitch, and roll
        gallons_idx = find(unique_gallons == data.gallons(i));
        pitch_idx = find(unique_pitch == data.Pitch(i));
        roll_idx = find(unique_roll == data.Roll(i));
        
        % Store probe height and ZE in the corresponding cell
        fuelHeightArray{gallons_idx, pitch_idx, roll_idx} = [data.probe_hgt(i), data.ZE(i)];
    end
end

function interpolatedValues = getInterpolatedFuelHeight(fuelHeightArray, gallons, pitch, roll, unique_gallons, unique_pitch, unique_roll)
    % Find nearest indices and interpolation weights for gallons
    [gallons_idx1, gallons_idx2, gallons_weight] = findInterpolationIndices(unique_gallons, gallons);
    
    % Find nearest indices and interpolation weights for pitch
    [pitch_idx1, pitch_idx2, pitch_weight] = findInterpolationIndices(unique_pitch, pitch);
    
    % Find nearest indices and interpolation weights for roll
    [roll_idx1, roll_idx2, roll_weight] = findInterpolationIndices(unique_roll, roll);
    
    % Retrieve values at the eight corners around the target point
    values_111 = cell2mat(fuelHeightArray{gallons_idx1, pitch_idx1, roll_idx1});
    values_211 = cell2mat(fuelHeightArray{gallons_idx2, pitch_idx1, roll_idx1});
    values_121 = cell2mat(fuelHeightArray{gallons_idx1, pitch_idx2, roll_idx1});
    values_221 = cell2mat(fuelHeightArray{gallons_idx2, pitch_idx2, roll_idx1});
    values_112 = cell2mat(fuelHeightArray{gallons_idx1, pitch_idx1, roll_idx2});
    values_212 = cell2mat(fuelHeightArray{gallons_idx2, pitch_idx1, roll_idx2});
    values_122 = cell2mat(fuelHeightArray{gallons_idx1, pitch_idx2, roll_idx2});
    values_222 = cell2mat(fuelHeightArray{gallons_idx2, pitch_idx2, roll_idx2});
    
    % Trilinear interpolation for both probe height and ZE
    interpolated_probe_hgt = ...
        values_111(1) * (1 - gallons_weight) * (1 - pitch_weight) * (1 - roll_weight) + ...
        values_211(1) * gallons_weight * (1 - pitch_weight) * (1 - roll_weight) + ...
        values_121(1) * (1 - gallons_weight) * pitch_weight * (1 - roll_weight) + ...
        values_221(1) * gallons_weight * pitch_weight * (1 - roll_weight) + ...
        values_112(1) * (1 - gallons_weight) * (1 - pitch_weight) * roll_weight + ...
        values_212(1) * gallons_weight * (1 - pitch_weight) * roll_weight + ...
        values_122(1) * (1 - gallons_weight) * pitch_weight * roll_weight + ...
        values_222(1) * gallons_weight * pitch_weight * roll_weight;
    
    interpolated_ZE = ...
        values_111(2) * (1 - gallons_weight) * (1 - pitch_weight) * (1 - roll_weight) + ...
        values_211(2) * gallons_weight * (1 - pitch_weight) * (1 - roll_weight) + ...
        values_121(2) * (1 - gallons_weight) * pitch_weight * (1 - roll_weight) + ...
        values_221(2) * gallons_weight * pitch_weight * (1 - roll_weight) + ...
        values_112(2) * (1 - gallons_weight) * (1 - pitch_weight) * roll_weight + ...
        values_212(2) * gallons_weight * (1 - pitch_weight) * roll_weight + ...
        values_122(2) * (1 - gallons_weight) * pitch_weight * roll_weight + ...
        values_222(2) * gallons_weight * pitch_weight * roll_weight;
    
    % Store interpolated results in output structure
    interpolatedValues.probe_hgt = interpolated_probe_hgt;
    interpolatedValues.ZE = interpolated_ZE;
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
