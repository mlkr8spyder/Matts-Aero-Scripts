function individualVolumes = getIndividualFuelVolumes(heightVolumeTables, combinedFuelHeight)
    % Initialize the output array for individual volumes
    numVolumes = length(heightVolumeTables);
    individualVolumes = zeros(1, numVolumes);
    
    % Loop through each individual fuel volume's height-volume table
    for i = 1:numVolumes
        % Get the current height-volume table
        table = heightVolumeTables{i};
        heights = table(:,1); % Assumes first column is height
        volumes = table(:,2); % Assumes second column is volume
        
        % Interpolate to find the volume at the specified combined fuel height
        if combinedFuelHeight >= min(heights) && combinedFuelHeight <= max(heights)
            individualVolumes(i) = interp1(heights, volumes, combinedFuelHeight, 'linear');
        else
            % Handle cases where the height is out of bounds (e.g., fill to max/min capacity)
            if combinedFuelHeight < min(heights)
                individualVolumes(i) = volumes(1); % Min capacity
            elseif combinedFuelHeight > max(heights)
                individualVolumes(i) = volumes(end); % Max capacity
            end
        end
    end
end
