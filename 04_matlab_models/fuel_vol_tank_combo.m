function individualVolumes = getIndividualFuelVolumesWithAngles(fuelHeightArray, unique_pitch, unique_roll, pitch, roll, combinedFuelHeight)
    % Initialize the output array for individual volumes
    numVolumes = length(fuelHeightArray);
    individualVolumes = zeros(1, numVolumes);
    
    % Loop through each individual fuel volume's height-volume table
    for i = 1:numVolumes
        % Interpolate to find the volume at the specified pitch, roll, and combined fuel height
        tankData = getInterpolatedFuelHeight(fuelHeightArray{i}, combinedFuelHeight, pitch, roll, unique_pitch, unique_roll);
        
        % Extract the interpolated volume at the combined height
        if combinedFuelHeight >= min(tankData(:,1)) && combinedFuelHeight <= max(tankData(:,1))
            individualVolumes(i) = interp1(tankData(:,1), tankData(:,2), combinedFuelHeight, 'linear');
        else
            % If height is out of bounds, use min/max volume
            if combinedFuelHeight < min(tankData(:,1))
                individualVolumes(i) = tankData(1, 2); % Min capacity
            elseif combinedFuelHeight > max(tankData(:,1))
                individualVolumes(i) = tankData(end, 2); % Max capacity
            end
        end
    end
end

function interpolatedData = getInterpolatedFuelHeight(fuelHeightArray, combinedFuelHeight, pitch, roll, unique_pitch, unique_roll)
    % Get interpolated values at the specified pitch, roll, and height
    [pitch_idx1, pitch_idx2, pitch_weight] = findInterpolationIndices(unique_pitch, pitch);
    [roll_idx1, roll_idx2, roll_weight] = findInterpolationIndices(unique_roll, roll);
    
    % Interpolate for each height in the table
    values_11 = cell2mat(fuelHeightArray{pitch_idx1, roll_idx1});
    values_21 = cell2mat(fuelHeightArray{pitch_idx2, roll_idx1});
    values_12 = cell2mat(fuelHeightArray{pitch_idx1, roll_idx2});
    values_22 = cell2mat(fuelHeightArray{pitch_idx2, roll_idx2});
    
    % Perform bilinear interpolation on probe height and volume data
    interpolated_heights = (1 - pitch_weight) * ((1 - roll_weight) * values_11(:, 1) + roll_weight * values_12(:, 1)) + ...
                           pitch_weight * ((1 - roll_weight) * values_21(:, 1) + roll_weight * values_22(:, 1));
    
    interpolated_volumes = (1 - pitch_weight) * ((1 - roll_weight) * values_11(:, 2) + roll_weight * values_12(:, 2)) + ...
                           pitch_weight * ((1 - roll_weight) * values_21(:, 2) + roll_weight * values_22(:, 2));
                       
    % Combine interpolated height and volume into a matrix for further interpolation
    interpolatedData = [interpolated_heights, interpolated_volumes];
end
