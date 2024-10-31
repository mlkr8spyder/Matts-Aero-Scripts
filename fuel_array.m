function fuelDataArray = setupFuelDataArray(filename)
    % Read the CSV file
    data = readtable(filename);
    
    % Extract unique pitch, roll, and volume values
    unique_pitch = unique(data.pitch);
    unique_roll = unique(data.roll);
    unique_vol = unique(data.vol);
    
    % Initialize a 3D cell array to store mass properties based on pitch, roll, and volume
    fuelDataArray = cell(length(unique_pitch), length(unique_roll), length(unique_vol));
    
    % Loop over each row of the data
    for i = 1:height(data)
        % Get the current pitch, roll, and volume indices
        pitch_idx = find(unique_pitch == data.pitch(i));
        roll_idx = find(unique_roll == data.roll(i));
        vol_idx = find(unique_vol == data.vol(i));
        
        % Store mass properties in the corresponding cell
        fuelDataArray{pitch_idx, roll_idx, vol_idx} = data{i, 4:end}; % Store from cgx onwards
    end
end
